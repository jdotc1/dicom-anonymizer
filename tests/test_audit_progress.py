"""Progress event contract only; DICOM reads and policy checks are mocked."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ENGINE = Path(__file__).resolve().parents[1] / 'engine' / 'engine.py'
spec = importlib.util.spec_from_file_location('engine_audit_progress', ENGINE)
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


class AuditProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def written(self, count):
        return [(self.root / f'{index:04d}.dcm', '00001') for index in range(count)]

    def test_counts_follow_successful_checks_and_include_final_partial_group(self):
        events = []
        checked = []

        def progress(event, **values):
            self.assertEqual(event, 'audit_progress')
            self.assertEqual(values['audited_files'], len(checked))
            self.assertEqual(values['total_files'], 25)
            events.append(values['audited_files'])

        with patch.object(engine, 'checked_read', return_value=object()), \
             patch.object(engine, 'validate'), \
             patch.object(engine, 'audit_file_header'), \
             patch.object(engine, 'audit_dataset', side_effect=lambda *args: checked.append(True)):
            result = engine.self_audit(self.root, self.written(25), set(), progress=progress)
        self.assertEqual(events, [0, 10, 20, 25])
        self.assertEqual(result['files_audited'], 25)
        self.assertEqual(result['result'], 'passed')

    def test_failed_file_is_never_reported_as_checked(self):
        events = []
        checked = 0

        def audit(*_args):
            nonlocal checked
            if checked == 10:
                raise engine.BatchError('Synthetic audit failure')
            checked += 1

        with patch.object(engine, 'checked_read', return_value=object()), \
             patch.object(engine, 'validate'), \
             patch.object(engine, 'audit_file_header'), \
             patch.object(engine, 'audit_dataset', side_effect=audit):
            with self.assertRaisesRegex(engine.BatchError, 'Synthetic audit failure'):
                engine.self_audit(self.root, self.written(11), set(),
                                  progress=lambda name, **values: events.append(values['audited_files']))
        self.assertEqual(events, [0, 10])
        self.assertEqual(checked, 10)

    def test_three_argument_call_remains_silent(self):
        with patch.object(engine, 'checked_read', return_value=object()), \
             patch.object(engine, 'validate'), patch.object(engine, 'audit_dataset'), \
             patch.object(engine, 'audit_file_header'), \
             patch.object(engine, 'emit') as emit:
            result = engine.self_audit(self.root, self.written(1), set())
        emit.assert_not_called()
        self.assertEqual(result['files_audited'], 1)

    def run_mocked_batch(self, *, audit_fails=False):
        # Empty mocked scan avoids all file processing. This exercises only run's
        # callback plumbing and the ordering of phase/report/publication events.
        source = self.root / 'input'
        source.mkdir()
        destination = self.root / 'output'
        events = []

        def progress(event, **values):
            events.append((event, values))
            if event == 'phase':
                self.assertEqual(values, {'name': 'finalizing'})
                self.assertFalse(destination.exists())
                self.assertEqual(list(self.root.glob('.dicom-batch-*/anonymization-report.json')), [])
            elif event == 'complete':
                report = json.loads((destination / 'anonymization-report.json').read_text())
                self.assertEqual(report['self_audit'], {'result': 'passed', 'files_audited': 0})

        def audit(staging, written, forbidden_uids, *, progress):
            self.assertTrue(staging.is_dir())
            self.assertEqual(written, [])
            progress('audit_progress', audited_files=0, total_files=0)
            if audit_fails:
                raise engine.BatchError('Synthetic audit failure')
            return {'result': 'passed', 'files_audited': 0}

        with patch.object(engine, 'scan', return_value=([], [], 0)), \
             patch.object(engine, 'check_disk_space'), \
             patch.object(engine, 'self_audit', side_effect=audit):
            if audit_fails:
                with self.assertRaisesRegex(engine.BatchError, 'Synthetic audit failure'):
                    engine.run(source, destination, progress=progress)
            else:
                engine.run(source, destination, progress=progress)
        return events, destination

    def test_run_forwards_audit_progress_then_finalizes_before_publication(self):
        events, destination = self.run_mocked_batch()
        self.assertEqual([name for name, _ in events], ['scan', 'audit_progress', 'phase', 'complete'])
        self.assertTrue(destination.is_dir())

    def test_run_never_emits_finalizing_or_complete_after_audit_failure(self):
        events, destination = self.run_mocked_batch(audit_fails=True)
        self.assertEqual([name for name, _ in events], ['scan', 'audit_progress'])
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])


if __name__ == '__main__':
    unittest.main()
