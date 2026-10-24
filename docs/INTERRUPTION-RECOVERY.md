# Interruption recovery — local source increment

Date: 2026-10-24. Not yet released. Public interface and metadata policy are unchanged.

## Operational journal

The native app assigns each processing run a unique record under its Application Support `DICOM Anonymizer/Operations` directory and passes `--journal` to the bundled worker. Scans do not create operation records. Direct CLI processing remains compatible when the optional flag is absent. Records are rejected inside the input or completed-output tree.

The engine exclusively creates a private record, writes through an atomic temporary-file replacement, fsyncs the file and parent directory, and records these boundaries:

- `started`: preflight passed, before staging allocation.
- `allocated`: current staging device/inode captured, before cancellation is re-enabled.
- `publishing`: report/audit/seal completed, before the existing exclusive-publication boundary.
- `published`: rename succeeded, before completion delivery.
- `cleaned`: normal failure/cancellation removed this operation's owned staging.

Records contain only schema/operation ID, process ID, timestamp, output/staging locations and staging identity. No original patient values, input-file inventory, source-file mapping or digests are added. The record is local application state, never part of batch output or release assets. Journal failures before publication stop safely through the existing cleanup path. A journal failure after rename reports published-but-unconfirmed output; cleanup-record failures preserve the primary failure.

## Existing recovery area

Startup inspects records in the background. A live recorded owner is left alone. Interrupted staging is described as owned only when it is a non-symlink directory with the recorded device/inode and expected output-parent relationship. An output is considered possibly published only by matching identity, not mere directory existence. Unknown, replaced or malformed state produces conservative recovery text. A late startup inspection cannot replace a new user action/error.

The existing recovery area shows the location and explanation; no new workflow surface is introduced. Nothing is resumed or deleted automatically. Successful native completion acknowledges only the unique published record whose output path and identity still match. The session-only sidecar option stays off after relaunch. Other unresolved records remain on disk for subsequent inspection.

## Focused evidence

Eleven new engine cases passed as a composite: nine initial journal/publication/cleanup cases plus new CLI forwarding and record-collision cases. Twelve new native CLI/model cases passed as a composite: six initial passes, three URL-trailing-slash fixture repairs, and three new malformed/semantic-record/current-action guard cases. Passing cases were not repeated. Actual optimized arm64/macOS 13 target compiled with warnings as errors using Swift 6.4.2, Xcode 27.2 build 27B48 and SDK 27.2.

Accepted policy/self-audit, sidecar/r2, worker feedback, runtime, dependency and icon evidence was reused. No GUI use, native app launch, remote publication, signing, notarization or installation occurred. Live startup/recovery, responsiveness and layout acceptance remain pending.

## Limits

This is advisory ownership-aware reconciliation, not automatic repair or a crash-proof transaction across every OS/storage failure. An interruption between staging creation and recording its identity remains unknown; device identity changes after remount also remain unknown. PID reuse can conservatively defer a notice. A live owner seen at startup is not continuously monitored. Journal persistence is durable to the filesystem's fsync contract, not a hardware power-loss guarantee. No privileged-local-attacker or atomic snapshot claim is made.
