import SwiftUI
import AppKit
import UniformTypeIdentifiers

struct PatientRow: Identifiable {
    let id: String
    let files: Int
    let series: Int
}

struct CompletionSummary: Equatable {
    let patients: Int
    let files: Int
    let excluded: Int
    let output: URL
    let elapsed: TimeInterval
    var sidecars: Int? = nil
    var auditedSidecars: Int? = nil
    var sidecarDetail: String? {
        guard let sidecars, let auditedSidecars else { return nil }
        return "\(sidecars) JSON sidecars cleaned · \(auditedSidecars) checked"
    }
}

// Engine JSON integers arrive as NSNumber; accept only whole, non-negative numbers
// and ignore anything else so new or changed fields cannot crash the UI.
func eventCount(_ value: Any?) -> Int? {
    guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
    let double = number.doubleValue
    guard double.isFinite, double >= 0, double <= Double(Int32.max), double == double.rounded() else { return nil }
    return number.intValue
}

func elapsedText(_ interval: TimeInterval) -> String {
    let seconds = max(0, Int(interval.rounded()))
    return seconds >= 3600
        ? String(format: "%d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
        : String(format: "%d:%02d", seconds / 60, seconds % 60)
}

// Framing is independent of JSON and retains partial UTF-8 bytes across reads.
struct EngineEventStream {
    private var pending = Data()
    mutating func append(_ chunk: Data) -> [Data] {
        pending.append(chunk)
        var lines: [Data] = []
        while let boundary = pending.firstIndex(of: 10) {
            lines.append(Data(pending[..<boundary]))
            pending.removeSubrange(...boundary)
        }
        return lines
    }
    mutating func finish() -> [Data] {
        guard !pending.isEmpty else { return [] }
        let tail = pending; pending.removeAll()
        return [tail]
    }
}

@MainActor
final class EngineEventDelivery {
    private(set) var malformed = false
    private(set) var sawComplete = false
    private(set) var sawError = false

    private func advances(_ previous: [String: Any], _ next: [String: Any]) -> Bool {
        guard let name = previous["event"] as? String, name == next["event"] as? String else { return false }
        let keys: [String]
        switch name {
        case "scan_progress", "sidecar_scan_progress": keys = ["files_examined", "folders_examined"]
        case "progress", "sidecar_progress": keys = ["processed"]
        case "audit_progress", "sidecar_audit_progress": keys = ["audited_files"]
        default: return false
        }
        if keys.count == 1 {
            guard let oldTotal = eventCount(previous["total_files"]),
                  let newTotal = eventCount(next["total_files"]), oldTotal == newTotal else { return false }
        }
        return keys.allSatisfy { key in
            guard let old = eventCount(previous[key]), let new = eventCount(next[key]) else { return false }
            return new >= old
        }
    }

    func deliver(_ lines: [Data], event: ([String: Any]) -> Void) {
        var progress: [String: Any]?
        for line in lines {
            if line.allSatisfy({ [9, 13, 32].contains($0) }) { continue }
            guard let object = try? JSONSerialization.jsonObject(with: line),
                  let json = object as? [String: Any],
                  let name = json["event"] as? String, !name.isEmpty else {
                if let progress { event(progress) }
                progress = nil; malformed = true
                continue
            }
            if let previous = progress, advances(previous, json) {
                progress = json
            } else {
                if let previous = progress { event(previous) }
                progress = json
            }
            if name == "complete" { sawComplete = true }
            if name == "error" { sawError = true }
        }
        if let progress { event(progress) }
    }

    func finish(code: Int32, cancelled: Bool, event: ([String: Any]) -> Void,
                finished: (Int32, Bool) -> Void) {
        if malformed && (!sawError || sawComplete) {
            // A valid complete event means publication happened. Without a safe
            // engine error, the output state is also uncertain: never claim no output.
            event(["event": "error", "output_published": true,
                   "message": "The engine response could not be fully read. Check the batch and output location before retrying; completed output may already be present."])
        }
        finished(malformed && code == 0 ? 1 : code, cancelled)
    }
}

// All blocking process I/O stays on one background queue. The lock only protects
// process ownership/cancellation; UI events are delivered in order on the main queue.
final class EngineRunner: @unchecked Sendable {
    private let lock = NSLock()
    private var process: Process?
    private var cancelled = false

    func cancel() {
        lock.lock()
        if cancelled { lock.unlock(); return }
        cancelled = true
        if let process, process.isRunning { process.terminate() }
        lock.unlock()
    }

    func start(arguments: [String], event: @escaping @MainActor @Sendable ([String: Any]) -> Void,
               finished: @escaping @MainActor @Sendable (Int32, Bool) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async { [self] in
            guard let resources = Bundle.main.resourceURL else {
                DispatchQueue.main.async { event(["event": "error", "message": "The app resources are missing. Reinstall the app and retry."]); finished(1, false) }
                return
            }
            let interpreter = resources.appendingPathComponent("python/bin/python3").path
            guard FileManager.default.isExecutableFile(atPath: interpreter) else {
                DispatchQueue.main.async { event(["event": "error", "message": "The bundled Python runtime is missing. Reinstall the app from the official release."]); finished(1, false) }
                return
            }
            let task = Process()
            let pipe = Pipe()
            task.executableURL = URL(fileURLWithPath: interpreter)
            task.arguments = ["-I", "-B", "-u", resources.appendingPathComponent("bootstrap.py").path] + arguments
            task.standardOutput = pipe
            // Raw library diagnostics can include original identifiers or filenames.
            // The engine emits safe, structured errors on stdout instead.
            task.standardError = FileHandle.nullDevice
            task.standardInput = FileHandle.nullDevice
            lock.lock()
            if cancelled { lock.unlock(); DispatchQueue.main.async { finished(130, true) }; return }
            process = task
            do { try task.run() } catch {
                process = nil; lock.unlock()
                DispatchQueue.main.async { event(["event": "error", "message": "The anonymization engine could not start. Reinstall the app and retry."]); finished(1, false) }
                return
            }
            lock.unlock()
            var stream = EngineEventStream()
            let delivery = DispatchQueue.main.sync { EngineEventDelivery() }
            while true {
                let chunk = pipe.fileHandleForReading.availableData
                if chunk.isEmpty { break }
                let lines = stream.append(chunk)
                // At most one delivery batch is outstanding. Backpressure stays
                // on this I/O worker, not on the main actor or an unbounded queue.
                if !lines.isEmpty {
                    DispatchQueue.main.sync { delivery.deliver(lines, event: event) }
                }
            }
            let tail = stream.finish()
            if !tail.isEmpty { DispatchQueue.main.sync { delivery.deliver(tail, event: event) } }
            task.waitUntilExit()
            lock.lock(); process = nil; let stopped = cancelled; lock.unlock()
            let code = task.terminationStatus
            DispatchQueue.main.async { delivery.finish(code: code, cancelled: stopped, event: event, finished: finished) }
        }
    }
}

struct InterruptionNotice: Sendable {
    let message: String
    let location: URL
    let ownedStaging: Bool
    let publicationPossible: Bool
}

// Records are local operational state, never part of a batch report or upload.
enum InterruptionRecovery {
    static var directory: URL? {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first?
            .appendingPathComponent("DICOM Anonymizer/Operations", isDirectory: true)
    }
    static func identity(_ url: URL) -> (UInt64, UInt64)? {
        guard let values = try? url.resourceValues(forKeys: [.isSymbolicLinkKey, .isDirectoryKey]),
              values.isSymbolicLink == false, values.isDirectory == true,
              let attributes = try? FileManager.default.attributesOfItem(atPath: url.path),
              let device = attributes[.systemNumber] as? NSNumber,
              let inode = attributes[.systemFileNumber] as? NSNumber else { return nil }
        return (device.uint64Value, inode.uint64Value)
    }
    static func record(_ url: URL) -> [String: Any]? {
        guard let values = try? url.resourceValues(forKeys: [.isSymbolicLinkKey, .isRegularFileKey, .fileSizeKey]),
              values.isSymbolicLink == false, values.isRegularFile == true,
              let size = values.fileSize, size > 0, size <= 65536,
              let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let schema = eventCount(json["schema"]), schema == 1,
              let operationID = json["operation_id"] as? String, UUID(uuidString: operationID) != nil,
              let phase = json["phase"] as? String,
              ["started", "allocated", "publishing", "published", "cleaned"].contains(phase),
              let output = json["output"] as? String, output.hasPrefix("/"),
              eventCount(json["pid"]) != nil else { return nil }
        return json
    }
    static func matches(_ url: URL, _ record: [String: Any]) -> Bool {
        guard let actual = identity(url), let device = record["device"] as? NSNumber,
              let inode = record["inode"] as? NSNumber else { return false }
        return actual.0 == device.uint64Value && actual.1 == inode.uint64Value
    }
    static func inspect(_ url: URL, ownerIsRunning: (Int) -> Bool = { pid in
        guard pid > 0, pid <= Int(Int32.max) else { return false }
        return kill(pid_t(pid), 0) == 0 || errno == EPERM
    }) -> InterruptionNotice? {
        guard let record = record(url), let phase = record["phase"] as? String,
              ["started", "allocated", "publishing", "published"].contains(phase),
              let outputPath = record["output"] as? String, outputPath.hasPrefix("/") else { return nil }
        if let pid = record["pid"] as? Int, ownerIsRunning(pid) { return nil }
        let output = URL(fileURLWithPath: outputPath).standardizedFileURL
        if ["publishing", "published"].contains(phase) && matches(output, record) {
            return InterruptionNotice(message: "A previous batch appears to have been published, but completion was not acknowledged. Review the output before retrying.", location: output, ownedStaging: false, publicationPossible: true)
        }
        if let path = record["staging"] as? String, path.hasPrefix("/") {
            let staging = URL(fileURLWithPath: path).standardizedFileURL
            if staging.deletingLastPathComponent() == output.deletingLastPathComponent(),
               staging.lastPathComponent.hasPrefix(".dicom-batch-"), matches(staging, record) {
                return InterruptionNotice(message: "A previous batch was interrupted and its staging identity still matches the recovery record. Review the incomplete staging folder before starting again. Nothing will be resumed or deleted automatically.", location: staging, ownedStaging: true, publicationPossible: false)
            }
        }
        return InterruptionNotice(message: "A previous batch was interrupted, but its staging or publication outcome cannot be confirmed. Inspect the output location before retrying; no automatic cleanup was attempted.", location: output.deletingLastPathComponent(), ownedStaging: false, publicationPossible: true)
    }
    static func firstNotice(in directory: URL) -> InterruptionNotice? {
        guard let files = try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil) else { return nil }
        for file in files.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) where file.pathExtension == "json" {
            if record(file) == nil {
                return InterruptionNotice(message: "A local recovery record could not be read safely. Inspect the recovery location and output before retrying; no automatic cleanup was attempted.", location: directory, ownedStaging: false, publicationPossible: true)
            }
            if let notice = inspect(file) { return notice }
        }
        return nil
    }
    static func acknowledge(_ journal: URL?, output: URL) {
        guard let journal, let record = record(journal), record["phase"] as? String == "published",
              record["output"] as? String == output.path, matches(output, record) else { return }
        // The worker has exited and each operation has a unique record path.
        try? FileManager.default.removeItem(at: journal)
    }
}

