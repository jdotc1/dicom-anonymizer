import Foundation

@main struct RecoveryConsistencyTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() async {
        let names = ["reportFailureDismissRestores", "reportSuccessRestores", "failureThenSuccessRestores", "explicitWarningDismiss", "newOperationResetsWarning", "nonblockingReportFailure", "repeatedReportCycles", "ordinaryReportRecovery", "outOfOrderSnapshots", "duplicateSnapshot", "oldSnapshotAfterIdleRun", "oldFailureAfterEmptyScan", "latestScanClearsOwnError", "currentChainTokens"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try await check(name); print("PASS " + name) } catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    @MainActor static func check(_ name: String) async throws {
        func require(_ value: Bool, _ message: String) throws { if !value { throw Failure(message: message) } }
        guard let base = ProcessInfo.processInfo.environment["DICOM_TEST_TMPDIR"], let defaults = UserDefaults(suiteName: UUID().uuidString) else { throw Failure(message: "fixture") }
        let root = URL(fileURLWithPath: base).appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let model = BatchModel(defaults: defaults), output = root.appendingPathComponent("output")
        func notice(_ text: String) -> InterruptionScan {
            InterruptionScan(notice: InterruptionNotice(message: text, location: root, ownedStaging: false, publicationPossible: true), hasLiveOwners: false, hasPendingLocations: true)
        }
        let empty = InterruptionScan(notice: nil, hasLiveOwners: false)
        let failedScan = InterruptionScan(notice: nil, hasLiveOwners: false, unavailableDirectory: root)
        let reportCases = ["reportFailureDismissRestores", "reportSuccessRestores", "failureThenSuccessRestores", "explicitWarningDismiss", "newOperationResetsWarning", "nonblockingReportFailure", "repeatedReportCycles", "ordinaryReportRecovery"]
        if reportCases.contains(name) {
            let worker = EngineRunner(command: { _ in
                (URL(fileURLWithPath: "/bin/sh"), ["-c", "printf '{\"event\":\"complete\",\"processed\":2,\"patients\":1}'"])
            })
            model.outputParent = root
            model.launch(arguments: [], isScan: false, output: output, worker: worker,
                         journalDirectory: name == "ordinaryReportRecovery" ? nil : root.appendingPathComponent("records"))
            let deadline = Date().addingTimeInterval(8)
            while model.busy && Date() < deadline { try await Task.sleep(for: .milliseconds(2)) }
            if model.busy { worker.cancel(); throw Failure(message: "timeout") }
            try require(model.summary?.files == 2 && model.canInspectOutput, "synthetic completion retained")
            if name != "ordinaryReportRecovery" { try require(model.problemTitle.contains("recovery record"), "selected missing record yields acknowledgement warning") }
        }
        switch name {
        case "reportFailureDismissRestores":
            model.reportOpeningFailed(message: "Synthetic missing report")
            try require(model.errorMessage == "Synthetic missing report" && model.problemTitle == "Report unavailable", "report failure temporarily owns presentation")
            model.dismissReportProblem()
            try require(model.problemTitle.contains("recovery record") && model.summary?.files == 2, "dismiss report error restores unresolved-record warning")
        case "reportSuccessRestores":
            model.reportOpeningSucceeded()
            try require(model.problemTitle.contains("recovery record"), "opening report does not acknowledge record")
        case "failureThenSuccessRestores":
            model.reportOpeningFailed(message: "Synthetic launch failure"); model.reportOpeningSucceeded()
            try require(model.problemTitle.contains("recovery record") && model.canInspectOutput, "report recovery preserves independent acknowledgement warning")
        case "explicitWarningDismiss":
            model.dismissReportProblem()
            try require(model.errorMessage == nil && model.summary?.files == 2, "explicit dismissal preserves completion")
            model.reportOpeningFailed(message: "Later report error"); model.dismissReportProblem()
            try require(model.errorMessage == nil, "explicitly dismissed warning does not return through report actions")
        case "newOperationResetsWarning":
            model.beginRunState(isScan: false, output: root.appendingPathComponent("new-output"))
            model.receive(["event": "complete", "processed": 3, "patients": 1])
            model.finishRun(code: 0, cancelled: false, isScan: false, output: root.appendingPathComponent("new-output"))
            model.reportOpeningFailed(message: "New report failure"); model.dismissReportProblem()
            try require(model.errorMessage == nil && model.summary?.files == 3, "old warning cannot attach to next operation")
        case "nonblockingReportFailure":
            model.reportOpeningFailed(message: "Synthetic report error")
            try require(!model.hasBlockingProblem && model.canInspectOutput && model.summary?.files == 2 && model.recoveryTitle == "Reveal Output", "existing actions and completion retained")
        case "repeatedReportCycles":
            for index in 1...2 {
                model.reportOpeningFailed(message: "Report error \(index)"); model.reportOpeningSucceeded()
                try require(model.problemTitle.contains("recovery record"), "each report recovery restores same warning")
            }
        case "ordinaryReportRecovery":
            model.reportOpeningFailed(message: "Ordinary report error"); model.reportOpeningSucceeded()
            try require(model.errorMessage == nil && model.summary?.files == 2, "no acknowledgement warning invented")
        case "outOfOrderSnapshots":
            let old = model.beginRecoveryInspection(), latest = model.beginRecoveryInspection()
            _ = model.receiveInterruptionScan(notice("latest"), generation: latest)
            try require(!model.receiveInterruptionScan(notice("old"), generation: old) && model.errorMessage == "latest", "old inspection cannot overwrite newer inspection")
        case "duplicateSnapshot":
            let token = model.beginRecoveryInspection(); _ = model.receiveInterruptionScan(notice("once"), generation: token)
            try require(!model.receiveInterruptionScan(empty, generation: token) && model.errorMessage == "once", "consumed result cannot be delivered twice")
        case "oldSnapshotAfterIdleRun":
            let token = model.beginRecoveryInspection()
            model.beginRunState(isScan: true, output: nil)
            model.receive(["event": "scan", "patients": [], "total_files": 0])
            model.finishRun(code: 0, cancelled: false, isScan: true, output: nil)
            try require(!model.busy && model.source == nil && model.summary == nil && model.errorMessage == nil, "model returned to idle-shaped state")
            try require(!model.receiveInterruptionScan(notice("old"), generation: token) && model.errorMessage == nil, "generation protects intervening action even after idle return")
        case "oldFailureAfterEmptyScan":
            let old = model.beginRecoveryInspection(), latest = model.beginRecoveryInspection()
            _ = model.receiveInterruptionScan(empty, generation: latest)
            try require(!model.receiveInterruptionScan(failedScan, generation: old) && model.errorMessage == nil, "old I/O failure cannot replace new successful listing")
        case "latestScanClearsOwnError":
            let old = model.beginRecoveryInspection()
            _ = model.receiveInterruptionScan(failedScan, generation: model.beginRecoveryInspection())
            try require(model.errorMessage != nil, "current failure visible")
            _ = model.receiveInterruptionScan(empty, generation: model.beginRecoveryInspection())
            try require(!model.receiveInterruptionScan(notice("old"), generation: old) && model.errorMessage == nil, "clearing own error cannot revive older inspection")
        case "currentChainTokens":
            let token = model.beginRecoveryInspection()
            try require(model.receiveInterruptionScan(notice("pending"), generation: token) && model.recoveryGeneration != token, "accepted result consumes token and permits current recheck")
            let next = model.beginRecoveryInspection()
            try require(!model.receiveInterruptionScan(empty, generation: next) && model.errorMessage == nil, "new current observation resolves own notice and stops chain")
        default: throw Failure(message: "unknown")
        }
    }
}
