#!/usr/bin/env python3
"""Generate six entirely synthetic MR/CT/RTSTRUCT objects for two fictional patients.

Reads no input files. Minimal metadata/geometry fixtures, not clinical images or a
claim of complete IOD conformance. Never writes into an existing destination.
"""
import argparse
from pathlib import Path
import struct
import uuid

from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, MRImageStorage, RTStructureSetStorage


def uid(label):
    return '2.25.' + str(uuid.uuid5(uuid.NAMESPACE_URL, 'dicom-anonymizer-synthetic/' + label).int)


def base(patient, name, modality, sop_class):
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = sop_class
    meta.MediaStorageSOPInstanceUID = uid(patient + '/' + modality + '/instance')
    ds = FileDataset(None, {}, file_meta=meta, preamble=b'\0' * 128)
    ds.SOPClassUID = sop_class; ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = uid(patient + '/study')
    ds.SeriesInstanceUID = uid(patient + '/' + modality + '/series')
    ds.FrameOfReferenceUID = uid(patient + '/frame')
    ds.Modality = modality; ds.PatientName = name; ds.PatientID = 'SYNTHETIC-' + patient
    ds.StudyDate = '20000101'; ds.PatientBirthDate = '19700101'
    ds.StudyDescription = 'SYNTHETIC ONLY - example identification text'
    ds.Manufacturer = 'Synthetic Device'; ds.SoftwareVersions = 'Example 1.0'
    ds.SeriesNumber = {'MR': 1, 'CT': 2, 'RTSTRUCT': 3}[modality]
    ds.InstanceNumber = 1
    return ds


def image(patient, name, modality):
    ds = base(patient, name, modality, MRImageStorage if modality == 'MR' else CTImageStorage)
    ds.SeriesDescription = 'Synthetic ' + modality + ' sequence'
    ds.ProtocolName = 'Synthetic metadata demonstration'; ds.SequenceName = 'SYNTHETIC'
    ds.ContrastBolusAgent = 'Synthetic agent'
    ds.Rows = 2; ds.Columns = 2; ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = 'MONOCHROME2'
    ds.BitsAllocated = 16; ds.BitsStored = 16; ds.HighBit = 15; ds.PixelRepresentation = 0
    ds.PixelSpacing = [1, 1]; ds.SliceThickness = 1
    ds.ImagePositionPatient = [0, 0, 0]; ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.PixelData = struct.pack('<4H', 0, 100, 200, 300)
    ds.BurnedInAnnotation = 'NO'
    ds.add_new((0x0011, 0x0010), 'LO', 'SYNTHETIC PRIVATE CREATOR')
    ds.add_new((0x0011, 0x1001), 'LO', 'SYNTHETIC REMOVE ME')
    return ds


def structure(patient, name, ct):
    ds = base(patient, name, 'RTSTRUCT', RTStructureSetStorage)
    ds.SeriesDescription = 'Synthetic contours'
    ds.StructureSetLabel = 'SYNTHETIC'; ds.StructureSetName = 'Synthetic demonstration'
    frame = Dataset(); frame.FrameOfReferenceUID = ct.FrameOfReferenceUID
    study = Dataset(); study.ReferencedSOPClassUID = '1.2.840.10008.3.1.2.3.1'
    study.ReferencedSOPInstanceUID = ct.StudyInstanceUID
    series = Dataset(); series.SeriesInstanceUID = ct.SeriesInstanceUID
    reference = Dataset(); reference.ReferencedSOPClassUID = CTImageStorage
    reference.ReferencedSOPInstanceUID = ct.SOPInstanceUID
    series.ContourImageSequence = Sequence([reference])
    study.RTReferencedSeriesSequence = Sequence([series])
    frame.RTReferencedStudySequence = Sequence([study])
    ds.ReferencedFrameOfReferenceSequence = Sequence([frame])
    roi = Dataset(); roi.ROINumber = 1; roi.ROIName = 'Synthetic ROI'
    roi.ReferencedFrameOfReferenceUID = ct.FrameOfReferenceUID; roi.ROIGenerationAlgorithm = 'MANUAL'
    ds.StructureSetROISequence = Sequence([roi])
    contour = Dataset(); contour.ContourGeometricType = 'CLOSED_PLANAR'; contour.NumberOfContourPoints = 4
    contour.ContourData = [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0]
    contour.ContourImageSequence = Sequence([reference])
    roi_contour = Dataset(); roi_contour.ReferencedROINumber = 1
    roi_contour.ContourSequence = Sequence([contour])
    ds.ROIContourSequence = Sequence([roi_contour])
    return ds


def generate(destination):
    destination.mkdir(parents=True, exist_ok=False)
    for patient, name in [('00001', 'SYNTHETIC^ALPHA'), ('00002', 'SYNTHETIC^BETA')]:
        folder = destination / patient; folder.mkdir()
        mr = image(patient, name, 'MR'); ct = image(patient, name, 'CT')
        rt = structure(patient, name, ct)
        for label, ds in [('mr', mr), ('ct', ct), ('rtstruct', rt)]:
            ds.save_as(folder / (label + '.dcm'), enforce_file_format=True)
    print('Created two fictional patients and six synthetic DICOM objects.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    generate(args.destination)