enum BatchProblem { case input, output, processing, report }
enum OutputIssue: String { case space, permissions, unavailable, conflict, unknown }
enum BatchProcessingPhase { case writing, auditing, finalizing }
enum SidecarProcessingPhase { case writing, auditing }

@MainActor
final class BatchModel: ObservableObject {
    // ObservableObject retains the original app's macOS 13 deployment target.
    @Published var source: URL?
    @Published var outputParent: URL?
    @Published var patients: [PatientRow] = []
    @Published var total = 0
    @Published var processed = 0
    @Published private(set) var processingPhase: BatchProcessingPhase = .writing
    @Published private(set) var auditedFiles = 0
    @Published private(set) var auditTotalFiles = 0
    @Published var excluded = 0
    @Published private(set) var cleanJSONSidecars = false
    @Published private(set) var sidecarFiles = 0
    @Published private(set) var processedSidecars = 0
    @Published private(set) var auditedSidecars = 0
    @Published private(set) var sidecarPhase: SidecarProcessingPhase?
    @Published var activePatient: String?
    @Published var busy = false
    @Published var scanning = false
    @Published private(set) var examiningInput = false
    @Published private(set) var scanFilesExamined = 0
    @Published private(set) var scanFoldersExamined = 0
    @Published private(set) var checkingSidecars = false
    @Published private(set) var sidecarFilesExamined = 0
    @Published private(set) var sidecarFoldersExamined = 0
    @Published var ready = false
    @Published var status = "Choose a batch folder to begin."
    @Published var errorMessage: String?
    @Published var problem: BatchProblem = .processing
    @Published var problemURL: URL?
    @Published private(set) var cancelling = false
    @Published private(set) var cleanupIncomplete = false
    @Published private(set) var outputIssue: OutputIssue?
    @Published var completedOutput: URL?
    @Published var runStarted: Date?
    @Published var summary: CompletionSummary?
    private var runner: EngineRunner?
    static let outputDefaultsKey = "OutputParentPath"

