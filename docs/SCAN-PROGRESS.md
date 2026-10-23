# Initial scan-progress feedback

Status: implemented locally on `codex/scan-progress`; not yet merged, published,
or installed. The existing shipped app remains unchanged by this increment.

The existing progress area shows files and folders examined during the initial
folder check and the scan repeated before processing. Progress remains
indeterminate. There is no percentage, denominator, ETA, or invented total.
The private app uses its existing Lumen loading detail; the public app uses its
existing scan status line and preflight progress panel, without duplicate counts.
No controls, design-system dependencies, deployment targets, or engine policy change.

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

- Eight new focused engine checks per repository: single-walk counts/exclusions,
  monotonic throttling and final snapshot, optional silent caller, empty/invalid
  source handling, CLI/preflight callback wiring, and symlink rejection before
  file probing. DICOM read and policy routines were mocked; temporary fixtures
  contain no real patient data. Evidence is composite: seven passing checks were
  reused while the new symlink-order case ran separately. The first public fixture
  assumed a private helper; that new fixture was corrected for the distinct public
  implementation and its log retained.
- Eleven new model checks per app: indeterminate initial/preflight state, separate
  counts, malformed/regressing updates, cancellation/error/idle suppression,
  completed-scan boundary, new-operation reset, and transition to writing.
- Actual optimized native targets built with Swift 6.4.2/Xcode 27.2/SDK 27.2,
  warnings as errors, arm64; private macOS 14/Lumen 0.56.2 and public macOS 13.
- Live, isolated native model/view fixtures checked the changed progress area at
  700×700 private and 700×655 public content sizes, with five-digit file counts,
  light/dark presentation, preflight, and cancellation priority. These fixtures
  drive synthetic events through the real models/views; they do not constitute a
  new real-DICOM end-to-end scan or a broad UI regression pass.
- Source-only independent review found no blockers. The public live preflight
  review caught duplicate status text; only that presentation was corrected and
  rebuilt, and its changed native state checked again. Accepted model results were
  reused. A menu-automation issue in the public review fixture was bypassed with an
  explicit dark/preflight fixture configuration; a process sample showed the app
  idle in its normal event loop, not a demonstrated application hang.

Accepted engine policy, self-audit, report/publication/storage recovery, runtime,
icon, and unchanged UI/dependency evidence is reused. No accepted suite, corpus,
provenance hash, dependency signature check, signing or notarization was repeated.
No merge/push, GitHub release, or installation was performed for this source increment.
The detailed local integration receipt records source checkpoints and product paths.
