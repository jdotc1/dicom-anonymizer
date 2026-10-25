import Foundation

@main struct OutputLocationRecheckTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() {
        let names = ["unavailableBecomesMatching", "matchingBecomesReplaced", "newerErrorWins", "selectedSourceWins", "malformedDoesNotPoll", "mixedRecordsKeepPolling", "removedRecordStopsPolling", "validOutputChoiceWins", "validOutputBeforeInitialScanWins"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try check(name); print("PASS " + name) } catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    @MainActor static func check(_ name: String) throws {
        func require(_ value: Bool, _ message: String) throws { if !value { throw Failure(message: message) } }
        let base = URL(fileURLWithPath: ProcessInfo.processInfo.environment["DICOM_TEST_TMPDIR"] ?? NSTemporaryDirectory())
        let root = base.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let records = root.appendingPathComponent("records"), parent = root.appendingPathComponent("volume"), parked = root.appendingPathComponent("parked")
        try FileManager.default.createDirectory(at: records, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
        let output = parent.appendingPathComponent("output"), journal = records.appendingPathComponent("operation.json")
        try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
        guard let identity = InterruptionRecovery.identity(output), let defaults = UserDefaults(suiteName: UUID().uuidString) else { throw Failure(message: "fixture") }
        let record: [String: Any] = ["schema": 1, "operation_id": UUID().uuidString, "pid": 0, "phase": "published", "output": output.path, "device": identity.0, "inode": identity.1]
        try JSONSerialization.data(withJSONObject: record).write(to: journal)
        let model = BatchModel(defaults: defaults)
        func snapshot() -> InterruptionScan { InterruptionRecovery.scan(in: records) }
        switch name {
        case "unavailableBecomesMatching":
            try FileManager.default.moveItem(at: parent, to: parked)
            try require(model.receiveInterruptionScan(snapshot()) && model.errorMessage?.contains("could not be inspected") == true, "unavailable valid record schedules refresh")
            try FileManager.default.moveItem(at: parked, to: parent)
            try require(model.receiveInterruptionScan(snapshot()) && model.errorMessage?.contains("Confirmed: the output folder matches") == true, "restored identity updates own notice")
            try require(model.summary == nil && !model.canAnonymize && FileManager.default.fileExists(atPath: journal.path), "reconnection is not completion or acknowledgement")
        case "matchingBecomesReplaced":
            _ = model.receiveInterruptionScan(snapshot())
            try FileManager.default.moveItem(at: output, to: parent.appendingPathComponent("original"))
            try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
            try require(model.receiveInterruptionScan(snapshot()) && model.errorMessage?.contains("could not be confirmed as matching") == true, "replacement cannot retain prior matching claim")
        case "newerErrorWins":
            _ = model.receiveInterruptionScan(snapshot()); let delayed = snapshot()
            model.setOutputParent(root.appendingPathComponent("missing")); let newer = model.errorMessage
            try require(!model.receiveInterruptionScan(delayed) && model.errorMessage == newer, "new output error stops polling and survives old snapshot")
        case "selectedSourceWins":
            _ = model.receiveInterruptionScan(snapshot()); let delayed = snapshot(); model.source = root
            let previous = model.errorMessage
            try require(!model.receiveInterruptionScan(delayed) && model.errorMessage == previous, "selected source owns area")
        case "validOutputChoiceWins":
            _ = model.receiveInterruptionScan(snapshot()); let delayed = snapshot()
            model.setOutputParent(root)
            try require(model.errorMessage == nil, "accepted location clears previous notice")
            try require(!model.receiveInterruptionScan(delayed) && model.errorMessage == nil && model.outputParent?.path == root.path, "delayed notice cannot undo successful location choice")
        case "validOutputBeforeInitialScanWins":
            let delayed = snapshot(); model.setOutputParent(root)
            try require(!model.receiveInterruptionScan(delayed) && model.errorMessage == nil, "initial scan cannot overwrite earlier successful choice")
        case "malformedDoesNotPoll":
            try Data("broken".utf8).write(to: journal)
            try require(!model.receiveInterruptionScan(snapshot()) && model.errorMessage != nil, "malformed record remains visible without recurring location I/O")
        case "mixedRecordsKeepPolling":
            try Data("broken".utf8).write(to: records.appendingPathComponent("bad.json"))
            let scan = snapshot()
            try require(scan.hasPendingLocations && model.receiveInterruptionScan(scan) && model.errorMessage?.contains("2 previous") == true, "valid location remains monitored among malformed records")
        case "removedRecordStopsPolling":
            _ = model.receiveInterruptionScan(snapshot()); try FileManager.default.removeItem(at: journal)
            try require(!model.receiveInterruptionScan(snapshot()) && model.errorMessage == nil, "external record resolution clears own notice and stops refresh")
            try require(FileManager.default.fileExists(atPath: output.path), "recheck never deletes output")
        default: throw Failure(message: "unknown")
        }
    }
}
