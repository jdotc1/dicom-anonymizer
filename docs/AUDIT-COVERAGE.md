# Audit coverage in batch reports

Delivered in Preview 34/build 38. This increment adds reporting only: the public
interface, supported inputs, metadata policy, audit enforcement and default-off
JSON-sidecar setting remain unchanged.

## Report contract

Completed batches include an additive `audit_coverage` object in
`anonymization-report.json`. Its `schema_version` is `1`. Existing top-level
fields, the `self_audit` result/counts and the optional `json_sidecars` section
remain available. Consumers should tolerate unknown report keys. This is a scope
description, not a certification or a per-file inventory of retained attributes.

| Field | Meaning |
| --- | --- |
| `dicom.result` | `passed` after the existing staged-file audit returns; `skipped` when DICOM auditing was explicitly disabled. |
| `dicom.files_written` / `files_audited` | Separate output and audit counts. A skipped audit has zero audited files. |
| `dicom.checks` | The existing descriptive check list, now also naming the already-enforced zeroed preamble, rebuilt file metadata and present StructureSetLabel normalization. Empty when skipped. These descriptions are human-readable, not stable check identifiers. |
| `json_sidecars.enabled` | Whether optional JSON-sidecar processing was requested for this batch. |
| `json_sidecars.result` | `not_requested` when disabled; `passed` after the existing enabled sidecar audit returns, including a zero-file pass. |
| `json_sidecars.files_written` / `files_audited` | Separate sidecar counts; zero does not by itself imply that sidecar processing was disabled. |
| `retained_content` | Numeric folder-identifier retention and examples of retained attributes and payloads requiring review. No original values are copied into this section. |
| `not_assessed` | Named limitations for pixel/contour identity, retained text, DICOM conformance, reference closure, other companion formats and external linkability. |

The DICOM `audit=False` option does not disable the independently required audit
of enabled sidecars. Their statuses are therefore reported separately. A failed
audit continues to block publication; this addition does not create a failure
report or allow a partially audited batch to publish through a new path.

The check descriptions cover actual enforced invariants. They do not claim full
DICOM IOD validation, complete reference closure, geometric alignment, independent
recalculation of encoded file-meta group length, removal of image text/faces, or
anonymity of retained ROI labels and contour geometry. Existing policy and
sidecar-specific report sections remain the authority for their detailed rules.

## Focused evidence

Five new synthetic report-boundary tests exercise the real engine and completed
JSON output: default-off sidecars, explicitly skipped DICOM auditing, enabled
sidecars, enabled sidecars with no matching files, and enabled sidecars while
DICOM auditing is skipped. Assertions cover truthful counts/status, retained
limitations, compatibility of existing report fields, and absence of source
paths, filenames and synthetic source identities from the report.

All five first failed because coverage was absent, then passed with the additive
report. Temporary generated inputs and outputs are removed after each case.
Accepted cleaner, independent-audit, sidecar, recovery, worker, native, runtime,
dependency and icon evidence is reused. No native source changed, so no native
build was repeated. Headless engine coverage does not establish live interface
acceptance. Source acceptance included no GUI use, app launch, installation or
publication; authorized delivery followed separately below.

## Guarded delivery

Preview 34/build 38 reuses the five accepted report-boundary tests and the
unchanged optimized native executable. No functional test or native build was
repeated during delivery. Accepted engine source is
`56c488f8aedef11f71c4cde179f531089443ec64`; native source is
`5ebaa55481308ec33169e0420fe10a8c31d9f8e4`; release source is
`2b2ab9003ed3ae0af5d04e78477793188b5d6658`.

New source/documentation, package and release-text sanitation boundaries passed,
with accepted receipts reused where applicable. The new root signature, stapled
ticket and Gatekeeper checks passed. Apple notarization
`5ed1f52d-2d8b-424e-a8db-ed6e90b8c964` was Accepted. The ZIP is 29,080,672 bytes.
Journaled publication completed without retrying a GitHub mutation; delivery
returned HTTP 200 to a HEAD request without redownloading the binary.
Earlier releases and signed downloads remain preserved. No GUI use, app launch
or installation occurred.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.34).
