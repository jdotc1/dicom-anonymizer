#!/usr/bin/env python3
"""Local bulk DICOM pseudonymization. Source data is never modified."""
import argparse
import errno
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import tempfile
import warnings
from dataclasses import dataclass

import pydicom
from pydicom.uid import generate_uid

warnings.filterwarnings('ignore', module='pydicom')
logging.getLogger('pydicom').disabled = True
POLICY = {
    'version': '2.0-build5', 'modalities': ['MR', 'CT', 'RTSTRUCT'],
    'patient_identity': 'Exact numeric patient folder identifier in PatientName and PatientID',
    'private_tags': 'removed recursively', 'dates_times': 'cleared recursively',
    'free_text': 'LT/ST/UT text, URLs and PS3.15 Annex E Basic Profile identifying attributes removed or cleared recursively',
    'uids': 'non-class UIDs consistently remapped; shared patient-relative frame UIDs across patient folders rejected',
    'filenames': 'generated independently of original names',
    'retained': 'SeriesDescription, ProtocolName, SequenceName, ContrastBolusAgent, SoftwareVersions, Manufacturer, pixel data, contour geometry, quantitative measurements, ROI names and observation labels',
    'limitation': 'Pseudonymization; not certified DICOM confidentiality-profile conformance. Review retained image, contour, and ROI content before sharing.'
}

class BatchError(Exception):
    def __init__(self, message, *, cancelled=False, cleanup_failed=False, staging_path=None, output_published=False,
                 output_issue=None, required_bytes=None, available_bytes=None):
        super().__init__(message)
        self.cancelled = cancelled
        self.cleanup_failed = cleanup_failed
        self.staging_path = staging_path
        self.output_published = output_published
        self.output_issue = output_issue
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes


CANCELLED = 'Processing was cancelled. No completed output was published.'
PROCESSING_FAILURE = ('Processing failed. Check input integrity, output permissions and available '
                      'disk space; no completed output was published.')


def output_error(error):
    """Classify only errors from a known destination operation; never source reads."""
    if error.errno in {errno.ENOSPC, errno.EDQUOT}:
        issue = 'space'
        message = 'The output location ran out of available space or its storage quota was reached. Free space or choose another output location, then retry.'
    elif error.errno in {errno.EACCES, errno.EPERM, errno.EROFS}:
        issue = 'permissions'
        message = 'The output location cannot be written to. Check its permissions or choose another writable output location, then retry.'
    elif error.errno in {errno.ENOENT, errno.ENOTDIR, errno.ENODEV, errno.ENXIO, errno.ESTALE, errno.EIO}:
        issue = 'unavailable'
        message = 'The output location could not be accessed. Check that it is available or choose another output location, then retry.'
    elif error.errno == errno.EEXIST:
        issue = 'conflict'
        message = 'The output folder already exists. Choose a new output folder, then retry.'
    else:
        issue = 'unknown'
        message = 'The output location could not be used. Check the location or choose another writable output location, then retry.'
    return BatchError(message + ' No completed output was published.', output_issue=issue)


def destination_operation(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except OSError as error:
        raise output_error(error) from None


def approximate_storage(value):
    # Use a human-readable estimate; events retain the original byte counts.
    for unit, scale in [('TiB', 1024 ** 4), ('GiB', 1024 ** 3), ('MiB', 1024 ** 2)]:
        if value >= scale:
            return f'{value / scale:.1f} {unit}'
    return f'{value} bytes'


class Cancellation:
    """Defer cancellation across atomic publication and while recovering a failed batch."""
    def __init__(self):
        self.deferred = False
        self.requested = False

    def cancel(self, _signum=None, _frame=None):
        self.requested = True
        if not self.deferred:
            raise BatchError(CANCELLED, cancelled=True)

    def begin_publication(self):
        # The boundary starts before rename: an interrupt cannot split a successful
        # rename from its complete event. A request already received still cancels.
        self.deferred = True
        if self.requested:
            raise BatchError(CANCELLED, cancelled=True)


class StagingOwnershipError(OSError):
    pass


def remove_staging(staging, identity):
    """Remove only the directory created by this operation, never a replacement."""
    try:
        current = staging.lstat()
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) != identity or not stat.S_ISDIR(current.st_mode):
        raise StagingOwnershipError('The staging directory was replaced.')
    shutil.rmtree(staging)


@dataclass
class Record:
    path: Path
    patient: str
    series: tuple
    sop: str
    identity: str
    signature: tuple


def emit(event, **values):
    print(json.dumps(dict(event=event, **values)), flush=True)


