# macOS release acceptance

## Current release — Preview 35, build 39

Preview 35/build 39 adds strict DICOM-only staging inventories and conservative
recovery-record write protection. Unexpected/missing inventory entries and
inspection failures prevent publication; ordinary record replacement during
preparation is detected without overwriting the foreign record. Before-publication
refusal remains distinct from uncertainty after completed output is published.
Public controls, metadata policy, report fields and sidecar default are unchanged.
See [Staging and journal protection](STAGING-JOURNAL-PROTECTION.md).

Release source is `6fedca8f15af84656dfc5aa6404676e2964c726e`; accepted engine
source is `4803c7b6b12845091ec5087e0618768d67acd047`; the reused native executable
was built at `5ebaa55481308ec33169e0420fe10a8c31d9f8e4`. Accepted evidence covers
10 inventory, 13 journal and 4 batch-integration methods. Unchanged policy,
sidecar, worker, native, runtime, dependency, icon and recovery receipts were
reused. No functional test or native build was repeated for delivery.

New assembly metadata, sanitation, root signature, stapled ticket and Gatekeeper
checks passed. Apple notarization `65ee9af6-a7d0-4ee2-ae8b-f32d31b40342` was
Accepted. The ZIP is 29,082,084 bytes. Journaled publication completed without
retrying a GitHub mutation; the download returned HTTP 200 to a HEAD request.
Existing GitHub releases/downloads remain preserved. No GUI use, app launch or
installation occurred. Live interaction acceptance remains pending; final
check-to-rename races remain outside these ordinary-mutation safeguards.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.35).

## Previous release — Preview 34, build 38

Preview 34/build 38 adds an additive audit-coverage section to completed batch
reports. DICOM and optional sidecar status/counts are separate, skipped checks
are explicit, and retained-content limitations are named. Existing report fields,
the public UI, cleaning policy, audit enforcement and sidecar default are retained.
See [Audit coverage](AUDIT-COVERAGE.md).

Release source is `2b2ab9003ed3ae0af5d04e78477793188b5d6658`; accepted engine source
is `56c488f8aedef11f71c4cde179f531089443ec64`; the reused native executable was
built at `5ebaa55481308ec33169e0420fe10a8c31d9f8e4`. Five new synthetic report
tests and unchanged engine/audit/sidecar/native/runtime/dependency/icon/recovery
evidence were reused. No functional test or native build was repeated for delivery.

New assembly metadata, sanitation, root signature, stapled ticket and Gatekeeper
checks passed. Apple notarization `5ed1f52d-2d8b-424e-a8db-ed6e90b8c964` was
Accepted. The ZIP is 29,080,672 bytes. Journaled publication completed without
retrying a GitHub mutation; the download returned HTTP 200 to a HEAD request.
Prior releases/downloads remain preserved. No GUI use, app launch or installation
occurred. Live interaction acceptance remains pending; report coverage does not
extend the underlying audit guarantees or establish irreversible anonymity.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.34).

## Previous release — Preview 33, build 37

Preview 33/build 37 limits accumulated recovery-message text to eight complete
details within a 16 KiB UTF-8 budget, while full inspection and all uncertainty
flags remain in use. Omitted counts and the record-directory location are shown;
unresolved records are preserved and existing cleaned-record retirement is
unchanged. See [Bounded recovery messages](BOUNDED-RECOVERY-MESSAGES.md).

Release source is `9309ccd9cfb44ee001c36c16c84f64858637862b`; accepted native/engine
source is `5ebaa55481308ec33169e0420fe10a8c31d9f8e4`. Nine new headless cases as
composite evidence, the accepted optimized native compile/product and unchanged
engine/header-audit/sidecar/runtime/dependency/icon/worker/recovery evidence were
reused. No functional test or native build was repeated for delivery.

