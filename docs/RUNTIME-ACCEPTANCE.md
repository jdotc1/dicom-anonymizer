# macOS release acceptance

## Current release — preview 10, build 14

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
