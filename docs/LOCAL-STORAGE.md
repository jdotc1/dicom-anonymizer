# Local artifact retention

## Cleanup — 24 October 2026

The unified checkout was already fully merged and pushed. Cleanup reduced its
local footprint from approximately 642 MB to 5.8 MB by removing ignored build
products and compiler/runtime caches. Git history was only a few megabytes and
was retained.

Across the inventoried DICOM development folders, allocated file storage fell
from approximately 15.70 GiB to 4.55 GiB: an 11.15 GiB reduction (71%). These are
filesystem allocated-block measurements, deduplicated by inode; APFS shared
extents and unrelated disk activity can make actual free-space changes differ.

Eight fully merged public feature branches and one obsolete public tooling
worktree were removed. The unified repository now has one checkout and `main`.
Release tags and published GitHub downloads were retained.

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
