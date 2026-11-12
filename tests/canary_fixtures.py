"""Minimal synthetic builders for the RT family, Segmentation, Registration and PT (test support only).

Each builder returns an in-memory pydicom Dataset with a faithful UID chain: its own SOP
instance, the shared study, its series, the frame of reference, and the references the
real IOD carries to the other objects. A builder never touches disk and carries no
patient data. build_chain() assembles one patient's set and returns, next to the
datasets, a list of reference specs the chain test resolves after cleaning:

    Ref(owner, path, target)   path = attribute names / item indexes inside the owner
    target = ('sop', key) | ('series', key) | ('study',) | ('frame', name) | ('external', label)
"""
import hashlib
from collections import namedtuple

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import (CTImageStorage, ExplicitVRLittleEndian, PositronEmissionTomographyImageStorage,
                         RTBeamsTreatmentRecordStorage, RTDoseStorage, RTImageStorage, RTPlanStorage,
                         RTStructureSetStorage, SegmentationStorage, SpatialRegistrationStorage)

Ref = namedtuple('Ref', 'owner path target')
Chain = namedtuple('Chain', 'datasets refs external')

ROOT = '2.25.4242424242'   # fixed root so the synthetic chain is reproducible


def uid(*parts):
    """Deterministic, valid numeric UID for a named part (names are hashed to digit components)."""
    digits = [str(int.from_bytes(hashlib.sha256(str(p).encode()).digest()[:6], 'big') + 1) for p in parts]
    return ROOT + '.' + '.'.join(digits)


def item(**values):
    out = Dataset()
    for name, value in values.items():
        setattr(out, name, value)
    return out


def seq(*items):
    return Sequence(list(items))


def base(sop_class, modality, sop, series, study, frame, label):
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = sop_class
    ds.file_meta.MediaStorageSOPInstanceUID = sop
    ds.SOPClassUID, ds.SOPInstanceUID = sop_class, sop
    ds.StudyInstanceUID, ds.SeriesInstanceUID = study, series
    if frame:
        ds.FrameOfReferenceUID = frame
    ds.Modality = modality
    ds.PatientName = 'Synthetic^Source'
    ds.PatientID = 'SRC-' + label
    ds.SeriesDescription = 'synthetic ' + label
    return ds


def ref_item(sop_class, sop):
    return item(ReferencedSOPClassUID=sop_class, ReferencedSOPInstanceUID=sop)


def build_image(kind, sop, series, study, frame, modality, sop_class):
    return base(sop_class, modality, sop, series, study, frame, kind)


def build_rtstruct(sop, series, study, frame, ct_series, ct_sops):
    ds = base(RTStructureSetStorage, 'RTSTRUCT', sop, series, study, frame, 'rtstruct')
    ds.StructureSetLabel = 'SRC-LABEL'
    contour_images = [ref_item(CTImageStorage, s) for s in ct_sops]
    series_item = item(SeriesInstanceUID=ct_series, ContourImageSequence=seq(*contour_images))
    study_item = item(ReferencedSOPClassUID='1.2.840.10008.3.1.2.3.2', ReferencedSOPInstanceUID=study,
                      RTReferencedSeriesSequence=seq(series_item))
    ds.ReferencedFrameOfReferenceSequence = seq(item(FrameOfReferenceUID=frame, RTReferencedStudySequence=seq(study_item)))
    ds.StructureSetROISequence = seq(item(ROINumber=1, ROIName='Target', ReferencedFrameOfReferenceUID=frame))
    return ds


def build_rtplan(sop, series, study, frame, rtstruct_sop, dose_sop, prior_plan_sop):
    ds = base(RTPlanStorage, 'RTPLAN', sop, series, study, frame, 'rtplan')
    ds.RTPlanLabel = 'SRC-PLAN'
    ds.ReferencedStructureSetSequence = seq(ref_item(RTStructureSetStorage, rtstruct_sop))
    ds.ReferencedDoseSequence = seq(ref_item(RTDoseStorage, dose_sop))
    ds.ReferencedRTPlanSequence = seq(item(ReferencedSOPClassUID=RTPlanStorage, ReferencedSOPInstanceUID=prior_plan_sop,
                                          RTPlanRelationship='PREDECESSOR'))
    return ds


def build_rtdose(sop, series, study, frame, plan_sop, rtstruct_sop):
    ds = base(RTDoseStorage, 'RTDOSE', sop, series, study, frame, 'rtdose')
    ds.ReferencedRTPlanSequence = seq(ref_item(RTPlanStorage, plan_sop))
    ds.ReferencedStructureSetSequence = seq(ref_item(RTStructureSetStorage, rtstruct_sop))
    return ds


