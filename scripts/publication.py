#!/usr/bin/env python3
"""Publish one finalized public release, journaling uncertain GitHub mutations."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import uuid

import release

REPOSITORY = 'jdotc1/dicom-anonymizer'


def gh(arguments):
    return json.loads(release.run(['gh', 'api', *arguments]))


def identity(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Archive must be a regular, non-symlink file')
    s = path.stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def selection(root):
    state = release.read(root / 'state.json')
    assembly = release.read(root / 'assembly.json')
    selected = release.read(root / 'selection.json')
    if assembly['variant'] != 'public' or selected['profile']['variant'] != 'public':
        raise ValueError('Only the public release profile may be published')
    if selected['profile']['bundle_identifier'] != 'io.github.jdotc1.dicom-anonymizer':
        raise ValueError('Unexpected public bundle identity')
    if state.get('notarization', {}).get('status') != 'Accepted':
        raise ValueError('Accepted notarization required')
    steps = state['steps']
    if any(steps.get(k, {}).get('status') != 'completed' for k in
           ('sign', 'signature', 'staple', 'staple_validation', 'gatekeeper', 'download')):
        raise ValueError('All distribution steps must be completed')
    archive = root / 'download.zip'
    if steps['download']['command'][-1] != str(archive):
        raise ValueError('Download receipt does not select this archive')
    manifest = selected['manifest']
    tag = manifest['release']
    commit = selected['release_source_commit']
    if not re.fullmatch(r'v[0-9A-Za-z._-]+', tag) or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Invalid release tag or immutable target')
    if (assembly['release'] != tag or assembly['release_source_commit'] != commit or
            assembly['bundle_build'] != str(manifest['build'])):
        raise ValueError('Finalized assembly and selection disagree')
    return dict(repository=REPOSITORY, tag=tag, target=commit,
                asset=f'DICOM-Anonymizer-{tag[1:]}-standalone-macOS-arm64.zip',
                archive=str(archive), identity=identity(archive))


def publish(root, title, notes, authorize=False, retry_absent=False, api=gh):
    if not authorize:
        raise ValueError('Explicit --authorize-publish is required for remote changes')
    root = Path(root).resolve()
    with release.locked(root):
        bound = selection(root)
        path = root / 'publication.json'
        current = dict(selection=bound, title=title, notes=notes, operations={}, asset_label="publication-" + uuid.uuid4().hex)
        state = release.read(path) if path.exists() else current
        if any(state[k] != current[k] for k in ('selection', 'title', 'notes')):
            raise ValueError('Publication selection or release text changed; preserve original journal')
        release.write(path, state)
        base = f'repos/{REPOSITORY}'
        metadata = api([base])
        if metadata['full_name'] != REPOSITORY or metadata['private'] is not False:
            raise ValueError('Target must be the expected public repository')
        # Resolve the tag itself: target_commitish may name a moving branch or be
        # ignored by GitHub when a tag already exists.
        def tag_commit():
            try:
                ref = api([base + '/git/ref/tags/' + bound['tag']])
            except subprocess.CalledProcessError as exc:
                if 'HTTP 404' in (exc.stderr or ''):
                    return None
                raise
            obj = ref['object']
            for _ in range(8):
                if obj['type'] == 'commit':
                    return obj['sha']
                if obj['type'] != 'tag':
                    break
                obj = api([base + '/git/tags/' + obj['sha']])['object']
            raise ValueError('Unsupported tag reference')
        def releases():
            # Paginate without interpreting a network/auth failure as absence.
            result = []
            for page in range(1, 101):
                batch = api([base + f'/releases?per_page=100&page={page}'])
                result.extend(x for x in batch if x['tag_name'] == bound['tag'])
                if len(batch) < 100:
                    return result
            raise ValueError('Release listing too large to reconcile safely')
        def mutation(name, args, found):
            prior = state['operations'].get(name)
            if found:
                state['operations'][name] = {'status': 'completed'}
                release.write(path, state)
                return
            if prior and (prior['status'] == 'completed' or not retry_absent):
                raise ValueError(name + ': remote outcome absent/uncertain; inspect then explicitly retry absent operation')
            state['operations'][name] = {'status': 'started'}
            release.write(path, state)
            api(args)  # A failed or interrupted response intentionally stays started.
        resolved = tag_commit()
        if resolved is not None and resolved != bound['target']:
            raise ValueError('Existing tag points to another commit')
        matches = releases()
        if matches and 'create' not in state['operations']:
            raise ValueError('Existing release is not owned by this publication journal')
        if len(matches) > 1:
            raise ValueError('Ambiguous release records')
        if not matches:
            # -f fields are separate argv values, never shell interpolation.
            mutation('create', [base + '/releases', '--method', 'POST',
                     '-f', 'tag_name=' + bound['tag'], '-f', 'target_commitish=' + bound['target'],
                     '-f', 'name=' + title, '-f', 'body=' + notes, '-F', 'draft=true', '-F', 'prerelease=true'], False)
            matches = releases()
        if len(matches) != 1:
            raise ValueError('Created release not yet visible; resume to reconcile')
        item = matches[0]
        if (item['name'] != title or item['body'] != notes or item['prerelease'] is not True or
                item['target_commitish'] != bound['target']):
            raise ValueError('Remote release metadata differs; no mutation permitted')
        resolved = tag_commit()
        if resolved != bound['target'] and not (resolved is None and item['draft']):
            raise ValueError('Release tag is not the selected commit')
        mutation('create', [], True)
        endpoint = base + f"/releases/{item['id']}"
        # Separate paginated assets endpoint: embedded assets may be incomplete.
        assets = []
        for page in range(1, 101):
            batch = api([endpoint + f'/assets?per_page=100&page={page}'])
            assets.extend(batch)
            if len(batch) < 100:
                break
        else:
            raise ValueError('Asset listing too large')
        exact = [a for a in assets if a['name'] == bound['asset']]
        if len(exact) > 1 or (exact and (exact[0]['size'] != bound['identity'][2] or exact[0]['state'] != 'uploaded' or exact[0].get('label') != state['asset_label'])):
            raise ValueError('Existing asset conflicts; never overwrite or delete it')
        if not item['draft'] and not exact:
            raise ValueError('Published release is missing the selected asset; manual reconciliation required')
        if identity(Path(bound['archive'])) != bound['identity']:
            raise ValueError('Selected archive changed')
        mutation('upload', [endpoint + '/assets?name=' + bound['asset'] + '&label=' + state['asset_label'], '--hostname', 'uploads.github.com',
                           '--method', 'POST', '-H', 'Content-Type: application/zip', '--input', bound['archive']], bool(exact))
        # Always read back after upload; do not publish from a successful response alone.
        confirmed = api([endpoint + '/assets?per_page=100'])
        if not any(a['name'] == bound['asset'] and a['size'] == bound['identity'][2] and a['state'] == 'uploaded' and a.get('label') == state['asset_label'] for a in confirmed):
            raise ValueError('Upload not confirmed; resume to reconcile')
        mutation('upload', [], True)
        if identity(Path(bound['archive'])) != bound['identity']:
            raise ValueError('Selected archive changed during upload')
        latest = api([endpoint])
        if any(latest.get(key) != item.get(key) for key in ('id', 'tag_name', 'target_commitish', 'name', 'body', 'prerelease')):
            raise ValueError('Remote metadata changed during upload')
        mutation('publish', [endpoint, '--method', 'PATCH', '-F', 'draft=false'], not item['draft'])
        final = api([endpoint])
        if final['draft'] or final['tag_name'] != bound['tag'] or tag_commit() != bound['target']:
            raise ValueError('Publication not confirmed; resume to reconcile')
        mutation('publish', [], True)
        state['url'] = final['html_url']
        release.write(path, state)
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--notes-file', type=Path, required=True)
    parser.add_argument('--authorize-publish', action='store_true')
    parser.add_argument('--retry-absent', action='store_true', help='Only after inspecting an uncertain remote operation')
    args = parser.parse_args()
    try:
        print(json.dumps(publish(args.output, args.title, args.notes_file.read_text(), args.authorize_publish, args.retry_absent), indent=2))
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
