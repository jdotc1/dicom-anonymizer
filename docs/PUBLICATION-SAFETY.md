# Enforced publication sanitation

The pre-push hook and release tools share `scripts/publication_safety.py`.
No source file, app, archive, or history is rewritten by this checker. A finding
stops the operation. Repair the changed input locally, then check that change.
Do not redact executable paths blindly, delete journals, or disable the gate.

## Push boundary

A persistent dispatcher copied from `.githooks/pre-push` into the private Git
common directory examines every non-deletion ref supplied by
Git, including annotated tags. All newly exposed reachable objects are checked,
so deleting a sensitive file in a later commit does not hide its earlier content.
Commit author/committer metadata, complete messages, tag messages, changed path
names and new blob contents are included. Unrelated ancestry is not implicitly
accepted. Git replacement objects and grafts are disabled; shallow histories,
new submodules and uninspected LFS pointers are refused.

Successful Git object IDs are retained privately in the Git common directory.
A commit is accepted only after all newly exposed reachable objects pass. The
existing owner-selected sanitation acceptance is a separate baseline: its commit
and the filesystem identity of its private evidence record must be selected
explicitly. Missing or replaced baseline evidence stops the gate; it never
silently rescans sealed history. Do not select an unreviewed commit as a baseline.

Local setup on another checkout requires an existing accepted commit and evidence:

```sh
python3 scripts/publication_safety.py install \
  --accepted-source ACCEPTED_COMMIT --evidence "$ACCEPTED_SANITATION_EVIDENCE"
```

The installer preserves unrelated custom hook configurations by refusing to
replace them. The disabled hooks setting may be replaced with this requested
hook. The hook path is configured locally and is not embedded in tracked files.
The dispatcher remains installed across branch switches; a branch without the
checker is refused rather than silently becoming unguarded.
Normal `git push` now runs the gate; this command does not perform a push.

## Release boundaries

Signing, notarization and finalization inspect the selected app before invoking
external distribution commands. The notarization upload ZIP is checked before
submission. The final download ZIP is checked before ownership finalization.
Publication checks the selected immutable source, title, notes and download
before creating a publication journal or making a GitHub API call. Existing
publication authorization, immutable selection, ownership, uncertain-outcome and
read-only reconciliation safeguards remain in force.

Private selection/journal/ownership files belong beside the app, never inside the
distribution. Source repositories, private workspace directories, credential files,
and imaging inputs are refused in new source/distributed members. Unsupported
compressed containers fail closed; supported nested ZIPs are inspected with size
and depth limits. Archive names, member metadata, comments, container bytes and
contents are inspected without extraction. Absolute and escaping symlinks are
refused. UTF-8/ASCII and both UTF-16 byte orders and alignments are inspected,
including strings embedded in binaries.

Rules cover machine home paths, local work roots, encoded home identifiers,
session scratch paths, configured personal email patterns, private correspondence
and workspace markers, unrelated internal application names, and recognizable credential formats. Errors name the rule
and object category without printing the matched private text. Test fixtures use
synthetic values assembled at runtime, not real private examples.

If a newly created download fails sanitation, its ownership-pending state remains
in the distribution journal. A resume can finish inspection and ownership without
repeating completed distribution commands. Legacy archives lacking that marker
are never adopted as freshly owned artifacts.

## Reuse and limits

Receipts live only in the Git common directory. Git contents use immutable object
IDs; release text uses its in-memory content digest. Apps reuse unchanged regular
file device/inode/size/mtime/ctime identities, and archives reuse the complete
selected file identity. These metadata identities detect ordinary replacement;
they are not cryptographic archive equality or privileged-attacker protection.
Failed inputs are never accepted. Pattern changes invalidate receipts; increment
`SCANNER_VERSION` when inspection semantics change without changing patterns.
Existing history acceptance is explicit and separate from generated receipts.

The checker is a deterministic publication guard, not a complete semantic privacy
review, a secret detector for every credential format, image OCR, or a proof of
complete anonymity. New private terminology or formats require explicit policy
and focused coverage. It never treats compilation, notarization, restored release
metadata, or an old functional test as artifact sanitation evidence. Old published
assets are not scanned merely by installing the gate.

Local hooks can be bypassed by changing Git configuration or using `--no-verify`.
Fresh clones must install the hook and select accepted history evidence before
publication. Direct external publication commands bypass these tools. Server-side
protection is separate and has not been configured by this change. There is no
claimed remote enforcement or live publication acceptance.

## Focused implementation evidence

Thirty-eight new synthetic sanitation methods passed as composite evidence,
including Git/history/tag boundaries, receipt reuse and invalidation, binary and
nested-archive inspection, private file types, symlink/overlay handling, lifecycle
refusal and recovery. Six affected existing publication/distribution/ownership
methods also passed. Two new fixtures initially mixed canonical and unresolved temporary paths;
only those failed fixtures were corrected and repeated. Other
repetitions followed relevant implementation changes. Existing app, engine,
self-audit, runtime, dependency, signing and publication evidence was reused.
No native build, real artifact scan, GUI use, app launch, installation, signing,
notarization or publication was performed for these fixtures.

Read-only review identified history substitution, compressed payload, symlink,
ZIP overlay, commit-cache and pending-ownership hazards; the implementation and
focused fixtures address them. Local hook installation imports the existing
sanitized-history acceptance instead of scanning that history again.
