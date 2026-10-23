# Source publication record

## Current release — preview 14, build 18

The receipt-driven workflow delivered public Preview 14/app build 18 with accepted engine-source `80caae5` and reused native-source `b28a3df`. Release source: `e2f95de`. Apple accepted notarization `92ca3f7b-0e55-46b6-93f2-c3fceeed405e`; the new root signature, stapled ticket and Gatekeeper assessment passed once. Accepted estimate evidence (24 new checks and four affected existing checks per repository) and earlier unchanged policy, self-audit, UI/build, runtime, icon and nested-signature receipts were reused. Five new packaging fixtures per app profile passed for distinct native/engine provenance and vendor cache exclusion; source-only review found no blockers. No accepted test suite, native build, provenance hash or dependency-signature check was repeated. The standalone arm64 ZIP was published and its HTTPS delivery returned HTTP 200. The deployment target remains macOS 13, with bundled Python. See `SPACE-ESTIMATE.md`.

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

`v2.0.0-preview.5` delivers the accepted workflow polish with the existing standalone Python and icon. The SwiftUI interface remains independent of the private Lumen app. Preview 4 remains available as the previous release; tags and earlier acceptance history are preserved.

## Preview 4 download housekeeping (historical)

Before preview 5 was prepared on 2026-10-14, `v2.0.0-preview.4` was the only downloadable GitHub release. Previews 1–3 were superseded by preview 4 and their GitHub release entries were removed; their Git tags remain. The earlier source-publication and runtime-acceptance records below are preserved as historical evidence. Preview 4 reuses the accepted standalone runtime from preview 3 and adds the approved icon; this housekeeping does not change source behavior, the current app download or acceptance scope.

## Destination and scope

The owner authorized public publication under the personal GitHub profile `jdotc1`. The publication destination is [jdotc1/dicom-anonymizer](https://github.com/jdotc1/dicom-anonymizer). This is a fresh source-only repository, separate from private development history. The initial source-only release is `v2.0.0-preview.1`. The current standalone macOS binary preview is `v2.0.0-preview.14`; it bundles Python and its focused acceptance is recorded in `RUNTIME-ACCEPTANCE.md`.

## Publication controls

- Include reviewed source, synthetic example/test sources, MIT license and dependency notices.
- Exclude patient data, private development history, internal receipts, prior build artifacts, credentials, signing material and existing artwork.
- Keep GitHub Actions disabled at publication. The committed workflow is manual-only and requires explicit acknowledgement if Actions is enabled later.
- Enable GitHub private vulnerability reporting and confirm its API status after the repository becomes public.
- Confirm the repository owner, public visibility, published source commit and prerelease metadata through GitHub.
- Preserve the private development repository and its history separately.

## Attribution and security

Copyright remains DICOM Anonymizer Project contributors. The source commits use a neutral display identity and the deliberately non-deliverable `maintainers@dicom-anonymizer.invalid` address. This address is not a contact channel. Repository ownership publicly associates this project with `jdotc1` by the owner’s choice; no personal email address is included in source metadata.

Use the repository’s Security > Advisories > Report a vulnerability channel. Reports must use synthetic reproductions. Repository administrators should monitor private-report notifications; no personal notification address is published and no response-time guarantee is made.

## Evidence and maturity

Publication readiness concerns source disclosure, packaging and truthful documentation. It does not establish runtime acceptance, clinical suitability, certified DICOM confidentiality-profile compliance or complete IOD conformance. The existing export disclosure/syntax receipt is retained privately. Unchanged sources were not retested or rehashed for publication. See `RUNTIME-ACCEPTANCE.md` for the newly executed focused runtime work and `RELEASE-REVIEW.md` for release boundaries.
