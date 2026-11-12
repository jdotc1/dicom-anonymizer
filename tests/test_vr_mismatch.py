import importlib.util
import io
import sys
import unittest
from pathlib import Path

import pydicom
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, MRImageStorage, generate_uid

ENGINE = Path(__file__).resolve().parents[1] / 'engine' / 'engine.py'
spec = importlib.util.spec_from_file_location('bulk_engine_vr_mismatch', ENGINE)
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

# (tag, file VR that differs from the dictionary VR, sentinel value)
CASES = [
    ((0x0008, 0x1050), 'LO', 'SENTINEL^PERFORMER'),
    ((0x0008, 0x1070), 'SH', 'SENTINEL^OPERATOR'),
    ((0x0008, 0x0090), 'LO', 'SENTINEL^REFERRER'),
    ((0x0008, 0x0020), 'LO', '19710203'),
    ((0x0008, 0x0030), 'SH', '123456'),
    ((0x0010, 0x0030), 'CS', '19710204'),
    ((0x0008, 0x002A), 'LO', '20010101120000'),
    ((0x0008, 0x0030), 'DT', '123457'),
]


def base():
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = MRImageStorage
    ds.SOPClassUID = MRImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.Modality = 'MR'
    ds.PatientName = 'X'
    ds.PatientID = 'X'
    return ds


def roundtrip(ds):
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    data = buf.getvalue()
    return data, pydicom.dcmread(io.BytesIO(data))


def serialize(ds):
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    return buf.getvalue()


class VrMismatchTests(unittest.TestCase):
    def build(self, tag, vr, value, nested):
        ds = base()
        element = DataElement(tag, vr, value)
        if nested:
            item = Dataset()
            item.add(DataElement(tag, vr, value))
            ds.ReferencedStudySequence = [item]
        else:
            ds.add(element)
        return ds

    def locate(self, ds, tag, nested):
        return ds.ReferencedStudySequence[0] if nested else ds

    def test_cleared_top_level_and_nested(self):
        for nested in (False, True):
            for tag, vr, value in CASES:
                with self.subTest(tag=tag, vr=vr, nested=nested):
                    data, ds = roundtrip(self.build(tag, vr, value, nested))
                    self.assertIn(value.encode(), data)
                    engine.clean(ds, '00001', {})
                    holder = self.locate(ds, tag, nested)
                    self.assertTrue(tag not in holder or holder[tag].value in (None, '', b''))
                    out = serialize(ds)
                    self.assertNotIn(value.encode(), out)
                    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
                    engine.audit_dataset(ds, '00001', set())

    def test_audit_flags_uncleaned_survivor(self):
        for nested in (False, True):
            for tag, vr, value in CASES:
                with self.subTest(tag=tag, vr=vr, nested=nested):
                    _, ds = roundtrip(self.build(tag, vr, value, nested))
                    with self.assertRaises(engine.BatchError):
                        engine.audit_dataset(ds, '00001', set())

    def test_implicit_vr_unaffected_and_cleared(self):
        ds = base()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.ReferringPhysicianName = 'SENTINEL^IMPLICIT'
        buf = io.BytesIO()
        ds.save_as(buf, enforce_file_format=True)
        read = pydicom.dcmread(io.BytesIO(buf.getvalue()))
        engine.clean(read, '00001', {})
        self.assertNotIn(b'SENTINEL^IMPLICIT', serialize(read))


if __name__ == '__main__':
    unittest.main()