New assembly metadata, sanitation, root signature, stapled ticket and Gatekeeper
checks passed. Apple notarization `56644144-8688-4f60-8215-7b54b8501a84` was
Accepted. The ZIP is 29,079,716 bytes. Journaled publication completed without
retrying a GitHub mutation. Prior releases/downloads remain preserved. No GUI
use, app launch or installation occurred. Live appearance/interaction remains
pending; directory listing/sorting is not bounded by the text cap.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.33).

## Previous release — Preview 32, build 36

Preview 32/build 36 independently audits zeroed preambles, synchronized file-meta
SOP Class/Instance UIDs and the writer's rebuilt implementation metadata. It
rejects reintroduced application identifiers/private information and extra fields.
The public UI, cleaning policy, retained content, sidecar defaults and report
schema are unchanged. See [File-header audit](FILE-HEADER-AUDIT.md).

Release source is `bf5a119e772a166020974d39015df9dca94a1008`; engine source is
`efb02dd47d09f544ca6a2542d2d78c58ef64d742`; native source remains
`af9ed1b84ca905ed5b69c809b031a705814499f2`. Seven new header-audit methods, one
affected RTSTRUCT round trip, three modified progress fixtures and earlier
unchanged engine/sidecar/runtime/dependency/icon/recovery evidence were reused.
No functional test or native build was repeated for delivery.

New assembly metadata, sanitation, root signature, stapled ticket and Gatekeeper
checks passed. Apple notarization `cb66d4be-01fb-4f66-81fd-3d131bfec65e` was
Accepted. The ZIP is 29,079,899 bytes. Guarded publication completed without
retrying a GitHub mutation; prior releases/downloads remain preserved.
No GUI use, app launch or installation occurred. Existing IOD, reference-closure,
pixel/anatomy and live-interaction limitations retain their original scope.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.32).

## Previous release — Preview 31, build 35

Preview 31/build 35 enforces the existing StructureSetLabel normalization in the
independent staged-output audit. Present root/nested labels must have SH VR and
decoded value `Structures`; absent labels remain accepted. The public UI,
metadata-cleaning policy, ROI-label retention, sidecar defaults and report schema
are unchanged. See [RTSTRUCT policy and coverage](RTSTRUCT-POLICY-COMPARISON.md).

Release source is `7be2548531f9d65d88bf893a35dcac6eb44008d0`; engine source is
`b50ac4dcc8d39ad6b1f94343ec7c8ca3548f49ff`; the reused native executable was built
at `af9ed1b84ca905ed5b69c809b031a705814499f2`. Accepted composite RTSTRUCT evidence
covers eleven methods, including five selected enforcement methods and eighteen
invalid-value/VR subcases. Six unaffected RTSTRUCT methods and earlier unchanged
engine/sidecar/runtime/dependency/icon/recovery evidence were reused.

No functional test or native build was repeated during delivery. New assembly
metadata, sanitation, root signature, stapled ticket and Gatekeeper checks passed.
Apple notarization `10c54229-3d93-483d-ae16-3d9a3e3dda5c` was Accepted. The ZIP is
29,079,491 bytes. Guarded publication completed without retrying a GitHub mutation.
No existing release or signed download was replaced. No GUI use, app launch or
installation occurred; live interaction/volume and complete RTSTRUCT IOD,
reference-closure and anatomical validation are not established by this evidence.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.31).

## Previous release — Preview 30, build 34

Preview 30/build 34 delivers bounded, identity-checked recovery-record reads and
qualified history-aware release provenance. Public UI, engine policy and sidecar
defaults are unchanged. Release source is `ec686b9fe6d047512a06913ffe0d8a7096f25f51`;
accepted native/engine source is `af9ed1b84ca905ed5b69c809b031a705814499f2`.

The accepted native executable, 15 new headless recovery cases, eight new
provenance fixture methods and unchanged engine/self-audit/sidecar/runtime/
dependency/icon evidence were reused. No native rebuild or functional test rerun
occurred for delivery. New assembly metadata, sanitation, root signature, stapled
ticket and Gatekeeper checks passed. Apple notarization
`7790c256-6886-481b-8067-791eb90f8e5a` was Accepted. The ZIP is 29,079,336 bytes.