def fingerprint(path):
    s = path.stat(follow_symlinks=False)
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def checked_read(path):
    if path.is_symlink():
        raise BatchError('Symbolic links are not supported. Use a local copy of the input folders.')
    try:
        if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
            raise BatchError('Input files cannot be read. Check permissions and available local storage.')
        try:
            ds = pydicom.dcmread(path)
        except pydicom.errors.InvalidDicomError:
            ds = pydicom.dcmread(path, force=True)
            if not all(ds.get(k) for k in ('SOPClassUID', 'SOPInstanceUID', 'StudyInstanceUID', 'SeriesInstanceUID')):
                raise ValueError('Unrecognized dataset')
        # Force lazy elements to decode before accepting input.
        list(ds.iterall())
        return ds
    except BatchError:
        raise
    except Exception:
        raise BatchError('A DICOM file could not be read. Repair or remove the malformed input before retrying.') from None


def validate(ds):
    if str(ds.get('Modality', '')) not in POLICY['modalities']:
        raise BatchError('An unsupported modality was found. This version accepts MR, CT and RTSTRUCT only.')
    for key in ('SOPClassUID', 'SOPInstanceUID', 'StudyInstanceUID', 'SeriesInstanceUID'):
        value = ds.get(key)
        if not value or not pydicom.uid.UID(str(value)).is_valid:
            raise BatchError('A DICOM file lacks a valid required class, instance, study or series UID.')
    if getattr(ds, 'file_meta', None) is None or not ds.file_meta.get('TransferSyntaxUID'):
        raise BatchError('A DICOM file lacks a transfer syntax. Repair the input before retrying.')
    for element in ds.iterall():
        if element.keyword == 'BurnedInAnnotation' and str(element.value).strip().upper() == 'YES':
            raise BatchError('Burned-in annotations are declared. Review and clean the image content before retrying.')
        if 0x6000 <= element.tag.group <= 0x601E:
            raise BatchError('An overlay was found. Review and remove potentially identifying overlays before retrying.')


# Patient-relative spatial identities, including nested RTSTRUCT/registration references.
# Synchronization/equipment frame identifiers do not imply patient-relative geometry.
PATIENT_FRAME_UID_KEYS = frozenset({
    'FrameOfReferenceUID', 'ReferencedFrameOfReferenceUID',
    'RelatedFrameOfReferenceUID', 'SourceFrameOfReferenceUID',
})
FRAME_COLLISION = ('The same patient frame of reference occurs in multiple patient folders. '
                   'Resolve the folder assignments before retrying.')


def claim_patient_frames(ds, patient, owners):
    for element in ds.iterall():
        if element.VR != 'UI' or element.keyword not in PATIENT_FRAME_UID_KEYS:
            continue
        values = element.value if element.VM > 1 else [element.value]
        for value in values:
            uid = str(value).strip() if value is not None else ''
            if uid and owners.setdefault(uid, patient) != patient:
                raise BatchError(FRAME_COLLISION)


def scan(source):
    source = Path(source).absolute()
    if source.is_symlink() or not source.is_dir():
        raise BatchError('Select an existing local batch folder, without symbolic links.')
    records, excluded, patients, seen_ids, seen_sops, seen_studies = [], 0, {}, {}, set(), {}
    frame_owners = {}
    def appledouble(path, header=None):
        # macOS writes "._<name>" resource-fork companions on exFAT/FAT/SMB volumes.
        if not path.name.startswith('._'):
            return False
        if header is None:
            with path.open('rb') as stream:
                header = stream.read(4)
        return header[:4] == b'\x00\x05\x16\x07'
    try:
        children = sorted(source.iterdir(), key=lambda p: p.name)
        for patient in children:
            if patient.is_symlink():
                raise BatchError('Symbolic links are not supported. Use a local copy of the input folders.')
            if patient.is_file() and (patient.name == '.DS_Store' or appledouble(patient)):
                excluded += 1
                continue
            if not patient.is_dir() or not re.fullmatch(r'[0-9]+', patient.name):
                raise BatchError('The batch folder must contain only numeric patient folders. Move unrelated root items elsewhere.')
            if len(patient.name) > 64:
                raise BatchError('A patient folder identifier exceeds 64 characters. Use a numeric identifier that fits DICOM patient fields.')
            local, identities, names = [], set(), set()
            def walk_error(_):
                raise BatchError('An input folder cannot be listed. Check read permissions and retry.')
            for root, dirs, files in os.walk(patient, followlinks=False, onerror=walk_error):
                dirs.sort(); files.sort()
                if any((Path(root) / d).is_symlink() for d in dirs):
                    raise BatchError('Symbolic links are not supported. Use a local copy of the input folders.')
                for filename in files:
                    path = Path(root) / filename
                    if path.is_symlink():
                        raise BatchError('Symbolic links are not supported. Use a local copy of the input folders.')
                    if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
                        raise BatchError('Input files cannot be read. Check permissions and available local storage.')
                    with path.open('rb') as stream:
                        header = stream.read(132)
                    if appledouble(path, header):
                        excluded += 1
                        continue
                    if header[128:132] != b'DICM' and path.suffix.lower() not in ('.dcm', '.dicom'):
                        # A valid DICOM dataset can lack both extension and Part 10 preamble.
                        try:
                            probe = pydicom.dcmread(path, force=True, stop_before_pixels=True)
                            candidate = any(probe.get(k) for k in ('SOPClassUID', 'SOPInstanceUID', 'StudyInstanceUID', 'SeriesInstanceUID'))
                        except BatchError:
                            raise
                        except Exception:
                            candidate = False
                        if not candidate:
                            excluded += 1
                            continue
                    ds = checked_read(path)
                    validate(ds)
                    name = str(ds.get('PatientName', '')).strip()
                    if name:
                        names.add(name)
                    identity = str(ds.get('PatientID', '')).strip()
                    if identity:
                        identities.add(identity)
                    sop = str(ds.SOPInstanceUID)
                    if sop in seen_sops:
                        raise BatchError('Duplicate DICOM instance UIDs were found. Remove duplicate or conflicting instances before retrying.')
                    seen_sops.add(sop)
                    study = str(ds.StudyInstanceUID)
                    if seen_studies.setdefault(study, patient.name) != patient.name:
                        raise BatchError('The same study occurs in multiple patient folders. Resolve the folder assignments before retrying.')
                    claim_patient_frames(ds, patient.name, frame_owners)
                    local.append(Record(path, patient.name, (str(ds.StudyInstanceUID), str(ds.SeriesInstanceUID)), sop, identity, fingerprint(path)))
            if not local:
                raise BatchError('A patient folder contains no readable DICOM files.')
            if len(identities) > 1 or len(names) > 1:
                raise BatchError('A patient folder contains conflicting patient identities. Correct the folder assignment before retrying.')
            for identity in identities:
                if identity in seen_ids:
                    raise BatchError('The same patient identity occurs in multiple patient folders. Resolve the folder assignments before retrying.')
                seen_ids[identity] = patient.name
            records.extend(local)
            patients[patient.name] = {'id': patient.name, 'files': len(local), 'series': len({r.series for r in local})}
    except BatchError:
        raise
    except OSError:
        raise BatchError('Input files cannot be read. Check permissions and available local storage.') from None
    if not records:
        raise BatchError('No numeric patient folders containing DICOM data were found.')
    return records, list(patients.values()), excluded

