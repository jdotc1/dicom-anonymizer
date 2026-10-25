#!/usr/bin/env python3
"""Receipt-driven app assembly and explicit, resumable distribution steps (stdlib only)."""
import argparse
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

import publication_safety
import release_storage


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)



def artifact_identity(path):
    """Filesystem metadata only; do not follow links or cross mount boundaries."""
    path = Path(path)
    device = path.lstat().st_dev
    def snapshot(item):
        value = item.lstat()
        if value.st_dev != device:
            raise ValueError('Cross-device entry in artifact: ' + str(item))
        if not (stat.S_ISREG(value.st_mode) or stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode)):
            raise ValueError('Special file in artifact: ' + str(item))
        return [value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns]
    def failed(error):
        raise error
    result = {'.': snapshot(path)}
    if path.is_dir() and not path.is_symlink():
        for parent, directories, files in os.walk(path, followlinks=False, onerror=failed):
            for name in directories + files:
                child = Path(parent) / name
                result[str(child.relative_to(path))] = snapshot(child)
    return result


def record_artifact_ownership(root):
    """Called only when this finalization newly creates the distribution archive."""
    if (root / 'artifact-ownership.json').exists() or (root / 'artifact-ownership.json').is_symlink():
        raise ValueError('Artifact ownership already recorded; never replace it')
    assembly = read(root / 'assembly.json')
    artifacts = {}
    for name in ('DICOM Anonymizer 2.0.app', 'download.zip', 'notarization-upload.zip'):
        path = root / name
        if path.exists():
            if path.is_symlink():
                raise ValueError('Artifact root cannot be a symlink')
            artifacts[name] = artifact_identity(path)
    write(root / 'artifact-ownership.json', dict(schema=1, release=assembly['release'],
          source=assembly['release_source_commit'], build=str(assembly['bundle_build']), artifacts=artifacts))


