
## 2026-10-23 — input-stability recovery (local source)

See `INPUT-STABILITY.md`: nine new synthetic test methods per variant, accepted unchanged evidence reused, no GUI or app launches. Release acceptance remains pending for this source.

Distribution completed: public build 19; Apple Accepted `b0807bd6-bd00-4f1f-b479-d9a89b363e30`, new root signature/stapled ticket/Gatekeeper passed once. Accepted unchanged evidence reused. No GUI use, app launch or installation.

## 2026-10-24 — unified Preview 16/build 20

New assembly source/resource checks, root signature, notarization `c3393d48-bcda-4dcc-9381-e2b0425a6c2d` (Accepted), stapled ticket, Gatekeeper and uploaded archive metadata passed once. Accepted sidecar/consolidation/native/runtime evidence reused. No GUI use, native app launch or installation. Live GUI acceptance remains pending. See `PUBLIC-CONSOLIDATION.md`.

## 2026-10-24 — r2 Preview 17/build 21

Accepted r2 delta, native and unchanged runtime/policy evidence reused. New package source/resource checks, root signature, notarization `3a5308be-cff7-4316-a945-64beebfda20a` (Accepted), stapled ticket and Gatekeeper passed once. No functional test/native build reruns, GUI use, native app launch or installation. Live GUI acceptance remains pending. See `SIDECAR-R2-RECONCILIATION.md`.

## 2026-10-24 — worker/feedback Preview 18/build 22

Accepted 15 native +8 engine +2 affected checks and optimized product reused. New package source/resources, root signature, Apple Accepted notarization `d1641659-914f-4b24-a8e4-44c32d159eef`, stapled ticket/Gatekeeper passed once. No functional test/native build repeated, GUI use, native app launch or installation. See `WORKER-SIDECAR-FEEDBACK.md`; live GUI acceptance pending.

## 2026-10-24 — resilience Preview 19/build 23

The unified public app is delivered as **Preview 19/build 23**, using the new resumable publication tooling. Packaged engine/release source is `a4fb9336cf821889dfdc7b7eb2259eacee2398c6`; accepted native executable source is `b0feaaba596360e39e183a344cc7ded69e3e0cf4`. Apple notarization `d8530154-3c29-406a-bfce-51d5c6c86844` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. The archive is 29,048,047 bytes.

Accepted evidence was reused: 11 engine journal cases, 12 native recovery/model/filesystem cases, 12 mocked publication methods and the existing policy, self-audit, sidecar/r2, worker-feedback, runtime, icon and dependency receipts. No functional test or native build was repeated for delivery. No GUI use, native app launch or installation occurred. Live startup/recovery, sidecar interaction, responsiveness and compact-window acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.19). Earlier entries retain their historical scope.

## 2026-10-24 — local recovery lifecycle and worker process increment

See `RECOVERY-LIFECYCLE.md`. Twenty new headless cases passed as composite evidence, plus four affected existing interruption cases; only changed-boundary cases were repeated after follow-up fixes. Actual optimized native target compiled with warnings as errors. Engine/policy, unchanged native/model/runtime and Preview 19 distribution receipts reused. No GUI use, native app launch, installation, signing, notarization or publication. Live interaction/scheduling acceptance pending.

## 2026-10-24 — recovery lifecycle Preview 20/build 24

The unified public app is delivered as **Preview 20/build 24**, using `scripts/publication.py`. Packaged engine/release source is `0e1868263a1b461e4530708d19a26176e06b1193`; accepted native executable source is `923828ab436daf06205857626e401503a29e0375`. Apple notarization `e24b8bff-915d-41be-8d8a-021c4de071eb` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,055,052 bytes.

Accepted verification was reused: 10 recovery-lifecycle cases, 10 headless worker process cases, four affected interruption cases and existing engine/policy/self-audit, sidecar/r2, worker/model, runtime, dependency and icon receipts. No functional test or native build was repeated for delivery. The public UI structure and engine policy are unchanged. No GUI use, native app launch or installation occurred. Live timer scheduling, recovery/sidecar interaction, responsiveness and layout acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.20). Prior receipts retain their historical scope.

## 2026-10-24 — local recovery explanations and worker-to-model increment

