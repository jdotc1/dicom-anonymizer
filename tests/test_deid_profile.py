"""PS3.15 Annex E Table E.1-1 Basic Profile coverage tests for engine.clean()."""
import json
from pathlib import Path
import tempfile
import unittest

import pydicom
from pydicom.datadict import dictionary_VR, tag_for_keyword
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import MRImageStorage

from test_engine import engine, make_dicom

SECRET = 'Secret ID text'

# Basic Profile attributes that must be removed (sequences) or emptied (other VRs).
PROFILE_ATTRIBUTES = [
    # Present before build 4; kept here as regression coverage.
    'AccessionNumber', 'InstitutionName', 'InstitutionAddress', 'InstitutionalDepartmentName',
    'StationName', 'DeviceSerialNumber', 'StudyID', 'OtherPatientIDs', 'OtherPatientIDsSequence',
    'IssuerOfPatientID', 'PatientComments', 'AdditionalPatientHistory', 'ImageComments',
    'RequestAttributesSequence', 'PerformedProcedureStepID', 'PerformedProcedureStepDescription',
    'ScheduledProcedureStepID', 'RequestedProcedureID', 'StudyDescription', 'RequestingService',
    'PerformedStationName', 'PerformedLocation', 'OperatorsName', 'PhysiciansOfRecord',
    'ReferringPhysicianName', 'PerformingPhysicianName', 'NameOfPhysiciansReadingStudy',
    'RequestingPhysician', 'MilitaryRank', 'EthnicGroup', 'Occupation', 'PatientTelephoneNumbers',
    'PatientAddress', 'MedicalRecordLocator', 'CountryOfResidence', 'RegionOfResidence',
    'PatientMotherBirthName', 'PatientBirthName', 'PatientBirthDate', 'ContentCreatorName',
    'VerifyingObserverName', 'ReviewerName', 'ROIInterpreter', 'StructureSetName', 'ROIDescription',
    'DerivationDescription', 'StudyDate', 'ContentTime', 'AcquisitionDateTime',
    'ScheduledStationAETitle', 'ClinicalTrialSubjectID',
    # Newly handled in build 4.
    'AdmissionID', 'IssuerOfAdmissionIDSequence', 'ServiceEpisodeID', 'ServiceEpisodeDescription',
    'CurrentPatientLocation', 'PatientInstitutionResidence', 'PatientState', 'SpecialNeeds',
    'VisitComments', 'DischargeDiagnosisDescription', 'AdmittingDiagnosesCodeSequence',
    'ReferencedPatientAliasSequence', 'ScheduledPatientInstitutionResidence',
    'ReferringPhysicianAddress', 'ReferringPhysicianTelephoneNumbers', 'PersonAddress',
    'PersonTelephoneNumbers', 'PersonTelecomInformation', 'InstitutionCodeSequence',
    'InstitutionalDepartmentTypeCodeSequence', 'ReferringPhysicianIdentificationSequence',
    'ConsultingPhysicianIdentificationSequence', 'PerformingPhysicianIdentificationSequence',
    'PhysiciansOfRecordIdentificationSequence', 'PhysiciansReadingStudyIdentificationSequence',
    'RequestingPhysicianIdentificationSequence', 'OperatorIdentificationSequence',
    'ScheduledPerformingPhysicianIdentificationSequence', 'HumanPerformerCodeSequence',
    'HumanPerformerOrganization', 'ActualHumanPerformersSequence', 'AuthorObserverSequence',
    'ParticipantSequence', 'CustodialOrganizationSequence',
    'VerifyingObserverIdentificationCodeSequence', 'ContentCreatorIdentificationCodeSequence',
    'InterpretationApproverSequence', 'DistributionAddress', 'ReasonForStudy',
    'RequestedContrastAgent', 'ScheduledStationName', 'ScheduledProcedureStepLocation',
    'FillerOrderNumberImagingServiceRequest', 'PlacerOrderNumberImagingServiceRequest',
    'InterpretationText', 'InterpretationDiagnosisDescription', 'InterpretationID', 'ResultsID',
    'ResultsIDIssuer', 'ResultsComments', 'TopicTitle', 'TopicSubject', 'TopicAuthor',
    'TopicKeywords', 'ModifiedAttributesSequence', 'ContentSequence', 'IconImageSequence',
    'AcquisitionComments', 'AcquisitionDeviceProcessingDescription', 'ROIGenerationDescription',
    'FrameComments', 'DeviceDescription', 'DetectorID', 'GantryID', 'PlateID', 'CassetteID',
    'StorageMediaFileSetID', 'TextValue', 'TextString', 'TextComments', 'LabelText',
    'ContainerIdentifier', 'ContainerDescription', 'IssuerOfTheContainerIdentifierSequence',
    'SpecimenAccessionNumber', 'SpecimenDescriptionSequence', 'ProtocolContextSequence',
    'RetrieveURL', 'RetrieveURI', 'ClinicalTrialCoordinatingCenterName', 'ClinicalTrialSeriesID',
    'ClinicalTrialSeriesDescription', 'ClinicalTrialTimePointID',
    'ClinicalTrialTimePointDescription', 'ClinicalTrialProtocolEthicsCommitteeName',
    'ClinicalTrialProtocolEthicsCommitteeApprovalNumber',
    'TimezoneOffsetFromUTC', 'ModifyingDeviceID', 'ModifyingDeviceManufacturer',
    'ModifiedImageDescription', 'AuthorizationEquipmentCertificationNumber',
    'ReferencedDigitalSignatureSequence', 'ReferencedSOPInstanceMACSequence',
    'PatientTransportArrangements', 'ScheduledHumanPerformersSequence', 'ScheduledStudyLocation',
    'SourceSerialNumber', 'ContributionDescription', 'IdentifyingComments',
]

