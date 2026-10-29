# Early release-capacity planning

`scripts/release_preflight.py` produces a read-only advisory report before release
assembly. It adds no app interface or engine-policy change. Run it before
allocating another release destination, using the explicit private guard policy
and registry files for the machine that will package the app:

```sh
python3 scripts/release_preflight.py \
  --current Release-Current/public \
  --output Release-Next/public \
  --guard-policy Guard/policy.json \
  --guard-registry Guard/state/registry.json \
  --superseded Release-Older/public
```

The paths above are placeholders. Keep the resulting report and supplied guard
files private; they contain local paths. The command prints JSON to standard
output and does not create the candidate, retirement plans, locks or files. It
does not invoke distribution tools or modify the guard registry or thresholds.

## What the report establishes

The adapter supports registry version 1 and a positive integer export-root limit,
including the exact Git-common-directory project override. It resolves the
current checkout's common directory and inspects only that project's registered
root kinds. Existing and active export paths count against the limit. Missing
inactive paths are listed as stale for prediction, without removing them from
the registry. Missing active paths still count, and unclassified active
destinations for the project count conservatively as potential exports.

The capacity status is `available`, `retirement_needed` or `active_destination`.
Proposed assembly output must be new and separate from source and protected
current-release inputs. A current finalized release is required; its metadata
provides the protected baseline, accepted executable, receipt and build-metadata
paths. Explicit older-release arguments are classified as protected,
metadata-eligible for retirement planning, or not metadata-eligible. Duplicate
and overlapping older roots are refused.

Malformed or unsupported snapshots fail closed. No package tree is traversed,
and no source/export hash, signature or accepted verification is repeated.
Metadata eligibility is deliberately separate from artifact ownership and
identity qualification: the existing retirement planner must perform its
ordinary replacement and protection checks before producing a concrete plan.

## What it does not authorize

The report always states `admission_authorized: false` and
`reserve_checked: false`. Snapshots can become stale and are not reservations.
Check free-space reserve with the supported guard command:

```sh
storage-guard check --path Release-Next/public
```

That check also does not reserve an export slot. Actual assembly and distribution
must continue through the authenticated guarded release workflow. No report
status waives a later guard refusal.

When capacity is full, the report supplies arguments for the existing
`retire_artifacts.py` plan-only command and identifies the explicit older
metadata candidates. Review the resulting plan and obtain explicit retirement
approval before using its separate apply command. No cleanup is automatic.

Removing an old app and ZIP children alone does not free the registered directory
while receipts or other files remain. Preserving that metadata and retiring the
obsolete directory requires a separately approved operation. This preflight does
not move evidence, remove directories, resume partial deletion, or alter existing
retirement journals.

## Focused evidence

Sixteen new tiny fixture methods cover available/full capacity, exact project
overrides, build/export distinction, stale and active roots, active destinations,
protected baselines, incomplete candidates, output protection, duplicate roots,
symlink snapshots, malformed versions/shapes and absence of package traversal.
Two initial CLI cases first failed because the command did not exist, then
passed. Fourteen additional methods passed after a duplicate-argument case first
demonstrated an invalid retirement recipe and was corrected. The original two
passing methods were reused rather than repeated.

Fixtures verify that guard snapshots and historical evidence remain unchanged
and no candidate output is created. Temporary synthetic files are removed after
each method. No accepted test suite, native build, real package scan, GUI use,
app launch, admission, retirement, signing, publication or installation occurred.
This source increment is not yet part of a published app release.
