# macOS preview release

Release: `v2.0.0-preview.2`, prepared 2026-10-14. Destination: [jdotc1/dicom-anonymizer](https://github.com/jdotc1/dicom-anonymizer). MIT license. The owner authorized public source publication under the personal profile. A fresh source history is published; private development history is excluded.

## Included

Python engine and bootstrap, native Swift source, local build scripts, pinned requirements, synthetic unit/native test sources, a standalone fictional-data generator, manual-only synthetic CI, license/dependency notices and documentation. The generator reads no files and writes new synthetic objects. No actual DICOM files or patient-derived examples are committed.

## Excluded

Private source-control history, internal handoff documents, execution receipts, original-path manifests, real-cohort tests/audits, patient data/outputs, prior app binaries, signing keys, credentials and existing app artwork. The private development repository remains separate.

## Attribution and contact

Copyright: DICOM Anonymizer Project contributors. Source commit metadata uses the deliberately non-deliverable `maintainers@dicom-anonymizer.invalid` address. It is not a registered contact or support mailbox. Public repository ownership is `jdotc1`. Use GitHub private vulnerability reporting for security-sensitive reports. The release app identifier is `io.github.jdotc1.dicom-anonymizer`.

## Evidence boundaries

Focused acceptance of previously unexecuted build-5 regressions and public-export changes is complete. The ten focused tests, real Swift 6.4 build, native model integration and signed-app six-file workflow passed. See `RUNTIME-ACCEPTANCE.md` for exact checks and limits. Earlier evidence was reused; unchanged full suites, corpus passes and provenance/dependency checks were not repeated.

The release ZIP targets Apple Silicon and requires Python 3.10+ at a supported Homebrew location. It bundles pydicom and its complete distribution notices, along with the project MIT license and third-party notice. The app identifier is `io.github.jdotc1.dicom-anonymizer` and the build number is 6. GitHub release metadata records final signing/notarization and download status.

## Release designation

This remains a preview prerelease. Focused runtime acceptance does not establish clinical validation, complete anonymization, certified confidentiality-profile compliance, complete IOD conformance or all-macOS-version qualification. Retained pixels, descriptors and linkable pseudonyms remain documented in the README and data-handling contract.
