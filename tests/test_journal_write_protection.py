"""Small record-update fixtures; no application launch or accepted suite reruns."""
import errno
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import operation_journal as journal_module
from operation_journal import JournalError, OperationJournal


class JournalWriteProtectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'recovery' / 'operation.json'
        self.writer = OperationJournal(self.path, self.root / 'output')
        self.before = self.path.read_bytes()
        self.before_record = dict(self.writer.record)

    def replacement(self):
        other = self.path.with_name('replacement.json')
        other.write_bytes(b'foreign replacement record')
        os.replace(other, self.path)

    def assert_no_temporaries(self):
        self.assertEqual(list(self.path.parent.glob('.operation-*')), [])

    def test_replacement_during_serialization_is_preserved(self):
        dump = journal_module.json.dump
        def change(*args, **kwargs):
            dump(*args, **kwargs)
            self.replacement()
        with patch.object(journal_module.json, 'dump', side_effect=change):
            with self.assertRaises(JournalError):
                self.writer.mark('allocated')
        self.assertEqual(self.path.read_bytes(), b'foreign replacement record')
        self.assertEqual(self.writer.record, self.before_record)
        self.assert_no_temporaries()

    def test_in_place_edit_during_serialization_is_preserved(self):
        dump = journal_module.json.dump
        def change(*args, **kwargs):
            dump(*args, **kwargs)
            self.path.write_bytes(b'foreign in-place edit')
        with patch.object(journal_module.json, 'dump', side_effect=change):
            with self.assertRaises(JournalError):
                self.writer.mark('publishing')
        self.assertEqual(self.path.read_bytes(), b'foreign in-place edit')
        self.assertEqual(self.writer.record, self.before_record)
        self.assert_no_temporaries()

    def test_replacement_during_temporary_sync_is_preserved(self):
        sync = journal_module.os.fsync
        def change(descriptor):
            sync(descriptor)
            self.replacement()
        with patch.object(journal_module.os, 'fsync', side_effect=change):
            with self.assertRaises(JournalError):
                self.writer.mark('publishing')
        self.assertEqual(self.path.read_bytes(), b'foreign replacement record')
        self.assert_no_temporaries()

    def test_substitution_after_replace_is_not_adopted(self):
        replace = journal_module.os.replace
        def change(source, destination):
            replace(source, destination)
            other = self.path.with_name('foreign.json')
            other.write_bytes(b'foreign after replace')
            replace(other, self.path)
        with patch.object(journal_module.os, 'replace', side_effect=change):
            with self.assertRaises(JournalError):
                self.writer.mark('publishing')
        self.assertEqual(self.path.read_bytes(), b'foreign after replace')
        with self.assertRaises(JournalError):
            self.writer.mark('cleaned')
        self.assertEqual(self.path.read_bytes(), b'foreign after replace')

    def test_serialization_failure_preserves_record_and_memory(self):
        with patch.object(journal_module.json, 'dump', side_effect=OSError(errno.ENOSPC, 'synthetic write failure')):
            with self.assertRaises(OSError):
                self.writer.mark('allocated', staging=self.root / 'staging', identity=(1, 2))
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(self.writer.record, self.before_record)
        self.assert_no_temporaries()

    def test_replace_failure_preserves_record_and_memory(self):
        with patch.object(journal_module.os, 'replace', side_effect=OSError(errno.EACCES, 'synthetic replace failure')):
            with self.assertRaises(OSError):
                self.writer.mark('allocated')
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(self.writer.record, self.before_record)
        self.assert_no_temporaries()

    def test_directory_sync_failure_keeps_uncertainty_and_blocks_later_overwrite(self):
        sync = journal_module.os.fsync
        calls = 0
        def fail_directory(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError(errno.EIO, 'synthetic directory sync failure')
            sync(descriptor)
        with patch.object(journal_module.os, 'fsync', side_effect=fail_directory):
            with self.assertRaises(OSError):
                self.writer.mark('publishing')
        self.assertEqual(json.loads(self.path.read_text())['phase'], 'publishing')
        self.assertEqual(self.writer.record, self.before_record)
        with self.assertRaises(JournalError):
            self.writer.mark('cleaned')
        self.assertEqual(json.loads(self.path.read_text())['phase'], 'publishing')
        self.assert_no_temporaries()

    def test_successful_updates_keep_identity_and_phase_consistent(self):
        self.writer.mark('allocated', staging=self.root / 'staging', identity=(12, 34))
        self.writer.mark('publishing')
        record = json.loads(self.path.read_text())
        self.assertEqual(record['phase'], 'publishing')
        self.assertEqual((record['device'], record['inode']), (12, 34))
        self.assertEqual(self.writer.record, record)
        info = self.path.lstat()
        self.assertEqual(self.writer.identity, (info.st_dev, info.st_ino))
        self.assertEqual(info.st_mode & 0o777, 0o600)
        self.assert_no_temporaries()

    def test_parent_replacement_preserves_both_records_and_cleans_owned_temporary(self):
        dump = journal_module.json.dump
        moved = self.root / 'original-recovery'
        def change(*args, **kwargs):
            dump(*args, **kwargs)
            self.path.parent.rename(moved)
            self.path.parent.mkdir()
            self.path.write_bytes(b'foreign parent record')
        with patch.object(journal_module.json, 'dump', side_effect=change):
            with self.assertRaises(JournalError):
                self.writer.mark('publishing')
        self.assertEqual(self.path.read_bytes(), b'foreign parent record')
        self.assertEqual((moved / 'operation.json').read_bytes(), self.before)
        self.assertEqual(list(moved.glob('.operation-*')), [])
        self.assertEqual(self.writer.record, self.before_record)

    def test_foreign_temporary_entry_is_not_published_or_removed(self):
        dump = journal_module.json.dump
        foreign = []
        def change(*args, **kwargs):
            dump(*args, **kwargs)
            [temporary] = list(self.path.parent.glob('.operation-*'))
            temporary.unlink()
            temporary.write_bytes(b'foreign temporary entry')
            foreign.append(temporary)
        with patch.object(journal_module.json, 'dump', side_effect=change):
            with self.assertRaises(JournalError):
                self.writer.mark('publishing')
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(foreign[0].read_bytes(), b'foreign temporary entry')

    def test_symlink_replacement_preserves_link_and_target(self):
        dump = journal_module.json.dump
        target = self.root / 'foreign-target'
        target.write_bytes(b'foreign target')
        def change(*args, **kwargs):
            dump(*args, **kwargs)
            self.path.unlink()
            self.path.symlink_to(target)
        with patch.object(journal_module.json, 'dump', side_effect=change):
            with self.assertRaises(JournalError):
                self.writer.mark('publishing')
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(target.read_bytes(), b'foreign target')
        self.assert_no_temporaries()

    def test_replacement_during_directory_sync_is_not_adopted(self):
        sync = journal_module.os.fsync
        calls = 0
        def change(descriptor):
            nonlocal calls
            calls += 1
            sync(descriptor)
            if calls == 2:
                self.replacement()
        with patch.object(journal_module.os, 'fsync', side_effect=change):
            with self.assertRaises(JournalError):
                self.writer.mark('publishing')
        self.assertEqual(self.path.read_bytes(), b'foreign replacement record')
        self.assertEqual(self.writer.record, self.before_record)
        with self.assertRaises(JournalError):
            self.writer.mark('cleaned')


if __name__ == '__main__':
    unittest.main()
