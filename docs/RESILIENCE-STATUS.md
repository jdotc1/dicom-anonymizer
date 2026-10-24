# Resilience implementation and delivery — 2026-10-24

Preview 19/build 23 is delivered. This increment combines interruption recovery, resumable publication and consolidation housekeeping. Public UI structure, macOS 13 deployment target and engine metadata policy are unchanged.

## Interruption recovery

See `INTERRUPTION-RECOVERY.md`. Eleven new engine journal cases and twelve new native model/filesystem cases passed as composite evidence. The real optimized native target compiled with warnings as errors. Only failed URL-fixture cases and newly added semantic-record/action guards were run after the initial native pass. No passing unchanged case was repeated. Independent source-only review found and resolved invalid-record handling; final delta review found no blockers.

## Resumable publication

See `RESUMABLE-PUBLICATION.md`. Twelve new mocked methods passed as composite evidence, including lost create/upload/publish responses, ownership conflicts, changed tags and paginated upload confirmation. The native app was not involved. Parent review identified an upload URL construction risk; official CLI source was consulted, and the absolute upload URL with canonical authentication host was corrected before any real use. A new upload-boundary fixture passed once. No live GitHub mutation or accepted package verification occurred during that source-only increment.

## Cleanup completed

## Evidence and authority

## Authorized delivery

The unified public app is delivered as **Preview 19/build 23**, using the new resumable publication tooling. Packaged engine/release source is `a4fb9336cf821889dfdc7b7eb2259eacee2398c6`; accepted native executable source is `b0feaaba596360e39e183a344cc7ded69e3e0cf4`. Apple notarization `d8530154-3c29-406a-bfce-51d5c6c86844` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. The archive is 29,048,047 bytes.

Accepted evidence was reused: 11 engine journal cases, 12 native recovery/model/filesystem cases, 12 mocked publication methods and the existing policy, self-audit, sidecar/r2, worker-feedback, runtime, icon and dependency receipts. No functional test or native build was repeated for delivery. No GUI use, native app launch or installation occurred. Live startup/recovery, sidecar interaction, responsiveness and compact-window acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.19). Earlier entries retain their historical scope.
