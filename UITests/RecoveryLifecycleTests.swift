import Foundation

@main struct RecoveryLifecycleTests {
    struct Failure: Error { let detail: String }
    @MainActor static func main() {
        let names = ["allRecordsVisible", "cleanedRetired", "liveCleanedPreserved", "changedRecordPreserved", "symlinkPreserved", "ownerRechecked", "aggregateRecoveryText", "refreshPreservesNewAction", "refreshUpdatesOwnNotice", "newOutputErrorSurvivesRefresh"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try check(name); print("PASS " + name) }
            catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    @MainActor static func check(_ name: String) throws {
        func require(_ condition: Bool, _ detail: String) throws { if !condition { throw Failure(detail: detail) } }
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        func write(_ name: String, phase: String = "allocated") throws -> URL {
            let file = root.appendingPathComponent(name + ".json")
            let output = root.appendingPathComponent(name + "-output")
            let data: [String: Any] = ["schema": 1, "operation_id": UUID().uuidString, "pid": 123, "phase": phase, "output": output.path]
            try JSONSerialization.data(withJSONObject: data).write(to: file)
            return file
        }
        switch name {
        case "allRecordsVisible":
            let a = try write("a"), b = try write("b")
            try Data("broken".utf8).write(to: root.appendingPathComponent("0.json"))
            let notice = InterruptionRecovery.firstNotice(in: root, ownerIsRunning: { _ in false })
            try require(notice?.message.contains("3 previous") == true && notice?.message.contains("3.") == true, "malformed record cannot hide remaining records")
            try require(FileManager.default.fileExists(atPath: a.path) && FileManager.default.fileExists(atPath: b.path), "unresolved records retained")
        case "cleanedRetired":
            let file = try write("cleaned", phase: "cleaned")
            let output = root.appendingPathComponent("cleaned-output")
            try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
            try require(InterruptionRecovery.firstNotice(in: root, ownerIsRunning: { _ in false }) == nil, "terminal state needs no notice")
            try require(!FileManager.default.fileExists(atPath: file.path) && FileManager.default.fileExists(atPath: output.path), "retire only local record")
        case "liveCleanedPreserved":
            let file = try write("live", phase: "cleaned")
            _ = InterruptionRecovery.firstNotice(in: root, ownerIsRunning: { _ in true })
            try require(FileManager.default.fileExists(atPath: file.path), "never retire live worker record")
        case "changedRecordPreserved":
            let file = try write("changed", phase: "cleaned")
            guard let identity = InterruptionRecovery.recordIdentity(file) else { throw Failure(detail: "identity") }
            try FileManager.default.removeItem(at: file)
            try Data("replacement".utf8).write(to: file)
            try require(!InterruptionRecovery.retire(file, identity: identity), "changed record not acknowledged")
        case "symlinkPreserved":
            let target = try write("target", phase: "cleaned"), link = root.appendingPathComponent("link.json")
            try FileManager.default.createSymbolicLink(at: link, withDestinationURL: target)
            try require(InterruptionRecovery.recordIdentity(link) == nil, "symlink not an owned record")
            try require(InterruptionRecovery.firstNotice(in: root, ownerIsRunning: { _ in true }) != nil, "unsafe record visible")
        case "ownerRechecked":
            _ = try write("owner")
            try require(InterruptionRecovery.firstNotice(in: root, ownerIsRunning: { _ in true }) == nil, "live owner deferred")
            try require(InterruptionRecovery.firstNotice(in: root, ownerIsRunning: { _ in false }) != nil, "later inspection observes exited owner")
        case "refreshPreservesNewAction":
            guard let defaults = UserDefaults(suiteName: UUID().uuidString) else { throw Failure(detail: "fixture") }
            let model = BatchModel(defaults: defaults)
            let notice = InterruptionNotice(message: "older", location: root, ownedStaging: false, publicationPossible: true)
            model.errorMessage = "newer action"
            try require(!model.receiveInterruptionScan(InterruptionScan(notice: notice, hasLiveOwners: true)) && model.errorMessage == "newer action", "new error stops refresh")
            model.errorMessage = nil; model.source = root
            try require(!model.receiveInterruptionScan(InterruptionScan(notice: notice, hasLiveOwners: true)) && model.errorMessage == nil, "selected batch stops refresh")
        case "refreshUpdatesOwnNotice":
            guard let defaults = UserDefaults(suiteName: UUID().uuidString) else { throw Failure(detail: "fixture") }
            let model = BatchModel(defaults: defaults)
            try require(model.receiveInterruptionScan(InterruptionScan(notice: nil, hasLiveOwners: true)), "live owner schedules recheck")
            let notice = InterruptionNotice(message: "owner exited", location: root, ownedStaging: false, publicationPossible: true)
            try require(!model.receiveInterruptionScan(InterruptionScan(notice: notice, hasLiveOwners: false)) && model.errorMessage == "owner exited", "exited owner becomes visible and polling stops")
            _ = model.receiveInterruptionScan(InterruptionScan(notice: nil, hasLiveOwners: false))
            try require(model.errorMessage == nil, "external resolution clears only own notice")
        case "newOutputErrorSurvivesRefresh":
            guard let defaults = UserDefaults(suiteName: UUID().uuidString) else { throw Failure(detail: "fixture") }
            let model = BatchModel(defaults: defaults)
            let notice = InterruptionNotice(message: "older interruption", location: root, ownedStaging: false, publicationPossible: true)
            model.presentInterruption(notice)
            model.setOutputParent(root.appendingPathComponent("missing-folder"))
            let newer = model.errorMessage
            try require(newer != nil && newer != "older interruption", "new validation problem owns recovery area")
            try require(!model.receiveInterruptionScan(InterruptionScan(notice: notice, hasLiveOwners: true)) && model.errorMessage == newer, "refresh cannot replace newer output error")
        case "aggregateRecoveryText":
            _ = try write("a"); _ = try write("b")
            guard let notice = InterruptionRecovery.firstNotice(in: root, ownerIsRunning: { _ in false }), let defaults = UserDefaults(suiteName: UUID().uuidString) else { throw Failure(detail: "fixture") }
            let model = BatchModel(defaults: defaults); model.presentInterruption(notice)
            try require(model.errorMessage?.contains("2 previous") == true && !model.recoveryMessage.contains("remove only"), "never instruct deletion of recovery directory")
            try require(model.problemURL?.path == root.path && !model.canAnonymize, "existing area blocks processing")
        default: throw Failure(detail: "unknown")
        }
    }
}
