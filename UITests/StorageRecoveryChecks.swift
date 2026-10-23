import Foundation

private struct StorageRecoveryFailure: Error { let message: String }

@main
@MainActor
struct StorageRecoveryChecks {
    static func main() throws {
        try run("spaceDetailsUseExistingOutputRecovery")
        try run("permissionAndAvailabilityReasonsHaveMatchingGuidance")
        try run("conflictAndUnknownDestinationFailuresStayOutputProblems")
        try run("validReplacementPreservesPreviewWithoutStartingWorker")
        try run("invalidReplacementKeepsValidPreferenceAndCorrectsReason")
        try run("cleanupFailureOutranksStorageAndRetainsQuitWarning")
        try run("inputFailureDoesNotBecomeOutputFailure")
        try run("scanIdleAndUnknownIssueEventsCannotClaimStorageFailure")
        try run("publishedUnconfirmedIsNotReclassifiedAsStorage")
        try run("storageFailureWithoutAcceptedPreviewCannotBecomeReady")
        try run("nextRunResetsStorageReasonAndCleanErrorCanQuit")
        print("PASS: 11 focused storage/output recovery model checks")
    }

    @MainActor static func run(_ name: String) throws {
        let suite = "DICOMStorageRecoveryTests." + UUID().uuidString
        guard let defaults = UserDefaults(suiteName: suite) else { throw StorageRecoveryFailure(message: "Isolated preferences unavailable") }
        defer { defaults.removePersistentDomain(forName: suite) }
        let root = URL(fileURLWithPath: "DICOM-Storage-Recovery-20261023/model-fixtures", isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
        let first = root.appendingPathComponent("First output", isDirectory: true)
        let replacement = root.appendingPathComponent("Replacement output", isDirectory: true)
        try FileManager.default.createDirectory(at: first, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: replacement, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let model = BatchModel(defaults: defaults)
        model.setOutputParent(first)
        model.source = root.appendingPathComponent("Input", isDirectory: true)
        model.patients = [PatientRow(id: "00001", files: 20, series: 2)]
        model.total = 20; model.ready = true
        let output = first.appendingPathComponent("Anonymized_fixture", isDirectory: true)
        let stage = first.appendingPathComponent(".dicom-batch-fixture", isDirectory: true)
        model.beginRunState(isScan: false, output: output)
        func failure(_ issue: String, _ message: String = "Safe output failure") {
            model.receive(["event": "error", "message": message, "output_issue": issue, "cancelled": false, "cleanup_failed": false])
        }
        func finish() { model.finishRun(code: 1, cancelled: false, isScan: false, output: output) }
        func require(_ value: Bool, _ message: String) throws {
            if !value { throw StorageRecoveryFailure(message: name + ": " + message) }
        }
        switch name {
        case "spaceDetailsUseExistingOutputRecovery":
            let message = "Not enough free disk space. Approximately 4.0 GiB is needed; 1.0 GiB is available. This is an estimate."
            model.receive(["event": "error", "message": message, "output_issue": "space", "required_bytes": 4_294_967_296, "available_bytes": 1_073_741_824])
            finish()
            try require(model.problem == .output && model.outputIssue == .space && model.problemTitle == "Not enough disk space", "Space failure must use existing output recovery")
            try require(model.errorMessage == message && model.problemURL == first && model.recoveryTitle == "Choose Location…", "Keep safe estimate details and this operation's output parent")
            try require(model.recoveryMessage.contains("approximate") && model.ready && !model.canAnonymize, "Explain estimate limits and block processing until recovery")
        case "permissionAndAvailabilityReasonsHaveMatchingGuidance":
            failure("permissions"); finish()
            try require(model.problemTitle == "Output location is not writable" && model.recoveryMessage.contains("write access"), "Write failures need permission recovery guidance")
            model.beginRunState(isScan: false, output: output); failure("unavailable"); finish()
            try require(model.problemTitle == "Output location unavailable" && model.recoveryMessage.contains("Reconnect"), "Unavailable locations need reconnection guidance")
        case "conflictAndUnknownDestinationFailuresStayOutputProblems":
            failure("conflict"); finish()
            try require(model.problem == .output && model.problemTitle == "Choose another output location" && model.recoveryMessage.contains("never overwritten"), "Conflict must preserve no-overwrite guidance")
            model.beginRunState(isScan: false, output: output); failure("unknown"); finish()
            try require(model.problem == .output && model.recoveryMessage.contains("Check the output volume"), "Unknown destination failures should retain output recovery")
        case "validReplacementPreservesPreviewWithoutStartingWorker":
            model.receive(["event": "progress", "processed": 5, "total_files": 20])
            failure("space"); finish()
            model.setOutputParent(replacement)
            try require(model.outputParent == replacement && model.errorMessage == nil && model.outputIssue == nil, "Valid replacement clears storage error")
            try require(model.ready && model.canAnonymize && !model.busy && model.patients.count == 1 && model.total == 20 && model.processed == 5, "Replacement must preserve accepted preview and not start a rescan")
            try require(defaults.string(forKey: BatchModel.outputDefaultsKey) == replacement.path && model.status.contains("Ready"), "Persist only valid replacement and return to ready")
        case "invalidReplacementKeepsValidPreferenceAndCorrectsReason":
            failure("space"); finish()
            let missing = root.appendingPathComponent("Disconnected output")
            model.setOutputParent(missing)
            try require(model.outputParent == first && defaults.string(forKey: BatchModel.outputDefaultsKey) == first.path, "Invalid selection must preserve last valid preference")
            try require(model.outputIssue == .unavailable && model.problemURL == missing && model.problemTitle == "Output location unavailable", "Invalid replacement must not retain stale disk-full title")
        case "cleanupFailureOutranksStorageAndRetainsQuitWarning":
            var quitReply: Bool?
            model.prepareToQuit { quitReply = $0 }
            model.receive(["event": "error", "message": "The output ran out of space. Incomplete output could not be removed.", "output_issue": "space", "cleanup_failed": true, "staging_path": stage.path])
            model.finishRun(code: 1, cancelled: true, isScan: false, output: output)
            try require(model.cleanupIncomplete && model.problemTitle == "Incomplete output needs attention" && model.problemURL == stage && !model.ready && quitReply == false, "Cleanup failure must keep priority over storage recovery")
            let message = model.errorMessage
            model.setOutputParent(root.appendingPathComponent("Missing replacement"))
            try require(model.errorMessage == message && model.problemURL == stage, "Invalid replacement must not erase the original cleanup warning")
        case "inputFailureDoesNotBecomeOutputFailure":
            model.receive(["event": "error", "message": "Input files cannot be read. Check permissions and available local storage."])
            finish()
            try require(model.problem == .processing && model.outputIssue == nil && !model.ready, "Input errors must retain processing recovery")
        case "scanIdleAndUnknownIssueEventsCannotClaimStorageFailure":
            model.beginRunState(isScan: true, output: nil); failure("space")
            try require(model.problem == .processing && model.outputIssue == nil, "Scan errors cannot claim destination writes failed")
            model.finishRun(code: 1, cancelled: false, isScan: true, output: nil); failure("space")
            try require(model.problem == .processing && model.outputIssue == nil, "Idle events cannot adopt operation-specific output context")
            model.beginRunState(isScan: false, output: nil); failure("space")
            try require(model.problem == .processing && model.outputIssue == nil, "Storage recovery requires this operation's destination")
            model.beginRunState(isScan: false, output: output); failure("not-a-storage-reason")
            try require(model.problem == .processing && model.outputIssue == nil, "Unknown event reason must use conservative generic recovery")
        case "publishedUnconfirmedIsNotReclassifiedAsStorage":
            var quitReply: Bool?
            model.prepareToQuit { quitReply = $0 }
            model.receive(["event": "error", "message": "Output was published, but completion could not be confirmed.", "output_issue": "space", "output_published": true])
            model.finishRun(code: 1, cancelled: true, isScan: false, output: output)
            try require(model.problem == .processing && model.outputIssue == nil && model.problemURL == output && quitReply == false, "Publication uncertainty must retain its accepted recovery priority")
        case "storageFailureWithoutAcceptedPreviewCannotBecomeReady":
            model.ready = false; model.patients = []; model.total = 0
            failure("permissions"); finish(); model.setOutputParent(replacement)
            try require(!model.ready && !model.canAnonymize && model.errorMessage == nil, "Choosing output must not invent an accepted input preview")
        case "nextRunResetsStorageReasonAndCleanErrorCanQuit":
            failure("space"); finish()
            model.beginRunState(isScan: false, output: output)
            try require(model.outputIssue == nil && model.errorMessage == nil, "Storage reason must not leak across operations")
            var quitReply: Bool?
            model.prepareToQuit { quitReply = $0 }
            failure("permissions")
            model.finishRun(code: 1, cancelled: true, isScan: false, output: output)
            try require(quitReply == true && model.problem == .output && model.errorMessage != nil, "A safely cleaned storage failure may finish requested Quit without being relabelled cancellation")
        default: throw StorageRecoveryFailure(message: "Unknown fixture " + name)
        }
    }
}