The guarded publication journal completed without retrying a GitHub mutation.
Earlier releases and signed downloads remain preserved. No GUI use, app launch
or installation occurred; live interaction and volume behavior remain pending.
See [Recovery-record reads](RECOVERY-RECORD-READS.md) and
[Release automation](RELEASE-AUTOMATION.md) for scope and provenance semantics.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.30).

## Previous release — Preview 29, build 33

Preview 29/build 33 delivers terminal-event consistency and improved diagnostics
through the existing Copy Details action. The public UI, engine policy and
sidecar defaults are retained. The accepted delivery reused 26 new focused
terminal/diagnostic cases, one affected process case, the native compile and
earlier unchanged engine, self-audit, sidecar, runtime, dependency and icon evidence.
See [Terminal diagnostics](TERMINAL-DIAGNOSTICS.md) for the original scope.

Apple notarization `f7668439-61ac-49e2-b414-0edcc3c58346` was Accepted. The signed
download is 29,077,421 bytes. New distribution checks passed during that delivery;
they were not repeated for subsequent source-history sanitation.

The sanitized release tag selects `cc2cc4b787a10eb5b5e99f6bb36b8364db10cc2e`.
Existing signed downloads retain their original build metadata and accepted
receipts. A rewritten source identity does not mean a binary was rebuilt.
All 29 tags, 26 release records and 25 signed download assets were preserved
in the history sanitation operation. Historical source IDs below retain their
original meaning; they are not current sanitized source selections.

No GUI use, app launch or installation occurred for that delivery or sanitation.
Live recovery/report/sidecar interaction, responsiveness and layout remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.29).
Unreleased source changes do not change this delivered version.

## Previous release — Preview 26, build 30

The unified public app is delivered as **Preview 26/build 30**, using bounded read-only visibility reconciliation in `scripts/publication.py`. Packaged engine/release source is `c50ae5762c641d802f9934dbcd59e9229ded253a`; reused accepted native executable source is `b64ce1b2bb999c217c6c4fa9638dc872b67ad37b`. Apple notarization `19dbf886-c264-4d4e-b49f-8941b05e6bb7` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,070,670 bytes.

Fresh finalization created the new artifact-ownership record. Its release/build/source and artifact entries were checked once as new metadata; no existing package was rehashed or reverified. No retirement plan was applied to real artifacts. Native/engine behavior remains unchanged from Preview 25.

Accepted verification reused: 26 retirement fixture methods and existing report/warning, snapshot-generation, engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal/acknowledgement, runtime, dependency, icon and publication-tooling evidence. No functional tests, native builds, unchanged source hashes or dependency-signature checks were repeated for delivery.

No GUI use, native app launch or installation occurred. Public UI structure and engine policy are unchanged. Live scheduling, recovery/report/sidecar interaction, volume behavior, responsiveness and layout remain pending. Ownership metadata supplies ordinary replacement detection, not cryptographic or privileged-attacker guarantees.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.26). Earlier records retain their historical scope.

## Previous release — Preview 25, build 29

The unified public app is delivered as **Preview 25/build 29**, using bounded read-only visibility reconciliation in `scripts/publication.py`. Packaged engine/release source is `58bf002ad7f6a3f9ee5523fa831a346533d81414`; accepted native executable source is `b64ce1b2bb999c217c6c4fa9638dc872b67ad37b`. Apple notarization `058b706f-133d-4a76-9588-e2ed1bbbfa3a` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,070,680 bytes.

Accepted verification reused: eight report/warning transition cases, six snapshot-generation cases and existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal/acknowledgement, runtime, dependency, icon and publication-tooling receipts. No functional tests, native builds, unchanged source hashes or dependency-signature checks were repeated for delivery. Public UI structure and engine policy are unchanged.

No GUI use, native app launch or installation occurred. Pure report-result reducers and synthetic workers do not establish actual report opening or real engine audit/publication; prior on-disk record-retention evidence retains its scope. Live scheduling, recovery/report/sidecar interaction, volume behavior, responsiveness and layout remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.25). Earlier records retain their historical scope.

