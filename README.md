# DICOM Anonymizer

**Current release: Preview 35/build 39.** DICOM-only batches receive strict
staging-inventory checks before publication, and recovery-record updates detect
ordinary concurrent replacement during preparation. The public interface,
metadata-cleaning policy, report fields and sidecar default remain unchanged.
See [Staging and journal protection](docs/STAGING-JOURNAL-PROTECTION.md) and the
[release download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.35).

**Resilience delivery:** Preview 19/build 23 adds interruption recovery and ships through the resumable publication tooling; consolidation cleanup is complete. See [Interruption recovery](docs/INTERRUPTION-RECOVERY.md).

**Recovery lifecycle:** Preview 20/build 24 delivers combined recovery notices, safe local-record retirement and guarded live-owner reinspection, with accepted headless worker process coverage. See [Recovery lifecycle](docs/RECOVERY-LIFECYCLE.md).

**Recovery explanations:** Preview 21/build 25 adds clearer confirmed/uncertain recovery guidance, with accepted headless worker-to-model integration coverage. See [Recovery explanations](docs/RECOVERY-EXPLANATIONS.md).

**Output-location recovery:** Preview 22/build 26 delivers guarded recovery-location rechecks, with accepted headless record acknowledgement coverage. See [Output-location rechecks](docs/OUTPUT-LOCATION-RECHECKS.md).

**Release tooling:** Preview 23/build 27 ships through bounded read-only reconciliation of delayed release/asset visibility and stale publication resumes, preserving journal/ownership safeguards. See [Resumable publication](docs/RESUMABLE-PUBLICATION.md).

**Recovery-state feedback:** Preview 24/build 28 retains uncertainty on recovery-directory inspection failure and preserves completed results with nonblocking acknowledgement warnings. See [Recovery-state feedback](docs/RECOVERY-STATE-FEEDBACK.md).

**Recovery consistency:** Preview 25/build 29 preserves outstanding acknowledgement warnings across report recovery and rejects stale background snapshots with generation tokens. See [Recovery consistency](docs/RECOVERY-CONSISTENCY.md).

**Artifact retirement tooling:** Preview 26/build 30 ships through fresh ownership-record creation; the plan-first retirement command protects current inputs and evidence. Cleanup requires a separate explicit apply. See [Artifact retirement](docs/ARTIFACT-RETIREMENT.md).

**Worker/sidecar feedback:** Preview 18 delivers robust worker-event framing and sidecar preflight/completion counts in the existing interface. See [Worker and sidecar feedback](docs/WORKER-SIDECAR-FEEDBACK.md).

**Unified public app:** ongoing development now uses this self-contained public SwiftUI implementation. Preview 16 adds detailed folder-conflict recovery and optional MRI JSON-sidecar cleaning. Live sidecar GUI acceptance remains pending. See [Consolidation](docs/PUBLIC-CONSOLIDATION.md) and [MRI JSON sidecars](docs/MRI-JSON-SIDECARS.md).

**Local DICOM metadata pseudonymization for imaging-data privacy.**

DICOM Anonymizer combines a Python engine with a native macOS interface for
preparing pseudonymized MR, CT, and RTSTRUCT batches. It replaces patient
identity fields with numeric folder pseudonyms and consistently remaps
patient-specific UIDs and nested references. Processing runs locally, keeps
source files read-only, and rereads staged output for self-audit before
publishing a new batch.

Use it when a research workflow calls for numeric patient pseudonyms and
consistent references across a batch. Its metadata policy preserves image
pixels and contour geometry; retained content still requires review before
sharing.

