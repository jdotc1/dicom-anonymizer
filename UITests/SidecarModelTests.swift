import Foundation
#if SWIFT_PACKAGE
import XCTest
@testable import DICOMAnonymizer2
#endif

private struct SidecarCheckFailure: Error { let detail: String }
@MainActor
private func checkSidecar(_ name: String) throws {
    let suite = "DICOMSidecarChecks." + UUID().uuidString
    guard let defaults = UserDefaults(suiteName: suite) else { throw SidecarCheckFailure(detail: "preferences") }
    defer { defaults.removePersistentDomain(forName: suite) }
    let model = BatchModel(defaults: defaults)
    func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw SidecarCheckFailure(detail: name + ": " + message) }
    }
    if name == "defaultOffAndSessionOnly" {
        try require(!model.cleanJSONSidecars, "default off")
        model.setCleanJSONSidecars(true)
        try require(model.cleanJSONSidecars, "explicit opt-in")
        try require(!BatchModel(defaults: defaults).cleanJSONSidecars, "not persisted")
        return
    }
    if name == "arguments" {
        let source = URL(fileURLWithPath: "/synthetic/input")
        let output = URL(fileURLWithPath: "/synthetic/output")
        try require(model.engineArguments(source: source, output: nil) == ["--source", source.path, "--scan"], "legacy arguments")
        model.setCleanJSONSidecars(true)
        try require(model.engineArguments(source: source, output: nil).last == "--clean-json-sidecars", "scan opt-in")
        try require(model.engineArguments(source: source, output: output) == ["--source", source.path, "--destination", output.path, "--clean-json-sidecars"], "run opt-in")
        return
    }
    model.setCleanJSONSidecars(true)
    model.beginRunState(isScan: false, output: nil)
    model.receive(["event":"scan", "patients":[["id":"00001", "files":2, "series":1]], "total_files":2,"excluded_files":0,"sidecar_files":2])
    model.receive(["event":"progress","processed":2,"total_files":2])
    func sidecar(_ count: Any, _ total: Any = 2, audit: Bool = false) {
        model.receive(["event":audit ? "sidecar_audit_progress" : "sidecar_progress", audit ? "audited_files" : "processed":count,"total_files":total])
    }
    func dicomAudit() {
        model.receive(["event":"audit_progress","audited_files":2,"total_files":2])
    }
    switch name {
    case "busyOptionIgnored":
        model.setCleanJSONSidecars(false)
        try require(model.cleanJSONSidecars, "no mode change while busy")
    case "writingPhase":
        sidecar(1)
        try require(model.progressTitle == "Cleaning JSON sidecars", "title")
        try require(model.progressDetail == "1 of 2 JSON sidecars cleaned", "detail")
        try require(model.progressFraction == 0.5 && !model.isFinalizing, "phase-specific fraction")
    case "malformedAndRegressingCounts":
        sidecar(1)
        for value: Any in [true, -1, 1.5, "2", 3] { sidecar(value) }
        sidecar(0); sidecar(2, 3)
        try require(model.processedSidecars == 1 && model.sidecarFiles == 2, "invalid/regressing/mismatched counts ignored")
    case "auditOrdering":
        sidecar(1, audit: true)
        try require(model.sidecarPhase == nil, "early audit ignored")
        sidecar(2); dicomAudit(); sidecar(1, audit: true)
        try require(model.progressTitle == "Checking JSON sidecars" && model.progressFraction == 0.5, "audit progress")
        sidecar(2)
        try require(model.sidecarPhase == .auditing, "no return to writing")
    case "finalizingWaitsForSidecarAudit":
        sidecar(2); dicomAudit()
        model.receive(["event":"phase","name":"finalizing"])
        try require(model.processingPhase != .finalizing, "no early finalization")
        sidecar(2, audit: true)
        model.receive(["event":"phase","name":"finalizing"])
        try require(model.processingPhase == .finalizing && model.sidecarPhase == nil, "finalization after both audits")
    case "cancellationAndErrorSuppressEvents":
        model.cancel(); sidecar(1)
        try require(model.processedSidecars == 0 && model.progressTitle == "Cancelling", "cancel suppresses")
        model.beginRunState(isScan: false, output: nil)
        model.receive(["event":"scan","total_files":2,"sidecar_files":2])
        model.receive(["event":"progress","processed":2,"total_files":2])
        model.receive(["event":"error","message":"Synthetic failure"]); sidecar(1)
        try require(model.processedSidecars == 0, "error suppresses")
    case "lateDICOMAuditIgnored":
        sidecar(2); dicomAudit(); sidecar(1, audit: true); dicomAudit()
        try require(model.sidecarPhase == .auditing && model.progressFraction == 0.5, "late DICOM event cannot regress phase")
    case "resetClearsTransientPhase":
        sidecar(1); model.resetProcessingProgress()
        try require(model.processedSidecars == 0 && model.auditedSidecars == 0 && model.sidecarPhase == nil, "cleared")
    case "disabledIgnoresSidecarEvents":
        let off = BatchModel(defaults: defaults)
        off.beginRunState(isScan:false,output:nil)
        off.receive(["event":"scan","total_files":2,"sidecar_files":9])
        off.receive(["event":"progress","processed":2,"total_files":2])
        off.receive(["event":"sidecar_progress","processed":1,"total_files":9])
        try require(off.sidecarFiles == 0 && off.sidecarPhase == nil && off.isFinalizing,"legacy mode unchanged")
    default: throw SidecarCheckFailure(detail: "Unknown scenario")
    }
}

#if SWIFT_PACKAGE
final class SidecarModelTests: XCTestCase {
    @MainActor func testDefaultOffAndSessionOnly() throws { try checkSidecar("defaultOffAndSessionOnly") }
    @MainActor func testArguments() throws { try checkSidecar("arguments") }
    @MainActor func testBusyOptionIgnored() throws { try checkSidecar("busyOptionIgnored") }
    @MainActor func testWritingPhase() throws { try checkSidecar("writingPhase") }
    @MainActor func testMalformedAndRegressingCounts() throws { try checkSidecar("malformedAndRegressingCounts") }
    @MainActor func testAuditOrdering() throws { try checkSidecar("auditOrdering") }
    @MainActor func testFinalizingWaitsForSidecarAudit() throws { try checkSidecar("finalizingWaitsForSidecarAudit") }
    @MainActor func testCancellationAndErrorSuppressEvents() throws { try checkSidecar("cancellationAndErrorSuppressEvents") }
    @MainActor func testLateDICOMAuditIgnored() throws { try checkSidecar("lateDICOMAuditIgnored") }
    @MainActor func testResetClearsTransientPhase() throws { try checkSidecar("resetClearsTransientPhase") }
    @MainActor func testDisabledIgnoresSidecarEvents() throws { try checkSidecar("disabledIgnoresSidecarEvents") }
}
#else
@main struct SidecarModelChecks {
    @MainActor static func main() throws {
        let scenarios = ["defaultOffAndSessionOnly", "arguments", "busyOptionIgnored", "writingPhase", "malformedAndRegressingCounts", "auditOrdering", "finalizingWaitsForSidecarAudit", "cancellationAndErrorSuppressEvents", "resetClearsTransientPhase", "disabledIgnoresSidecarEvents", "lateDICOMAuditIgnored"]
        for name in (CommandLine.arguments.count > 1 ? Array(CommandLine.arguments.dropFirst()) : scenarios) {
            try checkSidecar(name)
            print("PASS " + name)
        }
    }
}
#endif