## Previous release — Preview 24, build 28

The unified public app is delivered as **Preview 24/build 28**, using bounded read-only visibility reconciliation in `scripts/publication.py`. Packaged engine/release source is `d788bab6bdd6a846955495d2763274780f5079ae`; accepted native executable source is `5c9f2aa1c9d087674e6dac7dbcfab31df41fc000`. Apple notarization `d02a98f3-53eb-4f67-875a-8538067b2ec7` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,065,676 bytes.

Accepted verification reused: nine directory/model cases, eight acknowledgement-feedback cases, two affected worker-to-model cases, and existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency, icon and publication-tooling evidence. No functional tests, native builds, unchanged source hashes or dependency-signature checks were repeated for delivery. Public UI structure and engine policy are unchanged.

No GUI use, native app launch or installation occurred. Injected permission failures and synthetic worker outcomes retain their original evidence limits; they do not establish all real filesystem/volume configurations or real engine audit/publication. Live scheduling, volume behavior, recovery/sidecar interaction, responsiveness and layout remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.24). Earlier records retain their historical scope.

## Previous release — Preview 23, build 27

The unified public app is delivered as **Preview 23/build 27**, using the bounded read-only visibility reconciliation in `scripts/publication.py`. Packaged engine/release source is `83a1b08533c60b6beb4132f6f389d67d68ca869b`; accepted native executable source is `71d934e607437779f65c9fb56f4f66a7836d9cc0`. Apple notarization `fe79275a-8326-47e4-8fb9-944e68a672f4` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,058,329 bytes.

This is a tooling/distribution update; native and engine behavior are unchanged from Preview 22. Accepted verification reused: 17 publication-visibility mocked methods, nine location/model and eight record-acknowledgement cases, plus existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency and icon receipts. No functional tests, native builds, unchanged source hashes or dependency-signature checks were repeated for delivery.

No GUI use, native app launch or installation occurred. Public UI structure and engine policy are unchanged. Live scheduling, volume behavior, recovery/sidecar interaction, responsiveness and layout remain pending. Prior synthetic evidence retains its original limits.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.23). Earlier records retain their historical scope.

## Previous release — Preview 22, build 26

The unified public app is delivered as **Preview 22/build 26**, using `scripts/publication.py`. Packaged engine/release source is `34e8dec7c8ebb1caf69b1f75cb1844fa56587410`; accepted native executable source is `71d934e607437779f65c9fb56f4f66a7836d9cc0`. Apple notarization `804435d2-ae0e-4a09-9a54-faef4d35d743` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,058,325 bytes.

Accepted verification was reused: nine output-location/model cases, eight synthetic subprocess/model/record acknowledgement cases and existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency, icon and publication-tooling receipts. No functional test or native build was repeated for delivery. Public UI structure and engine policy are unchanged. No GUI use, native app launch or installation occurred.

Temporary directory moves and synthetic records establish scoped recheck/acknowledgement behavior, not real volume mounting or engine processing/audit/publication/durability. Record-retention cases do not establish rejection of a completion summary. Live scheduling, volume behavior, recovery/sidecar interaction, responsiveness and layout remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.22). Earlier records retain their historical scope.

## Previous release — Preview 21, build 25

The unified public app is delivered as **Preview 21/build 25**, using `scripts/publication.py`. Packaged engine/release source is `54972ffb0bd4aa38d4a703fdc8ef72876bb11c32`; accepted native executable source is `1c198174ac0927337e7a1d40d59a0fb229e6eb09`. Apple notarization `6d5b7b80-2587-4948-8c58-6361a8f0633f` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,057,708 bytes.

