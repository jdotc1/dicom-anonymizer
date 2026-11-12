# Canary survey and policy-table lint

Test-only tooling. It changes no engine behavior, policy table or policy version, and it is run by hand
(never from an automatic job). All data is synthetic and in memory.

## Canary survey

`tests/canary_survey.py` plants a unique canary value in every attribute of each class (named identity,
free-text, date, RT-descriptor, UID and retained-by-design attributes; private blocks; an unknown public
tag; curve data; and every text-capable dictionary attribute in groups 3002-3010, 0062, 0064, 0066 and
0070), at three nesting depths. It runs `clean()` once and classifies each canary by comparing the value
that comes back with the value that went in. It also asks `audit_dataset()` whether it would have flagged
the raw canary.

The answer key, `tests/canary_answer_key.py`, is written by hand from the retention contract and does not
import the engine or its tables. The survey emits a deterministic tab-separated survivor table
(`python -B canary_survey.py` from `tests/`): tag, keyword, VR, class, observed action per depth,
whether the audit sees the raw value, and a verdict.

Result with pydicom 3.0.2:

- 77 LO/SH attributes in the surveyed groups survive (75 excluding retired entries), matching the static
  estimate. Two are retained by design (ROI labels); the other 75 are recorded as known gaps. No UC, ST,
  LT, UT, UR, PN, AE, DA, DT or TM canary survives.
- The audit is blind to exactly these survivors, because it checks the same policy lists that `clean()`
  applies. It is not an independent oracle for them.
- One named answer-key attribute also survives (`BeamName`).

The known gaps are listed by tag and keyword only in `tests/canary_known_gaps.py`. They are recorded, not
fixed; whether to remove any is a policy decision. A planted gap in a patched copy of the tables is detected
as a new gap and a named violation.

`tests/canary_fixtures.py` builds minimal RT Plan, RT Dose, RT Image, treatment record, Spatial
Registration, Segmentation, PT, RT Structure Set and CT objects with consistent UID chains.
`tests/test_canary_chains.py` checks that in-batch references follow the remapped targets and that
references to objects outside the batch receive fresh, consistent UIDs.

## Policy-table lint

`tests/test_policy_lint.py` (helpers in `tests/policy_lint.py`) checks that every `REMOVE_KEYS` keyword
resolves, that each numeric tag comment matches the dictionary keyword (or sits in an explicit allowlist),
that no tag is in both numeric tables, that there are no duplicate literal entries, and that the six
dictionary-unknown numeric tags and the redundant `REMOVE_KEYS` entries are exactly the pinned lists. It
also pins `engine/policy/mri-physical-v1.json` to the Python sidecar policy; the Python object stays the
source. Run it once per policy change.
