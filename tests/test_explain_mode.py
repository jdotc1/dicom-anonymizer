"""Value-free explain mode: synthetic MR only; sentinel values must never be printed."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'engine' / 'engine.py'
spec = importlib.util.spec_from_file_location('explain_engine', ENGINE)
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

NAME, DATE, TEXT = 'Zzsentinel^Namevalue', '19570203', 'Zzsentinel free text note'
PRIVATE, UNBYTES = 'ZZPRIVATEVALUE', b'ZZUNBYTES'
STUDY, SERIES, SOP = '2.25.1111111', '2.25.2222222', '2.25.3333333'
NESTED_UID, FRAME = '2.25.4444444', '2.25.5555555'
SENTINELS = [NAME, DATE, TEXT, PRIVATE, UNBYTES.decode(), STUDY, SERIES, SOP, NESTED_UID, FRAME, 'Zzsentinel']


def make(path, modality='MR'):
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = MRImageStorage
    meta.MediaStorageSOPInstanceUID = SOP
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b'\0' * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = MRImageStorage, SOP
    ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = STUDY, SERIES, FRAME
    ds.Modality = modality
    ds.PatientName, ds.PatientID = NAME, 'ZzsentinelID'
    ds.StudyDate = DATE
    ds.ImageComments = TEXT
    ds.add_new((0x0011, 0x0010), 'LO', 'ZZCREATOR')
    ds.add_new((0x0011, 0x1001), 'LO', PRIVATE)
    ds.add_new(0x00231010, 'UN', UNBYTES)  # public-range tag with unknown VR
    ds.SeriesDescription = 'retained text'
    ds.Rows = ds.Columns = 2
    item = Dataset()
    item.ReferencedSOPClassUID = MRImageStorage
    item.ReferencedSOPInstanceUID = NESTED_UID
    item.PatientName = NAME
    ds.ReferencedImageSequence = Sequence([item])
    ds.save_as(path)
    return path


class ExplainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.file = make(self.dir / 'mr.dcm')

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(ENGINE), *args], capture_output=True, text=True)

    def rows(self, result):
        return {r['path']: r for r in json.loads(result.stdout)['attributes']}

    def test_actions_and_no_values_and_no_writes(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.dir.iterdir()}
        result = self.cli('--explain', str(self.file))
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in (result.stdout, result.stderr):
            for sentinel in SENTINELS:
                self.assertNotIn(sentinel, text)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.dir.iterdir()})
        rows = self.rows(result)
        self.assertEqual(rows['(0010,0010)']['action'], 'pseudonym')
        self.assertEqual(rows['(0010,0020)']['action'], 'pseudonym')
        self.assertEqual(rows['(0008,0020)']['action'], 'cleared')
        self.assertEqual(rows['(0020,000D)']['action'], 'uid_remapped')
        self.assertEqual(rows['(0020,0052)']['action'], 'uid_remapped')
        self.assertEqual(rows['(0008,0018)']['action'], 'uid_remapped')
        self.assertEqual(rows['(0008,0018)']['keyword'], 'SOPInstanceUID')
        self.assertEqual(rows['(0020,000E)']['vr'], 'UI')
        self.assertEqual(rows['(0020,4000)']['action'], 'cleared')
        self.assertEqual(rows['(0011,1001)']['action'], 'removed')
        self.assertEqual(rows['(0011,0010)']['action'], 'removed')
        self.assertEqual(rows['(0011,1001)']['keyword'], '')
        self.assertEqual(rows['(0023,1010)']['action'], 'removed')
        item = '(0008,1140)[0]/'
        self.assertEqual(rows[item + '(0008,1155)']['action'], 'uid_remapped')
        self.assertEqual(rows[item + '(0010,0010)']['action'], 'pseudonym')
        self.assertNotIn(item + '(0008,1150)', rows)  # SOP class is retained
        self.assertNotIn('(0008,103E)', rows)  # SeriesDescription is retained
        counts = json.loads(result.stdout)['counts']
        self.assertGreater(counts['retained'], 0)

    def test_matches_real_run_output_once(self):
        source = self.dir / 'src' / '001'
        source.mkdir(parents=True)
        make(source / 'mr.dcm')
        output = self.dir / 'out'
        engine.run(str(self.dir / 'src'), str(output), progress=lambda *a, **k: None, audit=False)
        written = next(p for p in output.rglob('*') if p.suffix == '.dcm')
        cleaned = pydicom.dcmread(written)
        original = pydicom.dcmread(self.file)
        result = self.cli('--explain', str(self.file))
        rows = self.rows(result)
        for element in original:
            action = rows.get('(%04X,%04X)' % (element.tag.group, element.tag.element), {}).get('action', 'retained')
            if action == 'removed':
                self.assertNotIn(element.tag, cleaned)
            elif action == 'retained' and element.VR != 'SQ':
                self.assertEqual(cleaned[element.tag].value, element.value)
            elif action == 'cleared':
                self.assertEqual(cleaned[element.tag].value in ('', None), True)
            elif action == 'uid_remapped':
                self.assertNotEqual(cleaned[element.tag].value, element.value)

    def test_refusal_uses_real_run_text(self):
        us = make(self.dir / 'us.dcm', modality='US')
        result = self.cli('--explain', str(us))
        self.assertEqual(result.returncode, 1)
        event = json.loads(result.stdout)
        self.assertEqual(event['event'], 'error')
        self.assertEqual(event['message'], 'An unsupported modality was found. This version accepts MR, CT and RTSTRUCT only.')

    def test_unreadable_file_uses_fixed_text(self):
        bad = self.dir / 'bad.dcm'
        bad.write_bytes(b'not dicom ZZPRIVATEVALUE')
        result = self.cli('--explain', str(bad))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('ZZPRIVATEVALUE', result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['message'].startswith('A DICOM file could not be read'))

    def test_in_process_restores_uid_factory_and_does_not_mutate(self):
        original = engine.generate_uid
        ds = engine.checked_read(self.file)
        before = repr(ds)
        spec2 = importlib.util.spec_from_file_location('explain_mode', ROOT / 'engine' / 'explain_mode.py')
        module = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(module)
        rows, counts = module.explain_dataset(engine, ds)
        self.assertIs(engine.generate_uid, original)
        self.assertEqual(repr(ds), before)
        self.assertTrue(rows)


if __name__ == '__main__':
    unittest.main()