def run(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout


def pointer(value, selector):
    if not selector.startswith('/'):
        raise ValueError('Receipt selector must be a JSON pointer')
    for part in selector[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    if not isinstance(value, str) or not value:
        raise ValueError('Receipt selection must be a nonempty string')
    return value


def resolve(base, value):
    return (base / value).resolve()


def translated_sources(accepted, base, repository, source, native):
    """Select an explicitly qualified history translation, never infer acceptance.

    The local qualification record supplements sealed receipts; it does not
    rewrite them or claim that a reused executable was built at a new commit.
    """
    selection = accepted.get('history_translation')
    if selection is None:
        return source, native
    path = resolve(base, selection)
    if path == repository.resolve() or repository.resolve() in path.parents:
        raise ValueError('History qualification must remain outside public source')
    record = read(path)
    if (not isinstance(record, dict) or record.get('schema') != 1 or
            record.get('accepted_verification_reused') is not True or
            not isinstance(record.get('entries'), list)):
        raise ValueError('Invalid history qualification record')
    results = []
    for original, scope in ((source, 'engine'), (native, 'native')):
        matches = [entry for entry in record['entries'] if isinstance(entry, dict) and
                   entry.get('original_commit') == original and entry.get('scope') == scope]
        if len(matches) != 1:
            raise ValueError('History qualification must select exactly one ' + scope + ' mapping')
        entry = matches[0]
        target = entry.get('sanitized_commit')
        if (entry.get('accepted') is not True or
                not isinstance(entry.get('qualification'), str) or not entry['qualification'].strip() or
                not isinstance(target, str) or not re.fullmatch('[0-9a-f]{40}', target)):
            raise ValueError('History mapping requires explicit scoped qualification')
        resolved = run(['git', '-C', str(repository), 'rev-parse', target + '^{commit}']).strip()
        if resolved != target:
            raise ValueError('History target must be an immutable commit')
        run(['git', '-C', str(repository), 'merge-base', '--is-ancestor', target, 'HEAD'])
        results.append(target)
    return tuple(results)


def plan(manifest_path, repository):
    manifest_path = Path(manifest_path).resolve()
    m = read(manifest_path)
    profile = read(repository / 'scripts/release-profile.json')
    if run(['git', '-C', str(repository), 'status', '--porcelain', '--untracked-files=all', '--',
            'scripts/release.py', 'scripts/release-profile.json', 'scripts/publication.py',
            'scripts/publication_safety.py', 'scripts/release_storage.py', '.githooks/pre-push']).strip():
        raise ValueError('Commit release tooling and profile before selecting release provenance')
    if m['schema'] != 1 or m['variant'] != profile['variant']:
        raise ValueError('Manifest schema or app variant mismatch')
    receipt_path = resolve(manifest_path.parent, m['accepted']['receipt'])
    receipt = read(receipt_path)
    for key in ('source_pointer', 'product_pointer'):
        if m['accepted'][key] != profile[key]:
            raise ValueError('Receipt selector belongs to a different app variant')
    # Acceptance is an explicit selection by the release owner, never inferred
    # from a successful compiler exit or a signature.
    if m['accepted']['reuse_accepted_verification'] is not True:
        raise ValueError('An accepted verification selection is required')
    source = pointer(receipt, m['accepted']['source_pointer'])
    if not re.fullmatch('[0-9a-f]{40}', source):
        raise ValueError('Accepted source must be a full immutable Git commit')
    product = resolve(receipt_path.parent, pointer(receipt, m['accepted']['product_pointer']))
    baseline = resolve(manifest_path.parent, m['baseline_app'])
    metadata = read(resolve(manifest_path.parent, m['accepted']['build_metadata']))
    for key in ('xcode', 'swift', 'macos_sdk', 'swift_language_mode', 'deployment_target', 'architecture'):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError('Invalid accepted build metadata: ' + key)
    runtime = metadata.get('bundled_python')
    if not isinstance(runtime, dict) or any(not isinstance(runtime.get(key), str) or not runtime[key].strip()
                                           for key in ('version', 'distribution', 'release', 'target')):
        raise ValueError('Incomplete accepted Python runtime metadata')
    info = plistlib.loads((baseline / 'Contents/Info.plist').read_bytes())
    if (info['CFBundleIdentifier'] != profile['bundle_identifier'] or
            info['LSMinimumSystemVersion'] != profile['deployment_target'] or
            metadata['deployment_target'] != profile['deployment_target'] or
            metadata['architecture'] != 'arm64' or metadata['source_commit'] != source):
        raise ValueError('Accepted product metadata or baseline identity mismatch')
    if info['CFBundleExecutable'] != 'DICOMAnonymizer2' or not product.is_file():
        raise ValueError('Missing accepted executable or unexpected app executable')
    if not re.fullmatch('[1-9][0-9]*', str(m['build'])) or int(m['build']) <= int(info['CFBundleVersion']):
        raise ValueError('Build number must increase from the accepted baseline')
    for key in ('release', 'version', 'evidence_label'):
        if not isinstance(m[key], str) or not m[key].strip() or '\n' in m[key]:
            raise ValueError('Missing or invalid ' + key)
    if '/' in m['evidence_label'] or '\\' in m['evidence_label']:
        raise ValueError('Evidence label must not disclose a local path')
    native_sources = receipt.get('builds', {}).get('native_source_commits', {})
    if not isinstance(native_sources, dict):
        raise ValueError('Native product source selection must be an object')
    native_source = native_sources.get(m['variant'], source)
    if (not isinstance(native_source, str) or not re.fullmatch('[0-9a-f]{40}', native_source)
            or metadata.get('native_source_commit', metadata['source_commit']) != native_source):
        raise ValueError('Accepted native product source does not match its metadata')
    selected_source, selected_native = translated_sources(m['accepted'], manifest_path.parent,
                                                         repository, source, native_source)
    if selected_native != selected_source:
        run(['git', '-C', str(repository), 'rev-parse', selected_native + '^{commit}'])
    commit = run(['git', '-C', str(repository), 'rev-parse', selected_source + '^{commit}']).strip()
    release_commit = run(['git', '-C', str(repository), 'rev-parse', 'HEAD']).strip()
    return dict(manifest=m, baseline=str(baseline), product=str(product), source_commit=commit,
                release_source_commit=release_commit, native_source_commit=native_source,
                accepted_source_commit=source, native_sanitized_source_commit=selected_native,
                metadata=metadata, profile=profile)


def assemble(manifest_path, output, repository):
    release_storage.require_active(output)
    p = plan(manifest_path, repository)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Output must be new; existing artifacts are never overwritten')
    output.parent.mkdir(parents=True, exist_ok=True)
    output = output.parent.resolve() / output.name
    for protected in (repository.resolve(), Path(p['baseline']), Path(p['product']).parent):
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError('Output must be separate from repository and accepted inputs')
    stage = Path(tempfile.mkdtemp(prefix='.release-', dir=output.parent))
    try:
        app = stage / 'DICOM Anonymizer 2.0.app'
        vendor = Path(p['baseline']) / 'Contents/Resources/vendor'
        def ignore_vendor_bytecode(directory, names):
            if Path(directory).is_relative_to(vendor):
                return {name for name in names if name == '__pycache__' or name.endswith(('.pyc', '.pyo'))}
            return set()
        # Local test/import caches are derived artifacts, not accepted vendor
        # sources. Preserve the bundled interpreter/runtime resources separately.
        shutil.copytree(p['baseline'], app, symlinks=True, ignore=ignore_vendor_bytecode)
        # A copied ancestor symlink must never redirect writes into the baseline.
        for relative in ('Contents', 'Contents/MacOS', 'Contents/Resources',
                         'Contents/Info.plist', 'Contents/MacOS/DICOMAnonymizer2',
                         'Contents/Resources/BuildInfo.json', 'Contents/Resources/ReleaseInfo.json',
                         'Contents/Resources/engine', 'Contents/_CodeSignature'):
            if (app / relative).is_symlink():
                raise ValueError('Unsafe mutable bundle path: ' + relative)
        shutil.copy2(p['product'], app / 'Contents/MacOS/DICOMAnonymizer2')
        engine = app / 'Contents/Resources/engine'
        if engine.exists():
            shutil.rmtree(engine)
        archive = subprocess.run(['git', '-C', str(repository), 'archive', p['source_commit'], 'engine'],
                                 check=True, capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if not parts or parts[0] != 'engine' or '..' in parts or not (member.isdir() or member.isfile()):
                    raise ValueError('Unsafe engine archive entry')
            tar.extractall(app / 'Contents/Resources', filter='data')
        m = p['manifest']
        info_path = app / 'Contents/Info.plist'
        info = plistlib.loads(info_path.read_bytes())
        info.update(CFBundleVersion=str(m['build']), CFBundleShortVersionString=m['version'])
        info_path.write_bytes(plistlib.dumps(info))
        provenance = {key: p['metadata'][key] for key in
                      ('xcode', 'swift', 'macos_sdk', 'swift_language_mode', 'deployment_target',
                       'architecture', 'bundled_python')}
        provenance.update(source_commit=p['source_commit'], engine_source_commit=p['source_commit'],
                          native_source_commit=p['native_source_commit'], release_source_commit=p['release_source_commit'],
                          release=m['release'], bundle_build=str(m['build']))
        if m['accepted'].get('history_translation') is not None:
            provenance.update(accepted_source_commit=p['accepted_source_commit'],
                              native_sanitized_source_commit=p['native_sanitized_source_commit'])
        evidence = dict(schema=1, variant=m['variant'], **provenance,
                        accepted_evidence=m['evidence_label'], verification='Accepted verification reused; no tests rerun',
                        nested_signatures='Preserved; unchanged dependencies not reverified',
                        packaging='Unsigned assembly; signing and notarization are separate stages')
        write(app / 'Contents/Resources/BuildInfo.json', provenance)
        write(app / 'Contents/Resources/ReleaseInfo.json', evidence)
        signature = app / 'Contents/_CodeSignature'
        if signature.exists():
            shutil.rmtree(signature)
        write(stage / 'assembly.json', evidence)
        write(stage / 'state.json', dict(schema=1, app=app.name, steps={}))
        # Retain private input paths outside the distributed app for local audit.
        write(stage / 'selection.json', p)
        stage.rename(output)
    except BaseException:
        shutil.rmtree(stage)
        raise
    return read(output / 'assembly.json')


@contextmanager
def locked(root):
    lock = root / '.release.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        yield
    finally:
        os.close(fd)
        lock.unlink()


def step(root, state, name, command, runner=None):
    runner = runner or run
    previous = state['steps'].get(name)
    if previous:
        if previous['status'] == 'completed':
            if previous['command'] != command:
                raise ValueError(name + ' already completed with different arguments')
            return previous['output']
        raise ValueError(name + ' has an uncertain prior outcome; reconcile it before proceeding')
    state['steps'][name] = dict(status='started', command=command)
    write(root / 'state.json', state)
    result = runner(command)
    state['steps'][name].update(status='completed', output=result)
    write(root / 'state.json', state)
    return result


def distribute(root, action, identity=None, profile=None, submission_id=None):
    release_storage.require_active(root)
    root = Path(root).resolve()
    with locked(root):
        state = read(root / 'state.json')
        app = root / state['app']
        if action in ('sign', 'notarize', 'finalize'):
            assembly = read(root / 'assembly.json')
            publication_safety.app_gate(Path(__file__).resolve().parents[1],
                                       assembly['release_source_commit'], app)
        if action == 'sign':
            if not identity or not identity.startswith('Developer ID Application:'):
                raise ValueError('Explicit Developer ID Application identity required')
            step(root, state, 'sign', ['/usr/bin/codesign', '--force', '--options', 'runtime', '--timestamp', '--sign', identity, str(app)])
            step(root, state, 'signature', ['/usr/bin/codesign', '--verify', '--strict', str(app)])
        elif action == 'notarize':
            if state['steps'].get('signature', {}).get('status') != 'completed' or not profile:
                raise ValueError('Completed signature and explicit keychain profile required')
            upload = root / 'notarization-upload.zip'
            step(root, state, 'upload_archive', ['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(upload)])
            if submission_id:
                if not re.fullmatch('[0-9a-fA-F-]{36}', submission_id):
                    raise ValueError('Invalid existing submission ID')
                previous = state.get('submission_id')
                if previous and previous != submission_id:
                    raise ValueError('Cannot replace an existing notarization submission')
                state['submission_id'] = submission_id
                write(root / 'state.json', state)
            if 'submission_id' not in state:
                with publication_safety.ledger(Path(__file__).resolve().parents[1]) as receipts:
                    publication_safety.archive_gate(upload, receipts)
                result = json.loads(step(root, state, 'submit', ['xcrun', 'notarytool', 'submit', str(upload), '--keychain-profile', profile, '--output-format', 'json']))
                state['submission_id'] = result['id']
                write(root / 'state.json', state)
            if state.get('notarization', {}).get('status') in ('Invalid', 'Rejected'):
                raise ValueError('Notarization rejected; inspect the existing submission, do not resubmit')
            if state.get('notarization', {}).get('status') != 'Accepted':
                state['notarization'] = json.loads(run(['xcrun', 'notarytool', 'info', state['submission_id'], '--keychain-profile', profile, '--output-format', 'json']))
                write(root / 'state.json', state)
        elif action == 'finalize':
            if state.get('notarization', {}).get('status') != 'Accepted':
                raise ValueError('Accepted notarization required')
            new_download = 'download' not in state['steps']
            if new_download and ((root / 'artifact-ownership.json').exists() or (root / 'artifact-ownership.json').is_symlink()):
                raise ValueError('Ownership record already exists; do not replace it')
            if new_download:
                state['ownership_pending'] = True
                write(root / 'state.json', state)
            step(root, state, 'staple', ['xcrun', 'stapler', 'staple', str(app)])
            step(root, state, 'staple_validation', ['xcrun', 'stapler', 'validate', str(app)])
            step(root, state, 'gatekeeper', ['/usr/sbin/spctl', '--assess', '--type', 'execute', '--verbose=2', str(app)])
            step(root, state, 'download', ['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(root / 'download.zip')])
            with publication_safety.ledger(Path(__file__).resolve().parents[1]) as receipts:
                publication_safety.archive_gate(root / 'download.zip', receipts)
            if state.get('ownership_pending'):
                ownership = root / 'artifact-ownership.json'
                if ownership.exists() or ownership.is_symlink():
                    if ownership.is_symlink():
                        raise ValueError('Unsafe pending ownership record')
                    recorded = read(ownership)
                    if (recorded['source'] != assembly['release_source_commit'] or
                            recorded['release'] != assembly['release'] or
                            recorded['build'] != str(assembly['bundle_build']) or
                            set(recorded['artifacts']) != {name for name in
                              ('DICOM Anonymizer 2.0.app', 'download.zip', 'notarization-upload.zip')
                              if (root / name).exists()} or
                            recorded['artifacts'] != {name: artifact_identity(root / name)
                              for name in recorded['artifacts']}):
                        raise ValueError('Pending ownership differs; preserve journal')
                else:
                    record_artifact_ownership(root)
                state.pop('ownership_pending')
                write(root / 'state.json', state)
        return state


def main(arguments=None, monitored=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'assemble', 'sign', 'notarize', 'finalize', 'status'))
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path, help='New assembly directory, or existing directory for later stages')
    parser.add_argument('--identity')
    parser.add_argument('--keychain-profile')
    parser.add_argument('--submission-id', help='Reconcile an interrupted submission; never resubmit blindly')
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    args = parser.parse_args(arguments)
    allocating = args.action in ('assemble', 'sign', 'notarize', 'finalize')
    if allocating and args.output is None:
        parser.error('allocating actions require --output')
    if args.action == 'assemble' and args.manifest is None:
        parser.error('assemble requires --manifest')
    repo = Path(__file__).resolve().parents[1]
    try:
        if allocating and not monitored:
            return release_storage.supervise(arguments)
        if args.action == 'plan':
            result = plan(args.manifest, repo)
        elif args.action == 'assemble':
            result = assemble(args.manifest, args.output, repo)
        elif args.action == 'status':
            result = read(args.output / 'state.json')
        else:
            result = distribute(args.output, args.action, args.identity, args.keychain_profile, args.submission_id)
        print(json.dumps(result, indent=2))
    except (ValueError, KeyError, IndexError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        detail = (exc.stderr or exc.stdout or '') if isinstance(exc, subprocess.CalledProcessError) else ''
        parser.exit(1, str(exc) + '\n' + detail)


if __name__ == '__main__':
    raise SystemExit(main())
