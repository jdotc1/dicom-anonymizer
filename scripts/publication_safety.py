#!/usr/bin/env python3
"""Fail-closed, receipt-reusing sanitation gates. Never modifies public inputs."""
import argparse
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import zipfile

# Patterns are intentionally written without embedding real private examples.
def _private_rule(name):
    # Owner-specific values are intentionally configured outside tracked source.
    repository = Path(__file__).resolve().parents[1]
    common = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', '--git-common-dir'], text=True).strip()
    path = (repository / common).resolve() / 'publication-safety/private-rules.json'
    if path.is_symlink() or not path.is_file():
        raise ValueError('Required private sanitation configuration is missing')
    configuration = json.loads(path.read_text())
    rules = configuration.get('rules', {})
    if configuration.get('schema') != 1 or name not in rules or not isinstance(rules[name], str) or not rules[name]:
        raise ValueError('Invalid private sanitation configuration')
    return rules[name]


RULES = {
    'machine-home': r'/(?:Users|home)/[^/\s"\'<>]+',
    'local-work-root': r'(?:~|\$(?:HOME|\{HOME\}))/Developer(?:/|\b)',
    'session-scratch': r'/(?:private/)?tmp/(?:claude|codex)-[^\s/]+',
    'encoded-home': r'(?:-Users-|%2[fF]Users%2[fF])[A-Za-z0-9_.-]+',
    'personal-email': _private_rule('personal-email'),
    'private-correspondence': _private_rule('private-correspondence'),
    'private-workspace': r'(?:CODEX[_]HANDOFF|CLAUDE[_]HANDOFF|\.claude/(?:projects|handoffs)|\.codex/(?:sessions|memories))',
    'unrelated-internal-app': _private_rule('unrelated-internal-app'),
    'credential': r'(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
}
# Bump when inspection semantics change, even if the pattern set stays the same.
SCANNER_VERSION = 2
POLICY = hashlib.sha256(json.dumps([SCANNER_VERSION, RULES], sort_keys=True).encode()).hexdigest()
# Version 2 only adds bounded gzip support. Version 1 rejected every gzip
# payload; its previously successful objects remain valid without rescanning.
COMPATIBLE_POLICIES = {hashlib.sha256(json.dumps([1, RULES], sort_keys=True).encode()).hexdigest()}
PATTERNS = {name: re.compile(value, re.I) for name, value in RULES.items()}
MAX_FILE = 512 * 1024 * 1024
MAX_ARCHIVE = 2 * 1024 * 1024 * 1024


def check(data, label):
    """Scan text and embedded ASCII/UTF-16 strings without logging matched data."""
    for encoding, offset in (('utf-8', 0), ('utf-16-le', 0), ('utf-16-be', 0),
                             ('utf-16-le', 1), ('utf-16-be', 1)):
        text = data[offset:].decode(encoding, errors='ignore')
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                raise ValueError('Sanitation refused: ' + name + ' in ' + label)


def git(repository, *args):
    environment = dict(os.environ, GIT_NO_REPLACE_OBJECTS='1', GIT_GRAFT_FILE=os.devnull)
    environment.pop('GIT_SHALLOW_FILE', None)
    return subprocess.run(['git', '--no-replace-objects', '-C', str(repository), *args],
                          check=True, capture_output=True, env=environment).stdout


def cache_root(repository):
    common = git(repository, 'rev-parse', '--git-common-dir').decode().strip()
    return (Path(repository) / common).resolve() / 'publication-safety'


