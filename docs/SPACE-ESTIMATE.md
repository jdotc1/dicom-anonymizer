# Allocation-aware disk-space estimate

Status: merged into `main` with history preserved and delivered on 2026-10-23.

The receipt-driven workflow delivered public Preview 14/app build 18 with accepted engine-source `80caae5` and reused native-source `b28a3df`. Release source: `e2f95de`. Apple accepted notarization `92ca3f7b-0e55-46b6-93f2-c3fceeed405e`; the new root signature, stapled ticket and Gatekeeper assessment passed once. Accepted estimate evidence (24 new checks and four affected existing checks per repository) and earlier unchanged policy, self-audit, UI/build, runtime, icon and nested-signature receipts were reused. Five new packaging fixtures per app profile passed for distinct native/engine provenance and vendor cache exclusion; source-only review found no blockers. No accepted test suite, native build, provenance hash or dependency-signature check was repeated. The standalone arm64 ZIP was published and its HTTPS delivery returned HTTP 200. The deployment target remains macOS 13, with bundled Python. This increment changes the output-capacity estimate,
not the metadata policy, supported inputs, writer, audit, report schema, recovery
interface, or native view/model code.

## Calculation

The former check used 110% of aggregate source sizes plus a 32 MiB reserve. The
new estimate adds costs at the level where they arise, without charging ordinary
pixel payloads a flat 10% growth allowance:

| Component | Budget |
|---|---|
| Encoded file basis | Existing source logical size from its accepted scan fingerprint |
| UID growth | Positive growth to 64 bytes per UI value, recursively, with separators and whole-field even padding; preserved/removed values conservatively included |
| Existing string replacements | Positive growth of nested PatientName/PatientID to the numeric folder identifier and StructureSetLabel to Structures; original character count is a conservative encoded-byte lower bound |
| Other per-file metadata | 4 KiB for rebuilt file metadata, preamble, newly added root attributes and remaining uncertainty |
| File allocation | Each file budget rounded up separately to the destination allocation unit |
| Output directories | One allocation unit each for staging root, patients and patient-specific series, plus 256 bytes per directory entry rounded to an allocation unit |
| Report | 64 KiB plus 512 bytes per patient, rounded to an allocation unit |
| Safety reserve | Existing 32 MiB retained |

The destination's `statvfs.f_frsize` supplies allocation granularity, falling back
to `f_bsize`, then 4 KiB if geometry is unavailable or invalid. This models allocation
cost, not exact physical storage. The existing disk-usage lookup still supplies
available bytes and retains its destination-error classification.

Deflated or unknown transfer syntax retains the former 10% source-size cushion,
then adds growth/metadata costs. Deflated recompression is inherently uncertain;
this remains a heuristic, not a size bound. Legacy records without scan estimate
metadata also use the conservative percentage-plus-metadata fallback. All rounding
uses integer arithmetic, including sizes above floating-point integer precision.
No apparent source shrinkage is subtracted.

The estimator observes the dataset already decoded during the existing scan. It
performs no extra filesystem walk, input read, pixel decoding, UID generation,
trial cleaning, serialization, or writing. Only integer estimate metadata is kept
on each internal Record. Initial scan events and the report schema are unchanged.

## Behavior and limits

Large ordinary image files avoid a blanket percentage charge on unchanged pixel
payload. Many tiny files account for per-file destination allocation, while patient
and series layout contributes explicit directory/report costs. UID-heavy or deeply
nested metadata receives a growth allowance beyond the fixed per-file reserve.

The existing shortage message still shows estimated need and available capacity,
and still states that the estimate is not a guarantee. Free space can change;
quotas, snapshots, compression, directory implementation details, malformed inputs,
and output encoding can defeat a prediction. Normal destination-write recovery and
exclusive publication remain in place. The estimate does not certify a batch fits,
change engine policy, or establish clinical/conformance acceptance.

## Changed-input evidence

Each repository has 24 new focused checks: 23 estimate/encoding cases and one new
scanner-to-estimator association case. Four existing affected checks were updated:
the obsolete aggregate-formula expectation and three scan fixtures whose decoded
dataset/fingerprint stubs needed the new estimate inputs. These 28 distinct checks
passed per repository as composite evidence. Passing unchanged cases were reused;
after review-driven nested-string accounting, only the new regressions and the two
new estimator cases exercising that changed branch ran again.

Coverage includes large payloads, nested/multivalue UIDs and padding, nested string
replacement growth, non-ASCII character lower bounds, no dataset mutation/trial
writes/UID generation, integer precision, geometry fallback, tiny-file allocation,
patient/series directories, report/reserve budgets, legacy/invalid metadata fallback,
exact-availability and shortage boundaries, and destination-error classification.
A bounded new synthetic encoding fixture covered implicit VR, explicit VR and
deflated transfer syntax with nested references and a 1 MiB synthetic byte payload.
The estimate covered those encoded examples; this is not corpus calibration or a
general upper-bound proof. DICOM metadata-policy processing and audit were not run.

A source-only independent review found recursive string-growth accounting missing
from the first draft; the fix and focused regressions passed, and final review
found no further blocker. Source and fixtures preserve the two engines' distinct
scan policies. No accepted policy/audit suite, real-data processing, native build,
UI test, provenance hash, dependency/signature check, signing or notarization was
repeated. Native sources did not change, so their accepted build and presentation
evidence remains reused. At the initial source-only checkpoint, no push, merge, release or installation had been performed. The subsequent authorized delivery is recorded above.

## Packaging correction history

Preliminary private build 18/public Preview 13 included vendor bytecode caches generated by local test imports. Preview 13's asset was withdrawn before final handoff; its tag and release record remain. Corrected private build 19/public Preview 14 exclude vendor import caches while preserving the separately accepted runtime resources. They received new signatures/notarization because package contents changed. The new exclusion fixture passed for each app profile; accepted engine, native and dependency checks were reused. Build 17 remains available for rollback.
