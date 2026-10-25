# Disk-space and output-location recovery

Source increment: 2026-10-23. The app retains its existing interface, platform target, metadata policy, report schema, self-audit and cancellation/publication contract.

## Destination error contract

Known destination operations classify filesystem failures into an optional `output_issue`: `space`, `permissions`, `unavailable`, `conflict` or `unknown`. This classification covers destination prechecks, staging allocation/metadata, generated output directories, DICOM writes, report writes and exclusive publication. Actual macOS publication errno is preserved for classification. Input resolution, scanning and input reads remain processing errors; a generic OSError anywhere in the engine is not assumed to be an output failure.

- `space`: full storage or a storage quota; free space or choose another location.
- `permissions`: permission denial or a read-only filesystem; restore write access or choose a writable folder.
- `unavailable`: the known destination operation cannot access its location; check availability/reconnect or choose another location. The message does not assert a specific disconnection cause.
- `conflict`: an existing destination or an invalid overlap; choose a separate output location. Nothing is overwritten.
- `unknown`: a destination operation failed for another reason; inspect the volume or choose another writable location.

Messages use fixed safe reasons rather than raw operating-system errors or source paths. The app obtains the output parent from the active operation rather than trusting a new path field.

## Approximate space estimate

The existing estimate is preserved exactly: `int(sum(source sizes) * 1.1) + 32 MiB`. A preflight shortage now reports the estimated need and available space in readable units and explicitly says that the estimate is not a guarantee. Its event also includes integer `required_bytes` and `available_bytes`. A later write failure reports the storage/quota problem without inventing fresh free-space counts.

No extra write probe, permission change, policy limit, parser change or batch-size restriction is introduced. Directory selection remains an existence check; actual destination failures are classified when the engine attempts the operation. Available space and access can change after checking.

## App recovery

A recognized storage error during processing, with an active destination, uses the existing output-error area and Choose Location action. The title and guidance distinguish insufficient space, write access, unavailable locations and conflicts. Malformed/unknown reason values, idle events, scan errors and missing operation destinations use conservative processing recovery.

After a cleanly recovered output failure, choosing a valid replacement preserves the accepted patient preview and returns to Ready without starting another worker or scan. The engine still performs its existing input scan before writing on the next run. An invalid replacement preserves the previous valid preference and cannot leave an obsolete disk-full title on an unavailable-folder error. Choosing output never creates an accepted input preview when none existed.

Cleanup failure retains priority over storage recovery: the original storage reason remains in the engine error, but the existing incomplete-staging warning remains visible and blocks a pending Quit. Invalid replacement selection cannot erase that cleanup warning. Lost/unknown staging ownership omits the removal target. A post-publication failure remains an unconfirmed-publication warning and does not become a retryable storage error.

## Focused evidence and reuse

Twenty-seven engine checks passed, plus the one existing publication-rename case whose expected error changed from raw OSError to the safe classified BatchError. Earlier passing storage checks were reused as narrow precheck and ownership refinements were added. Mocked scans, reads, policy operations and audits plus temporary output avoid processing DICOM data or filling a real drive.

Eleven model checks passed. They cover all storage reasons and the safe estimate message, valid replacement with preview/preference preservation, invalid replacement, cleanup and publication precedence, input-versus-output routing, active operation context, state reset, absent accepted preview and Quit after safe cleanup. Preferences and temporary folders are isolated.

The optimized target compiled with Xcode 27.2 build 27B48, Swift 6.4.2 and SDK 27.2, Swift 6 with warnings as errors, targeting arm64/macOS 13. Only the new StorageRecoveryChecks executable ran. The unchanged publication/cancellation cases, audit-progress suites, metadata/self-audit policy, standalone Python/runtime, dependency, icon and prior UI evidence are reused.

Native synthetic review used the actual model and views at 700 × 655 content points. Space-estimate warnings were inspected in light and dark; write-access and combined disk-full/cleanup warnings were inspected in dark appearance. Long paths and recovery actions remained visible. The existing native output chooser selected an isolated review folder after an unavailable-output error; the error cleared, the same one-patient/60-file preview returned to Ready and Anonymize Batch became available, without a worker/scan starting. No real DICOM input was read and no external drive was filled, disconnected or made read-only. The review candidate was quit afterward.

An independent source-only model review found no blocking issue and recommended requiring the active operation destination for storage routing; that guard was included before the successful builds and new model checks.

## Delivery boundary

## Public Preview 10 delivery

Delivered on 2026-10-23 from accepted app-source `35c967c` with release merge `7e78c05`. Apple accepted notarization `37d2468f-33cf-4a91-94c2-0be59e6bc79c`. The first changed root signature, stapled ticket and Gatekeeper assessment passed. Public Preview 10 is app version 2.0/build 14, delivered as the standalone arm64 macOS ZIP. GitHub asset metadata and public HTTP access were checked; earlier preview tags and acceptance records remain historical.

Accepted optimized executable, 27 new focused engine storage cases plus the one modified publication regression, 11 model checks and native storage/output-replacement evidence were reused. Unchanged nested runtime signatures and earlier policy/runtime/icon acceptance were retained. No unchanged acceptance, rebuild, corpus pass, provenance hash or dependency/signature check was repeated. Earlier Preview 9 retains its original artifact-specific qualification.

See [Visual development roadmap](ROADMAP-VISUAL.md) for delivered milestones, the current release and proposed next priorities.