**[Download the macOS preview](https://github.com/jdotc1/dicom-anonymizer/releases)** ·
**[Try the Python engine](#try-it-with-synthetic-data)** ·
**[Data-handling policy](docs/DATA-HANDLING.md)** ·
**[Report an issue](https://github.com/jdotc1/dicom-anonymizer/issues)**

The standalone preview targets **Apple silicon and macOS 13+** and includes
Python and pydicom. The Python engine is also available separately. Project
source is [MIT-licensed](LICENSE).

> **Metadata pseudonymization has limits.** Numeric folder identifiers remain in
> PatientName and PatientID and can remain linkable. Pixels, contours, selected
> free text, and demographic attributes are retained. The tool does not redact
> image text or faces and does not guarantee irreversible anonymity, certified
> DICOM confidentiality-profile conformance, or complete IOD validation. Review
> [retained content](#what-changes-and-what-remains) before sharing output.

**Current download: [Preview 35 (app build 39)](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.35).** Unified public app with strict DICOM-only staging inventories, recovery-record write protection, structured audit-coverage reports, bounded recovery messages, independent staged-header auditing and default-off MRI JSON-sidecar cleaning. Signed, notarized and stapled; accepted verification reused. Live GUI acceptance remains pending.

Preview 14 introduced allocation-aware estimates. Allocation-aware disk-space estimates account for metadata growth, destination allocation, output folders and the report while preserving the interface and engine policy. See [Disk-space estimate](docs/SPACE-ESTIMATE.md) and the [visual development roadmap](docs/ROADMAP-VISUAL.md).

Output self-audit progress and checked-file counts, introduced in Preview 8, remain included. See [Audit progress](docs/AUDIT-PROGRESS.md) for that contract and reused evidence.

## The batch workflow

Arrange the input as a batch folder whose immediate child folders are numeric
patient pseudonyms, such as `00001` and `00002`. Each identifier may be up to 64
characters, and its exact spelling—including leading zeros—becomes the output
folder name and both PatientName and PatientID.

1. **Scan the batch.** The engine checks supported inputs and cross-file identity
   and reference constraints.
2. **Process into a new destination.** Internal filenames are generated
   independently of source names; patient-specific UIDs and nested references
   are consistently remapped within each patient.
3. **Review the report and retained content.** Staged files are reread and
   self-audited before atomic publication. The completed batch includes
   `anonymization-report.json` with pseudonyms, aggregate counts, software/policy
   versions, and audit status, without an original-identity mapping.

The supported modality labels are **MR, CT, and RTSTRUCT**. Conflicting patient
identities, a study split across patient folders, or patient-relative
frame-of-reference UIDs shared across patient folders stop the batch. Repeated
references within one patient remain allowed. These checks do not establish
complete validity of every MR/CT/RTSTRUCT object.

## Download and install the macOS app

1. Open [Releases](https://github.com/jdotc1/dicom-anonymizer/releases) and download
   the standalone macOS arm64 preview ZIP.
2. Expand it and copy **DICOM Anonymizer 2.0.app** to Applications.
3. Open the app, choose the input batch and an output location, inspect the scan
   summary, and process the batch.

The [Preview 35 release](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.35)
is app version 2.0.0, build 39. Its app is Developer ID signed and Apple notarized,
with a stapled ticket. It includes **CPython 3.13.16 and pydicom 3.0.2** and uses
its bundled interpreter wherever the app is moved. No Homebrew, separate Python
installation, launch-time runtime download, or package installation is needed.

Earlier focused runtime acceptance was performed on Apple silicon with macOS 27.2. Older
deployment versions and Intel Macs were not exercised. The macOS 13 deployment
target is not a claim of runtime acceptance on every newer OS release.

### Recover from a problem

Preview 7 keeps long recovery messages scrollable while the affected path and
recovery actions remain visible. Blocking problems hide stale completion details;
report warnings preserve the completed result. The existing recovery behaviors
from preview 6 remain:

| Problem | App behavior |
| --- | --- |
| Rejected or inaccessible input | Clears the previous source and ready preview so another action cannot silently process an old batch. Choose a valid folder and check again. |
| Invalid or disconnected output location | Offers Choose Location. A valid replacement preserves the scanned batch without rescanning. Directory-existence validation does not guarantee write permission. |
| Missing or unopenable report | Keeps the completed-batch summary. Reveal Output locates the result; Dismiss returns to the completed state. |
| Cancellation or pending error | Keeps action availability consistent while the worker stops, ignores late progress, and disables repeated cancellation. |

See [compact recovery presentation](docs/RECOVERY-PRESENTATION-PARITY.md) for the
new focused evidence, [error recovery](docs/ERROR-RECOVERY.md) for the preceding
behavior, and [workflow polish](docs/WORKFLOW-POLISH.md) for earlier interface changes.

## Try it with synthetic data

The engine requires **Python 3.10+ and pydicom 3.0.2**. Installing the dependency
needs access to a package source; processing has no upload or network feature.

```sh
git clone https://github.com/jdotc1/dicom-anonymizer.git
cd dicom-anonymizer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python examples/generate_batch.py --destination .synthetic/input
python engine/engine.py --source .synthetic/input --scan
python engine/engine.py --source .synthetic/input --destination .synthetic/output
```

The generator reads no patient files. It creates two fictional patients and six
small MR/CT/RTSTRUCT objects, demonstrating metadata and references rather than
clinical images or complete IOD validation fixtures. Both the generator and
processing destination refuse an existing destination; choose a new path for
another run.

Expected output has `00001` and `00002`, three DICOM files per patient, and
`anonymization-report.json`. Inspect the report's aggregate counts and self-audit
status. The CLI emits JSON-line `scan`, `progress`, `complete`, and `error` events;
see the [engine guide](engine/README.md).

## What changes and what remains

| Content | Policy |
| --- | --- |
| PatientName and PatientID | Replaced recursively with the exact numeric patient-folder identifier. |
| Patient-specific UIDs and nested references | Consistently remapped. SOP-class, transfer-syntax, and explicit structural/coding identifiers remain. |
| Private tags, uninterpreted public UN elements, dates/times, and known identifying fields | Cleared or removed; retired curve groups are removed. Required type-2 fields may remain present with empty values. |
| File metadata and preamble | Rebuilt and synchronized; preambles are zeroed. |
| SeriesDescription, ProtocolName, SequenceName, ContrastBolusAgent, SoftwareVersions, and Manufacturer | Retained. Free text can still identify people or institutions. |
| PatientSex, PatientAge, PatientSize, and PatientWeight | Retained. These attributes can remain identifying in combination with other information. |
| Image pixels, contour geometry, public quantitative measurements, ROI names, and observation labels | Retained. Visual identifiers and facial anatomy are not removed. |

Removing private tags can remove vendor-specific quantitative information;
clearing dates removes temporal information. An absent burned-in annotation flag
does not establish that pixels contain no identifying content.

For RTSTRUCT-specific handling, retained labels, reference/geometry limits and
the focused comparison with the Stanford scripts, see
[RTSTRUCT policy and coverage](docs/RTSTRUCT-POLICY-COMPARISON.md).

The independent [staged-file header audit](docs/FILE-HEADER-AUDIT.md) also has
focused source coverage for the writer's existing preamble and file-meta guarantees;
its delivery status and evidence scope are recorded separately.

See [Bounded recovery messages](docs/BOUNDED-RECOVERY-MESSAGES.md) for the
delivered change that limits accumulated notice text while retaining
recovery records and uncertainty from omitted details.

Symbolic links, nonregular patient-file entries, unsupported modalities,
duplicate instance UIDs, invalid required UIDs, declared burned-in annotations,
and overlays stop processing. Non-DICOM sidecars, including recognized
AppleDouble companions, are excluded and counted. Malformed DICOM files stop
the batch; not every malformed-stream or resource-exhaustion case is covered.
Common atlas-space workflows are not an approved exception to cross-patient
frame-of-reference checks.

A disk-space preflight estimates required capacity. The pre-publication audit
checks identity, date, private-tag, UN, clear/remove, and UID invariants, including
metadata after Pixel Data. Some policy lists are shared with the cleaner, so the
self-audit is not an independent conformance oracle. Failures and handled
cancellation remove staging; abrupt process death or power loss can leave hidden
staging. The [data-handling policy](docs/DATA-HANDLING.md) is the detailed contract.

## Build the macOS interface from source

The native target is arm64 with macOS 13+. Building requires full Xcode, Apple
Swift 6.4 in Swift 6 language mode, and a local Python 3.12+ environment with the
pinned pydicom dependency. Warnings are treated as errors.
[toolchain.sh](toolchain.sh) uses the selected Xcode installation or
`DEVELOPER_DIR`.

```sh
bash build.sh
```

The result is `build/DICOM Anonymizer 2.0.app`, ad-hoc signed for local
development. The first build downloads the pinned standalone Python archive;
unchanged cached archives reuse their digest-bound acquisition receipt. These
are build-time requirements. The resulting app includes the interpreter,
pydicom, runtime licenses, and dependency notices.

The bundle identifier is `io.github.jdotc1.dicom-anonymizer`. Source contains no
Developer ID certificate, notarization credential, signing key, or custom artwork.
The downloadable app includes the project-selected icon. For a local build with
externally supplied compiled icon resources, set `APP_ICON_RESOURCES` to a folder
containing `Assets.car` and `AppIcon.icns`; the build copies them and sets the icon
plist keys before signing. Intel and other operating systems are not claimed as
native-app targets; the Python engine remains available separately.

## Development and acceptance evidence

Unit tests use synthetic temporary data. The optional native integration test
uses only the example generator and a separate preferences identifier, writing
under `.synthetic/`.

```sh
python -m unittest discover -s tests -v
bash test_drop.sh
```

[Runtime acceptance](docs/RUNTIME-ACCEPTANCE.md),
[error recovery](docs/ERROR-RECOVERY.md), and
[release review](docs/RELEASE-REVIEW.md) distinguish focused checks from reused
engine, self-audit, native processing, runtime, and dependency evidence. Bundled
runtime checks include scan/completion with external Python locations denied and
the missing-runtime error without external fallback. These are recorded checks,
not a claim that every preview reruns all suites or covers all native gestures.

The engine policy remains **2.0-build5**, separately versioned from the app's
release/build number. CI is manual-only, requires explicit acknowledgment, and
has read-only repository permissions. Use the linked records for actual command,
environment, and acceptance scope.

## Contributing, reporting, and license

Use minimal synthetic examples in [issues](https://github.com/jdotc1/dicom-anonymizer/issues)
and pull requests. Do not post patient files, original filenames, identifiers,
or unredacted logs. Follow [CONTRIBUTING.md](CONTRIBUTING.md); security-sensitive
reports use the private reporting route in [SECURITY.md](SECURITY.md).

Project source is [MIT-licensed](LICENSE). Dependencies retain their own terms. Preserve the complete notices in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) when redistributing them.

## Release tooling

Receipt-driven packaging and explicit resumable distribution steps are documented in
[Release automation](docs/RELEASE-AUTOMATION.md). Accepted application verification is reused;
packaging fixtures cover only the new tooling.

## Scan-progress feedback

Initial scan/preflight examined-file and examined-folder feedback is delivered.
It stays inside the existing progress area and remains indeterminate. See
[Scan progress](docs/SCAN-PROGRESS.md) for changed-input evidence and accepted
verification reuse.

## Allocation-aware disk-space estimate

Allocation-aware output-space estimation is delivered. It accounts for metadata
growth, destination allocation, directories and the report while preserving the
existing interface and engine policy. See [Disk-space estimate](docs/SPACE-ESTIMATE.md).