    private let defaults: UserDefaults
    private var activeJournal: URL?

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if defaults === UserDefaults.standard, let directory = InterruptionRecovery.directory {
            DispatchQueue.global(qos: .utility).async { [weak self] in
                let notice = InterruptionRecovery.firstNotice(in: directory)
                DispatchQueue.main.async {
                    guard let self, let notice, !self.busy, self.source == nil, self.summary == nil else { return }
                    self.presentInterruption(notice)
                }
            }
        }
        // Restore the last chosen output location only when it is still an existing folder.
        if let path = defaults.string(forKey: Self.outputDefaultsKey) {
            var isDirectory: ObjCBool = false
            if FileManager.default.fileExists(atPath: path, isDirectory: &isDirectory), isDirectory.boolValue {
                outputParent = URL(fileURLWithPath: path, isDirectory: true)
            } else {
                defaults.removeObject(forKey: Self.outputDefaultsKey)
            }
        }
    }

    private func isDirectory(_ url: URL) -> Bool {
        var directory: ObjCBool = false
        return url.isFileURL && FileManager.default.fileExists(atPath: url.path, isDirectory: &directory) && directory.boolValue
    }

    @discardableResult private func validateOutput(_ url: URL) -> Bool {
        guard isDirectory(url) else {
            if !cleanupIncomplete {
                outputIssue = .unavailable
                presentProblem(.output, message: "The output location is no longer an accessible folder.", url: url)
            }
            return false
        }
        return true
    }

    func setOutputParent(_ url: URL) {
        guard !busy, validateOutput(url) else { return }
        outputParent = url.standardizedFileURL
        defaults.set(url.standardizedFileURL.path, forKey: Self.outputDefaultsKey)
        if problem == .output { clearProblem(); status = idleStatus }
    }
    private var scanReceived = false
    private var completeReceived = false
    private var completedSidecars: Int?
    private var completedSidecarAudits: Int?
    private var terminationReply: ((Bool) -> Void)?
    private var activeOutput: URL?
    private var engineCancelled = false
    private var publishedWithoutConfirmation = false
    private var openPanel: NSOpenPanel?

    func selectSource(_ url: URL) {
        guard !busy else { return }
        guard isDirectory(url) else {
            rejectSource(url, message: "The selected item is not an accessible folder. Choose the parent folder containing numerical patient subfolders.")
            return
        }
        clearProblem()
        source = url.standardizedFileURL
        if outputParent == nil { outputParent = url.deletingLastPathComponent() }
        scan()
    }

    func chooseSource() {
        chooseFolder(title: "Choose the folder containing all patient folders") { self.selectSource($0) }
    }

    func chooseOutput() {
        chooseFolder(title: "Choose where to save the new anonymized batch") { self.setOutputParent($0) }
    }

    private func chooseFolder(title: String, completion: @escaping (URL) -> Void) {
        guard !busy, openPanel == nil else { return }
        let panel = NSOpenPanel()
        openPanel = panel
        panel.title = title
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = true
        panel.prompt = "Choose Folder"
        panel.begin { [weak self] result in
            Task { @MainActor in
                self?.openPanel = nil
                guard result == .OK, let url = panel.url else { return }
                completion(url)
            }
        }
    }

    func setCleanJSONSidecars(_ enabled: Bool) {
        guard !busy, enabled != cleanJSONSidecars else { return }
        cleanJSONSidecars = enabled
        sidecarFiles = 0; resetProcessingProgress(); ready = false
        if source != nil { clearProblem(); scan() }
    }

    func engineArguments(source: URL, output: URL?) -> [String] {
        var arguments = ["--source", source.path]
        if let output { arguments += ["--destination", output.path] }
        else { arguments.append("--scan") }
        if cleanJSONSidecars { arguments.append("--clean-json-sidecars") }
        return arguments
    }

    func scan() {
        guard canScan, let source else { return }
        patients = []; total = 0; excluded = 0; processed = 0; sidecarFiles = 0
        ready = false; completedOutput = nil; summary = nil
        launch(arguments: engineArguments(source: source, output: nil), isScan: true, output: nil)
    }

    func anonymize() {
        guard canAnonymize, let source, let outputParent, validateOutput(outputParent) else { return }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        let output = outputParent.appendingPathComponent("Anonymized_" + formatter.string(from: Date()) + "_" + UUID().uuidString.prefix(6))
        processed = 0; completedOutput = nil; summary = nil
        launch(arguments: engineArguments(source: source, output: output), isScan: false, output: output)
    }

    func beginRunState(isScan: Bool, output: URL?) {
        resetProcessingProgress()
        examiningInput = true; scanFilesExamined = 0; scanFoldersExamined = 0
        checkingSidecars = false; sidecarFilesExamined = 0; sidecarFoldersExamined = 0
        activeOutput = output
        engineCancelled = false
        publishedWithoutConfirmation = false
        busy = true; scanning = isScan; cancelling = false; clearProblem()
        scanReceived = false; completeReceived = false
        completedSidecars = nil; completedSidecarAudits = nil
        runStarted = isScan ? nil : Date()
        status = isScan ? "Checking patient folders and DICOM metadata…" : "Checking the batch before processing…"
    }

    func presentInterruption(_ notice: InterruptionNotice) {
        guard !busy, source == nil, summary == nil, errorMessage == nil else { return }
        ready = false; cleanupIncomplete = notice.ownedStaging
        publishedWithoutConfirmation = notice.publicationPossible
        presentProblem(.output, message: notice.message, url: notice.location)
    }

    private func launch(arguments: [String], isScan: Bool, output: URL?) {
        beginRunState(isScan: isScan, output: output)
        let worker = EngineRunner(); runner = worker
        var workerArguments = arguments
        activeJournal = nil
        if !isScan, let directory = InterruptionRecovery.directory {
            let journal = directory.appendingPathComponent(UUID().uuidString + ".json")
            activeJournal = journal
            workerArguments += ["--journal", journal.path]
        }
        worker.start(arguments: workerArguments, event: { [weak self] event in
            self?.receive(event)
        }, finished: { [weak self] code, cancelled in
            self?.finishRun(code: code, cancelled: cancelled, isScan: isScan, output: output)
        })
    }

    // Engine events and process exit are reduced in one place, including quit replies.
    func finishRun(code: Int32, cancelled: Bool, isScan: Bool, output: URL?) {
        var outcomeUncertain = false
        let elapsed = runStarted.map { Date().timeIntervalSince($0) } ?? 0
        busy = false; scanning = false; examiningInput = false; cancelling = false; runner = nil; activePatient = nil; runStarted = nil
        if code == 0 && !isScan && completeReceived, let output {
            completedOutput = output
            summary = CompletionSummary(patients: completedPatients ?? patients.count, files: processed,
                                             excluded: excluded, output: output, elapsed: elapsed,
                                             sidecars: cleanJSONSidecars ? completedSidecars : nil,
                                             auditedSidecars: cleanJSONSidecars ? completedSidecarAudits : nil)
            status = idleStatus
            InterruptionRecovery.acknowledge(activeJournal, output: output)
        } else if cleanupIncomplete {
            ready = false
            status = "Incomplete output needs attention."
        } else if engineCancelled || (cancelled && code == 130 && errorMessage == nil) {
            status = "Cancelled. No completed batch was published."
            clearProblem()
            if isScan { ready = false }
        } else if problem == .output, outputIssue != nil {
            // Keep an accepted preview for output replacement. The engine always
            // scans again before writing when the user retries the batch.
            ready = ready || (scanReceived && !patients.isEmpty && total > 0)
            status = problemTitle + "."
        } else if code == 0 && isScan && scanReceived {
            ready = true
            status = "Ready · \(patients.count) patients and \(total) DICOM files."
        } else {
            ready = false
            status = "Batch needs attention."
            if errorMessage == nil {
                if isScan {
                    presentProblem(.processing, message: "Folder checking stopped before it could be completed. Check the batch again.")
                } else {
                    outcomeUncertain = true
                    presentProblem(.processing, message: "The engine stopped before completion could be confirmed. Check the output location before retrying; a completed batch may already be present.", url: output)
                }
            }
        }
        activeOutput = nil; activeJournal = nil
        let reply = terminationReply; terminationReply = nil
        reply?(!cleanupIncomplete && !outcomeUncertain && !publishedWithoutConfirmation)
    }

    private func cleanupLocation(_ value: Any?) -> URL? {
        guard let path = value as? String, path.hasPrefix("/"), let activeOutput else { return nil }
        let location = URL(fileURLWithPath: path, isDirectory: true).standardizedFileURL
        guard location != activeOutput.standardizedFileURL, location != source?.standardizedFileURL,
              location.deletingLastPathComponent() == activeOutput.deletingLastPathComponent().standardizedFileURL,
              location.lastPathComponent.hasPrefix(".dicom-batch-"),
              location.lastPathComponent.count > ".dicom-batch-".count else { return nil }
        return location
    }

    private var completedPatients: Int?

    // Unknown event names and unknown or malformed fields are ignored, so engine and
    // report additions from other lanes stay backward compatible with this UI.
    func receive(_ event: [String: Any]) {
        guard let name = event["event"] as? String else { return }
        switch name {
        case "scan_progress":
            guard busy, examiningInput, !checkingSidecars, !scanReceived, !cancelling, errorMessage == nil,
                  processingPhase == .writing,
                  let files = eventCount(event["files_examined"]),
                  let folders = eventCount(event["folders_examined"]),
                  files >= scanFilesExamined, folders >= scanFoldersExamined else { return }
            scanFilesExamined = files; scanFoldersExamined = folders
            status = progressDetail
        case "sidecar_scan_progress":
            guard busy, examiningInput, cleanJSONSidecars, !scanReceived, !cancelling, errorMessage == nil,
                  let files = eventCount(event["files_examined"]),
                  let folders = eventCount(event["folders_examined"]),
                  files >= sidecarFilesExamined, folders >= sidecarFoldersExamined else { return }
            checkingSidecars = true
            sidecarFilesExamined = files; sidecarFoldersExamined = folders
            status = progressDetail
        case "scan":
            guard !cancelling, processingPhase == .writing else { return }
            resetProcessingProgress()
            examiningInput = false; checkingSidecars = false
            patients = (event["patients"] as? [Any] ?? []).compactMap { item in
                guard let row = item as? [String: Any], let id = row["id"] as? String, !id.isEmpty else { return nil }
                return PatientRow(id: id, files: eventCount(row["files"]) ?? 0, series: eventCount(row["series"]) ?? 0)
            }
            total = eventCount(event["total_files"]) ?? 0
            excluded = eventCount(event["excluded_files"]) ?? 0
            sidecarFiles = cleanJSONSidecars ? eventCount(event["sidecar_files"]) ?? 0 : 0
            completedPatients = nil
            scanReceived = true
        case "progress":
            guard !cancelling, processingPhase == .writing else { return }
            if let reported = eventCount(event["total_files"]), reported > 0 { total = reported }
            processed = min(eventCount(event["processed"]) ?? processed, max(total, processed))
            if let patient = event["patient_id"] as? String, !patient.isEmpty { activePatient = patient }
            status = progressDetail
        case "sidecar_progress", "sidecar_audit_progress":
            guard busy, !scanning, !cancelling, errorMessage == nil, cleanJSONSidecars,
                  scanReceived, !examiningInput, processingPhase != .finalizing,
                  total > 0, processed >= total,
                  let count = eventCount(event[name == "sidecar_progress" ? "processed" : "audited_files"]),
                  let reportedTotal = eventCount(event["total_files"]),
                  reportedTotal == sidecarFiles, count <= sidecarFiles else { return }
            if name == "sidecar_progress" {
                guard processingPhase == .writing, sidecarPhase != .auditing,
                      count >= processedSidecars else { return }
                processedSidecars = count; sidecarPhase = .writing
            } else {
                guard processingPhase == .auditing, auditedFiles == auditTotalFiles,
                      processedSidecars == sidecarFiles, count >= auditedSidecars else { return }
                auditedSidecars = count; sidecarPhase = .auditing
            }
            activePatient = nil; status = progressDetail
        case "audit_progress":
            guard busy, !scanning, !cancelling, processingPhase != .finalizing, sidecarPhase != .auditing,
                  let audited = eventCount(event["audited_files"]),
                  let auditTotal = eventCount(event["total_files"]),
                  total > 0, processed >= total, auditTotal == total, audited <= auditTotal else { return }
            if processingPhase == .auditing {
                guard auditTotal == auditTotalFiles, audited >= auditedFiles else { return }
            }
            sidecarPhase = nil
            processingPhase = .auditing
            auditedFiles = audited; auditTotalFiles = auditTotal; activePatient = nil
            status = progressDetail
        case "phase":
            guard busy, !scanning, !cancelling, event["name"] as? String == "finalizing",
                  processingPhase == .auditing, auditTotalFiles > 0, auditedFiles == auditTotalFiles,
                  (!cleanJSONSidecars || (processedSidecars == sidecarFiles && auditedSidecars == sidecarFiles)) else { return }
            sidecarPhase = nil
            processingPhase = .finalizing; activePatient = nil
            status = progressDetail
        case "complete":
            if cleanJSONSidecars,
               let written = eventCount(event["sidecar_files"]),
               let checked = eventCount(event["sidecar_audited_files"]),
               written == sidecarFiles, checked == written {
                completedSidecars = written; completedSidecarAudits = checked
            }
            processed = eventCount(event["processed"]) ?? total
            completedPatients = eventCount(event["patients"])
            if let value = eventCount(event["excluded_files"]) { excluded = value }
            completeReceived = true
        case "error":
            outputIssue = nil
            engineCancelled = event["cancelled"] as? Bool == true
            publishedWithoutConfirmation = event["output_published"] as? Bool == true
            let message = (event["message"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "The batch could not be processed."
            if busy, !scanning, event["cleanup_failed"] as? Bool == true {
                cleanupIncomplete = true
                presentProblem(.output, message: message, url: cleanupLocation(event["staging_path"]))
            } else if busy, !scanning, !publishedWithoutConfirmation, let activeOutput,
                      let value = event["output_issue"] as? String, let issue = OutputIssue(rawValue: value) {
                outputIssue = issue
                presentProblem(.output, message: message, url: activeOutput.deletingLastPathComponent())
            } else {
                presentProblem(.processing, message: message, url: publishedWithoutConfirmation ? activeOutput : nil)
            }
        default: break
        }
    }

    func copyErrorDetails() {
        guard let errorMessage else { return }
        // Only the generic engine message is copied: no identifiers, paths or UIDs.
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "2.0"
        let details = "DICOM Anonymizer \(version) error\n\(errorMessage)"
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(details, forType: .string)
    }

    func revealOutput() {
        guard canInspectOutput, let output = completedOutput else { return }
        NSWorkspace.shared.activateFileViewerSelecting([output])
    }

    func openReport() {
        guard canInspectOutput, let output = completedOutput else { return }
        let report = output.appendingPathComponent("anonymization-report.json")
        var directory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: report.path, isDirectory: &directory), !directory.boolValue else {
            presentProblem(.report, message: "The anonymization report could not be found. Check whether the output batch was moved or deleted.", url: output)
            return
        }
        if NSWorkspace.shared.open(report) { dismissReportProblem() }
        else { presentProblem(.report, message: "The report could not be opened. Reveal the output folder and try opening it there.", url: output) }
    }

    var hasBlockingProblem: Bool { errorMessage != nil && problem != .report }
    var canAnonymize: Bool { ready && !busy && outputParent != nil && !hasBlockingProblem }
    var canScan: Bool { source != nil && !busy && (errorMessage == nil || problem == .processing) }
    var canInspectOutput: Bool { completedOutput != nil && !busy }

    var problemTitle: String {
        switch problem {
        case .input: return "Choose a batch folder"
        case .output:
            if cleanupIncomplete { return "Incomplete output needs attention" }
            switch outputIssue {
            case .space: return "Not enough disk space"
            case .permissions: return "Output location is not writable"
            case .conflict: return "Choose another output location"
            default: return "Output location unavailable"
            }
        case .processing: return "Batch needs attention"
        case .report: return "Report unavailable"
        }
    }
    var recoveryMessage: String {
        switch problem {
        case .input: return "Choose the parent folder containing numerical patient subfolders, such as 00001."
        case .output:
            if cleanupIncomplete {
                return problemURL == nil
                    ? "Reconnect the output volume and inspect it for incomplete staging from this run. Its folder could not be identified safely here. Choose an output location, then check the batch again. Source files were not changed."
                    : "Reconnect the output volume and remove only the incomplete staging folder shown here. Choose an output location, then check the batch again. Source files were not changed."
            }
            switch outputIssue {
            case .space:
                return "Free space at this location or choose another output folder, then try again. The space estimate is approximate; available space can change while processing."
            case .permissions:
                return "Choose a writable output folder, or restore write access to this location, then choose it again and retry."
            case .conflict:
                return "Choose an output location and try again. Each run creates a new batch folder; existing output is never overwritten."
            case .unknown:
                return "Check the output volume and choose another writable location, then try again."
            default:
                return "Reconnect the output volume or choose another existing folder, then try again."
            }
        case .processing: return "Correct the reported problem, then check again. You can change the batch folder or output location."
        case .report: return "Reveal the output location to look for the report, or dismiss this message. The completed-batch record is kept."
        }
    }
    var recoveryTitle: String {
        switch problem {
        case .input: "Choose Folder…"
        case .output: "Choose Location…"
        case .processing: source == nil ? "Choose Folder…" : "Check Again"
        case .report: "Reveal Output"
        }
    }
    func recover() {
        guard !busy else { return }
        switch problem {
        case .input: chooseSource()
        case .output: chooseOutput()
        case .processing: if source == nil { chooseSource() } else { scan() }
        case .report: revealOutput()
        }
    }
    private var idleStatus: String {
        if let summary {
            return "Complete · \(summary.files) DICOM files across \(summary.patients) patients in \(elapsedText(summary.elapsed))." + (summary.sidecarDetail.map { " " + $0 + "." } ?? "")
        }
        return ready ? "Ready · \(patients.count) patients and \(total) DICOM files." : "Choose a batch folder to begin."
    }
    private func clearProblem() {
        errorMessage = nil; problemURL = nil; problem = .processing; cleanupIncomplete = false; outputIssue = nil
    }
    private func presentProblem(_ kind: BatchProblem, message: String, url: URL? = nil) {
        problem = kind; problemURL = url; errorMessage = message
        if kind == .processing { ready = false }
        if kind != .report { status = problemTitle + "." }
    }
    private func rejectSource(_ url: URL?, message: String) {
        resetProcessingProgress()
        source = nil; ready = false; patients = []; total = 0; processed = 0; excluded = 0; activePatient = nil
        presentProblem(.input, message: message, url: url)
    }
    func dismissReportProblem() {
        guard !busy, problem == .report else { return }
        clearProblem(); status = idleStatus
    }

    func resetProcessingProgress() {
        processingPhase = .writing; auditedFiles = 0; auditTotalFiles = 0
        processedSidecars = 0; auditedSidecars = 0; sidecarPhase = nil; activePatient = nil
    }

    var isFinalizing: Bool {
        sidecarPhase == nil && !examiningInput && !(cleanJSONSidecars && sidecarFiles > 0 && processingPhase == .writing) && (processingPhase == .finalizing || (processingPhase == .writing && total > 0 && processed >= total))
    }
    var progressFraction: Double? {
        guard !cancelling, !examiningInput, !isFinalizing else { return nil }
        if sidecarPhase == .writing { return sidecarFiles > 0 ? Double(processedSidecars) / Double(sidecarFiles) : nil }
        if sidecarPhase == .auditing { return sidecarFiles > 0 ? Double(auditedSidecars) / Double(sidecarFiles) : nil }
        if cleanJSONSidecars && sidecarFiles > 0 && processingPhase == .writing && processed >= total { return nil }
        if processingPhase == .auditing {
            return auditTotalFiles > 0 ? Double(auditedFiles) / Double(auditTotalFiles) : nil
        }
        return processed > 0 && total > 0 ? Double(processed) / Double(total) : nil
    }
    var progressTitle: String {
        if cancelling { return "Cancelling" }
        if examiningInput && checkingSidecars { return "Checking JSON sidecars" }
        if examiningInput { return "Checking batch" }
        if sidecarPhase == .writing { return "Cleaning JSON sidecars" }
        if sidecarPhase == .auditing { return "Checking JSON sidecars" }
        if processingPhase == .auditing { return "Checking output" }
        return isFinalizing ? "Finalizing batch" : processed == 0 ? "Preparing batch" : "Anonymizing"
    }
    var progressDetail: String {
        if cancelling { return "Waiting for the engine to stop or finish publication…" }
        if sidecarPhase == .writing { return "\(processedSidecars) of \(sidecarFiles) JSON sidecars cleaned" }
        if sidecarPhase == .auditing { return "\(auditedSidecars) of \(sidecarFiles) JSON sidecars checked" }
        if examiningInput && checkingSidecars { return "\(sidecarFilesExamined) JSON files · \(sidecarFoldersExamined) folders examined" }
        if examiningInput {
            return String(localized: "\(scanFilesExamined) files · \(scanFoldersExamined) folders examined")
        }
        if processingPhase == .auditing { return "\(auditedFiles) of \(auditTotalFiles) files checked" }
        if processingPhase == .finalizing { return "Checks passed. Preparing the report and publishing the batch…" }
        return isFinalizing ? "Writing is complete. Checking output and preparing the report…" :
            processed == 0 ? "Checking the batch before writing files…" :
            "Anonymizing patient \(activePatient ?? "—") · \(processed) of \(total) files"
    }

    func cancel() {
        guard busy, !cancelling else { return }
        cancelling = true; status = "Cancellation requested. Waiting for the engine…"; runner?.cancel()
    }

    func prepareToQuit(completion: @escaping (Bool) -> Void) {
        terminationReply = completion
        cancel()
    }

    func acceptDrop(_ providers: [NSItemProvider]) -> Bool {
        guard !busy, providers.count == 1, let provider = providers.first else { return false }
        provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { [weak self] item, _ in
            let url: URL?
            if let data = item as? Data { url = URL(dataRepresentation: data, relativeTo: nil) }
            else if let value = item as? URL { url = value }
            else { url = nil }
            Task { @MainActor in
                if let url { self?.selectSource(url) }
                else if let self, !self.busy { self.rejectSource(nil, message: "The dropped folder could not be read. Use Choose Folder.") }
            }
        }
        return true
    }
}