# Free text with potential identity; ROI labels and observation labels intentionally retained.
REMOVE_KEYS = {
    'AccessionNumber', 'StudyID', 'InstitutionName', 'InstitutionAddress',
    'InstitutionalDepartmentName', 'StationName', 'DeviceSerialNumber',
    'StudyDescription', 'ImageComments',
    'DerivationDescription', 'AdditionalPatientHistory', 'PatientComments',
    'RequestAttributesSequence', 'IssuerOfPatientID', 'IssuerOfPatientIDQualifiersSequence',
    'OtherPatientIDsSequence', 'OtherPatientIDs', 'PatientAddress', 'PatientTelephoneNumbers',
    'PatientTelecomInformation', 'MedicalRecordLocator', 'EthnicGroup', 'Occupation',
    'MilitaryRank', 'BranchOfService', 'CountryOfResidence', 'RegionOfResidence',
    'AdmittingDiagnosesDescription', 'RequestedProcedureDescription',
    'PerformedProcedureStepDescription', 'ScheduledProcedureStepDescription',
    'RequestedProcedureID', 'ScheduledProcedureStepID', 'PerformedProcedureStepID',
    'ClinicalTrialSponsorName', 'ClinicalTrialProtocolID', 'ClinicalTrialProtocolName',
    'ClinicalTrialSiteID', 'ClinicalTrialSiteName', 'ClinicalTrialSubjectID',
    'ClinicalTrialSubjectReadingID', 'DigitalSignaturesSequence', 'MACParametersSequence',
    'OriginalAttributesSequence', 'EncryptedAttributesSequence', 'DataSetTrailingPadding',
    'CommentsOnThePerformedProcedureStep', 'ImagingServiceRequestComments',
    'OrderCallbackPhoneNumber', 'OrderEntererLocation', 'PerformedLocation',
    'PerformedStationAETitle', 'PerformedStationName', 'PerformedProcedureTypeDescription',
    'ReasonForTheImagingServiceRequest', 'ReasonForTheRequestedProcedure',
    'RequestedProcedureComments', 'RequestedProcedureLocation', 'RequestingService',
    'SecondaryCaptureDeviceID', 'StudyComments', 'StructureSetName', 'StructureSetDescription',
    'ROIDescription', 'ROIObservationDescription', 'PositionReferenceIndicator',
    # Build 4: remaining PS3.15 Annex E Table E.1-1 Basic Profile identifiers (X/Z/D/U).
    'AdmissionID', 'IssuerOfAdmissionIDSequence', 'ServiceEpisodeID', 'ServiceEpisodeDescription',
    'CurrentPatientLocation', 'PatientInstitutionResidence', 'PatientState', 'SpecialNeeds',
    'VisitComments', 'DischargeDiagnosisDescription', 'AdmittingDiagnosesCodeSequence',
    'ReferencedPatientAliasSequence', 'ScheduledPatientInstitutionResidence',
    'ReferringPhysicianAddress', 'ReferringPhysicianTelephoneNumbers',
    'PersonAddress', 'PersonTelephoneNumbers', 'PersonTelecomInformation',
    'InstitutionCodeSequence', 'InstitutionalDepartmentTypeCodeSequence',
    'ReferringPhysicianIdentificationSequence', 'ConsultingPhysicianIdentificationSequence',
    'PerformingPhysicianIdentificationSequence', 'PhysiciansOfRecordIdentificationSequence',
    'PhysiciansReadingStudyIdentificationSequence', 'RequestingPhysicianIdentificationSequence',
    'OperatorIdentificationSequence', 'ScheduledPerformingPhysicianIdentificationSequence',
    'HumanPerformerCodeSequence', 'HumanPerformerOrganization', 'ActualHumanPerformersSequence',
    'AuthorObserverSequence', 'ParticipantSequence', 'CustodialOrganizationSequence',
    'VerifyingObserverIdentificationCodeSequence', 'ContentCreatorIdentificationCodeSequence',
    'InterpretationApproverSequence', 'DistributionAddress',
    'ReasonForStudy', 'RequestedContrastAgent', 'ScheduledStationName',
    'ScheduledProcedureStepLocation', 'FillerOrderNumberImagingServiceRequest',
    'PlacerOrderNumberImagingServiceRequest', 'InterpretationText',
    'InterpretationDiagnosisDescription', 'InterpretationID', 'ResultsID', 'ResultsIDIssuer',
    'ResultsComments', 'TopicTitle', 'TopicSubject', 'TopicAuthor', 'TopicKeywords',
    'ModifiedAttributesSequence', 'ContentSequence', 'IconImageSequence',
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
    'SourceSerialNumber', 'ContributionDescription', 'IdentifyingComments'
}


