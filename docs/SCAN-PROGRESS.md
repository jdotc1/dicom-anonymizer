# Initial scan-progress feedback

## Event contract

`scan(source, progress=None)` accepts an optional event callback. Existing silent
callers remain supported. The CLI scan and processing preflight use the existing
JSON event stream:

```json
{"event":"scan_progress","files_examined":12345,"folders_examined":456}
```

Counts describe the single existing traversal, not accepted DICOM files or written
output. The valid batch root counts once; each directory entered by the existing
walk adds one. Files encountered add one before exclusion/read checks, including
excluded metadata and sidecars. Unsupported symlink directories are not entered;
root symlinks are rejected before any file-target probe. No additional walk,
DICOM read, filename disclosure, filter change, or policy validation is introduced.

The first and last traversal snapshots are forced. Intermediate snapshots are
throttled by a monotonic clock to at most one per 0.1 seconds. This is checkpoint
feedback, not a heartbeat: a slow single-file read or directory enumeration can
leave counts unchanged while the spinner continues. A final count snapshot does
not grant readiness; the existing completed-scan event and successful process
exit still determine readiness and accepted DICOM totals.

Both models accept only whole nonnegative counter pairs in the existing numeric
decoder's bounds. Both counters must be monotonic; malformed or regressing pairs
are ignored atomically. Events are ignored after cancellation, error, completed
scan, or process exit. New operations reset the counters. Processing preflight
suppresses stale writing fractions until the completed scan restores the existing
writing/audit/finalization flow. Examined counts never overwrite accepted totals.

## Focused evidence and reuse

Accepted engine policy, self-audit, report/publication/storage recovery, runtime,
icon, and unchanged UI/dependency evidence is reused. No accepted suite, corpus,
provenance hash, dependency signature check, signing or notarization was repeated.
No merge/push, GitHub release, or installation was performed for this source increment.
The detailed local integration receipt records source checkpoints and product paths.