struct BatchHeader: View {
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "square.stack.3d.up.fill").foregroundStyle(.tint)
                .padding(10).background(.tint.opacity(0.1), in: RoundedRectangle(cornerRadius: 10))
            VStack(alignment: .leading, spacing: 6) {
                Text("DICOM Anonymizer 2.0").bold()
                Text("Anonymize a whole batch while keeping every patient identifier aligned.").foregroundStyle(.secondary)
            }
            Spacer()
            Text("BULK WORKFLOW").foregroundStyle(.secondary)
        }
    }
}

final class DropState: ObservableObject {
    @Published var targeted = false
}

struct FolderInput: View {
    let source: URL?
    let busy: Bool
    let choose: () -> Void
    let acceptDrop: ([NSItemProvider]) -> Bool
    @StateObject private var drop = DropState()
    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "folder.badge.plus").foregroundStyle(.tint)
            Text(source?.lastPathComponent ?? "Drop a folder containing patient subfolders").bold()
                .lineLimit(2).truncationMode(.middle)
                .help(source?.path ?? "Choose the batch folder containing numerical patient folders.")
            Text("Each immediate patient folder must have a numerical name, such as 00001.")
                .foregroundStyle(.secondary)
            Button(source == nil ? "Choose Folder…" : "Change Folder…", action: choose).disabled(busy)
                .help("Choose a batch folder. Command-O.")
        }
        .frame(maxWidth: .infinity).padding(18)
        .background(drop.targeted ? Color.accentColor.opacity(0.10) : Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(drop.targeted ? Color.accentColor : Color.secondary.opacity(0.35), style: StrokeStyle(lineWidth: 1, dash: [5, 4])))
        .onDrop(of: [.fileURL], isTargeted: $drop.targeted, perform: acceptDrop)
        .accessibilityIdentifier("batchDropZone")
    }
}

