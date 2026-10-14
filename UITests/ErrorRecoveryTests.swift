import SwiftUI
import AppKit

@main struct ErrorRecoveryTests {
    @MainActor static func main() {
        _ = NSApplication.shared
        do {
            if CommandLine.arguments.contains("--busy-only") {
                try RecoveryChecks.cancellationAndBusyActionsStayConsistent()
                print("PASS: busy actions with an existing completed-output record; no engine processing")
                return
            }
            try RecoveryChecks.rejectedSourceCannotRunPreviousBatch()
            try RecoveryChecks.outputRecoveryPreservesReadyBatchAndPreferences()
            try RecoveryChecks.missingReportPreservesCompletion()
            try RecoveryChecks.cancellationAndBusyActionsStayConsistent()
            print("PASS: four focused recovery model checks; no engine processing")
            let f = try RecoveryFixture(); defer { f.cleanup() }
            let model = f.model
            let long = URL(fileURLWithPath: "/Synthetic/" + String(repeating: "Long folder name ", count: 12))
            model.source = long; model.outputParent = long; model.completedOutput = long
            model.summary = CompletionSummary(patients: 1, files: 3, excluded: 0, output: long, elapsed: 2)
            for kind in [BatchProblem.input, .output, .processing, .report] {
                model.problem = kind; model.problemURL = long
                model.errorMessage = "The requested operation could not be completed."
                for scheme in [ColorScheme.light, .dark] {
                    let host = NSHostingController(rootView: BatchView(model: model).environment(\.colorScheme, scheme))
                    let size = host.sizeThatFits(in: CGSize(width: 700, height: 10_000))
                    FileHandle.standardError.write(Data("\(kind) \(scheme): \(size)\n".utf8))
                    try RecoveryChecks.require(size.width <= 700 && size.height <= 720, "Recovery layout must fit the default height at minimum width")
                }
            }
            print("PASS: public recovery layouts in light/dark")
        } catch {
            FileHandle.standardError.write(Data("FAIL: \(error)\n".utf8)); exit(1)
        }
    }
}
