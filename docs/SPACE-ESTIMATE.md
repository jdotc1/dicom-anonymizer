# Allocation-aware disk-space estimate

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
evidence remains reused. No push, merge, release or installation was performed.
