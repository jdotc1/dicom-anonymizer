import Foundation

struct RecoveryCheckFailure: Error { let message: String }

@MainActor
struct RecoveryFixture {
    let root: URL
    let input: URL
    let output: URL
    let alternate: URL
    let defaults: UserDefaults
    let suite: String
    let model: BatchModel

    init() throws {
        let base = ProcessInfo.processInfo.environment["DICOM_TEST_ROOT"].map { URL(fileURLWithPath: $0) } ?? FileManager.default.temporaryDirectory
        root = base.appendingPathComponent(UUID().uuidString, isDirectory: true)
        input = root.appendingPathComponent("input", isDirectory: true)
        output = root.appendingPathComponent("output", isDirectory: true)
        alternate = root.appendingPathComponent("alternate", isDirectory: true)
        for url in [input, output, alternate] { try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true) }
        suite = "io.dicomanonymizer.recovery-tests." + UUID().uuidString
        guard let store = UserDefaults(suiteName: suite) else { throw RecoveryCheckFailure(message: "Could not create isolated preferences") }
        defaults = store
        model = BatchModel(defaults: store)
        model.source = input; model.outputParent = output; model.ready = true
        model.patients = [PatientRow(id: "00001", files: 3, series: 1)]; model.total = 3
    }
    func cleanup() {
        defaults.removePersistentDomain(forName: suite)
        try? FileManager.default.removeItem(at: root)
    }
}

@MainActor
enum RecoveryChecks {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw RecoveryCheckFailure(message: message) }
    }
    static func rejectedSourceCannotRunPreviousBatch() throws {
        let f = try RecoveryFixture(); defer { f.cleanup() }
        f.model.selectSource(f.root.appendingPathComponent("missing"))
        try require(!f.model.ready && f.model.source == nil && f.model.patients.isEmpty, "Rejected source must invalidate the old selection and preview")
        try require(f.model.problem == .input && !f.model.canAnonymize && !f.model.canScan, "Input error must disable both actions")
        f.model.scan(); f.model.anonymize()
        try require(!f.model.busy, "Direct actions must not launch a previous batch")
        f.model.setOutputParent(f.alternate)
        try require(f.model.problem == .input && f.model.errorMessage != nil && !f.model.canScan, "Changing output must not dismiss an input error")
    }
    static func outputRecoveryPreservesReadyBatchAndPreferences() throws {
        let f = try RecoveryFixture(); defer { f.cleanup() }
        f.defaults.set(f.output.path, forKey: BatchModel.outputDefaultsKey)
        let invalid = f.root.appendingPathComponent("not-a-folder")
        try Data("synthetic sidecar".utf8).write(to: invalid)
        f.model.setOutputParent(invalid)
        try require(f.model.problem == .output && f.model.ready && !f.model.canAnonymize && !f.model.canScan, "Invalid output must preserve scan and block processing/recheck")
        try require(f.model.outputParent == f.output && f.defaults.string(forKey: BatchModel.outputDefaultsKey) == f.output.path, "Rejected output must not replace the last valid preference")
        f.model.setOutputParent(f.alternate)
        try require(f.model.errorMessage == nil && f.model.canAnonymize && f.model.source == f.input, "Choosing valid output must recover without rescan")
        try require(f.defaults.string(forKey: BatchModel.outputDefaultsKey) == f.alternate.path, "Recovered output must be remembered")
        f.model.outputParent = f.root.appendingPathComponent("disconnected-volume")
        f.model.anonymize()
        try require(!f.model.busy && f.model.problem == .output && f.model.errorMessage != nil, "Missing output at run time must fail before starting the engine")
    }
    static func missingReportPreservesCompletion() throws {
        let f = try RecoveryFixture(); defer { f.cleanup() }
        let summary = CompletionSummary(patients: 1, files: 3, excluded: 0, output: f.output, elapsed: 2)
        f.model.completedOutput = f.output; f.model.summary = summary
        f.model.openReport()
        try require(f.model.problem == .report && f.model.errorMessage != nil, "Missing report must have report recovery")
        try require(f.model.summary == summary && f.model.completedOutput == f.output && f.model.canAnonymize, "Report error must retain completed output and ready state")
        try require(!f.model.canScan, "Check Again must not erase completion during report recovery")
        f.model.scan()
        try require(!f.model.busy && f.model.summary == summary, "Direct recheck must honor report recovery")
        f.model.dismissReportProblem()
        try require(f.model.errorMessage == nil && f.model.summary == summary && f.model.status.hasPrefix("Complete"), "Dismiss must restore completion without processing")
        try FileManager.default.createDirectory(at: f.output.appendingPathComponent("anonymization-report.json"), withIntermediateDirectories: false)
        f.model.openReport()
        try require(f.model.problem == .report, "A directory named like the report must not open as a report")
    }
    static func cancellationAndBusyActionsStayConsistent() throws {
        let f = try RecoveryFixture(); defer { f.cleanup() }
        let idleStatus = f.model.status
        f.model.cancel()
        try require(!f.model.cancelling && f.model.status == idleStatus, "Idle cancellation must be a no-op")
        f.model.completedOutput = f.output
        f.model.busy = true
        f.model.cancel()
        let stopping = f.model.status
        f.model.cancel()
        f.model.receive(["event": "progress", "processed": 3, "total_files": 3, "patient_id": "00001"])
        try require(f.model.cancelling && f.model.status == stopping && f.model.processed == 0 && f.model.progressTitle == "Cancelling", "Late progress/repeated cancellation must not overwrite stopping state")
        f.model.setOutputParent(f.alternate); f.model.scan(); f.model.anonymize(); f.model.openReport()
        try require(f.model.errorMessage == nil && f.model.outputParent == f.output && !f.model.canInspectOutput && !f.model.canScan && !f.model.canAnonymize, "Busy actions must preserve selection and remain disabled")
    }
}
