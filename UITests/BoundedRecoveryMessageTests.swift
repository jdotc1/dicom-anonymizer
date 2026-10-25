import Foundation

@main struct BoundedRecoveryMessageTests {
    struct Failure: Error { let detail: String }
    static func require(_ value: Bool, _ detail: String) throws {
        if !value { throw Failure(detail: detail) }
    }
    static func main() {
        let names = ["backlog", "hugeSingle", "byteBudget", "latePublication", "lateOwnership", "singleFits", "empty", "lateMalformed", "smallAfterHuge"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            do { try check(name); print("PASS " + name) }
            catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }
    static func check(_ name: String) throws {
        let base = URL(fileURLWithPath: ProcessInfo.processInfo.environment["DICOM_TEST_TMPDIR"] ?? NSTemporaryDirectory())
        let root = base.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        var originals: [URL: Data] = [:]
        @discardableResult func write(_ index: Int, owned: Bool = false, pid: Int = 123,
                                     longCharacters: Int = 0) throws -> URL {
            let label = String(format: "%03d", index)
            let file = root.appendingPathComponent(label + ".json")
            let output = root.appendingPathComponent(longCharacters > 0 ? String(repeating: "界", count: longCharacters) : "output-" + label)
            var entry: [String: Any] = ["schema": 1, "operation_id": UUID().uuidString,
                                       "pid": pid, "phase": "allocated", "output": output.path]
            if owned {
                let staging = root.appendingPathComponent(".dicom-batch-" + label)
                try FileManager.default.createDirectory(at: staging, withIntermediateDirectories: true)
                guard let identity = InterruptionRecovery.identity(staging) else { throw Failure(detail: "fixture identity") }
                entry["staging"] = staging.path
                entry["device"] = identity.0; entry["inode"] = identity.1
            }
            let data = try JSONSerialization.data(withJSONObject: entry)
            try data.write(to: file); originals[file] = data
            return file
        }
        func retained() throws {
            for (file, data) in originals {
                try require(try Data(contentsOf: file) == data, "aggregation preserves every unresolved record byte")
            }
        }
        switch name {
        case "backlog":
            for index in 1...12 { try write(index) }
            let scan = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false })
            guard let notice = scan.notice else { throw Failure(detail: "backlog notice") }
            try require(notice.message.contains("12 previous") && notice.message.contains("4 additional recovery records"), "eight complete details plus exact omitted count")
            for index in 1...8 {
                let path = root.appendingPathComponent(String(format: "output-%03d", index)).path
                try require(notice.message.contains("\(index). Unconfirmed:") && notice.message.contains("Intended output: " + path + "."), "each admitted detail and complete path is rendered")
            }
            try require(!notice.message.contains("output-009") && notice.location == root && notice.publicationPossible, "summary points to records and limits details")
            try require(scan.hasPendingLocations && notice.message.utf8.count <= 16384, "pending state and byte bound")
            try retained()
        case "hugeSingle":
            try write(1, longCharacters: 12000)
            let scan = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false })
            guard let notice = scan.notice else { throw Failure(detail: "oversized notice") }
            try require(notice.message.utf8.count <= 16384 && notice.message.contains("1 additional recovery record needs"), "single huge Unicode notice summarized within byte bound")
            try require(notice.location == root && notice.publicationPossible && scan.hasPendingLocations, "omitted detail cannot clear uncertainty")
            try retained()
        case "byteBudget":
            for index in 1...6 { try write(index, longCharacters: 2200) }
            let notice = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false }).notice
            try require(notice != nil && notice!.message.utf8.count <= 16384 && notice!.message.contains("additional recovery records"), "UTF-8 budget limits text before detail count limit")
            try retained()
        case "latePublication":
            for index in 1...11 { try write(index, owned: true) }
            try write(12); try write(13, pid: 999)
            var inspected = 0
            let scan = InterruptionRecovery.scan(in: root, ownerIsRunning: { pid in inspected += 1; return pid == 999 })
            try require(inspected == 13 && scan.hasLiveOwners && scan.hasPendingLocations, "scan continues past cap and observes late live owner")
            try require(scan.notice?.ownedStaging == true && scan.notice?.publicationPossible == true && scan.notice?.message.contains("12 previous") == true, "late publication uncertainty is ORed into summary")
            try retained()
        case "lateOwnership":
            for index in 1...9 { try write(index) }
            try write(10, owned: true)
            let scan = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false })
            try require(scan.notice?.ownedStaging == true && scan.notice?.publicationPossible == true && scan.hasPendingLocations, "late staging ownership is retained")
            try retained()
        case "singleFits":
            try write(1, owned: true)
            let notice = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false }).notice
            try require(notice?.location == root.appendingPathComponent(".dicom-batch-001") && notice?.ownedStaging == true && notice?.publicationPossible == false, "single notice retains original location and certainty")
            try require(notice?.message.hasPrefix("Confirmed: the incomplete staging folder") == true, "single complete detail remains unchanged")
            try retained()
        case "lateMalformed":
            for index in 1...9 { try write(index, owned: true) }
            let broken = root.appendingPathComponent("010.json"), data = Data("broken".utf8)
            try data.write(to: broken); originals[broken] = data
            let scan = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false })
            try require(scan.notice?.ownedStaging == true && scan.notice?.publicationPossible == true &&
                        scan.notice?.message.contains("10 previous") == true, "late unreadable record retains publication uncertainty and count")
            try retained()
        case "smallAfterHuge":
            try write(1, longCharacters: 12000); try write(2, owned: true); try write(3, longCharacters: 12000)
            let notice = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false }).notice
            try require(notice?.message.contains("2. Confirmed: the incomplete staging folder") == true &&
                        notice?.message.contains("2 additional recovery records") == true,
                        "oversized early entry does not prevent later complete detail")
            try require(notice?.ownedStaging == true && notice?.publicationPossible == true &&
                        notice!.message.utf8.count <= 16384, "all flags and byte bound survive omitted entries")
            try retained()
        case "empty":
            let scan = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false })
            try require(scan.notice == nil && !scan.hasLiveOwners && !scan.hasPendingLocations, "empty listing unchanged")
        default: throw Failure(detail: "unknown case")
        }
    }
}
