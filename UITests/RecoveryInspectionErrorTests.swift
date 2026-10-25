import Foundation

@main struct RecoveryInspectionErrorTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() {
        let names = ["missingFresh", "unreadableFresh", "preserveOldNotice", "emptyAfterFailure", "recordsAfterFailure", "newLocationWins", "newErrorWins", "directoryReplacedByFile", "liveOwnerThenMissing"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try check(name); print("PASS " + name) } catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    @MainActor static func check(_ name: String) throws {
        func require(_ value: Bool, _ message: String) throws { if !value { throw Failure(message: message) } }
        let base = URL(fileURLWithPath: ProcessInfo.processInfo.environment["DICOM_TEST_TMPDIR"] ?? NSTemporaryDirectory())
        let root = base.appendingPathComponent(UUID().uuidString), records = root.appendingPathComponent("records")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        guard let defaults = UserDefaults(suiteName: UUID().uuidString) else { throw Failure(message: "fixture") }
        let model = BatchModel(defaults: defaults)
        func denied() -> InterruptionScan {
            InterruptionRecovery.scan(in: records, listDirectory: { _ in throw NSError(domain: NSCocoaErrorDomain, code: NSFileReadNoPermissionError) })
        }
        let prior = InterruptionNotice(message: "Existing publication uncertainty", location: root.appendingPathComponent("output"), ownedStaging: false, publicationPossible: true)
        switch name {
        case "missingFresh":
            let scan = InterruptionRecovery.scan(in: records)
            try require(scan.directoryMissing && scan.unavailableDirectory != nil && !model.receiveInterruptionScan(scan) && model.errorMessage == nil, "fresh missing directory is normal, not an empty successful scan")
        case "unreadableFresh":
            try require(model.receiveInterruptionScan(denied()) && model.errorMessage?.contains("could not be inspected") == true && model.problemURL?.path == records.path && !model.canAnonymize, "unreadable directory is visible and retried")
        case "preserveOldNotice":
            _ = model.receiveInterruptionScan(InterruptionScan(notice: prior, hasLiveOwners: false))
            try require(model.receiveInterruptionScan(denied()) && model.errorMessage?.contains(prior.message) == true, "failure cannot resolve old uncertainty")
            let text = model.errorMessage
            _ = model.receiveInterruptionScan(denied())
            try require(model.errorMessage == text, "repeated failure does not grow nested messages")
            _ = model.receiveInterruptionScan(InterruptionRecovery.scan(in: records))
            try require(model.errorMessage?.contains(prior.message) == true, "later missing directory cannot clear prior notice")
        case "emptyAfterFailure":
            _ = model.receiveInterruptionScan(denied()); try FileManager.default.createDirectory(at: records, withIntermediateDirectories: true)
            try require(!model.receiveInterruptionScan(InterruptionRecovery.scan(in: records)) && model.errorMessage == nil, "only successful empty listing clears own inspection warning")
        case "recordsAfterFailure":
            _ = model.receiveInterruptionScan(denied())
            try require(model.receiveInterruptionScan(InterruptionScan(notice: prior, hasLiveOwners: false, hasPendingLocations: true)) && model.errorMessage == prior.message, "successful inspection replaces warning with actual notice")
        case "newLocationWins":
            _ = model.receiveInterruptionScan(denied()); let delayed = denied(); model.setOutputParent(root)
            try require(!model.receiveInterruptionScan(delayed) && model.errorMessage == nil, "new successful location wins")
        case "newErrorWins":
            _ = model.receiveInterruptionScan(denied()); model.setOutputParent(root.appendingPathComponent("missing")); let text = model.errorMessage
            try require(!model.receiveInterruptionScan(denied()) && model.errorMessage == text, "new validation error wins")
        case "liveOwnerThenMissing":
            try FileManager.default.createDirectory(at: records, withIntermediateDirectories: true)
            let live: [String: Any] = ["schema": 1, "operation_id": UUID().uuidString, "pid": ProcessInfo.processInfo.processIdentifier, "phase": "published", "output": root.appendingPathComponent("output").path]
            try JSONSerialization.data(withJSONObject: live).write(to: records.appendingPathComponent("live.json"))
            let first = InterruptionRecovery.scan(in: records)
            try require(first.hasLiveOwners && first.notice == nil && model.receiveInterruptionScan(first), "live-owner-only scan schedules follow-up")
            try FileManager.default.removeItem(at: records)
            try require(model.receiveInterruptionScan(InterruptionRecovery.scan(in: records)) && model.errorMessage?.contains("could not be inspected") == true, "known recovery directory disappearing is never fresh-install absence")
        case "directoryReplacedByFile":
            try Data("not a directory".utf8).write(to: records)
            let scan = InterruptionRecovery.scan(in: records)
            try require(scan.unavailableDirectory != nil && !scan.directoryMissing && model.receiveInterruptionScan(scan), "file replacement is failed inspection, not empty")
        default: throw Failure(message: "unknown")
        }
    }
}
