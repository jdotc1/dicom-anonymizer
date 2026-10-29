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

**Policy version: 2.0-build5.** App preview/build numbers are separate. Accepted
engine and bundled-runtime evidence, reused checks, and remaining limits are
recorded in [runtime acceptance](../docs/RUNTIME-ACCEPTANCE.md). Later
[interface recovery checks](../docs/ERROR-RECOVERY.md) do not change the engine
policy or constitute a new full engine suite.
