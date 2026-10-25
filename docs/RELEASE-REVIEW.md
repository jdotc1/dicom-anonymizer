# macOS preview release

Release: `v2.0.0-preview.6`, prepared 2026-10-14. Destination: [jdotc1/dicom-anonymizer](https://github.com/jdotc1/dicom-anonymizer). MIT license. This record describes the source-disclosure and packaging scope of that historical preview.

## Included

Python engine and bootstrap, native Swift source, local build scripts, pinned requirements, synthetic unit/native test sources, a standalone fictional-data generator, manual-only synthetic CI, license/dependency notices and documentation. The generator reads no files and writes new synthetic objects. No actual DICOM files or patient-derived examples are committed.

## Excluded

Patient data and outputs, local operational records, internal correspondence, previous build artifacts, signing keys, credentials and icon-authoring files are excluded from the public source distribution.

## Attribution and contact

Copyright remains DICOM Anonymizer Project contributors. Use GitHub private vulnerability reporting for security-sensitive reports; see `SECURITY.md` for reporting channels. The release app identifier is `io.github.jdotc1.dicom-anonymizer`.

## Evidence boundaries

Focused acceptance of previously unexecuted build-5 regressions and public-export changes is complete. The ten focused tests, real Swift 6.4 build, native model integration and signed-app six-file workflow passed. See `RUNTIME-ACCEPTANCE.md` for exact checks and limits. Earlier evidence was reused; unchanged full suites, corpus passes and provenance/dependency checks were not repeated.

The standalone release ZIP targets Apple Silicon and includes CPython 3.13.16. No Homebrew or separate Python installation is required. It bundles pydicom and its complete distribution notices, along with the project MIT license and third-party notice. Python and compiled-dependency license texts are retained. The app identifier is `io.github.jdotc1.dicom-anonymizer` and the build number is 11. GitHub release metadata records final signing/notarization and download status.

## Release designation

This remains a preview prerelease. Focused runtime acceptance does not establish clinical validation, complete anonymization, certified confidentiality-profile compliance, complete IOD conformance or all-macOS-version qualification. Retained pixels, descriptors and linkable pseudonyms remain documented in the README and data-handling contract.

## Icon packaging delta (preview 4 history)

The downloadable app includes the project-selected app icon using compiled `Assets.car` and `AppIcon.icns` resources supplied separately. Both `CFBundleIconName` and `CFBundleIconFile` are set to `AppIcon`. Icon-authoring files are not distributed in this source repository; applicable artwork rights remain unchanged. Existing icon compilation and native appearance evidence were reused; the engine, runtime and Swift executable were not rebuilt or retested for this resource-only delta.

## Workflow polish delta — preview 5

The optimized executable accepted in `438fccb` is reused. The update improves preparing/finalizing feedback, long paths, completion layout and file commands, and disables processing after invalid selection. Focused model/layout and native presentation/command evidence is recorded in `WORKFLOW-POLISH.md`. The engine, self-audit, Python/runtime dependencies and compiled icon are unchanged; their existing receipts and nested signatures are reused. New release metadata and root signing/notarization are checked once for this artifact. No full UI or engine suite is repeated.

## Focused recovery delta — preview 6

The accepted optimized executable from `4e08049` is reused. Source and binary changes are limited to recovery/model action guards and existing-interface error presentation; engine policy, standalone runtime and compiled icon are unchanged. `ERROR-RECOVERY.md` records the new model/layout/native presentation checks. Distribution uses new metadata (app 2.0/build 10), root signing and notarization. No unchanged engine, self-audit, UI, runtime or dependency checks are repeated.

## Compact recovery presentation delta — preview 7

The accepted optimized executable from `96b1205` is reused. New presentation
checks at 700 × 655 content points in light and dark cover long-error scrolling,
fixed paths/actions, stale-completion suppression for blocking errors, and
completion retention for report warnings. Source, synthetic presentation and
startup evidence are recorded in `RECOVERY-PRESENTATION-PARITY.md`. The package
uses app 2.0/build 11 and retains accepted Python dependencies, engine, notices
and compiled icon. Only the changed package receives new root signing,
notarization, ticket validation and Gatekeeper assessment. No rebuild or
unchanged suite, dependency check or provenance hash is repeated.