Seven new explanation cases and eight new worker-to-model integration cases passed as composite evidence. Failed synthetic cancellation fixtures were diagnosed and corrected; only failed/changed cases were repeated. Read-only review corrected fallback wording that overstated metadata/identity evidence. Actual optimized native target compiled with warnings as errors. Accepted engine, lifecycle, worker/model, sidecar, runtime and Preview 20 distribution receipts reused. No GUI use, native app launch, installation or publication. See `RECOVERY-EXPLANATIONS.md` for scope and limits.

## 2026-10-24 — recovery explanations Preview 21/build 25

The unified public app is delivered as **Preview 21/build 25**, using `scripts/publication.py`. Packaged engine/release source is `54972ffb0bd4aa38d4a703fdc8ef72876bb11c32`; accepted native executable source is `1c198174ac0927337e7a1d40d59a0fb229e6eb09`. Apple notarization `6d5b7b80-2587-4948-8c58-6361a8f0633f` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,057,708 bytes.

Accepted verification was reused: seven recovery-explanation cases, eight headless worker-to-model cases and existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency, icon and publication-tooling evidence. No functional test or native build was repeated for delivery. Public UI structure and engine policy are unchanged. No GUI use, native app launch or installation occurred. Synthetic subprocess cases do not establish real Python processing, filesystem publication, journal acknowledgement or live UI behavior. Live scheduling, recovery/sidecar interaction, responsiveness and layout acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.21). Earlier records retain their historical scope.

## 2026-10-24 — local output-location rechecks and acknowledgement

Nine new location/model cases and eight new synthetic subprocess/model/record-acknowledgement cases passed as composite evidence. Source review found and resolved successful output selection retaining old refresh ownership; two new regression cases cover that change. Passing unchanged checks and accepted engine/policy, sidecar, lifecycle, worker/model/journal, runtime and Preview 21 distribution evidence reused. Optimized native target compiled with warnings as errors; no GUI use, native app launch, installation or publication. See `OUTPUT-LOCATION-RECHECKS.md` for limits.

## 2026-10-24 — output-location rechecks Preview 22/build 26

The unified public app is delivered as **Preview 22/build 26**, using `scripts/publication.py`. Packaged engine/release source is `34e8dec7c8ebb1caf69b1f75cb1844fa56587410`; accepted native executable source is `71d934e607437779f65c9fb56f4f66a7836d9cc0`. Apple notarization `804435d2-ae0e-4a09-9a54-faef4d35d743` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,058,325 bytes.

Accepted verification was reused: nine output-location/model cases, eight synthetic subprocess/model/record acknowledgement cases and existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency, icon and publication-tooling receipts. No functional test or native build was repeated for delivery. Public UI structure and engine policy are unchanged. No GUI use, native app launch or installation occurred.

Temporary directory moves and synthetic records establish scoped recheck/acknowledgement behavior, not real volume mounting or engine processing/audit/publication/durability. Record-retention cases do not establish rejection of a completion summary. Live scheduling, volume behavior, recovery/sidecar interaction, responsiveness and layout remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.22). Earlier records retain their historical scope.

## 2026-10-24 — local publication visibility reconciliation

Seventeen new mocked methods passed as composite evidence. Only the affected publication-timeout resume case was repeated after adding stale-draft resume reconciliation. New cases cover delayed create/upload/publish/tag visibility, timeouts/resume, lost publish response with stale draft, conflicts, archive change and read errors. Existing publication/packaging/app receipts reused. No live GitHub call, native build, GUI use, app launch, installation or publication. See `RESUMABLE-PUBLICATION.md` for bounds and limits.

## 2026-10-24 — publication visibility Preview 23/build 27

The unified public app is delivered as **Preview 23/build 27**, using the bounded read-only visibility reconciliation in `scripts/publication.py`. Packaged engine/release source is `83a1b08533c60b6beb4132f6f389d67d68ca869b`; accepted native executable source is `71d934e607437779f65c9fb56f4f66a7836d9cc0`. Apple notarization `fe79275a-8326-47e4-8fb9-944e68a672f4` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,058,329 bytes.

This is a tooling/distribution update; native and engine behavior are unchanged from Preview 22. Accepted verification reused: 17 publication-visibility mocked methods, nine location/model and eight record-acknowledgement cases, plus existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency and icon receipts. No functional tests, native builds, unchanged source hashes or dependency-signature checks were repeated for delivery.

No GUI use, native app launch or installation occurred. Public UI structure and engine policy are unchanged. Live scheduling, volume behavior, recovery/sidecar interaction, responsiveness and layout remain pending. Prior synthetic evidence retains its original limits.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.23). Earlier records retain their historical scope.
