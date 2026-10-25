# Recovery explanations and worker-to-model integration

## Scope — 24 October 2026

Local source increment after delivered Preview 20/build 24. The existing public views, recovery controls, macOS 13/arm64 target, engine metadata policy and default-off sidecar policy are unchanged. No automatic batch deletion or resume is added.

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

No GUI use, native app launch, installation, signing, notarization, push or release occurred for this source increment. Preview 20/build 24 remains the public download. Live recovery/sidecar interaction, scheduling, responsiveness and layout acceptance remain pending.
