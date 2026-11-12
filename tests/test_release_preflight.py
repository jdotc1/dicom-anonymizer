"""Tiny local metadata/snapshot fixtures; no real package or admission actions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'release_preflight.py'
REPOSITORY = SCRIPT.parent.parent


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        (self.inputs / 'baseline.app').mkdir()
        for name in ('native', 'receipt.json', 'metadata.json'):
            (self.inputs / name).write_text('accepted fixture')
        self.current = self.make_release('current', 3)
        self.older = self.make_release('older', 2)
        self.output = self.root / 'candidate'
        self.policy = self.root / 'policy.json'
        self.registry = self.root / 'registry.json'
        common = subprocess.check_output(['git', 'rev-parse', '--git-common-dir'], cwd=REPOSITORY, text=True).strip()
        self.common = str((REPOSITORY / common).resolve())
        self.project = 'git:' + self.common
        self.policy_value = {'max_export_roots': 2, 'projects': []}
        self.registry_value = {'version': 1, 'roots': {self.project: {}}, 'operations': {}}
        self.write(self.policy, self.policy_value)
        self.write(self.registry, self.registry_value)

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value))

    def make_release(self, name, build):
        root = self.root / name
        root.mkdir()
        (root / 'DICOM Anonymizer 2.0.app').mkdir()
        (root / 'download.zip').write_bytes(b'fixture archive')
        sha = str(build) * 40
        tag = 'v2.0.0-preview.' + str(build)
        values = {
            'state.json': {'schema': 1, 'app': 'DICOM Anonymizer 2.0.app', 'notarization': {'status': 'Accepted'}, 'steps': {key: {'status': 'completed'} for key in ('sign', 'signature', 'staple', 'staple_validation', 'gatekeeper', 'download')}},
            'assembly.json': {'schema': 1, 'variant': 'public', 'release': tag, 'bundle_build': str(build), 'release_source_commit': sha},
            'selection.json': {'profile': {'variant': 'public', 'bundle_identifier': 'io.github.jdotc1.dicom-anonymizer'}, 'release_source_commit': sha, 'baseline': str(self.inputs / 'baseline.app'), 'product': str(self.inputs / 'native'), 'manifest': {'schema': 1, 'release': tag, 'build': str(build), 'accepted': {'receipt': str(self.inputs / 'receipt.json'), 'build_metadata': str(self.inputs / 'metadata.json')}}},
            'publication.json': {'selection': {'repository': 'jdotc1/dicom-anonymizer', 'tag': tag, 'target': sha, 'archive': str(root / 'download.zip'), 'identity': []}, 'operations': {key: {'status': 'completed'} for key in ('create', 'upload', 'publish')}, 'url': 'https://github.com/jdotc1/dicom-anonymizer/releases/tag/' + tag},
        }
        for filename, value in values.items():
            self.write(root / filename, value)
        return root

    def command(self, *extra):
        return [sys.executable, '-B', str(SCRIPT), '--current', str(self.current), '--candidate-output', str(self.output), '--guard-policy', str(self.policy), '--guard-registry', str(self.registry), *map(str, extra)]

    def run_plan(self, *extra):
        before = {path: path.read_bytes() for path in (self.policy, self.registry)}
        result = subprocess.run(self.command(*extra), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        return json.loads(result.stdout)

    def register(self, path, kind='export'):
        self.registry_value['roots'][self.project][str(path)] = {'kind': kind, 'created': 1}
        self.write(self.registry, self.registry_value)

    def test_available_capacity_is_advisory_and_writes_nothing(self):
        self.register(self.current)
        result = self.run_plan('--superseded', self.older)
        self.assertEqual(result['capacity']['status'], 'available')
        self.assertEqual(result['capacity']['effective_export_roots'], 1)
        self.assertFalse(result['admission_authorized'])
        self.assertFalse(result['reserve_checked'])
        self.assertIn(str(self.inputs / 'native'), result['protected_paths'])
        self.assertEqual(result['superseded'][0]['status'], 'metadata_eligible_for_retirement_plan')

    def test_full_capacity_requires_explicit_retirement_and_preserves_receipts(self):
        self.register(self.current)
        self.register(self.older)
        (self.older / 'receipt.json').write_text('preserve historical evidence')
        result = self.run_plan('--superseded', self.older)
        self.assertEqual(result['capacity']['status'], 'retirement_needed')
        self.assertEqual(result['capacity']['additional_slots_needed'], 1)
        self.assertIn('metadata', result['capacity']['retirement_note'])
        self.assertEqual((self.older / 'receipt.json').read_text(), 'preserve historical evidence')
        self.assertEqual(result['next_steps'][0]['action'], 'plan_retirement')
        self.assertFalse(result['next_steps'][0]['deletion_authorized'])

    def test_missing_inactive_roots_are_ignored_without_editing_registry(self):
        self.register(self.current)
        self.register(self.root / 'missing-old-export')
        result = self.run_plan()
        self.assertEqual(result['capacity']['effective_export_roots'], 1)
        self.assertEqual(result['capacity']['stale_paths_ignored_in_prediction'], [str(self.root / 'missing-old-export')])
        self.assertEqual(result['capacity']['status'], 'available')

    def test_missing_active_registered_root_still_consumes_capacity(self):
        missing = self.root / 'not-created-yet'
        self.register(self.current)
        self.register(missing)
        self.registry_value['operations'] = {'fixture': {'project': self.project, 'roots': [str(missing)]}}
        self.write(self.registry, self.registry_value)
        result = self.run_plan()
        self.assertEqual(result['capacity']['effective_export_roots'], 2)
        self.assertEqual(result['capacity']['missing_but_active_export_paths'], [str(missing)])
        self.assertEqual(result['capacity']['status'], 'retirement_needed')

    def test_unclassified_active_project_root_is_counted_conservatively(self):
        missing = self.root / 'pending'
        self.register(self.current)
        self.registry_value['operations'] = {'fixture': {'project': self.project, 'roots': [str(missing)]}}
        self.write(self.registry, self.registry_value)
        result = self.run_plan()
        self.assertEqual(result['capacity']['effective_export_roots'], 2)
        self.assertEqual(result['capacity']['conservatively_counted_active_paths'], [str(missing)])

    def test_exact_common_directory_override_is_honored(self):
        self.register(self.current)
        self.register(self.older)
        self.policy_value['projects'] = [{'common_dir': self.common, 'max_export_roots': 3}]
        self.write(self.policy, self.policy_value)
        result = self.run_plan()
        self.assertEqual(result['capacity']['limit'], 3)
        self.assertEqual(result['capacity']['status'], 'available')

    def test_build_roots_do_not_consume_export_capacity(self):
        self.register(self.current)
        self.register(self.inputs, 'build')
        result = self.run_plan()
        self.assertEqual(result['capacity']['registered_export_roots'], 1)
        self.assertEqual(result['capacity']['effective_export_roots'], 1)

    def test_malformed_or_unsupported_snapshots_never_claim_capacity(self):
        fixtures = [
            ({'max_export_roots': True}, self.registry_value),
            ({'max_export_roots': 0}, self.registry_value),
            ({'max_export_roots': 2, 'projects': {}}, self.registry_value),
            ({'max_export_roots': 2, 'projects': [{'common_dir': self.common}, {'common_dir': self.common}]}, self.registry_value),
            (self.policy_value, {'version': 2, 'roots': {}, 'operations': {}}),
            (self.policy_value, {'version': True, 'roots': {}, 'operations': {}}),
            (self.policy_value, {'version': 1, 'roots': [], 'operations': {}}),
            (self.policy_value, {'version': 1, 'roots': {self.project: {str(self.current): {'kind': 'unknown'}}}, 'operations': {}}),
            (self.policy_value, {'version': 1, 'roots': {}, 'operations': {'x': {'project': self.project}}}),
            (self.policy_value, {'version': 1, 'roots': {self.project: {'relative': {'kind': 'export'}}}, 'operations': {}}),
        ]
        for policy, registry in fixtures:
            with self.subTest(policy=policy, registry=registry):
                self.write(self.policy, policy)
                self.write(self.registry, registry)
                result = subprocess.run(self.command(), capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
                self.assertFalse(self.output.exists())

    def test_current_baseline_candidate_is_explicitly_protected(self):
        selected = json.loads((self.current / 'selection.json').read_text())
        selected['baseline'] = str(self.older / 'DICOM Anonymizer 2.0.app')
        self.write(self.current / 'selection.json', selected)
        result = self.run_plan('--superseded', self.older)
        self.assertEqual(result['superseded'][0]['status'], 'protected')

    def test_incomplete_candidate_is_not_adopted_as_eligible(self):
        state = json.loads((self.older / 'state.json').read_text())
        state['steps']['download']['status'] = 'started'
        self.write(self.older / 'state.json', state)
        result = self.run_plan('--superseded', self.older)
        self.assertEqual(result['superseded'][0]['status'], 'not_metadata_eligible')

    def test_output_under_current_release_is_rejected(self):
        self.output = self.current / 'candidate'
        result = subprocess.run(self.command(), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.output.exists())

    def test_active_output_is_reported_as_busy_without_reserving_it(self):
        self.registry_value['operations'] = {'fixture': {'project': self.project, 'roots': [str(self.output)]}}
        self.write(self.registry, self.registry_value)
        result = self.run_plan()
        self.assertEqual(result['capacity']['status'], 'active_destination')
        self.assertFalse(result['admission_authorized'])

    def test_existing_output_is_not_overwritten(self):
        self.output.mkdir()
        keep = self.output / 'keep'
        keep.write_bytes(b'existing destination')
        result = subprocess.run(self.command(), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(keep.read_bytes(), b'existing destination')

    def test_duplicate_superseded_arguments_are_rejected_before_recipe(self):
        result = subprocess.run(self.command('--superseded', self.older, self.older), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')

    def test_symlink_snapshot_is_rejected(self):
        target = self.root / 'real-policy.json'
        self.policy.rename(target)
        self.policy.symlink_to(target)
        result = subprocess.run(self.command(), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)

    def test_metadata_plan_does_not_traverse_or_hash_app_payload(self):
        os.mkfifo(self.current / 'DICOM Anonymizer 2.0.app' / 'fixture-payload.fifo')
        result = self.run_plan()
        self.assertEqual(result['capacity']['status'], 'available')

    def test_write_shaped_output_option_is_not_an_alias_for_candidate(self):
        command = self.command()
        if '--candidate-output' in command:
            command[command.index('--candidate-output')] = '--output'
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
