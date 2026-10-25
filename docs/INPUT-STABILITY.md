# Input-stability recovery

Delivered on 2026-10-23: public Preview 15 (app build 19), signed, notarized and published.

## Behavior

Scanning captures each candidate's device, inode, size and nanosecond modification time before the header/probe reads. The full decoded DICOM read compares that identity immediately before and after reading, and retains the original identity in its scan record. Processing repeats the same two-sided check against that record before validation, cleaning or output writing.

Detected changes, missing files and symlink substitutions use the existing batch-error/retry path: keep input files unchanged and retry. A read failure accompanied by a detected change gets that recovery message; stable read failures and explicit cancellation preserve their existing errors. Processing failures retain the existing owned-staging cleanup and never publish completion. No paths are added to this error message.

The interfaces, metadata policy, exclusions, audit, output layout and publication mechanism are unchanged. This is an ordinary concurrent-change detector, not an atomic filesystem snapshot: same-size edits with restored modification times, mutations between comparisons, later changes to already-read files and newly added files are not comprehensively detected. Excluded non-DICOM files are not admitted as scan records.

## Focused verification

Nine new synthetic test methods cover unchanged reads, pre-read changes, edits/replacements/removals/symlinks during reading, failed reads after removal, preservation of stable errors and cancellation, pre-read scan identity, scan rejection before validation, and processing rejection with owned-staging cleanup and no output publication. The mutation test contains four distinct subcases.

Eight checks passed initially. A scan-success fixture needed correction for the current implementation; only that failed case was repeated and passed. Previously passing checks were reused.

Detailed verification records are retained outside the repository. Tests use synthetic files and mocked decoded datasets; no accepted app bundle is imported or modified.

## Accepted evidence reused

- Accepted allocation-estimate checks.
- Accepted native interface and scan-progress checks.
- Accepted cancellation/publication/cleanup checks.
- Prior shipped package/runtime qualification, scoped to the original artifacts.

No unchanged suites, dependency checks, hashes, signing or notarization checks were repeated. No native sources changed, so no native build was needed. No GUI use or app launch occurred. New package root signature, Apple notarization (b0807bd6-bd00-4f1f-b479-d9a89b363e30), stapling, ticket validation and Gatekeeper assessment passed once for this changed assembly. No app was launched or installed. The public update is Preview 15.

## Distribution provenance

Engine source: `8f536c93a7fa840d8f79cc909b17428020fbb2c0`. Reused native source: `b28a3df90d4cd762bc71644451e7df210f0aa0fc`. Release source: `8f536c93a7fa840d8f79cc909b17428020fbb2c0`. Only the new assembly/distribution outputs received fresh checks; unchanged nested signatures and dependencies were reused.

Release: https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.15
