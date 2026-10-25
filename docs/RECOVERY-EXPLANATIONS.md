# Recovery explanations and worker-to-model integration

## Scope — 24 October 2026

Source increment after Preview 20/build 24, now delivered as Preview 21/build 25. The existing public views, recovery controls, macOS 13/arm64 target, engine metadata policy and default-off sidecar policy are unchanged. No automatic batch deletion or resume is added.

## Recovery explanations

The existing recovery area now separates confirmed filesystem identity from unconfirmed completion and the next inspection step:

- Matching output: the folder matches the recorded staging identity. This does not establish that completion was acknowledged or that the batch/report is ready to share; review the output/report before retrying and avoid duplicate batches.
- Matching staging: the staging folder matches the operation record. The notice names the intended output separately and directs inspection of both locations without claiming completed publication.
- Unavailable parent: the output parent cannot be identified as a regular folder. Reconnect or locate it before inspecting the output and retrying.
- Existing unconfirmed output: an item exists at the intended output, but matching identity cannot be confirmed. Its existence is not accepted completion, and the notice does not authorize deleting it.
- Missing/unmatched folders: the parent is identified as a folder, but staging/output cannot be matched. This does not establish read access or prove that no output was published elsewhere.
- Unreadable record: the notice identifies the record by filename, claims neither staging ownership nor publication outcome, and retains uncertainty.

Combined notices preserve each operation's explanation and location in the existing scrollable area. Identity continuity is not content inspection, cryptographic integrity, an output audit, or a new confidentiality-policy claim.

## Headless worker-to-model coverage

`BatchModel.launch` exposes internal worker and journal-directory injection with production defaults unchanged. The new CLI harness invokes that actual launch path, including begin-run state, private journal arguments, `EngineRunner` subprocess/pipe delivery, main-actor event reduction and `finishRun`. It uses isolated preferences and temporary local paths, controlled shell workers, and no NSApplication or native app executable.

Eight new cases cover:

1. Valid completion at EOF with successful exit creates the completion summary.
2. Completion followed by nonzero exit does not create accepted completion.
3. Malformed output after completion retains publication uncertainty and the inspection location.
4. Abrupt exit does not claim no publication or restore readiness.
5. Explicit clean-cancellation acknowledgement produces the clean-cancellation state.
6. Late cancellation followed by completion and successful exit retains the published result.
7. Failed cleanup survives cancellation, identifies this operation's staging path, and vetoes a pending quit.
8. A safe structured error survives process failure.

These cases establish synthetic worker-to-model behavior. They do not rerun or establish real Python engine processing, actual filesystem publication, journal acknowledgement, live GUI/timer behavior, layout or responsiveness. Existing engine/model/journal receipts retain their scope.

## Focused evidence

Seven new explanation cases and eight new worker-to-model cases passed as composite evidence. Six worker cases passed initially; two cancellation cases initially failed because Swift consumed shell-quote escapes in the synthetic signal handlers, corrupting their JSON output. Failed-only diagnostic runs identified that fixture boundary; JSON is now supplied as a separate argument to a quoted printf handler. Only those two failed cases were rerun after the fixture fix. No product cancellation reducer change was needed.

Read-only review corrected two overstatements in fallback text: parent metadata does not prove content access, and unavailable identity does not prove mismatch. Only the two affected explanation cases were rerun after that wording change. Passing unchanged cases, lifecycle/worker process suites, engine policy/self-audit, sidecar/r2, runtime, dependencies, icon, publication-tooling and Preview 20 distribution receipts were reused.

The real optimized native target compiled with warnings as errors using Swift 6.4.2, Xcode 27.2 (27B48), SDK 27.2, Swift language mode 6, arm64/macOS 13. It was not launched. Detailed logs, diagnostic evidence and verification records are retained outside the repository.

No GUI use, native app launch, installation, signing, notarization, push or release occurred for this source increment. Preview 21/build 25 is the public download. Live recovery/sidecar interaction, scheduling, responsiveness and layout acceptance remain pending.

## Authorized distribution

The unified public app is delivered as **Preview 21/build 25**, using `scripts/publication.py`. Packaged engine/release source is `54972ffb0bd4aa38d4a703fdc8ef72876bb11c32`; accepted native executable source is `1c198174ac0927337e7a1d40d59a0fb229e6eb09`. Apple notarization `6d5b7b80-2587-4948-8c58-6361a8f0633f` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,057,708 bytes.

Accepted verification was reused: seven recovery-explanation cases, eight headless worker-to-model cases and existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency, icon and publication-tooling evidence. No functional test or native build was repeated for delivery. Public UI structure and engine policy are unchanged. No GUI use, native app launch or installation occurred. Synthetic subprocess cases do not establish real Python processing, filesystem publication, journal acknowledgement or live UI behavior. Live scheduling, recovery/sidecar interaction, responsiveness and layout acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.21). Earlier records retain their historical scope.
