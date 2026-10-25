# Workflow polish — 2026-10-14

## Changes

- Show Preparing before file writes and Finalizing after the last writing event, with an indeterminate indicator until the existing completion event arrives. No engine event or policy change.
- Expose Choose Output Location (Shift-Command-O), Check Again (Command-R), Reveal Output in Finder (Shift-Command-R) and Open Report (Option-Command-R) in the File menu. Disable commands when their prerequisites are absent or the app is busy.
- Keep full selected/output paths available through help and constrain long displayed names. Add keyboard/help hints to the affected controls.
- Clarify that numerical identifiers remain linkable and that pixel text is not redacted. Runtime startup errors tell app users to reinstall rather than rebuild.

Retain the existing SwiftUI interface and macOS 13 target. Collapse selected input to a compact folder row, keep root-window drop handling, use monospaced identifiers, and put completion actions below the summary. An error now disables Anonymize, including Command-Return, even if the previous batch was ready.

## Focused evidence

The changed real target compiled with Apple Swift 6.4, Swift 6 mode and warnings as errors. Synthetic model-state checks cover the final-writing/finalizing distinction; the public check also covers invalid selection after a ready batch. Long paths, 64-character identifiers and completion/finalizing layouts were inspected in light and dark. Finalization was inspected at 700 × 655 content points and long-name completion at 700 × 682, within the 720-point default height.

The initial layout fixture exposed excess drop-zone height, corrected with the compact folder row. Only failed or changed layout checks were repeated. Previously passing model checks were reused rather than repeated in subsequent presentation-only runs.

Native local candidates launched. The output-location menu command opened its native folder chooser and was cancelled without changing the output preference. Synthetic presentation harnesses showed empty, preparing, finalizing, error and completion states. These are UI presentation observations, not another end-to-end engine run.

## Reused evidence and delivery boundary

Reuse prior engine, metadata policy, self-audit, bundled-Python, dependency, icon, theme and notarization receipts for unchanged inputs. No batch processing, engine/self-audit suite, unchanged theme/signature/dependency check, provenance hash or corpus pass ran for this polish. The root signatures of the new local candidate/preview copies are ad-hoc; they are not new notarized releases.

Preview 5/build 9 uses the accepted optimized executable with updated release metadata. Distribution signing/notarization is recorded separately from the local candidate checks. Existing physical drag-and-drop acceptance limitations remain; the new public root drop target uses the unchanged NSItemProvider handler, without a new physical-drop acceptance claim.

Apple accepted the updated distribution submission `c36ff882-9b96-4888-8cf2-a7edf23edb98` on 2026-10-14. The accepted optimized executable was reused; no runtime or source test was repeated for submission.
