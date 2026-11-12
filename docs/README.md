# Documentation index

The project is in maintenance mode; see [ROADMAP.md](ROADMAP.md). Start with
[MAINTENANCE.md](MAINTENANCE.md) for tests, lint, CI and release pointers. Most
files below are dated delivery records; they keep the scope and evidence limits of
the release they describe.

## Roadmap and maintenance

- [ROADMAP.md](ROADMAP.md): delivered work, deferred work and decisions awaiting the maintainer.
- [ROADMAP-VISUAL.md](ROADMAP-VISUAL.md): milestone view with a retained historical graphic (`roadmap/`).
- [MAINTENANCE.md](MAINTENANCE.md): running tests and lint, manual CI, release pointers, policy-change rule.

## Data handling and policy

- [DATA-HANDLING.md](DATA-HANDLING.md): the data-handling contract: what changes, what remains.
- [RTSTRUCT-POLICY-COMPARISON.md](RTSTRUCT-POLICY-COMPARISON.md): RTSTRUCT handling, retained labels, reference limits.
- [MRI-JSON-SIDECARS.md](MRI-JSON-SIDECARS.md): optional, default-off MRI JSON sidecar cleaning.
- [FILE-HEADER-AUDIT.md](FILE-HEADER-AUDIT.md): independent audit of staged file headers.
- [AUDIT-COVERAGE.md](AUDIT-COVERAGE.md): structured audit coverage in batch reports.
- [AUDIT-PROGRESS.md](AUDIT-PROGRESS.md): self-audit progress and checked-file counts.
- [CANARY-SURVEY.md](CANARY-SURVEY.md): synthetic canary retention survey and policy-table lint.
- [INPUT-STABILITY.md](INPUT-STABILITY.md): detecting inputs that change during a run.
- [DESCRIPTOR-READS.md](DESCRIPTOR-READS.md): descriptor-pinned input reads.

## Engine interface and tools

- [ENGINE-INTERFACE.md](ENGINE-INTERFACE.md): command-line flags, JSON-line events, report keys.
- [../engine/README.md](../engine/README.md): engine guide, including `--explain` and `--verify-output`.
- [PERFORMANCE.md](PERFORMANCE.md): synthetic benchmark notes (not a gate).
- [SCAN-PROGRESS.md](SCAN-PROGRESS.md): scan progress feedback.
- [SPACE-ESTIMATE.md](SPACE-ESTIMATE.md): allocation-aware disk-space estimate.
- [WORKER-SIDECAR-FEEDBACK.md](WORKER-SIDECAR-FEEDBACK.md): worker-event framing and sidecar counts.
- [BOUNDED-WORKER-STORAGE.md](BOUNDED-WORKER-STORAGE.md): bounded worker-event buffering and release-storage admission.
- [TERMINAL-DIAGNOSTICS.md](TERMINAL-DIAGNOSTICS.md): terminal-event consistency and Copy Details.
- [SIDECAR-R2-RECONCILIATION.md](SIDECAR-R2-RECONCILIATION.md): sidecar reconciliation delta.
- [WORKFLOW-POLISH.md](WORKFLOW-POLISH.md): earlier interface polish.

## Recovery and publication of output

- [ERROR-RECOVERY.md](ERROR-RECOVERY.md): problem types and recovery behavior in the app.
- [RECOVERY-PRESENTATION-PARITY.md](RECOVERY-PRESENTATION-PARITY.md): compact recovery presentation.
- [BOUNDED-RECOVERY-MESSAGES.md](BOUNDED-RECOVERY-MESSAGES.md): bounded recovery notice text.
- [RECOVERY-RECORD-READS.md](RECOVERY-RECORD-READS.md): bounded recovery-record reads.
- [INTERRUPTION-RECOVERY.md](INTERRUPTION-RECOVERY.md): interruption recovery records.
- [RECOVERY-LIFECYCLE.md](RECOVERY-LIFECYCLE.md): combined notices, record retirement, live-owner reinspection.
- [RECOVERY-EXPLANATIONS.md](RECOVERY-EXPLANATIONS.md): confirmed versus uncertain recovery guidance.
- [RECOVERY-STATE-FEEDBACK.md](RECOVERY-STATE-FEEDBACK.md): recovery inspection failures and acknowledgement warnings.
- [RECOVERY-CONSISTENCY.md](RECOVERY-CONSISTENCY.md): generation tokens and preserved warnings.
- [OUTPUT-LOCATION-RECHECKS.md](OUTPUT-LOCATION-RECHECKS.md): guarded output-location rechecks.
- [PUBLICATION-RECOVERY.md](PUBLICATION-RECOVERY.md): unconfirmed publication and Quit handling.
- [STORAGE-RECOVERY.md](STORAGE-RECOVERY.md): storage-failure recovery.
- [STAGING-JOURNAL-PROTECTION.md](STAGING-JOURNAL-PROTECTION.md): staging inventories and recovery-record write protection.
- [LOCAL-STORAGE.md](LOCAL-STORAGE.md): local artifact retention.

## Release and publication process

- [RELEASE-AUTOMATION.md](RELEASE-AUTOMATION.md): receipt-driven packaging and resumable steps.
- [RELEASE-AUTOMATION-DELIVERY.md](RELEASE-AUTOMATION-DELIVERY.md): delivery record for the automation.
- [RELEASE-AUTOMATION-EVIDENCE.md](RELEASE-AUTOMATION-EVIDENCE.md): fixture and source-review coverage of the tooling.
- [RELEASE-PREFLIGHT.md](RELEASE-PREFLIGHT.md): release preflight checks.
- [RELEASE-REVIEW.md](RELEASE-REVIEW.md): macOS preview release review.
- [RESUMABLE-PUBLICATION.md](RESUMABLE-PUBLICATION.md): resumable publication and delayed-visibility reconciliation.
- [PUBLICATION-SAFETY.md](PUBLICATION-SAFETY.md): sanitation gates for source history, release text and artifacts.
- [ARTIFACT-RETIREMENT.md](ARTIFACT-RETIREMENT.md): plan-first retirement of local release artifacts.
- [PUBLIC-CONSOLIDATION.md](PUBLIC-CONSOLIDATION.md): consolidation into the public app.

## Evidence and acceptance records

- [RUNTIME-ACCEPTANCE.md](RUNTIME-ACCEPTANCE.md): per-release runtime acceptance, including the Preview 36 live GUI pass.
- [EVIDENCE.md](EVIDENCE.md): dated log of verification evidence and reuse.
- [PUBLICATION-CHECKLIST.md](PUBLICATION-CHECKLIST.md): per-release publication records; Preview 37 section in preparation.
- [RESILIENCE-STATUS.md](RESILIENCE-STATUS.md): resilience implementation and delivery status.
