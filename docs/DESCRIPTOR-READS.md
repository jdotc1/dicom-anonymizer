# Descriptor-pinned input reads

Local source, 2026-11-12. Not yet packaged, signed, notarized or published.

## Behavior

Every patient-file read in scanning and processing now goes through one pinned
descriptor. The engine checks with `lstat` that the path is a regular file, then
opens it with `O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC`. It compares the opened file's
device, inode, mode, size and nanosecond modification and change times against
that pre-open identity, and against the scan record's signature when one exists.
The DICOM header, the extensionless-file probe, the AppleDouble resource check
and the full decode all read from that descriptor. Before the descriptor closes,
the engine checks both the descriptor and the path once more.

This closes three gaps that remained after [input-stability recovery](INPUT-STABILITY.md):

- **Path substitution between the type check and the read.** Earlier reads
  reopened the path by name, so a file swapped in after the regular-file check
  was read in its place. A replaced path now fails the identity comparison.
- **Blocking on a substituted FIFO or device.** `O_NONBLOCK` keeps the open from
  waiting for a writer, and the identity comparison then rejects the special file.
  The header, probe, resource and decode reads each have a FIFO regression test
  with a two-second timeout.
- **Change-time-only edits during a read.** An in-place rewrite that restores
  the size and modification time while a file is open still changes `st_ctime`,
  which is now compared across that read. The scan record's signature keeps its
  original four fields (no change time), so an edit of this kind made between
  scanning and processing is still outside detection.

Detected changes keep the existing recovery path and message ("The input changed
during scanning or processing. Keep input files unchanged and retry."). Explicit
cancellation keeps its own error. Lazy DICOM elements are decoded before the
descriptor closes, and `filename` keeps the original path, so downstream
reporting is unchanged.

MRI JSON sidecar reads (`sidecar_deid._read_regular_nofollow`) are now
non-blocking too. They also compare mode and change time, and recheck the path
after the read, so a sidecar replaced by rename during reading is rejected. The
existing one-byte overflow contract for the size limit is unchanged.

The interfaces, metadata policy, exclusions, audit, output layout, error text and
publication mechanism are unchanged. Like input-stability recovery, this detects
ordinary concurrent changes. It is not an atomic filesystem snapshot: a writer
holding the same inode can still change bytes between comparisons without
altering the recorded times, which some filesystems allow.

## Release-preflight option rename

`scripts/release_preflight.py` accepts the hypothetical candidate path only as
`--candidate-output`, with no `--output` alias, so a supervising storage guard
cannot mistake the read-only planner for a write. See
[Release preflight](RELEASE-PREFLIGHT.md).

## Focused verification (2026-11-12)

- `tests/test_descriptor_reads.py`: 12 new synthetic methods, all passed on the
  first run. They cover replacement during decode, in-place change after decode,
  FIFO substitution at decode/probe/header/resource reads, a non-blocking sidecar
  FIFO open, sidecar replacement during a read, destination errno preservation,
  decoded payload and filename retention for Part 10 and headerless files, the
  sidecar size limit, and a replaced staged file blocking publication with
  staging cleanup.
- `tests/test_release_preflight.py`: 17 methods passed, including the new
  rejection of `--output`.
- Engine and sidecar suites that load `engine.py` or `sidecar_deid.py` (21
  modules, 253 methods) were run because their code under test changed. The
  pinned read broke four scan-progress methods: their fixture faked the file
  fingerprint, and the new identity check correctly rejected it. The fixture now
  uses the real fingerprint. That exposed a fixture defect that predates this
  change: two mocked datasets lacked `Modality`, which folder-conflict reporting
  reads. Both fixtures were corrected, and the scan-progress and input-stability
  modules (18 methods) then passed.
- Ten other methods in older modules failed. They test output-side messages and
  event streams, not the input-read path changed here, so these failures came
  before this change. They expected superseded wording or events: "conflicting"
  and "same study occurs in multiple patient folders" (replaced by the detailed
  folder-conflict messages), policy `2.0-build4` (now `2.0-build5`), a first CLI
  event of `scan` (now preceded by `scan_progress`), single-object CLI JSON (now
  multi-line progress), "space" when disk-usage inspection fails, and a raw
  `OSError` from a failed write (both now classified as output-location errors).
  Each new behavior was confirmed as documented in `STORAGE-RECOVERY.md`,
  `SCAN-PROGRESS.md` or the README. The tests were updated to match it, keeping
  their no-path-leak, no-output and staging-cleanup assertions. Two of them now
  also assert that no path leaks from output-location errors, and
  `test_batch_output_drops_file_meta_titles_and_reports_build4` was renamed
  `..._reports_build5`. Only those ten methods were re-run, and all pass.

No native sources changed, so no native build was needed. No GUI use, app launch,
packaging, signing or installation occurred. Tests used synthetic files only.
