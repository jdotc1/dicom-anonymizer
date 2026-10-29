# Staging inventory and recovery-record write protection

Implemented locally for the next release. Preview 34/build 38 remains the
published download. The public interface, metadata-cleaning policy, supported
inputs, report fields and default-off JSON-sidecar setting remain unchanged.

## DICOM-only publication inventory

The default DICOM-only path now invokes the existing strict inventory checker
after writing the batch report and before output publication. It requires exactly
the operation's expected DICOM files and report, and their expected parent
directories. Unexpected files/directories, symlinks, non-regular files, missing
outputs and inspection errors prevent publication. This also applies when the
optional DICOM metadata audit was explicitly skipped; inventory checking does
not change the report's skipped metadata-audit status.

The directory must still have the allocation device/inode before and after
inventory inspection. A replacement staging directory is not published or
removed as if it belonged to the operation. Existing cleanup-uncertainty fields
remain in use. The initial staged DICOM audit also propagates traversal errors
instead of silently skipping unreadable directories. Known destination errors
retain the existing output-location recovery categories.

Cancellation is checked during inventory work. Sidecar discovery, cleaning,
auditing and progress events remain disabled unless explicitly requested. The
portable sidecar module's existing inventory checker is reused without changing
its policy or implementation. A guarded sibling-module loader preserves callers
that import the engine by filename without modifying process-wide `sys.path`.

## Recovery-record updates

The writer snapshots the record's device/inode, mode, size and modification/change
timestamps. It checks that snapshot before preparing an update and immediately
before replacement, detecting ordinary replacement and in-place changes during
serialization or synchronization.

Temporary files are created with unique names, exclusive creation and mode 0600,
relative to a pinned parent-directory descriptor. Creation and cleanup therefore
stay in the same original directory when its pathname is moved or replaced.
Cleanup removes only the temporary inode created by this writer; substituted
entries remain preserved.

After replacement, the writer requires the destination to identify the prepared
record, synchronizes the original parent directory, then checks the record again.
In-memory phase and identity advance only after these steps succeed. Any failed
update leaves the writer uncertain and blocks subsequent updates, including a
cleanup-phase write that could otherwise overwrite a foreign or unconfirmed
record.

Before output publication, such a failure prevents publication and cleans only
owned staging. After output publication, it preserves completed output and
reports publication uncertainty. Recovery records remain private operational
state and are not added to batch reports or output folders.

## Focused acceptance

Twenty-seven new synthetic methods passed:

- Ten default-inventory methods cover unexpected/missing entries, symlinks,
  FIFOs, traversal/stat errors, cancellation, staging replacement before/after
  inspection, report compatibility, disabled sidecar processing and isolated
  import-by-filename execution.
- Thirteen journal methods cover replacement/in-place modification during
  preparation, substitution after replacement/synchronization, write/replace/sync
  failures, parent replacement at creation or serialization, foreign temporaries,
  symlinks and successful updates.
- Four real engine/journal cases cover pre-publication refusal, post-publication
  uncertainty, uncertain directory synchronization and successful completion
  without publishing the recovery record.

The initial inventory fault cases reproduced thirteen missing refusals. Journal
fault cases demonstrated record-update gaps; source review also identified a
temporary-creation interval, reproduced by a new parent-swap fixture and corrected
with descriptor-relative creation. An isolated subprocess reproduced and then
confirmed the correction for import-by-filename compatibility. Only new cases
and cases affected by relevant implementation changes were run. Final read-only
review found no further actionable issue.

Temporary inputs/outputs are tiny synthetic fixtures and removed after each
method. Existing metadata/header/RTSTRUCT/sidecar policy, worker, native, runtime,
dependency, icon and unaffected recovery evidence is reused. No native source
changed and no native build was repeated. No GUI use, app launch, installation,
signing, notarization, push or publication is included in this source acceptance.

These safeguards detect ordinary concurrent mutations. They do not provide an
atomic conditional rename, an immutable filesystem snapshot, or protection from
every change after an audit or final identity check. No new pixel, contour,
retained-text or DICOM-conformance guarantee is claimed.
