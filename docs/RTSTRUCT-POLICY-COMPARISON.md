# RTSTRUCT policy comparison and synthetic coverage

This is a source-level comparison and a focused test-only increment. The current
download remains Preview 30/build 34. No UI, engine, policy, report schema or
runtime dependency changes are included. No external anonymizer code or imaging
fixtures are vendored.

The comparison uses the app's policy at `e4755ed` and the following pinned
Stanford repository revision, `33b761fe1dfc4b415de7207b0a8ad2869706fe14`:

- [Anonymizer rules](https://github.com/susom/mirc-ctp/blob/33b761fe1dfc4b415de7207b0a8ad2869706fe14/scripts/stanford-anonymizer.script).
- [Input filter](https://github.com/susom/mirc-ctp/blob/33b761fe1dfc4b415de7207b0a8ad2869706fe14/scripts/stanford-filter.script).
- [Example launcher](https://github.com/susom/mirc-ctp/blob/33b761fe1dfc4b415de7207b0a8ad2869706fe14/anonymize.sh).
- [Scope and limitations](https://github.com/susom/mirc-ctp/blob/33b761fe1dfc4b415de7207b0a8ad2869706fe14/README.md).

The external scripts were read, not executed. An absent explicit rule below is
a static observation, not proof of what the external library would emit. The
external repository describes its scripts as incomplete testing samples without
a PHI-free guarantee. Its default filter rejects RTSTRUCT; anonymizer rules alone
do not establish that the complete example pipeline supports that modality.

## Comparison

| Area or attributes | Current app policy | Pinned Stanford configuration | Disposition |
| --- | --- | --- | --- |
| RTSTRUCT input | Supported with MR and CT. | Default unsupported-modality block includes RTSTRUCT. | Different scope; preserve app support. |
| PatientName / PatientID | Exact numeric patient-folder pseudonym, including leading zeros; recursively replaced. | Supplied PATIENTID parameter. | Preserve folder assignment. |
| Study/series/instance and nested reference UIDs | Consistent non-class UID remapping within the batch. | Explicit hash-based UID rules. | Similar goal; retain app mapping. |
| Referenced/Related Frame of Reference UID, including (3006,0024)/(3006,00C2) | Recursively remapped. | Explicit hash rules. | Add RT frame-relationship coverage. |
| SOP class identifiers | Preserved as structural identifiers. | Explicit keep rules. | Existing linkage evidence reused. |
| StructureSetDate / StructureSetTime; ROI DateTime / ROI Observation DateTime | DA/DT/TM values emptied recursively. | Structure-set date uses DATEINC; general date rules use JITTER. | Intentional policy difference; do not import date shifting. |
| StructureSetLabel | Replaced with `Structures`. | No explicit RT-specific rule found. | Add normal-path coverage; audit limitation below. |
| StructureSetName / StructureSetDescription | Cleared. | No explicit corresponding RT rules found. | Add actual RT sequence-context coverage. |
| ROIDescription / ROIGenerationDescription / ROIObservationDescription | Cleared. | No explicit corresponding RT rules found. | Add multi-item and audit coverage. |
| ROIInterpreter and other PN values | Emptied recursively, except folder PatientName. | No explicit ROIInterpreter rule found. | Add actual observations-item coverage. |
| ROICreatorSequence (3006,004D) / ROIInterpreterSequence (3006,004E) | Entire sequences removed through numeric policy tags. | No explicit corresponding rules found. | Add numeric-tag round trip and reinjection coverage. |
| ROIName / ROIObservationLabel | Intentionally retained, including identifier-like text. | No explicit corresponding RT rules found. | Record retained-text risk, not a removal guarantee. |
| Contours, ROI numbering, display colors, transformation matrices | Retained; numerical reference numbers remain unchanged. | No RT geometry-specific handling established. | Add multi-ROI polygon and transform coverage. |
| Private elements | Recursively removed. | Private-group removal enabled. | Existing generic evidence reused. |
| Overlays | Input rejected. | Overlay removal enabled. | Preserve refusal behavior. |

The launcher supplies JITTER while the RT date rule refers to DATEINC. This
parameter distinction needs separate examination before any reuse; no conclusion
about its executed result is claimed here. Unchecked-element removal is disabled
in the compared script, so a missing RT-specific entry is not evidence of an
explicit removal rule.

## Standards context and limits

[DICOM PS3.15 Annex E](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_E.html)
requires consistent replacement of related identifiers and application of the
selected protections within sequence items. Its confidentiality guidance also
distinguishes attribute treatment from de-identification of the complete object.
This comparison is not a complete Annex E action-table audit or a conformance
claim. The app's retained text, demographics, pixels and anatomy remain subject
to review; the external profile name does not certify this app.

UID consistency does not establish that every referenced image was included,
that every ROI reference is valid, or that contours align anatomically. The app
does not perform complete RTSTRUCT IOD, reference-closure or geometric validation.
The new polygon and matrix cases check preservation, not anatomical correctness.

### Independent-audit limitation

The cleaner normalizes StructureSetLabel to `Structures`, but the independent
self-audit does not currently require that exact value. A synthetic arbitrary
SH label reinserted after cleaning passes unless another existing audit rule
rejects it. The new characterization case records this limitation explicitly.
It does not represent the label as safe, and this increment does not change
production enforcement. A focused follow-up can enforce the already-defined
normalization invariant without deciding a new ROI-label policy.

This differs from ROIName and ROIObservationLabel: their retention is an explicit
policy choice. Synthetic identifier-like labels survive the new round-trip test
and the report still states the retention limitation. Successful self-audit is
not general text-identifier detection.

## New and reused evidence

`tests/test_rtstruct_policy.py` adds eight new methods:

1. RT-specific text and date/time handling across two ROI and observation items.
2. Identifier-like and Unicode label retention, with the report's limitation retained.
3. Removal of both numeric creator/interpreter sequences and all their items.
4. Two four-point closed polygons, ROI/observation reference numbers and display colors preserved through file output.
5. Consistent related-frame UID remapping with an unchanged retired transformation matrix.
6. Four reinjection cases: observation description, creator sequence, interpreter sequence and a source UID in a retained ROI label; the audit rejects each.
7. A reintroduced RT observation description blocks whole-batch publication and leaves no staging output.
8. The normalized-structure-label independent-audit limitation, characterized explicitly.

All eight methods passed as focused composite evidence on newly generated
synthetic inputs. Three methods gained explicit sequence-length assertions
during review; only those changed methods were repeated. The cases
exercise the current Python engine and staged-file audit; fixtures are small
examples, not complete conformant clinical RTSTRUCT objects. Generated files are
temporary and removed after each case. No imaging data is committed.

Existing generic PN/date/private-tag/UID evidence, the single CT/RTSTRUCT linkage
test, cross-patient frame-collision tests and prior native/runtime/UI evidence
are reused without reruns. No native build, external Java/Docker execution, GUI
use, app launch, signing, notarization or publication is part of this increment.
Detailed operational receipts and logs remain outside the source repository.
