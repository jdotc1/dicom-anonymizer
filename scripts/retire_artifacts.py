#!/usr/bin/env python3
"""Plan first, then explicitly retire superseded finalized public release artifacts."""
import argparse
import base64
from contextlib import ExitStack
import json
import os
import re
from pathlib import Path
import shutil

import release

APP = 'DICOM Anonymizer 2.0.app'
NAMES = (APP, 'download.zip', 'notarization-upload.zip')
REPOSITORY = Path(__file__).resolve().parents[1]


def canonical(value):
    path = Path(os.path.abspath(value))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink path is not eligible: ' + str(path))
    return path


def overlaps(a, b):
    return a == b or a in b.parents or b in a.parents


def stamp(path):
    s = path.lstat()
    return [s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def tree(path):
    return release.artifact_identity(path)



def record(root):
    root = canonical(root)
    if not root.is_dir() or overlaps(root, REPOSITORY):
        raise ValueError('Release folder must be separate from source')
    if any((p / '.git').exists() for p in (root, *root.parents)):
        raise ValueError('Source checkout is not a release retirement root')
    names = ('state.json', 'assembly.json', 'selection.json', 'publication.json')
    for name in names:
        p = root / name
        if p.is_symlink() or not p.is_file():
            raise ValueError('Regular finalized release metadata required: ' + str(p))
    state, assembly, selected, publication = [release.read(root / name) for name in names]
    if (state.get('schema') != 1 or assembly.get('schema') != 1 or
            selected['manifest'].get('schema') != 1 or
            state.get('app') != APP or assembly.get('variant') != 'public' or
            selected['profile']['variant'] != 'public' or
            selected['profile']['bundle_identifier'] != 'io.github.jdotc1.dicom-anonymizer' or
            state.get('notarization', {}).get('status') != 'Accepted'):
        raise ValueError('Expected finalized public release required')
    required = ('sign', 'signature', 'staple', 'staple_validation', 'gatekeeper', 'download')
    if (any(state['steps'].get(k, {}).get('status') != 'completed' for k in required) or
            any(v.get('status') != 'completed' for v in state['steps'].values()) or
            set(publication.get('operations', {})) != {'create', 'upload', 'publish'} or
            any(v.get('status') != 'completed' for v in publication['operations'].values())):
        raise ValueError('Incomplete or uncertain release cannot be retired')
    bound = publication['selection']
    if (bound['repository'] != 'jdotc1/dicom-anonymizer' or
            bound['tag'] != assembly['release'] or bound['target'] != assembly['release_source_commit'] or
            assembly['release_source_commit'] != selected['release_source_commit'] or
            assembly['release'] != selected['manifest']['release'] or
            str(assembly['bundle_build']) != str(selected['manifest']['build']) or
            canonical(bound['archive']) != root / 'download.zip'):
        raise ValueError('Release metadata selection disagrees')
    if (not re.fullmatch(r'v[0-9A-Za-z._-]+', assembly['release']) or
            not re.fullmatch('[0-9a-f]{40}', bound['target']) or
            publication.get('url') != 'https://github.com/jdotc1/dicom-anonymizer/releases/tag/' + assembly['release']):
        raise ValueError('Completed owned publication URL and immutable target required')
    build = int(assembly['bundle_build'])
    if build <= 0:
        raise ValueError('Positive build number required')
    protected = [root]
    for key in ('baseline', 'product'):
        if key not in selected:
            raise ValueError('Current release input selection required')
        protected.append(canonical(selected[key]))
    accepted = selected['manifest']['accepted']
    for key in ('receipt', 'build_metadata'):
        value = Path(accepted[key])
        if not value.is_absolute():
            # Assembly selection does not record the original manifest directory.
            raise ValueError('Absolute accepted input paths required for safe retirement')
        protected.append(canonical(value))
    ownership_path = root / 'artifact-ownership.json'
    ownership = None
    metadata = {name: stamp(root / name) for name in names}
    if ownership_path.exists() or ownership_path.is_symlink():
        if ownership_path.is_symlink() or not ownership_path.is_file():
            raise ValueError('Regular artifact ownership metadata required')
        ownership = release.read(ownership_path)
        if (ownership.get('schema') != 1 or ownership.get('release') != assembly['release'] or
                ownership.get('source') != bound['target'] or ownership.get('build') != str(build)):
            raise ValueError('Artifact ownership record disagrees with release')
        metadata['artifact-ownership.json'] = stamp(ownership_path)
    return dict(root=str(root), build=build, protected=list(map(str, protected)),
                metadata=metadata, ownership=ownership, download_identity=bound.get('identity'))


def protected_inodes(paths):
    found = set()
    for path in paths:
        if path.exists() or path.is_symlink():
            found.update(tuple(value[:2]) for value in tree(path).values())
    return found


def require_current(current):
    root = Path(current['root'])
    if ((root / APP).is_symlink() or (root / 'download.zip').is_symlink() or
            not (root / APP).is_dir() or not (root / 'download.zip').is_file()):
        raise ValueError('Current retained assembly and download must exist')
    if not Path(current['protected'][2]).is_file():
        raise ValueError('Current accepted native executable must exist')


def owned_artifact(old, name, identity):
    if name == 'download.zip':
        entry = identity['.']
        # Bind to the completed publication's existing filesystem identity.
        if old['download_identity'] != [entry[0], entry[1], entry[3], entry[4], entry[5]]:
            raise ValueError('Published download was replaced or changed before planning')
    ownership = old.get('ownership')
    expected = ownership.get('artifacts', {}).get(name) if ownership else None
    if expected is None:
        return name == 'download.zip'
    if expected != identity:
        raise ValueError('Artifact changed since its recorded creation')
    return True


def bundle_metadata(path):
    saved = {}
    for name in ('Contents/Info.plist', 'Contents/Resources/BuildInfo.json', 'Contents/Resources/ReleaseInfo.json'):
        item = path / name
        if item.is_file() and not item.is_symlink():
            saved[name] = base64.b64encode(item.read_bytes()).decode('ascii')
    return saved


def plan(current, superseded, plan_file):
    current_record = record(current)
    require_current(current_record)
    roots = [record(p) for p in superseded]
    paths = [Path(current_record['root']), *[Path(r['root']) for r in roots]]
    if any(overlaps(a, b) for i, a in enumerate(paths) for b in paths[i + 1:]):
        raise ValueError('Release roots must be distinct and non-overlapping')
    if any(r['build'] >= current_record['build'] for r in roots):
        raise ValueError('Only releases older than the explicit current release may be retired')
    protected = [REPOSITORY, *map(Path, current_record['protected'])]
    inodes = protected_inodes(protected)
    entries, skipped = [], []
    for old in roots:
        for name in NAMES:
            path = Path(old['root']) / name
            if path.is_symlink():
                raise ValueError('Artifact root cannot be a symlink')
            if not path.exists():
                continue
            if any(overlaps(path, p) for p in protected):
                skipped.append(dict(path=str(path), reason='protected current release input'))
                continue
            if (name == APP and not path.is_dir()) or (name != APP and not path.is_file()):
                raise ValueError('Unexpected artifact type')
            identity = tree(path)
            if any(tuple(value[:2]) in inodes for value in identity.values()):
                skipped.append(dict(path=str(path), reason='shares inode with protected current input'))
                continue
            if not owned_artifact(old, name, identity):
                skipped.append(dict(path=str(path), reason='no creation ownership record; legacy artifact retained'))
                continue
            if any('.git' in Path(name).parts for name in identity):
                raise ValueError('Source checkout embedded in artifact')
            entries.append(dict(root=old['root'], name=name, path=str(path), identity=identity,
                                bundle_metadata=bundle_metadata(path) if name == APP else {}))
    target = canonical(plan_file)
    if any(overlaps(target, p) for p in paths + protected):
        raise ValueError('Plan must be stored outside source and release/input paths')
    if not target.parent.is_dir():
        raise ValueError('Plan parent directory must already exist')
    result = dict(schema=1, current=current_record, superseded=roots, entries=entries, skipped=skipped)
    with release.locked(target.parent):
        with target.open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    return result


def apply(plan_file, remove=None):
    target = canonical(plan_file)
    if not target.is_file():
        raise ValueError('Existing explicit retirement plan required')
    selected = release.read(target)
    if selected.get('schema') != 1:
        raise ValueError('Unsupported retirement plan')
    roots = [selected['current'], *selected['superseded']]
    root_paths = [canonical(r['root']) for r in roots]
    if any(overlaps(a, b) for i, a in enumerate(root_paths) for b in root_paths[i + 1:]):
        raise ValueError('Release roots overlap')
    if any(overlaps(target, p) for p in root_paths + [REPOSITORY]):
        raise ValueError('Unsafe plan location')
    journal_path = target.with_name(target.name + '.journal.json')
    if journal_path.is_symlink():
        raise ValueError('Journal cannot be a symlink')
    with ExitStack() as locks:
        for directory in sorted(set([target.parent, *root_paths]), key=str):
            locks.enter_context(release.locked(directory))
        for original in roots:
            if record(original['root']) != original:
                raise ValueError('Release metadata changed since planning')
        if any(old['build'] >= roots[0]['build'] for old in roots[1:]):
            raise ValueError('Current release must remain newer')
        require_current(roots[0])
        protected = [REPOSITORY, *map(Path, roots[0]['protected'])]
        if any(overlaps(target, p) for p in protected):
            raise ValueError('Plan overlaps a protected input')
        inodes = protected_inodes(protected)
        journal = release.read(journal_path) if journal_path.exists() else dict(schema=1, plan_identity=stamp(target), entries={})
        if journal.get('schema') != 1 or journal.get('plan_identity') != stamp(target):
            raise ValueError('Plan changed after retirement started; preserve its journal')
        # Preflight the complete plan before any deletion. Unknown paths never
        # gain authority merely by being written into a plan file.
        for entry in selected['entries']:
            root = canonical(entry['root']); path = canonical(entry['path'])
            if root not in root_paths[1:] or entry['name'] not in NAMES or path != root / entry['name']:
                raise ValueError('Plan contains an unowned artifact path')
            if any(overlaps(path, p) for p in protected):
                raise ValueError('Protected release input selected')
            prior = journal['entries'].get(str(path))
            if prior:
                if path.exists():
                    raise ValueError('Started/retired artifact exists; inspect partial deletion or replacement before replanning')
            elif not path.exists() or tree(path) != entry['identity']:
                raise ValueError('Artifact changed or disappeared since planning')
            elif not owned_artifact(next(r for r in roots[1:] if r['root'] == str(root)), entry['name'], entry['identity']):
                raise ValueError('Artifact lacks recorded creation ownership')
            elif any(tuple(value[:2]) in inodes for value in entry['identity'].values()):
                raise ValueError('Artifact shares an inode with a protected input')
        release.write(journal_path, journal)
        for entry in selected['entries']:
            path = Path(entry['path']); key = str(path)
            prior = journal['entries'].get(key)
            if prior:
                journal['entries'][key]['status'] = 'retired'
                release.write(journal_path, journal)
                continue
            if tree(path) != entry['identity']:
                raise ValueError('Artifact changed before deletion')
            journal['entries'][key] = dict(status='started', bundle_metadata=entry['bundle_metadata'])
            release.write(journal_path, journal)
            if remove:
                remove(path)
            elif path.is_dir():
                if not shutil.rmtree.avoids_symlink_attacks:
                    raise ValueError('Symlink-resistant directory removal unavailable')
                shutil.rmtree(path)
            else:
                path.unlink()
            if path.exists() or path.is_symlink():
                raise ValueError('Artifact removal not confirmed')
            journal['entries'][key]['status'] = 'retired'
            release.write(journal_path, journal)
        return journal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', type=Path)
    parser.add_argument('--superseded', type=Path, nargs='+')
    parser.add_argument('--plan-file', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Apply an already reviewed plan; never creates a plan')
    args = parser.parse_args()
    try:
        if args.apply:
            if args.current or args.superseded:
                raise ValueError('Apply uses only the existing --plan-file')
            result = apply(args.plan_file)
        else:
            if not args.current or not args.superseded:
                raise ValueError('Planning requires explicit --current and --superseded release folders')
            result = plan(args.current, args.superseded, args.plan_file)
        if args.apply:
            summary = dict(mode='applied', journal=str(args.plan_file) + '.journal.json',
                           artifacts={p: value['status'] for p, value in result['entries'].items()})
        else:
            summary = dict(mode='plan-only', plan=str(args.plan_file),
                           artifacts=[entry['path'] for entry in result['entries']], skipped=result['skipped'])
        print(json.dumps(summary, indent=2))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
