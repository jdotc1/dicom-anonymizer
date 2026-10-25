import Foundation

@main struct RecoveryExplanationTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() {
        let names = ["matchingOutput", "matchingStaging", "unavailableParent", "replacedOutput", "missingFolders", "malformedRecordNamed", "combinedLocations"]
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
        let stage = root.appendingPathComponent(".dicom-batch-fixture"), output = root.appendingPathComponent("output"), journal = root.appendingPathComponent("operation.json")
        try FileManager.default.createDirectory(at: stage, withIntermediateDirectories: true)
        guard let id = InterruptionRecovery.identity(stage) else { throw Failure(message: "fixture") }
        var entry: [String: Any] = ["schema": 1, "operation_id": UUID().uuidString, "pid": 0, "phase": "publishing", "staging": stage.path, "output": output.path, "device": id.0, "inode": id.1]
        func save() throws { try JSONSerialization.data(withJSONObject: entry).write(to: journal) }
        try save()
        switch name {
        case "matchingOutput":
            try FileManager.default.moveItem(at: stage, to: output)
            guard let notice = InterruptionRecovery.inspect(journal) else { throw Failure(message: "notice") }
            try require(notice.message.contains("Confirmed: the output folder matches") && notice.message.contains("Unconfirmed:") && notice.message.contains("report"), "identity is separate from accepted completion")
            try require(notice.publicationPossible && !notice.ownedStaging && notice.location.path == output.path, "published uncertainty retained")
        case "matchingStaging":
            guard let notice = InterruptionRecovery.inspect(journal) else { throw Failure(message: "notice") }
            try require(notice.message.contains("Confirmed: the incomplete staging") && notice.message.contains(output.path) && notice.ownedStaging, "staging and intended output both identified")
        case "unavailableParent":
            entry["staging"] = root.appendingPathComponent("absent/.dicom-batch-fixture").path
            entry["output"] = root.appendingPathComponent("absent/output").path; try save()
            let text = InterruptionRecovery.inspect(journal)?.message ?? ""
            try require(text.contains("could not be inspected") && text.contains("reconnect or locate") && !text.contains("No completed batch"), "unavailable volume is not a no-publication claim")
        case "replacedOutput":
            try FileManager.default.removeItem(at: stage)
            try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
            entry["inode"] = 0; try save()
            let notice = InterruptionRecovery.inspect(journal)
            try require(notice?.message.contains("identity could not be confirmed as matching") == true && notice?.message.contains("do not treat") == true && notice?.publicationPossible == true, "unrelated output is not accepted")
        case "missingFolders":
            try FileManager.default.removeItem(at: stage)
            let text = InterruptionRecovery.inspect(journal)?.message ?? ""
            try require(text.contains("output parent was identified as a folder") && text.contains("moved, removed, or replaced") && text.contains(output.path), "missing is distinguished from unavailable parent")
        case "malformedRecordNamed":
            try Data("broken".utf8).write(to: journal)
            let text = InterruptionRecovery.firstNotice(in: root)?.message ?? ""
            try require(text.contains("operation.json") && text.contains("no staging ownership or publication outcome"), "unreadable record named without claiming ownership")
        case "combinedLocations":
            let second = root.appendingPathComponent("second.json")
            try Data("broken".utf8).write(to: second)
            let notice = InterruptionRecovery.firstNotice(in: root)
            try require(notice?.message.contains(output.path) == true && notice?.message.contains(stage.path) == true && notice?.message.contains("second.json") == true, "combined notice retains per-operation detail")
            guard let defaults = UserDefaults(suiteName: UUID().uuidString), let notice else { throw Failure(message: "model") }
            let model = BatchModel(defaults: defaults); model.presentInterruption(notice)
            try require(!model.recoveryMessage.contains("remove only") && !model.canAnonymize, "same safe recovery area")
        default: throw Failure(message: "unknown")
        }
    }
}