# Structural dictionary identifiers are not patient-specific identifiers.
PRESERVE_UID_KEYS = {
    'TransferSyntaxUID', 'ImplementationClassUID', 'CodingSchemeUID',
    'ContextGroupExtensionCreatorUID', 'MappingResourceUID', 'ContextUID',
    'SOPClassesInStudy', 'SOPClassesSupported', 'RelatedGeneralSOPClassUID',
    'OriginalSpecializedSOPClassUID'
}


# Numeric policy additions: PS3.15 2026d E.1-1, resolved against the shipped
# README, except ContrastBolusAgent retains the existing product behavior.
# Numeric tags also cover entries absent from pydicom 3.0.2.
CLEAR_TAGS = {
    0x00081088,  # PyramidDescription
    0x00120022,  # IssuerOfClinicalTrialProtocolID
    0x00120032,  # IssuerOfClinicalTrialSiteID
    0x00120041,  # IssuerOfClinicalTrialSubjectID
    0x00120043,  # IssuerOfClinicalTrialSubjectReadingID
    0x00120055,  # IssuerOfClinicalTrialTimePointID
    0x00120073,  # IssuerOfClinicalTrialSeriesID
    0x00160071,  # GPSLatitudeRef
    0x00160072,  # GPSLatitude
    0x00160073,  # GPSLongitudeRef
    0x00160074,  # GPSLongitude
    0x00160075,  # GPSAltitudeRef
    0x00160076,  # GPSAltitude
    0x00160079,  # GPSStatus
    0x0016007A,  # GPSMeasureMode
    0x0016007B,  # GPSDOP
    0x0016007C,  # GPSSpeedRef
    0x0016007D,  # GPSSpeed
    0x0016007E,  # GPSTrackRef
    0x0016007F,  # GPSTrack
    0x00160080,  # GPSImgDirectionRef
    0x00160081,  # GPSImgDirection
    0x00160083,  # GPSDestLatitudeRef
    0x00160084,  # GPSDestLatitude
    0x00160085,  # GPSDestLongitudeRef
    0x00160086,  # GPSDestLongitude
    0x00160087,  # GPSDestBearingRef
    0x00160088,  # GPSDestBearing
    0x00160089,  # GPSDestDistanceRef
    0x0016008A,  # GPSDestDistance
    0x0016008E,  # GPSDifferential
    0x00181005,  # GeneratorID
    0x00181011,  # HardcopyCreationDeviceID
    0x001811BB,  # AcquisitionFieldOfViewLabel
    0x00189367,  # XRaySourceID
    0x00189371,  # XRayDetectorID
    0x00189937,  # RequestedSeriesDescription
    0x00200027,  # PyramidLabel
    0x00320012,  # StudyIDIssuer
    0x00380011,  # IssuerOfAdmissionID
    0x00380061,  # IssuerOfServiceEpisodeID
    0x003A0020,  # MultiplexGroupLabel
    0x003A0203,  # ChannelLabel
    0x003A020C,  # ChannelDerivationDescription
    0x00400012,  # PreMedication
    0x00400551,  # SpecimenIdentifier
    0x00400600,  # SpecimenShortDescription
    0x004006FA,  # SlideIdentifier
    0x00403001,  # ConfidentialityConstraintOnPatientDataDescription
    0x0040A027,  # VerifyingOrganization
    0x0040A354,  # TelephoneNumberTrial
    0x0040B03F,  # MontageChannelLabel
    0x0050001B,  # ContainerComponentID
    0x006A0005,  # AnnotationGroupLabel
    0x0072005F,  # SelectorASValue
    0x00720066,  # SelectorLOValue
    0x0072006C,  # SelectorSHValue
    0x04000563,  # ModifyingSystem
    0x04000564,  # SourceOfPreviousValues
    0x04000565,  # ReasonForTheAttributeModification
    0x04000600,  # InstanceOriginStatus
    0x30020121,  # PositionAcquisitionTemplateName
    0x3004007F,  # DoseCalculationModelName
    0x300A0002,  # RTPlanLabel
    0x300A0003,  # RTPlanName
    0x300A000B,  # TreatmentSites
    0x300A0016,  # DoseReferenceDescription
    0x300A0072,  # FractionGroupDescription
    0x300A00B2,  # TreatmentMachineName
    0x300A0216,  # SourceManufacturer
    0x300A0608,  # TreatmentPositionGroupLabel
    0x300A0611,  # RTAccessoryHolderSlotID
    0x300A0615,  # RTAccessoryDeviceSlotID
    0x300A0619,  # RadiationDoseIdentificationLabel
    0x300A0623,  # RadiationDoseInVivoMeasurementLabel
    0x300A062A,  # RTToleranceSetLabel
    0x300A067C,  # RadiationGenerationModeLabel
    0x300A079A,  # DisplacementReferenceLabel
    0x300C0113,  # ReasonForOmissionDescription
    0x3010001B,  # DeviceAlternateIdentifier
    0x3010002D,  # DeviceLabel
    0x30100033,  # UserContentLabel
    0x30100034,  # UserContentLongLabel
    0x30100035,  # EntityLabel
    0x30100036,  # EntityName
    0x30100038,  # EntityLongLabel
    0x30100054,  # RTPrescriptionLabel
    0x30100056,  # RTTreatmentApproachLabel
    0x30100077,  # TreatmentSite
    0x40080202,  # InterpretationIDIssuer
}
REMOVE_TAGS = {
    0x00081301,  # PrincipalDiagnosisCodeSequence
    0x00081302,  # PrimaryDiagnosisCodeSequence
    0x00081303,  # SecondaryDiagnosesCodeSequence
    0x00081304,  # HistologicalDiagnosesCodeSequence
    0x00120023,  # OtherClinicalTrialProtocolIDsSequence
    0x0016002B,  # MakerNote
    0x0016004B,  # DeviceSettingDescription
    0x00160070,  # GPSVersionID
    0x0016008B,  # GPSProcessingMethod
    0x0016008C,  # GPSAreaInformation
    0x0018100A,  # UDISequence
    0x00185011,  # TransducerIdentificationSequence
    0x00321067,  # ReasonForVisitCodeSequence
    0x00340001,  # FlowIdentifierSequence
    0x00380064,  # IssuerOfServiceEpisodeIDSequence
    0x00400555,  # AcquisitionContextSequence
    0x00400562,  # IssuerOfTheSpecimenIdentifierSequence
    0x00400610,  # SpecimenPreparationSequence
    0x0040100A,  # ReasonForRequestedProcedureCodeSequence
    0x00401011,  # IntendedRecipientsOfResultsIdentificationSequence
    0x00401101,  # PersonIdentificationCodeSequence
    0x00404025,  # ScheduledStationNameCodeSequence
    0x00404027,  # ScheduledStationGeographicLocationCodeSequence
    0x00404028,  # PerformedStationNameCodeSequence
    0x00404030,  # PerformedStationGeographicLocationCodeSequence
    0x0040A073,  # VerifyingObserverSequence
    0x0040A358,  # VerbalSourceIdentifierCodeSequenceTrial
    0x0040B020,  # WaveformAnnotationSequence
    0x00700001,  # GraphicAnnotationSequence
    0x04000310,  # CertifiedTimestamp
    0x04000404,  # MAC
    0x04000551,  # NonconformingModifiedAttributesSequence
    0x04000552,  # NonconformingDataElementValue
    0x3006004D,  # ROICreatorSequence
    0x3006004E,  # ROIInterpreterSequence
    0x30100081,  # PrescriptionNotesSequence
    0x40080118,  # ResultsDistributionListSequence
    0xFFFCFFFC,  # DataSetTrailingPadding
}


