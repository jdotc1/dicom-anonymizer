# Output-location rechecks and recovery-record acknowledgement

## Scope — 24 October 2026

Local source increment after delivered Preview 21/build 25. Public views/controls, engine metadata and sidecar policies, bundled runtime, and arm64/macOS 13 target are unchanged. No automatic processing retry, resume or batch-data deletion is added.

## Output-location rechecks

Recovery scans mark valid unresolved records as having pending locations. Those records keep the existing single-pending, 30-second background inspection chain active while the recovery area remains idle and owned by that notice. This permits updated explanations after a path becomes available, a matching folder is replaced or a record is resolved externally. It uses conservative path/identity checks; availability alone never establishes completion or triggers acknowledgement.

Malformed records alone remain visible without recurring location inspection. A mixed set retains all notices while rechecking valid unresolved locations. Live-owner rechecks retain their accepted behavior.

A selected source, active run, completion, newer error or deliberate successful output choice stops the refresh chain. The successful-choice guard is explicit because clearing an error alone leaves an otherwise idle model; a delayed snapshot must not restore an old notice over that newer choice. No new controls or filesystem event observers are introduced.

## Headless acknowledgement coverage

The synthetic Python worker in `UITests/Fixtures/record_worker.py` writes isolated output markers and a recovery record at the exact unique journal path supplied by the real model launch path. Its JSON events and process exit pass through `EngineRunner`, main-actor model reduction, `finishRun` and the existing acknowledgement function.

Eight new integration cases establish:

- A successful completion/exit retires the matching published local record.
- A nonzero exit, malformed response or cancelled worker retains the record and preserves the model's uncertain/failure state.
- Replaced output identity, a different recorded output path, a non-published record phase, and a symlinked record prevent acknowledgement/removal.
- Original output marker data, unrelated replacement data and symlink targets survive record handling.

The identity/path/phase negative cases test record retention, not rejection of a completion summary. The existing model accepts a completion event plus exit zero separately from acknowledgement; refusal to remove a record is not a new completion-policy gate. No engine or completion-reducer policy was changed.

## Focused evidence

Nine new location/model cases and eight new subprocess/model/filesystem acknowledgement cases passed as composite evidence. The first seven location cases and all eight acknowledgement cases passed once. Source-only review found a successful-location-choice race; the explicit ownership invalidation and two new regression cases address it. Passing unchanged cases were reused, not rerun.

Accepted engine/policy/self-audit, sidecar/r2, prior lifecycle/worker/model/journal, runtime, dependency, icon and Preview 21 distribution receipts were reused. No engine suite, unchanged native suite, source hashes, dependency-signature checks or accepted release verification were repeated.

## Limits and delivery status

Tests simulate disappearance/restoration by moving temporary directories; they do not mount/unmount a real volume. Model snapshots establish refresh decisions and stale-result protection, not live app timer scheduling. The synthetic worker writes a fixture record/output directly, so it does not establish real engine processing, self-audit, atomic publication or durability. Existing receipts retain their original scope.

No GUI use, native app launch, installation, signing, notarization, push or publication occurred. Preview 21/build 25 remains the public download. Live scheduling, recovery/sidecar interaction, volume behavior, responsiveness and layout acceptance remain pending.
