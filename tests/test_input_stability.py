"""Synthetic concurrent-input recovery only; no policy or self-audit reruns."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('input_stability_engine', Path(__file__).resolve().parents[1] / 'engine/engine.py')
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


class InputStabilityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / 'input'
        self.path = self.source / '001' / 'one.dcm'
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'fixture')
        self.signature = engine.fingerprint(self.path)
        self.ds = SimpleNamespace(StudyInstanceUID='1', SeriesInstanceUID='2', SOPInstanceUID='3', get=lambda key, default='': default, iterall=lambda: iter(()))

    def assert_changed(self, action):
        with self.assertRaisesRegex(engine.BatchError, 'Keep input files unchanged and retry') as failure:
            action()
        self.assertNotIn(str(self.root), str(failure.exception))
        self.assertIsNone(failure.exception.output_issue)

    def test_unchanged_read_returns_same_dataset(self):
        with patch.object(engine, 'checked_read', return_value=self.ds) as read:
            self.assertIs(engine.stable_read(self.path, self.signature), self.ds)
        read.assert_called_once_with(self.path)

    def test_changed_before_read_does_not_read(self):
        self.path.write_bytes(b'changed length')
        with patch.object(engine, 'checked_read') as read:
            self.assert_changed(lambda: engine.stable_read(self.path, self.signature))
        read.assert_not_called()

    def test_changes_during_read_are_rejected(self):
        for kind in ('edit', 'replace', 'remove', 'symlink'):
            with self.subTest(kind=kind):
                if self.path.is_symlink() or self.path.exists():
                    self.path.unlink()
                self.path.write_bytes(b'fixture')
                signature = engine.fingerprint(self.path)
                def read(_):
                    if kind == 'edit':
                        self.path.write_bytes(b'new content length')
                    elif kind == 'replace':
                        replacement = self.root / 'replacement'
                        replacement.write_bytes(b'fixture')
                        os.replace(replacement, self.path)
                    else:
                        self.path.unlink()
                        if kind == 'symlink':
                            self.path.symlink_to(self.root / 'missing')
                    return self.ds
                with patch.object(engine, 'checked_read', side_effect=read):
                    self.assert_changed(lambda: engine.stable_read(self.path, signature))

    def test_failed_read_after_removal_reports_input_change(self):
        def read(_):
            self.path.unlink()
            raise engine.BatchError('malformed')
        with patch.object(engine, 'checked_read', side_effect=read):
            self.assert_changed(lambda: engine.stable_read(self.path, self.signature))

    def test_stable_read_failure_is_preserved(self):
        failure = engine.BatchError('existing read error')
        with patch.object(engine, 'checked_read', side_effect=failure):
            with self.assertRaises(engine.BatchError) as caught:
                engine.stable_read(self.path, self.signature)
        self.assertIs(caught.exception, failure)

    def test_cancellation_is_preserved_even_if_input_changes(self):
        failure = engine.BatchError('cancelled', cancelled=True)
        def read(_):
            self.path.unlink()
            raise failure
        with patch.object(engine, 'checked_read', side_effect=read):
            with self.assertRaises(engine.BatchError) as caught:
                engine.stable_read(self.path, self.signature)
        self.assertIs(caught.exception, failure)

    def test_scan_records_pre_read_identity(self):
        with patch.object(engine, 'checked_read', return_value=self.ds), patch.object(engine, 'validate'), patch.object(engine, 'claim_patient_frames'):
            records, _, _ = engine.scan(self.source)
        self.assertEqual(records[0].signature, self.signature)

    def test_scan_rejects_change_before_validation_or_acceptance(self):
        def read(_):
            self.path.write_bytes(b'changed length')
            return self.ds
        with patch.object(engine, 'checked_read', side_effect=read), patch.object(engine, 'validate') as validate:
            self.assert_changed(lambda: engine.scan(self.source))
        validate.assert_not_called()

    def test_processing_rejects_change_and_cleans_owned_staging(self):
        record = engine.Record(self.path, '001', ('1', '2'), '3', '', self.signature)
        destination = self.root / 'output'
        events = []
        def read(_):
            self.path.write_bytes(b'changed length')
            return self.ds
        with patch.object(engine, 'scan', return_value=([record], [{'id': '001', 'files': 1, 'series': 1}], 0)), patch.object(engine, 'check_disk_space'), patch.object(engine, 'checked_read', side_effect=read), patch.object(engine, 'validate') as validate, patch.object(engine, 'clean') as clean, patch.object(engine, 'self_audit') as audit:
            self.assert_changed(lambda: engine.run(self.source, destination, lambda event, **values: events.append(event)))
        validate.assert_not_called()
        clean.assert_not_called()
        audit.assert_not_called()
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])
        self.assertNotIn('complete', events)


if __name__ == '__main__':
    unittest.main()
