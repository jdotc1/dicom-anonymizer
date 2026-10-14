# DICOM Anonymizer

A local bulk metadata-pseudonymization tool for numeric patient-folder batches, with a Python engine and an optional native macOS interface. Licensed under MIT.

**Standalone macOS preview — v2.0.0-preview.5.** Focused runtime acceptance of the public-export changes is complete on Apple Silicon. The repository contains source and entirely synthetic example generators. Synthetic objects demonstrate metadata behavior and references; they are not clinical images or complete IOD-validation fixtures.

The workflow-polish update adds clearer preparing/finalizing status, long-path handling, completion actions and File-menu shortcuts. See `docs/WORKFLOW-POLISH.md` for focused evidence and reuse boundaries.

## Workflow

Each immediate folder under an input batch is a numeric pseudonym, such as `00001` or `00002`. Its exact spelling, including leading zeros, becomes the output folder name and both PatientName and PatientID. The engine processes the whole batch, generates new internal names, and atomically publishes a new output folder. Sources remain read-only.

MR, CT and RTSTRUCT are supported. Conflicting patient identities, a study split across patient folders, or patient-relative frame-of-reference UIDs shared across patient folders stop the batch. References within each patient remain consistently remapped. Other unsupported or malformed inputs can also stop the batch; see `docs/DATA-HANDLING.md`.

## Python engine

Requires Python 3.10+ and pydicom 3.0.2. Dependency installation needs access to a package source; anonymization itself has no upload or network feature.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python examples/generate_batch.py --destination .synthetic/input
python engine/engine.py --source .synthetic/input --scan
python engine/engine.py --source .synthetic/input --destination .synthetic/output
```

The generator reads no patient data and creates two fictional patients with six small MR/CT/RTSTRUCT objects. It refuses to overwrite an existing destination. Expected output contains `00001` and `00002`, three DICOM files per patient, and `anonymization-report.json`. Inspect that report for aggregate counts and self-audit status. Choose a new destination for another run.

## Download and install the macOS app

The macOS release ZIP contains `DICOM Anonymizer 2.0.app`. Expand the ZIP and copy the app to Applications. This preview targets **Apple Silicon and macOS 13 or newer**. Runtime acceptance was performed on macOS 27.2; older supported deployment versions and Intel Macs were not exercised.

**No Homebrew or separate Python installation is required.** The app includes CPython 3.13.16 and pydicom 3.0.2. It uses only its bundled interpreter and relocates with the app. No runtime download or package installation occurs at launch.

The downloadable release is Developer ID signed and Apple notarized, with the notarization ticket stapled to the app. See the repository’s Releases section for the ZIP and acceptance details. Metadata processing runs locally. Review the retained-content policy below before sharing outputs.

## Native macOS interface

The source target is Apple Silicon with macOS 13+. Building requires full Xcode with Apple Swift 6.4 and Swift 6 language mode; warnings are treated as errors. `toolchain.sh` uses the selected Xcode installation or `DEVELOPER_DIR`.

```sh
bash build.sh
```

The local result is `build/DICOM Anonymizer 2.0.app`, ad-hoc signed for local development. Building requires a local Python 3.12+ environment with the pinned pydicom dependency, and downloads the pinned standalone Python archive on first use. Unchanged cached archives reuse their digest-bound acquisition receipt. This is a build-time requirement; the resulting app includes Python and pydicom. Runtime and dependency notices are bundled. No Developer ID certificate, notarization credential, signing key or custom artwork is included in source. The downloadable app includes the project-selected icon. For a local build with externally supplied compiled icon resources, set `APP_ICON_RESOURCES` to a folder containing `Assets.car` and `AppIcon.icns`; the build copies those resources and sets both icon plist keys before signing.

The release bundle identifier is `io.github.jdotc1.dicom-anonymizer`, with app version 2.0/build 9. Intel and other operating systems are not claimed as native-app targets; the Python engine remains available separately.

## Retained content and privacy

SeriesDescription, ProtocolName, SequenceName, ContrastBolusAgent, SoftwareVersions, Manufacturer, pixels, contour geometry, measurements, and approved ROI names/observation labels are retained. Numeric pseudonyms remain linkable. Image text, faces and retained free text are not visually redacted. Processing is metadata pseudonymization, without a claim of certified DICOM confidentiality-profile or complete IOD conformance. Review retained content before sharing.

Do not post patient files, original filenames, identifiers, or unredacted logs in issues or pull requests. Use synthetic reproductions. See `SECURITY.md` and `CONTRIBUTING.md`.

## Development and acceptance

Unit tests use synthetic temporary data. The optional native integration test uses only the example generator:

```sh
python -m unittest discover -s tests -v
bash test_drop.sh
```

The ten build-5 regression tests passed for preview 2 and that evidence is reused. The real app compiled with Swift 6.4, the synthetic native model integration passed, and the signed release app completed a native six-file batch. Existing earlier suite receipts were reused; full suites and corpus passes were not repeated. See `docs/RUNTIME-ACCEPTANCE.md` for scope and results. CI is manual-only, requires explicit acknowledgement, and has read-only repository permissions.

Bundled-runtime checks cover Swift-to-Python scan/completion with external Python locations denied and the missing-runtime error without external fallback. The native test uses a separate preferences identifier and writes only under `.synthetic/`. The engine/policy is build 5. The public repository is maintained under the owner’s personal GitHub profile at [jdotc1/dicom-anonymizer](https://github.com/jdotc1/dicom-anonymizer). Use GitHub private vulnerability reporting for security-sensitive reports; see `SECURITY.md`. Focused runtime acceptance is recorded in `docs/RUNTIME-ACCEPTANCE.md`; see `docs/RELEASE-REVIEW.md` for release boundaries.

## License and dependencies

Project source is MIT-licensed; see `LICENSE`. Dependency notices remain under their respective terms. See `THIRD_PARTY_NOTICES.md`. No patient datasets, private development history, previous build artifacts, or internal evidence archives are included.
