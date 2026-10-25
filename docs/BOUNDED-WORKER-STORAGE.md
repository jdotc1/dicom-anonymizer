# Bounded worker events and monitored release writes

Delivered in Preview 28/build 32. Public view structure, metadata policy, sidecar defaults,
and engine processing are unchanged.

## Worker transport

`EngineEventStream` retains at most 8 MiB of pending frame bytes, excluding the
newline delimiter. A fragment that would exceed the limit is never copied into
the pending buffer. The buffer is released and a bounded invalid-JSON marker
enters the existing malformed-protocol path. Remaining bytes of that frame are
discarded through its newline while pipe reads continue. An oversized final
unterminated frame is reported once and its bytes are discarded at EOF.

Later valid frames are still delivered. Completion before or after an oversized
frame remains evidence of possible publication; it cannot produce nominal
success after a protocol failure. Safe structured engine errors and cleanup
information remain available. Cancellation after overflow does not imply that
no output was published. No raw oversized content is retained or displayed.

This is a transport-frame bound, not a new imaging-file, patient-count or
metadata policy. An exceptionally large legitimate JSON event can exceed it and
will need the same conservative recovery handling as any unreadable response.
The bound covers pending frame accumulation, not all process memory, queued
view state or the engine's own working memory. The test seam uses small injected
limits to exercise boundaries without generating large fixtures.

## Release storage admission

Allocating `scripts/release.py` actions (`assemble`, `sign`, `notarize`, `finalize`)
dispatch through `scripts/release_storage.py` under the shared storage guard.
The supervisor receives the original output arguments and owns the worker's
process group, including external packaging commands. There is no environment-
marker-only bypass: direct allocating Python APIs also authenticate the live
guard operation and admit the actual destination before release writes.
Supported nested admission attaches that destination's root and volume to the
existing parent monitor. Authentication is checked again afterward so a vanished
supervisor cannot authorize writes. Operational warnings remain visible.

Configure `storage-guard` through `PATH` or `STORAGE_GUARD`. No local machine path
is embedded in source. External development hosts need their own configured
guard. The adapter does not change shared reserves, warnings, registry limits
or admission policy. Read-only `plan` and `status` do not allocate a monitored
release job. Completed distribution commands continue to reuse their journals.

A missing guard, failed authentication, or destination refusal stops before
release writes. A supervisor stop returns its status, preserves partial output,
and never retries automatically. Partial output is not a successful artifact or
receipt. Source, current inputs, receipts, logs and dependencies are not deleted
to satisfy admission. Explicit retirement remains a separate operation.

## Focused evidence

Thirteen new headless worker cases passed as composite evidence: eleven initial
cases and two subsequently added review cases. These include real synthetic
shell-worker-to-model checks, with no application instance. The affected native
target compiled once, optimized, with Swift 6 and warnings treated as errors,
for arm64 macOS 13 using Xcode 27.2 / SDK 27.2 / Swift 6.4.2. The headless helper
was rebuilt only when its test source changed, and only the new cases were run.

Twenty new storage-admission mocks passed as composite evidence; one affected
preflight case was repeated after nested admission changed. They cover refusal,
authentication, destination admission,
argument/status preservation, interrupted supervision, read-only actions and
completed-step reuse. Existing fixture adapters isolate that new host boundary;
the earlier functional suites and accepted app/engine/runtime/dependency checks
were reused. No real package was signed or notarized, and no release was published.

The real shared guard supervised the changed native compile and headless checks.
One small live adapter check authenticated and admitted the existing destination
through the actual nested guard path, without any release writes.
Mocked stop cases do not claim a new live low-space incident or package-monitor
qualification; accepted shared-guard monitoring evidence retains its scope.
No GUI use, application launch, installation or publication occurred. Live
interaction, responsiveness and layout acceptance remain pending.

## Guarded delivery

Preview 28/build 32 was assembled using the accepted native executable without
a rebuild or functional rerun. Release/engine source is
`82f1950d3b943ca8e2cff1bac7c736ecd50bd994`; native source is
`f07c817cf4a769e46b5624615488d2018700df8f`. The real storage adapter admitted and
monitored assembly, signing, notarization and finalization. Source, app, upload
ZIP, release text and final download passed their sanitation boundaries.

Apple notarization `68ffcc89-7cde-4460-a40b-c0900af8300c` was Accepted. The new root
signature, stapled ticket validation and Gatekeeper passed once. The download is
29,071,405 bytes; HTTPS delivery returned HTTP 200. Publication completed in one
invocation with completed create/upload/publish operations and no manual retry.

Accepted 13 worker and 20 storage methods, the existing native compile and earlier
engine/policy/self-audit/runtime/dependency/icon evidence were reused. No GUI use,
app launch or installation occurred. This does not establish a live low-space
stop, live UI acceptance or a new engine-policy qualification.
