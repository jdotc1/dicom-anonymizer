"""New writer-to-batch uncertainty cases on tiny synthetic output."""
import errno
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_engine as fixtures

sys.path.insert(0, str(fixtures.ENGINE.parent))
import operation_journal

engine = fixtures.engine


class JournalBatchProtectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'input'
        fixtures.make_dicom(self.source / '00043' / 'source.dcm')
        self.output = self.root / 'output'
        self.journal = self.root / 'recovery' / 'operation.json'
        self.events = []

    def batch(self):
        return engine.run(self.source, self.output, journal=self.journal,
                          progress=lambda event, **values: self.events.append((event, values)))

    def replace_during_phase(self, phase):
        original_dump = operation_journal.json.dump

        def dump(record, stream, **kwargs):
            original_dump(record, stream, **kwargs)
            if record['phase'] == phase:
                replacement = self.journal.with_name('replacement.json')
                replacement.write_bytes(b'FOREIGN_RECOVERY_RECORD')
                os.replace(replacement, self.journal)

        return patch.object(operation_journal.json, 'dump', dump)

    def assert_no_success_or_temporaries(self):
        self.assertNotIn('complete', [event for event, _ in self.events])
        self.assertEqual(list(self.journal.parent.glob('.operation-*')), [])
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_replaced_prepublish_record_survives_batch_cleanup(self):
        with self.replace_during_phase('publishing'):
            with self.assertRaises(engine.BatchError) as caught:
                self.batch()
        self.assertFalse(caught.exception.output_published)
        self.assertFalse(caught.exception.cleanup_failed)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.journal.read_bytes(), b'FOREIGN_RECOVERY_RECORD')
        self.assertNotIn(str(self.source), str(caught.exception))
        self.assert_no_success_or_temporaries()

    def test_replaced_postpublish_record_preserves_output_and_uncertainty(self):
        with self.replace_during_phase('published'):
            with self.assertRaises(engine.BatchError) as caught:
                self.batch()
        self.assertTrue(caught.exception.output_published)
        self.assertTrue(self.output.is_dir())
        self.assertEqual(len(list(self.output.rglob('*.dcm'))), 1)
        report = json.loads((self.output / 'anonymization-report.json').read_text())
        self.assertEqual(report['self_audit']['files_audited'], 1)
        self.assertEqual(self.journal.read_bytes(), b'FOREIGN_RECOVERY_RECORD')
        self.assert_no_success_or_temporaries()

    def test_uncertain_directory_sync_cannot_be_rewritten_as_cleaned(self):
        original_sync = operation_journal.os.fsync

        def sync(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                record = json.loads(self.journal.read_text())
                if record['phase'] == 'publishing':
                    raise OSError(errno.EIO, 'SYNTHETIC_PRIVATE_LOCATION')
            original_sync(descriptor)

        with patch.object(operation_journal.os, 'fsync', sync):
            with self.assertRaises(engine.BatchError) as caught:
                self.batch()
        self.assertFalse(caught.exception.output_published)
        self.assertFalse(self.output.exists())
        record = json.loads(self.journal.read_text())
        self.assertEqual(record['phase'], 'publishing')
        self.assertNotIn('SYNTHETIC_PRIVATE_LOCATION', str(caught.exception))
        self.assert_no_success_or_temporaries()

    def test_valid_journaled_default_batch_completes_without_publishing_record(self):
        result = self.batch()
        record = json.loads(self.journal.read_text())
        self.assertEqual(record['phase'], 'published')
        info = self.output.lstat()
        self.assertEqual((record['device'], record['inode']), (info.st_dev, info.st_ino))
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['audited_files'], 1)
        self.assertEqual(self.events[-1][0], 'complete')
        report = (self.output / 'anonymization-report.json').read_text()
        self.assertNotIn(str(self.journal), report)
        self.assertNotIn(record['operation_id'], report)
        self.assertFalse((self.output / 'operation.json').exists())
        self.assertEqual(list(self.journal.parent.glob('.operation-*')), [])
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])


if __name__ == '__main__':
    unittest.main()
