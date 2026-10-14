import importlib.util
import json
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import unittest
from unittest.mock import patch
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset, Dataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, RTStructureSetStorage, generate_uid

ENGINE = Path(__file__).resolve().parents[1] / 'engine' / 'engine.py'
spec = importlib.util.spec_from_file_location('bulk_engine', ENGINE)
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


def make_dicom(path, identity='synthetic-source-id', study=None, series=None, sop=None, ref=None, frame=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = MRImageStorage if ref is None else RTStructureSetStorage
    meta.MediaStorageSOPInstanceUID = sop or generate_uid()
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b'private' + b'\0' * 121)
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = study or generate_uid()
    ds.SeriesInstanceUID = series or generate_uid()
    # Synthetic patients have distinct spatial frames; files within a patient share one.
    patient_root = next((parent for parent in reversed(path.parents) if parent.name.isdecimal()), path.parent)
    ds.FrameOfReferenceUID = frame or ('2.25.' + str(uuid.uuid5(uuid.NAMESPACE_URL, str(patient_root)).int))
    ds.Modality = 'MR' if ref is None else 'RTSTRUCT'
    ds.PatientName = 'Private^Person'
    ds.PatientID = identity
    ds.PatientBirthDate = '19600101'
    ds.SeriesDescription = 'DWI axial b1000'
    ds.ProtocolName = 'Prostate diffusion'
    ds.SequenceName = '*ep_b1000'
    ds.StudyDescription = 'Private study name'
    ds.add_new((0x0011, 0x0010), 'LO', 'PRIVATE')
    nested = Dataset()
    nested.PatientName = 'Nested^Identity'
    nested.PatientID = identity
    nested.PatientBirthDate = '19600101'
    ds.ReferencedPatientSequence = Sequence([nested])
    if ref:
        nested = Dataset()
        nested.ReferencedSOPClassUID = MRImageStorage
        nested.ReferencedSOPInstanceUID = ref
        ds.ReferencedImageSequence = Sequence([nested])
        roi = Dataset(); roi.ROINumber = 1; roi.ROIName = 'Prostate'; roi.ReferencedFrameOfReferenceUID = ds.FrameOfReferenceUID
        ds.StructureSetROISequence = Sequence([roi])
    else:
        ds.Rows = 2; ds.Columns = 2; ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = 'MONOCHROME2'
        ds.BitsAllocated = 16; ds.BitsStored = 16; ds.HighBit = 15; ds.PixelRepresentation = 0
        ds.PixelData = b'\1\0\2\0\3\0\4\0'
    ds.save_as(path, enforce_file_format=True)
    return ds

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input'; self.source.mkdir()
        self.output = self.root / 'output'
    def tearDown(self):
        self.tmp.cleanup()
    def run_batch(self):
        return engine.run(self.source, self.output, progress=lambda *a, **k: None)
    def assert_no_output(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])
    def test_bulk_identity_uid_references_and_pixels(self):
        study, series = generate_uid(), generate_uid()
        first = make_dicom(self.source / '00001' / 'private-a' / 'same.dcm', study=study, series=series)
        make_dicom(self.source / '00001' / 'private-b' / 'same.dcm', study=study, series=series)
        make_dicom(self.source / '00001' / 'rt.dcm', study=study, ref=first.SOPInstanceUID)
        make_dicom(self.source / '00002' / 'same.dcm', identity='second-person')
        (self.source / '00001' / 'sidecar').write_text('private text')
        before = {p: p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        result = self.run_batch()
        self.assertEqual(result['processed'], 4)
        self.assertEqual(result['excluded_files'], 1)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        output = [pydicom.dcmread(p) for p in sorted((self.output / '00001').rglob('*.dcm'))]
        self.assertEqual(len(output), 3)
        self.assertEqual(len(list((self.output / '00001').iterdir())), 2)
        images = [ds for ds in output if ds.Modality == 'MR']
        rt = next(ds for ds in output if ds.Modality == 'RTSTRUCT')
        self.assertIn(rt.ReferencedImageSequence[0].ReferencedSOPInstanceUID, {ds.SOPInstanceUID for ds in images})
        self.assertEqual(rt.ReferencedImageSequence[0].ReferencedSOPClassUID, MRImageStorage)
        self.assertEqual(rt.StructureSetROISequence[0].ReferencedFrameOfReferenceUID, images[0].FrameOfReferenceUID)
        self.assertEqual(rt.StructureSetROISequence[0].ROIName, 'Prostate')
        for ds in output:
            self.assertEqual(str(ds.PatientName), '00001'); self.assertEqual(ds.PatientID, '00001')
            self.assertEqual(ds.PatientBirthDate, '')
            self.assertEqual(ds.SeriesDescription, first.SeriesDescription)
            self.assertEqual(ds.ProtocolName, first.ProtocolName)
            self.assertEqual(ds.SequenceName, first.SequenceName)
            self.assertEqual(ds.StudyDescription, '')
            self.assertEqual(ds.file_meta.MediaStorageSOPInstanceUID, ds.SOPInstanceUID)
            self.assertNotEqual(ds.StudyInstanceUID, first.StudyInstanceUID)
            self.assertEqual(ds.preamble, b'\0' * 128)
            self.assertFalse(any(e.tag.is_private for e in ds.iterall()))
            self.assertEqual(ds.ReferencedPatientSequence[0].PatientID, '00001')
            self.assertEqual(ds.ReferencedPatientSequence[0].PatientBirthDate, '')
        for ds in images:
            self.assertEqual(ds.PixelData, first.PixelData)
        report = (self.output / 'anonymization-report.json').read_text()
        self.assertNotIn('synthetic-source-id', report)
        self.assertNotIn('Private', report)
        self.assertEqual(json.loads(report)['total_files'], 4)
    def test_sequence_labels_preserved_recursively_without_creating_missing_fields(self):
        ds = Dataset()
        ds.SeriesDescription = 'DWI / RSI: b0, b1000'
        ds.ProtocolName = 'Prostate diffusion'
        ds.SequenceName = '*ep_b1000'
        nested = Dataset()
        nested.SeriesDescription = 'ADC map'
        nested.ProtocolName = 'Diffusion-derived'
        nested.SequenceName = 'ADC'
        nested.PatientName = 'Private^Person'
        nested.StudyDescription = 'Private study name'
        ds.ReferencedSeriesSequence = Sequence([nested])
        expected = [(item.SeriesDescription, item.ProtocolName, item.SequenceName) for item in (ds, nested)]
        engine.clean(ds, '00001', {})
        self.assertEqual([(item.SeriesDescription, item.ProtocolName, item.SequenceName) for item in (ds, nested)], expected)
        self.assertEqual(str(nested.PatientName), '00001')
        self.assertEqual(nested.StudyDescription, '')
        empty = Dataset()
        engine.clean(empty, '00001', {})
        self.assertNotIn('SeriesDescription', empty)
        self.assertNotIn('ProtocolName', empty)
        self.assertNotIn('SequenceName', empty)

    def test_structural_uids_and_nested_name_only(self):
        ds = Dataset()
        ds.SOPClassesInStudy = [MRImageStorage, RTStructureSetStorage]
        ds.CodingSchemeUID = '1.2.3.9'
        ds.MappingResourceUID = '1.2.3.8'
        nested = Dataset(); nested.PatientName = 'Private^OnlyName'
        ds.ReferencedPatientSequence = Sequence([nested])
        engine.clean(ds, '00001', {})
        self.assertEqual(ds.CodingSchemeUID, '1.2.3.9')
        self.assertEqual(ds.MappingResourceUID, '1.2.3.8')
        self.assertEqual(list(ds.SOPClassesInStudy), [MRImageStorage, RTStructureSetStorage])
        self.assertEqual(str(nested.PatientName), '00001')
    def test_extensionless_without_preamble(self):
        p = self.source / '1' / 'extensionless'
        make_dicom(p)
        p.write_bytes(p.read_bytes()[132:])
        self.assertEqual(self.run_batch()['processed'], 1)
    def test_changed_source_and_output_race_cleanup(self):
        p = self.source / '1' / 'a.dcm'; make_dicom(p)
        def mutate(event, **kw):
            if event == 'scan':
                p.write_bytes(p.read_bytes() + b'changed')
        with self.assertRaisesRegex(engine.BatchError, 'changed'):
            engine.run(self.source, self.output, progress=mutate)
        self.assert_no_output()
        make_dicom(p)
        def occupy(event, **kw):
            if event == 'progress':
                self.output.mkdir()
                (self.output / 'keep').write_text('existing')
        with self.assertRaisesRegex(engine.BatchError, 'appeared'):
            engine.run(self.source, self.output, progress=occupy)
        self.assertEqual((self.output / 'keep').read_text(), 'existing')
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])
    def test_mixed_and_duplicate_patient_identity(self):
        make_dicom(self.source / '1' / 'a.dcm')
        make_dicom(self.source / '1' / 'b.dcm', identity='different')
        with self.assertRaisesRegex(engine.BatchError, 'conflicting'):
            self.run_batch()
        (self.source / '1' / 'b.dcm').unlink()
        make_dicom(self.source / '2' / 'b.dcm')
        with self.assertRaisesRegex(engine.BatchError, 'multiple patient'):
            self.run_batch()
        self.assert_no_output()
    def test_folder_identifier_length(self):
        make_dicom(self.source / ('1' * 65) / 'a.dcm')
        with self.assertRaisesRegex(engine.BatchError, 'exceeds 64'):
            self.run_batch()
        self.assert_no_output()
        (self.source / ('1' * 65)).rename(self.source / ('1' * 64))
        self.assertEqual(self.run_batch()['processed'], 1)
    def test_conflicting_names_with_shared_or_missing_ids(self):
        for identity in ('shared-id', ''):
            make_dicom(self.source / '1' / 'a.dcm', identity=identity)
            p = self.source / '1' / 'b.dcm'
            ds = make_dicom(p, identity=identity)
            ds.PatientName = 'Different^PrivateName'
            ds.save_as(p, enforce_file_format=True)
            with self.assertRaisesRegex(engine.BatchError, 'conflicting'):
                self.run_batch()
            self.assert_no_output()
    def test_links_and_ambiguous_root(self):
        make_dicom(self.source / '1' / 'a.dcm')
        (self.source / '1' / 'linked').symlink_to(self.source / '1' / 'a.dcm')
        with self.assertRaisesRegex(engine.BatchError, 'Symbolic'):
            self.run_batch()
        (self.source / '1' / 'linked').unlink()
        (self.source / 'notes').mkdir()
        with self.assertRaisesRegex(engine.BatchError, 'numeric patient'):
            self.run_batch()
        self.assert_no_output()
    def test_malformed_and_missing_uids(self):
        (self.source / '1').mkdir()
        p = self.source / '1' / 'bad.dcm'; p.write_bytes(b'bad')
        with self.assertRaisesRegex(engine.BatchError, 'could not be read'):
            self.run_batch()
        ds = make_dicom(p); del ds.SeriesInstanceUID; ds.save_as(p, enforce_file_format=True)
        with self.assertRaisesRegex(engine.BatchError, 'required'):
            self.run_batch()
        self.assert_no_output()
    def test_repeat_and_overlap(self):
        make_dicom(self.source / '1' / 'a.dcm')
        with self.assertRaisesRegex(engine.BatchError, 'separate'):
            engine.run(self.source, self.source / 'out')
        self.run_batch()
        with self.assertRaisesRegex(engine.BatchError, 'already exists'):
            self.run_batch()
    def test_write_failure_and_cancellation_cleanup(self):
        make_dicom(self.source / '1' / 'a.dcm')
        with patch.object(pydicom.dataset.Dataset, 'save_as', side_effect=OSError('private path')):
            with self.assertRaises(OSError):
                self.run_batch()
        self.assert_no_output()
        def cancelled(event, **k):
            if event == 'progress':
                raise engine.BatchError('cancelled')
        with self.assertRaises(engine.BatchError):
            engine.run(self.source, self.output, progress=cancelled)
        self.assert_no_output()
    def test_cli_sigterm_cleans_staging(self):
        study, series = generate_uid(), generate_uid()
        for i in range(120):
            make_dicom(self.source / '1' / f'{i:04d}.dcm', study=study, series=series)
        proc = subprocess.Popen([sys.executable, str(ENGINE), '--source', str(self.source), '--destination', str(self.output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(json.loads(proc.stdout.readline())['event'], 'scan')
            self.assertEqual(json.loads(proc.stdout.readline())['event'], 'progress')
            proc.send_signal(signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 1)
            self.assertIn('cancelled', stdout)
            self.assertEqual(stderr, '')
            self.assert_no_output()
        finally:
            if proc.poll() is None:
                proc.kill(); proc.wait()
    def test_cli_safe_error_and_scan(self):
        make_dicom(self.source / '1' / 'a.dcm')
        result = subprocess.run([sys.executable, str(ENGINE), '--source', str(self.source), '--scan'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['total_files'], 1)
        (self.source / '1' / 'bad-private-name.dcm').write_bytes(b'bad')
        result = subprocess.run([sys.executable, str(ENGINE), '--source', str(self.source), '--scan'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('bad-private-name', result.stdout + result.stderr)
        self.assertNotIn(str(self.source), result.stdout + result.stderr)
    def test_burned_in_and_overlay_and_unsupported(self):
        p = self.source / '1' / 'a.dcm'
        for keyword, value, message in [('BurnedInAnnotation','YES','Burned-in'), ('Modality','US','unsupported')]:
            ds = make_dicom(p); setattr(ds, keyword, value); ds.save_as(p, enforce_file_format=True)
            with self.assertRaisesRegex(engine.BatchError, message):
                self.run_batch()
        ds = make_dicom(p); ds.add_new((0x6000, 0x3000), 'OW', b'\0\0'); ds.save_as(p, enforce_file_format=True)
        with self.assertRaisesRegex(engine.BatchError, 'overlay'):
            self.run_batch()

if __name__ == '__main__':
    unittest.main()
