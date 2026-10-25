"""New storage-admission fixtures only; no real package, build or distribution."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release
import release_storage as storage


class ReleaseStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='release-storage-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.guard = 'fixture-storage-guard'

    def test_missing_guard_refuses_before_assembly_or_state_writes(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(storage.shutil, 'which', return_value=None):
            with patch.object(release, 'plan', side_effect=AssertionError('accepted inputs read')):
                with self.assertRaisesRegex(storage.StorageGuardError, 'required'):
                    release.assemble(self.root / 'manifest', self.root / 'output', self.root)
            with self.assertRaises(storage.StorageGuardError):
                release.distribute(self.root / 'output', 'sign')
        self.assertFalse((self.root / 'output').exists())

    def test_forged_environment_marker_does_not_bypass_authentication(self):
        with patch.dict(os.environ, {'STORAGE_GUARD': self.guard, 'DICOM_RELEASE_GUARDED': '1',
                                    'STORAGE_GUARD_OPERATION': 'forged', 'STORAGE_GUARD_TOKEN': 'forged'}):
            with patch.object(storage.subprocess, 'run', return_value=SimpleNamespace(returncode=1)) as run:
                with self.assertRaisesRegex(storage.StorageGuardError, 'authenticated'):
                    storage.require_active(self.root)
        self.assertEqual(run.call_args.args[0], [self.guard, 'active'])
        self.assertEqual(run.call_count, 1)

    def test_valid_supervisor_preflights_actual_destination(self):
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            storage.require_active(self.root / 'new-output')
        self.assertEqual([c.args[0] for c in run.call_args_list], [
            [self.guard, 'active'], [self.guard, 'check', '--path', str(self.root / 'new-output')],
            [self.guard, 'run', '--entry', str(Path(storage.__file__).resolve()),
             '--interpreter', sys.executable, '--', '--admit-output', '--output', str(self.root / 'new-output')],
            [self.guard, 'active']])

    def test_destination_refusal_prevents_lock_or_distribution_commands(self):
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=75)]), \
             patch.object(release, 'locked', side_effect=AssertionError('lock write')):
            with self.assertRaisesRegex(storage.StorageGuardError, 'refused'):
                release.distribute(self.root, 'finalize')
        self.assertFalse((self.root / '.release.lock').exists())

    def test_unexecutable_guard_fails_closed(self):
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', side_effect=FileNotFoundError('fixture')):
            with self.assertRaisesRegex(storage.StorageGuardError, 'could not execute'):
                storage.require_active(self.root)
            with self.assertRaisesRegex(storage.StorageGuardError, 'could not start'):
                storage.supervise(['assemble', '--output', str(self.root)])

    def test_cli_allocating_actions_dispatch_without_writing(self):
        for action in ('assemble', 'sign', 'notarize', 'finalize'):
            args = [action, '--output', str(self.root / 'output')]
            if action == 'assemble':
                args += ['--manifest', str(self.root / 'manifest')]
            with self.subTest(action=action), \
                 patch.object(storage, 'supervise', return_value=75) as supervise, \
                 patch.object(release, 'assemble', side_effect=AssertionError('unguarded copy')), \
                 patch.object(release, 'distribute', side_effect=AssertionError('unguarded write')):
                self.assertEqual(75, release.main(args))
                supervise.assert_called_once_with(args)
        self.assertFalse((self.root / 'output').exists())

    def test_supervised_command_preserves_arguments_and_exit_status(self):
        args = ['sign', '--output', str(self.root / 'space in name'), '--identity', 'Developer ID Application: Fixture']
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', return_value=SimpleNamespace(returncode=75)) as run:
            self.assertEqual(75, storage.supervise(args))
        self.assertEqual(run.call_args.args[0], [self.guard, 'run', '--entry', str(Path(storage.__file__).resolve()),
                         '--interpreter', sys.executable, '--', *args])
        self.assertEqual(run.call_count, 1)

    def test_read_only_plan_and_status_do_not_dispatch_guard(self):
        status = self.root / 'status'
        status.mkdir()
        (status / 'state.json').write_text('{"steps":{}}')
        with patch.object(storage, 'supervise', side_effect=AssertionError('allocation')), \
             patch.object(storage, 'require_active', side_effect=AssertionError('admission')), \
             patch.object(release, 'plan', return_value={'status':'planned'}), \
             contextlib.redirect_stdout(io.StringIO()):
            release.main(['plan', '--manifest', str(self.root / 'manifest')])
            release.main(['status', '--output', str(status)])

    def test_worker_path_reauthenticates_before_allocating(self):
        args = ['assemble', '--manifest', str(self.root / 'manifest'), '--output', str(self.root / 'output')]
        with patch.object(storage, 'require_active', side_effect=storage.StorageGuardError('fixture refusal')) as active, \
             patch.object(storage, 'supervise', side_effect=AssertionError('recursive dispatch')), \
             patch.object(release, 'plan', side_effect=AssertionError('accepted source read')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                release.main(args, monitored=True)
        self.assertEqual(1, stopped.exception.code)
        active.assert_called_once()
        self.assertFalse((self.root / 'output').exists())

    def test_interrupted_supervisor_retains_partial_output_and_does_not_retry(self):
        partial = self.root / 'partial-output'
        partial.mkdir()
        (partial / 'payload').write_bytes(b'partial')
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', return_value=SimpleNamespace(returncode=143)) as run:
            self.assertEqual(143, storage.supervise(['assemble', '--output', str(partial)]))
            run.assert_called_once()
        self.assertEqual(b'partial', (partial / 'payload').read_bytes())
        self.assertFalse((partial / 'assembly.json').exists())

    def test_missing_output_refuses_before_dispatch(self):
        with patch.object(storage, 'supervise', side_effect=AssertionError('dispatch')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                release.main(['sign'])

    def test_missing_manifest_refuses_before_dispatch(self):
        with patch.object(storage, 'supervise', side_effect=AssertionError('dispatch')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                release.main(['assemble', '--output', str(self.root)])

    def test_configured_guard_used_without_machine_specific_fallback(self):
        with patch.dict(os.environ, {'STORAGE_GUARD': self.guard}), \
             patch.object(storage.shutil, 'which', side_effect=AssertionError('fallback')):
            self.assertEqual(self.guard, storage.executable())

    def test_authenticated_resume_preserves_completed_distribution_steps(self):
        root = self.root.resolve()
        app = root / 'fixture.app'
        identity = 'Developer ID Application: Fixture'
        steps = {
            'sign': {'status':'completed', 'output':'accepted', 'command':[
                '/usr/bin/codesign', '--force', '--options', 'runtime', '--timestamp', '--sign', identity, str(app)]},
            'signature': {'status':'completed', 'output':'accepted', 'command':[
                '/usr/bin/codesign', '--verify', '--strict', str(app)]}}
        (root / 'state.json').write_text(json.dumps({'app':'fixture.app', 'steps':steps}))
        (root / 'assembly.json').write_text(json.dumps({'release_source_commit':'a'*40}))
        before = (root / 'state.json').read_bytes()
        with patch.object(storage, 'require_active') as active, \
             patch.object(release.publication_safety, 'app_gate'), \
             patch.object(release, 'run', side_effect=AssertionError('accepted command repeated')):
            state = release.distribute(root, 'sign', identity=identity)
        active.assert_called_once_with(root)
        self.assertEqual(steps, state['steps'])
        self.assertEqual(before, (root / 'state.json').read_bytes())

    def test_successful_preflight_warning_remains_visible(self):
        warning = 'STORAGE WARNING: fixture destination near reserve\n'
        responses = [SimpleNamespace(returncode=0), SimpleNamespace(returncode=0, stderr=warning),
                     SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)]
        capture = io.StringIO()
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', side_effect=responses), \
             contextlib.redirect_stderr(capture):
            storage.require_active(self.root)
        self.assertEqual(warning, capture.getvalue())

    def test_direct_api_nested_admission_quota_refusal_prevents_writes(self):
        responses = [SimpleNamespace(returncode=0), SimpleNamespace(returncode=0),
                     SimpleNamespace(returncode=75, stderr='fixture root quota refusal\n')]
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', side_effect=responses) as run, \
             patch.object(release, 'locked', side_effect=AssertionError('lock write')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(storage.StorageGuardError, 'admission'):
                release.distribute(self.root, 'sign')
        self.assertEqual(3, run.call_count)
        self.assertIn('--admit-output', run.call_args.args[0])
        self.assertFalse((self.root / '.release.lock').exists())

    def test_parent_loss_after_nested_admission_prevents_writes(self):
        responses = [SimpleNamespace(returncode=0), SimpleNamespace(returncode=0),
                     SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', side_effect=responses), \
             patch.object(release, 'plan', side_effect=AssertionError('accepted source read')):
            with self.assertRaisesRegex(storage.StorageGuardError, 'authenticated'):
                release.assemble(self.root / 'manifest', self.root / 'output', self.root)
        self.assertFalse((self.root / 'output').exists())

    def test_admission_worker_authenticates_without_copying_or_dispatch(self):
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run, \
             patch.object(release, 'main', side_effect=AssertionError('distribution dispatch')):
            self.assertEqual(0, storage.main(['--admit-output', '--output', str(self.root / 'output')]))
        run.assert_called_once_with([self.guard, 'active'], capture_output=True, text=True)
        self.assertFalse((self.root / 'output').exists())

    def test_admission_worker_refuses_unauthenticated_invocation(self):
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', return_value=SimpleNamespace(returncode=1)), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                storage.main(['--admit-output', '--output', str(self.root / 'output')])
        self.assertEqual(1, stopped.exception.code)
        self.assertFalse((self.root / 'output').exists())

    def test_nested_admission_operational_warning_remains_visible(self):
        warning = 'STORAGE WARNING: fixture nested admission\n'
        responses = [SimpleNamespace(returncode=0), SimpleNamespace(returncode=0),
                     SimpleNamespace(returncode=0, stderr=warning), SimpleNamespace(returncode=0)]
        capture = io.StringIO()
        with patch.object(storage, 'executable', return_value=self.guard), \
             patch.object(storage.subprocess, 'run', side_effect=responses), \
             contextlib.redirect_stderr(capture):
            storage.require_active(self.root)
        self.assertEqual(warning, capture.getvalue())


if __name__ == '__main__':
    unittest.main()
