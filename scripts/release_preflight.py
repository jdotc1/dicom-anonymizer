#!/usr/bin/env python3
"""Read-only release-capacity snapshot; never authorizes admission or cleanup."""
import argparse
import json
import os
from pathlib import Path
import subprocess

import retire_artifacts as retirement

REPOSITORY = Path(__file__).resolve().parents[1]
SNAPSHOT_LIMIT = 16 * 1024 * 1024


def snapshot(path):
    path = retirement.canonical(path)
    if not path.is_file():
        raise ValueError('A regular guard snapshot file is required')
    with path.open('rb') as stream:
        data = stream.read(SNAPSHOT_LIMIT + 1)
    if len(data) > SNAPSHOT_LIMIT:
        raise ValueError('Guard snapshot exceeds the supported metadata limit')
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError('Guard snapshot must be an object')
    return value


def absolute(value):
    if not isinstance(value, str) or not value or not os.path.isabs(value) or os.path.normpath(value) != value:
        raise ValueError('Guard snapshot paths must be canonical absolute strings')
    return value


def capacity(policy, registry, common, output):
    if registry.get('version') != 1 or isinstance(registry.get('version'), bool):
        raise ValueError('Unsupported guard registry version')
    if not isinstance(registry.get('roots'), dict) or not isinstance(registry.get('operations'), dict):
        raise ValueError('Guard registry roots and operations must be objects')
    projects = policy.get('projects', [])
    if not isinstance(projects, list) or any(not isinstance(item, dict) for item in projects):
        raise ValueError('Guard project policy must be an array of objects')
    matches = [item for item in projects if item.get('common_dir') == common]
    if len(matches) > 1:
        raise ValueError('Ambiguous project-specific guard policy')
    limit = matches[0].get('max_export_roots', policy.get('max_export_roots')) if matches else policy.get('max_export_roots')
    if type(limit) is not int or limit <= 0:
        raise ValueError('A positive integer export-root limit is required')
    project = 'git:' + common
    all_active = set()
    project_active = set()
    for operation in registry['operations'].values():
        if (not isinstance(operation, dict) or not isinstance(operation.get('project'), str) or
                not isinstance(operation.get('roots'), list)):
            raise ValueError('Unsupported active-operation snapshot')
        roots = {absolute(path) for path in operation['roots']}
        all_active.update(roots)
        if operation['project'] == project:
            project_active.update(roots)
    entries = registry['roots'].get(project, {})
    if not isinstance(entries, dict):
        raise ValueError('Project root registration must be an object')
    exports, stale, active_missing = [], [], []
    for path, metadata in entries.items():
        absolute(path)
        if not isinstance(metadata, dict) or metadata.get('kind') not in ('export', 'build'):
            raise ValueError('Unsupported registered-root metadata')
        if Path(path).exists() or path in all_active:
            if metadata['kind'] == 'export':
                exports.append(path)
                if not Path(path).exists():
                    active_missing.append(path)
        else:
            stale.append(path)
    # A snapshot may be observed between an operation's reservation and its
    # registration. Unknown active destinations count as potential exports.
    unclassified_active = project_active - set(entries)
    count = len(exports) + len(unclassified_active)
    status = 'active_destination' if str(output) in all_active else 'available' if count < limit else 'retirement_needed'
    return {
        'status': status, 'project': project, 'limit': limit,
        'registered_export_roots': len([entry for entry in entries.values() if entry['kind'] == 'export']),
        'effective_export_roots': count, 'additional_slots_needed': max(0, count + 1 - limit),
        'existing_or_active_export_paths': sorted(exports),
        'missing_but_active_export_paths': sorted(active_missing),
        'conservatively_counted_active_paths': sorted(unclassified_active),
        'stale_paths_ignored_in_prediction': sorted(stale),
        'retirement_note': 'Removing app/ZIP children alone does not free a registered directory while metadata remains. Evidence preservation and retirement of the obsolete directory require a separately approved operation.',
    }


def plan(current, output, guard_policy, guard_registry, superseded=()):
    current_record = retirement.record(current)
    retirement.require_current(current_record)
    output = retirement.canonical(output)
    protected = [REPOSITORY.resolve(), *map(Path, current_record['protected'])]
    if output.exists() or output.is_symlink():
        raise ValueError('Proposed assembly output must be new')
    if any(retirement.overlaps(output, path) for path in protected):
        raise ValueError('Proposed assembly output overlaps a protected input')
    superseded = [retirement.canonical(path) for path in superseded]
    if any(retirement.overlaps(first, second)
           for index, first in enumerate(superseded) for second in superseded[index + 1:]):
        raise ValueError('Superseded release roots must be distinct and non-overlapping')
    raw = subprocess.check_output(['git', '-C', str(REPOSITORY), 'rev-parse', '--git-common-dir'], text=True).strip()
    common = str((REPOSITORY / raw).resolve())
    prediction = capacity(snapshot(guard_policy), snapshot(guard_registry), common, output)
    candidates = []
    for path in superseded:
        item = {'path': str(path), 'status': 'metadata_eligible_for_retirement_plan', 'deletion_authorized': False}
        if any(retirement.overlaps(path, protected_path) for protected_path in protected):
            item.update(status='protected', reason='Overlaps the current release, source or an accepted input')
        else:
            try:
                old = retirement.record(path)
                if old['build'] >= current_record['build']:
                    raise ValueError('Not older')
                item.update(build=old['build'], registered_export_root=str(path) in prediction['existing_or_active_export_paths'])
            except (ValueError, KeyError, TypeError, OSError):
                item.update(status='not_metadata_eligible', reason='Not a complete older public release with consistent metadata')
        candidates.append(item)
    eligible = [item['path'] for item in candidates if item['status'] == 'metadata_eligible_for_retirement_plan']
    next_steps = []
    if prediction['status'] == 'retirement_needed' and eligible:
        next_steps.append({'action': 'plan_retirement', 'deletion_authorized': False,
                           'arguments': ['--current', current_record['root'], '--superseded', *eligible, '--plan-file', 'CHOOSE_NEW_PRIVATE_PLAN_PATH'],
                           'tool': 'scripts/retire_artifacts.py'})
    next_steps.extend([
        {'action': 'obtain_explicit_approval_before_apply_or_metadata_preservation', 'deletion_authorized': False},
        {'action': 'use_guarded_release_tooling_for_actual_admission', 'admission_authorized': False},
    ])
    return {'schema': 1, 'mode': 'read-only-snapshot', 'capacity': prediction,
            'current_release': current_record['root'], 'proposed_output': str(output),
            'protected_paths': list(map(str, protected)), 'superseded': candidates,
            'next_steps': next_steps, 'admission_authorized': False, 'reserve_checked': False,
            'limitations': ['Snapshot can become stale; it is not a reservation or authoritative guard admission.',
                            'Metadata eligibility is not artifact ownership/identity acceptance; the retirement planner must perform its existing checks.',
                            'No source/package hash, signature, filesystem tree inventory, cleanup or guard-state modification is performed.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--guard-policy', type=Path, required=True)
    parser.add_argument('--guard-registry', type=Path, required=True)
    parser.add_argument('--superseded', type=Path, nargs='*', default=[])
    args = parser.parse_args()
    try:
        print(json.dumps(plan(args.current, args.output, args.guard_policy, args.guard_registry, args.superseded), indent=2))
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError):
        parser.exit(1, 'Release-capacity preflight failed; inspect the explicit private metadata inputs.\n')


if __name__ == '__main__':
    main()