def build_rtimage(sop, series, study, frame, plan_sop, ct_sop, external_image_sop):
    ds = base(RTImageStorage, 'RTIMAGE', sop, series, study, frame, 'rtimage')
    ds.ReferencedRTPlanSequence = seq(ref_item(RTPlanStorage, plan_sop))
    ds.ReferencedImageSequence = seq(ref_item(CTImageStorage, ct_sop), ref_item(CTImageStorage, external_image_sop))
    return ds


def build_treatment_record(sop, series, study, frame, plan_sop, dose_sop, external_record_sop):
    ds = base(RTBeamsTreatmentRecordStorage, 'RTRECORD', sop, series, study, frame, 'record')
    ds.ReferencedRTPlanSequence = seq(ref_item(RTPlanStorage, plan_sop))
    ds.ReferencedDoseSequence = seq(ref_item(RTDoseStorage, dose_sop))
    ds.ReferencedTreatmentRecordSequence = seq(ref_item(RTBeamsTreatmentRecordStorage, external_record_sop))
    return ds


def build_registration(sop, series, study, fixed_frame, moving_frame, ct_series, ct_sop, pt_series, pt_sop):
    ds = base(SpatialRegistrationStorage, 'REG', sop, series, study, fixed_frame, 'registration')
    ds.RegistrationSequence = seq(
        item(FrameOfReferenceUID=fixed_frame),
        item(FrameOfReferenceUID=moving_frame))
    ds.ReferencedSeriesSequence = seq(
        item(SeriesInstanceUID=ct_series, ReferencedInstanceSequence=seq(ref_item(CTImageStorage, ct_sop))),
        item(SeriesInstanceUID=pt_series,
             ReferencedInstanceSequence=seq(ref_item(PositronEmissionTomographyImageStorage, pt_sop))))
    return ds


def build_segmentation(sop, series, study, frame, ct_series, ct_sop, external_series, external_sop):
    ds = base(SegmentationStorage, 'SEG', sop, series, study, frame, 'segmentation')
    ds.ReferencedSeriesSequence = seq(
        item(SeriesInstanceUID=ct_series, ReferencedInstanceSequence=seq(ref_item(CTImageStorage, ct_sop))),
        item(SeriesInstanceUID=external_series, ReferencedInstanceSequence=seq(ref_item(CTImageStorage, external_sop))))
    return ds


def build_pt(sop, series, study, frame, ct_sop, external_sop):
    ds = base(PositronEmissionTomographyImageStorage, 'PT', sop, series, study, frame, 'pt')
    ds.ReferencedImageSequence = seq(ref_item(CTImageStorage, ct_sop), ref_item(CTImageStorage, external_sop))
    return ds


