# DICOM Anonymizer — visual development roadmap

Updated 29 October 2026. This view tracks the sole ongoing public app. The current delivered milestone is Preview 35/app build 39: unified public UI, folder and interruption recovery, optional MRI JSON sidecars, worker feedback, bounded recovery-record reads/messages, RTSTRUCT label enforcement, staged-file header auditing, structured audit coverage, strict DICOM-only staging inventories, recovery-record write protection and guarded publication.

The graphic below is the retained storage-recovery milestone snapshot, before the release-automation delivery. Current delivery is stated above; the unchanged graphic was not rerendered or reverified.

![Storage-recovery milestone snapshot](roadmap/current-roadmap.png)

[Open the vector graphic](roadmap/current-roadmap.svg) · [Open the full-resolution image](roadmap/current-roadmap.png)

## Current development stage

The app has a delivered standalone macOS workflow, bundled Python, an app icon, signing/notarization, pre-publication output auditing, visible audit progress and focused recovery. Current delivery includes allocation-aware disk-space estimates, scan/audit and sidecar feedback, and worker-event reliability, with the existing metadata policy retained. Live sidecar interaction, startup/recovery, responsiveness and compact-window appearance checks remain pending under the no-GUI restriction.

The storage-recovery implementation reuses accepted optimized products and evidence: 27 new engine checks plus one intentionally changed publication regression for the public app, 11 model checks, and native warning/output-replacement review. Earlier unchanged policy, runtime, icon and UI receipts remain in use. See [Storage recovery](STORAGE-RECOVERY.md) for the acceptance and delivery record.

Release assembly and provenance automation is now delivered. See [the delivery record](RELEASE-AUTOMATION-DELIVERY.md); accepted app behavior and verification are retained.

Initial scan activity is now delivered: files/folders examined appear without a total. See [Scan progress](SCAN-PROGRESS.md).

Allocation-aware disk-space estimates are now delivered. See [Disk-space estimate](SPACE-ESTIMATE.md).

## Latest delivered increment

The latest app delivery is Preview 35/build 39: strict DICOM-only staging
inventories and conservative recovery-record updates. Audit-coverage reporting
retains separate DICOM/sidecar statuses and retained-content limitations. Recovery-message
text remains bounded while complete inspection and uncertainty flags remain in use. File-header and
RTSTRUCT label audits remain in place. Existing publication, terminal-event and
Copy Details behavior is retained. Prior releases and signed downloads remain
preserved. Accepted source/functional evidence was reused; only new distribution
boundaries were checked. See [Staging and journal protection](STAGING-JOURNAL-PROTECTION.md).
The graphic remains a historical snapshot, and live interaction acceptance
remains pending.

## Audit-coverage delivery

Structured audit coverage is delivered in Preview 34/build 38. Reports
separate DICOM and optional JSON-sidecar audit status/counts and explicitly name
retained-content limitations. Five new synthetic report-boundary cases passed;
unchanged verification is reused. This changes reporting only, with no interface
or engine-policy change. Accepted verification was reused for guarded delivery;
no functional test or native build was repeated. See
[Audit coverage](AUDIT-COVERAGE.md).

## Staging and journal protection delivery

Strict DICOM-only staging inventories and recovery-record write protection are
delivered in Preview 35/build 39. Twenty-seven new synthetic methods passed as focused
evidence, with unchanged policy/native/runtime verification reused. The public
interface and metadata policy remain unchanged. No GUI use, app launch, installation
or repeated functional test/native build occurred during guarded delivery.
See [Staging and journal protection](STAGING-JOURNAL-PROTECTION.md).

## Earlier resilience milestone

Interruption recovery records operation ownership/publication state and uses the existing recovery area without automatic resume/deletion. Resumable publication binds a finalized archive to a draft release and reconciles uncertain remote outcomes. Focused synthetic/mock evidence was reused for Preview 19; its first live authenticated publication completed using the new tooling. No GUI use or app launches occurred.

## Recovery lifecycle delivery

Recovery records are aggregated in the existing area, cleaned local records are retired with identity checks, and live owners trigger guarded background reinspection. A headless harness covers the real worker process/pipe boundary. This increment is delivered in Preview 20/build 24; accepted engine/policy and unchanged runtime evidence were reused. See [Recovery lifecycle](RECOVERY-LIFECYCLE.md).

## Recovery explanation delivery

Recovery explanations distinguish confirmed folder identity, uncertain publication and the next inspection step. New headless cases cover the actual worker launch through the batch model’s final state, including cancellation, malformed output and nonzero exits. Source acceptance is separate from live interaction; this increment is delivered as Preview 21/build 25. See [Recovery explanations](RECOVERY-EXPLANATIONS.md).

## Output-location recheck delivery

Valid unresolved recovery locations are rechecked through the existing guarded background chain, including restoration/replacement, with explicit protection for a newer successful output choice. Headless subprocess-to-model cases cover record acknowledgement/retention and preservation of batch data. This increment is delivered as Preview 22/build 26. See [Output-location rechecks](OUTPUT-LOCATION-RECHECKS.md).

## Publication visibility delivery

Publication tooling now reconciles delayed release/asset/published-tag visibility through bounded reads and preserves the existing journal, archive selection and ownership safeguards. Seventeen new mocked methods passed as composite evidence; the changed tooling is used for the Preview 23 release, with the accepted native executable reused. Mock timing guarantees remain separate from live service behavior. See [Resumable publication](RESUMABLE-PUBLICATION.md).

## Recovery-state feedback delivery

Recovery inspection failures are distinct from empty listings and retain prior uncertainty, including after live-owner-only observations. Successful completion with unresolved local-record acknowledgement now retains the result and shows a nonblocking warning through existing controls. This increment is delivered as Preview 24/build 28. See [Recovery-state feedback](RECOVERY-STATE-FEEDBACK.md).

## Recovery consistency delivery

Outstanding acknowledgement warnings are independent of report-error presentation, and single-use generation tokens protect recovery results and scheduled refreshes from intervening actions. Fourteen new headless cases passed; this increment is delivered as Preview 25/build 29. See [Recovery consistency](RECOVERY-CONSISTENCY.md).

## Artifact retirement tooling delivery

Conservative artifact retirement plans first, protects current release inputs and evidence, and requires a separate apply command. Fresh finalizations record metadata ownership for future retirement; legacy unbound bundles/uploads remain retained. Twenty-six new fixture methods passed as composite evidence. This tooling is delivered with Preview 26/build 30; fresh ownership registration was exercised, and no real retirement plan was applied. See [Artifact retirement](ARTIFACT-RETIREMENT.md).

## Decision-dependent future scope

Terminal-event consistency and improved diagnostics in the existing Copy Details
action are delivered in Preview 29/build 33, preserving the public UI and engine
policy. See [Terminal diagnostics](TERMINAL-DIAGNOSTICS.md).

Bounded worker-event buffering and monitored release-storage admission are
delivered in Preview 28/build 32, reusing focused headless evidence and the
accepted compile-only native build. See
[Worker and storage bounds](BOUNDED-WORKER-STORAGE.md). The dated graphic above
remains unchanged; it was not rerendered or reverified.

1. **Resolve supported-input policy decisions separately.** Opaque payloads, unsupported structures, resource limits and conformance claims need explicit scope and approval before implementation.

These priorities are proposals, not scheduled commitments. The graphic separates delivered work from future work and decision-dependent scope. Its editable source is SVG, with Arial 10 pt text throughout; the PNG is a rendered copy.
