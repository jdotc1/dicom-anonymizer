# Terminal-event consistency and Copy Details

Local implementation; not released. The current download remains Preview 28 /
build 32. Public view structure, controls, engine metadata policy and sidecar
defaults are unchanged.

## Terminal evidence

Worker delivery tracks completion and error events across pipe reads. A completion
combined with an error, conflicting valid counts in repeated completion events,
or a completion followed by a nonzero exit prevents a clean-success claim.
The worker's exit status remains nonzero; a contradictory nominal zero is reduced
to failure. An error alone also cannot become success solely because exit was zero.

Conflict recovery preserves completion as evidence that output may exist. It
retains a specific engine message and cleanup ownership fields while adding
uncertain-output guidance. A cleanup-bearing error survives a later generic error.
Cancellation cannot claim that no completed batch exists when completion evidence
is present; the existing quit guard retains uncertainty and incomplete cleanup.

Compatible duplicate completion events remain accepted. Absent or malformed
optional fields retain their existing compatibility behavior. Later omission
does not erase counts already provided by an earlier completion. Unknown fields
do not create contradictions. No image, patient, metadata or sidecar policy is
re-evaluated by this transport-state change.

## Existing Copy Details action

The same button now uses a pure formatter containing app version/build, operation
phase, failure category, output certainty and the displayed recovery message.
Missing version/build values are explicitly unknown. Specific recovery details,
including multiline text and local paths already present in the message, are
preserved. No source/output paths are newly appended by the formatter, and no
clipboard automation is used for verification.

The phase is captured before worker state is reset at exit. A new local selection
error or new run takes ownership of diagnostic context, so an earlier cancellation
or protocol failure does not describe the new problem. A report warning after
confirmed completion continues to describe the completed output as confirmed.

## Evidence and scope

Focused headless cases exercise event delivery, actual synthetic shell workers
through the batch model, cancellation/quit behavior, optional-field compatibility,
formatting and stale-context reset. This is synthetic process/model coverage;
it does not establish live UI, clipboard, real imaging or report-opening behavior.
Existing engine, self-audit, runtime, dependency, icon and unaffected worker/recovery
verification is reused. Native compilation uses the existing macOS 13 arm64 target
and warning policy. Only newly added or affected cases run after a source change.

Twenty-six new cases passed as composite evidence: twenty-one initial cases,
two added compatibility/context cases and three added terminal-exit cases.
The affected cancellation-conflict case was repeated after its exit reduction
changed. The existing process fixture for completion followed by exit 7 now
expects the uncertainty error as well as the completion event; only that affected
older case was run. Accepted unchanged suites were not repeated.

No GUI use, application launch, installation, signing, notarization or publication
is part of this local increment. Build products and logs are retained locally;
the task's compiler cache is disposable after compilation completes.
