"""Default-mode publication inventory checks on tiny synthetic batches."""
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_engine as fixtures

sys.path.insert(0, str(fixtures.ENGINE.parent))
import sidecar_deid

engine = fixtures.engine


class DicomStagingInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'input'
        fixtures.make_dicom(self.source / '00043' / 'source.dcm')
        (self.source / '00043' / 'source.json').write_text('{"PatientName":"SOURCE_ONLY"}')
        self.output = self.root / 'output'
        self.events = []
        self.outside = self.root / 'outside'
        self.outside.mkdir()
        (self.outside / 'keep').write_bytes(b'preserve outside target')

    def run_batch(self, **options):
        return engine.run(self.source, self.output,
                          progress=lambda event, **values: self.events.append((event, values)), **options)

    def after_report(self, fault):
        original = Path.write_text

        def write(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path.name == 'anonymization-report.json':
                fault(path.parent)
            return result

        return patch.object(Path, 'write_text', write)

    def assert_blocked(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])
        self.assertNotIn('complete', [event for event, _ in self.events])
        self.assertEqual((self.outside / 'keep').read_bytes(), b'preserve outside target')

    def test_late_unexpected_entries_and_missing_outputs_block_publication(self):
        def missing_dicom(stage):
            next(stage.rglob('*.dcm')).unlink()

        faults = {
            'extra_file': lambda stage: (stage / 'unproduced.txt').write_text('UNPRODUCED'),
            'extra_directory': lambda stage: (stage / 'unproduced').mkdir(),
            'file_symlink': lambda stage: (stage / 'unproduced.txt').symlink_to(self.outside / 'keep'),
            'directory_symlink': lambda stage: (stage / 'unproduced').symlink_to(self.outside, target_is_directory=True),
            'fifo': lambda stage: os.mkfifo(stage / 'unproduced.fifo'),
            'missing_dicom': missing_dicom,
            'missing_report': lambda stage: (stage / 'anonymization-report.json').unlink(),
        }
        for name, fault in faults.items():
            self.output = self.root / ('output-' + name)
            self.events.clear()
            with self.subTest(fault=name), self.after_report(fault):
                with self.assertRaises(engine.BatchError):
                    self.run_batch()
                self.assert_blocked()

    def test_uninspectable_final_inventory_maps_output_recovery(self):
        original_walk = os.walk
        faults = [(errno.EACCES, 'permissions'), (errno.ENODEV, 'unavailable')]
        for number, issue in faults:
            self.output = self.root / ('output-' + issue)
            self.events.clear()
            def walk(path, *args, **kwargs):
                if (Path(path) / 'anonymization-report.json').exists():
                    handler = kwargs.get('onerror')
                    if handler:
                        handler(OSError(number, 'SYNTHETIC_PRIVATE_LOCATION'))
                    return iter(())
                return original_walk(path, *args, **kwargs)
            with self.subTest(issue=issue), patch.object(os, 'walk', walk):
                with self.assertRaises(engine.BatchError) as caught:
                    self.run_batch()
                self.assertEqual(caught.exception.output_issue, issue)
                self.assertNotIn('SYNTHETIC_PRIVATE_LOCATION', str(caught.exception))
                self.assert_blocked()

    def test_self_audit_walk_error_cannot_be_silently_skipped(self):
        original_walk = os.walk

        def walk(path, *args, **kwargs):
            if Path(path).name.startswith('.dicom-batch-'):
                handler = kwargs.get('onerror')
                if handler:
                    handler(OSError(errno.EIO, 'SYNTHETIC_PRIVATE_LOCATION'))
                return iter(())
            return original_walk(path, *args, **kwargs)

        with patch.object(os, 'walk', walk):
            with self.assertRaises(engine.BatchError) as caught:
                self.run_batch()
        self.assertEqual(caught.exception.output_issue, 'unavailable')
        self.assert_blocked()

    def test_skipped_metadata_audit_still_requires_complete_inventory(self):
        with self.after_report(lambda stage: (stage / 'unexpected').write_text('UNPRODUCED')):
            with self.assertRaises(engine.BatchError):
                self.run_batch(audit=False)
        self.assert_blocked()

    def test_replaced_staging_root_is_preserved_and_not_published(self):
        original_stage = self.root / 'original-stage'

        def replace(stage):
            stage.rename(original_stage)
            shutil.copytree(original_stage, stage)

        with self.after_report(replace):
            with self.assertRaises(engine.BatchError) as caught:
                self.run_batch()
        self.assertTrue(caught.exception.cleanup_failed)
        self.assertIsNone(caught.exception.staging_path)
        self.assertFalse(self.output.exists())
        self.assertTrue(original_stage.is_dir())
        [replacement] = list(self.root.glob('.dicom-batch-*'))
        self.assertTrue((replacement / 'anonymization-report.json').is_file())
        self.assertNotIn('complete', [event for event, _ in self.events])

    def test_late_cancellation_during_default_inventory_cleans_owned_staging(self):
        cancellation = engine.Cancellation()
        original_seal = sidecar_deid.seal_staging_inventory
        callbacks = []

        def seal(*args, **kwargs):
            original_check = kwargs['cancel_check']

            def check():
                callbacks.append(True)
                if len(callbacks) == 2:
                    cancellation.requested = True
                original_check()

            kwargs['cancel_check'] = check
            return original_seal(*args, **kwargs)

        with patch.object(sidecar_deid, 'seal_staging_inventory', seal):
            with self.assertRaises(engine.BatchError) as caught:
                self.run_batch(cancellation=cancellation)
        self.assertTrue(caught.exception.cancelled)
        self.assertEqual(len(callbacks), 2)
        self.assert_blocked()

    def test_root_replaced_after_inventory_is_not_published_or_removed(self):
        original_seal = sidecar_deid.seal_staging_inventory
        original_stage = self.root / 'original-stage'

        def seal(stage, **kwargs):
            original_seal(stage, **kwargs)
            stage.rename(original_stage)
            shutil.copytree(original_stage, stage)

        with patch.object(sidecar_deid, 'seal_staging_inventory', seal):
            with self.assertRaises(engine.BatchError) as caught:
                self.run_batch()
        self.assertTrue(caught.exception.cleanup_failed)
        self.assertIsNone(caught.exception.staging_path)
        self.assertFalse(self.output.exists())
        self.assertTrue(original_stage.is_dir())
        [replacement] = list(self.root.glob('.dicom-batch-*'))
        self.assertTrue((replacement / 'anonymization-report.json').is_file())
        self.assertNotIn('complete', [event for event, _ in self.events])

    def test_final_inventory_lstat_error_maps_output_permissions(self):
        original_seal = sidecar_deid.seal_staging_inventory
        original_lstat = Path.lstat

        def lstat(path, *args, **kwargs):
            if path.name == 'anonymization-report.json':
                raise PermissionError(errno.EACCES, 'SYNTHETIC_PRIVATE_LOCATION')
            return original_lstat(path, *args, **kwargs)

        def seal(*args, **kwargs):
            with patch.object(Path, 'lstat', lstat):
                return original_seal(*args, **kwargs)

        with patch.object(sidecar_deid, 'seal_staging_inventory', seal):
            with self.assertRaises(engine.BatchError) as caught:
                self.run_batch()
        self.assertEqual(caught.exception.output_issue, 'permissions')
        self.assertNotIn('SYNTHETIC_PRIVATE_LOCATION', str(caught.exception))
        self.assert_blocked()

    def test_valid_default_batch_keeps_sidecars_disabled_and_report_compatible(self):
        with patch.object(sidecar_deid, 'scan_sidecars', side_effect=AssertionError('sidecars enabled')), \
             patch.object(sidecar_deid, 'clean_sidecars_to_staging', side_effect=AssertionError('sidecars enabled')), \
             patch.object(sidecar_deid, 'audit_sidecars', side_effect=AssertionError('sidecars enabled')):
            result = self.run_batch()
        report = json.loads((self.output / 'anonymization-report.json').read_text())
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['audited_files'], 1)
        self.assertEqual(report['excluded_files'], 1)
        self.assertNotIn('json_sidecars', report)
        self.assertEqual(report['audit_coverage']['json_sidecars']['result'], 'not_requested')
        self.assertEqual(len(list(self.output.rglob('*.dcm'))), 1)
        self.assertFalse(any(event.startswith('sidecar') for event, _ in self.events))
        self.assertEqual(self.events[-1][0], 'complete')
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_importing_engine_by_file_keeps_default_processing_available(self):
        script = '''
import importlib.util
import sys
spec = importlib.util.spec_from_file_location('isolated_engine', sys.argv[1])
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)
result = engine.run(sys.argv[2], sys.argv[3], progress=lambda *args, **kwargs: None)
print(result['processed'])
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
                                 str(fixtures.ENGINE), str(self.source), str(self.output)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '1')
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])


if __name__ == '__main__':
    unittest.main()
