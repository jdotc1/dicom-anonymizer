# Output self-audit progress

The next source increment makes the pre-publication self-audit visible in the existing progress area. It does not change the metadata policy, audit rules, output report schema, or atomic publication contract.

## Event contract

After writing the staged files, the engine emits `audit_progress` with `audited_files` and `total_files`. The initial event reports zero. Subsequent events count each successfully audited file, throttled to every ten files and the final file. A file that fails its audit is never counted as successful. Existing three-argument `self_audit` callers remain supported and silent unless they supply a progress callback.

After all checks pass, the engine emits `phase` with `name: "finalizing"` before writing the report and publishing the batch. Only the existing complete event followed by successful process exit produces the completed-batch record.

## App behavior

Malformed, regressing, mismatched, premature, and post-cancellation audit events are ignored. Writing and scan events cannot rewind an established audit/finalization phase. New operations reset the phase and counts. An older engine without the new events retains the existing generic finalization display after writing completes.

## Evidence and delivery