Accepted verification was reused: seven recovery-explanation cases, eight headless worker-to-model cases and existing engine/policy/self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency, icon and publication-tooling evidence. No functional test or native build was repeated for delivery. Public UI structure and engine policy are unchanged. No GUI use, native app launch or installation occurred. Synthetic subprocess cases do not establish real Python processing, filesystem publication, journal acknowledgement or live UI behavior. Live scheduling, recovery/sidecar interaction, responsiveness and layout acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.21). Earlier records retain their historical scope.

## Previous release — Preview 20, build 24

The unified public app is delivered as **Preview 20/build 24**, using `scripts/publication.py`. Packaged engine/release source is `0e1868263a1b461e4530708d19a26176e06b1193`; accepted native executable source is `923828ab436daf06205857626e401503a29e0375`. Apple notarization `e24b8bff-915d-41be-8d8a-021c4de071eb` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. Archive size: 29,055,052 bytes.

Accepted verification was reused: 10 recovery-lifecycle cases, 10 headless worker process cases, four affected interruption cases and existing engine/policy/self-audit, sidecar/r2, worker/model, runtime, dependency and icon receipts. No functional test or native build was repeated for delivery. The public UI structure and engine policy are unchanged. No GUI use, native app launch or installation occurred. Live timer scheduling, recovery/sidecar interaction, responsiveness and layout acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.20). Prior receipts retain their historical scope.

## Previous release — Preview 19, build 23

The unified public app is delivered as **Preview 19/build 23**, using the new resumable publication tooling. Packaged engine/release source is `a4fb9336cf821889dfdc7b7eb2259eacee2398c6`; accepted native executable source is `b0feaaba596360e39e183a344cc7ded69e3e0cf4`. Apple notarization `d8530154-3c29-406a-bfce-51d5c6c86844` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. The archive is 29,048,047 bytes.

Accepted evidence was reused: 11 engine journal cases, 12 native recovery/model/filesystem cases, 12 mocked publication methods and the existing policy, self-audit, sidecar/r2, worker-feedback, runtime, icon and dependency receipts. No functional test or native build was repeated for delivery. No GUI use, native app launch or installation occurred. Live startup/recovery, sidecar interaction, responsiveness and compact-window acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.19). Earlier entries retain their historical scope.

## Previous release — Preview 18, build 22

The unified public app is delivered as Preview 18/build 22. See [Worker/sidecar feedback](WORKER-SIDECAR-FEEDBACK.md) for accepted source and distribution evidence. Accepted notarization is `d1641659-914f-4b24-a8e4-44c32d159eef`; release source `ca109d3`, native source `d7b49e4`. Existing receipts are reused, not reverified. No GUI use, native app launch or installation occurred for that delivery; live sidecar/startup/response/layout acceptance remains pending.

At that milestone, interruption recovery and resumable publication were not yet released. Older entries below are retained historical receipts, not current status.

## Preview 14 delivery (historical) — preview 14, build 18

The receipt-driven workflow delivered public Preview 14/app build 18 with accepted engine-source `80caae5` and reused native-source `b28a3df`. Release source: `e2f95de`. Apple accepted notarization `92ca3f7b-0e55-46b6-93f2-c3fceeed405e`; the new root signature, stapled ticket and Gatekeeper assessment passed once. Accepted estimate evidence (24 new checks and four affected existing checks for the public app) and earlier unchanged policy, self-audit, UI/build, runtime, icon and nested-signature receipts were reused. Five new packaging fixtures for the public release profile passed for distinct native/engine provenance and vendor cache exclusion; source-only review found no blockers. No accepted test suite, native build, provenance hash or dependency-signature check was repeated. The standalone arm64 ZIP was published and its HTTPS delivery returned HTTP 200. The deployment target remains macOS 13, with bundled Python. See `SPACE-ESTIMATE.md`.

## Preview 13 packaging withdrawal (historical)

Preview 13 was briefly published during release finalization with locally generated vendor bytecode caches. Its downloadable asset was withdrawn, and its tag/release record remains. Preview 14 replaces it with those caches excluded; the metadata policy and native code are unchanged. See `SPACE-ESTIMATE.md` for correction history.

