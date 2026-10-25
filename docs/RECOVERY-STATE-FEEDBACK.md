# Recovery-directory inspection and acknowledgement feedback

## Scope — 24 October 2026

Local source increment after Preview 23/build 27. Public view structure, controls, macOS 13/arm64 target, engine metadata policy and default-off sidecar policy are unchanged. No automatic batch deletion, retry or resume is added.

## Directory inspection

A recovery scan now distinguishes a successful listing from an unavailable directory. Listing failures carry the recovery-directory location and whether the error specifically reports missing data; raw filesystem diagnostics are not presented.

- An initially missing Operations directory is normal before the first batch.
- An unreadable directory produces a conservative inspection notice in the existing recovery area and retains the guarded recheck chain.
- Failure during a refresh retains the last available recovery notice and its location, rather than treating the records as resolved. Repeated failures do not recursively grow the explanation.
- After any successful directory observation, including one with only a live owner and no visible notice, a missing directory is a new inspection problem. It cannot be mistaken for fresh-install absence.
- A subsequent successful empty listing may clear the app's own inspection notice. A successful listing with unresolved records restores their actual notices.
- Existing current-action guards still protect newer errors, successful output choices, selected sources, active runs and completion results.

Permission failures are simulated through an internal directory-listing closure; tests do not change OS permissions or claim coverage of every real volume/filesystem permission configuration.

## Acknowledgement feedback

Local record acknowledgement now returns one of three results: not requested, retired, or unresolved. Identity/path/phase/symlink guards remain conservative. A failure to remove an eligible local record is independent of the worker's successful batch result.

After valid completion and successful worker exit, unresolved acknowledgement presents a nonblocking warning through the existing report/recovery area. The completion summary, output location, Reveal Output action and Dismiss action remain available. The warning explains that a later recovery notice may reappear and asks the user to review the output before retrying to avoid duplicate work.

Dismissing the warning retains the completed result and does not remove the unresolved record. A record problem alone does not veto a pending quit after confirmed completion. Missing, mismatched, non-published or unsafe records are not deleted. No batch data is removed by acknowledgement.

The `.report` presentation is reused to preserve the public view/control structure; its title and guidance distinguish this local-record warning from an unavailable report. Ordinary later problems clear the warning marker.

## Focused evidence

Nine new directory/model cases and eight new synthetic worker/model/record-feedback cases passed as composite evidence. The initial eight directory cases passed. Review found that a live-owner-only observation was not remembered when a directory later disappeared; a history flag and one new regression case resolved it, with only the affected fresh-missing case repeated.

The first seven acknowledgement cases reached their expected completion/record states but failed an invalid final harness assertion that called `prepareToQuit` while idle. The app delegate does not call that helper while idle. The harness was corrected without changing product quit behavior; failed-only cases passed, and a new active-worker pending-quit case verifies successful completion plus record-removal failure resolves the pending quit. Removal permission failure is injected only at local-record deletion.

Two affected older worker-to-model cases, whose synthetic workers intentionally omit the selected record, now expect retained completion plus a nonblocking acknowledgement warning. Only those two existing cases were run. All unrelated passing engine, policy, self-audit, sidecar/r2, lifecycle, worker/model/journal, runtime, dependency, icon and Preview 23 distribution receipts were reused.

## Evidence limits and delivery

Synthetic workers create isolated records/output markers; they do not establish real engine processing, audit/publication/durability or live app termination behavior. Snapshot checks establish model decisions, not actual timer scheduling. Live recovery/sidecar interaction, volume behavior, responsiveness and layout remain pending.

No GUI use, native app launch, installation, signing, notarization, push or publication occurred for this increment. Preview 23/build 27 remains the public download until separately authorized delivery.
