"""Destination fault injection only; no DICOM policy, audit or corpus processing."""
import errno
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('storage_engine', Path(__file__).resolve().parents[1] / 'engine/engine.py')
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


class StorageRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.destination = self.root / 'output'
        self.events = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(engine, 'scan', return_value=([], [], 0)))
        self.check_space = engine.check_disk_space
        self.stack.enter_context(patch.object(engine, 'check_disk_space'))
        self.stack.enter_context(patch.object(engine, 'self_audit', return_value={'result': 'passed', 'files_audited': 0}))

    def progress(self, event_name, **values):
        self.events.append((event_name, values))

    def run_batch(self):
        return engine.run(self.source, self.destination, self.progress)

    def assert_issue(self, number, issue, operation):
        with patch.object(*operation, side_effect=OSError(number, '/private/source/or/output/sensitive')):
            with self.assertRaises(engine.BatchError) as failure:
                self.run_batch()
        self.assertEqual(failure.exception.output_issue, issue)
        self.assertNotIn('/private', str(failure.exception))
        self.assertNotIn('complete', [name for name, _ in self.events])
        return failure.exception

    def test_errno_groups_are_safe_and_specific(self):
        groups = {'space': [errno.ENOSPC, errno.EDQUOT],
                  'permissions': [errno.EACCES, errno.EPERM, errno.EROFS],
                  'unavailable': [errno.ENOENT, errno.ENOTDIR, errno.ENODEV, errno.ENXIO, errno.ESTALE, errno.EIO],
                  'conflict': [errno.EEXIST], 'unknown': [errno.EINVAL, None]}
        for issue, numbers in groups.items():
            for number in numbers:
                with self.subTest(issue=issue, number=number):
                    error = engine.output_error(OSError(number, '/private/sensitive'))
                    self.assertEqual(error.output_issue, issue)
                    self.assertNotIn('/private', str(error))
                    self.assertIsNone(error.required_bytes)
                    self.assertIsNone(error.available_bytes)
                    self.assertNotIn('disconnected', str(error))

    def test_stage_creation_disk_full(self):
        self.assert_issue(errno.ENOSPC, 'space', (engine.tempfile, 'mkdtemp'))
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_stage_creation_read_only(self):
        self.assert_issue(errno.EROFS, 'permissions', (engine.tempfile, 'mkdtemp'))

    def test_stage_metadata_unavailable_preserves_unknown_ownership(self):
        original = Path.lstat
        def stat(path, *args, **kwargs):
            if path.name.startswith('.dicom-batch-'):
                raise OSError(errno.EIO, '/private/sensitive')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', stat):
            with self.assertRaises(engine.BatchError) as failure:
                self.run_batch()
        self.assertEqual(failure.exception.output_issue, 'unavailable')
        self.assertTrue(failure.exception.cleanup_failed)
        self.assertIsNone(failure.exception.staging_path)
        self.assertIn('ownership could not be confirmed', str(failure.exception))
        self.assertNotIn('/private', str(failure.exception))

    def test_report_write_quota(self):
        self.assert_issue(errno.EDQUOT, 'space', (Path, 'write_text'))
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_report_write_location_unavailable(self):
        self.assert_issue(errno.ENODEV, 'unavailable', (Path, 'write_text'))

    def test_nonmac_publication_permissions(self):
        with patch.object(engine.sys, 'platform', 'storage-test'):
            self.assert_issue(errno.EACCES, 'permissions', (engine.os, 'rename'))
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_nonmac_publication_conflict(self):
        with patch.object(engine.sys, 'platform', 'storage-test'):
            self.assert_issue(errno.EEXIST, 'conflict', (engine.os, 'rename'))

    def test_mac_publication_preserves_errno(self):
        import ctypes
        library = MagicMock()
        library.renamex_np.return_value = -1
        with patch.object(engine.sys, 'platform', 'darwin'), patch.object(ctypes, 'CDLL', return_value=library), patch.object(ctypes, 'get_errno', return_value=errno.ENOSPC):
            with self.assertRaises(engine.BatchError) as failure:
                self.run_batch()
        self.assertEqual(failure.exception.output_issue, 'space')
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def fake_record(self):
        record = engine.Record(self.source / 'fake.dcm', '1', ('series',), 'instance', 'identity', (0, 0, 10, 0))
        dataset = MagicMock()
        dataset.SOPInstanceUID = 'instance'
        dataset.SOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        dataset.get.return_value = 'identity'
        dataset.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'
        self.stack.enter_context(patch.object(engine, 'scan', return_value=([record], ['1'], 0)))
        self.stack.enter_context(patch.object(engine, 'fingerprint', return_value=record.signature))
        self.stack.enter_context(patch.object(engine, 'checked_read', return_value=dataset))
        self.stack.enter_context(patch.object(engine, 'validate'))
        self.stack.enter_context(patch.object(engine, 'clean'))
        self.stack.enter_context(patch.object(engine, 'source_uids'))
        return dataset

    def test_output_folder_creation_permissions(self):
        self.fake_record()
        original = Path.mkdir
        def mkdir(path, *args, **kwargs):
            if path.name.startswith('Series_'):
                raise OSError(errno.EPERM, '/private/sensitive')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'mkdir', mkdir):
            with self.assertRaises(engine.BatchError) as failure:
                self.run_batch()
        self.assertEqual(failure.exception.output_issue, 'permissions')
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_dicom_save_disk_full_is_output_issue(self):
        dataset = self.fake_record()
        dataset.save_as.side_effect = OSError(errno.ENOSPC, '/private/sensitive')
        with self.assertRaises(engine.BatchError) as failure:
            self.run_batch()
        self.assertEqual(failure.exception.output_issue, 'space')
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_input_read_error_is_not_output_issue(self):
        self.fake_record()
        with patch.object(engine, 'checked_read', side_effect=OSError(errno.EIO, '/private/input')):
            with self.assertRaises(OSError) as failure:
                self.run_batch()
        self.assertNotIsInstance(failure.exception, engine.BatchError)
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_scan_input_error_is_not_output_issue(self):
        with patch.object(engine, 'scan', side_effect=OSError(errno.ENOSPC, '/private/input')):
            with self.assertRaises(OSError):
                self.run_batch()
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_cleanup_failure_preserves_storage_error_and_precedence(self):
        with patch.object(Path, 'write_text', side_effect=OSError(errno.ENOSPC, '/private/sensitive')), patch.object(engine.shutil, 'rmtree', side_effect=OSError(errno.EACCES, '/private/sensitive')):
            with self.assertRaises(engine.BatchError) as failure:
                self.run_batch()
        error = failure.exception
        self.assertEqual(error.output_issue, 'space')
        self.assertTrue(error.cleanup_failed)
        self.assertIn('ran out', str(error))
        self.assertIn('Incomplete output', str(error))
        self.assertNotIn('/private', str(error))
        self.assertTrue(Path(error.staging_path).is_dir())

    def test_postpublication_transport_failure_has_no_output_issue(self):
        def progress(event_name, **values):
            if event_name == 'complete':
                raise OSError(errno.ENOSPC, '/private/transport')
        with patch.object(engine.sys, 'platform', 'storage-test'):
            with self.assertRaises(engine.BatchError) as failure:
                engine.run(self.source, self.destination, progress)
        self.assertTrue(failure.exception.output_published)
        self.assertIsNone(failure.exception.output_issue)
        self.assertTrue(self.destination.is_dir())

    def test_existing_destination_conflict(self):
        self.destination.mkdir()
        with self.assertRaises(engine.BatchError) as failure:
            self.run_batch()
        self.assertEqual(failure.exception.output_issue, 'conflict')

    def test_overlapping_destination_conflict(self):
        with self.assertRaises(engine.BatchError) as failure:
            engine.run(self.source, self.source / 'output', self.progress)
        self.assertEqual(failure.exception.output_issue, 'conflict')

    def test_missing_destination_parent_unavailable(self):
        with self.assertRaises(engine.BatchError) as failure:
            engine.run(self.source, self.root / 'missing' / 'output', self.progress)
        self.assertEqual(failure.exception.output_issue, 'unavailable')

    def test_preflight_shortage_retains_formula_and_estimate(self):
        records = [SimpleNamespace(signature=(0, 0, 1000, 0))]
        expected = int(1000 * 1.1) + engine.DISK_MARGIN_BYTES
        with patch.object(engine.shutil, 'disk_usage', return_value=SimpleNamespace(free=1024)):
            with self.assertRaises(engine.BatchError) as failure:
                self.check_space(records, self.root)
        error = failure.exception
        self.assertEqual(error.output_issue, 'space')
        self.assertEqual(error.required_bytes, expected)
        self.assertEqual(error.available_bytes, 1024)
        self.assertIn('Estimated need:', str(error))
        self.assertIn('available:', str(error))
        self.assertIn('not a guarantee', str(error))

    def test_preflight_access_failure_is_output_issue(self):
        with patch.object(engine.shutil, 'disk_usage', side_effect=OSError(errno.EACCES, '/private/sensitive')):
            with self.assertRaises(engine.BatchError) as failure:
                self.check_space([], self.root)
        self.assertEqual(failure.exception.output_issue, 'permissions')
        self.assertIsNone(failure.exception.required_bytes)
        self.assertNotIn('/private', str(failure.exception))

    def emit_error(self, error):
        with patch.object(sys, 'argv', ['engine', '--source', str(self.source), '--destination', str(self.destination)]), patch.object(engine.signal, 'signal'), patch.object(engine, 'run', side_effect=error), patch.object(engine, 'emit') as emit:
            self.assertEqual(engine.main(), 1)
        return emit.call_args.kwargs

    def test_error_event_has_structured_issue_and_shortage_counts(self):
        event = self.emit_error(engine.BatchError('Safe estimate.', output_issue='space', required_bytes=100, available_bytes=20))
        self.assertEqual(event['output_issue'], 'space')
        self.assertEqual(event['required_bytes'], 100)
        self.assertEqual(event['available_bytes'], 20)

    def test_error_event_omits_counts_except_valid_shortage(self):
        for values in [('permissions', 100, 20), ('space', 10, 20), ('space', True, 0), ('space', 100, -1), ('space', None, None)]:
            with self.subTest(values=values):
                event = self.emit_error(engine.BatchError('Safe.', output_issue=values[0], required_bytes=values[1], available_bytes=values[2]))
                self.assertNotIn('required_bytes', event)
                self.assertNotIn('available_bytes', event)

    def test_postpublication_event_suppresses_storage_issue(self):
        event = self.emit_error(engine.BatchError('Published.', output_published=True, output_issue='space', required_bytes=100, available_bytes=20))
        self.assertTrue(event['output_published'])
        self.assertNotIn('output_issue', event)
        self.assertNotIn('required_bytes', event)

    def test_cleanup_event_preserves_issue_counts_and_cleanup_flag(self):
        event = self.emit_error(engine.BatchError('Safe.', cleanup_failed=True, staging_path='/owned/staging', output_issue='space', required_bytes=100, available_bytes=20))
        self.assertTrue(event['cleanup_failed'])
        self.assertEqual(event['staging_path'], '/owned/staging')
        self.assertEqual(event['output_issue'], 'space')
        self.assertEqual(event['required_bytes'], 100)


if __name__ == '__main__':
    unittest.main()