struct PatientPreview: View {
    let patients: [PatientRow]
    let activePatient: String?
    let total: Int
    let excluded: Int
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack {
                Text("Patient preview").bold()
                Spacer()
                Text("\(patients.count) patients · \(total) DICOM files").foregroundStyle(.secondary)
            }
            HStack {
                Text("Folder / PatientName / PatientID").frame(maxWidth: .infinity, alignment: .leading)
                Text("Series").frame(width: 65, alignment: .trailing)
                Text("Files").frame(width: 70, alignment: .trailing)
            }.foregroundStyle(.secondary)
            Divider()
            ScrollView {
                LazyVStack(spacing: 9) {
                    ForEach(patients) { patient in
                        HStack {
                            Text(patient.id).monospaced().bold().lineLimit(1).truncationMode(.middle)
                                .help(patient.id).frame(maxWidth: .infinity, alignment: .leading)
                            if activePatient == patient.id { Text("Processing").foregroundStyle(.tint) }
                            Text("\(patient.series)").frame(width: 65, alignment: .trailing)
                            Text("\(patient.files)").frame(width: 70, alignment: .trailing)
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("Patient \(patient.id)")
                        .accessibilityValue("\(patient.series) series, \(patient.files) files" + (activePatient == patient.id ? ", processing" : ""))
                    }
                    if patients.isEmpty { Text("Patient identifiers will appear after the folder is checked.").foregroundStyle(.secondary).padding(.vertical, 20) }
                }
            }.frame(minHeight: 90, maxHeight: 145)
            if excluded > 0 { Text("\(excluded) non-DICOM or system files excluded from output.").foregroundStyle(.secondary) }
        }
        .padding(14).background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 10))
    }
}

