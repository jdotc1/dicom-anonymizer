"""Changed publication/cancellation/cleanup contract; no DICOM policy processing."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publication_engine', Path(__file__).resolve().parents[1] / 'engine/engine.py')
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


class PublicationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.destination = self.root / 'output'
        self.cancellation = engine.Cancellation()
        self.events = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(engine, 'scan', return_value=([], [], 0)))
        self.stack.enter_context(patch.object(engine, 'check_disk_space'))
        self.stack.enter_context(patch.object(engine, 'self_audit', return_value={'result': 'passed', 'files_audited': 0}))

    def progress(self, event_name, **values):
        self.events.append((event_name, values))

    def run_batch(self, progress=None):
        return engine.run(self.source, self.destination, progress or self.progress, cancellation=self.cancellation)

    def test_cancel_before_publication_removes_staging_and_has_no_complete(self):
        def progress(event_name, **values):
            self.progress(event_name, **values)
            if event_name == 'phase':
                self.cancellation.cancel()
        with self.assertRaises(engine.BatchError) as failure:
            self.run_batch(progress)
        self.assertTrue(failure.exception.cancelled)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])
        self.assertNotIn('complete', [name for name, _ in self.events])

    def test_cancel_during_staging_allocation_cleans_owned_directory(self):
        allocate = engine.tempfile.mkdtemp
        def create(**kwargs):
            path = allocate(**kwargs)
            self.cancellation.cancel()
            return path
        with patch.object(engine.tempfile, 'mkdtemp', side_effect=create):
            with self.assertRaises(engine.BatchError) as failure:
                self.run_batch()
        self.assertTrue(failure.exception.cancelled)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_pending_cancel_is_checked_at_publication_entry(self):
        def progress(event_name, **values):
            if event_name == 'phase':
                self.cancellation.requested = True
        with self.assertRaises(engine.BatchError) as failure:
            self.run_batch(progress)
        self.assertTrue(failure.exception.cancelled)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_signal_after_atomic_rename_still_completes_and_stays_deferred(self):
        rename = os.rename
        def publish(source, destination):
            rename(source, destination)
            self.cancellation.cancel()
        with patch.object(engine.sys, 'platform', 'publication-test'), patch.object(engine.os, 'rename', side_effect=publish):
            result = self.run_batch()
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(self.events[-1], ('complete', result))
        self.cancellation.cancel()  # Also deferred after run returns to main.
        self.assertTrue(self.cancellation.requested)

    def test_signal_during_complete_callback_does_not_replace_success(self):
        def progress(event_name, **values):
            self.progress(event_name, **values)
            if event_name == 'complete':
                self.cancellation.cancel()
        self.run_batch(progress)
        self.assertEqual(self.events[-1][0], 'complete')
        self.assertTrue(self.destination.is_dir())

    def test_rename_failure_removes_staging_and_keeps_original_error(self):
        with patch.object(engine.sys, 'platform', 'publication-test'), patch.object(engine.os, 'rename', side_effect=OSError('synthetic publication failure')):
            with self.assertRaisesRegex(OSError, 'synthetic publication failure'):
                self.run_batch()
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_cleanup_failure_preserves_processing_message_and_staging(self):
        self.stack.enter_context(patch.object(engine, 'self_audit', side_effect=engine.BatchError('Synthetic audit failure')))
        with patch.object(engine.shutil, 'rmtree', side_effect=PermissionError('synthetic cleanup failure')):
            with self.assertRaises(engine.BatchError) as failure:
                self.run_batch()
        error = failure.exception
        self.assertIn('Synthetic audit failure', str(error))
        self.assertTrue(error.cleanup_failed)
        self.assertFalse(error.cancelled)
        self.assertTrue(Path(error.staging_path).is_dir())
        self.assertEqual(Path(error.staging_path).parent, self.root)
        self.assertIsInstance(error.__cause__, engine.BatchError)

    def test_cancel_cleanup_failure_is_distinguished_from_clean_cancellation(self):
        def progress(event_name, **values):
            if event_name == 'phase':
                self.cancellation.cancel()
        with patch.object(engine.shutil, 'rmtree', side_effect=OSError('synthetic cleanup failure')):
            with self.assertRaises(engine.BatchError) as failure:
                self.run_batch(progress)
        self.assertTrue(failure.exception.cancelled)
        self.assertTrue(failure.exception.cleanup_failed)
        self.assertTrue(Path(failure.exception.staging_path).is_dir())

    def test_second_cancel_during_cleanup_does_not_interrupt_removal(self):
        remove = engine.shutil.rmtree
        def cleanup(path):
            self.cancellation.cancel()
            remove(path)
        self.stack.enter_context(patch.object(engine, 'self_audit', side_effect=engine.BatchError('Original failure')))
        with patch.object(engine.shutil, 'rmtree', side_effect=cleanup):
            with self.assertRaisesRegex(engine.BatchError, '^Original failure$'):
                self.run_batch()
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_cleanup_refuses_replacement_directory(self):
        staging = self.root / '.dicom-batch-owned'
        staging.mkdir()
        before = staging.lstat()
        original = self.root / 'original'
        staging.rename(original)
        staging.mkdir()
        marker = staging / 'unrelated'
        marker.write_text('preserve')
        with self.assertRaises(OSError):
            engine.remove_staging(staging, (before.st_dev, before.st_ino))
        self.assertEqual(marker.read_text(), 'preserve')
        self.assertTrue(original.is_dir())

    def test_main_emits_structured_cleanup_failure_without_path_in_message(self):
        error = engine.BatchError('Cancelled; incomplete output remains.', cancelled=True, cleanup_failed=True, staging_path=str(self.root / '.dicom-batch-owned'))
        with patch.object(sys, 'argv', ['engine', '--source', str(self.source), '--destination', str(self.destination)]), patch.object(engine.signal, 'signal'), patch.object(engine, 'run', side_effect=error), patch.object(engine, 'emit') as emit:
            self.assertEqual(engine.main(), 1)
        emit.assert_called_once_with('error', message=str(error), cancelled=True, cleanup_failed=True, staging_path=error.staging_path)
        self.assertNotIn(str(self.root), str(error))

    def test_main_late_signal_returns_zero_after_complete(self):
        def run(source, destination, *, cancellation):
            cancellation.begin_publication()
            cancellation.cancel()
            return {}
        with patch.object(sys, 'argv', ['engine', '--source', str(self.source), '--destination', str(self.destination)]), patch.object(engine.signal, 'signal'), patch.object(engine, 'run', side_effect=run), patch.object(engine, 'emit') as emit:
            self.assertEqual(engine.main(), 0)
        emit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
