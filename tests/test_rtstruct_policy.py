"""RTSTRUCT policy-specific synthetic gaps; no complete-IOD or visual claim."""
import json
import os
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid

import test_engine as fixtures

engine = fixtures.engine


class RTStructPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('RTSTRUCT_TEST_ROOT'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'input'
        self.output = self.root / 'output'
        self.patient = '00042'
        image = fixtures.make_dicom(self.source / self.patient / 'image.dcm')
        self.path = self.source / self.patient / 'structures.dcm'
        self.rt = fixtures.make_dicom(self.path, study=image.StudyInstanceUID,
                                      ref=image.SOPInstanceUID, frame=image.FrameOfReferenceUID)
        self.rt.SpecificCharacterSet = 'ISO_IR 192'
        self.rt.StructureSetLabel = 'SYNTH_LABEL'
        self.rt.StructureSetName = 'SYNTHETIC_NAME'
        self.rt.StructureSetDescription = 'SYNTHETIC_DESCRIPTION'
        self.rt.StructureSetDate = '20200102'
        self.rt.StructureSetTime = '123456'
        self.rt.StructureSetROISequence = Sequence([])
        self.rt.ROIContourSequence = Sequence([])
        self.rt.RTROIObservationsSequence = Sequence([])
        for number in (1, 2):
            roi = Dataset()
            roi.ROINumber = number
            roi.ReferencedFrameOfReferenceUID = image.FrameOfReferenceUID
            roi.ROIName = f'Café_ROI_{number}'
            roi.ROIDescription = f'SYNTHETIC_ROI_DESCRIPTION_{number}'
            roi.ROIGenerationAlgorithm = 'MANUAL'
            roi.ROIGenerationDescription = f'SYNTHETIC_GENERATION_{number}'
            roi.add_new(0x3006002D, 'DT', '20200102123456')  # ROI DateTime
            roi.add_new(0x3006002E, 'DT', '20200102123556')  # ROI Observation DateTime
            self.rt.StructureSetROISequence.append(roi)
            contour = Dataset()
            contour.ContourGeometricType = 'CLOSED_PLANAR'
            contour.NumberOfContourPoints = 4
            contour.ContourData = [0, 0, number, 2, 0, number, 2, 2, number, 0, 2, number]
            contour_image = Dataset()
            contour_image.ReferencedSOPClassUID = image.SOPClassUID
            contour_image.ReferencedSOPInstanceUID = image.SOPInstanceUID
            contour.ContourImageSequence = Sequence([contour_image])
            group = Dataset()
            group.ReferencedROINumber = number
            group.ROIDisplayColor = [number * 50, 100, 200]
            group.ContourSequence = Sequence([contour])
            self.rt.ROIContourSequence.append(group)
            observation = Dataset()
            observation.ObservationNumber = number
            observation.ReferencedROINumber = number
            observation.ROIObservationLabel = f'SYNTH_OBS_{number}'
            observation.ROIObservationDescription = f'SYNTHETIC_OBSERVATION_{number}'
            observation.ROIInterpreter = f'Synthetic{number}^Interpreter'
            observation.RTROIInterpretedType = 'CTV'
            self.rt.RTROIObservationsSequence.append(observation)

    def run_batch(self):
        self.rt.save_as(self.path, enforce_file_format=True)
        result = engine.run(self.source, self.output, progress=lambda *args, **kwargs: None)
        datasets = [pydicom.dcmread(path) for path in self.output.rglob('*.dcm')]
        return result, next(ds for ds in datasets if ds.Modality == 'RTSTRUCT')

    def cleaned(self):
        original_uids = engine.source_uids(self.rt, set())
        mapping = {}
        engine.clean(self.rt, self.patient, mapping)
        self.rt.file_meta.MediaStorageSOPInstanceUID = self.rt.SOPInstanceUID
        return original_uids, mapping

    def test_rt_specific_multi_item_text_and_dates_round_trip(self):
        _, rt = self.run_batch()
        self.assertEqual(rt.StructureSetLabel, 'Structures')
        for key in ('StructureSetName', 'StructureSetDescription', 'StructureSetDate', 'StructureSetTime'):
            self.assertIn(rt.get(key), ('', None), key)
        self.assertEqual(len(rt.StructureSetROISequence), 2)
        self.assertEqual(len(rt.RTROIObservationsSequence), 2)
        for roi, observation in zip(rt.StructureSetROISequence, rt.RTROIObservationsSequence):
            for key in ('ROIDescription', 'ROIGenerationDescription'):
                self.assertIn(roi.get(key), ('', None), key)
            for tag in (0x3006002D, 0x3006002E):
                self.assertIn(roi[tag].value, ('', None))
            self.assertIn(observation.ROIObservationDescription, ('', None))
            self.assertEqual(str(observation.ROIInterpreter), '')

    def test_retained_label_risk_and_unicode_are_explicit(self):
        for index, roi in enumerate(self.rt.StructureSetROISequence, 1):
            roi.ROIName = f'SYNTHETIC_ID_{index}_Café'
            self.rt.RTROIObservationsSequence[index - 1].ROIObservationLabel = f'SYNTH_ID_{index}'
        result, rt = self.run_batch()
        self.assertEqual(len(rt.StructureSetROISequence), 2)
        self.assertEqual(len(rt.RTROIObservationsSequence), 2)
        for index, (roi, observation) in enumerate(zip(rt.StructureSetROISequence, rt.RTROIObservationsSequence), 1):
            self.assertEqual(roi.ROIName, f'SYNTHETIC_ID_{index}_Café')
            self.assertEqual(observation.ROIObservationLabel, f'SYNTH_ID_{index}')
        self.assertEqual(result['processed'], 2)
        report = json.loads((self.output / 'anonymization-report.json').read_text())
        self.assertEqual(report['self_audit']['result'], 'passed')
        self.assertIn('ROI names and observation labels', report['policy']['retained'])
        self.assertIn('Pseudonymization', report['policy']['limitation'])

    def test_numeric_creator_interpreter_sequences_removed_in_rt_contexts(self):
        contexts = [self.rt, *self.rt.StructureSetROISequence, *self.rt.RTROIObservationsSequence]
        for context in contexts:
            for tag in (0x3006004D, 0x3006004E):
                items = []
                for number in (1, 2):
                    item = Dataset()
                    item.CodeMeaning = f'SYNTHETIC_CREATOR_{number}'
                    item.PersonName = f'Synthetic{number}^Creator'
                    items.append(item)
                context.add_new(tag, 'SQ', Sequence(items))
        _, rt = self.run_batch()
        self.assertEqual(len(rt.StructureSetROISequence), 2)
        self.assertEqual(len(rt.RTROIObservationsSequence), 2)
        for context in [rt, *rt.StructureSetROISequence, *rt.RTROIObservationsSequence]:
            for tag in (0x3006004D, 0x3006004E):
                self.assertNotIn(tag, context)

    def test_multi_roi_polygons_and_numeric_links_are_preserved(self):
        expected = [(int(item.ReferencedROINumber), list(item.ROIDisplayColor),
                     [float(v) for v in item.ContourSequence[0].ContourData])
                    for item in self.rt.ROIContourSequence]
        _, rt = self.run_batch()
        self.assertEqual(len(rt.ROIContourSequence), 2)
        self.assertEqual(len(rt.StructureSetROISequence), 2)
        self.assertEqual(len(rt.RTROIObservationsSequence), 2)
        for number, (group, roi, observation) in enumerate(zip(rt.ROIContourSequence,
                rt.StructureSetROISequence, rt.RTROIObservationsSequence), 1):
            self.assertEqual((int(roi.ROINumber), int(group.ReferencedROINumber),
                              int(observation.ReferencedROINumber)), (number, number, number))
            self.assertEqual(int(observation.ObservationNumber), number)
            self.assertEqual(observation.RTROIInterpretedType, 'CTV')
            self.assertEqual(len(group.ContourSequence), 1)
            contour = group.ContourSequence[0]
            self.assertEqual(int(contour.NumberOfContourPoints), 4)
            self.assertEqual(contour.ContourGeometricType, 'CLOSED_PLANAR')
            self.assertEqual((int(group.ReferencedROINumber), list(group.ROIDisplayColor),
                              [float(v) for v in contour.ContourData]), expected[number - 1])

    def test_retired_frame_relationship_maps_uid_without_changing_transform(self):
        related = generate_uid()
        matrix = [1, 0, 0, 12.5, 0, 1, 0, -3.25, 0, 0, 1, 2, 0, 0, 0, 1]
        frames = []
        for _ in range(2):
            frame = Dataset()
            frame.FrameOfReferenceUID = self.rt.FrameOfReferenceUID
            relation = Dataset()
            relation.RelatedFrameOfReferenceUID = related
            relation.FrameOfReferenceTransformationType = 'RIGID'
            relation.FrameOfReferenceTransformationMatrix = matrix
            frame.FrameOfReferenceRelationshipSequence = Sequence([relation])
            frames.append(frame)
        self.rt.ReferencedFrameOfReferenceSequence = Sequence(frames)
        _, rt = self.run_batch()
        relations = [item.FrameOfReferenceRelationshipSequence[0]
                     for item in rt.ReferencedFrameOfReferenceSequence]
        self.assertNotEqual(str(relations[0].RelatedFrameOfReferenceUID), related)
        self.assertEqual(relations[0].RelatedFrameOfReferenceUID, relations[1].RelatedFrameOfReferenceUID)
        for relation in relations:
            self.assertEqual([float(v) for v in relation.FrameOfReferenceTransformationMatrix], matrix)
            self.assertEqual(relation.FrameOfReferenceTransformationType, 'RIGID')

    def test_rt_audit_rejects_reintroduced_descriptions_sequences_and_source_uid(self):
        original_instance = str(self.rt.SOPInstanceUID)
        forbidden, _ = self.cleaned()
        cases = [('description', 0x30060088, 'ST', 'SYNTHETIC_REINTRODUCED'),
                 ('creator', 0x3006004D, 'SQ', Sequence([Dataset()])),
                 ('interpreter', 0x3006004E, 'SQ', Sequence([Dataset()])),
                 ('source_uid_in_label', 0x30060026, 'LO', original_instance)]
        for name, tag, vr, value in cases:
            with self.subTest(case=name):
                candidate = deepcopy(self.rt)
                context = (candidate.StructureSetROISequence[1] if name in ('creator', 'source_uid_in_label')
                           else candidate.RTROIObservationsSequence[1])
                context.add_new(tag, vr, value)
                with self.assertRaisesRegex(engine.BatchError, 'self-audit'):
                    engine.audit_dataset(candidate, self.patient, forbidden)

    def test_rt_description_reintroduced_after_clean_blocks_batch_publication(self):
        original_clean = engine.clean
        def reinject(ds, patient, mapping):
            original_clean(ds, patient, mapping)
            if ds.get('Modality') == 'RTSTRUCT':
                ds.RTROIObservationsSequence[1].ROIObservationDescription = 'SYNTHETIC_REINTRODUCED'
        with patch.object(engine, 'clean', side_effect=reinject):
            with self.assertRaisesRegex(engine.BatchError, 'self-audit'):
                self.run_batch()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])

    def test_audit_rejects_reintroduced_structure_label(self):
        forbidden, _ = self.cleaned()
        self.assertEqual(self.rt.StructureSetLabel, 'Structures')
        self.rt.StructureSetLabel = 'SYNTH_REINSERTED'
        with self.assertRaisesRegex(engine.BatchError, 'self-audit'):
            engine.audit_dataset(self.rt, self.patient, forbidden)

    def test_structure_label_rejects_noncanonical_values_and_vrs_recursively(self):
        forbidden, _ = self.cleaned()
        cases = [('replacement', 'SH', 'SYNTH_CHANGED'), ('empty', 'SH', ''),
                 ('whitespace', 'SH', 'Structures '),
                 ('multiple', 'SH', ['Structures', 'Structures']),
                 ('wrong_text_vr', 'LO', 'Structures'), ('sequence_vr', 'SQ', Sequence([]))]
        for location in ('root', 'roi', 'observation'):
            for name, vr, value in cases:
                with self.subTest(location=location, case=name):
                    candidate = deepcopy(self.rt)
                    context = {'root': candidate, 'roi': candidate.StructureSetROISequence[1],
                               'observation': candidate.RTROIObservationsSequence[1]}[location]
                    context.add_new(0x30060002, vr, value)
                    with self.assertRaisesRegex(engine.BatchError, 'self-audit'):
                        engine.audit_dataset(candidate, self.patient, forbidden)

    def test_structure_label_canonical_nested_and_absent_remain_accepted(self):
        self.rt.StructureSetROISequence[1].StructureSetLabel = 'SYNTH_NESTED'
        self.rt.RTROIObservationsSequence[1].StructureSetLabel = 'SYNTH_NESTED'
        forbidden, _ = self.cleaned()
        for context in (self.rt, self.rt.StructureSetROISequence[1], self.rt.RTROIObservationsSequence[1]):
            self.assertEqual(context.StructureSetLabel, 'Structures')
        engine.audit_dataset(self.rt, self.patient, forbidden)
        # clean() normalizes present labels; it does not require or add this tag.
        for context in (self.rt, self.rt.StructureSetROISequence[1], self.rt.RTROIObservationsSequence[1]):
            del context.StructureSetLabel
        engine.audit_dataset(self.rt, self.patient, forbidden)

    def test_reintroduced_structure_label_blocks_batch_publication(self):
        original_clean = engine.clean
        def reinject(ds, patient, mapping):
            original_clean(ds, patient, mapping)
            if ds.get('Modality') == 'RTSTRUCT':
                ds.StructureSetLabel = 'SYNTH_REINSERTED'
        with patch.object(engine, 'clean', side_effect=reinject):
            with self.assertRaisesRegex(engine.BatchError, 'self-audit'):
                self.run_batch()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])


if __name__ == '__main__':
    unittest.main()
