# macOS release acceptance

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
