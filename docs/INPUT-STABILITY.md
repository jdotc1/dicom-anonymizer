# Input-stability recovery

Implemented locally on 2026-10-23; not yet packaged or released.

## Behavior

Scanning captures each candidate's device, inode, size and nanosecond modification time before the header/probe reads. The full decoded DICOM read compares that identity immediately before and after reading, and retains the original identity in its scan record. Processing repeats the same two-sided check against that record before validation, cleaning or output writing.

Detected changes, missing files and symlink substitutions use the existing batch-error/retry path: keep input files unchanged and retry. A read failure accompanied by a detected change gets that recovery message; stable read failures and explicit cancellation preserve their existing errors. Processing failures retain the existing owned-staging cleanup and never publish completion. No paths are added to this error message.

The interfaces, metadata policy, exclusions, audit, output layout and publication mechanism are unchanged. This is an ordinary concurrent-change detector, not an atomic filesystem snapshot: same-size edits with restored modification times, mutations between comparisons, later changes to already-read files and newly added files are not comprehensively detected. Excluded non-DICOM files are not admitted as scan records.

## Focused verification

Nine new synthetic test methods per app cover unchanged reads, pre-read changes, edits/replacements/removals/symlinks during reading, failed reads after removal, preservation of stable errors and cancellation, pre-read scan identity, scan rejection before validation, and processing rejection with owned-staging cleanup and no output publication. The mutation test contains four distinct subcases.

Private: all nine passed once. Public: eight passed on the first run; the scan-success fixture incorrectly referenced a private-only helper. That test fixture was corrected and only the failed test was rerun, successfully. Passing tests were not repeated.

Evidence: `/Users/jeff/Developer/Codex/DICOM-Input-Stability-20261023/` (`private-tests.log`, `public-tests.log`, `public-fixture-fix.log`, `integration-receipt.json`). Tests use synthetic files, mocked decoded datasets and `PYTHONDONTWRITEBYTECODE=1`; no accepted app bundle is imported or modified.

## Accepted evidence reused

- Allocation estimates: `DICOM-Space-Estimate-20261023/integration-receipt.json`.
- Native interface and scan-progress acceptance: `DICOM-Scan-Progress-20261023`.
- Existing cancellation/publication/cleanup acceptance: `DICOM-Publication-Recovery-20261023`.
- Shipped package/runtime distribution: `DICOM-Space-Release-Corrected-20261023/delivery-receipt.json` (applies to the already shipped versions only).

No unchanged suites, dependency checks, hashes, signing or notarization checks were repeated. No native sources changed, so no native build was needed. No GUI use or app launch occurred. New source has not been signed, notarized, published or installed.
