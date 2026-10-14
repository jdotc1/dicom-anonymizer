import Foundation
import UniformTypeIdentifiers

@main
struct DropHandlerTests {
    @MainActor static func main() async {
        guard CommandLine.arguments.count == 3 else { exit(2) }
        let source = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        let model = BatchModel()
        let provider = NSItemProvider(item: source.dataRepresentation as NSData, typeIdentifier: UTType.fileURL.identifier)
        precondition(!model.acceptDrop([]))
        precondition(!model.acceptDrop([provider, provider]))
        precondition(model.acceptDrop([provider]))
        let deadline = Date().addingTimeInterval(30)
        while Date() < deadline && !model.ready && model.errorMessage == nil {
            try? await Task.sleep(nanoseconds: 50_000_000)
        }
        guard model.ready, model.patients.map(\.id) == ["00001", "00002"], model.total == 6 else {
            print("Drop handler integration FAILED: " + (model.errorMessage ?? "scan timeout or incorrect identifiers"))
            model.cancel()
            exit(1)
        }
        // Exercise progress/completion delivery across the Swift 6 actor boundary.
        // Both paths are supplied by the synthetic test wrapper.
        let validation = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
        try! FileManager.default.createDirectory(at: validation, withIntermediateDirectories: true)
        model.outputParent = validation
        model.anonymize()
        let completionDeadline = Date().addingTimeInterval(180)
        while model.busy && Date() < completionDeadline {
            try? await Task.sleep(nanoseconds: 50_000_000)
        }
        guard !model.busy, model.errorMessage == nil, model.processed == 6,
              let output = model.completedOutput else {
            model.cancel()
            print("FAIL: batch completion or progress delivery")
            exit(1)
        }
        guard let summary = model.summary, summary.files == 6, summary.patients == 2, summary.output == output else {
            print("FAIL: completion summary")
            exit(1)
        }
        // Unknown events and unexpected/malformed fields from newer engines are ignored safely.
        model.receive(["event": "report_note", "detail": ["nested": true]])
        model.receive(["unexpected": 1])
        model.receive(["event": "progress", "processed": "bad", "total_files": -5, "future_field": [1, 2]])
        precondition(model.errorMessage == nil && model.processed == 6 && model.total == 6)
        try! output.path.write(to: validation.appendingPathComponent("latest-output.txt"), atomically: true, encoding: .utf8)
        let beforeCancel = try! FileManager.default.contentsOfDirectory(atPath: validation.path).sorted()
        model.anonymize()
        model.cancel()
        let cancellationDeadline = Date().addingTimeInterval(30)
        while model.busy && Date() < cancellationDeadline {
            try? await Task.sleep(nanoseconds: 50_000_000)
        }
        precondition(!model.busy && model.completedOutput == nil && model.errorMessage == nil)
        let remaining = try! FileManager.default.contentsOfDirectory(at: validation, includingPropertiesForKeys: nil)
        precondition(remaining.map(\.lastPathComponent).sorted() == beforeCancel)
        precondition(!remaining.contains { $0.lastPathComponent.hasPrefix(".dicom-batch-") })
        print("PASS: full batch progress/completion and immediate cancellation through the Swift 6 model.")
        print("PASS: completion summary counts and tolerant handling of unknown engine events and fields.")
        print("PASS: native NSItemProvider file-URL drop loads two exact identifiers and six synthetic files; zero/multiple drops rejected.")
    }
}
