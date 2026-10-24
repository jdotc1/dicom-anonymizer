import Foundation

@main struct InterruptionRecoveryTests {
    struct Failure: Error { let message: String }
    @MainActor static func main() {
        let names = ["ownedStaging", "replacementUnknown", "publishedIdentity", "unrelatedOutput", "liveOwner", "symlinkStaging", "acknowledgement", "cleanedIgnored", "existingRecoveryArea", "malformedRecord", "invalidRecordFields", "currentActionNotOverwritten"]
        var failed=false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try check(name); print("PASS " + name) } catch { failed=true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    @MainActor static func check(_ name: String) throws {
        func require(_ value: Bool, _ message: String) throws { if !value { throw Failure(message:message) } }
        let root=URL(fileURLWithPath:ProcessInfo.processInfo.environment["DICOM_TEST_TMPDIR"] ?? NSTemporaryDirectory()).appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        defer { try? FileManager.default.removeItem(at:root) }
        let stage=root.appendingPathComponent(".dicom-batch-fixture"), output=root.appendingPathComponent("output"), journal=root.appendingPathComponent("operation.json")
        try FileManager.default.createDirectory(at:stage,withIntermediateDirectories:true)
        guard let identity=InterruptionRecovery.identity(stage) else { throw Failure(message:"fixture identity") }
        var record: [String:Any] = ["schema":1,"operation_id":UUID().uuidString,"pid":0,"phase":"allocated","staging":stage.path,"output":output.path,"device":identity.0,"inode":identity.1]
        func save() throws { try JSONSerialization.data(withJSONObject:record).write(to:journal) }
        try save()
        func inspect() -> InterruptionNotice? { InterruptionRecovery.inspect(journal,ownerIsRunning:{_ in false}) }
        switch name {
        case "ownedStaging":
            let notice=inspect();try require(notice?.ownedStaging == true && notice?.publicationPossible == false,"owned only")
        case "replacementUnknown":
            try FileManager.default.removeItem(at:stage);record["inode"]=0;try save()
            let notice=inspect();try require(notice?.ownedStaging == false && notice?.publicationPossible == true,"unknown does not offer ownership")
        case "publishedIdentity":
            record["phase"]="publishing";try save();try FileManager.default.moveItem(at:stage,to:output)
            let notice=inspect();try require(notice?.publicationPossible == true && notice?.location.path == output.path,"rename reconciled by identity")
        case "unrelatedOutput":
            record["phase"]="publishing";try save();try FileManager.default.createDirectory(at:output,withIntermediateDirectories:true)
            let notice=inspect();try require(notice?.ownedStaging == true && notice?.location.path == stage.path,"existence alone does not prove publication")
        case "liveOwner":
            try require(InterruptionRecovery.inspect(journal,ownerIsRunning:{_ in true}) == nil,"do not disturb live worker")
        case "symlinkStaging":
            let target=root.appendingPathComponent("target");try FileManager.default.moveItem(at:stage,to:target)
            try FileManager.default.createSymbolicLink(at:stage,withDestinationURL:target)
            try require(inspect()?.ownedStaging == false,"symlink never owned cleanup")
        case "acknowledgement":
            record["phase"]="published";try save();try FileManager.default.moveItem(at:stage,to:output)
            InterruptionRecovery.acknowledge(journal,output:root.appendingPathComponent("different"))
            try require(FileManager.default.fileExists(atPath:journal.path),"wrong output not acknowledged")
            InterruptionRecovery.acknowledge(journal,output:output)
            try require(!FileManager.default.fileExists(atPath:journal.path),"completed record acknowledged after identity check")
        case "cleanedIgnored":
            record["phase"]="cleaned";try save();try require(inspect() == nil,"normal failure already cleaned")
        case "invalidRecordFields":
            record["phase"]="publishing";record["output"]=42;try save()
            let notice=InterruptionRecovery.firstNotice(in:root)
            try require(notice != nil && notice?.ownedStaging == false && notice?.publicationPossible == true,"semantic corruption remains visible")
        case "malformedRecord":
            try Data("broken".utf8).write(to:journal)
            let notice=InterruptionRecovery.firstNotice(in:root)
            try require(notice != nil && notice?.ownedStaging == false && notice?.publicationPossible == true,"unreadable record never silently clears uncertainty")
        case "currentActionNotOverwritten":
            let suite="InterruptionGuard."+UUID().uuidString
            guard let defaults=UserDefaults(suiteName:suite),let notice=inspect() else { throw Failure(message:"guardfixture") }
            defer { defaults.removePersistentDomain(forName:suite) }
            let model=BatchModel(defaults:defaults);model.errorMessage="New user action failed"
            model.presentInterruption(notice)
            try require(model.errorMessage == "New user action failed" && !model.cleanupIncomplete,"late startup check cannot replace current user problem")
        case "existingRecoveryArea":
            let suite="InterruptionRecovery."+UUID().uuidString
            guard let defaults=UserDefaults(suiteName:suite),let notice=inspect() else { throw Failure(message:"modelfixture") }
            defer { defaults.removePersistentDomain(forName:suite) }
            let model=BatchModel(defaults:defaults);model.presentInterruption(notice)
            try require(model.problem == .output && model.problemURL?.path == stage.path && model.cleanupIncomplete && model.summary == nil && !model.canAnonymize,"uses existing safe recovery without claiming completion")
            try require(!model.cleanJSONSidecars,"session option stays off")
        default: throw Failure(message:"unknown scenario")
        }
    }
}