def clean(ds, patient, uid_map):
    ds.remove_private_tags()
    for element in list(ds):
        keyword = element.keyword
        if element.tag in REMOVE_TAGS or element.tag.group & 0xFF00 == 0x5000:
            del ds[element.tag]
        elif keyword in {'PatientName', 'PatientID'}:
            element.value = patient
        elif element.VR in ('PN', 'DA', 'DT', 'TM', 'AE'):
            # Keep required type-2 attributes present with empty values.
            element.value = ''
        elif element.VR == 'UN':
            # Public tags pydicom cannot interpret are uninspectable bytes that may carry identity; drop them.
            del ds[element.tag]
        elif keyword == 'StructureSetLabel':
            element.value = 'Structures'
        elif (element.tag.group == 0x0010 and keyword not in {'PatientSex', 'PatientAge', 'PatientSize', 'PatientWeight'}) or keyword in REMOVE_KEYS or element.tag in CLEAR_TAGS or element.VR in ('LT', 'ST', 'UT', 'UR'):
            # Free-text (LT/ST/UT) and URL (UR) values can carry identity; none is in the retention contract.
            if element.VR == 'SQ':
                del ds[element.tag]
            else:
                element.value = ''
        elif element.VR == 'SQ':
            for item in element.value:
                clean(item, patient, uid_map)
        elif element.VR == 'UI' and not ('SOPClassUID' in keyword or keyword in PRESERVE_UID_KEYS):
            def remap(value):
                value = str(value)
                if not value:
                    return ''
                if value not in uid_map:
                    uid_map[value] = generate_uid()
                return uid_map[value]
            element.value = [remap(v) for v in element.value] if element.VM > 1 else remap(element.value)