# Instance UIDs that must be remapped consistently (never retained verbatim).
REMAPPED_UIDS = [
    'FrameOfReferenceUID', 'DeviceUID', 'IrradiationEventUID', 'ConcatenationUID',
    'DimensionOrganizationUID', 'SynchronizationFrameOfReferenceUID', 'StorageMediaFileSetUID',
    'InstanceCreatorUID', 'ReferencedFrameOfReferenceUID', 'TargetUID', 'TrackingUID',
]

SAMPLE = {'PN': 'Secret^Person', 'DA': '20200101', 'TM': '101010', 'DT': '20200101101010',
          'AE': 'SECRETAE', 'CS': 'SECRET', 'UR': 'http://identifying.invalid/record'}


def sample_value(vr):
    return SAMPLE.get(vr, SECRET)


def populate(ds):
    for keyword in PROFILE_ATTRIBUTES:
        tag = tag_for_keyword(keyword)
        vr = dictionary_VR(tag).split(' or ')[0]
        if vr == 'SQ':
            item = Dataset()
            item.CodeValue = 'SECRET-CODE'
            item.CodeMeaning = SECRET
            item.InstitutionName = SECRET
            setattr(ds, keyword, Sequence([item]))
        else:
            ds.add_new(tag, vr, sample_value(vr))
    for index, keyword in enumerate(REMAPPED_UIDS):
        setattr(ds, keyword, f'1.2.826.0.1.3680043.99.{index + 1}')
    return ds


def retained(ds):
    ds.PatientName = 'Private^Person'
    ds.PatientID = 'private-id'
    ds.SeriesDescription = 'DWI axial b1000'
    ds.ProtocolName = 'Prostate diffusion'
    ds.SequenceName = '*ep_b1000'
    ds.PatientSex = 'M'
    ds.PatientAge = '064Y'
    ds.PatientSize = '1.8'
    ds.PatientWeight = '80'
    ds.SliceThickness = '3'
    ds.EchoTime = '84'
    ds.ROIName = 'Prostate'
    ds.ROIObservationLabel = 'GTV'
    ds.SOPClassUID = MRImageStorage
    ds.ReferencedSOPClassUID = MRImageStorage
    contour = Dataset()
    contour.ContourGeometricType = 'CLOSED_PLANAR'
    contour.NumberOfContourPoints = 1
    contour.ContourData = ['1.5', '-2.5', '3.25']
    ds.ContourSequence = Sequence([contour])
    ds.PixelData = b'\1\0\2\0'
    return ds


