# Conservative local artifact retirement

## Scope — 24 October 2026

`scripts/retire_artifacts.py` is a stdlib companion to the release tooling. It
creates a concrete plan by default; deletion requires a separate explicit apply
command using that existing plan. It does not build, test, sign, notarize,
publish, launch, install or contact GitHub.

This local tooling increment follows Preview 25/build 29. App interfaces and
engine policy are unchanged. No live release folder was cleaned while developing
or testing this command.

## Plan, review, apply

Use canonical absolute paths to an explicit current finalized public release,
explicit superseded finalized public release folders, and a plan outside source
and release/input paths. Example paths below are placeholders:

```sh
python3 scripts/retire_artifacts.py \
  --current Release-Current/public \
  --superseded Release-Previous/public \
  --plan-file Retirement/plan.json
```

The parent directory for the plan must exist. Review the printed candidate and
skipped paths and the saved JSON plan. Planning deletes nothing and refuses to
overwrite an existing plan. Then, only when retirement of that plan is intended:

```sh
python3 scripts/retire_artifacts.py \
  --plan-file Retirement/plan.json --apply
```

Apply refuses new planning arguments. It locks the plan directory and all
selected release folders, rechecks current inputs and release metadata, and
preflights all entries before deletion. A sibling `plan.json.journal.json`
records each started/retired operation and retained bundle metadata. Neither
original release receipts nor publication journals are rewritten.

## Eligibility and protection

Only these exact children of explicitly selected older public releases are
candidates:

- `DICOM Anonymizer 2.0.app`
- `download.zip`
- `notarization-upload.zip`

All other files remain, including receipts, logs, source, reports and imaging
data. The command does not sweep arbitrary caches, workspaces, private releases,
installed apps or user data. Generic cache retirement remains outside this
version until caches have explicit creation/ownership records.

Release records must agree on public identity, tag, build and immutable target;
notarization/distribution and publication operations must be complete. Incomplete
or uncertain releases are refused. Only builds older than the declared current
release are eligible. Source checkouts and overlapping roots are refused.

The current folder, its accepted executable, baseline assembly, accepted receipt
and build-metadata paths are protected. Current app/download/executable existence
is checked again at apply time. Candidates sharing an inode with protected
inputs are skipped/refused, so even hardlinked archive metadata is protected.

## Ownership and legacy artifacts

A completed publication already binds `download.zip` to filesystem identity.
Retirement requires that recorded identity to match; it never adopts a
replacement archive merely because its name is familiar.

For future releases, a finalization that **newly creates** its download also
writes `artifact-ownership.json`, binding generated artifacts to filesystem
metadata at finalization. This records metadata only, without hashes or repeated
accepted checks. It refuses an existing ownership file or symlink. Completed
legacy finalization steps are reused without backfilling ownership records.

Bundles and upload ZIPs lacking recorded creation ownership are retained and
listed as skipped. This command intentionally cannot automatically retire every
legacy artifact from before ownership recording. A bound legacy download may
still qualify. Current release inputs remain protected in all cases.

## Replacement, traversal and interruption handling

Plans capture entry-by-entry filesystem metadata and retain Info.plist,
BuildInfo.json and ReleaseInfo.json when available. Apply compares against the
reviewed plan and creation/publication bindings. Plan edits after retirement
starts are refused. These are ordinary replacement checks, not cryptographic
identity or privileged-attacker protection.

Artifact root symlinks and symlink ancestors are refused. Internal bundle links
are recorded without following targets. Traversal errors, cross-device entries,
special files and embedded source checkouts stop progression. Directory removal
requires the platform's symlink-resistant removal implementation. External
concurrent mutations are not covered by an atomic filesystem transaction.

An interrupted deletion remains started in the journal. If the selected path is
already absent, resume may reconcile that absence without another deletion. If
it still exists, the command stops for inspection of partial deletion or
replacement. It does not automatically retry partial removal. A retired path
that reappears is also refused. Reapplying a fully completed unchanged plan is a
no-op.

## Focused evidence

Twenty-six new synthetic fixture methods passed as composite evidence: fifteen
initial cases, nine new ownership/traversal/CLI/finalization cases, one missing
current-download case and one broken-ledger-link case. Six affected initial
eligibility/deletion cases were repeated after the ownership changes; all other unchanged
passing cases were reused. Read-only review identified and resolved archive
replacement, missing current inputs, traversal/mount and dangling-ledger guards;
final focused review found no blockers.

No accepted package, native executable or historical evidence was rehashed or
reverified. Existing app/engine/packaging/publication receipts were reused. No
GUI use, app launch, native build, signing, notarization, installation, network
publication or real artifact deletion occurred. Live behavior of the new
ownership registration remains untested until a separately authorized release.
