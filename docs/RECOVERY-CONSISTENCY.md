# Acknowledgement warning persistence and recovery snapshot generations

## Scope — 24 October 2026

Local source increment after delivered Preview 24/build 28. Public view structure, controls, engine metadata policy, default-off sidecar policy, bundled runtime and arm64/macOS 13 target are unchanged. No automatic retry, resume or batch-data deletion is added.

## Independent warning and report state

The completed operation's outstanding acknowledgement warning is stored separately from the currently presented report problem. The native report-opening path and headless checks share pure success/failure reducers.

- A report error temporarily occupies the existing recovery area without clearing the pending acknowledgement state.
- Opening the report successfully or dismissing its error restores the acknowledgement warning when it remains outstanding for that completed output.
- Explicitly dismissing the acknowledgement warning hides it for the session. Later report actions do not resurrect that explicitly dismissed warning; the unresolved on-disk record is unaffected.
- Starting a new operation resets the previous operation's pending warning so it cannot attach to a later result.
- Completion summaries, output inspection and existing reveal/dismiss controls remain available and nonblocking.

No report opener, file viewer or clipboard was invoked in the headless checks. On-disk record retention remains covered by accepted prior receipts; the new report-action fixtures intentionally omit their selected record to exercise warning persistence.

## Single-use snapshot generations

Each production background recovery inspection captures a UUID generation before filesystem work begins. Beginning another inspection supersedes the previous generation. Applying a current snapshot consumes its token; duplicate or older results are rejected before modifying presentation or inspection history.

Ordinary problem presentation/clearing, new operations and successful output choices invalidate pending generations. Applying an owned recovery result uses internal non-invalidating presentation helpers, so its own valid refresh chain can continue. The scheduled 30-second callback also checks its captured post-application generation before beginning another inspection; an obsolete callback cannot restart a superseded chain.

This handles intervening actions even when visible state later returns to an idle shape. Existing guards for active work, selected source, completion, newer errors and explicit output choices remain in force. Synchronous untagged snapshot injection remains available for existing model fixtures; production background delivery always supplies the captured token.

## Focused evidence

Fourteen new cases passed once: eight report/warning transitions and six generation/order cases. Coverage includes report failure/dismissal, report success/recovery, explicit warning dismissal, operation reset, nonblocking completion controls, repeated report cycles, ordinary report recovery, out-of-order/duplicate snapshots, an intervening run returning to idle, delayed failures after a newer empty scan, and the current refresh token chain.

Read-only source review found no blockers. The actual optimized native target compiled with warnings as errors using Swift 6.4.2, Xcode 27.2 (27B48), SDK 27.2, Swift language mode 6, arm64/macOS 13. The executable was not launched.

## Limits and delivery

Synthetic workers and pure report-result reducers do not establish actual report opening, real engine processing/audit/publication, GUI interaction, timer scheduling, layout or responsiveness. The tests establish token acceptance/rejection and presentation transitions; they do not wait for live timers or inspect native windows.

No GUI use, native app launch, installation, signing, notarization, push or publication occurred for this increment. Preview 24/build 28 remains the public download until separately authorized delivery.