struct OutputSection: View {
    let parent: URL?
    let disabled: Bool
    let choose: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Save anonymized batch in").bold()
                    Text(parent?.path ?? "Choose an output location").id(parent).lineLimit(2).truncationMode(.middle).textSelection(.enabled).foregroundStyle(.secondary)
                        .help(parent?.path ?? "Choose where new anonymized batches will be saved.")
                }
                Spacer()
                Button("Choose Location…", action: choose).disabled(disabled)
                    .help("Choose an output location. Shift-Command-O.")
            }
            Text("A new Anonymized folder is created for each run. Source files stay intact.").foregroundStyle(.secondary)
        }
    }
}

struct BatchProgress: View {
    let title: String
    let detail: String
    let fraction: Double?
    let started: Date?
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let fraction {
                Text(title).bold()
                ProgressView(value: fraction)
                    .accessibilityLabel("Anonymization progress")
                    .accessibilityValue(detail)
            } else {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text(title).bold()
                }
                .accessibilityElement(children: .combine)
            }
            HStack {
                Text(detail)
                Spacer()
                if let started {
                    TimelineView(.periodic(from: started, by: 1)) { context in
                        Text("Elapsed \(elapsedText(context.date.timeIntervalSince(started)))").monospacedDigit()
                    }
                }
            }
            .foregroundStyle(.secondary)
            .accessibilityElement(children: .combine)
        }
        .accessibilityIdentifier("batchProgress")
    }
}

