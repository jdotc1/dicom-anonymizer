import Foundation

private struct ScanProgressFailure: Error { let message: String }

@MainActor
private func checkScanProgress(_ name: String) throws {
    let suite = "DICOMScanProgressTests." + UUID().uuidString
    guard let defaults = UserDefaults(suiteName: suite) else { throw ScanProgressFailure(message: "Cannot isolate preferences") }
    defer { defaults.removePersistentDomain(forName: suite) }
    let m = BatchModel(defaults: defaults)
    func require(_ condition: Bool, _ detail: String) throws {
        if !condition { throw ScanProgressFailure(message: name + ": " + detail) }
    }
    func progress(_ files: Any, _ folders: Any) {
        m.receive(["event": "scan_progress", "files_examined": files, "folders_examined": folders])
    }
    func scanComplete() {
        m.receive(["event": "scan", "patients": [["id":"00001", "files":8,"series":1]], "total_files":8, "excluded_files":2])
    }
    m.beginRunState(isScan: true, output: nil)
    switch name {
    case "initialScanIsIndeterminate":
        try require(m.examiningInput && m.scanning && m.busy, "Initial scan state")
        try require(m.scanFilesExamined == 0 && m.scanFoldersExamined == 0, "Counters start at zero")
        try require(m.progressTitle == "Checking batch" && m.progressFraction == nil, "Indeterminate checking title")
        try require(m.progressDetail == "0 files · 0 folders examined", "Counts without a total")
        try require(m.total == 0 && !m.canAnonymize, "No invented total or early ready")
    case "countsAdvanceWithoutChangingPreview":
        progress(12, 3)
        try require(m.status == "12 files · 3 folders examined", "Existing status receives counts")
        try require(m.total == 0 && m.processed == 0 && m.patients.isEmpty, "Examined is distinct from accepted or processed")
        try require(m.progressFraction == nil && !m.ready && m.summary == nil, "Counts are not completion")
    case "preflightIgnoresStaleWritingFraction":
        m.total = 8; m.processed = 8
        m.beginRunState(isScan: false, output: URL(fileURLWithPath:"/Synthetic/Output"))
        progress(4, 2)
        try require(!m.scanning && m.examiningInput, "Processing preflight uses same counts")
        try require(m.progressFraction == nil && !m.isFinalizing, "No stale writing fraction")
        try require(m.progressTitle == "Checking batch", "Correct preflight title")
    case "malformedCountsAreAtomic":
        progress(5, 2)
        let bad: [[String: Any]] = [
            ["files_examined":6], ["folders_examined":3],
            ["files_examined":true,"folders_examined":3],
            ["files_examined":6,"folders_examined":false],
            ["files_examined":-1,"folders_examined":3],
            ["files_examined":6,"folders_examined":-1],
            ["files_examined":6.5,"folders_examined":3],
            ["files_examined":6,"folders_examined":3.5],
            ["files_examined":"6","folders_examined":3],
            ["files_examined":Double.nan,"folders_examined":3],
            ["files_examined":Int64.max,"folders_examined":3]]
        for fields in bad {
            m.receive(fields.merging(["event":"scan_progress"]) { _,new in new })
            try require(m.scanFilesExamined == 5 && m.scanFoldersExamined == 2, "Malformed event rejected atomically")
        }
    case "regressingCountsAreIgnored":
        progress(5, 3); progress(4, 4); progress(6, 2)
        try require(m.scanFilesExamined == 5 && m.scanFoldersExamined == 3, "Both counters monotonic")
        progress(5, 3); progress(7, 4)
        try require(m.scanFilesExamined == 7 && m.scanFoldersExamined == 4, "Equal and increasing updates valid")
    case "completedScanStopsProgress":
        progress(10, 2); scanComplete(); let status = m.status
        progress(99, 9)
        try require(!m.examiningInput && m.scanFilesExamined == 10 && m.status == status, "Late scan progress ignored")
        try require(!m.ready, "Final count event does not grant ready")
        m.finishRun(code:0,cancelled:false,isScan:true,output:nil)
        try require(m.ready && m.total == 8 && m.excluded == 2, "Existing final scan/exit grants ready")
    case "cancellationSuppressesProgress":
        progress(4, 2); m.cancel(); let status=m.status
        progress(8, 3)
        try require(m.scanFilesExamined == 4 && m.status == status, "Cancellation wins")
        try require(m.progressTitle == "Cancelling" && m.progressFraction == nil, "Indeterminate cancellation retained")
    case "errorSuppressesProgress":
        progress(4, 2); m.receive(["event":"error", "message":"Synthetic scan problem"])
        let status=m.status; progress(8,3)
        try require(m.scanFilesExamined == 4 && m.status == status, "Error wins over queued progress")
    case "idleSuppressesProgress":
        progress(4, 2); m.finishRun(code:130,cancelled:true,isScan:true,output:nil)
        let status=m.status; progress(8, 3)
        try require(!m.examiningInput && m.scanFilesExamined == 4 && m.status == status, "Idle ignores late progress")
    case "nextOperationResetsCounts":
        progress(12,4); m.finishRun(code:130,cancelled:true,isScan:true,output:nil)
        m.beginRunState(isScan:false,output:nil)
        try require(m.scanFilesExamined == 0 && m.scanFoldersExamined == 0 && m.examiningInput, "New run resets counts")
    case "preflightTransitionsToWriting":
        m.beginRunState(isScan:false,output:nil); progress(10,2); scanComplete()
        m.receive(["event":"progress","processed":1,"total_files":8,"patient_id":"00001"])
        try require(!m.examiningInput && m.progressFraction == 0.125, "Real writing fraction restored")
        try require(m.progressDetail.contains("1 of 8"), "Existing writing detail preserved")
    default: throw ScanProgressFailure(message:"Unknown scenario")
    }
}

@main
@MainActor
struct ScanProgressChecks {
    static func main() throws {
        try checkScanProgress("initialScanIsIndeterminate")
        try checkScanProgress("countsAdvanceWithoutChangingPreview")
        try checkScanProgress("preflightIgnoresStaleWritingFraction")
        try checkScanProgress("malformedCountsAreAtomic")
        try checkScanProgress("regressingCountsAreIgnored")
        try checkScanProgress("completedScanStopsProgress")
        try checkScanProgress("cancellationSuppressesProgress")
        try checkScanProgress("errorSuppressesProgress")
        try checkScanProgress("idleSuppressesProgress")
        try checkScanProgress("nextOperationResetsCounts")
        try checkScanProgress("preflightTransitionsToWriting")
        print("PASS: 11 new scan-progress model checks")
    }
}
