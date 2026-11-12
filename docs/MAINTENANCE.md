# Maintenance

The project is in maintenance mode; see the [roadmap](ROADMAP.md).

## Tests and lint

All tests use synthetic data.

```sh
scripts/run_tests.sh      # unit tests with a private temp root; extra arguments go to unittest discover
scripts/lint.sh           # optional lint counts, non-gating (--strict to gate)
```

`scripts/run_tests.sh` uses `DICOM_TEST_TMPDIR` if set to an existing directory
(never removed), otherwise it creates and removes its own. `DICOM_TEST_TIMEOUT_SCALE`
stretches subprocess timeouts on a slow machine. Re-run a suite only when its inputs
changed; reuse recorded evidence otherwise (see [Evidence](EVIDENCE.md)).

## Continuous integration

CI is manual only: `.github/workflows/tests.yml` runs on `workflow_dispatch` and
requires the `acknowledge` input. It has read-only repository permissions. It does
not run on push or pull request.

## Releases

- Packaging, notarization and resumable publication: [Release automation](RELEASE-AUTOMATION.md).
- Checks before a release is assembled: [Release preflight](RELEASE-PREFLIGHT.md).
- Per-release records: [Publication checklist](PUBLICATION-CHECKLIST.md).

## Publication safety

Source history, release text and artifacts pass the sanitation gates described in
[Publication safety](PUBLICATION-SAFETY.md). Do not bypass the gate. Do not post
patient files, identifiers or unredacted logs anywhere.

## Policy changes

The engine policy version (currently 2.0-build6) is separate from the app
release/build number. Batch policy edits: make all policy changes for a release in
one policy-version bump, not one bump per edit, and update
[data handling](DATA-HANDLING.md) and the [engine interface](ENGINE-INTERFACE.md)
in the same change. The interface contract tests fail if an event name or report
key changes without the reference changing.