def save(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.sanitation-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def ledger(repository):
    root = cache_root(repository)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / 'receipts.json'
        value = json.loads(path.read_text()) if path.exists() else {}
        if value.get('policy') in COMPATIBLE_POLICIES:
            value['policy'] = POLICY
        elif value.get('policy') != POLICY:
            value = dict(policy=POLICY, objects={}, archives={}, texts={})
        try:
            yield value
        finally:
            # Successful individual checks survive a later failure; failures never do.
            save(path, value)


def git_gate(repository, tips, receipts):
    if git(repository, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        raise ValueError('Sanitation refused: incomplete shallow history')
    for tip in tips:
        git(repository, 'rev-parse', '--verify', tip + '^{commit}')
    accepted_path = cache_root(repository) / 'accepted-history.json'
    if not accepted_path.is_file() or accepted_path.is_symlink():
        raise ValueError('Accepted sanitation baseline is required; sealed history will not be rescanned')
    accepted = json.loads(accepted_path.read_text())
    excludes = []
    if accepted:
        # This imports an existing human-selected cleanup receipt, not a new scan.
        # Path identity guards ordinary replacement of that private receipt.
        evidence = Path(accepted['evidence'])
        if file_identity(evidence) != accepted['identity']:
            raise ValueError('Accepted sanitation evidence changed; explicit reselection required')
        excludes.append(accepted['commit'])
    excludes += [oid for oid, kind in receipts['objects'].items() if kind == 'commit']
    objects = git(repository, 'rev-list', '--objects', '--no-object-names',
                  *tips, '--not', *excludes).decode().splitlines()
    accepted_commits = []
    for oid in objects:
        if oid in receipts['objects']:
            continue
        kind = git(repository, 'cat-file', '-t', oid).decode().strip()
        size = int(git(repository, 'cat-file', '-s', oid))
        if size > MAX_FILE:
            raise ValueError('Sanitation refused: oversized Git object')
        if kind == 'tree':
            for entry in git(repository, 'ls-tree', '-z', oid).split(b'\0'):
                if not entry:
                    continue
                meta, name = entry.split(b'\t', 1)
                check(name, 'Git tree path')
                member_name(PurePosixPath(name.decode()), distribution=False)
                if meta.split()[1] == b'commit':
                    raise ValueError('Sanitation refused: unaudited submodule')
        elif kind in ('commit', 'tag', 'blob'):
            payload_check(git(repository, 'cat-file', kind, oid), 'Git ' + kind + ' ' + oid[:12])
            if kind == 'commit':
                # Also inspect complete newly changed path names, including renames.
                check(git(repository, 'diff-tree', '--root', '-m', '-r', '--no-commit-id',
                          '--name-only', '-z', oid), 'Git changed path')
        else:
            raise ValueError('Sanitation refused: unsupported Git object')
        if kind == 'commit':
            accepted_commits.append(oid)
        else:
            receipts['objects'][oid] = kind
    # Never accept a reachable commit until all of its newly exposed objects pass.
    for oid in accepted_commits:
        receipts['objects'][oid] = 'commit'


def file_identity(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Sanitation input must be a regular non-symlink file')
    s = path.stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def payload_check(data, label, budget=None, depth=0):
    if depth > 3:
        raise ValueError('Sanitation refused: nested archive depth')
    check(data, label)
    if data.startswith(b'version https://git-lfs.github.com/spec/v1'):
        raise ValueError('Sanitation refused: uninspected LFS payload')
    if data[257:262] == b'ustar':
        raise ValueError('Sanitation refused: unsupported tar payload')
    if data.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            unpacked = stream.read(MAX_FILE + 1)
        total = budget if budget is not None else [0]
        total[0] += len(unpacked)
        if len(unpacked) > MAX_FILE or total[0] > MAX_ARCHIVE:
            raise ValueError('Sanitation refused: gzip inspection size limit')
        payload_check(unpacked, label, total, depth + 1)
    elif zipfile.is_zipfile(io.BytesIO(data)):
        zip_check(io.BytesIO(data), budget if budget is not None else [0], depth + 1)
    elif data.startswith((b'BZh', b'\xfd7zXZ', b'7z\xbc\xaf\x27\x1c')):
        raise ValueError('Sanitation refused: unsupported compressed payload')


def safe_link(parent_parts, target, floor=0):
    parts = list(parent_parts)
    if PurePosixPath(target).is_absolute() or '\\' in target:
        raise ValueError('Sanitation refused: absolute or nonportable symlink')
    for part in PurePosixPath(target).parts:
        if part == '..':
            if len(parts) <= floor:
                raise ValueError('Sanitation refused: escaping symlink')
            parts.pop()
        elif part != '.':
            parts.append(part)


def member_name(path, distribution=True):
    if any(part in ('.git', '.claude', '.codex') for part in path.parts) or path.suffix.lower() in ('.p12', '.p8', '.key', '.dcm', '.dicom') or path.name.startswith('.env'):
        raise ValueError('Sanitation refused: private member type')
    if distribution and path.name in ('selection.json', 'publication.json', 'artifact-ownership.json'):
        raise ValueError('Sanitation refused: private archive member type')


def zip_check(stream, budget, depth=0):
    if depth > 3:
        raise ValueError('Sanitation refused: nested archive depth')
    with zipfile.ZipFile(stream) as archive:
        for entry in archive.infolist():
            check(entry.filename.encode(), 'archive member name')
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename:
                raise ValueError('Sanitation refused: unsafe archive member')
            member_name(path)
            budget[0] += entry.file_size
            if entry.file_size > MAX_FILE or budget[0] > MAX_ARCHIVE:
                raise ValueError('Sanitation refused: archive inspection size limit')
            data = archive.read(entry)  # CRC validation; never extracts or follows links
            check(entry.comment + entry.extra, 'archive member metadata')
            payload_check(data, 'archive member content', budget, depth)
            if stat.S_ISLNK(entry.external_attr >> 16):
                target = data.decode('utf-8', errors='strict')
                safe_link(path.parts[:-1], target, 1 if path.parts[0].endswith('.app') else 0)
        check(archive.comment, 'archive comment')


def archive_gate(path, receipts):
    path = Path(path)
    before = file_identity(path)
    key = json.dumps(before)
    if key in receipts['archives']:
        return
    if before[2] > MAX_ARCHIVE:
        raise ValueError('Sanitation refused: archive size limit')
    with path.open('rb') as stream:
        tail = b''
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            check(tail + block, 'archive container bytes')
            tail = block[-1024:]
        stream.seek(0)
        zip_check(stream, [0])
    if file_identity(path) != before:
        raise ValueError('Archive changed during sanitation inspection')
    receipts['archives'][key] = {'status': 'accepted'}


def text_gate(text, receipts):
    # In-memory new release text only; no sealed source/product hashing.
    identity = hashlib.sha256(text.encode()).hexdigest()
    if identity not in receipts['texts']:
        check(text.encode(), 'release text')
        receipts['texts'][identity] = 'accepted'


def app_gate(repository, commit, app):
    with ledger(repository) as receipts:
        git_gate(repository, [commit], receipts)
        app = Path(app)
        if app.is_symlink() or not app.is_dir():
            raise ValueError('Sanitation refused: unsafe app root')
        def failed(error):
            raise error
        for parent, directories, files in os.walk(app, followlinks=False, onerror=failed):
            for name in directories + files:
                path = Path(parent) / name
                relative = path.relative_to(app).as_posix()
                name_key = 'bundle-name:' + relative
                if name_key not in receipts['texts']:
                    check(relative.encode(), 'bundle member name')
                    member_name(PurePosixPath(relative))
                    receipts['texts'][name_key] = 'accepted'
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode):
                    target = os.readlink(path)
                    check(target.encode(), 'bundle symlink')
                    safe_link(path.relative_to(app).parts[:-1], target)
                    if not path.resolve().is_relative_to(app.resolve()):
                        raise ValueError('Sanitation refused: escaping bundle symlink')
                elif stat.S_ISREG(mode):
                    before = file_identity(path)
                    key = 'file:' + json.dumps(before)
                    if key not in receipts['archives']:
                        if before[2] > MAX_FILE:
                            raise ValueError('Sanitation refused: oversized bundle member')
                        data = path.read_bytes()
                        payload_check(data, 'bundle member content')
                        if file_identity(path) != before:
                            raise ValueError('Bundle member changed during inspection')
                        receipts['archives'][key] = {'status': 'accepted'}
                elif not stat.S_ISDIR(mode):
                    raise ValueError('Sanitation refused: special bundle member')


def release_gate(repository, commit, title, notes, archive):
    with ledger(repository) as receipts:
        git_gate(repository, [commit], receipts)
        text_gate(title + '\n' + notes, receipts)
        archive_gate(archive, receipts)


def pre_push(repository, lines):
    tips = []
    for line in lines:
        local_ref, oid, remote_ref, remote_oid = line.split()
        check((local_ref + '\n' + remote_ref).encode(), 'push reference name')
        if set(oid) != {'0'}:
            tips.append(oid)
    if tips:
        with ledger(repository) as receipts:
            git_gate(repository, tips, receipts)


def install(repository, accepted, evidence):
    # This is a local configuration action, never a remote operation.
    oid = git(repository, 'rev-parse', accepted + '^{commit}').decode().strip()
    git(repository, 'merge-base', '--is-ancestor', oid, 'HEAD')
    root = cache_root(repository)
    hook = root / 'hooks'
    existing = subprocess.run(['git', '-C', str(repository), 'config', '--get', 'core.hooksPath'], capture_output=True, text=True).stdout.strip()
    if existing not in ('', '/dev/null', str(hook), '.githooks',
                         str(Path(repository).resolve() / '.githooks')):
        raise ValueError('Existing hooks configuration requires explicit integration')
    root = cache_root(repository)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = dict(commit=oid, evidence=str(Path(evidence).resolve()), identity=file_identity(evidence),
                  scope='Existing owner-selected history sanitation acceptance; no rescan')
    target = root / 'accepted-history.json'
    if target.exists() and json.loads(target.read_text()) != record:
        raise ValueError('Accepted baseline already selected; preserve it')
    save(target, record)
    hook.mkdir(exist_ok=True, mode=0o700)
    template = Path(__file__).resolve().parents[1] / '.githooks/pre-push'
    dispatcher = hook / 'pre-push'
    dispatcher.write_bytes(template.read_bytes())
    dispatcher.chmod(0o700)
    git(repository, 'config', '--local', 'core.hooksPath', str(hook))


def main():
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('pre-push', 'install'))
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--accepted-source')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'install':
            if not args.accepted_source or not args.evidence:
                parser.error('install requires explicit accepted source and existing evidence')
            install(args.repository, args.accepted_source, args.evidence)
        else:
            pre_push(args.repository, sys.stdin)
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        # Paths/private command output must not leak into a public hook/CI log.
        print(str(exc) if isinstance(exc, ValueError) else 'Sanitation gate failed; inspect private local inputs', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
