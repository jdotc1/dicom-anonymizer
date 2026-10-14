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
                DispatchQueue.main.async { event(["event": "error", "message": "The app resources are missing. Rebuild the app."]); finished(1, false) }
                return
            }
            let candidates = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3"]
            var interpreter: String?
            for candidate in candidates where FileManager.default.isExecutableFile(atPath: candidate) {
                lock.lock(); let stop = cancelled; lock.unlock()
                if stop { DispatchQueue.main.async { finished(130, true) }; return }
                let probe = Process()
                probe.executableURL = URL(fileURLWithPath: candidate)
                probe.arguments = ["-I", "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"]
                probe.standardOutput = FileHandle.nullDevice
                probe.standardError = FileHandle.nullDevice
                do { try probe.run(); probe.waitUntilExit() } catch { continue }
                if probe.terminationStatus == 0 { interpreter = candidate; break }
            }
            guard let interpreter else {
                DispatchQueue.main.async { event(["event": "error", "message": "Python 3.10 or newer is required. Restore the local Python installation, then reopen the app."]); finished(1, false) }
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
                DispatchQueue.main.async { event(["event": "error", "message": "The anonymization engine could not start. Rebuild the app and retry."]); finished(1, false) }
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

@MainActor
final class BatchModel: ObservableObject {
    // ObservableObject retains the original app's macOS 13 deployment target.
    @Published var source: URL?
    @Published var outputParent: URL?
    @Published var patients: [PatientRow] = []
    @Published var total = 0
    @Published var processed = 0
    @Published var excluded = 0
    @Published var activePatient: String?
    @Published var busy = false
    @Published var scanning = false
    @Published var ready = false
    @Published var status = "Choose a batch folder to begin."
    @Published var errorMessage: String?
    @Published var completedOutput: URL?
    @Published var runStarted: Date?
    @Published var summary: CompletionSummary?
    private var runner: EngineRunner?
    static let outputDefaultsKey = "OutputParentPath"

    init() {
        // Restore the last chosen output location only when it is still an existing folder.
        if let path = UserDefaults.standard.string(forKey: Self.outputDefaultsKey) {
            var isDirectory: ObjCBool = false
            if FileManager.default.fileExists(atPath: path, isDirectory: &isDirectory), isDirectory.boolValue {
                outputParent = URL(fileURLWithPath: path, isDirectory: true)
            } else {
                UserDefaults.standard.removeObject(forKey: Self.outputDefaultsKey)
            }
        }
    }

    func setOutputParent(_ url: URL) {
        outputParent = url.standardizedFileURL
        UserDefaults.standard.set(url.standardizedFileURL.path, forKey: Self.outputDefaultsKey)
    }
    private var scanReceived = false
    private var completeReceived = false
    private var terminationReply: (() -> Void)?
    private var openPanel: NSOpenPanel?

    func selectSource(_ url: URL) {
        guard !busy else { return }
        var isDirectory: ObjCBool = false
        guard url.isFileURL, FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory), isDirectory.boolValue else {
            errorMessage = "Choose one folder containing numerical patient subfolders."; return
        }
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
        guard let source, !busy else { return }
        patients = []; total = 0; excluded = 0; processed = 0
        ready = false; completedOutput = nil; summary = nil
        launch(arguments: ["--source", source.path, "--scan"], isScan: true, output: nil)
    }

    func anonymize() {
        guard ready, !busy, let source, let outputParent else { return }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        let output = outputParent.appendingPathComponent("Anonymized_" + formatter.string(from: Date()) + "_" + UUID().uuidString.prefix(6))
        processed = 0; completedOutput = nil; summary = nil
        launch(arguments: ["--source", source.path, "--destination", output.path], isScan: false, output: output)
    }

    private func launch(arguments: [String], isScan: Bool, output: URL?) {
        busy = true; scanning = isScan; errorMessage = nil
        scanReceived = false; completeReceived = false
        runStarted = isScan ? nil : Date()
        status = isScan ? "Checking patient folders and DICOM metadata…" : "Checking the batch before processing…"
        let worker = EngineRunner(); runner = worker
        worker.start(arguments: arguments, event: { [weak self] event in
            self?.receive(event)
        }, finished: { [weak self] code, cancelled in
            guard let self else { return }
            let elapsed = self.runStarted.map { Date().timeIntervalSince($0) } ?? 0
            self.busy = false; self.scanning = false; self.runner = nil; self.activePatient = nil; self.runStarted = nil
            if code == 0 && !isScan && self.completeReceived, let output {
                self.completedOutput = output
                self.summary = CompletionSummary(patients: self.completedPatients ?? self.patients.count, files: self.processed,
                                                 excluded: self.excluded, output: output, elapsed: elapsed)
                self.status = "Complete · \(self.processed) DICOM files across \(self.completedPatients ?? self.patients.count) patients in \(elapsedText(elapsed))."
            } else if cancelled {
                self.status = "Cancelled. No completed batch was published."
                self.errorMessage = nil
                if isScan { self.ready = false }
            } else if code == 0 && isScan && self.scanReceived {
                self.ready = true
                self.status = "Ready · \(self.patients.count) patients and \(self.total) DICOM files."
            } else {
                self.ready = false
                self.status = "Batch needs attention."
                if self.errorMessage == nil { self.errorMessage = "The engine stopped before completing the batch. No completed batch was published." }
            }
            self.terminationReply?(); self.terminationReply = nil
        })
    }

    private var completedPatients: Int?

    // Unknown event names and unknown or malformed fields are ignored, so engine and
    // report additions from other lanes stay backward compatible with this UI.
    func receive(_ event: [String: Any]) {
        guard let name = event["event"] as? String else { return }
        switch name {
        case "scan":
            patients = (event["patients"] as? [Any] ?? []).compactMap { item in
                guard let row = item as? [String: Any], let id = row["id"] as? String, !id.isEmpty else { return nil }
                return PatientRow(id: id, files: eventCount(row["files"]) ?? 0, series: eventCount(row["series"]) ?? 0)
            }
            total = eventCount(event["total_files"]) ?? 0
            excluded = eventCount(event["excluded_files"]) ?? 0
            completedPatients = nil
            scanReceived = true
        case "progress":
            if let reported = eventCount(event["total_files"]), reported > 0 { total = reported }
            processed = min(eventCount(event["processed"]) ?? processed, max(total, processed))
            if let patient = event["patient_id"] as? String, !patient.isEmpty { activePatient = patient }
            status = "Anonymizing patient \(activePatient ?? "") · \(processed) of \(total) files"
        case "complete":
            processed = eventCount(event["processed"]) ?? total
            completedPatients = eventCount(event["patients"])
            if let value = eventCount(event["excluded_files"]) { excluded = value }
            completeReceived = true
        case "error":
            errorMessage = (event["message"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "The batch could not be processed."
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
        guard let output = completedOutput else { return }
        NSWorkspace.shared.activateFileViewerSelecting([output])
    }

    func openReport() {
        guard let output = completedOutput else { return }
        let report = output.appendingPathComponent("anonymization-report.json")
        if FileManager.default.fileExists(atPath: report.path) { NSWorkspace.shared.open(report) }
        else { errorMessage = "The anonymization report could not be found in the output folder." }
    }

    var canAnonymize: Bool { ready && !busy && outputParent != nil }

    func cancel() { status = "Cancelling and removing incomplete output…"; runner?.cancel() }

    func prepareToQuit(completion: @escaping () -> Void) {
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
                else { self?.errorMessage = "The dropped folder could not be read. Use Choose Folder." }
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
            Text("Each immediate patient folder must have a numerical name, such as 00001.")
                .foregroundStyle(.secondary)
            Button(source == nil ? "Choose Folder…" : "Change Folder…", action: choose).disabled(busy)
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
                            Text(patient.id).bold().frame(maxWidth: .infinity, alignment: .leading)
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
                    Text(parent?.path ?? "Choose an output location").id(parent).lineLimit(2).textSelection(.enabled).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Choose Location…", action: choose).disabled(disabled)
            }
            Text("A new Anonymized folder is created for each run. Source files stay intact.").foregroundStyle(.secondary)
        }
    }
}

struct BatchProgress: View {
    let processed: Int
    let total: Int
    let activePatient: String?
    let started: Date?
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            ProgressView(value: Double(min(processed, max(1, total))), total: Double(max(1, total)))
                .accessibilityLabel("Anonymization progress")
                .accessibilityValue("\(processed) of \(total) files")
            HStack {
                Text("\(processed) of \(total) files")
                if let activePatient { Text("· Patient \(activePatient)").foregroundStyle(.tint) }
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
        HStack(alignment: .center, spacing: 10) {
            Image(systemName: "checkmark.circle.fill").foregroundStyle(.green).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text("Batch complete · \(summary.output.lastPathComponent)").bold().textSelection(.enabled)
                Text("\(summary.patients) patients · \(summary.files) files · \(summary.excluded) excluded · \(elapsedText(summary.elapsed))")
                    .foregroundStyle(.secondary)
            }
            .accessibilityElement(children: .combine)
            Spacer()
            Button("Reveal in Finder", action: reveal)
            Button("Open Report", action: openReport)
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
            Text("Series descriptions and sequence names retained. Patient identifiers, dates and private tags anonymized.")
            Text("Pixel text is not redacted. Review images before sharing. MR, CT and RTSTRUCT supported.").foregroundStyle(.secondary)
        }
    }
}

