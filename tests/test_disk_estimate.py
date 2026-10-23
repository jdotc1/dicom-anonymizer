"""Changed estimate boundaries only; no anonymization, policy audit, or real data."""
import errno
from copy import deepcopy
from io import BytesIO
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence

spec=importlib.util.spec_from_file_location('estimate_engine',Path(__file__).resolve().parents[1]/'engine/engine.py')
engine=importlib.util.module_from_spec(spec);sys.modules[spec.name]=engine;spec.loader.exec_module(engine)


def dataset():
    ds=Dataset();ds.file_meta=FileMetaDataset();ds.file_meta.TransferSyntaxUID='1.2.840.10008.1.2.1'
    return ds


def record(size,estimate=None,patient='001',series=('study','series')):
    return engine.Record(Path('/synthetic/not-opened'),patient,series,'1.2.3','001',(0,0,size,0),estimate)


class DiskEstimateTests(unittest.TestCase):
    def test_large_pixel_payload_does_not_pay_ten_percent(self):
        ds=dataset();size=4*1024**3
        with patch.object(engine,'clean',side_effect=AssertionError('No cleaning for estimates')), patch.object(engine,'checked_read',side_effect=AssertionError('No reread')):
            estimate=engine.estimate_output_bytes(ds,size)
        self.assertEqual(estimate,size+4096)
        self.assertLess(estimate,(size*11)//10)

    def test_nested_uid_and_multivalue_growth_with_whole_element_padding(self):
        ds=dataset();ds.StudyInstanceUID='1.2.3'
        child=Dataset();child.add_new(0x00081158,'UI',['1.2','1.2.345'])
        ds.ReferencedStudySequence=Sequence([child])
        # scalar:64-6=58; VM:130-(3+1+7 padded to12)=118
        self.assertEqual(engine.estimate_output_bytes(ds,1000),1000+4096+58+118)

    def test_preserved_class_uids_are_conservatively_counted(self):
        ds=dataset();ds.SOPClassUID='1.2.3'
        self.assertEqual(engine.estimate_output_bytes(ds,100),100+4096+58)

    def test_full_length_uids_do_not_gain_bytes(self):
        ds=dataset();ds.StudyInstanceUID='1.'+'2'*62
        self.assertEqual(engine.estimate_output_bytes(ds,100),4196)

    def test_dataset_and_pixel_payload_are_not_mutated_or_serialized(self):
        ds=dataset();ds.PatientName='Original';ds.StudyInstanceUID='1.2.3';ds.PixelData=b'original pixels'
        before=repr(ds)
        with patch.object(Dataset,'save_as',side_effect=AssertionError('No trial write')),patch.object(engine,'generate_uid',side_effect=AssertionError('No UID generation')):
            engine.estimate_output_bytes(ds,1000)
        self.assertEqual(repr(ds),before);self.assertEqual(ds.PixelData,b'original pixels')

    def test_deflated_and_unknown_transfer_keep_percentage_cushion(self):
        ds=dataset();ds.file_meta.TransferSyntaxUID=engine.DEFLATED_TRANSFER_SYNTAX
        self.assertEqual(engine.estimate_output_bytes(ds,101),112+4096)
        ds.file_meta=FileMetaDataset()
        self.assertEqual(engine.estimate_output_bytes(ds,101),112+4096)

    def test_integer_math_above_float_precision(self):
        size=2**56+3
        ds=dataset();ds.file_meta.TransferSyntaxUID=engine.DEFLATED_TRANSFER_SYNTAX
        self.assertEqual(engine.estimate_output_bytes(ds,size),(size*11+9)//10+4096)

    def test_additive_estimate_covers_new_synthetic_encoded_variants(self):
        # New generated datasets only: no engine clean(), validation or audit.
        for transfer in ('1.2.840.10008.1.2', '1.2.840.10008.1.2.1', engine.DEFLATED_TRANSFER_SYNTAX):
            with self.subTest(transfer=transfer):
                meta=FileMetaDataset();meta.TransferSyntaxUID=transfer
                meta.MediaStorageSOPClassUID='1.2.840.10008.5.1.4.1.1.4';meta.MediaStorageSOPInstanceUID='1.2.3'
                ds=FileDataset(None,{},file_meta=meta,preamble=b'\0'*128)
                ds.SOPClassUID=meta.MediaStorageSOPClassUID;ds.SOPInstanceUID='1.2.3'
                ds.PatientName='Source';ds.PatientID='1'
                items=[]
                for index in range(100):
                    item=Dataset();item.ReferencedSOPInstanceUID='1.2.'+str(index+1);items.append(item)
                ds.ReferencedImageSequence=Sequence(items)
                ds.add_new(0x7FE00010,'OB', b'x'*(1024*1024))
                original=BytesIO();ds.save_as(original,enforce_file_format=True)
                estimated=engine.estimate_output_bytes(ds,len(original.getvalue()))
                output=deepcopy(ds)
                for index,element in enumerate(output.iterall()):
                    if element.VR=='UI' and 'SOPClassUID' not in element.keyword:
                        element.value='2.25.'+str(10**58+index)
                output.PatientName='9'*64;output.PatientID='9'*64
                output.PatientIdentityRemoved='YES'
                output.DeidentificationMethod='Local bulk metadata pseudonymization v2; review retained content'
                output.file_meta.MediaStorageSOPInstanceUID=output.SOPInstanceUID
                encoded=BytesIO();output.save_as(encoded,enforce_file_format=True)
                self.assertGreaterEqual(estimated,len(encoded.getvalue()))

    def test_repeated_nested_replacements_have_per_element_growth(self):
        ds=dataset();items=[]
        for _ in range(100):
            item=Dataset();item.PatientName='';item.PatientID='';item.StructureSetLabel=''
            items.append(item)
        ds.ReferencedStudySequence=Sequence(items)
        self.assertEqual(engine.estimate_output_bytes(ds,1000,'9'*64),1000+4096+100*(64+64+10))

    def test_actual_patient_length_and_original_text_lower_bound(self):
        ds=dataset();ds.PatientName='é';ds.PatientID='1';ds.StructureSetLabel='A'
        # Both original identifiers pad to2; target001 pads to4. Label2 grows to10.
        self.assertEqual(engine.estimate_output_bytes(ds,1000,'001'),1000+4096+2+2+8)

    def test_longer_existing_replacement_fields_are_not_subtracted(self):
        ds=dataset();ds.PatientName='Original^Longer';ds.PatientID='123456';ds.StructureSetLabel='LongerStructures'
        self.assertEqual(engine.estimate_output_bytes(ds,1000,'1'),1000+4096)

    def test_destination_fragment_size_preferred(self):
        with patch.object(engine.os,'statvfs',return_value=NS(f_frsize=65536,f_bsize=4096)):
            self.assertEqual(engine.allocation_unit('/synthetic'),65536)

    def test_destination_block_size_fallback(self):
        with patch.object(engine.os,'statvfs',return_value=NS(f_frsize=0,f_bsize=8192)):
            self.assertEqual(engine.allocation_unit('/synthetic'),8192)

    def test_unavailable_or_invalid_geometry_uses_documented_fallback(self):
        for outcome in [NS(f_frsize=-1,f_bsize=0),OSError(errno.EIO,'synthetic'),NotImplementedError()]:
            with patch.object(engine.os,'statvfs',**({'side_effect':outcome} if isinstance(outcome,Exception) else {'return_value':outcome})):
                self.assertEqual(engine.allocation_unit('/synthetic'),4096)

    def test_per_file_allocation_and_folder_report_allowances(self):
        # Two files:2*4096; root+patient+series:3*4096; entries:4096; report:69632.
        self.assertEqual(engine.estimate_disk_space([record(1,1),record(1,1)],4096),engine.DISK_MARGIN_BYTES+94208)

    def test_different_series_and_patients_add_directory_cost(self):
        same=engine.estimate_disk_space([record(1,1),record(1,1)],4096)
        series=engine.estimate_disk_space([record(1,1),record(1,1,series=('study','second'))],4096)
        patients=engine.estimate_disk_space([record(1,1),record(1,1,patient='002')],4096)
        self.assertEqual(series-same,4096);self.assertEqual(patients-same,8192)

    def test_many_tiny_files_cost_more_on_larger_allocation_units(self):
        records=[record(1,4097) for _ in range(1000)]
        small=engine.estimate_disk_space(records,4096);large=engine.estimate_disk_space(records,65536)
        self.assertGreater(large-small,50*1024**2)

    def test_legacy_records_use_conservative_fallback(self):
        r=record(1000)
        self.assertIsNone(r.estimated_output_bytes)
        self.assertEqual(engine.estimate_disk_space([r],4096),engine.DISK_MARGIN_BYTES+94208)

    def test_missing_invalid_and_undersized_estimates_cannot_discount_source(self):
        expected=engine.estimate_disk_space([record(1000)],4096)
        for value in [False,-1,999,1.5]:
            self.assertEqual(engine.estimate_disk_space([record(1000,value)],4096),expected)
        r=NS(signature=(0,0,1000,0))
        self.assertEqual(engine.estimate_disk_space([r],4096),expected)

    def test_empty_record_budget_retains_margin_report_and_staging_folder(self):
        self.assertEqual(engine.estimate_disk_space([],4096),engine.DISK_MARGIN_BYTES+73728)

    def test_shortage_uses_new_estimate_in_existing_safe_error(self):
        records=[record(1000,5096)];expected=engine.DISK_MARGIN_BYTES+94208
        with patch.object(engine,'allocation_unit',return_value=4096),patch.object(engine.shutil,'disk_usage',return_value=NS(free=expected-1)):
            with self.assertRaises(engine.BatchError) as failure:engine.check_disk_space(records,'/synthetic')
        error=failure.exception
        self.assertEqual(error.required_bytes,expected);self.assertEqual(error.available_bytes,expected-1)
        self.assertEqual(error.output_issue,'space');self.assertIn('not a guarantee',str(error))

    def test_exact_available_budget_passes(self):
        records=[record(1000,5096)];expected=engine.DISK_MARGIN_BYTES+94208
        with patch.object(engine,'allocation_unit',return_value=4096),patch.object(engine.shutil,'disk_usage',return_value=NS(free=expected)):
            self.assertEqual(engine.check_disk_space(records,'/synthetic'),expected)

    def test_space_lookup_errors_keep_destination_classification(self):
        with patch.object(engine,'allocation_unit',return_value=4096),patch.object(engine.shutil,'disk_usage',side_effect=OSError(errno.EACCES,'/private/not-disclosed')):
            with self.assertRaises(engine.BatchError) as failure:engine.check_disk_space([], '/synthetic')
        self.assertEqual(failure.exception.output_issue,'permissions');self.assertNotIn('/private',str(failure.exception))


if __name__=='__main__': unittest.main()
