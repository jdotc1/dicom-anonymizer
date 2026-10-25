# Bounded recovery-record reads

This source change is not yet released. The delivered app remains Preview 29/build
33. Public controls, engine policy, sidecar defaults and imaging processing are
unchanged.

Recovery inspection opens each record once with no-follow, nonblocking and
close-on-exec flags. Only a regular file between 1 and 65,536 bytes is eligible.
Reading stops after at most 65,537 bytes, allowing growth beyond the limit to be
rejected without allocating an unbounded buffer. Interrupted reads are retried;
other read errors retain uncertainty.

Descriptor identity, size and modification/change timestamps must remain equal
before and after reading. The path must still identify the same record before
the parsed snapshot is used. Directory inspection and acknowledgement use this
snapshot rather than opening a second potentially different record. Retirement
checks the snapshot identity again. If a cleaned record changes or cannot be
retired, inspection retains a warning through the existing recovery area.

No staging or output data is deleted by this change. These checks handle ordinary
concurrent file replacement and writes; they do not promise atomic conditional
unlink or protection against a privileged process manipulating the filesystem.

Focused evidence covers valid, empty, malformed and oversized records, growth,
truncation, replacement during/after reading, symlinks, FIFOs, stale retirement,
unreadable-record uncertainty and failed retirement of a changed cleaned record.
The real native target is compiled for macOS 13 arm64 with warnings as errors.
Headless file checks do not establish live UI or volume behavior. Accepted
unchanged engine, self-audit, runtime, dependency, icon and interaction evidence
is reused; no GUI use or app launch is required for this source increment.
