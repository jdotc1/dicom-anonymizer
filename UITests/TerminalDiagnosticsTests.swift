import Foundation

@main struct TerminalDiagnosticsTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() async {
        let names = ["duplicateIdentical", "duplicateOptional", "duplicateConflict", "errorZeroExit",
                     "specificCleanup", "cleanupBeforeComplete", "formatIdentity", "formatUnknown", "formatMessage", "noError",
                     "diagnosticInput", "diagnosticReset", "localErrorAfterWorker", "localErrorAfterCancellation", "directErrorVeto", "workerCompleteError",
                     "workerErrorComplete", "workerDuplicateConflict", "workerCleanupConflict",
                     "workerCancelConflict", "workerValidOptional", "workerCompleteEOF", "workerDuplicateOmitted",
                     "workerCompleteCancelNoError", "workerCompleteNonzero", "workerMalformedComplete"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try await check(name); print("PASS " + name) }
            catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }

    @MainActor static func check(_ name: String) async throws {
        func require(_ value: Bool, _ message: String) throws { if !value { throw Failure(message: message) } }
        func data(_ value: String) -> Data { Data(value.utf8) }
        if name.hasPrefix("worker") { try await worker(name); return }
        if name.hasPrefix("format") {
            let message = "Recovery details\n/synthetic/batch/00001 · inspect output"
            let details = ErrorDetails(version: name == "formatUnknown" ? " " : "2.0", build: name == "formatUnknown" ? "" : "32",
                                       phase: "Auditing DICOM files", category: "cleanup", outcome: "Output publication uncertain", message: message).text
            if name == "formatIdentity" { try require(details.contains("2.0 (build 32)") && details.contains("Operation: Auditing DICOM files") && details.contains("Category: cleanup") && details.contains("Outcome: Output publication uncertain"), "identity and operation context") }
            if name == "formatUnknown" { try require(details.contains("unknown (build unknown)"), "missing metadata explicit") }
            if name == "formatMessage" { try require(details.hasSuffix(message), "existing multiline recovery detail preserved exactly") }
            return
        }
        let suite = "Terminal." + UUID().uuidString
        guard let defaults = UserDefaults(suiteName: suite) else { throw Failure(message: "preferences") }
        defer { defaults.removePersistentDomain(forName: suite) }
        let model = BatchModel(defaults: defaults)
        if name == "noError" { try require(model.errorDetails(version: "2", build: "32") == nil, "nothing to copy"); return }
        if name == "diagnosticInput" {
            model.problem = .input; model.errorMessage = "Choose numeric patient folders."
            let details = model.errorDetails(version: "2", build: "32") ?? ""
            try require(details.contains("Operation: Input selection") && details.contains("Category: input") && details.contains("Completion not confirmed"), "input diagnostic context")
            return
        }
        if name == "localErrorAfterCancellation" {
            model.beginRunState(isScan: false, output: URL(fileURLWithPath: "/synthetic/output"))
            model.receive(["event":"error", "message":"Cancellation acknowledged", "cancelled":true])
            model.finishRun(code: 130, cancelled: true, isScan: false, output: URL(fileURLWithPath: "/synthetic/output"))
            model.setOutputParent(URL(fileURLWithPath: "/nonexistent/terminal-fixture-output"))
            let details = model.errorDetails(version: "2", build: "32") ?? ""
            try require(details.contains("Operation: Output location") && details.contains("Completion not confirmed") && !details.contains("Cancellation acknowledged"), "old cancellation does not describe new local error")
            return
        }
        if name == "diagnosticReset" || name == "directErrorVeto" || name == "localErrorAfterWorker" {
            model.beginRunState(isScan: false, output: URL(fileURLWithPath: "/synthetic/output"))
            model.receive(["event":"complete", "processed":1])
            model.receive(["event":"error", "message":"Safe failure", "protocol_failure":true, "output_published":true])
            model.finishRun(code: 0, cancelled: false, isScan: false, output: URL(fileURLWithPath: "/synthetic/output"))
            try require(model.summary == nil && model.errorDetails(version: "2", build: "32")?.contains("Category: worker-protocol") == true, "direct reducer cannot accept success over error")
            if name == "diagnosticReset" {
                model.beginRunState(isScan: true, output: nil)
                model.receive(["event":"error", "message":"Fresh scan failure"])
                model.finishRun(code: 1, cancelled: false, isScan: true, output: nil)
                let details = model.errorDetails(version: "2", build: "32") ?? ""
                try require(details.contains("Operation: Checking input") && details.contains("Category: processing") && !details.contains("Output publication uncertain"), "new run clears prior context")
            } else if name == "localErrorAfterWorker" {
                model.setOutputParent(URL(fileURLWithPath: "/nonexistent/terminal-fixture-output"))
                let details = model.errorDetails(version: "2", build: "32") ?? ""
                try require(details.contains("Operation: Output location") && details.contains("Category: output-unavailable") && details.contains("Completion not confirmed") && !details.contains("worker-protocol"), "new local error owns its diagnostic context")
            }
            return
        }
        let delivery = EngineEventDelivery()
        var events: [[String: Any]] = []
        let complete = "{\"event\":\"complete\",\"processed\":1}"
        let lines: [String]
        switch name {
        case "duplicateIdentical": lines = [complete, complete]
        case "duplicateOptional": lines = [complete, "{\"event\":\"complete\",\"processed\":1,\"patients\":1,\"extra\":true}"]
        case "duplicateConflict": lines = [complete, "{\"event\":\"complete\",\"processed\":2}"]
        case "errorZeroExit": lines = ["{\"event\":\"error\",\"message\":\"Safe failure\"}"]
        case "specificCleanup", "cleanupBeforeComplete":
            let cleanup = "{\"event\":\"error\",\"message\":\"Keep staging\",\"cleanup_failed\":true,\"staging_path\":\"/synthetic/.dicom-batch-owned\"}"
            let generic = "{\"event\":\"error\",\"message\":\"Later error\"}"
            lines = name == "specificCleanup" ? [cleanup, generic, complete] : [cleanup, complete, generic]
        default: throw Failure(message: "Unknown case")
        }
        // Independent delivery batches exercise terminal state across pipe reads.
        for line in lines { delivery.deliver([data(line)], event: { events.append($0) }) }
        var code: Int32 = 0
        delivery.finish(code: 0, cancelled: false, event: { events.append($0) }, finished: { code = $0; _ = $1 })
        if name == "duplicateIdentical" || name == "duplicateOptional" {
            try require(code == 0 && !delivery.terminalConflict, "compatible duplicate remains accepted")
        } else {
            try require(code == 1, "terminal failure overrides zero exit")
            if name != "errorZeroExit" { try require(delivery.terminalConflict && events.last?["output_published"] as? Bool == true, "publication uncertainty retained") }
            if name == "specificCleanup" || name == "cleanupBeforeComplete" { try require(events.last?["cleanup_failed"] as? Bool == true && events.last?["message"] as? String == "Keep staging Completion could not be confirmed. Check the output location before retrying; a completed batch may already be present.", "specific cleanup survives generic later error") }
        }
    }

    @MainActor static func worker(_ name: String) async throws {
        let suite = "TerminalWorker." + UUID().uuidString
        guard let defaults = UserDefaults(suiteName: suite) else { throw Failure(message: "preferences") }
        defer { defaults.removePersistentDomain(forName: suite) }
        let base = URL(fileURLWithPath: ProcessInfo.processInfo.environment["DICOM_TEST_TMPDIR"] ?? NSTemporaryDirectory())
        let root = base.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let output = root.appendingPathComponent("output")
        func emit(_ json: String) -> String { "printf '%s\\n' '" + json + "'; " }
        let complete = emit("{\"event\":\"complete\",\"processed\":1,\"patients\":1}")
        let error = emit("{\"event\":\"error\",\"message\":\"Safe fixture failure\",\"cancelled\":true}")
        let script: String
        switch name {
        case "workerCompleteError": script = complete + error
        case "workerCancelConflict": script = "trap 'exit 130' TERM; " + complete + error + "while :; do sleep 0.02; done"
        case "workerCompleteCancelNoError": script = "trap 'exit 130' TERM; " + complete + "while :; do sleep 0.02; done"
        case "workerCompleteNonzero": script = complete + "exit 7"
        case "workerMalformedComplete": script = complete + "printf '%s' '{broken'"
        case "workerErrorComplete": script = error + complete
        case "workerDuplicateConflict": script = complete + emit("{\"event\":\"complete\",\"processed\":2}")
        case "workerCleanupConflict":
            let payload = ["event":"error", "message":"Keep staging", "cleanup_failed":true, "staging_path":root.appendingPathComponent(".dicom-batch-owned").path] as [String: Any]
            let json = String(decoding: try JSONSerialization.data(withJSONObject: payload), as: UTF8.self)
            script = complete + emit(json)
        case "workerValidOptional": script = emit("{\"event\":\"complete\",\"processed\":1}")
        case "workerDuplicateOmitted": script = complete + emit("{\"event\":\"complete\"}")
        case "workerCompleteEOF": script = "printf '%s' '{\"event\":\"complete\",\"processed\":1}'"
        default: throw Failure(message: "Unknown worker case")
        }
        let runner = EngineRunner(command: { _ in (URL(fileURLWithPath: "/bin/sh"), ["-c", script]) })
        let model = BatchModel(defaults: defaults)
        model.outputParent = root
        model.launch(arguments: [], isScan: false, output: output, worker: runner, journalDirectory: root.appendingPathComponent("records"))
        let deadline = Date().addingTimeInterval(8)
        var quitReply: Bool?
        var cancelled = false
        while model.busy && Date() < deadline {
            if ["workerCancelConflict", "workerCompleteCancelNoError"].contains(name) && model.processed > 0 && !cancelled {
                model.prepareToQuit { quitReply = $0 }; cancelled = true
            }
            try await Task.sleep(for: .milliseconds(2))
        }
        if model.busy { runner.cancel(); throw Failure(message: "worker timeout") }
        let details = model.errorDetails(version: "2.0", build: "32") ?? ""
        if ["workerCancelConflict", "workerCompleteCancelNoError"].contains(name) && (!cancelled || quitReply != false) { throw Failure(message: "uncertain cancellation must veto quit") }
        if name == "workerValidOptional" || name == "workerCompleteEOF" || name == "workerDuplicateOmitted" {
            guard model.summary?.files == 1 && details.contains("Completed output confirmed") else { throw Failure(message: "optional completion compatibility or report warning lost") }
            if name == "workerDuplicateOmitted" && model.summary?.patients != 1 { throw Failure(message: "earlier patient count lost") }
        } else {
            guard model.summary == nil && !model.canAnonymize && details.contains("Output publication uncertain") else { throw Failure(message: "conflict reported clean success/cancellation") }
            if name == "workerCleanupConflict" {
                guard model.cleanupIncomplete && model.problemURL?.lastPathComponent == ".dicom-batch-owned" && details.contains("Category: cleanup") else { throw Failure(message: "cleanup ownership lost") }
            } else {
                guard model.problemURL == output && details.contains("Category: worker-protocol") else { throw Failure(message: "protocol context lost") }
            }
        }
    }
}
