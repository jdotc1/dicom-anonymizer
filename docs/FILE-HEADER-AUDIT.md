# Independent staged-file header audit

Delivered in Preview 32/build 36. This enforces existing file-writing guarantees without changing the
public UI, metadata-cleaning policy, ROI-label retention, sidecar defaults,
report schema or dependencies.

## What is enforced

Before output publication, each staged DICOM is reread. Its header must satisfy:

- The preamble is exactly 128 zero bytes.
- File-meta SOP Class UID and SOP Instance UID match their dataset values.
- File-meta version and implementation identifiers match the defaults generated
  by the pinned writer library, rather than retaining source implementation data.
- File metadata contains only the fields the rebuilt writer emits. Reintroduced
  source/sending/receiving application titles, presentation addresses, private
  information and unknown extra fields are rejected, including empty extra fields.
- An emitted group-length element has UL representation and a nonnegative scalar
  integer value. Its numeric value is not independently recomputed here.

The expected metadata is constructed in a separate FileMetaDataset using the
same library-default mechanism as the existing writer. The audit does not repair
or rewrite staged data. It preserves the declared transfer syntax rather than
requiring one particular encoding. Existing file-meta instance synchronization,
source-UID and dataset-policy checks still apply.

Header validation is part of the staged-file self-audit, separate from
`audit_dataset`'s in-memory metadata-policy checks. This avoids imposing a file
preamble requirement on those dataset-only callers. The writer still cleans and
rebuilds files as before; the new check independently rejects deviations before
the staging directory is published.

## Focused evidence

Seven new methods in `tests/test_file_header_audit.py` cover nonzero preambles,
class mismatches, reintroduced application titles/addresses, altered implementation
identifiers, private information and unknown metadata, valid explicit/implicit
little-endian encodings, and whole-batch refusal/cleanup for three staged faults.
Fixtures are generated, small synthetic examples and removed after each case.

The initial negative run exposed sixteen rejection subcases the old audit accepted.
After the production check was added, all seven methods passed. One directly
affected RTSTRUCT round-trip method also passed under the stricter staged-file
audit. Three progress-only fixtures were updated to isolate the new header-check
boundary alongside their existing policy mocks; only those three modified
selectors ran and passed. No other accepted test was repeated. Existing cleaner/preamble, file-meta
rebuilding, generic metadata, RTSTRUCT linkage, sidecar, native, runtime and
dependency evidence is reused; no native rebuild is needed for this Python change.

The tests corrupt staged files after writing and exercise the real file reader,
audit and batch cleanup. They do not establish complete DICOM IOD conformance,
reference closure, pixel/contour anonymity or resilience to arbitrary parser
attacks. Existing retained-content limitations still apply.

No GUI use, app launch, installation, signing, notarization or publication occurred
during source acceptance. Detailed logs and receipts remain outside the public
repository; no original imaging data or binary fixtures are included.

## Guarded delivery

Preview 32/build 36 packages accepted engine source
`efb02dd47d09f544ca6a2542d2d78c58ef64d742` with the accepted native executable
from `af9ed1b84ca905ed5b69c809b031a705814499f2`. Release source is
`bf5a119e772a166020974d39015df9dca94a1008`. Existing verification was reused;
no functional test or native build was repeated during delivery.

New distribution sanitation, root signature, stapled ticket and Gatekeeper checks
passed. Apple notarization `cb66d4be-01fb-4f66-81fd-3d131bfec65e` was Accepted.
The 29,079,899-byte ZIP was published through the guarded journal without retrying
a GitHub mutation. Prior releases/downloads remain preserved. No GUI use, app
launch or installation occurred.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.32).
