import Foundation

// A CLI harness only: no NSApplication, App scene, windows or bundled app launch.
@main struct WorkerProcessIntegrationTests {
    @MainActor final class Capture {
        var events: [[String: Any]] = []
        var finished = false
        var timedOut = false
    }
    struct Result { let events: [String]; let code: Int32; let cancelled: Bool; let timedOut: Bool }
    @MainActor static func run(script: String, cancelOnReady: Bool = false, precancel: Bool = false, executable: String = "/bin/sh") async -> Result {
        let runner = EngineRunner(command: { args in (URL(fileURLWithPath: executable), ["-c", script, "fixture"] + args) })
        let capture = Capture()
        if precancel { runner.cancel() }
        return await withCheckedContinuation { continuation in
            let timeout = Task { @MainActor in
                try? await Task.sleep(for: .seconds(8))
                guard !Task.isCancelled, !capture.finished else { return }
                capture.timedOut = true; runner.cancel()
            }
            runner.start(arguments: ["forwarded"], event: { event in
                capture.events.append(event)
                if cancelOnReady && event["event"] as? String == "ready" { runner.cancel() }
            }, finished: { code, cancelled in
                guard !capture.finished else { return }
                capture.finished = true; timeout.cancel()
                continuation.resume(returning: Result(events: capture.events.map { $0["event"] as? String ?? "" }, code: code, cancelled: cancelled, timedOut: capture.timedOut))
            })
        }
    }
    @MainActor static func main() async {
        let names = ["fragmentedPipe", "abruptExit", "cancelRunning", "cancelBeforeStart", "malformedTail", "completionThenExit", "launchFailure", "stderrIsolation", "argumentForwarding", "pipePressure"]
        var failed = false
        for name in CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : names {
            let result: Result
            let passed: Bool
            switch name {
            case "fragmentedPipe":
                result = await run(script: "printf '{\"event\":\"pro'; sleep 0.02; printf 'gress\"}\\n{\"event\":\"complete\"}'")
                passed = result.events == ["progress", "complete"] && result.code == 0
            case "abruptExit":
                result = await run(script: "printf '{\"event\":\"ready\"}\\n'; kill -KILL $$")
                passed = result.events == ["ready"] && result.code != 0 && !result.cancelled
            case "cancelRunning":
                result = await run(script: "printf '{\"event\":\"ready\"}\\n'; exec /bin/sleep 30", cancelOnReady: true)
                passed = result.events == ["ready"] && result.cancelled && result.code != 0
            case "cancelBeforeStart":
                result = await run(script: "printf '{\"event\":\"unexpected\"}'", precancel: true)
                passed = result.events.isEmpty && result.cancelled && result.code == 130
            case "malformedTail":
                result = await run(script: "printf '{\"event\":\"ready\"}\\n{broken'")
                passed = result.events == ["ready", "error"] && result.code == 1
            case "completionThenExit":
                result = await run(script: "printf '{\"event\":\"complete\"}\\n'; exit 7")
                passed = result.events == ["complete", "error"] && result.code == 7
            case "launchFailure":
                result = await run(script: "", executable: "/nonexistent/dicom-fixture-worker")
                passed = result.events == ["error"] && result.code == 1 && !result.cancelled
            case "stderrIsolation":
                result = await run(script: "printf 'PRIVATE_DIAGNOSTIC' >&2; printf '{\"event\":\"complete\"}\\n'")
                passed = result.events == ["complete"] && result.code == 0
            case "argumentForwarding":
                result = await run(script: "test \"$1\" = forwarded || exit 9; printf '{\"event\":\"complete\"}'")
                passed = result.events == ["complete"] && result.code == 0
            case "pipePressure":
                result = await run(script: "i=0; while [ $i -lt 2000 ]; do printf '{\"event\":\"tick\"}\\n'; i=$((i+1)); done; printf '{\"event\":\"complete\"}'")
                passed = result.events.count == 2001 && result.events.last == "complete" && result.code == 0
            default: print("FAIL unknown " + name); exit(1)
            }
            if passed && !result.timedOut { print("PASS " + name) }
            else { failed = true; print("FAIL \(name): code=\(result.code), cancelled=\(result.cancelled), timeout=\(result.timedOut), events=\(result.events.count)") }
        }
        if failed { exit(1) }
    }
}
