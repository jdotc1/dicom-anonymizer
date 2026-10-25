
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