## Preview 12 delivery (historical) — preview 12, build 16

The receipt-driven workflow delivered public Preview 12/app build 16 from accepted app-source `b28a3df`, with release merge `be40e72`. Apple accepted notarization `a90b6f26-e197-4512-962e-626a565ac180`; the new root signature, stapled ticket and Gatekeeper assessment passed once. Accepted optimized product, eight new focused engine telemetry checks, eleven new model checks and scoped native progress/cancellation review were reused. Earlier unchanged engine-policy, self-audit, runtime, icon, UI and nested-signature evidence remains reused. No accepted test suite, build, provenance hash or dependency-signature check was repeated. The standalone arm64 ZIP was published and its HTTPS delivery returned HTTP 200. The deployment target remains macOS 13, with bundled Python. See `SCAN-PROGRESS.md`.

## Preview 11 delivery (historical) — preview 11, build 15

The receipt-driven workflow assembled public Preview 11/app build 15 from accepted app-source `35c967c`, with release-tooling merge `546640d`. Apple accepted notarization `6d2d57f0-5b5b-48d7-91a2-2a9f345de687`. The new root signature, stapled ticket and Gatekeeper assessment passed once. Accepted executable, engine, policy, UI, Python, icon and nested-signature evidence was reused; no unchanged suite, build, provenance hash or dependency check was repeated. The existing interface and engine policy are unchanged. The standalone arm64 ZIP was published and its HTTPS delivery returned HTTP 200. This is macOS 13+ and requires no external Python installation. See `RELEASE-AUTOMATION-DELIVERY.md`.

## Preview 10 delivery (historical) — preview 10, build 14

`v2.0.0-preview.10` delivers disk-space and output-location recovery from accepted app-source `35c967c`, with release merge `7e78c05`. The independent SwiftUI interface, macOS 13 target, metadata policy, estimate formula, self-audit, report schema, Python and icon are retained. Apple accepted notarization `37d2468f-33cf-4a91-94c2-0be59e6bc79c`; the changed root signature, stapled ticket and Gatekeeper assessment passed. Accepted optimized product, 27 new engine storage cases plus one modified publication case, 11 model checks and focused native recovery were reused. No unchanged suite, build, source hash or dependency-signature check was repeated. See `STORAGE-RECOVERY.md` and the [visual roadmap](ROADMAP-VISUAL.md).

## Preview 9 delivery (historical) — preview 9, build 13

`v2.0.0-preview.9` delivers cancellation/publication and failed-cleanup recovery from accepted app-source `41594fa`, with release source `376613d`. It preserves the current SwiftUI interface, macOS 13 target, metadata policy, self-audit rules, report schema, bundled Python and icon. Apple accepted notarization `43c80b7e-5dd6-4ce0-a063-1c9d0a86f229`; the changed root signature, stapled ticket and Gatekeeper assessment passed. Accepted optimized product, 15 new mocked engine lifecycle checks, 13 new model checks and native recovery/Quit evidence were reused. No accepted suite, source hash or dependency/signature check was repeated. See `PUBLICATION-RECOVERY.md` for source and delivery boundaries.

## Preview 7 delivery (historical) — preview 7, build 11

`v2.0.0-preview.7` delivers compact recovery presentation from `96b1205` using
the accepted optimized executable. Long error text scrolls while the affected
path and recovery controls remain visible; blocking problems hide stale
completion details, and report warnings retain the completed result. The app
retains its existing SwiftUI interface, macOS 13 target, bundled Python and icon.
See `RECOVERY-PRESENTATION-PARITY.md` for the focused build/native presentation
evidence and reused verification. Distribution checks cover only the new bundle.

## Preview 6 delivery (historical) — preview 6, build 10

`v2.0.0-preview.6` delivers focused error recovery from `4e08049` using the accepted optimized executable. It retains the independent SwiftUI interface, macOS 13 target, bundled Python and approved icon. See `ERROR-RECOVERY.md` for new focused evidence and verification reuse. Previous releases and their acceptance records remain historical.