def build_chain():
    """One patient: two CT slices, RTSTRUCT, RTPLAN, RTDOSE, RTIMAGE, treatment record, REG, SEG and PT."""
    study = uid('study')
    frame_a, frame_b = uid('frame', 'a'), uid('frame', 'b')
    s = {n: uid('series', n) for n in ('ct', 'rtstruct', 'plan', 'dose', 'rtimage', 'record', 'reg', 'seg', 'pt')}
    i = {n: uid('sop', n) for n in ('ct1', 'ct2', 'rtstruct', 'plan', 'dose', 'rtimage', 'record', 'reg', 'seg', 'pt')}
    external = {
        'prior_plan': uid('outside', 'plan'),
        'outside_image': uid('outside', 'image'),
        'outside_record': uid('outside', 'record'),
        'outside_series': uid('outside', 'series'),
        'outside_pt_ref': uid('outside', 'ptref'),
    }
    datasets = {
        'ct1': build_image('ct1', i['ct1'], s['ct'], study, frame_a, 'CT', CTImageStorage),
        'ct2': build_image('ct2', i['ct2'], s['ct'], study, frame_a, 'CT', CTImageStorage),
        'rtstruct': build_rtstruct(i['rtstruct'], s['rtstruct'], study, frame_a, s['ct'], [i['ct1'], i['ct2']]),
        'plan': build_rtplan(i['plan'], s['plan'], study, frame_a, i['rtstruct'], i['dose'], external['prior_plan']),
        'dose': build_rtdose(i['dose'], s['dose'], study, frame_a, i['plan'], i['rtstruct']),
        'rtimage': build_rtimage(i['rtimage'], s['rtimage'], study, frame_a, i['plan'], i['ct1'], external['outside_image']),
        'record': build_treatment_record(i['record'], s['record'], study, frame_a, i['plan'], i['dose'], external['outside_record']),
        'reg': build_registration(i['reg'], s['reg'], study, frame_a, frame_b, s['ct'], i['ct1'], s['pt'], i['pt']),
        'seg': build_segmentation(i['seg'], s['seg'], study, frame_a, s['ct'], i['ct1'], external['outside_series'], external['outside_image']),
        'pt': build_pt(i['pt'], s['pt'], study, frame_b, i['ct2'], external['outside_pt_ref']),
    }
    sop = lambda k: ('sop', k)
    series = lambda k: ('series', k)
    R = Ref
    refs = [
        # RTSTRUCT: frame -> study -> series -> contour images
        R('rtstruct', ('ReferencedFrameOfReferenceSequence', 0, 'FrameOfReferenceUID'), ('frame', 'a')),
        R('rtstruct', ('ReferencedFrameOfReferenceSequence', 0, 'RTReferencedStudySequence', 0, 'ReferencedSOPInstanceUID'), ('study',)),
        R('rtstruct', ('ReferencedFrameOfReferenceSequence', 0, 'RTReferencedStudySequence', 0, 'RTReferencedSeriesSequence', 0, 'SeriesInstanceUID'), series('ct')),
        R('rtstruct', ('ReferencedFrameOfReferenceSequence', 0, 'RTReferencedStudySequence', 0, 'RTReferencedSeriesSequence', 0, 'ContourImageSequence', 0, 'ReferencedSOPInstanceUID'), sop('ct1')),
        R('rtstruct', ('ReferencedFrameOfReferenceSequence', 0, 'RTReferencedStudySequence', 0, 'RTReferencedSeriesSequence', 0, 'ContourImageSequence', 1, 'ReferencedSOPInstanceUID'), sop('ct2')),
        R('rtstruct', ('StructureSetROISequence', 0, 'ReferencedFrameOfReferenceUID'), ('frame', 'a')),
        # RTPLAN
        R('plan', ('ReferencedStructureSetSequence', 0, 'ReferencedSOPInstanceUID'), sop('rtstruct')),
        R('plan', ('ReferencedDoseSequence', 0, 'ReferencedSOPInstanceUID'), sop('dose')),
        R('plan', ('ReferencedRTPlanSequence', 0, 'ReferencedSOPInstanceUID'), ('external', 'prior_plan')),
        # RTDOSE
        R('dose', ('ReferencedRTPlanSequence', 0, 'ReferencedSOPInstanceUID'), sop('plan')),
        R('dose', ('ReferencedStructureSetSequence', 0, 'ReferencedSOPInstanceUID'), sop('rtstruct')),
        # RTIMAGE
        R('rtimage', ('ReferencedRTPlanSequence', 0, 'ReferencedSOPInstanceUID'), sop('plan')),
        R('rtimage', ('ReferencedImageSequence', 0, 'ReferencedSOPInstanceUID'), sop('ct1')),
        R('rtimage', ('ReferencedImageSequence', 1, 'ReferencedSOPInstanceUID'), ('external', 'outside_image')),
        # treatment record
        R('record', ('ReferencedRTPlanSequence', 0, 'ReferencedSOPInstanceUID'), sop('plan')),
        R('record', ('ReferencedDoseSequence', 0, 'ReferencedSOPInstanceUID'), sop('dose')),
        R('record', ('ReferencedTreatmentRecordSequence', 0, 'ReferencedSOPInstanceUID'), ('external', 'outside_record')),
        # registration
        R('reg', ('RegistrationSequence', 0, 'FrameOfReferenceUID'), ('frame', 'a')),
        R('reg', ('RegistrationSequence', 1, 'FrameOfReferenceUID'), ('frame', 'b')),
        R('reg', ('ReferencedSeriesSequence', 0, 'SeriesInstanceUID'), series('ct')),
        R('reg', ('ReferencedSeriesSequence', 0, 'ReferencedInstanceSequence', 0, 'ReferencedSOPInstanceUID'), sop('ct1')),
        R('reg', ('ReferencedSeriesSequence', 1, 'SeriesInstanceUID'), series('pt')),
        R('reg', ('ReferencedSeriesSequence', 1, 'ReferencedInstanceSequence', 0, 'ReferencedSOPInstanceUID'), sop('pt')),
        # segmentation (second referenced series and its image are outside the batch; the image UID is also shared with RTIMAGE)
        R('seg', ('ReferencedSeriesSequence', 0, 'SeriesInstanceUID'), series('ct')),
        R('seg', ('ReferencedSeriesSequence', 0, 'ReferencedInstanceSequence', 0, 'ReferencedSOPInstanceUID'), sop('ct1')),
        R('seg', ('ReferencedSeriesSequence', 1, 'SeriesInstanceUID'), ('external', 'outside_series')),
        R('seg', ('ReferencedSeriesSequence', 1, 'ReferencedInstanceSequence', 0, 'ReferencedSOPInstanceUID'), ('external', 'outside_image')),
        # PT
        R('pt', ('ReferencedImageSequence', 0, 'ReferencedSOPInstanceUID'), sop('ct2')),
        R('pt', ('ReferencedImageSequence', 1, 'ReferencedSOPInstanceUID'), ('external', 'outside_pt_ref')),
    ]
    return Chain(datasets, refs, external)


def resolve(ds, path):
    """Follow attribute names and item indexes; return the value at the end of the path."""
    value = ds
    for step in path:
        value = value[step] if isinstance(step, int) else getattr(value, step)
    return value
