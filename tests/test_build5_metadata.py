"""Focused build-5 regressions. Authored 2026-10-13; not executed in that review."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from test_engine import engine, make_dicom


class Build5MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'input'
        self.path = self.source / '00001' / 'image.dcm'
        self.ds = make_dicom(self.path)
        self.output = self.root / 'output'

    def run_batch(self):
        return engine.run(self.source, self.output, progress=lambda *a, **k: None)

    def test_retention_contract_survives_nested_round_trip(self):
        expected = dict(ContrastBolusAgent='Gadobutrol', SoftwareVersions='Research 1.0',
                        Manufacturer='Example Vendor', SeriesDescription='DWI axial b1000',
                        ProtocolName='Prostate diffusion', SequenceName='*ep_b1000')
        for ds in (self.ds, self.ds.ReferencedPatientSequence[0]):
            for key, value in expected.items():
                setattr(ds, key, value)
        original_pixels = self.ds.PixelData
        self.ds.save_as(self.path, enforce_file_format=True)
        self.run_batch()
        result = pydicom.dcmread(next(self.output.rglob('*.dcm')))
        for ds in (result, result.ReferencedPatientSequence[0]):
            for key, value in expected.items():
                self.assertEqual(str(ds.get(key)), value)
            self.assertEqual(str(ds.PatientName), '00001')
            self.assertEqual(str(ds.PatientID), '00001')
        self.assertEqual(result.PixelData, original_pixels)

    def test_numeric_and_sequence_gaps_and_curve_bytes_removed(self):
        for ds in (self.ds, self.ds.ReferencedPatientSequence[0]):
            ds.add_new(0x00160072, 'DS', ['40', '30', '20'])  # GPSLatitude
            child = Dataset(); child.CodeMeaning = 'SYNTHETIC_DIAGNOSIS'
            ds.add_new(0x00081301, 'SQ', Sequence([child]))
            ds.add_new(0x50003000, 'OB', b'SYNTHETIC_CURVE')
        self.ds.save_as(self.path, enforce_file_format=True)
        self.run_batch()
        result = pydicom.dcmread(next(self.output.rglob('*.dcm')))
        for ds in (result, result.ReferencedPatientSequence[0]):
            self.assertFalse(ds[0x00160072].value)
            self.assertNotIn(0x00081301, ds)
            self.assertNotIn(0x50003000, ds)

    def test_device_class_uid_remapped_without_changing_sop_class(self):
        original = '2.25.9918273645'
        self.ds.ManufacturerDeviceClassUID = original
        sop_class = self.ds.SOPClassUID
        source = engine.source_uids(self.ds, set())
        self.assertIn(original, source)
        mapping = {}; engine.clean(self.ds, '00001', mapping)
        self.assertNotEqual(str(self.ds.ManufacturerDeviceClassUID), original)
        self.assertEqual(str(self.ds.ManufacturerDeviceClassUID), mapping[original])
        self.assertEqual(self.ds.SOPClassUID, sop_class)

    def test_staged_metadata_after_pixels_blocks_publication(self):
        original = engine.clean
        def leak(ds, patient, uid_map):
            original(ds, patient, uid_map)
            if 'PixelData' in ds:
                ds.add_new(0x7FE11010, 'LO', 'SYNTHETIC_POST_PIXEL')
        with patch.object(engine, 'clean', leak):
            with self.assertRaisesRegex(engine.BatchError, 'self-audit'):
                self.run_batch()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_audit_blocks_scalar_sequence_free_text_and_empty_un_leaks(self):
        for tag, vr, value in [(0x3010002D, 'LO', 'SYNTHETIC_DEVICE'),
                               (0x00081301, 'SQ', Sequence([Dataset()])),
                               (0x0040A160, 'UT', 'SYNTHETIC_TEXT'),
                               (0x77760001, 'UN', b'')]:
            with self.subTest(tag=tag):
                engine.clean(self.ds, '00001', {})
                self.ds.file_meta.MediaStorageSOPInstanceUID = self.ds.SOPInstanceUID
                engine.audit_dataset(self.ds, '00001', set())
                self.ds.add_new(tag, vr, value)
                with self.assertRaises(engine.BatchError):
                    engine.audit_dataset(self.ds, '00001', set())
                del self.ds[tag]

    def test_audit_cancellation_keeps_message(self):
        with patch.object(engine, 'checked_read', side_effect=engine.BatchError('Cancelled.')):
            with self.assertRaisesRegex(engine.BatchError, '^Cancelled[.]$'):
                engine.self_audit(self.source, [(self.path, '00001')], set())

    def test_cross_patient_frame_collision_blocks_before_publication(self):
        shared = '2.25.771122334455'
        self.ds.FrameOfReferenceUID = shared
        self.ds.save_as(self.path, enforce_file_format=True)
        make_dicom(self.source / '00002' / 'other.dcm', identity='other-patient', frame=shared)
        with self.assertRaisesRegex(engine.BatchError, 'same patient frame of reference'):
            self.run_batch()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_nested_reference_collision_is_cross_role_and_private_error(self):
        shared = str(self.ds.FrameOfReferenceUID)
        second_path = self.source / '00002' / 'other.dcm'
        second = make_dicom(second_path, identity='other-patient')
        for keyword in ('ReferencedFrameOfReferenceUID', 'RelatedFrameOfReferenceUID', 'SourceFrameOfReferenceUID'):
            with self.subTest(keyword=keyword):
                child = Dataset(); setattr(child, keyword, shared)
                second.ReferencedPatientSequence = Sequence([child])
                second.save_as(second_path, enforce_file_format=True)
                with self.assertRaises(engine.BatchError) as caught:
                    self.run_batch()
                self.assertEqual(str(caught.exception), engine.FRAME_COLLISION)
                for secret in (shared, '00001', '00002', str(self.source), 'other-patient'):
                    self.assertNotIn(secret, str(caught.exception))
                self.assertFalse(self.output.exists())

    def test_within_patient_frame_references_remain_consistent(self):
        shared = str(self.ds.FrameOfReferenceUID)
        make_dicom(self.source / '00001' / 'rt.dcm', study=self.ds.StudyInstanceUID,
                   ref=self.ds.SOPInstanceUID, frame=shared)
        make_dicom(self.source / '00002' / 'other.dcm', identity='other-patient')
        self.run_batch()
        patient = [pydicom.dcmread(path) for path in (self.output / '00001').rglob('*.dcm')]
        image = next(ds for ds in patient if ds.Modality == 'MR')
        rt = next(ds for ds in patient if ds.Modality == 'RTSTRUCT')
        self.assertEqual(image.FrameOfReferenceUID, rt.FrameOfReferenceUID)
        self.assertEqual(image.FrameOfReferenceUID, rt.StructureSetROISequence[0].ReferencedFrameOfReferenceUID)
        self.assertEqual(image.SOPInstanceUID, rt.ReferencedImageSequence[0].ReferencedSOPInstanceUID)
        other = pydicom.dcmread(next((self.output / '00002').rglob('*.dcm')))
        self.assertNotEqual(image.FrameOfReferenceUID, other.FrameOfReferenceUID)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX filesystem required')
    def test_fifo_rejected_before_open(self):
        os.mkfifo(self.source / '00001' / 'z-fifo.dcm')
        result = subprocess.run([sys.executable, str(Path(engine.__file__)), '--source', str(self.source),
                                 '--destination', str(self.output)], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(str(self.source), result.stdout + result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
