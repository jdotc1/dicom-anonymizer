# Recovery presentation in compact windows

## Local source change

Commit `96b120585fd4a8ae1059033a3e158b9badae420c` on
`codex/recovery-presentation-parity` improves recovery presentation in the public
app's existing SwiftUI interface. This is an unshipped local source change.
The published preview 6/build 10 remains the historical release described in
`docs/ERROR-RECOVERY.md`; this work does not establish a new release or the
current installed version.

## Behavior

- Recovery text fits naturally when space allows and scrolls within the available
  height when a long message would otherwise crowd out actions. The recovery
  buttons and affected Folder or Location remain outside the scrolling text.
- The affected path uses at most two lines with middle truncation. The full path
  remains available through text selection and the existing help presentation.
- A blocking problem hides a stale completion summary. A report problem preserves
  the completed-batch summary and its recovery behavior.
- During an error, the footer omits the redundant Check Again button; the relevant
  action remains in the recovery area. Busy-state cancellation remains available.
- The toolchain guard accepts Apple Swift 6.4 patch releases, including 6.4.2,
  while retaining the requirement for Apple Swift 6.4 from Xcode.

This change preserves the public interface and macOS 13 deployment target.
It does not change the engine, anonymization policy, event schema, runtime
requirements or existing accessibility behavior. It introduces no Lumen
dependency.

## Evidence

The first build attempt stopped at the old toolchain guard before compilation
because it rejected the selected Swift 6.4.2 compiler. It provides no compilation
evidence. After the guard adjustment, the real optimized target compiled with
exit code 0 under Apple Swift 6.4.2, targeting arm64/macOS 13 with warnings treated
as errors.

Focused native presentation review: **pending**. Record the actual candidate
identity, compact-window observations, recovery behavior and any remaining
limitations here after that review. Compilation alone does not establish that
long messages scroll correctly or that the recovery actions remain visible.

Existing preview-6/build-10 delivery records and accepted engine, runtime, icon
and unchanged recovery evidence remain historical evidence for their original
inputs. No unchanged tests, engine processing, signing/dependency checks,
provenance hashes or corpus passes are required by this documentation update.
No source push, installation or release publication is part of this local lane.
