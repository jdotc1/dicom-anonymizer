# RTSTRUCT policy comparison and synthetic coverage

This is a source-level comparison with focused synthetic coverage and independent
audit enforcement of the existing StructureSetLabel normalization. The current
download remains Preview 30/build 34; the audit change is not yet released.
The UI, metadata-cleaning policy, report schema and runtime dependencies are
unchanged. No external anonymizer code or imaging fixtures are vendored.

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
| StructureSetLabel | Replaced with `Structures`; independent audit now enforces the present SH value. | No explicit RT-specific rule found. | Existing normalization invariant enforced; see below. |
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

### Independent-audit normalization invariant

The comparison identified a gap: the cleaner normalized StructureSetLabel to
`Structures`, while the independent self-audit did not enforce that exact value.
The follow-up closes that gap. Every present occurrence must have SH VR and the
decoded scalar value `Structures`, including inside sequence items. Empty,
reintroduced, whitespace-altered, multi-valued and wrong-VR values are rejected
with the existing self-audit failure. The check precedes sequence handling so a
malformed SQ value cannot bypass it. This is decoded-value validation, not a
requirement on DICOM's normal on-disk space padding.

Absent labels remain accepted: the existing cleaner normalizes present values
and does not add the attribute. This does not assert RTSTRUCT IOD conformance.
The change enforces an existing replacement rule without broadening the
metadata-cleaning policy or adding general label classification.

This differs from ROIName and ROIObservationLabel: their retention is an explicit
policy choice. Synthetic identifier-like labels survive the new round-trip test
and the report still states the retention limitation. Successful self-audit is
not general text-identifier detection.

## New and reused evidence

`tests/test_rtstruct_policy.py` contains eleven focused methods:

1. RT-specific text and date/time handling across two ROI and observation items.
2. Identifier-like and Unicode label retention, with the report's limitation retained.
3. Removal of both numeric creator/interpreter sequences and all their items.
4. Two four-point closed polygons, ROI/observation reference numbers and display colors preserved through file output.
5. Consistent related-frame UID remapping with an unchanged retired transformation matrix.
6. Four reinjection cases: observation description, creator sequence, interpreter sequence and a source UID in a retained ROI label; the audit rejects each.
7. A reintroduced RT observation description blocks whole-batch publication and leaves no staging output.
8. Reintroduction of a noncanonical StructureSetLabel is rejected by the audit.
9. Eighteen noncanonical-value/VR cases across root, ROI and observation contexts, including a sequence-VR bypass attempt, are rejected.
10. Canonical labels at root/nested levels and absence of labels remain accepted.
11. A reintroduced StructureSetLabel blocks batch publication and leaves no staging output.

The initial eight methods passed as focused composite evidence on newly generated
synthetic inputs. Three methods gained explicit sequence-length assertions
during review; only those changed methods were repeated. The follow-up replaced
the original gap characterization with a rejection assertion and added three
methods. Only those four new/modified methods and the directly affected normal
RTSTRUCT round-trip method ran for enforcement; all five passed. Six unaffected
RTSTRUCT methods and earlier generic evidence were reused. The cases
exercise the current Python engine and staged-file audit; fixtures are small
examples, not complete conformant clinical RTSTRUCT objects. Generated files are
temporary and removed after each case. No imaging data is committed.

Existing generic PN/date/private-tag/UID evidence, the single CT/RTSTRUCT linkage
test, cross-patient frame-collision tests and prior native/runtime/UI evidence
are reused without reruns. No native build, external Java/Docker execution, GUI
use, app launch, signing, notarization or publication is part of this increment.
Detailed operational receipts and logs remain outside the source repository.
