"""Hand-written answer key for the canary retention survey (test support only).

Everything here is written from the de-identification intent (the README retention
contract and the DICOM identity-bearing attribute classes), NOT derived from the
engine's REMOVE_KEYS / CLEAR_TAGS / REMOVE_TAGS tables. This module must not import
the engine, and a test enforces that. Tags are explicit numbers so a typo in a
keyword cannot silently follow a typo in the engine; a test cross-checks each
tag/keyword/VR against the pinned pydicom dictionary.

Expectation vocabulary
  GONE      the planted value must not survive (element removed, blanked or replaced)
  REMOVED   the element itself must be absent afterwards
  REPLACED  the value is replaced by a pseudonym or fixed label
  REMAPPED  a UID must change to a fresh value
  KEPT      the value is retained by design
"""
from collections import namedtuple

Entry = namedtuple('Entry', 'tag keyword vr expect')

GONE, REMOVED, REPLACED, REMAPPED, KEPT = 'GONE', 'REMOVED', 'REPLACED', 'REMAPPED', 'KEPT'

NAMED = (
    # Patient and person identity
    Entry(0x00100010, 'PatientName', 'PN', REPLACED),
    Entry(0x00100020, 'PatientID', 'LO', REPLACED),
    Entry(0x00100030, 'PatientBirthDate', 'DA', GONE),
    Entry(0x00100032, 'PatientBirthTime', 'TM', GONE),
    Entry(0x00101000, 'OtherPatientIDs', 'LO', GONE),
    Entry(0x00101001, 'OtherPatientNames', 'PN', GONE),
    Entry(0x00101005, 'PatientBirthName', 'PN', GONE),
    Entry(0x00101040, 'PatientAddress', 'LO', GONE),
    Entry(0x00102154, 'PatientTelephoneNumbers', 'SH', GONE),
    Entry(0x00102150, 'CountryOfResidence', 'LO', GONE),
    Entry(0x00102180, 'Occupation', 'SH', GONE),
    Entry(0x001021B0, 'AdditionalPatientHistory', 'LT', GONE),
    Entry(0x00104000, 'PatientComments', 'LT', GONE),
    Entry(0x00080090, 'ReferringPhysicianName', 'PN', GONE),
    Entry(0x00081048, 'PhysiciansOfRecord', 'PN', GONE),
    Entry(0x00081050, 'PerformingPhysicianName', 'PN', GONE),
    Entry(0x00081070, 'OperatorsName', 'PN', GONE),
    Entry(0x00321032, 'RequestingPhysician', 'PN', GONE),
    # Institution, device and order identifiers
    Entry(0x00080050, 'AccessionNumber', 'SH', GONE),
    Entry(0x00080080, 'InstitutionName', 'LO', GONE),
    Entry(0x00080081, 'InstitutionAddress', 'ST', GONE),
    Entry(0x00081010, 'StationName', 'SH', GONE),
    Entry(0x00081040, 'InstitutionalDepartmentName', 'LO', GONE),
    Entry(0x00181000, 'DeviceSerialNumber', 'LO', GONE),
    Entry(0x00181010, 'SecondaryCaptureDeviceID', 'LO', GONE),
    Entry(0x00200010, 'StudyID', 'SH', GONE),
    Entry(0x00321060, 'RequestedProcedureDescription', 'LO', GONE),
    Entry(0x00400254, 'PerformedProcedureStepDescription', 'LO', GONE),
    Entry(0x00120010, 'ClinicalTrialSponsorName', 'LO', GONE),
    Entry(0x00120040, 'ClinicalTrialSubjectID', 'LO', GONE),
    # Free text
    Entry(0x00081030, 'StudyDescription', 'LO', GONE),
    Entry(0x00082111, 'DerivationDescription', 'ST', GONE),
    Entry(0x00204000, 'ImageComments', 'LT', GONE),
    Entry(0x00284000, 'ImagePresentationComments', 'LT', GONE),
    Entry(0x00880200, 'IconImageSequence', 'SQ', REMOVED),
    Entry(0x00400275, 'RequestAttributesSequence', 'SQ', REMOVED),
    Entry(0x00400004, 'ScheduledProcedureStepEndDate', 'DA', GONE),
    Entry(0x00404005, 'ScheduledProcedureStepStartDateTime', 'DT', GONE),
    Entry(0x00081190, 'RetrieveURL', 'UR', GONE),
    Entry(0x0040A160, 'TextValue', 'UT', GONE),
    # Dates and times
    Entry(0x00080020, 'StudyDate', 'DA', GONE),
    Entry(0x00080021, 'SeriesDate', 'DA', GONE),
    Entry(0x00080022, 'AcquisitionDate', 'DA', GONE),
    Entry(0x00080023, 'ContentDate', 'DA', GONE),
    Entry(0x00080030, 'StudyTime', 'TM', GONE),
    Entry(0x00080031, 'SeriesTime', 'TM', GONE),
    Entry(0x0008002A, 'AcquisitionDateTime', 'DT', GONE),
    Entry(0x00181012, 'DateOfSecondaryCapture', 'DA', GONE),
    # RT-family descriptors, labels, names and operators
    Entry(0x300A0002, 'RTPlanLabel', 'SH', GONE),
    Entry(0x300A0003, 'RTPlanName', 'LO', GONE),
    Entry(0x300A0004, 'RTPlanDescription', 'ST', GONE),
    Entry(0x300A0006, 'RTPlanDate', 'DA', GONE),
    Entry(0x300A0016, 'DoseReferenceDescription', 'LO', GONE),
    Entry(0x300A0072, 'FractionGroupDescription', 'LO', GONE),
    Entry(0x300A00B2, 'TreatmentMachineName', 'SH', GONE),
    Entry(0x300A00C3, 'BeamDescription', 'ST', GONE),
    Entry(0x300A00C2, 'BeamName', 'LO', GONE),
    Entry(0x300E0008, 'ReviewerName', 'PN', GONE),
    Entry(0x30060004, 'StructureSetName', 'LO', GONE),
    Entry(0x30060006, 'StructureSetDescription', 'ST', GONE),
    Entry(0x30060028, 'ROIDescription', 'ST', GONE),
    Entry(0x300600A6, 'ROIInterpreter', 'PN', GONE),
    Entry(0x30060002, 'StructureSetLabel', 'SH', REPLACED),
    # Retained by design (README retention contract)
    Entry(0x0008103E, 'SeriesDescription', 'LO', KEPT),
    Entry(0x00181030, 'ProtocolName', 'LO', KEPT),
    Entry(0x00180024, 'SequenceName', 'SH', KEPT),
    Entry(0x00080070, 'Manufacturer', 'LO', KEPT),
    Entry(0x00181020, 'SoftwareVersions', 'LO', KEPT),
    Entry(0x00180010, 'ContrastBolusAgent', 'LO', KEPT),
    Entry(0x30060026, 'ROIName', 'LO', KEPT),
    Entry(0x30060085, 'ROIObservationLabel', 'SH', KEPT),
    Entry(0x00100040, 'PatientSex', 'CS', KEPT),
    Entry(0x00101010, 'PatientAge', 'AS', KEPT),
    Entry(0x00101020, 'PatientSize', 'DS', KEPT),
    Entry(0x00101030, 'PatientWeight', 'DS', KEPT),
    # UIDs
    Entry(0x0020000D, 'StudyInstanceUID', 'UI', REMAPPED),
    Entry(0x0020000E, 'SeriesInstanceUID', 'UI', REMAPPED),
    Entry(0x00080018, 'SOPInstanceUID', 'UI', REMAPPED),
    Entry(0x00200052, 'FrameOfReferenceUID', 'UI', REMAPPED),
    Entry(0x00200200, 'SynchronizationFrameOfReferenceUID', 'UI', REMAPPED),
    Entry(0x00083010, 'IrradiationEventUID', 'UI', REMAPPED),
    Entry(0x00081155, 'ReferencedSOPInstanceUID', 'UI', REMAPPED),
    Entry(0x00081150, 'ReferencedSOPClassUID', 'UI', KEPT),
    Entry(0x00080016, 'SOPClassUID', 'UI', KEPT),
)

