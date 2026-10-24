# Resumable public publication

`scripts/publication.py` is a separate, stdlib companion to `release.py`. It does
not build, sign, notarize, launch, install, or rerun accepted verification.
Its only target is `jdotc1/dicom-anonymizer`; repository metadata must say public.
Use authenticated `gh` as `jdotc1`, after explicit authorization for this release.

Only a finalized assembly can be selected. The existing state must record
completed signing, strict signature, stapling, ticket validation, Gatekeeper and
download creation, plus Accepted notarization. Assembly, public profile, release
selection, tag, build and immutable target must agree. Only its `download.zip`
is uploaded, under a deterministic public filename.

Example for a future authorized release (not an instruction to publish now):

```sh
python3 scripts/publication.py --output /path/to/finalized-assembly \
  --title 'DICOM Anonymizer Preview N' --notes-file /path/to/release-notes.md \
  --authorize-publish
```

The local `publication.json` binds the original selection, archive filesystem
identity, release text and random asset label. A lock prevents concurrent local
publication. Each mutation is journaled before invocation. Resume with exactly
the same arguments: release/tag, asset and publication state are read back before
any mutation. Existing unrelated releases/assets are never overwritten or
deleted. A matching size alone cannot adopt an asset: the unique journal label
must also match. A draft tag may not exist until GitHub publishes it; any
existing tag must resolve to the selected commit, including annotated tags.
Publication checks the final tag again.

If a lost response actually completed, readback adopts that result without
repeating the mutation. If the outcome is absent, stop and inspect GitHub first.
`--retry-absent` explicitly permits retry only after a new absence readback.
An operation previously recorded completed but now missing always stops. Network
or permission failures are never evidence of absence. Do not remove journals or
locks to bypass an unresolved outcome. Preserve local state outside the archive.

## Evidence limits

No archive is rehashed. Device/inode/size/mtime/ctime detect ordinary local
replacement; they do not establish cryptographic equality or adversarial race
protection. Remote size, state and unique label establish upload reconciliation,
not byte-for-byte integrity or independent package verification. Accepted
packaging receipts supply that earlier evidence. Remote concurrent changes can
still require manual reconciliation; GitHub publication has no transaction
spanning all API calls. The tool does not remove unrelated assets.

The new mocked tests cover completion/resume, lost create/upload/publish
responses, uncertain absence requiring explicit retry, archive replacement,
unfinalized packages, missing authority, conflicting assets, wrong tags,
unowned drafts and remote failures. No GitHub call or real archive was used.

## Upload transport

The upload uses an absolute, fixed `https://uploads.github.com/repos/...` API
endpoint with `--hostname github.com` and the selected archive as `--input`.
This avoids Enterprise-style REST prefixes for an uploads-host relative URL.
GitHub CLI's auth transport normalizes `*.github.com` to `github.com` before
looking up credentials; it does not require separate uploads-host credentials.
Source references: [absolute URL handling](https://github.com/cli/cli/blob/trunk/pkg/cmd/api/http.go),
[auth transport](https://github.com/cli/cli/blob/trunk/api/http_client.go), and
[hostname normalization](https://github.com/cli/go-gh/blob/trunk/pkg/auth/auth.go).
No credentials were printed or copied. Both initial and post-upload asset lists
are paginated, including when the selected asset is beyond the first 100.

## First authorized live delivery — Preview 19

The unified public app is delivered as **Preview 19/build 23**, using the new resumable publication tooling. Packaged engine/release source is `a4fb9336cf821889dfdc7b7eb2259eacee2398c6`; accepted native executable source is `b0feaaba596360e39e183a344cc7ded69e3e0cf4`. Apple notarization `d8530154-3c29-406a-bfce-51d5c6c86844` was Accepted. New assembly/archive checks, root signature, stapled ticket validation, Gatekeeper, uploaded asset metadata and download HTTP 200 passed. The archive is 29,048,047 bytes.

Accepted evidence was reused: 11 engine journal cases, 12 native recovery/model/filesystem cases, 12 mocked publication methods and the existing policy, self-audit, sidecar/r2, worker-feedback, runtime, icon and dependency receipts. No functional test or native build was repeated for delivery. No GUI use, native app launch or installation occurred. Live startup/recovery, sidecar interaction, responsiveness and compact-window acceptance remain pending.

[Release and download](https://github.com/jdotc1/dicom-anonymizer/releases/tag/v2.0.0-preview.19). Earlier entries retain their historical scope.

The owned draft was temporarily absent from immediate readback. The tool stopped, then reconciled and resumed the same journal after read-only inspection. Create, upload and publish are all recorded completed; no duplicate release, overwrite, deletion or `--retry-absent` was needed. This is live transport evidence, separate from the accepted mocked cases.
