# Source publication record

## Current release — preview 7, build 11

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

The owner authorized public publication under the personal GitHub profile `jdotc1`. The publication destination is [jdotc1/dicom-anonymizer](https://github.com/jdotc1/dicom-anonymizer). This is a fresh source-only repository, separate from private development history. The initial source-only release is `v2.0.0-preview.1`. The current standalone macOS binary preview is `v2.0.0-preview.7`; it bundles Python and its focused acceptance is recorded in `RUNTIME-ACCEPTANCE.md`.

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