struct CompletionView: View {
    let summary: CompletionSummary
    let reveal: () -> Void
    let openReport: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(.green).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 3) {
                    Text("Batch complete").bold()
                    Text(summary.output.lastPathComponent).lineLimit(2).truncationMode(.middle)
                        .textSelection(.enabled).help(summary.output.path)
                    if let detail = summary.sidecarDetail { Text(detail).foregroundStyle(.secondary).monospacedDigit() }
                    Text("\(summary.patients) patients · \(summary.files) files · \(summary.excluded) excluded · \(elapsedText(summary.elapsed))")
                        .foregroundStyle(.secondary).monospacedDigit()
                }
                .accessibilityElement(children: .combine)
                Spacer(minLength: 0)
            }
            HStack {
                Button("Reveal in Finder", action: reveal).help("Show the completed batch in Finder. Shift-Command-R.")
                Button("Open Report", action: openReport).help("Open the anonymization report. Option-Command-R.")
            }
        }
        .padding(10)
        .background(Color.green.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
        .accessibilityIdentifier("completionSummary")
    }
}

struct SidecarOptions: View {
    @ObservedObject var model: BatchModel
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Toggle("Clean JSON sidecars", isOn: Binding(get: { model.cleanJSONSidecars }, set: model.setCleanJSONSidecars))
                .disabled(model.busy)
            Text("Optional MRI metadata allowlist. Writes generated JSON copies; source files stay intact. NIfTI images are not copied or cleaned.")
                .foregroundStyle(.secondary)
            if model.cleanJSONSidecars {
                Text("\(model.sidecarFiles) JSON sidecars in the last batch check.").foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 10))
    }
}

struct PolicySummary: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("Identifier preserved in folder, PatientName and PatientID. New internal folder and file names.")
            Text("Series descriptions and sequence names retained. Other patient identifiers, dates and private tags anonymized.")
            Text("Numerical identifiers remain linkable to your patient list. Pixel text is not redacted. Review images before sharing. MR, CT and RTSTRUCT supported.").foregroundStyle(.secondary)
        }
    }
}

