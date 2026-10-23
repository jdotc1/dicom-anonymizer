# DICOM Anonymizer — visual development roadmap

Updated 23 October 2026. This view tracks the public standalone macOS app. The current delivered milestone is Preview 10/app build 14.

![Delivered milestones, current release and proposed next priorities](roadmap/current-roadmap.png)

[Open the vector graphic](roadmap/current-roadmap.svg) · [Open the full-resolution image](roadmap/current-roadmap.png)

## Current development stage

The app has a delivered standalone macOS workflow, bundled Python, an app icon, signing/notarization, pre-publication output auditing, visible audit progress and focused recovery. This release improves disk-space messages and output-location recovery while retaining the existing interface and metadata policy.

The storage-recovery implementation reuses accepted optimized products and evidence: 27 new engine checks plus one intentionally changed publication regression per repository, 11 model checks per app, and native warning/output-replacement review. Earlier unchanged policy, runtime, icon and UI receipts remain in use. See [Storage recovery](STORAGE-RECOVERY.md) for the acceptance and delivery record.

## Proposed next priorities

1. **Automate release assembly and provenance.** Make accepted-product selection and release metadata/receipt association repeatable.
2. **Show initial scan activity.** Add files/folders-examined feedback inside the existing progress area without inventing a total.
3. **Evaluate more precise space estimation.** Keep this separate from reporting improvements; establish the changed requirements and test only the affected behavior.
4. **Resolve supported-input policy decisions separately.** Opaque payloads, unsupported structures, resource limits and conformance claims need explicit scope and approval before implementation.

These priorities are proposals, not scheduled commitments. The graphic separates delivered work from future work and decision-dependent scope. Its editable source is SVG, with Arial 10 pt text throughout; the PNG is a rendered copy.
