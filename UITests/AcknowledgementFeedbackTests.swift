import Foundation

@main struct AcknowledgementFeedbackTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() async {
        let names = ["removeFailure", "wrongOutput", "notPublished", "missingRecord", "successfulRetirement", "dismissWarning", "noJournal", "pendingQuit"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try await check(name); print("PASS " + name) } catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    @MainActor static func check(_ name: String) async throws {
        func require(_ value: Bool, _ message: String) throws { if !value { throw Failure(message: message) } }
        let env = ProcessInfo.processInfo.environment
        guard let base = env["DICOM_TEST_TMPDIR"], let fixture = env["DICOM_RECORD_WORKER"], let python = env["DICOM_TEST_PYTHON"], let defaults = UserDefaults(suiteName: UUID().uuidString) else { throw Failure(message: "fixtures") }
        let root = URL(fileURLWithPath: base).appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let output = root.appendingPathComponent("output"), records = root.appendingPathComponent("records")
        var removalCalls = 0
        let model = BatchModel(defaults: defaults, removeRecoveryRecord: { url in
            removalCalls += 1
            if ["removeFailure", "dismissWarning", "pendingQuit"].contains(name) { throw NSError(domain: NSCocoaErrorDomain, code: NSFileWriteNoPermissionError) }
            try FileManager.default.removeItem(at: url)
        })
        model.outputParent = root
        let worker = EngineRunner(command: { args in
            if name == "noJournal" { return (URL(fileURLWithPath: "/bin/sh"), ["-c", "printf '{\"event\":\"complete\",\"processed\":2,\"patients\":1}'"]) }
            return (URL(fileURLWithPath: python), ["-I", "-B", "-u", fixture, name, output.path] + args)
        })
        model.launch(arguments: [], isScan: false, output: output, worker: worker, journalDirectory: name == "noJournal" ? nil : records)
        let deadline = Date().addingTimeInterval(8)
        var quitReply: Bool?
        var quitRequested = false
        while model.busy && Date() < deadline {
            if name == "pendingQuit" && !quitRequested && model.processed > 0 {
                quitRequested = true; model.prepareToQuit { quitReply = $0 }
            }
            try await Task.sleep(for: .milliseconds(2))
        }
        if model.busy { worker.cancel(); throw Failure(message: "timeout") }
        try require(model.summary?.files == 2 && model.completedOutput?.path == output.path && model.canInspectOutput && !model.hasBlockingProblem, "local acknowledgement cannot invalidate successful completion")
        if ["successfulRetirement", "noJournal"].contains(name) {
            try require(model.errorMessage == nil, "no warning for retired or unrequested record")
        } else {
            try require(model.errorMessage?.contains("batch completed") == true && model.problem == .report && model.problemTitle.contains("recovery record") && model.recoveryTitle == "Reveal Output", "nonblocking feedback uses existing completion/recovery actions")
            try require(model.recoveryMessage.contains("does not remove"), "dismissal does not imply record retirement")
        }
        if ["wrongOutput", "notPublished", "missingRecord", "noJournal"].contains(name) { try require(removalCalls == 0, "unsafe/unrequested record never reaches removal") }
        if name == "successfulRetirement" { try require(removalCalls == 1, "matching record retired once") }
        if name != "noJournal" {
            let files = try FileManager.default.contentsOfDirectory(at: records, includingPropertiesForKeys: nil)
            let shouldRemain = !["successfulRetirement", "missingRecord"].contains(name)
            try require(files.filter { $0.pathExtension == "json" }.count == (shouldRemain ? 1 : 0), "record retention remains conservative")
            try require(try String(contentsOf: output.appendingPathComponent("synthetic-marker.txt"), encoding: .utf8) == "synthetic output preserved\n", "batch data preserved")
            if name == "dismissWarning" {
                model.dismissReportProblem()
                try require(model.errorMessage == nil && model.summary?.files == 2 && model.canInspectOutput && !files.isEmpty, "dismiss preserves completion and retained record")
            }
        }
        if name == "pendingQuit" { try require(quitRequested && quitReply == true, "confirmed completion with local-record warning does not veto pending quit") }
    }
}
