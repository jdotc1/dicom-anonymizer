"""Only scan telemetry plumbing; all DICOM reads and policy checks are mocked."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('engine_scan_progress', Path(__file__).resolve().parents[1] / 'engine/engine.py')
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


class ScanProgressTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'))
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / 'input'
        (self.source / '001' / 'nested').mkdir(parents=True)
        (self.source / '.DS_Store').write_bytes(b'metadata')
        (self.source / '001' / 'one.dcm').write_bytes(b'fixture')
        (self.source / '001' / 'nested' / 'two.dcm').write_bytes(b'fixture')
        self.ds = SimpleNamespace(StudyInstanceUID='1', SeriesInstanceUID='2', SOPInstanceUID='3', get=lambda key, default='': default, iterall=lambda: iter(()))
        for name, value in [('checked_read', self.ds), ('validate', None), ('claim_patient_frames', None), ('fingerprint', (0, 0, 7, 0))]:
            mocker = patch.object(engine, name, return_value=value)
            mocker.start()
            self.addCleanup(mocker.stop)
        # Public scan's identity checks stay intact; synthetic reads have unique UIDs.
        engine.checked_read.side_effect = lambda path: SimpleNamespace(
            StudyInstanceUID='1', SeriesInstanceUID='2', SOPInstanceUID=path.name,
            get=lambda key, default='': default, iterall=lambda: iter(()))
        self.events = []

    def progress(self, event, **values):
        self.events.append((event, values))

    def test_counts_entered_folders_and_all_encountered_files_without_total(self):
        with patch.object(engine.time, 'monotonic', return_value=10):
            records, patients, excluded = engine.scan(self.source, self.progress)
        self.assertEqual(self.events, [
            ('scan_progress', {'files_examined': 0, 'folders_examined': 1}),
            ('scan_progress', {'files_examined': 3, 'folders_examined': 3})])
        self.assertEqual((len(records), patients[0]['files'], excluded), (2, 2, 1))

    def test_scan_attaches_estimate_using_actual_folder_identifier(self):
        with patch.object(engine, 'estimate_output_bytes', wraps=engine.estimate_output_bytes) as estimate:
            records, _, _ = engine.scan(self.source, self.progress)
        self.assertEqual([call.args[2] for call in estimate.call_args_list], ['001', '001'])
        self.assertTrue(all(record.estimated_output_bytes == 4104 for record in records))

    def test_time_throttle_and_final_snapshot(self):
        with patch.object(engine.time, 'monotonic', side_effect=[0, .02, .04, .06, .15, .16, .17]):
            engine.scan(self.source, self.progress)
        self.assertEqual([value for _, value in self.events], [
            {'files_examined': 0, 'folders_examined': 1},
            {'files_examined': 2, 'folders_examined': 3},
            {'files_examined': 3, 'folders_examined': 3}])

    def test_legacy_scan_call_remains_silent(self):
        with patch.object(engine, 'emit') as emit:
            result = engine.scan(self.source)
        emit.assert_not_called()
        self.assertEqual(len(result[0]), 2)

    def test_empty_source_finishes_traversal_then_preserves_existing_error(self):
        empty = self.root / 'empty'
        empty.mkdir()
        with self.assertRaisesRegex(engine.BatchError, 'No numeric patient folders'):
            engine.scan(empty, self.progress)
        self.assertEqual(self.events[-1][1], {'files_examined': 0, 'folders_examined': 1})

    def test_invalid_root_does_not_claim_traversal(self):
        with self.assertRaisesRegex(engine.BatchError, 'existing local batch folder'):
            engine.scan(self.root / 'missing', self.progress)
        self.assertEqual(self.events, [])

    def test_root_symlink_is_rejected_before_file_probe(self):
        link = self.source / '000'
        link.symlink_to(self.root / 'never-read-target')
        original_is_file = Path.is_file

        def file_probe(path):
            if path == link:
                self.fail('Root symlink target must not be probed as a file')
            return original_is_file(path)

        with patch.object(Path, 'is_file', file_probe):
            with self.assertRaisesRegex(engine.BatchError, 'Symbolic links are not supported'):
                engine.scan(self.source, self.progress)
        self.assertEqual(self.events, [
            ('scan_progress', {'files_examined': 0, 'folders_examined': 1})])

    def test_cli_scan_passes_emitter_and_retains_completed_event(self):
        with patch.object(sys, 'argv', ['engine', '--source', str(self.source), '--scan']), \
             patch.object(engine.signal, 'signal'), \
             patch.object(engine, 'scan', return_value=([], [], 2)) as scan, \
             patch.object(engine, 'emit') as emit:
            self.assertEqual(engine.main(), 0)
            scan.assert_called_once_with(str(self.source), progress=emit)
            emit.assert_called_once_with('scan', patients=[], total_files=0, excluded_files=2)

    def test_processing_preflight_passes_existing_callback_before_disk_check(self):
        destination = self.root / 'output'
        with patch.object(engine, 'scan', return_value=([], [], 0)) as scan, \
             patch.object(engine, 'check_disk_space', side_effect=engine.BatchError('stop fixture')):
            with self.assertRaisesRegex(engine.BatchError, 'stop fixture'):
                engine.run(self.source, destination, progress=self.progress)
        scan.assert_called_once_with(self.source.absolute(), progress=self.progress)
        self.assertEqual(self.events, [('scan', {'patients': [], 'total_files': 0, 'excluded_files': 0})])


if __name__ == '__main__':
    unittest.main()
