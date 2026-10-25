# Bounded recovery-message aggregation

Delivered in Preview 33/build 37. Existing controls, engine policy, report schema and dependencies are
unchanged. No GUI use or app launch is part of this source acceptance.

## Text and detail limits

Recovery inspection retains at most eight complete record details and limits the
resulting message to 16 KiB of UTF-8 text. The byte budget includes numbering,
locations, separators, the total/omitted counts and recovery instructions. A
512-byte reserve covers the fixed summary text and count values.

Oversized details are omitted as whole entries; paths and instructions are not
clipped. Later smaller entries may still fit. The summary reports the total
number of notices needing review and exactly how many details were omitted.
Its existing reveal control points to the recovery-record directory, and the
message instructs review of every record before another batch. A single complete
notice that fits retains its existing message and original recovery location.

## State and records

Inspection continues through the full listing after either limit is reached.
Staging ownership and possible-publication flags are accumulated from every
notice, including omitted and malformed records. Live-owner and pending-location
state continue to be computed independently of displayed details. A later record
cannot lose uncertainty because earlier details filled the text budget.

The display cap performs no record deletion or content rewrite. Unresolved
records, staging and output data remain untouched. Existing identity-checked
retirement of records already marked cleaned is unchanged; this increment does
not replace the recovery-record lifecycle with a new retention policy.

The bounded accumulator replaces the unbounded array of full notices. Directory
listing and sorting are unchanged and still scale with the number of directory
entries; the limit concerns retained notice text, not a bound on total directory
size or filesystem inspection time. Per-record bounded reads remain in force.

## Focused acceptance

Nine new headless cases cover:

- A twelve-notice backlog, eight complete rendered details, exact omitted count,
  preserved record bytes and the directory recovery location.
- A single oversized Unicode detail and a byte limit reached before the item cap.
- Late publication uncertainty, staging ownership, live owners and pending state.
- A malformed record beyond the cap, and a small detail after an oversized one.
- Unchanged single-notice and empty-listing behavior.

The initial new backlog and oversized-single cases demonstrated the old unbounded
behavior. Seven new cases then passed with the accumulator, followed by two new
late-record cases. Review strengthened the backlog's rendered-detail assertions;
only that changed selector was repeated. All nine cases passed as composite
evidence on synthetic records. Generated records and staging fixtures are removed
after each case. No imaging data or binary fixtures are committed.

The real optimized native target is compiled for macOS 13 arm64 using Swift 6
and warnings as errors. This is compile-only app evidence plus headless filesystem
coverage; it does not establish live recovery-area appearance or interaction.
Accepted engine, file-header audit, sidecar, runtime, dependency, icon, worker and
unaffected recovery evidence is reused. Source acceptance did not include signing,
notarization, publication or installation; authorized delivery followed separately.

## Guarded delivery

Preview 33/build 37 reused the accepted native executable and source evidence
without rebuilding or repeating functional tests. Accepted native/engine source
is `5ebaa55481308ec33169e0420fe10a8c31d9f8e4`; release source is
`9309ccd9cfb44ee001c36c16c84f64858637862b`.

New distribution sanitation, root signature, stapled ticket and Gatekeeper checks
passed. Apple notarization `56644144-8688-4f60-8215-7b54b8501a84` was Accepted.
The 29,079,716-byte ZIP was published through the guarded journal without retrying
a GitHub mutation. Prior releases and signed downloads remain preserved. No GUI
use, app launch or installation occurred.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.33).
