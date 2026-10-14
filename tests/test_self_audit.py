import importlib.util
import json
from collections import namedtuple
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pydicom
from pydicom.uid import generate_uid

TESTS = Path(__file__).resolve().parent
ENGINE = TESTS.parents[0] / 'engine' / 'engine.py'
spec = importlib.util.spec_from_file_location('bulk_engine_self_audit', ENGINE)
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

helper_spec = importlib.util.spec_from_file_location('engine_test_helpers', TESTS / 'test_engine.py')
helpers = importlib.util.module_from_spec(helper_spec)
helper_spec.loader.exec_module(helpers)
make_dicom = helpers.make_dicom

Usage = namedtuple('Usage', 'total used free')


class SelfAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'input'
        self.source.mkdir()
        self.output = self.root / 'output'
        study = generate_uid()
        self.image_sop = generate_uid()
        self.source_uids = {study, self.image_sop}
        self.first = make_dicom(self.source / '00001' / 'a.dcm', identity='synthetic-source-id', study=study, sop=self.image_sop, frame='1.2.3.4.5')
        self.rt = make_dicom(self.source / '00001' / 'rt.dcm', identity='synthetic-source-id', study=study, ref=self.image_sop, frame='1.2.3.4.5')
        self.second = make_dicom(self.source / '00002' / 'b.dcm', identity='other-source-id')
        for ds in (self.first, self.rt, self.second):
            self.source_uids.update({str(ds.SOPInstanceUID), str(ds.StudyInstanceUID), str(ds.SeriesInstanceUID)})

    def tearDown(self):
        self.tmp.cleanup()

    def run_batch(self):
        return engine.run(self.source, self.output, progress=lambda *a, **k: None)

    def assert_no_output(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def assert_leak_blocked(self, leak):
        original = engine.clean

        def leaky_clean(ds, patient, uid_map):
            original(ds, patient, uid_map)
            if 'SOPInstanceUID' in ds:  # top-level dataset only
                leak(ds)
        with patch.object(engine, 'clean', leaky_clean):
            with self.assertRaises(engine.BatchError) as caught:
                self.run_batch()
        message = str(caught.exception)
        self.assertIn('self-audit', message)
        for secret in ('Private', 'synthetic-source-id', str(self.source), *self.source_uids):
            self.assertNotIn(secret, message)
        self.assert_no_output()

    def test_forced_private_tag_leak_blocks_publication(self):
        self.assert_leak_blocked(lambda ds: ds.add_new((0x0029, 0x0010), 'LO', 'VENDOR'))

    def test_forced_nested_private_tag_leak_blocks_publication(self):
        def leak(ds):
            ds.ReferencedPatientSequence[0].add_new((0x0029, 0x0010), 'LO', 'VENDOR')
        self.assert_leak_blocked(leak)

    def test_forced_date_leak_blocks_publication(self):
        def leak(ds):
            ds.StudyDate = '20200101'
        self.assert_leak_blocked(leak)

    def test_forced_stray_person_name_blocks_publication(self):
        def leak(ds):
            ds.OperatorsName = 'Stray^Operator'
        self.assert_leak_blocked(leak)

    def test_forced_nested_identity_mismatch_blocks_publication(self):
        def leak(ds):
            ds.ReferencedPatientSequence[0].PatientID = 'synthetic-source-id'
        self.assert_leak_blocked(leak)

    def test_forced_source_uid_leak_blocks_publication(self):
        def leak(ds):
            ds.add_new((0x0020, 0x0052), 'UI', '1.2.3.4.5')  # original FrameOfReferenceUID
        self.assert_leak_blocked(leak)

    def test_forced_unknown_public_un_element_blocks_publication(self):
        # An uninterpreted (UN) public element can carry names, dates or UIDs, so it must not pass the audit.
        self.assert_leak_blocked(lambda ds: ds.add_new((0x0008, 0x1234), 'UN', b'19700101 SMITH^JOHN'))

    def test_unknown_public_un_elements_are_removed_top_level_and_nested(self):
        path = self.source / '00001' / 'a.dcm'
        ds = pydicom.dcmread(path)
        ds.add_new((0x0008, 0x1234), 'UN', b'19700101 SMITH^JOHN')
        ds.ReferencedPatientSequence[0].add_new((0x0008, 0x1234), 'UN', b'SMITH^JOHN')
        ds.save_as(path)
        self.run_batch()
        for out in self.output.rglob('*.dcm'):
            written = pydicom.dcmread(out)
            self.assertFalse(any(e.tag == (0x0008, 0x1234) for e in written.iterall()), out.name)
            self.assertFalse(any(e.VR == 'UN' and e.value for e in written.iterall()), out.name)

    def test_disk_space_preflight(self):
        with patch.object(engine.shutil, 'disk_usage', return_value=Usage(10, 10, 0)):
            with self.assertRaisesRegex(engine.BatchError, 'disk space') as caught:
                self.run_batch()
        self.assertNotIn(str(self.root), str(caught.exception))
        self.assert_no_output()
        with patch.object(engine.shutil, 'disk_usage', side_effect=OSError('private path')):
            with self.assertRaisesRegex(engine.BatchError, 'space'):
                self.run_batch()
        self.assert_no_output()
        with patch.object(engine.shutil, 'disk_usage', return_value=Usage(1 << 40, 0, 1 << 40)):
            self.assertEqual(self.run_batch()['processed'], 3)

    def test_report_contains_environment_counts_and_audit_without_identifiers(self):
        result = self.run_batch()
        self.assertEqual(result['audited_files'], 3)
        text = (self.output / 'anonymization-report.json').read_text()
        report = json.loads(text)
        self.assertEqual(report['software']['pydicom'], pydicom.__version__)
        self.assertEqual(report['software']['python'], '%d.%d.%d' % sys.version_info[:3])
        self.assertEqual(report['patient_count'], 2)
        self.assertEqual({p['id']: (p['files'], p['series']) for p in report['patients']}, {'00001': (2, 2), '00002': (1, 1)})
        self.assertEqual(report['excluded_files'], 0)
        self.assertEqual(report['total_files'], 3)
        self.assertEqual(report['self_audit']['result'], 'passed')
        self.assertEqual(report['self_audit']['files_audited'], 3)
        for secret in ('Private^Person', 'Nested^Identity', 'synthetic-source-id', 'other-source-id',
                       str(self.source), 'a.dcm', 'rt.dcm', '1.2.3.4.5', *self.source_uids):
            self.assertNotIn(secret, text)

    def test_audit_passes_on_clean_output_and_can_be_disabled(self):
        self.assertEqual(self.run_batch()['audited_files'], 3)
        second = self.root / 'output-unaudited'
        result = engine.run(self.source, second, progress=lambda *a, **k: None, audit=False)
        self.assertEqual(result['audited_files'], 0)
        report = json.loads((second / 'anonymization-report.json').read_text())
        self.assertEqual(report['self_audit']['result'], 'skipped')


if __name__ == '__main__':
    unittest.main()
