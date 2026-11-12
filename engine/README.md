# Bulk metadata engine

The Python engine processes numeric patient-folder batches: it pseudonymizes
selected metadata, remaps patient-specific references, audits staged output, and
atomically publishes a new batch. Source files remain read-only.

Use **Python 3.10+ with pydicom 3.0.2**. From an installed checkout, try the
synthetic example described in the [root README](../README.md#try-it-with-synthetic-data):

```sh
python engine/engine.py --source .synthetic/input --scan
python engine/engine.py --source .synthetic/input --destination .synthetic/output
```

The destination must be new. Exact numeric folder names, including leading
zeros, become PatientName and PatientID. Read the [data-handling policy](../docs/DATA-HANDLING.md)
for supported MR/CT/RTSTRUCT scope, retained pixels/text/demographics, refusal
conditions, and pseudonymization limits. No patient data or Python runtime is
bundled in the source repository; the separately released macOS app bundles its
runtime.

JSON-line event names are `scan`, `progress`, `complete`, and `error`. Errors use
fixed text to avoid exposing source identity, and library diagnostic messages
are suppressed. Completed output includes `anonymization-report.json` with
aggregate counts and self-audit status.

Preview 34/build 38 adds structured [audit coverage](../docs/AUDIT-COVERAGE.md)
to completed reports, including separate DICOM/sidecar statuses and retained-content
limitations. Existing report fields remain available.

Preview 35/build 39 adds [staging and journal protection](../docs/STAGING-JOURNAL-PROTECTION.md):
strict default-mode publication inventories and conservative recovery-record
updates. It does not enable sidecar processing or change the metadata policy.

Preview 36/build 40 adds [descriptor-pinned input reads](../docs/DESCRIPTOR-READS.md):
each patient-file read in scanning and processing uses one open descriptor, and a
path replaced after the regular-file check is rejected with the existing
input-changed message. Metadata-only changes are still accepted, and the metadata
policy is unchanged.

## Verifying a published output folder

```sh
python engine/engine.py --verify-output path/to/output
```

This read-only mode needs no source. It re-runs the engine's own file-header and
dataset audit over every output DICOM file (with the patient taken from each
top-level folder), checks that the tree has exactly the engine layout and agrees
with `anonymization-report.json` (patient, series and file counts, policy
version, passed self-audit), and checks that every RTSTRUCT reference resolves to
an instance in the same patient folder. It also rejects duplicate instance UIDs
and patient frames shared across folders. Nothing under the folder is written.

Events are the usual JSON lines (`scan`, `audit_progress`, `error` with fixed
text containing no path or value) plus one terminal `verify_complete` event with
the audited counts and a `tree_sha256` digest of the report and every DICOM file,
which can be recorded and compared later. It never emits `complete`. The terminal
event always states `source_uid_check: not_performed`: leaked source UIDs can
only be found with the source. It is not an independent conformance check, since
it reuses the engine's own audit, and the report holds no per-file digests, so
it cannot detect an edit that stays audit-clean unless the `tree_sha256` from an
earlier run is compared. Closure is strict: a tree whose RTSTRUCT referenced
images that were not in the source batch fails. Trees with JSON sidecar output
are refused. `--verify-output` cannot be combined with `--source`.

**Policy version: 2.0-build5.** App preview/build numbers are separate. Accepted
engine and bundled-runtime evidence, reused checks, and remaining limits are
recorded in [runtime acceptance](../docs/RUNTIME-ACCEPTANCE.md). Later
[interface recovery checks](../docs/ERROR-RECOVERY.md) do not change the engine
policy or constitute a new full engine suite.