class BasicProfileTests(unittest.TestCase):
    def build(self):
        top = retained(populate(Dataset()))
        nested = retained(populate(Dataset()))
        deeper = retained(populate(Dataset()))
        nested.ReferencedImageSequence = Sequence([deeper])
        top.ReferencedSeriesSequence = Sequence([nested])
        return top, nested, deeper

    def assert_cleaned(self, ds, where):
        for keyword in PROFILE_ATTRIBUTES:
            with self.subTest(where=where, keyword=keyword):
                if dictionary_VR(tag_for_keyword(keyword)) == 'SQ':
                    self.assertNotIn(keyword, ds)
                else:
                    self.assertIn(keyword, ds)  # emptied, keeping Type 2 attributes present
                    self.assertIn(ds[keyword].value, ('', None))

    def test_profile_attributes_removed_or_emptied_top_and_nested(self):
        top, nested, deeper = self.build()
        engine.clean(top, '00001', {})
        for ds, where in ((top, 'top'), (nested, 'nested'), (deeper, 'nested-2')):
            self.assert_cleaned(ds, where)

    def test_no_secret_text_survives_anywhere(self):
        top, _, _ = self.build()
        engine.clean(top, '00001', {})
        for element in top.iterall():
            if element.VR in ('SQ', 'OB', 'OW', 'UN'):
                continue
            text = str(element.value)
            with self.subTest(keyword=element.keyword):
                self.assertNotIn('Secret', text)
                self.assertNotIn('SECRET', text)
                self.assertNotIn('identifying.invalid', text)
                self.assertNotIn('20200101', text)

    def test_generic_free_text_vrs_are_cleared(self):
        ds = Dataset()
        ds.add_new((0x0018, 0x9004), 'CS', 'RESEARCH')  # ContentQualification is retained (CS)
        ds.add_new(tag_for_keyword('ImageComments'), 'LT', SECRET)
        # Public free-text attributes not individually listed are cleared by VR.
        ds.add_new(tag_for_keyword('RequestedContrastAgent'), 'LO', SECRET)
        ds.add_new(tag_for_keyword('ReasonForVisit'), 'UT', SECRET) if tag_for_keyword('ReasonForVisit') else None
        ds.add_new(tag_for_keyword('CommentsOnRadiationDose'), 'ST', SECRET)
        ds.add_new(tag_for_keyword('PixelDataProviderURL'), 'UR', 'http://identifying.invalid/x')
        item = Dataset(); item.add_new(tag_for_keyword('CommentsOnRadiationDose'), 'ST', SECRET)
        ds.ReferencedStudySequence = Sequence([item])
        engine.clean(ds, '00001', {})
        self.assertEqual(ds.ContentQualification, 'RESEARCH')
        for element in ds.iterall():
            if element.VR in ('LT', 'ST', 'UT', 'UR', 'LO') and element.keyword != 'ContentQualification':
                with self.subTest(keyword=element.keyword):
                    self.assertIn(element.value, ('', None))

    def test_retention_contract_top_and_nested(self):
        top, nested, deeper = self.build()
        engine.clean(top, '00007', {})
        for ds in (top, nested, deeper):
            self.assertEqual(str(ds.PatientName), '00007')
            self.assertEqual(ds.PatientID, '00007')
            self.assertEqual(ds.SeriesDescription, 'DWI axial b1000')
            self.assertEqual(ds.ProtocolName, 'Prostate diffusion')
            self.assertEqual(ds.SequenceName, '*ep_b1000')
            self.assertEqual((ds.PatientSex, ds.PatientAge), ('M', '064Y'))
            self.assertEqual((float(ds.PatientSize), float(ds.PatientWeight)), (1.8, 80.0))
            self.assertEqual((float(ds.SliceThickness), float(ds.EchoTime)), (3.0, 84.0))
            self.assertEqual((ds.ROIName, ds.ROIObservationLabel), ('Prostate', 'GTV'))
            self.assertEqual(ds.SOPClassUID, MRImageStorage)
            self.assertEqual(ds.ReferencedSOPClassUID, MRImageStorage)
            self.assertEqual([float(v) for v in ds.ContourSequence[0].ContourData], [1.5, -2.5, 3.25])
            self.assertEqual(ds.ContourSequence[0].ContourGeometricType, 'CLOSED_PLANAR')
            self.assertEqual(ds.PixelData, b'\1\0\2\0')

    def test_instance_uids_remapped_consistently_top_and_nested(self):
        top, nested, deeper = self.build()
        originals = {k: str(top[k].value) for k in REMAPPED_UIDS}
        uid_map = {}
        engine.clean(top, '00001', uid_map)
        for keyword in REMAPPED_UIDS:
            with self.subTest(keyword=keyword):
                new = str(top[keyword].value)
                self.assertNotEqual(new, originals[keyword])
                self.assertTrue(pydicom.uid.UID(new).is_valid)
                self.assertEqual(str(nested[keyword].value), new)
                self.assertEqual(str(deeper[keyword].value), new)
                self.assertEqual(uid_map[originals[keyword]], new)

    def test_batch_output_drops_file_meta_titles_and_reports_build4(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'input' / '00001' / 'a.dcm'
            make_dicom(path)
            ds = pydicom.dcmread(path)
            ds.file_meta.SourceApplicationEntityTitle = 'SECRETAE'
            ds.file_meta.ImplementationVersionName = 'SECRETVER'
            populate(ds)
            ds.save_as(path, enforce_file_format=True)
            output = root / 'output'
            engine.run(root / 'input', output, progress=lambda *a, **k: None)
            out = pydicom.dcmread(next(output.rglob('*.dcm')))
            self.assertNotIn('SourceApplicationEntityTitle', out.file_meta)
            self.assertNotEqual(str(out.file_meta.get('ImplementationVersionName', '')), 'SECRETVER')
            self.assert_cleaned(out, 'written')
            self.assertEqual(out.SeriesDescription, 'DWI axial b1000')
            self.assertEqual(out.PatientID, '00001')
            report = json.loads((output / 'anonymization-report.json').read_text())
            self.assertEqual(report['policy']['version'], '2.0-build4')
            self.assertEqual(engine.POLICY['version'], '2.0-build4')


if __name__ == '__main__':
    unittest.main()
