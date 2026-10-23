# Recovery presentation in compact windows

## Local source change

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

## Evidence

The first build attempt stopped at the old toolchain guard before compilation
because it rejected the selected Swift 6.4.2 compiler. It provides no compilation
evidence. After the guard adjustment, the real optimized target compiled with
exit code 0 under Apple Swift 6.4.2, targeting arm64/macOS 13 with warnings treated
as errors.

Focused native presentation review completed on 2026-10-23 using synthetic
states and the actual changed model/view source from `96b1205`. At 700 × 655
content points in light and dark, a ten-section conflict report scrolled to its
final suggested fix while the path, recovery buttons and Copy Details remained
visible. The footer showed no duplicate Check Again action. A rejected input
after a synthetic completion hid the old success summary. A report warning kept
the completion summary, and Dismiss removed the warning without clearing the
completed result. No engine processing was started for these checks.

The real optimized local candidate also launched and displayed its native window.
Startup logs retained macOS preferences/AppIntents service-registration and
BaseBoard errors; no crash or hang was observed. Both isolated local apps were
quit after inspection. The presentation harness and logs are retained outside
source control. They are UI evidence, not installed-app or processing acceptance.

Existing preview-6/build-10 delivery records and accepted engine, runtime, icon
and unchanged recovery evidence remain historical evidence for their original
inputs. No unchanged tests, engine processing, signing/dependency checks,
provenance hashes or corpus passes are required by this documentation update.
No source push, installation or release publication is part of this local lane.
