# MRI JSON sidecars — local implementation

Date: 2026-10-24. Status: unreleased; native live interaction acceptance pending.

## Scope

The session-only **Clean JSON sidecars** option defaults off. Changing it while idle invalidates the previous ready state and rescans the selected batch. It is disabled while busy. The existing numeric-patient-folder DICOM workflow remains required; JSON-only and NIfTI-only inputs are not supported.

When enabled, the engine discovers `.json` companions under numeric patient folders, rejects malformed or unsafe selected JSON before staging, and writes cleaned copies under `<patient>/Sidecars/Sidecar_000001.json`. The original filename/path mapping is deliberately not published. Part 10 DICOM files named `.json` and genuine AppleDouble companions are excluded from sidecar selection. Source files are never rewritten.

The `mri-physical-v1` policy (1.0.0, catalog 2026-10-24.1) retains only 44 catalogued MRI acquisition/physics fields, with exact numeric tokens, bounded types, ranges and cardinalities. Unknown keys are dropped. Wrong values for known keys reject the batch. The machine-readable catalog is `engine/policy/mri-physical-v1.json`; executable rules are in `engine/sidecar_deid.py`.

Patient/site/device identifiers, dates, UIDs, paths and arbitrary free text are omitted from cleaned JSON. This JSON policy intentionally differs from the unchanged DICOM retention policy: DICOM sequence/ROI labels remain governed by that existing policy.

## Integration

## Evidence and limits

The supplied archive's `evidence/FINAL_VERIFICATION.log` reports **92 portable tests passed**. That is reused handoff evidence, not a fresh local run. Parser, field-policy, number-token and original resource-budget tests were not repeated. The historical blob-gated patcher was not bypassed or applied to the newer source; integration was ported semantically into isolated current-main worktrees.

No GUI use or app launches are authorized. Live toggle/rescan behavior, light/dark layout and minimum-window inspection remain pending. No merge, push, release, signing, notarization or installation was performed for this increment. Accepted DICOM policy/self-audit, existing recovery suites, runtime/dependency/icon evidence were reused, not rerun.

This cleans JSON metadata only. It does not copy or anonymize NIfTI voxels, image text/faces or other companion formats. Technical values and numeric patient pseudonyms can remain linkable. Generated filenames lose BIDS/source acquisition linkage; outputs need review before sharing. This is not certified anonymization or DICOM confidentiality-profile conformance.

## Provenance
