# Receipt-driven release automation

`scripts/release.py` assembles a new distribution from accepted inputs. It does not
build the app, run application tests, execute the engine, re-hash accepted inputs,
or re-sign/re-verify unchanged nested dependencies. App interfaces and engine
policy are unchanged. Python 3.12 or later is required for the release tool;
end users continue to use the Python runtime bundled inside the app.

The recipe and provenance are repeatable. Signed archives are not promised to be
byte-identical: signing timestamps, notarization tickets, and ZIP metadata vary.
A successful packaging command is not runtime acceptance.

## Select accepted inputs

Commit the release tool and profile before planning a real distribution. Copy
`scripts/release-manifest.example.json` to a private release workspace outside the
repository. Example build/release numbers are placeholders, not published versions.
All input paths resolve relative to that manifest, except executable paths selected
from a receipt, which resolve relative to the receipt. Keep these local manifests,
receipts, keychain names, and output directories out of source control.

The manifest explicitly selects an accepted verification receipt, its immutable
40-character source commit, its accepted optimized native executable, and the
accepted build metadata. The per-app profile fixes the receipt selectors, bundle
identifier, and minimum OS so the other variant cannot be selected accidentally.
The receipt layout is the existing integration-receipt layout: variant commit
fields and a `builds.products` array. Missing selections fail closed.

`reuse_accepted_verification: true` is the release owner's explicit assertion that
the selected evidence was accepted and covers the selected native product and
baseline resources. The tool checks structural association and metadata; it does
not independently authenticate receipts or infer runtime acceptance from them.
Review this selection before any authorized release run. A different runtime,
icon, or resource bundle requires its own changed-input evidence and accepted
baseline. Do not use an arbitrary old bundle just because its version matches.

Accepted `BuildInfo.json` must match the selected source commit and app deployment
target, specify arm64 and the accepted compiler/SDK/language metadata, and include
Python version, distribution, release, and target. Use the metadata produced when
that executable was accepted; never substitute the current compiler's version.
No host compiler or dependency lookup is performed. The new build number must
increase from the selected baseline.

## Plan and assemble

Run from the checkout, substituting your private workspace paths:

```sh
python3 scripts/release.py plan --manifest /release-workspace/manifest.json
python3 scripts/release.py assemble --manifest /release-workspace/manifest.json --output /release-workspace/candidate
```

`plan` only reads the selection and Git metadata. `assemble` requires a new output
directory separate from the checkout and accepted inputs. It copies the accepted
baseline, replaces its main executable with the receipt-selected accepted product,
and extracts `engine/` from that exact accepted Git commit. Later working-tree
changes and untracked engine files cannot leak into the distribution. Unsafe
archive entries and mutable bundle symlinks are rejected. Assembly stages privately
and produces the output directory only after completion.

`BuildInfo.json` and `ReleaseInfo.json` distinguish the accepted executable/engine
`source_commit` from the release tooling's `release_source_commit`. Metadata is
written freshly, avoiding stale inherited candidate claims. Only the logical
`evidence_label` goes inside the app, not local evidence paths. The external
`selection.json` retains full input paths; **do not publish that file**. Publish only
the finalized `download.zip` and a deliberately sanitized release description.

## Explicit distribution stages

These commands perform real distribution operations and require release-specific
authorization. Assembly never invokes them automatically. The initial source-only
implementation did not run them against real apps. The subsequent authorized
use is recorded in [Release automation delivery](RELEASE-AUTOMATION-DELIVERY.md).

```sh
python3 scripts/release.py sign --output /release-workspace/candidate --identity 'Developer ID Application: Your Name (TEAMID)'
python3 scripts/release.py notarize --output /release-workspace/candidate --keychain-profile YOUR_PROFILE
python3 scripts/release.py status --output /release-workspace/candidate
python3 scripts/release.py finalize --output /release-workspace/candidate
```

Signing changes only the root app and checks that new root signature once, without
`--deep`. The previously accepted nested runtime signatures are retained.
Notarization creates a separate upload ZIP, submits once, records the request ID,
and queries its status. While it is pending, invoke `notarize` later to query the
same request. Once Accepted, its receipt is reused without another service query.
Finalization requires Accepted, staples, validates the new ticket, assesses the new
bundle with Gatekeeper, and creates `download.zip` after stapling.

Each stage records intent before calling an external command and completion after
success. Repeating a completed stage returns its stored result, without repeating
signing, validation, or archive creation. A completed step with different arguments
is rejected. The stage lock prevents concurrent mutations. Do not modify a staged
bundle, manifest, state, or archive between steps; receipts apply only to that
unchanged stage directory. Changed inputs require a new assembly directory.

A failed or interrupted external command leaves an uncertain step, not permission
to repeat it. Inspect the command diagnostics and reconcile its outcome first. If
submission returned an ID before interruption, adopt that existing request:

```sh
python3 scripts/release.py notarize --output /release-workspace/candidate --keychain-profile YOUR_PROFILE --submission-id EXISTING_REQUEST_UUID
```

If the ID is unknown, recover it from the notarization account history before
proceeding. Never blindly resubmit. Other uncertain steps require manual outcome
reconciliation; no force/retry/reset option bypasses a valid receipt. A stale lock
after a process crash may be removed only after confirming no release process is
still using that directory. Rejected notarization requires investigation, not a
repeat submission of unchanged inputs.

Publication and installation remain separate authorized operations. The tool does
not upload GitHub assets, push commits, or replace Applications. Never replace a
running installed app.

## Focused verification

The fixtures cover immutable source selection, resource preservation, variant and
metadata rejection, symlink safety, assembly rollback, locking, cached completion,
and interrupted-submission reconciliation. They qualify the tooling logic, not a
real notarized release. Existing app, engine, policy, UI, Python, and icon acceptance
remain reused rather than repeated.

## Engine-only updates with accepted native products

When native sources and resources are unchanged, reuse their accepted product.
The integration receipt may supply `builds.native_source_commits`, keyed by app
variant. Its native source must match the accepted metadata's explicit
`native_source_commit`; a distinct source cannot be inferred silently. Both
commits must resolve locally. `source_commit` remains the integrated acceptance
checkpoint selected for the engine. `engine_source_commit` records that identity,
while `native_source_commit` records where the reused native product was built.
`release_source_commit` separately records the release tooling tree. The actual
compiler metadata is reused from that native product; no rebuild is implied.
Receipts predating this distinction default both component sources to their
single accepted source. Four new isolated fixtures per app profile cover distinct
sources, missing/mismatched native metadata, and legacy selection; existing
packaging fixtures remain reused.
