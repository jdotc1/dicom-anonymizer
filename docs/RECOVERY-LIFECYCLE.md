# Recovery-record lifecycle and headless worker integration

## Scope — 24 October 2026

Local source increment after delivered Preview 19/build 23. Public view structure, macOS 13/arm64 target, bundled runtime and engine/sidecar policies are unchanged. No GUI use, native app launch or installation is part of this increment.

## Recovery lifecycle

- Inspect all JSON recovery records in deterministic filename order. Combine unresolved notices and their locations in the existing scrollable recovery area; an unreadable record cannot hide other interrupted operations.
- Leave unresolved, malformed, symlinked and live-owner records alone. Nothing resumes automatically and no batch staging/output is deleted.
- Retire a `cleaned` local record only after its owner is no longer running and the captured regular-file identity still matches. Successful publication acknowledgement uses the same identity-checked local-record removal. Identity includes device, inode, size and modification time; this is ordinary replacement detection, not a privileged-attacker or atomic-filesystem guarantee.
- While any recorded owner remains live, schedule one background inspection after 30 seconds. Stop scheduling when no live owner remains or a selected source, active run, completion or newer problem owns the area. Refreshes may update or clear only their own recovery presentation.
- Preserve the recovery explanation separately from ordinary output-error instructions so an aggregate notice never suggests deleting the shared Operations directory.

The model's refresh ownership marker is cleared by every ordinary problem presentation and set only after an interruption presentation. This prevents an older recovery snapshot from replacing a newer output-validation error.

## Worker integration

`EngineRunner` accepts an internal command resolver for headless checks. Production uses the default resolver and the same bundled isolated Python/bootstrap command. Both paths share process creation, null stdin/stderr, stdout framing, main-actor delivery, cancellation and termination handling.

`WorkerProcessIntegrationTests.swift` runs only controlled command-line subprocesses, never the app executable or NSApplication. Ten new cases cover fragmented pipe output plus final EOF frame, abrupt exit, active cancellation, pre-start cancellation, malformed tail, completion followed by nonzero exit, launch failure, stderr isolation, argument forwarding, and 2,000 events under pipe pressure. The assertions cover runner events/status callbacks; they do not establish the final live UI outcome or rerun accepted BatchModel completion suites.

## Focused evidence

Ten new lifecycle cases and ten new worker process cases passed as composite evidence. Four affected existing interruption cases were checked: acknowledgement, malformed record, invalid record fields and use of the existing recovery area. Only cases affected by subsequent scan/ownership changes were run again; passing unchanged worker and record-retirement cases were reused.

Source review identified two gaps and both were addressed: production reinspection of live owners, and a recovery marker surviving a newer output-validation error. The latter has its own new regression case. The real optimized native target compiles with warnings as errors, Swift 6.4.2, Xcode 27.2 (27B48), SDK 27.2, arm64/macOS 13. The executable was not launched.

## Remaining limits

Live app timer scheduling, recovery interaction, sidecar interaction, responsiveness and layout acceptance remain pending. A scan stopped by a new user workflow is not a continuous process monitor. PID reuse can conservatively defer recovery. Record removal remains a best-effort local-state operation; no automatic staging cleanup or resume is added. Preview 19 remains the public download until separately authorized delivery.
