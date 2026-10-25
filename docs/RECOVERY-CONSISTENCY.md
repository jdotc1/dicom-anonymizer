# Acknowledgement warning persistence and recovery snapshot generations

## Scope — 24 October 2026

Source increment after Preview 24/build 28, now delivered as Preview 25/build 29. Public view structure, controls, engine metadata policy, default-off sidecar policy, bundled runtime and arm64/macOS 13 target are unchanged. No automatic retry, resume or batch-data deletion is added.

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

Accepted engine/policy/self-audit, sidecar/r2, prior lifecycle/worker/model/journal/acknowledgement, runtime, dependency, icon, publication-tooling and Preview 24 distribution receipts were reused. No passing unchanged suites, engine checks, source hashes or dependency signatures were repeated. Detailed logs, harnesses and verification records are retained outside the repository.

## Limits and delivery

Synthetic workers and pure report-result reducers do not establish actual report opening, real engine processing/audit/publication, GUI interaction, timer scheduling, layout or responsiveness. The tests establish token acceptance/rejection and presentation transitions; they do not wait for live timers or inspect native windows.

No GUI use, native app launch, installation, signing, notarization, push or publication occurred for this increment. Preview 25/build 29 is the public download.

## Authorized distribution

The unified public app is delivered as **Preview 25/build 29**, using bounded read-only visibility reconciliation in `scripts/publication.py`. Packaged engine/release source is `58bf002ad7f6a3f9ee5523fa831a346533d81414`; accepted native executable source is `b64ce1b2bb999c217c6c4fa9638dc872b67ad37b`. Apple notarization `058b706f-133d-4a76-9588-e2ed1bbbfa3a` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,070,680 bytes.

Accepted verification reused: eight report/warning transition cases, six snapshot-generation cases and existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal/acknowledgement, runtime, dependency, icon and publication-tooling receipts. No functional tests, native builds, unchanged source hashes or dependency-signature checks were repeated for delivery. Public UI structure and engine policy are unchanged.

No GUI use, native app launch or installation occurred. Pure report-result reducers and synthetic workers do not establish actual report opening or real engine audit/publication; prior on-disk record-retention evidence retains its scope. Live scheduling, recovery/report/sidecar interaction, volume behavior, responsiveness and layout remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.25). Earlier records retain their historical scope.
