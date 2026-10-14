# macOS preview acceptance

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
