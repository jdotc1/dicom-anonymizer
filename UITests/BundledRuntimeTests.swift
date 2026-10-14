import Foundation

@main
struct BundledRuntimeTests {
    @MainActor static func main() async {
        guard CommandLine.arguments.count == 4 else { exit(2) }
        let missing = CommandLine.arguments[1] == "missing"
        let model = BatchModel()
        model.selectSource(URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true))
        let scanDeadline = Date().addingTimeInterval(30)
        while model.busy && Date() < scanDeadline {
            try? await Task.sleep(nanoseconds: 50_000_000)
        }
        if missing {
            guard !model.busy, !model.ready,
                  model.errorMessage == "The bundled Python runtime is missing. Reinstall the app from the official release." else {
                print("FAIL: missing runtime did not report the expected error"); exit(1)
            }
            print("PASS: missing bundled runtime fails clearly without external Python fallback.")
            return
        }
        guard model.ready, model.patients.map(\.id) == ["00001", "00002"], model.total == 6 else {
            print("FAIL: bundled runtime scan"); exit(1)
        }
        model.outputParent = URL(fileURLWithPath: CommandLine.arguments[3], isDirectory: true)
        model.anonymize()
        let deadline = Date().addingTimeInterval(30)
        while model.busy && Date() < deadline {
            try? await Task.sleep(nanoseconds: 50_000_000)
        }
        guard !model.busy, model.errorMessage == nil, let summary = model.summary,
              summary.files == 6, summary.patients == 2, let output = model.completedOutput else {
            print("FAIL: bundled runtime completion"); exit(1)
        }
        do {
            let data = try Data(contentsOf: output.appendingPathComponent("anonymization-report.json"))
            let report = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            let software = report?["software"] as? [String: Any]
            let audit = report?["self_audit"] as? [String: Any]
            guard software?["python"] as? String == "3.13.16", software?["pydicom"] as? String == "3.0.2",
                  audit?["result"] as? String == "passed" else {
                print("FAIL: report does not identify the bundled runtime and passed audit"); exit(1)
            }
            print("PASS: Swift model scans and completes six synthetic files using bundled Python 3.13.16 and pydicom 3.0.2 with external runtimes denied.")
        } catch { print("FAIL: bundled runtime output report"); exit(1) }
    }
}
