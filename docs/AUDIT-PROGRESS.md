# Output self-audit progress

The next source increment makes the pre-publication self-audit visible in the existing progress area. It does not change the metadata policy, audit rules, output report schema, or atomic publication contract.

## Event contract

After writing the staged files, the engine emits `audit_progress` with `audited_files` and `total_files`. The initial event reports zero. Subsequent events count each successfully audited file, throttled to every ten files and the final file. A file that fails its audit is never counted as successful. Existing three-argument `self_audit` callers remain supported and silent unless they supply a progress callback.

After all checks pass, the engine emits `phase` with `name: "finalizing"` before writing the report and publishing the batch. Only the existing complete event followed by successful process exit produces the completed-batch record.

## App behavior

Both app models keep audit counts separate from writing counts. During auditing, the existing progress area displays **Checking output** and **X of Y files checked**. At audit 100%, the batch remains busy and pre-publication. Finalization is indeterminate while the report and completed batch are published.

Malformed, regressing, mismatched, premature, and post-cancellation audit events are ignored. Writing and scan events cannot rewind an established audit/finalization phase. New operations reset the phase and counts. An older engine without the new events retains the existing generic finalization display after writing completes.

The app keeps its existing interface and macOS 13 minimum.

## Evidence and delivery

The engine callback tests use mocked reads/audit operations and temporary output. Five new tests passed once in each repository before integration; their results are reused for the unchanged engine implementation. Existing engine-policy, self-audit policy, runtime, icon, and prior UI receipts remain associated with their accepted inputs and were not rerun.

The final optimized public Swift target compiled with Swift 6.4.2, warnings as errors, and the arm64/macOS 13 target. All six new synthetic model checks passed. Native presentation at 700 × 655 content points showed audit counts and indeterminate finalization in light and dark, audit zero and full counts without a completion summary, and Cancel changing to the stopping state. The actual app model/views were driven by synthetic events; no DICOM batch was processed in this review. An earlier public compile predates final event guards and is not acceptance of the final source.

This increment follows Preview 7. That delivered app retains its own source and notarization receipt. Updating source on main does not replace the downloadable app.

## Preview 8 delivery

Preview 8 is app version 2.0/build 12, using accepted source `0509442` with release metadata updated in `448b324`. Apple accepted notarization `b326bfb9-63fe-4d5d-8aac-c38e25267f6a`; the new root signature, stapled ticket and Gatekeeper checks passed. The accepted optimized executable, focused test and native presentation evidence, and nested runtime signatures were reused. No unchanged engine, model, runtime, dependency or icon verification was repeated. Earlier preview tags and their acceptance records remain historical.

The final archive corrects inherited BuildInfo provenance to the accepted audit-progress source and actual compiler build. Only the changed metadata/root signature was reissued and notarized; accepted executable, test, runtime and UI evidence remained reusable. Superseded packaging receipts are retained locally.

## Follow-up source work

Cancellation/publication and failed-cleanup recovery are described in `PUBLICATION-RECOVERY.md`. They preserve the audit-progress event contract and reuse this increment's accepted evidence for unchanged inputs.
