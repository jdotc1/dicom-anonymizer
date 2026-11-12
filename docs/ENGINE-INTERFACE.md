# Engine interface reference

This page describes the command-line interface of `engine/engine.py`: its flags,
the JSON-line events written to standard output, and the keys of
`anonymization-report.json`. The facts here were confirmed from a single run of
the [synthetic example](../README.md#try-it-with-synthetic-data), plus one run
with a synthetic JSON sidecar and one run against an existing destination. A
conformance test (`tests/test_engine_interface.py`) fails if an event name or
report key is added or removed in the engine without this page changing.

## Compatibility

Consumers must ignore event names, event fields and report keys they do not
recognize. Existing documented names and fields are kept within a policy version,
but this page is a description of current behavior, not a stability guarantee
beyond that sentence; the maintainer decides any wider compatibility promise.

## Flags

| Flag | Meaning |
| --- | --- |
| `--source PATH` | Required except with `--verify-output`. Folder of numeric patient folders. Read-only. |
| `--scan` | Required unless `--destination` is given (mutually exclusive). Reports counts and writes nothing. |
| `--destination PATH` | Required unless `--scan` is given. Must not exist; the parent must exist. |
| `--verify-output DIR` | Read-only, source-free re-audit of a published output folder; mutually exclusive with `--scan`, `--destination`, `--source`, `--journal` and `--clean-json-sidecars`. Ends with `verify_complete`, never `complete`. Not an independent conformance check. |
| `--journal PATH` | Optional private recovery record (mode 0600). Never copied into output or reports. |
| `--clean-json-sidecars` | Optional. Also writes cleaned MRI JSON sidecar copies (policy `mri-physical-v1`). |

Exit status is 0 on success and 1 after an `error` event.

`--explain FILE` is a separate read-only mode handled before argument parsing: it takes one file path, prints a single value-free `explain` JSON line (a per-attribute action list and counts) and writes nothing. It is described in the [engine guide](../engine/README.md#explain-mode).

## Output format

Standard output carries one JSON object per line. Every object has an `event`
string. Nothing else is written to standard output; library diagnostics are
suppressed. Counters never decrease within one event name during a run.

## Events

Fields marked optional appear only in the stated case.

| Event | Fields |
| --- | --- |
| `scan_progress` | `files_examined`, `folders_examined`. Traversal counts, including excluded files. Throttled; first and last are always sent. |
| `sidecar_scan_progress` | `files_examined`, `folders_examined`. Only with `--clean-json-sidecars`. |
| `scan` | `patients` (list of `id`, `files`, `series`), `total_files`, `excluded_files`; `sidecar_files` only with `--clean-json-sidecars`. Terminal event of `--scan`. |
| `progress` | `patient_id`, `processed`, `total_files`. Sent every 10 files and at the end. |
| `sidecar_progress` | `processed`, `total_files`. Only with `--clean-json-sidecars`. |
| `audit_progress` | `audited_files`, `total_files`. First event has `audited_files` 0. |
| `sidecar_audit_progress` | `audited_files`, `total_files`. Only with `--clean-json-sidecars`. |
| `phase` | `name`. Currently only `finalizing`, sent before the report is written and output published. |
| `complete` | `processed`, `total_files`, `patients`, `excluded_files`, `audited_files`; `sidecar_files`, `sidecar_audited_files` only with `--clean-json-sidecars`. |
| `error` | `message`, `cancelled`, `cleanup_failed`; optional `staging_path` (cleanup failed), `output_published` (true if output was published anyway), `output_issue` (`space`, `permissions`, `unavailable`, `conflict` or `unknown`), and for `space` only `required_bytes` and `available_bytes`. |

Ordering and termination: a `--scan` run ends with exactly one `scan` event
(unless it ends with `error`). A processing run emits `scan` first, then
`progress`, optional `sidecar_progress`, `audit_progress`, optional
`sidecar_audit_progress` and `phase`, and ends with exactly one of `complete` or
`error`. After `error` no `complete` follows. Progress events may be interleaved
with earlier phases only as listed here.

Error text is fixed per condition and contains no source or patient identity,
path from the input, or library diagnostic message. `staging_path` is a local
output-side location only.

## Report keys

`anonymization-report.json` in the published folder has these top-level keys.

| Key | Meaning |
| --- | --- |
| `policy` | Engine policy version string. |
| `software` | `pydicom` and `python` versions. |
| `patients` | Per-patient aggregate counts. |
| `patient_count` | Number of patients. |
| `total_files` | Supported DICOM files processed. |
| `excluded_files` | Files not processed. |
| `self_audit` | Staged-output audit summary: `result`, `files_audited`, `checks`. |
| `audit_coverage` | Structured coverage, `schema_version` 1; see [audit coverage](AUDIT-COVERAGE.md). Keys: `schema_version`, `dicom`, `json_sidecars`, `retained_content`, `not_assessed`. |
| `json_sidecars` | Only with `--clean-json-sidecars`. Value-free aggregate sidecar summary. |

See also [data handling](DATA-HANDLING.md) for policy scope and the
[engine guide](../engine/README.md).
