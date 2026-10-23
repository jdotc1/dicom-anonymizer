import Foundation

private struct PublicationRecoveryFailure: Error { let message: String }

@main
@MainActor
struct PublicationRecoveryChecks {
    static func main() throws {
        try run("lateCancellationKeepsPublishedCompletion")
        try run("acknowledgedCancellationClearsOnlyCancelledError")
        try run("failedCleanupSurvivesCancellationAndVetoesQuit")
        try run("processingFailureIsNotHiddenByCancel")
        try run("uncertainExitDoesNotClaimNoPublication")
        try run("completeStillRequiresSuccessfulExit")
        try run("cleanupPathRejectsOtherOperations")
        try run("nextOperationResetsCleanupAndCancellation")
        try run("lateCancellationAllowsSuccessfulQuit")
        try run("cancellationBeforeWorkerStartAllowsQuit")
        try run("publishedWithoutConfirmationRetainsWarningAndVetoesQuit")
        try run("unknownScanExitDoesNotSuggestPublishedOutput")
        try run("cleanupPathRejectsSourceAndDestination")
        print("PASS: 13 focused publication/cleanup model checks")
    }

    @MainActor static func run(_ name: String) throws {
        let suite = "DICOMPublicationRecoveryTests." + UUID().uuidString
        guard let defaults = UserDefaults(suiteName: suite) else { throw PublicationRecoveryFailure(message: "Isolated preferences unavailable") }
        defer { defaults.removePersistentDomain(forName: suite) }
        let model = BatchModel(defaults: defaults)
        let parent = URL(fileURLWithPath: "/Users/jeff/Developer/Codex/DICOM-Publication-Recovery-20261023/model-output", isDirectory: true)
        let output = parent.appendingPathComponent("Anonymized_fixture", isDirectory: true)
        let stage = parent.appendingPathComponent(".dicom-batch-fixture", isDirectory: true)
        model.outputParent = parent
        model.beginRunState(isScan: false, output: output)
        func complete() { model.receive(["event": "complete", "processed": 3, "patients": 1, "excluded_files": 2]) }
        func cleanup(_ path: String) {
            model.receive(["event": "error", "message": "Processing was cancelled. Incomplete output could not be removed. Remove the staging folder before retrying.", "cancelled": true, "cleanup_failed": true, "staging_path": path])
        }
        func require(_ condition: Bool, _ message: String) throws {
            if !condition { throw PublicationRecoveryFailure(message: name + ": " + message) }
        }
        switch name {
        case "lateCancellationKeepsPublishedCompletion":
            model.cancel(); complete()
            model.finishRun(code: 0, cancelled: true, isScan: false, output: output)
            try require(model.summary?.files == 3 && model.summary?.patients == 1 && model.completedOutput == output, "Published completion must survive a late cancellation request")
            try require(model.canInspectOutput && model.errorMessage == nil && !model.busy, "Published result must retain existing reveal/report actions")
        case "acknowledgedCancellationClearsOnlyCancelledError":
            model.cancel()
            model.receive(["event": "error", "message": "Processing was cancelled. No completed output was published.", "cancelled": true, "cleanup_failed": false])
            model.finishRun(code: 1, cancelled: true, isScan: false, output: output)
            try require(model.summary == nil && model.completedOutput == nil && model.errorMessage == nil, "Clean cancellation must not create completion or retain a blocking error")
            try require(model.status == "Cancelled. No completed batch was published.", "Only acknowledged prepublication cancellation can claim no output")
        case "failedCleanupSurvivesCancellationAndVetoesQuit":
            var quitReply: Bool?
            model.prepareToQuit { quitReply = $0 }
            cleanup(stage.path)
            model.finishRun(code: 1, cancelled: true, isScan: false, output: output)
            try require(model.cleanupIncomplete && model.problem == .output && model.problemURL == stage, "Cleanup warning must name this operation's staging path")
            try require(model.errorMessage?.contains("Incomplete output") == true && !model.ready && !model.canAnonymize, "Cancellation must retain cleanup warning and block stale readiness")
            try require(quitReply == false && !model.busy && model.recoveryTitle == "Choose Location…", "Pending quit must be declined so existing recovery area stays visible")
        case "processingFailureIsNotHiddenByCancel":
            model.cancel()
            model.receive(["event": "error", "message": "Synthetic original write failure", "cancelled": false, "cleanup_failed": false])
            model.finishRun(code: 1, cancelled: true, isScan: false, output: output)
            try require(model.errorMessage == "Synthetic original write failure" && model.problem == .processing, "A cancel request must not replace a real processing error")
            try require(model.status != "Cancelled. No completed batch was published.", "A processing failure is not an acknowledged cancellation")
        case "uncertainExitDoesNotClaimNoPublication":
            var quitReply: Bool?
            model.prepareToQuit { quitReply = $0 }
            model.finishRun(code: 15, cancelled: true, isScan: false, output: output)
            try require(model.summary == nil && model.completedOutput == nil, "Unexpected exit cannot synthesize completed output")
            try require(model.errorMessage?.contains("may already be present") == true && model.problemURL == output && quitReply == false, "Unknown outcome must remain visible and advise output inspection")
        case "completeStillRequiresSuccessfulExit":
            complete()
            model.finishRun(code: 1, cancelled: false, isScan: false, output: output)
            try require(model.summary == nil && model.completedOutput == nil && model.errorMessage != nil, "Complete event alone must not create accepted completion")
        case "cleanupPathRejectsOtherOperations":
            for path in ["relative/.dicom-batch-fixture", parent.appendingPathComponent("ordinary-folder").path, "/tmp/.dicom-batch-other", parent.appendingPathComponent(".dicom-batch-").path] {
                cleanup(path)
                try require(model.cleanupIncomplete && model.problemURL == nil, "Unrelated or malformed staging paths must never be presented as this operation's cleanup target")
                try require(model.recoveryMessage.contains("could not be identified safely"), "Unknown staging identity must not advise deleting the output parent")
            }
        case "cleanupPathRejectsSourceAndDestination":
            model.source = stage
            cleanup(stage.path)
            try require(model.problemURL == nil, "Never suggest removing the original source folder")
            model.beginRunState(isScan: false, output: stage)
            cleanup(stage.path)
            try require(model.problemURL == nil, "Never suggest removing the final destination as incomplete staging")
        case "nextOperationResetsCleanupAndCancellation":
            model.cancel(); cleanup(stage.path)
            model.finishRun(code: 1, cancelled: true, isScan: false, output: output)
            model.beginRunState(isScan: false, output: output)
            try require(!model.cleanupIncomplete && !model.cancelling && model.errorMessage == nil && model.problemURL == nil, "New operation must reset cleanup and cancellation state")
            model.finishRun(code: 1, cancelled: false, isScan: false, output: output)
            try require(model.errorMessage?.contains("may already be present") == true, "Old cancellation acknowledgement must not leak into next run")
        case "lateCancellationAllowsSuccessfulQuit":
            var quitReply: Bool?
            model.prepareToQuit { quitReply = $0 }
            complete()
            model.finishRun(code: 0, cancelled: true, isScan: false, output: output)
            try require(quitReply == true && model.summary != nil, "Successfully published output must permit requested quit")
        case "publishedWithoutConfirmationRetainsWarningAndVetoesQuit":
            var quitReply: Bool?
            model.prepareToQuit { quitReply = $0 }
            model.receive(["event": "error", "message": "The completed output was published, but completion could not be confirmed. Check the output folder before retrying.", "output_published": true, "cancelled": false, "cleanup_failed": false])
            model.finishRun(code: 1, cancelled: true, isScan: false, output: output)
            try require(model.summary == nil && model.completedOutput == nil && model.errorMessage?.contains("was published") == true, "An unconfirmed published batch must retain its warning without inventing accepted completion")
            try require(model.problemURL == output && quitReply == false, "Published but unconfirmed output must remain visible during Quit")
        case "unknownScanExitDoesNotSuggestPublishedOutput":
            model.beginRunState(isScan: true, output: nil)
            model.finishRun(code: 15, cancelled: true, isScan: true, output: nil)
            try require(model.errorMessage?.contains("Folder checking") == true && model.summary == nil, "Scan failures cannot suggest that scanning published output")
        case "cancellationBeforeWorkerStartAllowsQuit":
            var quitReply: Bool?
            model.prepareToQuit { quitReply = $0 }
            model.finishRun(code: 130, cancelled: true, isScan: false, output: output)
            try require(quitReply == true && model.summary == nil && model.errorMessage == nil, "Cancellation before worker startup leaves no output and permits quit")
        default: throw PublicationRecoveryFailure(message: "Unknown test " + name)
        }
    }
}