## Preview 5 delivery (historical) — preview 5, build 9

`v2.0.0-preview.5` delivers the accepted workflow polish with the existing standalone Python and icon. The existing SwiftUI interface is retained. Preview 4 remains available as the previous release; tags and earlier acceptance history are preserved.

## Preview 4 download housekeeping (historical)

Before preview 5 was prepared on 2026-10-14, `v2.0.0-preview.4` was the only downloadable GitHub release. Previews 1–3 were superseded by preview 4 and their GitHub release entries were removed; their Git tags remain. The earlier source-publication and runtime-acceptance records below are preserved as historical evidence. Preview 4 reuses the accepted standalone runtime from preview 3 and adds the approved icon; this housekeeping does not change source behavior, the current app download or acceptance scope.

## Preview 2 baseline acceptance

Date: 2026-10-14. Release: `v2.0.0-preview.2`; app version 2.0/build 6; bundle identifier `io.github.jdotc1.dicom-anonymizer`.

## Reused evidence

Earlier build-4 synthetic suite and native acceptance receipts remain historical evidence for unchanged behavior. The separate full proposed-patch results do not certify the selective build-5 composition. Existing source-export disclosure/syntax review is reused. No unchanged full suite, corpus pass, source-provenance hash, baseline signature check or dependency verification was repeated.

## Newly executed checks

- The ten previously unexecuted `Build5MetadataTests` passed: recursive retention and clearing/removal; device-class UID remapping; after-pixel metadata detection; scalar/sequence/free-text/UN leak rejection; cancellation error preservation; cross-patient and cross-role frame collision rejection; within-patient reference consistency; FIFO rejection before open.
- Real macOS target compiled with Xcode 27.2, Apple Swift 6.4, Swift 6 language mode and warnings as errors; arm64, macOS 13 deployment target.
- The example generator created six fictional MR/CT/RTSTRUCT objects in two numeric patient folders.
- Native model integration passed: NSItemProvider file-URL drop, exact identifiers, scan counts, progress/completion, completion summary, immediate cancellation, no cancelled output/staging residue, and tolerant handling of unknown engine events/fields. Test preferences use a separate bundle identifier.
- The Developer ID-signed release app launched from its actual release bundle. Native folder selection showed two patients and six DICOM files. Anonymize Batch completed with two patients, six files and zero exclusions. The resulting report's six-file self-audit passed.
- The model run's outputs preserved source pixel bytes, contour coordinates and series descriptions; preserved exact numeric pseudonyms; removed private tags; remapped source frames; and retained consistent within-patient image/RTSTRUCT references.
- Strict signature verification passed for the new Developer ID-signed package. Its first binary disclosure/inventory inspection found 25 upstream pydicom character-set/palette DICOM fixtures; the package was revised to omit these unused payloads. Code, license notices and prior native acceptance remain reused. The changed package inventory contains no DICOM files and no prior private-path/credential findings remain.
- Apple notarization accepted submission `b2376548-7ba2-4652-81c7-5b9eaf2cbd4b`. The ticket is stapled to the app and its validation passed. Gatekeeper accepted the app as a notarized Developer ID application.

## Environment and boundaries

Runtime host: Apple Silicon, macOS 27.2, Python 3.15.0, pydicom 3.0.2. Native model tests and signed-app interaction are separate evidence layers. The system emitted locale, task-port and NSOpenPanel diagnostics; no app crash, hang or failed processing was observed in this workflow.

This is focused synthetic acceptance, not a complete regression rerun, all-platform qualification, clinical validation, image redaction, certified DICOM confidentiality-profile compliance or complete IOD validation. macOS 13 is the build deployment target; this run does not establish runtime acceptance on every macOS version. Python is a required external runtime. Signing and notarization status must be read from the published release record.

## Standalone runtime delta — preview 3, build 7

The engine, pydicom package, metadata policy, original synthetic fixture, ten build-5 tests and preview-2 native/drop/cancellation results are unchanged and reused. New work is limited to bundled Python, launcher selection, packaging/signing and runtime notices.

