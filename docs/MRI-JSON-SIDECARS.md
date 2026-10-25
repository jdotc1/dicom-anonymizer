# MRI JSON sidecars — local implementation

## Preview 16 delivery — 2026-10-24

Published unified public Preview 16 (version 2.0.0, build 20) from engine/release source `78d315cb52bbe372c5da02f7a99f9bd4dce1bdd8` and reused native source `80a8a8d1e820e64c6aab322894f61213a7adf893`. Developer ID signing, Apple Accepted notarization `c3393d48-bcda-4dcc-9381-e2b0425a6c2d`, stapling/ticket validation and Gatekeeper assessment passed once for this new package. Accepted functional/native/runtime evidence was reused; no tests, native build or unchanged dependency-signature checks were repeated. No GUI use, native app launch or installation occurred. Live toggle/rescan/layout acceptance remains pending.

Release: https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.16

The source-increment record below is retained as history; its pre-publication statements describe that earlier stage.


Date: 2026-10-24. Source acceptance complete; published as Preview 16; native live interaction acceptance pending.

## Scope

The session-only **Clean JSON sidecars** option defaults off. Changing it while idle invalidates the previous ready state and rescans the selected batch. It is disabled while busy. The existing numeric-patient-folder DICOM workflow remains required; JSON-only and NIfTI-only inputs are not supported.

When enabled, the engine discovers `.json` companions under numeric patient folders, rejects malformed or unsafe selected JSON before staging, and writes cleaned copies under `<patient>/Sidecars/Sidecar_000001.json`. The original filename/path mapping is deliberately not published. Part 10 DICOM files named `.json` and genuine AppleDouble companions are excluded from sidecar selection. Source files are never rewritten.

The `mri-physical-v1` policy (1.0.0, catalog 2026-10-24.1) retains only 44 catalogued MRI acquisition/physics fields, with exact numeric tokens, bounded types, ranges and cardinalities. Unknown keys are dropped. Wrong values for known keys reject the batch. The machine-readable catalog is `engine/policy/mri-physical-v1.json`; executable rules are in `engine/sidecar_deid.py`.

Patient/site/device identifiers, dates, UIDs, paths and arbitrary free text are omitted from cleaned JSON. This JSON policy intentionally differs from the unchanged DICOM retention policy: DICOM sequence/ROI labels remain governed by that existing policy.

## Integration

- Lazy sidecar import and explicit `--clean-json-sidecars` CLI flag; disabled mode retains original DICOM report/events and does not invoke the new inventory seal.
- Scan validates and estimates cleaned bytes from the same bounded read. Disk-space budgeting adds sidecar allocation, directories/entries and report allowance, retaining the existing reserve and uncertainty warning.
- Discovery walk errors fail closed; discovery, cleaning, audit and final sealing cooperate with cancellation.
- All output shares existing owned staging, cleanup and exclusive atomic publication. Destination errors preserve existing space/permissions/location recovery classifications.
- DICOM writing → sidecar cleaning → DICOM audit → mandatory sidecar audit → report/inventory sealing → existing publication boundary.
- Sidecar audit checks content and expected size/digest. Final seal rejects unexpected/missing/symlink entries and rechecks sidecar integrity before publication. Operational per-output digests are part of the new audit, not repeated provenance checks of accepted inputs.
- Events carry only counts; reports add policy identity and aggregate counts, without source names/paths, dropped values or raw digests.
- Native models validate monotonic counts and phase order; sidecar audit must finish before finalization. The native interface retains its existing style.

## Evidence and limits

The supplied portable implementation reports **92 tests passed**. This is reused external evidence, not a fresh host run. Parser, field-policy, number-token and original resource-budget tests were not repeated. Integration preserved the current host behavior instead of applying an obsolete baseline-specific patcher.

The public consolidation retains this sidecar implementation and adds the folder-conflict checks before discovery/staging. Public UI and native product inputs are unchanged by that port. Four new consolidation seam checks passed; the accepted sidecar checks below were reused, not repeated.

Detailed verification records are retained outside the repository:

- 17 engine checks cover host adaptation/recovery, mixed synthetic DICOM/JSON
  processing and symlink-root inventory sealing.
- 11 native model checks passed as composite evidence. They cover default-off and
  session-only state, CLI arguments, busy guarding, count validation, cleaning/audit
  phases, finalization, cancellation/error handling, reset and late-event ordering.
- The optimized arm64/macOS 13 executable compiled with warnings as errors.
- Background bundle/import validation has separate evidence. Compilation and model
  checks do not establish live layout or interaction behavior.

These records do not establish live toggle/rescan behavior, light/dark layout or minimum-window appearance; those remain pending. No merge, push, release, signing, notarization or installation was performed for this increment. Accepted DICOM policy/self-audit, existing recovery suites, runtime/dependency/icon evidence were reused, not rerun.

This cleans JSON metadata only. It does not copy or anonymize NIfTI voxels, image text/faces or other companion formats. Technical values and numeric patient pseudonyms can remain linkable. Generated filenames lose BIDS/source acquisition linkage; outputs need review before sharing. This is not certified anonymization or DICOM confidentiality-profile conformance.

## Implementation origin

The sidecar parser and policy were integrated from a supplied portable design.
Host integration retained input-stability checks, output recovery, cancellation,
publication and audit ordering. No unrelated comparison-interface implementation
was included. Existing repository licensing and applicable third-party notices
remain unchanged.
