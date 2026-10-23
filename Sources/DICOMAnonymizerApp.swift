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
            var pending = Data()
            while true {
                let chunk = pipe.fileHandleForReading.availableData
                if chunk.isEmpty { break }
                pending.append(chunk)
                while let boundary = pending.firstIndex(of: 10) {
                    let line = Data(pending[..<boundary])
                    pending.removeSubrange(...boundary)
                    // Transfer immutable Data; decode non-Sendable JSON only on the UI actor.
                    DispatchQueue.main.async {
                        if let json = try? JSONSerialization.jsonObject(with: line) as? [String: Any] {
                            event(json)
                        }
                    }
                }
            }
            task.waitUntilExit()
            lock.lock(); process = nil; let stopped = cancelled; lock.unlock()
            let code = task.terminationStatus
            DispatchQueue.main.async { finished(code, stopped) }
        }
    }
}

enum BatchProblem { case input, output, processing, report }
enum BatchProcessingPhase { case writing, auditing, finalizing }

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
    @Published var activePatient: String?
    @Published var busy = false
    @Published var scanning = false
    @Published var ready = false
    @Published var status = "Choose a batch folder to begin."
    @Published var errorMessage: String?
    @Published var problem: BatchProblem = .processing
    @Published var problemURL: URL?
    @Published private(set) var cancelling = false
    @Published private(set) var cleanupIncomplete = false
    @Published var completedOutput: URL?
    @Published var runStarted: Date?
    @Published var summary: CompletionSummary?
    private var runner: EngineRunner?
    static let outputDefaultsKey = "OutputParentPath"

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
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
            presentProblem(.output, message: "The output location is no longer an accessible folder.", url: url)
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

    func scan() {
        guard canScan, let source else { return }
        patients = []; total = 0; excluded = 0; processed = 0
        ready = false; completedOutput = nil; summary = nil
        launch(arguments: ["--source", source.path, "--scan"], isScan: true, output: nil)
    }

    func anonymize() {
        guard canAnonymize, let source, let outputParent, validateOutput(outputParent) else { return }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        let output = outputParent.appendingPathComponent("Anonymized_" + formatter.string(from: Date()) + "_" + UUID().uuidString.prefix(6))
        processed = 0; completedOutput = nil; summary = nil
        launch(arguments: ["--source", source.path, "--destination", output.path], isScan: false, output: output)
    }

    func beginRunState(isScan: Bool, output: URL?) {
        resetProcessingProgress()
        activeOutput = output
        engineCancelled = false
        publishedWithoutConfirmation = false
        busy = true; scanning = isScan; cancelling = false; clearProblem()
        scanReceived = false; completeReceived = false
        runStarted = isScan ? nil : Date()
        status = isScan ? "Checking patient folders and DICOM metadata…" : "Checking the batch before processing…"
    }

    private func launch(arguments: [String], isScan: Bool, output: URL?) {
        beginRunState(isScan: isScan, output: output)
        let worker = EngineRunner(); runner = worker
        worker.start(arguments: arguments, event: { [weak self] event in
            self?.receive(event)
        }, finished: { [weak self] code, cancelled in
            self?.finishRun(code: code, cancelled: cancelled, isScan: isScan, output: output)
        })
    }

    // Engine events and process exit are reduced in one place, including quit replies.
    func finishRun(code: Int32, cancelled: Bool, isScan: Bool, output: URL?) {
        var outcomeUncertain = false
        let elapsed = runStarted.map { Date().timeIntervalSince($0) } ?? 0
        busy = false; scanning = false; cancelling = false; runner = nil; activePatient = nil; runStarted = nil
        if code == 0 && !isScan && completeReceived, let output {
            completedOutput = output
            summary = CompletionSummary(patients: completedPatients ?? patients.count, files: processed,
                                             excluded: excluded, output: output, elapsed: elapsed)
            status = "Complete · \(processed) DICOM files across \(completedPatients ?? patients.count) patients in \(elapsedText(elapsed))."
        } else if cleanupIncomplete {
            ready = false
            status = "Incomplete output needs attention."
        } else if engineCancelled || (cancelled && code == 130 && errorMessage == nil) {
            status = "Cancelled. No completed batch was published."
            clearProblem()
            if isScan { ready = false }
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
        activeOutput = nil
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
        case "scan":
            guard !cancelling, processingPhase == .writing else { return }
            resetProcessingProgress()
            patients = (event["patients"] as? [Any] ?? []).compactMap { item in
                guard let row = item as? [String: Any], let id = row["id"] as? String, !id.isEmpty else { return nil }
                return PatientRow(id: id, files: eventCount(row["files"]) ?? 0, series: eventCount(row["series"]) ?? 0)
            }
            total = eventCount(event["total_files"]) ?? 0
            excluded = eventCount(event["excluded_files"]) ?? 0
            completedPatients = nil
            scanReceived = true
        case "progress":
            guard !cancelling, processingPhase == .writing else { return }
            if let reported = eventCount(event["total_files"]), reported > 0 { total = reported }
            processed = min(eventCount(event["processed"]) ?? processed, max(total, processed))
            if let patient = event["patient_id"] as? String, !patient.isEmpty { activePatient = patient }
            status = progressDetail
        case "audit_progress":
            guard busy, !scanning, !cancelling, processingPhase != .finalizing,
                  let audited = eventCount(event["audited_files"]),
                  let auditTotal = eventCount(event["total_files"]),
                  total > 0, processed >= total, auditTotal == total, audited <= auditTotal else { return }
            if processingPhase == .auditing {
                guard auditTotal == auditTotalFiles, audited >= auditedFiles else { return }
            }
            processingPhase = .auditing
            auditedFiles = audited; auditTotalFiles = auditTotal; activePatient = nil
            status = progressDetail
        case "phase":
            guard busy, !scanning, !cancelling, event["name"] as? String == "finalizing",
                  processingPhase == .auditing, auditTotalFiles > 0, auditedFiles == auditTotalFiles else { return }
            processingPhase = .finalizing; activePatient = nil
            status = progressDetail
        case "complete":
            processed = eventCount(event["processed"]) ?? total
            completedPatients = eventCount(event["patients"])
            if let value = eventCount(event["excluded_files"]) { excluded = value }
            completeReceived = true
        case "error":
            engineCancelled = event["cancelled"] as? Bool == true
            publishedWithoutConfirmation = event["output_published"] as? Bool == true
            let message = (event["message"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "The batch could not be processed."
            if busy, !scanning, event["cleanup_failed"] as? Bool == true {
                cleanupIncomplete = true
                presentProblem(.output, message: message, url: cleanupLocation(event["staging_path"]))
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
        case .input: "Choose a batch folder"
        case .output: cleanupIncomplete ? "Incomplete output needs attention" : "Output location unavailable"
        case .processing: "Batch needs attention"
        case .report: "Report unavailable"
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
            return "Reconnect the output volume or choose another existing folder, then try again."
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
            return "Complete · \(summary.files) DICOM files across \(summary.patients) patients in \(elapsedText(summary.elapsed))."
        }
        return ready ? "Ready · \(patients.count) patients and \(total) DICOM files." : "Choose a batch folder to begin."
    }
    private func clearProblem() {
        errorMessage = nil; problemURL = nil; problem = .processing; cleanupIncomplete = false
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
        processingPhase = .writing; auditedFiles = 0; auditTotalFiles = 0; activePatient = nil
    }

    var isFinalizing: Bool {
        processingPhase == .finalizing || (processingPhase == .writing && total > 0 && processed >= total)
    }
    var progressFraction: Double? {
        guard !cancelling, !isFinalizing else { return nil }
        if processingPhase == .auditing {
            return auditTotalFiles > 0 ? Double(auditedFiles) / Double(auditTotalFiles) : nil
        }
        return processed > 0 && total > 0 ? Double(processed) / Double(total) : nil
    }
    var progressTitle: String {
        if cancelling { return "Cancelling" }
        if processingPhase == .auditing { return "Checking output" }
        return isFinalizing ? "Finalizing batch" : processed == 0 ? "Preparing batch" : "Anonymizing"
    }
    var progressDetail: String {
        if cancelling { return "Waiting for the engine to stop or finish publication…" }
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
                Text(model.status).id(model.status).accessibilityIdentifier("batchStatus").textSelection(.enabled)
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
