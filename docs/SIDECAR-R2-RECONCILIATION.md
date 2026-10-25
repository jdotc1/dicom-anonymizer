# Revised sidecar integration — 2026-10-24

Status: delivered as public Preview 17 (version 2.0.0, build 21). The source-acceptance record below describes the preceding local development stage.

The revised supplied portable design was compared with the unified public source at `3ec5c1e`. Its 108-test final portable receipt is reused supplied evidence, not a fresh local run. No historical patcher or manifest/hash gate was rerun. The patcher targets an older baseline and was not used or bypassed.

## Already incorporated in Preview 16

- Exact serialized output sizes computed during sidecar preflight, without another estimation read.
- Allocation-aware file/directory/entry/report budgeting; the current explicit sidecar estimator is retained instead of adding the revised generic record adapter.
- Opt-in-only import, discovery, report extension, inventory seal and completion counts; existing DICOM policy and disabled behavior retained.
- Destination classification for cleaning/writing through the existing output-operation callback.
- Cancellation during discovery, cleaning, audit and sealing, mandatory sidecar audit, safe generated paths and privacy-minimized events/reports.

## Additional r2 improvements incorporated locally

- Aggregate cleaned-output byte limit is enforced during discovery, before staging or any DICOM writing; the existing per-file limit remains.
- Typed `SidecarDestinationError` retains the underlying OSError for the host's existing destination classifier. Audit reads and final-seal reads/lstat/walk errors now use the same space/permissions/unavailable recovery as writes.
- Bounded reads convert read/fstat failures to safe sidecar messages; close failures cannot mask the active error.
- Cancellation checkpoints include empty discovery and individual inventory entries, plus preflight parse/size boundaries.

## Current protections retained over the supplied revision

The revised module omits some protections already added locally. Discovery still uses a fail-closed `os.walk` error callback. Final sealing still rejects a symlink/non-directory staging root, including zero-sidecar batches. Existing output callback compatibility remains. Audit ordering stays DICOM writing → sidecar cleaning → DICOM audit → sidecar audit → finalization, matching the accepted native model. No Swift/UI or metadata retention changes were made.

## Focused evidence

Seven new r2 delta checks passed: aggregate preflight rejection before staging; output-location recovery for audit read, seal lstat and seal walk I/O errors; pending cancellation with empty discovery; cancellation within a single inventory directory; and write-error classification through the retained callback.

The first `unittest discover` command also discovered the imported existing 17-case integration class. Its result was 23 passes and one failed assertion expecting the old generic seal message. The test import was changed to a module alias to prevent that additional discovery. The affected seal fixture now supplies an actual permissions errno and asserts the permissions classification, safe message and no publication; only that failed case was rerun and passed. All seven new passing cases were reused without rerun. The full 108-test portable suite and other accepted policy/native/runtime suites were not run.

Logs and reconciliation records are retained outside the repository. Existing native/model, consolidated folder recovery, bundled runtime and release receipts remain input-specific reused evidence. No native rebuild was needed because native sources did not change. No GUI use, app launch, push, merge, signing, notarization, release or installation occurred. Live sidecar GUI acceptance remains pending.

## Preview 17 distribution

Delivered on 2026-10-24 from engine/release source `2ae7e69a131eb51f9f4b5692cc352f430f006fd5` with accepted native source `80a8a8d1e820e64c6aab322894f61213a7adf893` reused. Developer ID signature, Apple Accepted notarization `3a5308be-cff7-4316-a945-64beebfda20a`, stapled ticket and Gatekeeper assessment passed once for the new package. Only changed assembly/distribution outputs received fresh checks. No functional tests or native build were repeated. No GUI use, native app launch or installation occurred; live GUI acceptance remains pending.

Release: https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.17