struct BatchView: View {
    @ObservedObject var model: BatchModel
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            BatchHeader()
            if let source = model.source {
                HStack {
                    Label(source.lastPathComponent, systemImage: "folder")
                        .lineLimit(1).truncationMode(.middle).help(source.path)
                    Spacer()
                    Button("Change Folder…", action: model.chooseSource).disabled(model.busy)
                        .help("Choose a different batch folder. Command-O.")
                }
            } else {
                FolderInput(source: nil, busy: model.busy, choose: model.chooseSource, acceptDrop: model.acceptDrop)
            }
            if model.errorMessage == nil {
                PatientPreview(patients: model.patients, activePatient: model.activePatient, total: model.total, excluded: model.excluded)
            }
            OutputSection(parent: model.outputParent, disabled: model.busy, choose: model.chooseOutput)
            SidecarOptions(model: model)
            Divider()
            if model.errorMessage == nil { PolicySummary() }
            if let error = model.errorMessage {
                VStack(alignment: .leading, spacing: 6) {
                    ViewThatFits(in: .vertical) {
                        recoveryText(error)
                        ScrollView { recoveryText(error) }.scrollIndicators(.visible)
                    }
                    .frame(minHeight: 30, maxHeight: .infinity, alignment: .topLeading)
                    if let location = model.problemURL ?? (model.problem == .output ? model.outputParent : model.source) {
                        Text("\(model.problem == .output ? "Location" : "Folder"): \(location.path)")
                            .lineLimit(2).truncationMode(.middle).textSelection(.enabled).help(location.path)
                    }
                    HStack {
                        Button(model.recoveryTitle, action: model.recover).disabled(model.busy)
                        if model.problem == .report {
                            Button("Dismiss", action: model.dismissReportProblem)
                        } else if model.problem == .processing {
                            if model.source != nil { Button("Choose Folder…", action: model.chooseSource).disabled(model.busy) }
                            Button("Choose Location…", action: model.chooseOutput).disabled(model.busy)
                        }
                        Spacer()
                        Button("Copy Details", action: model.copyErrorDetails)
                            .accessibilityHint("Copies the error message to the clipboard")
                    }
                }
                .accessibilityIdentifier("batchError")
                .layoutPriority(1)
            }
            VStack(alignment: .leading, spacing: 8) {
                if model.busy && model.errorMessage == nil {
                    if model.scanning { ProgressView().controlSize(.small).accessibilityLabel(model.cancelling ? "Cancelling" : "Checking batch") }
                    else { BatchProgress(title: model.progressTitle, detail: model.progressDetail, fraction: model.progressFraction, started: model.runStarted) }
                }
                if let summary = model.summary, !model.busy && !model.hasBlockingProblem {
                    CompletionView(summary: summary, reveal: model.revealOutput, openReport: model.openReport)
                }
                // Preflight already shows the new scan counts inside BatchProgress.
                // Initial scan still uses the existing spinner and this status line.
                if !model.busy || !model.examiningInput || model.scanning || model.cancelling || model.errorMessage != nil {
                    Text(model.status).id(model.status).accessibilityIdentifier("batchStatus").textSelection(.enabled)
                }
            }
            HStack {
                if model.busy { Button(model.cancelling ? "Cancelling…" : "Cancel", action: model.cancel).keyboardShortcut(.cancelAction).disabled(model.cancelling) }
                else if model.errorMessage == nil { Button("Check Again", action: model.scan).disabled(!model.canScan) }
                Spacer()
                if let output = model.completedOutput {
                    Button("Open Output") { NSWorkspace.shared.open(output) }.disabled(!model.canInspectOutput)
                }
                Button("Anonymize Batch", action: model.anonymize)
                    .buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
                    .disabled(!model.canAnonymize)
                    .accessibilityIdentifier("anonymizeBatch")
                    .accessibilityHint("Anonymizes every patient folder. Shortcut: Command-Return.")
                    .help(model.canAnonymize ? "Create a new anonymized batch. Command-Return." : "Choose a valid batch folder and output location first.")
            }
        }
        .font(.custom("Arial", size: 10))
        .padding(22)
        .frame(minWidth: 700, idealWidth: 780, minHeight: 655, idealHeight: 720)
        .background(Color(nsColor: .windowBackgroundColor))
        .onDrop(of: [.fileURL], isTargeted: nil, perform: model.acceptDrop)
    }

    private func recoveryText(_ error: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(model.problemTitle, systemImage: "exclamationmark.triangle.fill").bold().foregroundStyle(.red)
            Text(error).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            Text(model.recoveryMessage).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .fixedSize(horizontal: false, vertical: true)
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    weak var model: BatchModel?
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let model, model.busy else { return .terminateNow }
        model.prepareToQuit { mayQuit in sender.reply(toApplicationShouldTerminate: mayQuit) }
        return .terminateLater
    }
}

#if !MODEL_TEST
@main
struct DICOMAnonymizerApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var model = BatchModel()
    var body: some Scene {
        Window("DICOM Anonymizer 2.0", id: "batch") {
            BatchView(model: model).onAppear { delegate.model = model }
        }
        .defaultSize(width: 780, height: 720)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Open Batch Folder…", action: model.chooseSource).keyboardShortcut("o").disabled(model.busy)
                Button("Choose Output Location…", action: model.chooseOutput)
                    .keyboardShortcut("o", modifiers: [.command, .shift]).disabled(model.busy)
                Button("Check Again", action: model.scan)
                    .keyboardShortcut("r").disabled(!model.canScan)
                Button("Anonymize Batch", action: model.anonymize)
                    .keyboardShortcut(.return, modifiers: .command).disabled(!model.canAnonymize)
                Divider()
                Button("Reveal Output in Finder", action: model.revealOutput)
                    .keyboardShortcut("r", modifiers: [.command, .shift])
                    .disabled(!model.canInspectOutput)
                Button("Open Report", action: model.openReport)
                    .keyboardShortcut("r", modifiers: [.command, .option])
                    .disabled(!model.canInspectOutput)
            }
        }
    }
}
#endif