def run(source, destination, progress=emit, audit=True, *, cancellation=None):
    cancellation = cancellation or Cancellation()
    source = Path(source).absolute()
    destination = Path(destination).absolute()
    if destination_operation(destination.exists) or destination_operation(destination.is_symlink):
        raise BatchError('The output folder already exists. Choose a new output folder.', output_issue='conflict')
    src_real = source.resolve()
    dst_real = destination_operation(destination.resolve)
    if src_real == dst_real or src_real in dst_real.parents or dst_real in src_real.parents:
        raise BatchError('The output must be separate from the input folder, with neither inside the other.', output_issue='conflict')
    if not destination_operation(destination.parent.is_dir):
        raise BatchError('The output parent folder does not exist. Choose an existing location.', output_issue='unavailable')
    records, patients, excluded = scan(source)
    progress('scan', patients=patients, total_files=len(records), excluded_files=excluded)
    check_disk_space(records, destination.parent)
    staging = None
    staging_identity = None
    publication_succeeded = False
    try:
        # Capture ownership before honoring a signal delivered during allocation.
        cancellation.deferred = True
        staging = Path(destination_operation(tempfile.mkdtemp, prefix='.dicom-batch-', dir=destination.parent))
        created = destination_operation(staging.lstat)
        staging_identity = (created.st_dev, created.st_ino)
        cancellation.deferred = False
        if cancellation.requested:
            cancellation.cancel()
        uid_map, series_map, counters = {}, {}, {}
        forbidden_uids, written = set(), []
        for index, record in enumerate(records, 1):
            if record.path.is_symlink() or fingerprint(record.path) != record.signature:
                raise BatchError('The input changed during processing. Keep input files unchanged and retry.')
            ds = checked_read(record.path)
            validate(ds)
            if str(ds.SOPInstanceUID) != record.sop or str(ds.get('PatientID', '')).strip() != record.identity:
                raise BatchError('The input changed during processing. Keep input files unchanged and retry.')
            if audit:
                source_uids(ds, forbidden_uids)
                forbidden_uids.update(str(v) for v in (ds.file_meta.get('MediaStorageSOPInstanceUID'),) if v)
            clean(ds, record.patient, uid_map)
            ds.PatientName = record.patient
            ds.PatientID = record.patient
            ds.PatientIdentityRemoved = 'YES'
            ds.DeidentificationMethod = 'Local bulk metadata pseudonymization v2; review retained content'
            ds.preamble = b'\0' * 128
            # Rebuild file meta to exclude original implementation identifiers and titles.
            transfer = ds.file_meta.TransferSyntaxUID
            ds.file_meta = pydicom.dataset.FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = transfer
            ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
            ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
            patient_series = series_map.setdefault(record.patient, {})
            if record.series not in patient_series:
                patient_series[record.series] = len(patient_series) + 1
            series_number = patient_series[record.series]
            key = (record.patient, series_number)
            counters[key] = counters.get(key, 0) + 1
            folder = staging / record.patient / f'Series_{series_number:04d}'
            destination_operation(folder.mkdir, parents=True, exist_ok=True)
            out_path = folder / f'Image_{counters[key]:06d}.dcm'
            destination_operation(ds.save_as, out_path, enforce_file_format=True)
            written.append((out_path, record.patient))
            if index % 10 == 0 or index == len(records):
                progress('progress', patient_id=record.patient, processed=index, total_files=len(records))
        audit_summary = self_audit(staging, written, forbidden_uids, progress=progress) if audit else {'result': 'skipped', 'files_audited': 0}
        progress('phase', name='finalizing')
        forbidden_uids = None
        report = {'policy': POLICY, 'software': environment_info(), 'patients': patients,
                  'patient_count': len(patients), 'total_files': len(records), 'excluded_files': excluded,
                  'self_audit': audit_summary}
        destination_operation((staging / 'anonymization-report.json').write_text, json.dumps(report, indent=2) + '\n')
        # Recheck before publication; rename is atomic. macOS exclusive rename prevents races.
        if destination_operation(destination.exists) or destination_operation(destination.is_symlink):
            raise BatchError('The output folder appeared during processing. Choose another output folder.', output_issue='conflict')
        cancellation.begin_publication()
        if sys.platform == 'darwin':
            import ctypes
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.renamex_np(os.fsencode(staging), os.fsencode(destination), 4) != 0:
                raise output_error(OSError(ctypes.get_errno(), 'Output publication failed.')) from None
        else:
            destination_operation(os.rename, staging, destination)
        publication_succeeded = True
        staging = None
        result = dict(processed=len(records), total_files=len(records), patients=len(patients), excluded_files=excluded, audited_files=audit_summary['files_audited'])
        progress('complete', **result)
        return result
    except Exception as original:
        # A second Cancel must not interrupt cleanup or replace the first failure.
        cancellation.deferred = True
        if publication_succeeded:
            raise BatchError(
                'The completed output was published, but completion could not be confirmed. '
                'Check the output folder before retrying.', output_published=True) from original
        if staging is not None:
            try:
                remove_staging(staging, staging_identity)
            except OSError as cleanup_error:
                owned_path = None if staging_identity is None or isinstance(cleanup_error, StagingOwnershipError) else str(staging)
                recovery = (
                    ' The staging folder ownership could not be confirmed. Inspect the output location before retrying.'
                    if staging_identity is None else
                    ' The staging location changed and could not be cleaned safely. Inspect the output location before retrying.'
                    if owned_path is None else
                    ' Incomplete output could not be removed. Remove the staging folder before retrying.')
                message = str(original) if isinstance(original, BatchError) else PROCESSING_FAILURE
                raise BatchError(
                    message + recovery,
                    cancelled=isinstance(original, BatchError) and original.cancelled,
                    cleanup_failed=True, staging_path=owned_path,
                    output_issue=getattr(original, 'output_issue', None),
                    required_bytes=getattr(original, 'required_bytes', None),
                    available_bytes=getattr(original, 'available_bytes', None)) from original
        raise


