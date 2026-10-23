# Cancellation, publication and incomplete-output recovery

## Operation outcomes

- Cancellation before publication raises a structured cancellation error and removes this operation's staging directory. Signals received during staging allocation are deferred until ownership has been recorded, then honoured before processing continues.
- Once the short publication boundary begins immediately before the exclusive rename, cancellation is deferred through the complete event and successful return to main. A late request cannot separate a published result from its completion acknowledgement.
- The app still requires a complete event and successful worker exit before it records completion. A late local cancellation request does not discard that accepted result.
- If a failure occurs after the rename succeeds, the engine reports that output was published but completion could not be confirmed, with `output_published: true`. It exits unsuccessfully; the app retains the warning and destination without inventing a completed summary.
- An unexpected worker exit without an outcome event is described as unconfirmed. The app asks the user to inspect the destination rather than claiming no output exists. A failed scan is described only as an incomplete folder check.

## Failed cleanup

Cleanup attempts removal of the staging directory allocated for the current operation. Its recorded device/inode and directory type are checked before removal. A replacement directory is preserved. This check is a recovery safeguard, not a guarantee against adversarial filesystem races.

Cleanup errors retain the original safe processing message and add `cleanup_failed: true`, the accurate `cancelled` flag and, when ownership is still known, `staging_path`. Paths stay in structured local context rather than the copyable error message. When ownership is lost, the path is omitted and the user is told to inspect the output location. Cleanup failure does not lead to broad deletion of other staging folders or automatic resumption of partial output.

Quit during processing requests cancellation as before. If cleanup fails or publication remains unconfirmed, the pending Quit is declined so the existing recovery message remains visible. The user can review it and quit again once the operation has stopped. Clean cancellation and confirmed completion permit the pending Quit.

## Focused evidence

Native synthetic review used the actual app models, views and AppDelegate with fixture events, at 700 × 700 content points for private and 700 × 655 for public. Failed-cleanup messages and paths remained readable in light and dark; unknown staging and published-but-unconfirmed states retained their existing recovery controls. Native Command-Q during pending cleanup entered cancellation, and the window stayed open when cleanup failed. A subsequent idle Quit closed each review app. No DICOM batch or real cleanup deletion was performed by the native harness. The private harness initially omitted DICOMMetrics.swift; that harness-only compile was repaired by including all app source files. The accepted real-target build and model results were reused, not repeated.

An independent read-only review found no blocking issues. A displayed staging path is the ownership snapshot from the failed cleanup attempt, not a continuously verified deletion target.

## Reused evidence and delivery boundary

Reuse the accepted audit-progress evidence in `AUDIT-PROGRESS.md`, earlier recovery/presentation receipts, metadata-policy/self-audit policy checks, standalone Python, runtime, icon and dependency evidence for unchanged inputs. No unchanged suite, corpus processing, provenance hash or dependency/signature verification was repeated. Native synthetic evidence is not a fresh end-to-end DICOM batch run.
