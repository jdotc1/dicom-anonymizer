# Public app consolidation

## Consolidated source

## Focused evidence

Four new public host seam checks passed once in `tests/test_public_consolidation.py`:

1. Shared source patient ID across numeric folders blocks a sidecar-enabled batch before staging, with safe actionable recovery.
2. Public CLI emits the detailed recovery message without absolute paths or synthetic source identity.
3. Distinct patients retain exact numeric output folders while DICOM and sidecar outputs are both audited and published together.
4. Default-off DICOM-only processing uses the improved recovery without invoking sidecar discovery.

Source-only independent review found no consolidation blocker. Public native sources were unchanged by consolidation, so the accepted optimized executable, 11 sidecar model checks and development-bundle runtime evidence from `80a8a8d` are reused. No native rebuild, model rerun or bundle smoke rerun occurred for this engine-only port. The sidecar source receipt has 17 engine seam checks per variant plus one new development-bundle CLI smoke check per variant; those remain their own input-specific evidence.

## CI and publication

The existing public workflow remains manually authorized; no workflow was dispatched. Its temporary-directory environment is now set explicitly so the focused fixtures have a valid scratch location on a future authorized CI run. No automatic full-suite reruns were enabled.

## Sidecar limits

JSON companions are cleaned only within valid DICOM batches. No JSON-only/NIfTI-only workflow, voxel de-identification or BIDS filename-linkage mapping is added. The JSON allowlist is intentionally stricter than the retained DICOM sequence-label policy. Numeric pseudonyms and retained technical values remain linkable; output review is required before sharing.
