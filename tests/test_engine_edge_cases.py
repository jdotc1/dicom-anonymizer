"""Edge-case tests for batch scanning and cleaning. All inputs are synthetic."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import CTImageStorage, RTStructureSetStorage, generate_uid

from test_engine import engine, make_dicom

# AppleDouble ("._name") header as written by macOS onto exFAT/SMB/FAT volumes.
APPLEDOUBLE = b'\x00\x05\x16\x07\x00\x02\x00\x00' + b'Mac OS X        ' + b'\x00' * 58


class EdgeCaseTests(unittest.TestCase):
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

    def output_files(self, patient=None):
        base = self.output / patient if patient else self.output
        return sorted(p for p in base.rglob('*') if p.is_file())

    def test_appledouble_resource_forks_are_excluded(self):
        make_dicom(self.source / '1' / 'Series A' / 'Image1.dcm')
        (self.source / '1' / 'Series A' / '._Image1.dcm').write_bytes(APPLEDOUBLE)
        (self.source / '1' / '._Series A').write_bytes(APPLEDOUBLE)
        (self.source / '._1').write_bytes(APPLEDOUBLE)
        records, patients, excluded = engine.scan(self.source)
        self.assertEqual(len(records), 1)
        self.assertEqual(excluded, 3)
        result = self.run_batch()
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['excluded_files'], 3)
        names = [p.name for p in self.output_files()]
        self.assertFalse(any(n.startswith('._') for n in names))
        self.assertEqual(sorted(names), ['Image_000001.dcm', 'anonymization-report.json'])

    def test_dot_underscore_name_without_appledouble_header_is_not_skipped(self):
        # Only genuine AppleDouble companions are excluded; real DICOM is never silently dropped.
        make_dicom(self.source / '1' / '._real.dcm')
        self.assertEqual(engine.scan(self.source)[2], 0)
        self.assertEqual(self.run_batch()['processed'], 1)
        (self.source / '1' / '._bad.dcm').write_bytes(b'not appledouble')
        with self.assertRaisesRegex(engine.BatchError, 'could not be read'):
            engine.scan(self.source)

    def test_appledouble_prefix_does_not_hide_other_problems(self):
        # A "._" directory is still not a numeric patient folder.
        make_dicom(self.source / '1' / 'a.dcm')
        (self.source / '._notes').mkdir()
        with self.assertRaisesRegex(engine.BatchError, 'numeric patient'):
            self.run_batch()
        self.assert_no_output()

    def test_nested_ds_store_is_excluded_not_copied(self):
        make_dicom(self.source / '1' / 'series' / 'a.dcm')
        (self.source / '1' / '.DS_Store').write_bytes(b'\0\0\0\1Bud1' + b'\0' * 64)
        (self.source / '1' / 'series' / '.DS_Store').write_bytes(b'\0\0\0\1Bud1' + b'\0' * 64)
        (self.source / '.DS_Store').write_bytes(b'\0\0\0\1Bud1' + b'\0' * 64)
        result = self.run_batch()
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['excluded_files'], 3)
        self.assertFalse(any(p.name == '.DS_Store' for p in self.output_files()))

    def test_leading_zero_identifiers_preserved_everywhere(self):
        make_dicom(self.source / '00123' / 'a.dcm', identity='source-a')
        make_dicom(self.source / '000' / 'b.dcm', identity='source-b')
        records, patients, _ = engine.scan(self.source)
        self.assertEqual([p['id'] for p in patients], ['000', '00123'])
        self.assertEqual({r.patient for r in records}, {'000', '00123'})
        self.run_batch()
        self.assertTrue((self.output / '00123').is_dir())
        self.assertTrue((self.output / '000').is_dir())
        for patient in ('00123', '000'):
            for path in self.output_files(patient):
                ds = pydicom.dcmread(path)
                self.assertEqual(str(ds.PatientName), patient)
                self.assertEqual(ds.PatientID, patient)
                self.assertEqual(ds.ReferencedPatientSequence[0].PatientID, patient)
                self.assertEqual(str(ds.ReferencedPatientSequence[0].PatientName), patient)
        report = (self.output / 'anonymization-report.json').read_text()
        self.assertIn('"00123"', report)
        self.assertIn('"000"', report)

    def test_non_ascii_and_space_names_inside_patient_folder(self):
        study, series = generate_uid(), generate_uid()
        make_dicom(self.source / '7' / 'Séries ñ 1' / 'Bild ü 1.dcm', study=study, series=series)
        make_dicom(self.source / '7' / 'Séries ñ 1' / '画像 2.DCM', study=study, series=series)
        make_dicom(self.source / '7' / 'with space' / 'no extension', study=study)
        result = self.run_batch()
        self.assertEqual(result['processed'], 3)
        self.assertEqual(result['excluded_files'], 0)
        names = [str(p.relative_to(self.output)) for p in self.output_files('7')]
        self.assertEqual(names, ['7/Series_0001/Image_000001.dcm', '7/Series_0001/Image_000002.dcm',
                                 '7/Series_0002/Image_000001.dcm'])
        report = (self.output / 'anonymization-report.json').read_text()
        for fragment in ('Séries', 'Bild', '画像', 'with space', 'no extension'):
            self.assertNotIn(fragment, report)

    def test_non_ascii_digits_and_whitespace_patient_folders_rejected(self):
        make_dicom(self.source / '1' / 'a.dcm')
        for name in ('١٢٣', '12 3', '123 ', '１２'):
            folder = self.source / name
            make_dicom(folder / 'a.dcm')
            with self.assertRaisesRegex(engine.BatchError, 'numeric patient'):
                engine.scan(self.source)
            for p in folder.iterdir():
                p.unlink()
            folder.rmdir()
        self.assertEqual(len(engine.scan(self.source)[0]), 1)

    def test_other_os_sidecars_inside_patient_folders_are_excluded(self):
        make_dicom(self.source / '1' / 'series' / 'a.dcm')
        (self.source / '1' / 'Icon\r').write_bytes(b'')
        (self.source / '1' / 'series' / 'Thumbs.db').write_bytes(b'\xd0\xcf\x11\xe0' + b'\0' * 200)
        (self.source / '1' / 'series' / 'desktop.ini').write_text('[.ShellClassInfo]')
        (self.source / '1' / 'series' / 'DICOMDIR.txt').write_text('private listing')
        result = self.run_batch()
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['excluded_files'], 4)
        self.assertEqual([p.name for p in self.output_files('1')], ['Image_000001.dcm'])

    def test_zero_byte_dcm_file_stops_batch(self):
        make_dicom(self.source / '1' / 'a.dcm')
        (self.source / '1' / 'empty.dcm').write_bytes(b'')
        with self.assertRaisesRegex(engine.BatchError, 'could not be read'):
            self.run_batch()
        self.assert_no_output()

    def test_cli_scan_counts_appledouble_without_leaking_names(self):
        import json, subprocess
        make_dicom(self.source / '1' / 'a.dcm')
        (self.source / '1' / '._a.dcm').write_bytes(APPLEDOUBLE)
        result = subprocess.run([sys.executable, str(Path(engine.__file__)), '--source', str(self.source), '--scan'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        event = json.loads(result.stdout)
        self.assertEqual((event['event'], event['total_files'], event['excluded_files']), ('scan', 1, 1))
        self.assertNotIn('._a', result.stdout)
        self.assertNotIn(str(self.source), result.stdout + result.stderr)

    def test_study_split_across_patient_folders_stops_batch(self):
        # Without source PatientIDs, one study in two folders would link two pseudonyms.
        for identities in (('', ''), ('source-a', 'source-b')):
            study = generate_uid()
            make_dicom(self.source / '1' / 'a.dcm', identity=identities[0], study=study)
            make_dicom(self.source / '2' / 'b.dcm', identity=identities[1], study=study)
            with self.assertRaisesRegex(engine.BatchError, 'same study occurs in multiple patient folders'):
                self.run_batch()
            self.assert_no_output()
        make_dicom(self.source / '2' / 'b.dcm', identity='source-b')
        self.assertEqual(self.run_batch()['processed'], 2)

    def test_empty_patient_folder_stops_batch(self):
        make_dicom(self.source / '1' / 'a.dcm')
        (self.source / '2').mkdir()
        with self.assertRaisesRegex(engine.BatchError, 'no readable DICOM'):
            self.run_batch()
        self.assert_no_output()

    def test_patient_folder_with_only_sidecars_stops_batch(self):
        make_dicom(self.source / '1' / 'a.dcm')
        (self.source / '2' / 'notes').mkdir(parents=True)
        (self.source / '2' / 'notes' / 'readme.txt').write_text('private text')
        (self.source / '2' / '.DS_Store').write_bytes(b'\0\0\0\1Bud1')
        with self.assertRaisesRegex(engine.BatchError, 'no readable DICOM'):
            self.run_batch()
        self.assert_no_output()

    def test_multiframe_instance_pixels_and_frame_count_retained(self):
        p = self.source / '1' / 'multi.dcm'
        ds = make_dicom(p)
        ds.NumberOfFrames = 3
        ds.PixelData = bytes(range(24))
        ds.save_as(p, enforce_file_format=True)
        self.run_batch()
        [out] = self.output_files('1')
        result = pydicom.dcmread(out)
        self.assertEqual(int(result.NumberOfFrames), 3)
        self.assertEqual(result.PixelData, bytes(range(24)))
        frame_bytes = int(result.Rows) * int(result.Columns) * int(result.BitsAllocated) // 8
        self.assertEqual(len(result.PixelData), int(result.NumberOfFrames) * frame_bytes)

    def test_rtstruct_references_follow_remapped_ct_uids(self):
        study, series, frame = generate_uid(), generate_uid(), generate_uid()
        ct_sops = []
        for i in range(2):
            p = self.source / '1' / 'ct' / f'{i}.dcm'
            ds = make_dicom(p, study=study, series=series)
            ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
            ds.Modality = 'CT'
            ds.FrameOfReferenceUID = frame
            ds.save_as(p, enforce_file_format=True)
            ct_sops.append(str(ds.SOPInstanceUID))
        p = self.source / '1' / 'rt.dcm'
        rt = make_dicom(p, study=study, ref=ct_sops[0])
        rt.FrameOfReferenceUID = frame
        contour_images = []
        for sop in ct_sops:
            item = Dataset(); item.ReferencedSOPClassUID = CTImageStorage; item.ReferencedSOPInstanceUID = sop
            contour_images.append(item)
        series_item = Dataset(); series_item.SeriesInstanceUID = series
        series_item.ContourImageSequence = Sequence(contour_images)
        study_item = Dataset(); study_item.ReferencedSOPClassUID = '1.2.840.10008.3.1.2.3.1'
        study_item.ReferencedSOPInstanceUID = study
        study_item.RTReferencedSeriesSequence = Sequence([series_item])
        frame_item = Dataset(); frame_item.FrameOfReferenceUID = frame
        frame_item.RTReferencedStudySequence = Sequence([study_item])
        rt.ReferencedFrameOfReferenceSequence = Sequence([frame_item])
        rt.StructureSetROISequence[0].ReferencedFrameOfReferenceUID = frame
        contour = Dataset(); contour.ContourGeometricType = 'CLOSED_PLANAR'
        contour.NumberOfContourPoints = 1; contour.ContourData = [1.5, 2.5, 3.5]
        contour_ref = Dataset(); contour_ref.ReferencedSOPClassUID = CTImageStorage
        contour_ref.ReferencedSOPInstanceUID = ct_sops[1]
        contour.ContourImageSequence = Sequence([contour_ref])
        roi_contour = Dataset(); roi_contour.ReferencedROINumber = 1
        roi_contour.ContourSequence = Sequence([contour])
        rt.ROIContourSequence = Sequence([roi_contour])
        rt.save_as(p, enforce_file_format=True)
        self.run_batch()
        output = [pydicom.dcmread(p) for p in self.output_files('1')]
        cts = [ds for ds in output if ds.Modality == 'CT']
        [out_rt] = [ds for ds in output if ds.Modality == 'RTSTRUCT']
        self.assertEqual(len(cts), 2)
        new_sops = {str(ds.SOPInstanceUID) for ds in cts}
        self.assertTrue(new_sops.isdisjoint(ct_sops))
        new_frame = str(cts[0].FrameOfReferenceUID)
        self.assertNotEqual(new_frame, frame)
        self.assertEqual({str(ds.FrameOfReferenceUID) for ds in cts}, {new_frame})
        self.assertEqual(str(out_rt.FrameOfReferenceUID), new_frame)
        frame_item = out_rt.ReferencedFrameOfReferenceSequence[0]
        self.assertEqual(str(frame_item.FrameOfReferenceUID), new_frame)
        study_item = frame_item.RTReferencedStudySequence[0]
        self.assertEqual(str(study_item.ReferencedSOPInstanceUID), str(cts[0].StudyInstanceUID))
        self.assertEqual(str(study_item.ReferencedSOPClassUID), '1.2.840.10008.3.1.2.3.1')
        series_item = study_item.RTReferencedSeriesSequence[0]
        self.assertEqual(str(series_item.SeriesInstanceUID), str(cts[0].SeriesInstanceUID))
        self.assertEqual({str(i.ReferencedSOPInstanceUID) for i in series_item.ContourImageSequence}, new_sops)
        self.assertEqual({str(i.ReferencedSOPClassUID) for i in series_item.ContourImageSequence}, {CTImageStorage})
        self.assertEqual(str(out_rt.StructureSetROISequence[0].ReferencedFrameOfReferenceUID), new_frame)
        contour = out_rt.ROIContourSequence[0].ContourSequence[0]
        self.assertIn(str(contour.ContourImageSequence[0].ReferencedSOPInstanceUID), new_sops)
        self.assertEqual([float(v) for v in contour.ContourData], [1.5, 2.5, 3.5])
        self.assertEqual(out_rt.StructureSetROISequence[0].ROIName, 'Prostate')
        self.assertEqual(str(out_rt.file_meta.MediaStorageSOPClassUID), RTStructureSetStorage)

    def test_pn_and_dates_cleared_three_sequence_levels_deep(self):
        ds = Dataset()
        level1 = Dataset(); level2 = Dataset(); level3 = Dataset()
        for depth, item in enumerate((level1, level2, level3), 1):
            item.PatientName = f'Deep{depth}^Private'
            item.ReferringPhysicianName = f'Doctor{depth}^Private'
            item.OperatorsName = f'Operator{depth}^Private'
            item.StudyDate = '20200101'
            item.ContentTime = '101010'
            item.AcquisitionDateTime = '20200101101010'
            item.PatientBirthDate = '19600101'
            item.SeriesDescription = f'label {depth}'
        level2.ReferencedStudySequence = Sequence([level3])
        level1.ReferencedSeriesSequence = Sequence([level2])
        ds.ReferencedPatientSequence = Sequence([level1])
        engine.clean(ds, '00042', {})
        items = [ds.ReferencedPatientSequence[0]]
        items.append(items[0].ReferencedSeriesSequence[0])
        items.append(items[1].ReferencedStudySequence[0])
        for depth, item in enumerate(items, 1):
            self.assertEqual(str(item.PatientName), '00042')
            for key in ('ReferringPhysicianName', 'OperatorsName', 'StudyDate', 'ContentTime',
                        'AcquisitionDateTime', 'PatientBirthDate'):
                self.assertIn(key, item)
                self.assertEqual(str(item.get(key)), '', f'{key} at depth {depth}')
            self.assertEqual(item.SeriesDescription, f'label {depth}')

    def test_deep_names_and_dates_cleared_in_written_output(self):
        p = self.source / '5' / 'a.dcm'
        ds = make_dicom(p)
        level3 = Dataset(); level3.PatientName = 'Deep^Private'; level3.StudyDate = '20200101'
        level2 = Dataset(); level2.ReferencedStudySequence = Sequence([level3])
        ds.ReferencedPatientSequence[0].ReferencedSeriesSequence = Sequence([level2])
        ds.save_as(p, enforce_file_format=True)
        self.run_batch()
        [out] = self.output_files('5')
        raw = out.read_bytes()
        self.assertNotIn(b'Private', raw)
        self.assertNotIn(b'20200101', raw)
        self.assertNotIn(b'19600101', raw)
        result = pydicom.dcmread(out)
        deep = result.ReferencedPatientSequence[0].ReferencedSeriesSequence[0].ReferencedStudySequence[0]
        self.assertEqual(str(deep.PatientName), '5')
        self.assertEqual(deep.StudyDate, '')


if __name__ == '__main__':
    unittest.main()
