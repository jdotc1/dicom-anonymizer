import Foundation

// Headless protocol fixtures only; no application instance or imaging data.
@main struct BoundedWorkerTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() async {
        let names = ["exactLimit", "splitOverflow", "singleChunkRecovery", "discardedEOF",
                     "consecutiveOversized", "fragmentedUTF8AtLimit", "errorAfterOverflow",
                     "completionAfterOverflow", "completionBeforeOverflow", "workerComplete",
                     "workerSafeError", "workerPipeDrain", "workerCancelledOverflow"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try await check(name); print("PASS " + name) }
            catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }

    @MainActor static func check(_ name: String) async throws {
        func require(_ condition: Bool, _ message: String) throws {
            if !condition { throw Failure(message: message) }
        }
        func bytes(_ value: String) -> Data { Data(value.utf8) }
        var stream = EngineEventStream(maxFrameBytes: 16)
        switch name {
        case "exactLimit":
            let expected = Data(repeating: 65, count: 16)
            try require(stream.append(expected).isEmpty && stream.bufferedByteCount == 16, "exact limit retained")
            try require(stream.append(bytes("\n")) == [expected] && stream.bufferedByteCount == 0, "newline not counted")
        case "splitOverflow":
            _ = stream.append(Data(repeating: 65, count: 15))
            let marker = stream.append(bytes("BC"))
            try require(marker == [Data([0])] && stream.bufferedByteCount == 0, "overflow emits one bounded failure marker")
            for _ in 0..<8 {
                try require(stream.append(Data(repeating: 65, count: 32)).isEmpty && stream.bufferedByteCount == 0, "discard without accumulation")
            }
            try require(stream.append(bytes("\n{}\n")) == [bytes("{}")], "next frame preserved")
        case "singleChunkRecovery":
            let frames = stream.append(Data(repeating: 65, count: 64) + bytes("\n{}\n"))
            try require(frames == [Data([0]), bytes("{}")] && stream.bufferedByteCount == 0, "large chunk never retained as pending")
        case "discardedEOF":
            try require(stream.append(Data(repeating: 65, count: 17)) == [Data([0])], "unterminated overflow detected immediately")
            try require(stream.finish().isEmpty && stream.finish().isEmpty && stream.bufferedByteCount == 0, "no duplicated error or leaked tail at EOF")
        case "consecutiveOversized":
            let frame = Data(repeating: 65, count: 17) + bytes("\n")
            try require(stream.append(frame + frame + bytes("ok")) == [Data([0]), Data([0])], "one marker for each oversized frame")
            try require(stream.finish() == [bytes("ok")], "valid final tail retained")
        case "fragmentedUTF8AtLimit":
            let expected = bytes("é界")
            var exact = EngineEventStream(maxFrameBytes: expected.count)
            for value in expected { try require(exact.append(Data([value])).isEmpty, "partial UTF8 buffered as bytes") }
            try require(exact.finish() == [expected], "byte limit preserves fragmented UTF8")
        case "errorAfterOverflow", "completionAfterOverflow", "completionBeforeOverflow":
            var framing = EngineEventStream(maxFrameBytes: 128)
            let delivery = EngineEventDelivery()
            var events: [[String: Any]] = []
            let valid = name == "errorAfterOverflow"
                ? "{\"event\":\"error\",\"message\":\"Safe failure\",\"cleanup_failed\":true}\n"
                : "{\"event\":\"complete\"}\n"
            let input = name == "completionBeforeOverflow"
                ? bytes(valid) + Data(repeating: 65, count: 129)
                : Data(repeating: 65, count: 129) + bytes("\n" + valid)
            delivery.deliver(framing.append(input) + framing.finish(), event: { events.append($0) })
            var code: Int32 = 0
            delivery.finish(code: 0, cancelled: false, event: { events.append($0) }, finished: { code = $0; _ = $1 })
            try require(delivery.malformed && code == 1, "no nominal success after overflow")
            if name == "errorAfterOverflow" {
                try require(events.count == 1 && events[0]["cleanup_failed"] as? Bool == true, "safe cleanup error survives")
            } else {
                try require(delivery.sawComplete && events.first?["event"] as? String == "complete" && events.last?["output_published"] as? Bool == true, "publication evidence survives with uncertainty")
            }
        case "workerComplete", "workerSafeError", "workerPipeDrain", "workerCancelledOverflow":
            try await worker(name)
        default: throw Failure(message: "Unknown case")
        }
    }

    @MainActor static func worker(_ name: String) async throws {
        let suite = "BoundedWorker." + UUID().uuidString
        guard let defaults = UserDefaults(suiteName: suite) else { throw Failure(message: "preferences") }
        defer { defaults.removePersistentDomain(forName: suite) }
        let base = URL(fileURLWithPath: ProcessInfo.processInfo.environment["DICOM_TEST_TMPDIR"] ?? NSTemporaryDirectory())
        let root = base.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let output = root.appendingPathComponent("output")
        let oversized = name == "workerPipeDrain"
            ? "i=0; while [ $i -lt 32 ]; do printf '%04096d\\n' 0; i=$((i+1)); done; "
            : "printf '%01024d\\n' 0; "
        let tail = name == "workerSafeError"
            ? "printf '%s\\n' '{\"event\":\"error\",\"message\":\"Safe fixture error\",\"cleanup_failed\":false}'; exit 1"
            : "printf '%s' '{\"event\":\"complete\",\"processed\":1,\"patients\":1}'"
        let script = name == "workerCancelledOverflow"
            ? "trap 'exit 130' TERM; printf '%s\\n' '{\"event\":\"progress\",\"processed\":1,\"total_files\":2}'; " + oversized + "while :; do sleep 0.02; done"
            : oversized + tail
        let runner = EngineRunner(command: { _ in
            (URL(fileURLWithPath: "/bin/sh"), ["-c", script])
        }, maxFrameBytes: 128)
        let model = BatchModel(defaults: defaults)
        model.outputParent = root
        model.launch(arguments: [], isScan: false, output: output, worker: runner,
                     journalDirectory: root.appendingPathComponent("records"))
        let deadline = Date().addingTimeInterval(8)
        var cancelled = false
        while model.busy && Date() < deadline {
            if name == "workerCancelledOverflow" && model.processed > 0 && !cancelled {
                model.cancel(); cancelled = true
            }
            try await Task.sleep(for: .milliseconds(2))
        }
        if name == "workerCancelledOverflow" && !cancelled { throw Failure(message: "cancellation not exercised") }
        if model.busy { runner.cancel(); throw Failure(message: "worker timeout") }
        guard model.summary == nil && !model.canAnonymize else { throw Failure(message: "false success after oversized response") }
        if name == "workerSafeError" {
            guard model.errorMessage == "Safe fixture error" else { throw Failure(message: "safe error lost") }
        } else {
            guard model.errorMessage?.contains("may already be present") == true,
                  model.problemURL?.path == output.path else { throw Failure(message: "publication uncertainty lost") }
        }
    }
}
