import SwiftUI
import AppKit

@main
struct WorkflowPolishTests {
    @MainActor static func main() {
        _ = NSApplication.shared
        let model = BatchModel()
        model.ready = true
        model.outputParent = URL(fileURLWithPath: "/Synthetic/Output")
        if !CommandLine.arguments.contains("--layout-only") {
        precondition(model.canAnonymize)
        model.selectSource(URL(fileURLWithPath: "/Synthetic/missing-folder"))
        precondition(model.errorMessage != nil && !model.canAnonymize, "Rejected selection must disable the button and keyboard command")
        model.errorMessage = nil; model.busy = true; model.total = 6
        precondition(model.progressTitle == "Preparing batch")
        model.receive(["event": "progress", "processed": 3, "total_files": 6, "patient_id": "00001"])
        precondition(model.progressTitle == "Anonymizing")
        model.receive(["event": "progress", "processed": 6, "total_files": 6, "patient_id": "00002"])
        precondition(model.progressTitle == "Finalizing batch")
        precondition(model.summary == nil && model.completedOutput == nil && model.busy)
        }
        model.errorMessage = nil; model.total = 6; model.processed = 6; model.busy = true
        let long = String(repeating: "Long folder name ", count: 12)
        model.source = URL(fileURLWithPath: "/Synthetic/" + long)
        model.outputParent = URL(fileURLWithPath: "/Synthetic/" + long + "/Output")
        model.patients = [PatientRow(id: String(repeating: "0", count: 64), files: 3, series: 1), PatientRow(id: "00002", files: 3, series: 2)]
        for state in ["finalizing", "completion"] {
            if state == "completion" {
                model.busy = false
                model.summary = CompletionSummary(patients: 2, files: 6, excluded: 1, output: URL(fileURLWithPath: "/Synthetic/" + long), elapsed: 65)
            }
            for scheme in [ColorScheme.light, .dark] {
                let host = NSHostingController(rootView: BatchView(model: model).environment(\.colorScheme, scheme))
                let size = host.sizeThatFits(in: CGSize(width: 700, height: 10_000))
                FileHandle.standardError.write(Data("\(state) \(scheme): \(size)\n".utf8))
                precondition(size.width <= 700 && size.height <= 720, "Affected state must fit the minimum-width/default-height window")
            }
        }
        print(CommandLine.arguments.contains("--layout-only") ? "PASS: public affected layout only; earlier model assertions reused; no engine run" : "PASS: public invalid selection, preparing/finalizing states, long labels and completion layout; no engine run")
    }
}
