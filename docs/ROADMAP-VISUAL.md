# DICOM Anonymizer — visual development roadmap

Updated 23 October 2026. This view tracks the public standalone macOS app. The current delivered milestone is Preview 14/app build 18.

The graphic below is the retained storage-recovery milestone snapshot, before the release-automation delivery. Current delivery is stated above; the unchanged graphic was not rerendered or reverified.

![Storage-recovery milestone snapshot](roadmap/current-roadmap.png)

[Open the vector graphic](roadmap/current-roadmap.svg) · [Open the full-resolution image](roadmap/current-roadmap.png)

## Current development stage

The app has a delivered standalone macOS workflow, bundled Python, an app icon, signing/notarization, pre-publication output auditing, visible audit progress and focused recovery. This release adds allocation-aware disk-space estimates while retaining the interface, initial scan-progress feedback and metadata policy.

The storage-recovery implementation reuses accepted optimized products and evidence: 27 new engine checks plus one intentionally changed publication regression per repository, 11 model checks per app, and native warning/output-replacement review. Earlier unchanged policy, runtime, icon and UI receipts remain in use. See [Storage recovery](STORAGE-RECOVERY.md) for the acceptance and delivery record.

Release assembly and provenance automation is now delivered. See [the delivery record](RELEASE-AUTOMATION-DELIVERY.md); accepted app behavior and verification are retained.

Initial scan activity is now delivered: files/folders examined appear without a total. See [Scan progress](SCAN-PROGRESS.md).

Allocation-aware disk-space estimates are now delivered. See [Disk-space estimate](SPACE-ESTIMATE.md).

## Proposed next priorities

1. **Resolve supported-input policy decisions separately.** Opaque payloads, unsupported structures, resource limits and conformance claims need explicit scope and approval before implementation.

These priorities are proposals, not scheduled commitments. The graphic separates delivered work from future work and decision-dependent scope. Its editable source is SVG, with Arial 10 pt text throughout; the PNG is a rendered copy.
