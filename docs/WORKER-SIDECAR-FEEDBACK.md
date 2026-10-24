# Worker events and sidecar feedback — 2026-10-24

Status: local source increment; not yet released. Public UI structure, macOS 13 target, engine retention policy and sidecar allowlist remain unchanged.

## Worker delivery

`EngineEventStream` retains partial bytes across reads, splits complete newline-delimited frames, and drains a valid unterminated final frame at EOF. UTF-8 is decoded only after a complete frame is available. Blank/whitespace-only lines are ignored.

`EngineEventDelivery` runs on the main actor. It coalesces only adjacent monotonic progress events of the same type with compatible totals. Scan, phase, error, completion and unknown named events remain ordered barriers. Regressing/malformed count payloads are left for the existing model guards rather than replacing accepted progress. Only immutable Data crosses the worker/actor boundary.

The process I/O worker synchronously delivers each available frame batch before reading the next batch. This bounds outstanding main-queue delivery work without moving blocking pipe reads or process exit waits onto the main actor. EOF frames are delivered before the process-exit callback.

Malformed JSON or envelopes mark a protocol failure, without exposing raw stdout. A nominal zero exit becomes failure. A safe engine error retains its specific recovery information; otherwise the generic error tells the user to inspect the batch/output location and treats publication as uncertain. A valid completion event is never silently discarded after malformed data. This does not claim atomic filesystem protection or add new input-policy limits.

## Sidecar feedback

Optional discovery emits `sidecar_scan_progress` with only `files_examined` and `folders_examined`. Files count encountered `.json` candidates, including candidates later excluded as Part 10/AppleDouble; folders count entered numeric-patient directories and descendants. No total or fraction is invented. An initial and final snapshot are forced; intermediate events are throttled to 0.1 seconds. Error/cancellation does not emit a misleading final successful snapshot.

The existing progress area shows “Checking JSON sidecars” and examined counts. Guards reject malformed/regressing pairs, cancellation/error/late events, and DICOM scan events after sidecar checking starts. The completed scan returns the accepted sidecar count as before.

The existing completion panel and status show actual JSON files cleaned and checked when valid complete-event counts agree with the selected sidecar count. Enabled zero is distinct from disabled mode; missing/malformed counts do not invent totals. Completion summaries capture terminal counts rather than reading later mutable option state. No paths, values or source names are added to telemetry.

## Focused evidence

- 15 new native CLI checks passed once: fragmented UTF-8 at every split, EOF/whitespace, coalescing/barriers, regressing progress, malformed tail, protocol error plus completion, preserved safe engine error, unknown events, sidecar preflight/guards, actual completion counts, zero/disabled behavior, invalid counts, reset and exit ordering.
- Eight new engine telemetry checks passed once: initial/final counts, throttling/monotonicity, silent legacy helper, host forwarding, zero candidates, cancellation, CLI event ordering and count-only privacy.
- Two affected existing fixtures were updated and checked once: enabled-sidecar event ordering now selects the completed scan rather than assuming it is the first event; the r2 aggregate-budget mock accepts/forwards the new optional progress callback.
- Actual optimized public native target and the new CLI model/stream harness compiled with warnings as errors, Apple Swift 6.4.2, Swift language mode 6, Xcode 27.2 build 27B48, SDK 27.2, arm64/macOS 13.
- Independent source-only delta review found no blockers.

Accepted policy/self-audit, sidecar parser/catalog/resource gates, previous recovery/consolidation/r2 and bundled runtime/icon/dependency evidence were reused. No passing unchanged suite, dependency/provenance hash or signature check was rerun. No merge, push, signing, notarization, release or installation occurred.
