# Local artifact retention

## Generated-artifact cleanup

Superseded generated build and validation payloads were retired while source,
current release inputs, original imaging inputs, reports, verification records
and logs were preserved. Detailed operator inventories are retained outside this
repository. Historical records do not imply that old generated payloads remain
available locally.

## Retention policy

Keep:

- The latest signed/stapled public app assembly and downloadable archive, for
  subsequent receipt-driven assembly without rebuilding unchanged inputs.
- The accepted native executable used by that release.
- Source, history, dependency pins, icon resources, receipts, logs and release
  journals. Retain bundle metadata when retiring superseded app copies.
- Original imaging data and validation evidence unless their retention is
  separately decided.

Retire after supersession:

- Compiler/module and SwiftPM caches, derived helper products, and local runtime
  download caches.
- Old app assemblies, installation backup copies and upload/download archives
  that are no longer the retained baseline.

Historical receipts remain historical evidence. Their old payload paths may be
intentionally retired; they are not a claim that every old package remains
locally available. A retired publication must not be resumed by deleting its
journal or bypassing selection safeguards. Keep the current release's selected
download intact for the active publication journal.

Cache removal does not require repeating accepted tests, builds, source hashes,
or signature/dependency checks. Reuse accepted receipts; perform only genuinely
changed-boundary validation on future work.

No app code or engine policy changed during cleanup. No GUI use, app launch,
installation, build, test, notarization or release was performed.

## Conservative retirement tooling — delivered with Preview 26

A plan-first companion command now supports bounded retirement of explicitly
selected finalized public artifacts, while protecting current inputs and keeping
receipts/logs. Ownership metadata is recorded only for freshly finalized future
releases; unbound legacy bundles/uploads are skipped. Generic cache sweeping is
not automated. See [Artifact retirement](ARTIFACT-RETIREMENT.md). No additional real cleanup was applied. Fresh ownership registration was
exercised for the separately authorized Preview 26 release.
