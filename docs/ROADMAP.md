# Maintenance roadmap

Status: feature development is paused indefinitely and the repository is in
maintenance mode. The latest release is Preview 37 (app build 41, engine policy
2.0-build6). Nothing in the "awaiting decision" or "deferred" sections below has
been implemented, and none of it is scheduled. Behavior statements come from source
reading and small synthetic experiments, not real clinical data. Statements marked
"unconfirmed" rest on recollection or secondary sources and must be checked against
the primary source (the DICOM Standard, regulations, vendor documentation) before
anyone relies on them.

## Delivered

- Standalone macOS app (arm64, macOS 13+) with a bundled Python runtime and a Python engine for MR, CT and RTSTRUCT batches; see the [README](../README.md) and [data handling](DATA-HANDLING.md).
- Pre-publication self-audit, staged-file header audit, structured audit coverage in reports, strict DICOM-only staging inventories, descriptor-pinned input reads, default-off MRI JSON sidecar cleaning.
- Interruption and publication recovery, bounded recovery messages, guarded atomic publication.
- Receipt-driven release tooling with resumable publication, preflight checks and publication-safety gates.
- Since Preview 36: dictionary-VR clearing of identity-bearing elements (policy 2.0-build6), `--explain`, `--verify-output`, an engine-interface reference with contract tests, a documented output-permission contract, a synthetic benchmark, a canary retention survey with policy-table lint tests, and manual-only test and lint scripts. See [Maintenance](MAINTENANCE.md).

## Awaiting maintainer decision (supported-input and policy)

Each item is a question about what the tool should accept or assert. Several would
narrow accepted input or change output, so each needs an explicit decision, tests
and a policy-version bump before implementation.

- **Opaque binary payloads.** Binary attributes the engine cannot inspect (embedded documents, ICC profiles, waveform data, selector value attributes) currently pass through unexamined. Options: retain and document, reject when present and non-empty, delete and count, or tiered handling. The exact attribute set is unconfirmed.
- **Command-set elements and DICOMDIR.** A directory-record file stops the batch with the generic unsupported message, and stray group 0000/0004/0006 elements inside accepted images pass through. Options: document, reject with a fixed message and strip length/offset elements, or exclude with a count.
- **Extensionless file detection.** Files without a preamble or extension are probed and silently excluded if no key UID is found, so excluded files can include undetected DICOM. Options: keep and document, add reason counters, or a shallow magic-byte check (which would lose preamble-less implicit-VR files).
- **Parser and resource limits.** The DICOM path has no bound on file size, element length, nesting depth, header count, batch size or time per file. Synthetic measurements showed memory near 64 times file size for a decimal-string-heavy structure set. Starting values would need real-world maxima. Also open: rejecting truncated pixel data.
- **New modalities and the RT family.** Admission by SOP Class rather than the Modality string; a fail-closed rule that text-capable attributes in newly admitted objects are cleared unless allowlisted; then which objects (RT dose, RT plan, registrations, segmentation, RT image and treatment records, PET) and in what order. Plans carry a large retained-text surface, and registrations across patients are rejected by design.
- **Conformance claims.** Whether to add an independent, bounded check of the de-identification tables transcribed from the primary Standard text, and which public claims (conformance, comparisons with other tools, data-sharing guidance) to make. Today the self-audit shares policy lists with the cleaner and is not an independent oracle.
- **Ages over 89.** PatientAge is retained verbatim. Options: retain, cap year-unit values above 089Y to 090Y, or remove. The regulatory wording is unconfirmed.
- **Truthfulness of de-identification markers.** What outputs should assert about themselves (identity-removed marker, method text, method code sequence) given that pixel data is not assessed. Direction under consideration: delete inherited method code sequences, add no new claim.
- **Retired and UC attribute clearing.** Clearing free-text (UC) values and retired order-number attributes, and aligning policy text with what is enforced, batched into one policy bump.
- **Deterministic UIDs and cross-batch linkage.** Random UIDs per run are the current behavior. Keyed or deterministic derivation would create a recoverable linkage, so it is not assumed; related questions are visit ordering, a crosswalk helper and patient subset lists.
- **Burned-in text.** Header-only advisory triage versus on-device OCR screening. A zero advisory count could reassure falsely, and recognized text must never be stored.
- **Private tags.** Keep the current behavior (private tags are removed) and document it, adopt an allow-list, or change it. No allow-list is planned without a concrete need.
- **Sandboxing and local-only enforcement.** Whether "no network" should be enforced by the operating system (entitlement assertion in preflight, allowlisted worker environment, path-free copied diagnostics, an App Sandbox prototype). Sandboxing may break exclusive-rename publication and external-volume access (untested).

## Deferred engineering (not started)

- **Deterministic UID factory with golden-output tests**, as groundwork for equivalence evidence.
- **Hot-path performance work** (raw pass-through of bulk numeric strings, relaxed parser validation, patient-sharded parallel processing). Deferred behind parser limits and equivalence tests; each could change accept/reject behavior. See [Performance](PERFORMANCE.md).
- **Native test runner**, so the app's checks can be run by one command; it would precede any restructuring of the native source.
- **Retained-content review sheet** for pre-share checks.
- **Scan-time problem inventory**: report every rejection of a rejected batch in one pass, value-free, instead of one error at a time (this changes error text and event fields, so it is an interface change).

## Release hygiene

- Pin GitHub Actions in the manual workflow to commit SHAs. The workflow is manual-only with read-only permissions today.
- Other supply-chain items awaiting a decision: runtime re-pin with precompiled bytecode, recording a SHA-256 at finalize, immutable releases, a dedicated offline signing key for tags and checksums, a Python version matrix after 3.10 end of life, an SBOM and advisory register. Platform and service behavior behind these is unconfirmed.

## Known limits of `--verify-output`

- Not an independent conformance check: it reuses the engine's own audit.
- RTSTRUCT reference closure is strict: a tree whose structure sets reference images that were not in the source batch fails.
- No per-file digests are stored in the report, so an edit that stays audit-clean is detected only by comparing a `tree_sha256` recorded from an earlier run.
- It always states `source_uid_check: not_performed`; leaked source UIDs can only be found with the source.
- Trees containing JSON sidecar output are refused.
- It does not handle SIGINT or SIGTERM cancellation.

## How decisions are made

Policy changes are batched into one policy-version bump per release (see
[Maintenance](MAINTENANCE.md)). A decision needs the primary-source check noted
above, a synthetic test for each new accept, reject or clear behavior, and a
statement of whether it narrows accepted input. The [visual roadmap](ROADMAP-VISUAL.md)
shows milestones.
