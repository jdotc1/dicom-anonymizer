# DICOM Anonymizer

A local bulk metadata-pseudonymization tool for numeric patient-folder batches, with a Python engine and an optional native macOS interface. Licensed under MIT.

**Source preview — v2.0.0-preview.1.** The current changes have not completed runtime acceptance. This repository contains source and entirely synthetic example generators, with no downloadable app release. Synthetic objects demonstrate metadata behavior and references; they are not clinical images or complete IOD-validation fixtures.

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

## Native macOS interface

The source target is Apple Silicon with macOS 13+. Building requires full Xcode with Apple Swift 6.4 and Swift 6 language mode; warnings are treated as errors. `toolchain.sh` uses the selected Xcode installation or `DEVELOPER_DIR`.

```sh
bash build.sh
```

The local result is `build/DICOM Anonymizer 2.0.app`, ad-hoc signed for local development. No Developer ID certificate, notarization credential or signing key is included. There is no standalone runtime: install Python 3.10+ at a standard Homebrew location (`/opt/homebrew/bin/python3` or `/usr/local/bin/python3`). The app bundles pydicom and its distribution notices but not Python. The source build does not embed the build-machine interpreter path. No custom artwork is included.

The bundle identifier uses the reserved `org.example` namespace for this source preview. Choose the project's final identifier before a signed distribution. Intel and other operating systems are not claimed as native-app targets; the Python engine remains available separately.

## Retained content and privacy

SeriesDescription, ProtocolName, SequenceName, ContrastBolusAgent, SoftwareVersions, Manufacturer, pixels, contour geometry, measurements, and approved ROI names/observation labels are retained. Numeric pseudonyms remain linkable. Image text, faces and retained free text are not visually redacted. Processing is metadata pseudonymization, without a claim of certified DICOM confidentiality-profile or complete IOD conformance. Review retained content before sharing.

Do not post patient files, original filenames, identifiers, or unredacted logs in issues or pull requests. Use synthetic reproductions. See `SECURITY.md` and `CONTRIBUTING.md`.

## Development and acceptance

Unit tests use synthetic temporary data. The optional native integration test uses only the example generator:

```sh
python -m unittest discover -s tests -v
bash test_drop.sh
```

These are reference commands, not results reported for this snapshot. No suite, build or native integration was rerun during source-export preparation. CI is manual-only, requires an explicit acknowledgement, and has read-only repository permissions. Maintainers should reuse valid verification evidence and authorize any new acceptance work deliberately.

The native test uses a separate preferences identifier and writes only under `.synthetic/`. The engine/policy is build 5. The public repository is maintained under the owner’s personal GitHub profile at [jdotc1/dicom-anonymizer](https://github.com/jdotc1/dicom-anonymizer). Use GitHub private vulnerability reporting for security-sensitive reports; see `SECURITY.md`. Runtime acceptance remains pending; see `docs/RELEASE-REVIEW.md`.

## License and dependencies

Project source is MIT-licensed; see `LICENSE`. Dependency notices remain under their respective terms. See `THIRD_PARTY_NOTICES.md`. No patient datasets, private development history, previous build artifacts, or internal evidence archives are included.