AUDIT_FAILURE = 'The pre-publication self-audit found retained identifying metadata. No output was published.'
DISK_MARGIN_BYTES = 32 * 1024 * 1024
# Value representations that can carry a copied UID string; numeric VRs are excluded to avoid false positives.
UID_CARRYING_VRS = {'UI', 'LO', 'LT', 'SH', 'ST', 'UT', 'UC', 'UR', 'CS', 'AE'}


def source_uids(ds, found):
    """Collect source non-class UID values (the ones clean() must remap), recursively."""
    for element in ds.iterall():
        if element.VR != 'UI' or 'SOPClassUID' in element.keyword or element.keyword in PRESERVE_UID_KEYS:
            continue
        values = element.value if element.VM > 1 else [element.value]
        # Standard DICOM-defined UIDs (1.2.840.10008.*) are not patient-specific and may legitimately recur.
        found.update(u for u in (str(v).strip() for v in values if v is not None) if u and not u.startswith('1.2.840.10008.'))
    return found


def check_disk_space(records, destination_parent):
    required = int(sum(r.signature[2] for r in records) * 1.1) + DISK_MARGIN_BYTES
    try:
        free = shutil.disk_usage(destination_parent).free
    except OSError as error:
        raise output_error(error) from None
    if free < required:
        raise BatchError(
            f'Not enough free disk space at the output location. Estimated need: {approximate_storage(required)}; '
            f'available: {approximate_storage(free)}. This estimate is not a guarantee. '
            'Free space or choose another output location, then retry.',
            output_issue='space', required_bytes=required, available_bytes=free)
    return required


def audit_values(element):
    value = element.value
    if value is None:
        return []
    if isinstance(value, (list, tuple, pydicom.multival.MultiValue)):
        return [str(v).strip() for v in value if v is not None]
    return [str(value).strip()]


