# Cancellation, publication and incomplete-output recovery

Source increment: 2026-10-23. This change retains the current interface and platform target, metadata policy, pre-publication self-audit, report schema and exclusive atomic publication.

## Operation outcomes

- Cancellation before publication raises a structured cancellation error and removes this operation's staging directory. Signals received during staging allocation are deferred until ownership has been recorded, then honoured before processing continues.
- Once the short publication boundary begins immediately before the exclusive rename, cancellation is deferred through the complete event and successful return to main. A late request cannot separate a published result from its completion acknowledgement.
- The app still requires a complete event and successful worker exit before it records completion. A late local cancellation request does not discard that accepted result.
- If a failure occurs after the rename succeeds, the engine reports that output was published but completion could not be confirmed, with `output_published: true`. It exits unsuccessfully; the app retains the warning and destination without inventing a completed summary.
- An unexpected worker exit without an outcome event is described as unconfirmed. The app asks the user to inspect the destination rather than claiming no output exists. A failed scan is described only as an incomplete folder check.

## Failed cleanup

Cleanup attempts removal of the staging directory allocated for the current operation. Its recorded device/inode and directory type are checked before removal. A replacement directory is preserved. This check is a recovery safeguard, not a guarantee against adversarial filesystem races.

Cleanup errors retain the original safe processing message and add `cleanup_failed: true`, the accurate `cancelled` flag and, when ownership is still known, `staging_path`. Paths stay in structured local context rather than the copyable error message. When ownership is lost, the path is omitted and the user is told to inspect the output location. Cleanup failure does not lead to broad deletion of other staging folders or automatic resumption of partial output.

The app keeps cleanup warnings in its existing output-error area after the worker stops. The model accepts a staging path only under the current destination parent, with a nonempty `.dicom-batch-` name, excluding the source and final destination. An unavailable or rejected path receives recovery guidance that does not instruct deletion of the displayed output parent.

Quit during processing requests cancellation as before. If cleanup fails or publication remains unconfirmed, the pending Quit is declined so the existing recovery message remains visible. The user can review it and quit again once the operation has stopped. Clean cancellation and confirmed completion permit the pending Quit.

## Focused evidence

Fifteen focused engine lifecycle checks cover cancellation, staging ownership, cleanup and post-publication failures. These mocked checks do not process imaging data or repeat policy/self-audit verification.

Thirteen model checks passed. They cover late cancellation with successful completion, acknowledged cancellation, failed cleanup and pending Quit, preservation of a processing failure despite Cancel, uncertain exits, the complete-plus-successful-exit requirement, malformed/unrelated/source/destination cleanup paths, state reset, and successful/pre-start-cancelled Quit replies. Preferences are isolated; these checks do not start the worker or process DICOM data.

The optimized native target compiled with Swift 6.4.2, Xcode 27.2 build 27B48 and SDK 27.2, in Swift 6 mode with warnings as errors, targeting arm64/macOS 13. Only the new PublicationRecoveryChecks executable ran.

Native synthetic review used the actual model, views and AppDelegate with fixture events at 700 × 655 content points. Failed-cleanup messages and paths remained readable in light and dark; unknown staging and published-but-unconfirmed states retained their existing recovery controls. Native Command-Q during pending cleanup entered cancellation, and the window stayed open when cleanup failed. A subsequent idle Quit closed the review app. No DICOM batch or real cleanup deletion was performed by the native harness. The accepted real-target build and model results were reused, not repeated.

An independent read-only review found no blocking issues. A displayed staging path is the ownership snapshot from the failed cleanup attempt, not a continuously verified deletion target.

## Reused evidence and delivery boundary

Reuse the accepted audit-progress evidence in `AUDIT-PROGRESS.md`, earlier recovery/presentation receipts, metadata-policy/self-audit policy checks, standalone Python, runtime, icon and dependency evidence for unchanged inputs. No unchanged suite, corpus processing, provenance hash or dependency/signature verification was repeated. Native synthetic evidence is not a fresh end-to-end DICOM batch run.

## Public Preview 9 delivery

Delivered on 2026-10-23 using accepted app-source `41594fa` and release source `376613d`. Apple accepted notarization `43c80b7e-5dd6-4ce0-a063-1c9d0a86f229`. The new distribution root signature, stapled ticket and Gatekeeper assessment passed. Public Preview 9 is app version 2.0/build 13, distributed as the standalone arm64 macOS ZIP. Earlier preview tags and acceptance records remain historical.

Accepted optimized executable, engine/model checks, native recovery/Quit review and unchanged nested runtime signatures were reused. Only changed release metadata/distribution and delivery inputs were checked. Earlier Preview 8 retains its original artifact-specific qualification.
