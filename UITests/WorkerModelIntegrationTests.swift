import Foundation

// CLI-only synthetic subprocesses enter BatchModel's production launch reducer.
@main struct WorkerModelIntegrationTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() async {
        let names = ["successfulEOF", "completeNonzeroExit", "malformedAfterComplete", "abruptExit", "acknowledgedCancellation", "lateCancellationCompletion", "cleanupFailureVetoesQuit", "safeErrorPreserved"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try await check(name); print("PASS " + name) } catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    @MainActor static func check(_ name: String) async throws {
        func require(_ value: Bool, _ message: String) throws { if !value { throw Failure(message: message) } }
        let suite = "WorkerModel." + UUID().uuidString
        guard let defaults = UserDefaults(suiteName: suite) else { throw Failure(message: "preferences") }
        defer { defaults.removePersistentDomain(forName: suite) }
        let base = URL(fileURLWithPath: ProcessInfo.processInfo.environment["DICOM_TEST_TMPDIR"] ?? NSTemporaryDirectory())
        let root = base.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let output = root.appendingPathComponent("output"), staging = root.appendingPathComponent(".dicom-batch-fixture")
        let complete = "printf '{\"event\":\"complete\",\"processed\":2,\"patients\":1,\"excluded_files\":0}'"
        let progress = "printf '{\"event\":\"progress\",\"processed\":1,\"total_files\":2}\\n'"
        let script: String
        switch name {
        case "successfulEOF": script = complete
        case "completeNonzeroExit": script = complete + "; exit 7"
        case "malformedAfterComplete": script = complete + "; printf '\\n{broken'"
        case "abruptExit": script = progress + "; kill -KILL $$"
        case "acknowledgedCancellation":
            script = "trap 'printf \"%s\\n\" \"$1\"; exit 1' TERM; " + progress + "; while :; do sleep 0.02; done"
        case "lateCancellationCompletion":
            script = "trap 'exit 0' TERM; " + complete + "; printf '\\n'; while :; do sleep 0.02; done"
        case "cleanupFailureVetoesQuit":
            script = "trap 'printf \"%s\\n\" \"$1\"; exit 1' TERM; " + progress + "; while :; do sleep 0.02; done"
        case "safeErrorPreserved": script = "printf '{\"event\":\"error\",\"message\":\"Synthetic safe write failure\",\"cancelled\":false,\"cleanup_failed\":false}\\n'; exit 1"
        default: throw Failure(message: "unknown")
        }
        let errorData: [String: Any] = ["event": "error", "message": name == "acknowledgedCancellation" ? "Processing was cancelled. No completed output was published." : "Incomplete output could not be removed.", "cancelled": true, "cleanup_failed": name != "acknowledgedCancellation", "staging_path": staging.path]
        let cleanupJSON = String(decoding: try JSONSerialization.data(withJSONObject: errorData), as: UTF8.self)
        let worker = EngineRunner(command: { args in
            // Ensure the actual model supplied its private operation record argument.
            guard args.contains("--journal") else { return nil }
            return (URL(fileURLWithPath: "/bin/sh"), ["-c", script, "fixture", cleanupJSON])
        })
        let model = BatchModel(defaults: defaults); model.outputParent = root
        model.launch(arguments: [], isScan: false, output: output, worker: worker, journalDirectory: root.appendingPathComponent("records"))
        let deadline = Date().addingTimeInterval(8)
        var requested = false
        var quitReply: Bool?
        while model.busy && Date() < deadline {
            if !requested && model.processed > 0 && ["acknowledgedCancellation", "lateCancellationCompletion", "cleanupFailureVetoesQuit"].contains(name) {
                requested = true
                if name == "cleanupFailureVetoesQuit" { model.prepareToQuit { quitReply = $0 } }
                else { model.cancel() }
            }
            try await Task.sleep(for: .milliseconds(2))
        }
        if model.busy { worker.cancel(); throw Failure(message: "worker timeout") }
        try require(!model.scanning && !model.cancelling, "exit clears activity state")
        switch name {
        case "successfulEOF", "lateCancellationCompletion":
            try require(model.summary?.files == 2 && model.completedOutput?.path == output.path && model.canInspectOutput && model.errorMessage?.contains("local recovery record") == true && !model.hasBlockingProblem, "accepted completion survives absent synthetic recovery record with a warning")
            if name == "lateCancellationCompletion" { try require(requested, "late cancellation exercised") }
        case "completeNonzeroExit", "malformedAfterComplete", "abruptExit":
            try require(model.summary == nil && model.completedOutput == nil && !model.canAnonymize, "no false completion/readiness")
            try require(model.errorMessage?.contains("may already be present") == true && model.problemURL?.path == output.path, "publication uncertainty and inspection location retained")
        case "acknowledgedCancellation":
            try require(requested && model.summary == nil && model.errorMessage == nil && model.status == "Cancelled. No completed batch was published.", "only worker acknowledgement reports clean cancellation: requested=\(requested), status=\(model.status), error=\(model.errorMessage ?? "nil")")
        case "cleanupFailureVetoesQuit":
            try require(requested && quitReply == false && model.summary == nil && model.cleanupIncomplete && model.problemURL?.path == staging.path && !model.canAnonymize, "cleanup warning survives cancellation and vetoes quit: requested=\(requested), quit=\(String(describing: quitReply)), cleanup=\(model.cleanupIncomplete), error=\(model.errorMessage ?? "nil"), location=\(model.problemURL?.path ?? "nil")")
        case "safeErrorPreserved":
            try require(model.errorMessage == "Synthetic safe write failure" && model.summary == nil && !model.canAnonymize, "safe error survives process failure")
        default: break
        }
    }
}
