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

The CLI writes JSON-line events; the complete list of flags, events, fields and
report keys is in the [engine interface reference](../docs/ENGINE-INTERFACE.md). Errors use
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

## Explain mode

`python engine/engine.py --explain FILE` previews what a real run would do to one
file, without printing any dataset value and without writing anything. It uses
the same pinned read and `validate()` as a real run, then runs the engine's own
`clean()` on a deep copy with a throwaway UID map and a fixed UID factory, and
compares the copy with the original. One JSON line is printed: `event: explain`,
an `attributes` list (`path`, dictionary `keyword`, `vr`, `action`) and `counts`.

Actions are `removed`, `cleared`, `pseudonym` (PatientName/PatientID),
`uid_remapped`, `replaced` and `changed`; unchanged attributes are only counted
as `retained`. Nested items use tag paths such as `(0008,1140)[0]/(0008,1155)`;
elements removed with a parent sequence are only counted (`removed_with_parent`).
Private and unknown elements show an empty keyword and are never described by
creator or value. Refusals (unsupported modality, overlays, unreadable file)
print the same fixed `error` event as a real run, with exit code 1.

Explain covers `clean()` only. Fields a real run then sets (pseudonym identity,
de-identification markers, rebuilt file meta, output naming) and the
self-audit are not part of the preview, and the cleaning policy is unchanged.

Rough, caveated synthetic-data timing figures and a manual benchmark script are in
[performance notes](../docs/PERFORMANCE.md); they are not a gate.

**Policy version: 2.0-build5.** App preview/build numbers are separate. Accepted
engine and bundled-runtime evidence, reused checks, and remaining limits are
recorded in [runtime acceptance](../docs/RUNTIME-ACCEPTANCE.md). Later
[interface recovery checks](../docs/ERROR-RECOVERY.md) do not change the engine
policy or constitute a new full engine suite.
