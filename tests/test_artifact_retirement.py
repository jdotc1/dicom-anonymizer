"""Tiny retirement fixtures only; no accepted app/package or remote operations."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import retire_artifacts as retire


class RetirementTests(unittest.TestCase):
    def setUp(self):
        for name in ('app_gate', 'archive_gate', 'ledger'):
            gate = patch.object(retire.release.publication_safety, name)
            gate.start()
            self.addCleanup(gate.stop)
        temporary = tempfile.TemporaryDirectory(prefix='retirement-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.current = self.root / 'current'
        self.old = self.root / 'old'
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        for name in ('native', 'receipt.json', 'metadata.json'):
            (self.inputs / name).write_text('protected')
        self.make_release(self.current, 2)
        self.make_release(self.old, 1)
        self.plan_file = self.root / 'retirement.json'

    def write(self, path, value):
        path.write_text(json.dumps(value))

    def make_release(self, root, build):
        root.mkdir()
        app = root / retire.APP
        (app / 'Contents/Resources').mkdir(parents=True)
        for name in ('Info.plist', 'Resources/BuildInfo.json', 'Resources/ReleaseInfo.json'):
            (app / 'Contents' / name).write_text('metadata preserved')
        (app / 'Contents/payload').write_bytes(b'tiny synthetic app')
        for name in ('download.zip', 'notarization-upload.zip'):
            (root / name).write_bytes(b'synthetic archive')
        tag = 'v2.0.0-preview.' + str(build)
        sha = str(build) * 40
        state = dict(schema=1, app=retire.APP, notarization={'status': 'Accepted'}, steps={
            name: {'status': 'completed'} for name in ('sign', 'signature', 'staple', 'staple_validation', 'gatekeeper', 'download')})
        selected = dict(profile={'variant': 'public', 'bundle_identifier': 'io.github.jdotc1.dicom-anonymizer'},
                        release_source_commit=sha, baseline=str(self.inputs / 'baseline.app'), product=str(self.inputs / 'native'),
                        manifest=dict(schema=1, release=tag, build=str(build), accepted=dict(receipt=str(self.inputs / 'receipt.json'), build_metadata=str(self.inputs / 'metadata.json'))))
        assembly = dict(schema=1, variant='public', release=tag, bundle_build=str(build), release_source_commit=sha)
        download = (root / 'download.zip').stat()
        publication = dict(selection=dict(repository='jdotc1/dicom-anonymizer', tag=tag, target=sha, archive=str(root / 'download.zip'), identity=[download.st_dev, download.st_ino, download.st_size, download.st_mtime_ns, download.st_ctime_ns]),
                           operations={name: {'status': 'completed'} for name in ('create', 'upload', 'publish')},
                           url='https://github.com/jdotc1/dicom-anonymizer/releases/tag/' + tag)
        for name, value in [('state.json', state), ('selection.json', selected), ('assembly.json', assembly), ('publication.json', publication)]:
            self.write(root / name, value)
        (root / 'receipt.json').write_text('historical receipt')
        (root / 'build.log').write_text('accepted log')
        (root / 'original.dcm').write_bytes(b'original outside artifact allowlist')
        retire.release.record_artifact_ownership(root)

    def plan(self):
        return retire.plan(self.current, [self.old], self.plan_file)

    def edit(self, root, name, callback):
        path = root / name
        value = json.loads(path.read_text()); callback(value); self.write(path, value)

    def test_plan_only_preserves_every_artifact(self):
        plan = self.plan()
        self.assertEqual(len(plan['entries']), 3)
        self.assertTrue(all(Path(e['path']).exists() for e in plan['entries']))
        self.assertFalse(Path(str(self.plan_file) + '.journal.json').exists())

    def test_apply_retains_current_inputs_receipts_logs_and_metadata(self):
        self.plan(); journal = retire.apply(self.plan_file)
        self.assertTrue(all(v['status'] == 'retired' for v in journal['entries'].values()))
        for name in retire.NAMES:
            self.assertFalse((self.old / name).exists())
            self.assertTrue((self.current / name).exists())
        for name in ('state.json', 'selection.json', 'assembly.json', 'publication.json', 'receipt.json', 'build.log', 'original.dcm'):
            self.assertTrue((self.old / name).exists())
        self.assertEqual((self.inputs / 'native').read_text(), 'protected')
        self.assertEqual(len(journal['entries'][str(self.old / retire.APP)]['bundle_metadata']), 3)

    def test_repeated_apply_is_noop_and_reappearing_artifact_refused(self):
        self.plan(); first = retire.apply(self.plan_file)
        self.assertEqual(retire.apply(self.plan_file), first)
        (self.old / 'download.zip').write_bytes(b'replacement')
        with self.assertRaisesRegex(ValueError, 'Started/retired artifact exists'):
            retire.apply(self.plan_file)
        self.assertTrue((self.old / 'download.zip').exists())

    def test_uncertain_and_incomplete_publication_refused(self):
        self.edit(self.old, 'publication.json', lambda d: d['operations']['publish'].update(status='started'))
        with self.assertRaisesRegex(ValueError, 'Incomplete or uncertain'):
            self.plan()
        self.assertTrue((self.old / retire.APP).exists())

    def test_current_and_newer_release_never_selected(self):
        with self.assertRaises(ValueError):
            retire.plan(self.current, [self.current], self.plan_file)
        self.edit(self.old, 'assembly.json', lambda d: d.update(bundle_build='3'))
        self.edit(self.old, 'selection.json', lambda d: d['manifest'].update(build='3'))
        self.edit(self.old, 'artifact-ownership.json', lambda d: d.update(build='3'))
        with self.assertRaisesRegex(ValueError, 'older'):
            self.plan()

    def test_current_baseline_and_hardlinked_archive_are_skipped(self):
        self.edit(self.current, 'selection.json', lambda d: d.update(baseline=str(self.old / retire.APP)))
        (self.old / 'download.zip').unlink()
        os.link(self.current / 'download.zip', self.old / 'download.zip')
        plan = self.plan()
        self.assertEqual([e['name'] for e in plan['entries']], ['notarization-upload.zip'])
        self.assertEqual(len(plan['skipped']), 2)

    def test_symlink_root_and_source_checkout_refused(self):
        link = self.root / 'link'; link.symlink_to(self.old, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            retire.plan(self.current, [link], self.plan_file)
        (self.old / '.git').mkdir()
        with self.assertRaisesRegex(ValueError, 'Source checkout'):
            self.plan()

    def test_symlink_inside_app_never_deletes_external_target(self):
        external = self.root / 'external'; external.write_text('retain')
        (self.old / retire.APP / 'Contents/link').symlink_to(external)
        (self.old / 'artifact-ownership.json').unlink()
        retire.release.record_artifact_ownership(self.old)
        self.plan(); retire.apply(self.plan_file)
        self.assertEqual(external.read_text(), 'retain')

    def test_nested_change_aborts_all_deletion(self):
        self.plan()
        (self.old / retire.APP / 'Contents/payload').write_bytes(b'changed nested input')
        with self.assertRaisesRegex(ValueError, 'changed or disappeared'):
            retire.apply(self.plan_file)
        self.assertTrue(all((self.old / name).exists() for name in retire.NAMES))

    def test_changed_metadata_and_forged_candidate_refused(self):
        self.plan()
        self.edit(self.plan_file.parent, self.plan_file.name, lambda d: d['entries'][0].update(path=str(self.inputs / 'native')))
        with self.assertRaisesRegex(ValueError, 'unowned artifact'):
            retire.apply(self.plan_file)
        self.assertTrue((self.inputs / 'native').exists())

    def test_incomplete_distribution_and_plan_inside_release_refused(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            retire.plan(self.current, [self.old], self.current / 'cleanup.json')
        self.edit(self.old, 'state.json', lambda d: d['steps']['gatekeeper'].update(status='started'))
        with self.assertRaisesRegex(ValueError, 'Incomplete or uncertain'):
            self.plan()

    def test_interruption_after_deletion_reconciles_absence_without_retry(self):
        self.plan()
        def lost_response(path):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
            raise OSError('interruption after deletion')
        with self.assertRaises(OSError):
            retire.apply(self.plan_file, remove=lost_response)
        journal = retire.apply(self.plan_file)
        self.assertTrue(all(e['status'] == 'retired' for e in journal['entries'].values()))

    def test_partial_deletion_stops_and_preserves_uncertain_journal(self):
        self.plan()
        def partial(path):
            (path / 'Contents/payload').unlink()
            raise OSError('partial interruption')
        with self.assertRaises(OSError):
            retire.apply(self.plan_file, remove=partial)
        with self.assertRaisesRegex(ValueError, 'partial deletion'):
            retire.apply(self.plan_file)
        self.assertTrue((self.old / 'download.zip').exists())
        self.assertEqual(json.loads(Path(str(self.plan_file) + '.journal.json').read_text())['entries'][str(self.old / retire.APP)]['status'], 'started')

    def test_changed_plan_after_started_is_refused(self):
        self.plan()
        with self.assertRaises(OSError):
            retire.apply(self.plan_file, remove=lambda p: (_ for _ in ()).throw(OSError('stop')))
        self.edit(self.plan_file.parent, self.plan_file.name, lambda d: d.update(edited=True))
        with self.assertRaisesRegex(ValueError, 'Plan changed'):
            retire.apply(self.plan_file)

    def test_existing_release_lock_prevents_deletion(self):
        self.plan(); (self.old / '.release.lock').write_text('active')
        with self.assertRaises(FileExistsError):
            retire.apply(self.plan_file)
        self.assertTrue(all((self.old / name).exists() for name in retire.NAMES))

    def test_replacement_before_planning_is_not_adopted(self):
        (self.old / 'download.zip').unlink()
        (self.old / 'download.zip').write_bytes(b'unrelated replacement')
        with self.assertRaisesRegex(ValueError, 'Published download was replaced'):
            self.plan()
        self.assertTrue((self.old / retire.APP).exists())

    def test_missing_current_input_after_plan_prevents_all_retirement(self):
        self.plan(); (self.inputs / 'native').unlink()
        with self.assertRaisesRegex(ValueError, 'Current accepted native'):
            retire.apply(self.plan_file)
        self.assertTrue(all((self.old / name).exists() for name in retire.NAMES))

    def test_missing_current_app_after_plan_prevents_retirement(self):
        self.plan(); shutil.rmtree(self.current / retire.APP)
        with self.assertRaisesRegex(ValueError, 'Current retained assembly'):
            retire.apply(self.plan_file)
        self.assertTrue(all((self.old / name).exists() for name in retire.NAMES))

    def test_missing_current_download_after_plan_prevents_retirement(self):
        self.plan(); (self.current / 'download.zip').unlink()
        with self.assertRaisesRegex(ValueError, 'Current retained assembly'):
            retire.apply(self.plan_file)
        self.assertTrue(all((self.old / name).exists() for name in retire.NAMES))

    def test_changed_release_metadata_after_plan_prevents_retirement(self):
        self.plan()
        self.edit(self.old, 'assembly.json', lambda d: d.update(note='later edit'))
        with self.assertRaisesRegex(ValueError, 'metadata changed'):
            retire.apply(self.plan_file)
        self.assertTrue(all((self.old / name).exists() for name in retire.NAMES))

    def test_legacy_unbound_app_and_upload_are_retained(self):
        (self.old / 'artifact-ownership.json').unlink()
        plan = self.plan()
        self.assertEqual([e['name'] for e in plan['entries']], ['download.zip'])
        retire.apply(self.plan_file)
        self.assertTrue((self.old / retire.APP).exists())
        self.assertTrue((self.old / 'notarization-upload.zip').exists())

    def test_cross_device_entry_refused(self):
        original = Path.lstat
        other = self.old / retire.APP / 'Contents/payload'
        def switched(path):
            value = original(path)
            if path == other:
                return SimpleNamespace(st_dev=value.st_dev + 1, st_ino=value.st_ino,
                    st_mode=value.st_mode, st_size=value.st_size,
                    st_mtime_ns=value.st_mtime_ns, st_ctime_ns=value.st_ctime_ns)
            return value
        with patch.object(Path, 'lstat', switched):
            with self.assertRaisesRegex(ValueError, 'Cross-device'):
                retire.tree(self.old / retire.APP)

    def test_traversal_error_is_fatal(self):
        def failed(*args, **kwargs):
            kwargs['onerror'](PermissionError('unreadable subtree'))
            return iter(())
        with patch.object(retire.release.os, 'walk', failed):
            with self.assertRaises(PermissionError):
                retire.tree(self.old / retire.APP)

    def test_cli_plan_apply_are_separate_and_conflicting_flags_refused(self):
        command = [sys.executable, str(Path(retire.__file__)), '--plan-file', str(self.plan_file)]
        planned = subprocess.run(command + ['--current', str(self.current), '--superseded', str(self.old)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(planned.stdout)['mode'], 'plan-only')
        self.assertTrue((self.old / 'download.zip').exists())
        bad = subprocess.run(command + ['--apply', '--current', str(self.current)], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertTrue((self.old / 'download.zip').exists())
        applied = subprocess.run(command + ['--apply'], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(applied.stdout)['mode'], 'applied')

    def test_broken_ownership_symlink_is_never_overwritten(self):
        ledger = self.old / 'artifact-ownership.json'
        ledger.unlink(); ledger.symlink_to(self.root / 'missing-ledger-target')
        with self.assertRaisesRegex(ValueError, 'already recorded'):
            retire.release.record_artifact_ownership(self.old)
        state = dict(schema=1, app=retire.APP, notarization={'status':'Accepted'}, steps={})
        self.write(self.old / 'state.json', state)
        with patch.object(retire.release, 'run', side_effect=AssertionError('distribution should not start')):
            with self.assertRaisesRegex(ValueError, 'already exists'):
                retire.release.distribute(self.old, 'finalize')
        self.assertTrue(ledger.is_symlink())

    def test_finalize_records_new_ownership_but_never_adopts_legacy_on_resume(self):
        (self.old / 'artifact-ownership.json').unlink()
        (self.old / 'download.zip').unlink()
        state = dict(schema=1, app=retire.APP, notarization={'status':'Accepted'}, steps={})
        self.write(self.old / 'state.json', state)
        def runner(command):
            if command[0] == '/usr/bin/ditto':
                Path(command[-1]).write_bytes(b'new synthetic archive')
            return 'fixture output'
        with patch.object(retire.release, 'run', runner):
            retire.release.distribute(self.old, 'finalize')
        self.assertTrue((self.old / 'artifact-ownership.json').is_file())
        (self.old / 'artifact-ownership.json').unlink()
        with patch.object(retire.release, 'run', side_effect=AssertionError('unchanged step rerun')):
            retire.release.distribute(self.old, 'finalize')
        self.assertFalse((self.old / 'artifact-ownership.json').exists())


if __name__ == '__main__':
    unittest.main()