- Pinned CPython 3.13.16, python-build-standalone release 20261013, arm64. First acquisition matched the upstream GitHub digest. Subsequent build reused the stat/digest-bound archive receipt; no unchanged archive was rehashed. Matching full-distribution license texts are retained.
- The changed real Swift target built successfully. The launcher selects `Contents/Resources/python/bin/python3` exclusively, with isolated Python execution (`-I`) and no external interpreter fallback.
- The bundled interpreter started with a minimal PATH and access denied to Homebrew, `/usr/local`, the system Python framework and the local uv/venv Python locations. Standard-library native imports succeeded. All Python import paths were inside the app.
- A focused native-model harness passed the missing-runtime error case, then scanned and processed the accepted six-file fixture using bundled Python 3.13.16/pydicom 3.0.2 with external runtime locations denied. Its output report self-audit passed.
- The signed standalone app completed the same native folder-selection/scan/process workflow with two patients, six files and zero exclusions. Its report identified bundled Python 3.13.16 and passed the six-file self-audit. A relocated copy in a differently named folder also scanned successfully with external runtimes denied.
- First linkage inspection of the new Python native code found no non-system absolute library dependencies. Eleven Mach-O code files, including the changed Swift executable, were signed from the inside out; the new bundle passed deep strict signature verification.
- First bounded disclosure inspection covered the newly introduced runtime/notices and changed native executable: no checked private-path, account-email, private-key or DICOM-payload findings. Unchanged engine/vendor content reused its existing receipt.

The standalone runtime's build deployment target is macOS 11. The app remains arm64/macOS 13+. Runtime interaction was checked on macOS 27.2; older macOS versions, Intel execution and physical clean-machine installation were not tested. Denied external-runtime access is the evidence for Python independence. This changes runtime delivery, not scientific or clinical validation scope. Apple notarization accepted standalone submission `dbf019f6-291e-4dd9-961d-e46ac4e5013c`; the ticket was stapled and validated, and Gatekeeper accepted the app as Notarized Developer ID.

## Icon resource delta — preview 4, build 8

The accepted preview-3 standalone bundle is reused. Already compiled `Assets.car` and `AppIcon.icns` were copied from the separately accepted icon build, with `CFBundleIconName` and `CFBundleIconFile` both set to `AppIcon`. The new package build number is 8; engine policy remains `2.0-build5`. The icon's authoring files/provenance remain private by the owner's instruction.

Existing icon compilation and native appearance evidence were reused. No Swift or engine rebuild, icon recompilation, runtime/engine test, self-audit test, dependency re-verification or source hash was repeated for this resource-only delta. The icon package composition was checked, its changed root signature passed strict verification, Apple accepted notarization submission `f026e02d-f2ad-43c4-ace9-98c60bcdc46c`, and its ticket and Gatekeeper assessment passed. Nested code signatures and all standalone acceptance evidence remain reused.

## Workflow polish distribution — preview 5, build 9

The focused workflow-polish source, optimized build, synthetic model/layout and native presentation evidence is reused from the accepted polish pass. The standalone runtime, engine, self-audit, compiled icon and nested signatures remain unchanged. Release metadata selects app 2.0/build 9. A new Developer ID root signature passed strict verification and Apple accepted notarization `c36ff882-9b96-4888-8cf2-a7edf23edb98`. Stapling, ticket validation and Gatekeeper acceptance are recorded with the final release artifact. No engine/self-audit processing, unchanged UI/theme/runtime/dependency checks or hashes were repeated.

## Focused recovery distribution — preview 6, build 10

The accepted recovery executable and unchanged bundled resources are reused. The new root Developer ID signature passed strict verification and Apple accepted submission `97c13195-06fc-4cec-9261-1ef558d33792`. Final stapling, ticket validation and Gatekeeper evidence are recorded for this artifact. No unchanged engine, self-audit, UI suite, runtime/dependency check or hash was repeated.
