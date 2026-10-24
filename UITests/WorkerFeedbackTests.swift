import Foundation

@main struct WorkerFeedbackTests {
    @MainActor static func main() {
        let scenarios = ["fragmentedUTF8", "eofAndWhitespace", "coalescingAndBarriers", "regressingProgressRetained", "malformedTail", "protocolErrorAfterComplete", "safeEngineErrorPreserved", "unknownEventsRetained", "sidecarChecking", "preflightGuards", "completedCounts", "zeroAndDisabled", "invalidCompletionCounts", "nextRunResets", "exitAfterEvents"]
        var failed = false
        for name in (CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : scenarios) {
            do { try check(name); print("PASS " + name) }
            catch { failed = true; print("FAIL \(name): \(error)") }
        }
        if failed { exit(1) }
    }

    struct Failure: Error { let detail: String }
    @MainActor static func check(_ name: String) throws {
        func require(_ value: Bool, _ detail: String) throws { if !value { throw Failure(detail: detail) } }
        func data(_ string: String) -> Data { Data(string.utf8) }
        let delivery = EngineEventDelivery()
        var events: [[String: Any]] = []
        let receive: ([String: Any]) -> Void = { events.append($0) }
        switch name {
        case "fragmentedUTF8":
            let bytes = data("{\"event\":\"scan\",\"label\":\"é界\"}\n{\"event\":\"complete\"}")
            for split in 0...bytes.count {
                var stream = EngineEventStream()
                let frames = stream.append(Data(bytes.prefix(split))) + stream.append(Data(bytes.dropFirst(split))) + stream.finish()
                try require(frames.count == 2, "all split positions preserve frames")
                try require((try JSONSerialization.jsonObject(with: frames[0]) as? [String: Any])?["label"] as? String == "é界", "UTF8 preserved")
            }
        case "eofAndWhitespace":
            var stream = EngineEventStream()
            delivery.deliver(stream.append(data("\r\n  \n{\"event\":\"complete\"}\r")), event: receive)
            delivery.deliver(stream.finish(), event: receive)
            try require(events.count == 1 && delivery.sawComplete && !delivery.malformed, "valid tail without newline")
            try require(stream.finish().isEmpty, "EOF idempotent")
        case "coalescingAndBarriers":
            delivery.deliver([data("{\"event\":\"progress\",\"processed\":1,\"total_files\":3}"), data("{\"event\":\"progress\",\"processed\":2,\"total_files\":3}"), data("{\"event\":\"phase\",\"name\":\"finalizing\"}"), data("{\"event\":\"complete\"}")],event:receive)
            try require(events.count == 3 && eventCount(events[0]["processed"]) == 2, "adjacent progress coalesces")
            try require(events.map { $0["event"] as? String } == ["progress","phase","complete"], "barriers retained")
        case "regressingProgressRetained":
            delivery.deliver([data("{\"event\":\"progress\",\"processed\":2,\"total_files\":3}"),data("{\"event\":\"progress\",\"processed\":1,\"total_files\":3}"),data("{\"event\":\"progress\",\"processed\":3,\"total_files\":4}")],event:receive)
            try require(events.count == 3,"regression/total change never replaces accepted progress")
        case "malformedTail":
            delivery.deliver([data("{\"event\":\"scan\"}"),data("{broken")],event:receive)
            var code: Int32 = 0
            delivery.finish(code:0,cancelled:false,event:receive,finished:{ code=$0; _=$1 })
            try require(delivery.malformed && code == 1 && events.last?["event"] as? String == "error", "protocol failure explicit")
        case "protocolErrorAfterComplete":
            delivery.deliver([data("{broken"),data("{\"event\":\"complete\"}")],event:receive)
            var code: Int32 = 0
            delivery.finish(code:0,cancelled:false,event:receive,finished:{ code=$0; _=$1 })
            try require(events.first?["event"] as? String == "complete" && events.last?["output_published"] as? Bool == true && code == 1,"do not lose publication or claim success")
        case "safeEngineErrorPreserved":
            delivery.deliver([data("{broken"),data("{\"event\":\"error\",\"cleanup_failed\":true}")],event:receive)
            delivery.finish(code:1,cancelled:false,event:receive,finished:{_,_ in})
            try require(events.count == 1 && events[0]["cleanup_failed"] as? Bool == true,"specific engine recovery preserved")
        case "unknownEventsRetained":
            delivery.deliver([data("{\"event\":\"future_event\"}")],event:receive)
            try require(events.count == 1 && !delivery.malformed,"forward compatibility")
        case "exitAfterEvents":
            var order: [String] = []
            delivery.deliver([data("{\"event\":\"scan\"}"),data("{\"event\":\"complete\"}")],event:{ order.append($0["event"] as? String ?? "") })
            delivery.finish(code:0,cancelled:false,event:{_ in},finished:{_,_ in order.append("exit")})
            try require(order == ["scan","complete","exit"],"exit follows all events")
        default:
            let suite = "WorkerFeedback." + UUID().uuidString
            guard let defaults = UserDefaults(suiteName:suite) else { throw Failure(detail:"preferences") }
            defer { defaults.removePersistentDomain(forName:suite) }
            let model = BatchModel(defaults:defaults)
            if name != "zeroAndDisabled" { model.setCleanJSONSidecars(true) }
            model.beginRunState(isScan:false,output:URL(fileURLWithPath:"/synthetic/output"))
            func scan(_ count: Int = 2) { model.receive(["event":"scan","patients":[["id":"00001","files":1,"series":1]],"total_files":1,"sidecar_files":count]) }
            func progress(_ files: Any, _ folders: Any) { model.receive(["event":"sidecar_scan_progress","files_examined":files,"folders_examined":folders]) }
            switch name {
            case "sidecarChecking":
                progress(5,2)
                try require(model.progressTitle == "Checking JSON sidecars" && model.progressFraction == nil,"existing indeterminate area")
                try require(model.progressDetail == "5 JSON files · 2 folders examined", "no invented total")
                model.receive(["event":"scan_progress","files_examined":99,"folders_examined":99])
                try require(model.status == "5 JSON files · 2 folders examined","no backwards DICOM phase")
            case "preflightGuards":
                progress(5,2);progress(4,2);progress(true,3);progress(6,"3")
                try require(model.sidecarFilesExamined == 5 && model.sidecarFoldersExamined == 2,"invalid/regressing pairs ignored")
                scan();progress(20,20)
                try require(!model.checkingSidecars && model.sidecarFilesExamined == 5,"late events ignored")
            case "completedCounts":
                scan();model.receive(["event":"complete","processed":1,"patients":1,"sidecar_files":2,"sidecar_audited_files":2])
                model.finishRun(code:0,cancelled:false,isScan:false,output:URL(fileURLWithPath:"/synthetic/output"))
                try require(model.summary?.sidecarDetail == "2 JSON sidecars cleaned · 2 checked", "terminal counts preserved")
                try require(model.status.contains("2 JSON sidecars"),"status includes actual completed counts")
            case "zeroAndDisabled":
                progress(8,2);scan(0);model.receive(["event":"complete","processed":1,"sidecar_files":7,"sidecar_audited_files":7])
                model.finishRun(code:0,cancelled:false,isScan:false,output:URL(fileURLWithPath:"/synthetic/output"))
                try require(model.summary?.sidecarDetail == nil && !model.checkingSidecars,"disabled mode unchanged")
                let zero = CompletionSummary(patients:1,files:1,excluded:0,output:URL(fileURLWithPath:"/synthetic/output"),elapsed:0,sidecars:0,auditedSidecars:0)
                try require(zero.sidecarDetail == "0 JSON sidecars cleaned · 0 checked","explicit zero is distinct from disabled")
            case "invalidCompletionCounts":
                scan();model.receive(["event":"complete","processed":1,"sidecar_files":2,"sidecar_audited_files":true])
                model.finishRun(code:0,cancelled:false,isScan:false,output:URL(fileURLWithPath:"/synthetic/output"))
                try require(model.summary?.sidecarDetail == nil,"no invented audited counts")
            case "nextRunResets":
                progress(8,2);model.beginRunState(isScan:true,output:nil)
                try require(!model.checkingSidecars && model.sidecarFilesExamined == 0 && model.sidecarFoldersExamined == 0,"phase counters reset")
            default: throw Failure(detail:"unknown scenario")
            }
        }
    }
}
