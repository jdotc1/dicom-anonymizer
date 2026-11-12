"""Pins the output permission contract: root 0700, journal 0600, staging 0700."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

import test_engine as fixtures

sys.path.insert(0, str(fixtures.ENGINE.parent))
engine = fixtures.engine


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


class OutputPermissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        fixtures.make_dicom(self.root / 'input' / '00001' / 'image.dcm')
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)

    def test_staging_root_journal_and_inner_modes(self):
        staging_modes = []

        def progress(event, **values):
            if event == 'audit_progress':
                [stage] = list(self.root.glob('.dicom-batch-*'))
                staging_modes.append(mode(stage))

        output = self.root / 'output'
        journal = self.root / 'private' / 'record.json'
        engine.run(self.root / 'input', output, progress=progress, journal=journal)
        self.assertTrue(staging_modes)
        self.assertEqual(set(staging_modes), {0o700})
        self.assertEqual(mode(output), 0o700)
        self.assertEqual(mode(journal), 0o600)
        self.assertEqual(mode(journal.parent), 0o700)
        # Inner entries follow the umask (022 here); documented in DATA-HANDLING.md.
        self.assertEqual(mode(output / '00001'), 0o755)
        self.assertEqual(mode(output / '00001' / 'Series_0001'), 0o755)
        self.assertEqual(mode(output / '00001' / 'Series_0001' / 'Image_000001.dcm'), 0o644)
        self.assertEqual(mode(output / 'anonymization-report.json'), 0o644)
        self.assertFalse(list(output.rglob('record.json')))


if __name__ == '__main__':
    unittest.main()