struct BatchView: View {
    @ObservedObject var model: BatchModel
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            BatchHeader()
            FolderInput(source: model.source, busy: model.busy, choose: model.chooseSource, acceptDrop: model.acceptDrop)
            PatientPreview(patients: model.patients, activePatient: model.activePatient, total: model.total, excluded: model.excluded)
            OutputSection(parent: model.outputParent, disabled: model.busy, choose: model.chooseOutput)
            Divider()
            PolicySummary()
            if let error = model.errorMessage {
                HStack(alignment: .top) {
                    Label(error, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.red)
                        .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                    Spacer()
                    Button("Copy Details", action: model.copyErrorDetails)
                        .accessibilityHint("Copies the error message to the clipboard")
                }
                .accessibilityIdentifier("batchError")
            }
            VStack(alignment: .leading, spacing: 8) {
                if model.busy {
                    if model.scanning { ProgressView().controlSize(.small).accessibilityLabel("Checking batch") }
                    else { BatchProgress(processed: model.processed, total: model.total, activePatient: model.activePatient, started: model.runStarted) }
                }
                if let summary = model.summary, !model.busy {
                    CompletionView(summary: summary, reveal: model.revealOutput, openReport: model.openReport)
                }
                Text(model.status).id(model.status).accessibilityIdentifier("batchStatus").textSelection(.enabled)
            }
            HStack {
                if model.busy { Button("Cancel", action: model.cancel).keyboardShortcut(.cancelAction) }
                else { Button("Check Again", action: model.scan).disabled(model.source == nil) }
                Spacer()
                if let output = model.completedOutput {
                    Button("Open Output") { NSWorkspace.shared.open(output) }
                }
                Button("Anonymize Batch", action: model.anonymize)
                    .buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
                    .disabled(!model.canAnonymize)
                    .accessibilityIdentifier("anonymizeBatch")
                    .accessibilityHint("Anonymizes every patient folder. Shortcut: Command-Return.")
            }
        }
        .font(.custom("Arial", size: 10))
        .padding(22)
        .frame(minWidth: 700, idealWidth: 780, minHeight: 655, idealHeight: 720)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    weak var model: BatchModel?
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let model, model.busy else { return .terminateNow }
        model.prepareToQuit { sender.reply(toApplicationShouldTerminate: true) }
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
                Button("Anonymize Batch", action: model.anonymize)
                    .keyboardShortcut(.return, modifiers: .command).disabled(!model.canAnonymize)
            }
        }
    }
}
#endif
