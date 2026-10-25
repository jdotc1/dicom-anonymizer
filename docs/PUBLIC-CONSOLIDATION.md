# Public app consolidation

## Preview 16 delivery — 2026-10-24

Published unified public Preview 16 (version 2.0.0, build 20) from engine/release source `78d315cb52bbe372c5da02f7a99f9bd4dce1bdd8` and reused native source `80a8a8d1e820e64c6aab322894f61213a7adf893`. Developer ID signing, Apple Accepted notarization `c3393d48-bcda-4dcc-9381-e2b0425a6c2d`, stapling/ticket validation and Gatekeeper assessment passed once for this new package. Accepted functional/native/runtime evidence was reused; no tests, native build or unchanged dependency-signature checks were repeated. No GUI use, native app launch or installation occurred. Live toggle/rescan/layout acceptance remains pending.

Release: https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.16

The source-increment record below is retained as history; its pre-publication statements describe that earlier stage.


The repository `jdotc1/dicom-anonymizer` is the app source for ongoing development. The SwiftUI interface, Apple silicon/macOS 13 target, bundle identifier, icon and standalone Python runtime are retained.

## Consolidated source

- Retained optional MRI JSON-sidecar processing.
- Added aggregated folder-conflict explanations, source-patient-ID reuse detection,
  relative-location masking and actionable fixes before staging.
- Retained the metadata clean/audit policy, input-stability comparisons, progress,
  storage estimates, cancellation, owned cleanup and exclusive publication.
- Retained `tests/test_folder_conflicts.py` and its accepted verification for
  unchanged behavior. Patient datasets, credentials and signing secrets are not
  part of this source distribution.

## Focused evidence

Four new public host seam checks passed once in `tests/test_public_consolidation.py`:

1. Shared source patient ID across numeric folders blocks a sidecar-enabled batch before staging, with safe actionable recovery.
2. Public CLI emits the detailed recovery message without absolute paths or synthetic source identity.
3. Distinct patients retain exact numeric output folders while DICOM and sidecar outputs are both audited and published together.
4. Default-off DICOM-only processing uses the improved recovery without invoking sidecar discovery.

Source-only independent review found no consolidation blocker. Native sources were unchanged, so the accepted optimized executable, 11 sidecar model checks and development-bundle runtime evidence were reused. No native rebuild, model rerun or bundle smoke rerun occurred for this engine-only change. The accepted 17 engine seam checks and development-bundle CLI smoke check retain their original input-specific scope.

Detailed consolidation and sidecar verification records are retained outside the repository.

## CI and publication

The existing public workflow remains manually authorized; no workflow was dispatched. Its temporary-directory environment is now set explicitly so the focused fixtures have a valid scratch location on a future authorized CI run. No automatic full-suite reruns were enabled.

The original source-only stage involved no distribution or installation. Subsequent delivery is recorded above. Live toggle/rescan/layout acceptance remains pending; compilation, model and CLI evidence do not establish live GUI behavior.

## Sidecar limits

JSON companions are cleaned only within valid DICOM batches. No JSON-only/NIfTI-only workflow, voxel de-identification or BIDS filename-linkage mapping is added. The JSON allowlist is intentionally stricter than the retained DICOM sequence-label policy. Numeric pseudonyms and retained technical values remain linkable; output review is required before sharing.
