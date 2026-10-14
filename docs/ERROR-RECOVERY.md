# Focused error recovery — 2026-10-14

## Scope and fixes

Keep the existing interface, engine events, anonymization policy, runtime dependencies and icon.

- Rejecting an inaccessible input clears the old source and ready preview. Check Again and direct processing calls cannot silently use the previous batch.
- Validate that a chosen output is an existing directory before saving its preference and again before processing. A failed selection preserves the last valid preference. Choosing a valid replacement clears the output error without rescanning the ready batch. This is directory-existence validation; it does not guarantee write permissions.
- Distinguish input, output, processing and report problems. Offer the appropriate Choose Folder, Choose Location, Check Again or Reveal Output action. Processing errors retain alternatives for changing either folder.
- A missing/unopenable report retains the completed-batch record and summary. Dismiss restores the completed state. A directory named anonymization-report.json is not treated as a report file.
- Enforce action availability in model methods as well as buttons and File commands. Block output inspection and folder changes while busy.
- Make cancellation idempotent, ignore late progress updates while stopping and disable repeated cancellation. Suppress misleading preparing progress after an error while leaving Cancel available until the worker stops.

## Changed-input evidence

Four new isolated model checks cover rejected input after a ready batch; invalid/disconnected output and saved preferences; missing-report recovery with completion preserved; and cancellation/busy action guards. Fixtures contain no DICOM data, use an isolated UserDefaults suite and do not start engine processing.

Recovery layouts for all four problem types fit the minimum width in light and dark with long paths. Native synthetic previews confirmed report dismissal preserves completion, output replacement preserves the ready preview without a scan, input errors remove stale preview, and cancellation/pending-error actions reflect the stopping state. Actual local candidates launched and their idle File menus disabled actions lacking prerequisites. Candidates and previews were quit after inspection; the installed app was untouched. Synthetic presentation evidence is not new end-to-end processing acceptance.

Public: retain the independent SwiftUI interface and macOS 13. The real optimized target compiled with warnings as errors. Four model checks and light/dark layouts passed (700 × 655 content points). After the final public-only pending-error spinner correction and strengthening the busy fixture with an existing output record, the target compiled and only the changed busy model case ran again. Native inspection confirmed the corrected pending-error presentation; passed idle recovery layout cases were reused.

## Reused evidence and delivery boundary

Reuse the accepted evidence recorded in WORKFLOW-POLISH.md and the existing engine, self-audit, standalone-Python, dependency, icon and theme receipts. No engine/self-audit processing, unchanged suite, signing/dependency verification, provenance rehash or corpus pass was repeated. Existing physical drag-and-drop acceptance limitations remain unchanged.

This pass creates local source commits and ad-hoc local candidates only. It does not change main, the installed app or the published release. A changed executable requires its own distribution signature and notarization when delivery is authorized; the earlier ticket does not certify this executable.
