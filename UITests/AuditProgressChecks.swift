import Foundation

struct AuditProgressFailure: Error { let message: String }

@MainActor
struct AuditProgressFixture {
    let model: BatchModel
    let defaults: UserDefaults
    let suite: String

    init() throws {
        suite = "io.dicomanonymizer.audit-progress-tests." + UUID().uuidString
        guard let store = UserDefaults(suiteName: suite) else {
            throw AuditProgressFailure(message: "Could not create isolated preferences")
        }
        defaults = store
        model = BatchModel(defaults: store)
        model.total = 20; model.processed = 20; model.activePatient = "00001"; model.busy = true
    }
    func cleanup() { defaults.removePersistentDomain(forName: suite) }
}

@main
@MainActor
struct AuditProgressChecks {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw AuditProgressFailure(message: message) }
    }

    static func main() throws {
        try auditCountsRemainSeparateUntilExplicitFinalization()
        try malformedAndRegressingEventsAreIgnored()
        try prematureAndOutOfOrderEventsAreIgnored()
        try inactiveScanAndCancellationEventsAreIgnored()
        try resettingAndScanEventsClearAuditState()
        try legacyProgressRetainsFinalizingFallback()
        print("PASS: 6 focused audit-progress model checks")
    }

    static func auditCountsRemainSeparateUntilExplicitFinalization() throws {
        let f = try AuditProgressFixture(); defer { f.cleanup() }
        let m = f.model
        m.receive(["event": "audit_progress", "audited_files": 0, "total_files": 20])
        try require(m.processingPhase == .auditing && m.progressTitle == "Checking output", "Audit start must have an explicit checking phase")
        try require(m.progressDetail == "0 of 20 files checked" && m.progressFraction == 0 && m.activePatient == nil, "Audit start must show zero checks and hide the previous patient")
        m.receive(["event": "audit_progress", "audited_files": 10, "total_files": 20])
        try require(m.progressFraction == 0.5 && m.processed == 20 && m.total == 20, "Audit must not mutate writing counts")
        m.receive(["event": "progress", "processed": 1, "total_files": 2, "patient_id": "late"])
        try require(m.processed == 20 && m.total == 20 && m.activePatient == nil && m.progressFraction == 0.5, "Late writing events must not regress the audit display")
        m.receive(["event": "audit_progress", "audited_files": 20, "total_files": 20])
        try require(m.progressFraction == 1 && !m.isFinalizing && m.busy && m.summary == nil && m.completedOutput == nil, "Audit 100 percent must remain active and must not imply published completion")
        m.receive(["event": "phase", "name": "finalizing"])
        try require(m.processingPhase == .finalizing && m.progressFraction == nil && m.progressTitle == "Finalizing batch", "Explicit finalization must be indeterminate")
        try require(m.busy && m.summary == nil && m.completedOutput == nil, "Finalization must not create a completed output")
        m.receive(["event": "audit_progress", "audited_files": 0, "total_files": 20])
        try require(m.processingPhase == .finalizing && m.auditedFiles == 20, "Late audit events must not reopen finalization")
    }

    static func malformedAndRegressingEventsAreIgnored() throws {
        let f = try AuditProgressFixture(); defer { f.cleanup() }
        let m = f.model
        let invalid: [[String: Any]] = [
            ["audited_files": true, "total_files": 20], ["audited_files": -1, "total_files": 20],
            ["audited_files": 0.5, "total_files": 20], ["audited_files": "0", "total_files": 20],
            ["audited_files": 0, "total_files": 0], ["audited_files": 21, "total_files": 20],
            ["audited_files": 0, "total_files": false], ["total_files": 20],
            ["audited_files": 0, "total_files": Double.infinity]
        ]
        for fields in invalid {
            var event = fields; event["event"] = "audit_progress"; m.receive(event)
        }
        m.receive(["event": "phase", "name": "unrecognized"])
        try require(m.processingPhase == .writing && m.auditedFiles == 0 && m.auditTotalFiles == 0, "Malformed audit counts and unknown phases must be ignored")
        m.receive(["event": "audit_progress", "audited_files": 10, "total_files": 20])
        m.receive(["event": "audit_progress", "audited_files": 9, "total_files": 20])
        m.receive(["event": "audit_progress", "audited_files": 11, "total_files": 21])
        try require(m.auditedFiles == 10 && m.auditTotalFiles == 20, "Audit counts must be monotonic with a stable total")
    }

    static func prematureAndOutOfOrderEventsAreIgnored() throws {
        let f = try AuditProgressFixture(); defer { f.cleanup() }
        let m = f.model
        m.processed = 10
        m.receive(["event": "audit_progress", "audited_files": 0, "total_files": 20])
        m.receive(["event": "phase", "name": "finalizing"])
        try require(m.processingPhase == .writing && m.progressFraction == 0.5, "Audit and finalization must not begin before writing completes")
        m.processed = 20
        m.receive(["event": "audit_progress", "audited_files": 0, "total_files": 21])
        try require(m.processingPhase == .writing, "Audit totals must match the writing batch")
        m.receive(["event": "audit_progress", "audited_files": 10, "total_files": 20])
        m.receive(["event": "phase", "name": "finalizing"])
        m.receive(["event": "scan", "patients": [], "total_files": 2])
        try require(m.processingPhase == .auditing && m.auditTotalFiles == 20 && m.total == 20, "Premature finalization or late scans must not replace an active audit")
    }

    static func inactiveScanAndCancellationEventsAreIgnored() throws {
        let f = try AuditProgressFixture(); defer { f.cleanup() }
        let m = f.model
        for state in [(false, false), (true, true)] {
            m.busy = state.0; m.scanning = state.1
            m.receive(["event": "audit_progress", "audited_files": 10, "total_files": 20])
            m.receive(["event": "phase", "name": "finalizing"])
            try require(m.processingPhase == .writing && m.auditTotalFiles == 0, "Audit phases must be ignored outside a processing run")
        }
        m.scanning = false; m.busy = true
        m.receive(["event": "audit_progress", "audited_files": 10, "total_files": 20])
        m.cancel()
        let status = m.status
        m.receive(["event": "audit_progress", "audited_files": 20, "total_files": 20])
        m.receive(["event": "phase", "name": "finalizing"])
        try require(m.auditedFiles == 10 && m.processingPhase == .auditing && m.status == status && m.progressTitle == "Cancelling" && m.progressFraction == nil, "Late phase events must preserve cancellation")
    }

    static func resettingAndScanEventsClearAuditState() throws {
        let f = try AuditProgressFixture(); defer { f.cleanup() }
        let m = f.model
        m.receive(["event": "audit_progress", "audited_files": 10, "total_files": 20])
        m.resetProcessingProgress()
        try require(m.processingPhase == .writing && m.auditedFiles == 0 && m.auditTotalFiles == 0, "The run reset must clear audit state")
        m.receive(["event": "audit_progress", "audited_files": 10, "total_files": 20])
        m.resetProcessingProgress()
        m.receive(["event": "scan", "patients": [], "total_files": 3, "excluded_files": 0])
        try require(m.processingPhase == .writing && m.auditedFiles == 0 && m.auditTotalFiles == 0 && m.total == 3, "A fresh scan event must clear prior audit state")
    }

    static func legacyProgressRetainsFinalizingFallback() throws {
        let f = try AuditProgressFixture(); defer { f.cleanup() }
        let m = f.model
        m.processed = 0
        try require(m.progressTitle == "Preparing batch" && m.progressFraction == nil, "Legacy preparing must remain indeterminate")
        m.receive(["event": "progress", "processed": 10, "total_files": 20, "patient_id": "00001"])
        try require(m.progressTitle == "Anonymizing" && m.progressFraction == 0.5, "Legacy writing must remain determinate")
        m.receive(["event": "progress", "processed": 20, "total_files": 20, "patient_id": "00001"])
        try require(m.isFinalizing && m.progressTitle == "Finalizing batch" && m.progressFraction == nil && m.summary == nil, "Legacy engines must retain the finalizing fallback without early completion")
    }
}
