import Foundation

@main struct RecordAcknowledgementIntegrationTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() async {
        let names = ["successful", "failedExit", "malformed", "replacedOutput", "wrongOutput", "notPublished", "symlinkRecord", "cancelled"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try await check(name); print("PASS " + name) } catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    @MainActor static func check(_ name: String) async throws {
        func require(_ value: Bool, _ message: String) throws { if !value { throw Failure(message: message) } }
        let env = ProcessInfo.processInfo.environment
        guard let base = env["DICOM_TEST_TMPDIR"], let fixture = env["DICOM_RECORD_WORKER"], let python = env["DICOM_TEST_PYTHON"] else { throw Failure(message: "explicit fixture/runtime locations required") }
        let root = URL(fileURLWithPath: base).appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let suite = "RecordAcknowledgement." + UUID().uuidString
        guard let defaults = UserDefaults(suiteName: suite) else { throw Failure(message: "preferences") }
        defer { defaults.removePersistentDomain(forName: suite) }
        let output = root.appendingPathComponent("output"), records = root.appendingPathComponent("records")
        let worker = EngineRunner(command: { args in (URL(fileURLWithPath: python), ["-I", "-B", "-u", fixture, name, output.path] + args) })
        let model = BatchModel(defaults: defaults); model.outputParent = root
        model.launch(arguments: [], isScan: false, output: output, worker: worker, journalDirectory: records)
        let deadline = Date().addingTimeInterval(8)
        var cancelRequested = false
        while model.busy && Date() < deadline {
            if name == "cancelled" && !cancelRequested && model.processed > 0 { cancelRequested = true; model.cancel() }
            try await Task.sleep(for: .milliseconds(2))
        }
        if model.busy { worker.cancel(); throw Failure(message: "timeout") }
        let files = try FileManager.default.contentsOfDirectory(at: records, includingPropertiesForKeys: nil)
        let journals = files.filter { $0.pathExtension == "json" }
        if name == "successful" {
            try require(model.summary?.files == 2 && model.canInspectOutput && journals.isEmpty, "accepted exit acknowledges matching published record")
        } else {
            try require(journals.count == 1, "unsafe or uncertain acknowledgement retains unique record")
            if ["failedExit", "malformed", "cancelled"].contains(name) {
                try require(model.summary == nil && model.errorMessage != nil && !model.canAnonymize, "failure or uncertainty cannot create accepted completion")
            }
        }
        let original = name == "replacedOutput" ? root.appendingPathComponent("original-output") : output
        try require(try String(contentsOf: original.appendingPathComponent("synthetic-marker.txt"), encoding: .utf8) == "synthetic output preserved\n", "record retirement cannot delete batch data")
        if name == "replacedOutput" {
            try require(FileManager.default.fileExists(atPath: output.appendingPathComponent("replacement-marker.txt").path), "replacement output untouched")
        }
        if name == "symlinkRecord" { try require(files.contains { $0.pathExtension == "target" }, "symlink target untouched") }
        if name == "cancelled" { try require(cancelRequested, "running worker cancellation exercised") }
    }
}
