import Foundation
import Darwin

@main struct RecoveryRecordReadTests {
    struct Failure: Error { let detail: String }
    static func require(_ value: Bool, _ detail: String) throws {
        if !value { throw Failure(detail: detail) }
    }
    static func main() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("operation.json")
        let output = root.appendingPathComponent("output")
        let entry: [String: Any] = ["schema": 1, "operation_id": UUID().uuidString,
                                  "pid": 123, "phase": "allocated", "output": output.path]
        let valid = try JSONSerialization.data(withJSONObject: entry)
        func reset() throws { try? FileManager.default.removeItem(at: file); try valid.write(to: file) }
        if CommandLine.arguments.dropFirst().contains("snapshotIntegration") {
            try reset()
            let rewritten = InterruptionRecovery.snapshot(file, afterRead: {
                let handle = try! FileHandle(forWritingTo: file)
                try! handle.write(contentsOf: Data(repeating: 32, count: valid.count))
                try! handle.close()
            })
            try require(rewritten == nil, "same-size in-place change rejected")
            print("PASS same-size in-place change")
            try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
            guard let identity = InterruptionRecovery.identity(output) else { throw Failure(detail: "output identity") }
            var published = entry
            published["phase"] = "published"
            published["device"] = identity.0
            published["inode"] = identity.1
            try JSONSerialization.data(withJSONObject: published).write(to: file)
            guard case .retired = InterruptionRecovery.acknowledge(file, output: output) else {
                throw Failure(detail: "stable published record acknowledged")
            }
            try require(!FileManager.default.fileExists(atPath: file.path) &&
                        FileManager.default.fileExists(atPath: output.path), "acknowledgement removes only record")
            print("PASS stable snapshot acknowledgement")
            return
        }
        if CommandLine.arguments.dropFirst().contains("cleanedReplacement") {
            var cleaned = entry
            cleaned["phase"] = "cleaned"
            try JSONSerialization.data(withJSONObject: cleaned).write(to: file)
            let scan = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in
                try! FileManager.default.removeItem(at: file)
                try! valid.write(to: file)
                return false
            })
            try require(scan.notice?.publicationPossible == true && scan.hasPendingLocations &&
                        FileManager.default.fileExists(atPath: file.path), "failed retirement retains uncertainty")
            print("PASS cleaned replacement retains uncertainty")
            return
        }
        try reset()
        try require(InterruptionRecovery.snapshot(file)?.entry["output"] as? String == output.path, "valid snapshot")
        print("PASS valid snapshot")
        for (name, data) in [("empty", Data()), ("malformed", Data("{".utf8)),
                             ("oversized", Data(repeating: 32, count: 65537))] {
            try data.write(to: file)
            try require(InterruptionRecovery.snapshot(file) == nil, name)
            print("PASS " + name)
        }
        try reset()
        let replaced = InterruptionRecovery.snapshot(file, afterOpen: {
            try! FileManager.default.removeItem(at: file)
            try! valid.write(to: file)
        })
        try require(replaced == nil, "replacement rejected")
        print("PASS replacement during read")
        try reset()
        let grown = InterruptionRecovery.snapshot(file, afterOpen: {
            try! Data(repeating: 32, count: 131072).write(to: file, options: [])
        })
        try require(grown == nil, "growth bounded and rejected")
        print("PASS growth during read")
        try reset()
        let truncated = InterruptionRecovery.snapshot(file, afterOpen: { try! Data().write(to: file) })
        try require(truncated == nil, "truncation rejected")
        print("PASS truncation during read")
        try reset()
        let changed = InterruptionRecovery.snapshot(file, afterRead: {
            try! FileManager.default.removeItem(at: file)
            try! valid.write(to: file)
        })
        try require(changed == nil, "post-read replacement rejected")
        print("PASS replacement after read")
        let target = root.appendingPathComponent("target")
        try valid.write(to: target)
        try FileManager.default.removeItem(at: file)
        try FileManager.default.createSymbolicLink(at: file, withDestinationURL: target)
        try require(InterruptionRecovery.snapshot(file) == nil, "symlink rejected")
        print("PASS symlink")
        try FileManager.default.removeItem(at: file)
        try require(mkfifo(file.path, 0o600) == 0, "create FIFO")
        try require(InterruptionRecovery.snapshot(file) == nil, "FIFO cannot block")
        print("PASS FIFO")
        try reset()
        guard let snapshot = InterruptionRecovery.snapshot(file) else { throw Failure(detail: "snapshot") }
        try FileManager.default.removeItem(at: file)
        try valid.write(to: file)
        try require(!InterruptionRecovery.retire(file, identity: snapshot.identity), "stale snapshot cannot retire replacement")
        print("PASS stale retirement")
        try Data("broken".utf8).write(to: file)
        let scan = InterruptionRecovery.scan(in: root, ownerIsRunning: { _ in false })
        try require(scan.notice?.publicationPossible == true && FileManager.default.fileExists(atPath: file.path),
                    "unreadable record retains uncertainty and record")
        print("PASS unreadable record uncertainty")
    }
}
