"""Small synthetic staged-header checks; no real imaging or application launch."""
import os
from pathlib import Path
import tempfile
import unittest

import pydicom
from pydicom.dataset import FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, ImplicitVRLittleEndian

import test_engine as fixtures

engine = fixtures.engine


class FileHeaderAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('HEADER_AUDIT_TEST_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patient = '00043'
        self.input = self.root / 'input'
        self.original = fixtures.make_dicom(self.input / self.patient / 'image.dcm')
        self.forbidden = engine.source_uids(self.original, set())
        self.staging = self.root / 'staged'
        self.staging.mkdir()
        self.path = self.staging / 'image.dcm'

    def write_staged(self, transfer=ExplicitVRLittleEndian):
        ds = pydicom.dcmread(self.original.filename)
        engine.clean(ds, self.patient, {})
        ds.preamble = b'\0' * 128
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = transfer
        meta.MediaStorageSOPClassUID = ds.SOPClassUID
        meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        ds.file_meta = meta
        ds.save_as(self.path, enforce_file_format=True)

    def mutate_meta(self, operation, path=None):
        path = path or self.path
        ds = pydicom.dcmread(path)
        operation(ds.file_meta)
        # Standard-enforcing writes repair mismatched class UIDs. Preserve the
        # deliberate staged fault here so the real reader/audit must reject it.
        ds.save_as(path, enforce_file_format=False)

    def audit(self):
        return engine.self_audit(self.staging, [(self.path, self.patient)], self.forbidden)

    def assert_header_rejected(self):
        with self.assertRaisesRegex(engine.BatchError, 'self-audit') as caught:
            self.audit()
        self.assertNotIn(str(self.root), str(caught.exception))
        self.assertNotIn('SYNTH', str(caught.exception))

    def test_nonzero_preamble_rejected_after_staged_file_read(self):
        self.write_staged()
        with self.path.open('r+b') as stream:
            stream.write(b'SYNTH_HEADER' + b'\0' * (128 - len(b'SYNTH_HEADER')))
        self.assert_header_rejected()

    def test_file_meta_class_mismatch_rejected(self):
        self.write_staged()
        self.mutate_meta(lambda meta: setattr(meta, 'MediaStorageSOPClassUID', CTImageStorage))
        decoded = pydicom.dcmread(self.path)
        self.assertNotEqual(decoded.file_meta.MediaStorageSOPClassUID, decoded.SOPClassUID)
        self.assert_header_rejected()

    def test_reintroduced_application_titles_and_addresses_rejected(self):
        for tag, vr, value in [(0x00020016, 'AE', 'SYNTH_SOURCE_AE'),
                               (0x00020017, 'AE', 'SYNTH_SEND_AE'),
                               (0x00020018, 'AE', 'SYNTH_RECV_AE'),
                               (0x00020026, 'UR', 'https://synthetic.invalid/source'),
                               (0x00020027, 'UR', 'https://synthetic.invalid/send'),
                               (0x00020028, 'UR', 'https://synthetic.invalid/receive')]:
            with self.subTest(tag=tag):
                self.write_staged()
                self.mutate_meta(lambda meta: meta.add_new(tag, vr, value))
                self.assert_header_rejected()

    def test_reintroduced_implementation_identity_rejected(self):
        for keyword, value in [('ImplementationClassUID', '2.25.9912345678901'),
                               ('ImplementationVersionName', 'SYNTH_IMPL')]:
            with self.subTest(keyword=keyword):
                self.write_staged()
                self.mutate_meta(lambda meta: setattr(meta, keyword, value))
                self.assert_header_rejected()

    def test_extra_private_information_and_unknown_meta_rejected(self):
        for tag, vr, value in [(0x00020100, 'UI', '2.25.9912345678902'),
                               (0x00020102, 'OB', b'SYNTH_PRIVATE'),
                               (0x00020014, 'LO', 'SYNTH_EXTRA')]:
            with self.subTest(tag=tag):
                self.write_staged()
                self.mutate_meta(lambda meta: meta.add_new(tag, vr, value))
                self.assert_header_rejected()

    def test_rebuilt_header_accepts_preserved_transfer_syntaxes(self):
        for transfer in (ExplicitVRLittleEndian, ImplicitVRLittleEndian):
            with self.subTest(transfer=transfer):
                self.write_staged(transfer)
                result = self.audit()
                self.assertEqual(result['result'], 'passed')
                self.assertEqual(result['files_audited'], 1)
                decoded = pydicom.dcmread(self.path)
                self.assertEqual(decoded.file_meta.TransferSyntaxUID, transfer)

    def test_faulted_staged_header_blocks_batch_publication_and_cleans_staging(self):
        for fault in ('preamble', 'class', 'title'):
            with self.subTest(fault=fault):
                output = self.root / ('output-' + fault)
                injected = []
                def progress(event, **values):
                    if event != 'audit_progress' or values.get('audited_files') != 0:
                        return
                    stages = list(self.root.glob('.dicom-batch-*'))
                    self.assertEqual(len(stages), 1)
                    [path] = list(stages[0].rglob('*.dcm'))
                    if fault == 'preamble':
                        with path.open('r+b') as stream:
                            stream.write(b'SYNTH_HEADER' + b'\0' * (128 - len(b'SYNTH_HEADER')))
                    elif fault == 'class':
                        self.mutate_meta(lambda meta: setattr(meta, 'MediaStorageSOPClassUID', CTImageStorage), path)
                    else:
                        self.mutate_meta(lambda meta: setattr(meta, 'SourceApplicationEntityTitle', 'SYNTH_SOURCE_AE'), path)
                    injected.append(fault)
                with self.assertRaisesRegex(engine.BatchError, 'self-audit') as caught:
                    engine.run(self.input, output, progress=progress)
                self.assertEqual(injected, [fault])
                self.assertNotIn(str(self.root), str(caught.exception))
                self.assertNotIn('SYNTH', str(caught.exception))
                self.assertFalse(output.exists())
                self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])


if __name__ == '__main__':
    unittest.main()