# Elements planted without a dictionary identity. These exercise the "unreadable or
# private content must not survive" classes. VR is what the file would carry.
PRIVATE_BLOCKS = (
    (0x0009, 'PrivateCreatorA', ((0x01, 'LO'), (0x02, 'SH'), (0x03, 'LT'), (0x04, 'UN'))),
    (0x0029, 'PrivateCreatorB', ((0x01, 'LO'), (0x10, 'OB'))),
)
UNKNOWN_PUBLIC_TAG = 0x00089999   # even group, no dictionary entry: carried as UN
CURVE_TAG = 0x50003000            # retired curve data group
OVERLAY_NOTE = 'Overlay groups (60xx) are retained pixel-adjacent content and are not planted.'

# --- Survey classes -------------------------------------------------------------
# Groups of the RT family plus the segmentation, registration and presentation-state
# families where free-text labels and descriptors live.
SURVEY_GROUPS = (0x3002, 0x3004, 0x3006, 0x3008, 0x300A, 0x300C, 0x300E, 0x3010,
                 0x0062, 0x0064, 0x0066, 0x0070)
# VRs that can carry a person's identity or free text.
SURVEY_VRS = ('LO', 'SH', 'UC', 'ST', 'LT', 'UT', 'UR', 'PN', 'AE', 'DA', 'DT', 'TM')
# Of the survey attributes, only these are retained by design: the engine documents
# that ROI labels and observation labels are intentionally kept. Every other survey
# attribute is expected not to survive.
SURVEY_INTENDED_RETAINED = frozenset({0x30060026, 0x30060085})
# StructureSetLabel is replaced by a fixed label, which also satisfies the expectation.