def audit_dataset(ds, patient, forbidden_uids):
    """Raise BatchError unless a staged dataset meets the invariants that must hold for every output."""
    for element in ds.iterall():
        if element.tag.is_private or element.tag in REMOVE_TAGS or element.tag.group & 0xFF00 == 0x5000:
            raise BatchError(AUDIT_FAILURE)
        vr, keyword = element.VR, element.keyword
        clear_value = (element.tag in CLEAR_TAGS or keyword in REMOVE_KEYS or
                       (element.tag.group == 0x0010 and keyword not in
                        {'PatientName', 'PatientID', 'PatientSex', 'PatientAge', 'PatientSize', 'PatientWeight'}) or
                       vr in ('AE', 'LT', 'ST', 'UT', 'UR'))
        if clear_value and (vr == 'SQ' or element.value not in (None, '', b'')):
            raise BatchError(AUDIT_FAILURE)
        if vr == 'SQ':
            continue
        if vr == 'UN':
            raise BatchError(AUDIT_FAILURE)
        values = audit_values(element) if vr not in ('OB', 'OW', 'OF', 'OD', 'OL', 'OV', 'UN') else []
        if keyword in ('PatientName', 'PatientID'):
            if values != [patient]:
                raise BatchError(AUDIT_FAILURE)
        elif vr == 'PN' and any(values):
            raise BatchError(AUDIT_FAILURE)
        elif vr in ('DA', 'DT', 'TM') and any(values):
            raise BatchError(AUDIT_FAILURE)
        if forbidden_uids and vr in UID_CARRYING_VRS and any(v in forbidden_uids for v in values):
            raise BatchError(AUDIT_FAILURE)
    meta = getattr(ds, 'file_meta', None)
    if meta is None or str(meta.get('MediaStorageSOPInstanceUID', '')) != str(ds.get('SOPInstanceUID', '')) or not str(ds.get('SOPInstanceUID', '')):
        raise BatchError(AUDIT_FAILURE)
    for element in meta:
        if element.tag.is_private or (element.VR in UID_CARRYING_VRS and any(v in forbidden_uids for v in audit_values(element))):
            raise BatchError(AUDIT_FAILURE)


def self_audit(staging, written, forbidden_uids, progress=None):
    """Re-read each entire staged DICOM, including metadata after Pixel Data, before publication."""
    total = len(written)
    if progress is not None:
        progress('audit_progress', audited_files=0, total_files=total)
    staged = {path for path, _ in written}
    for root, _dirs, files in os.walk(staging):
        for filename in files:
            path = Path(root) / filename
            if path.suffix == '.dcm' and path not in staged:
                raise BatchError(AUDIT_FAILURE)
    for index, (path, patient) in enumerate(written, 1):
        try:
            ds = checked_read(path)
            validate(ds)
        except BatchError:
            raise
        except Exception:
            raise BatchError('A staged output file could not be re-read for the self-audit. No output was published.') from None
        audit_dataset(ds, patient, forbidden_uids)
        if progress is not None and (index % 10 == 0 or index == total):
            progress('audit_progress', audited_files=index, total_files=total)
    return {'result': 'passed', 'files_audited': len(written),
            'checks': ['entire staged file decoded', 'removed attributes and curve groups absent',
                       'cleared policy attributes and free text empty', 'no uninterpreted UN attributes', 'no private tags', 'PatientName/PatientID equal folder identifier', 'no other person names',
                       'no dates/times', 'no source instance/study/series/frame UIDs', 'file meta instance UID synchronized']}


def environment_info():
    return {'pydicom': pydicom.__version__, 'python': '%d.%d.%d' % sys.version_info[:3]}


def main():
    parser = argparse.ArgumentParser(description='Bulk local DICOM pseudonymization')
    parser.add_argument('--source', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--scan', action='store_true')
    group.add_argument('--destination')
    args = parser.parse_args()
    cancellation = Cancellation()
    signal.signal(signal.SIGTERM, cancellation.cancel)
    signal.signal(signal.SIGINT, cancellation.cancel)
    try:
        if args.scan:
            records, patients, excluded = scan(args.source)
            emit('scan', patients=patients, total_files=len(records), excluded_files=excluded)
        else:
            run(args.source, args.destination, cancellation=cancellation)
        return 0
    except BatchError as exc:
        cancellation.deferred = True
        details = dict(message=str(exc), cancelled=exc.cancelled, cleanup_failed=exc.cleanup_failed)
        if exc.cleanup_failed and exc.staging_path is not None:
            details['staging_path'] = exc.staging_path
        if exc.output_published:
            details['output_published'] = True
        elif exc.output_issue in {'space', 'permissions', 'unavailable', 'conflict', 'unknown'}:
            details['output_issue'] = exc.output_issue
            if (exc.output_issue == 'space' and type(exc.required_bytes) is int and
                    type(exc.available_bytes) is int and exc.required_bytes > exc.available_bytes >= 0):
                details['required_bytes'] = exc.required_bytes
                details['available_bytes'] = exc.available_bytes
        emit('error', **details)
    except Exception:
        cancellation.deferred = True
        emit('error', message=PROCESSING_FAILURE, cancelled=False, cleanup_failed=False)
    return 1

if __name__ == '__main__':
    sys.exit(main())
