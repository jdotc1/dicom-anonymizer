"""New host adapters only; accepted portable parser/policy suite is not repeated."""
import errno
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ENGINE = Path(__file__).resolve().parents[1] / 'engine'
sys.path.insert(0, str(ENGINE))
import sidecar_deid as sidecar
spec = importlib.util.spec_from_file_location('sidecar_host', ENGINE / 'engine.py')
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

class SidecarIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / 'source'
        self.patient = self.source / '00001'
        self.patient.mkdir(parents=True)
        self.file = self.patient / 'Private_Patient.json'
        self.file.write_text('{"EchoTime": 0.00300, "PatientName":"Private Patient"}')
        self.output = self.root / 'output'
        self.events = []
        self.scan = patch.object(engine, 'scan', return_value=([], [], 1))
        self.scan.start(); self.addCleanup(self.scan.stop)
        self.audit = patch.object(engine, 'self_audit', return_value={'files_audited':0,'result':'passed'})
        self.audit.start(); self.addCleanup(self.audit.stop)

    def run_batch(self, enabled=True, **kwargs):
        return engine.run(self.source, self.output, lambda event, **values: self.events.append(dict(event=event, **values)), clean_json_sidecars=enabled, **kwargs)

    def assert_not_published(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])
        self.assertNotIn('complete', [e['event'] for e in self.events])

    def test_enabled_batch_uses_generated_names_exact_tokens_audit_report_and_seal(self):
        result = self.run_batch()
        text = (self.output/'00001/Sidecars/Sidecar_000001.json').read_text()
        self.assertIn('0.00300', text)
        self.assertNotIn('Private', text)
        report = json.loads((self.output/'anonymization-report.json').read_text())
        self.assertEqual(report['json_sidecars']['files_audited'], 1)
        self.assertEqual(report['excluded_files'], 0)
        self.assertEqual(result['sidecar_files'], 1)
        self.assertEqual(self.events[0]['sidecar_files'], 1)
        self.assertNotIn('Private', json.dumps(self.events)+json.dumps(report))
        self.assertEqual(self.file.read_text(), '{"EchoTime": 0.00300, "PatientName":"Private Patient"}')
        self.assertEqual(self.events[-1]['event'], 'complete')

    def test_disabled_mode_has_no_sidecar_calls_or_report_event_fields(self):
        with patch.object(engine, '_sidecar_scan', side_effect=AssertionError('unexpected sidecar scan')):
            result=self.run_batch(False)
        report=json.loads((self.output/'anonymization-report.json').read_text())
        self.assertNotIn('json_sidecars', report)
        self.assertNotIn('sidecar_files', result)
        self.assertNotIn('sidecar_files', self.events[0])
        self.assertEqual(result['excluded_files'], 1)
        self.assertFalse((self.output/'00001').exists())

    def test_malformed_or_invalid_known_value_fails_before_staging(self):
        for text in ('{', '{"EchoTime":"Private Patient"}'):
            with self.subTest(text=text):
                self.file.write_text(text)
                with patch.object(engine.tempfile,'mkdtemp', side_effect=AssertionError('allocated staging')):
                    with self.assertRaises(engine.BatchError):self.run_batch()
                self.assert_not_published()

    def test_preflight_size_feeds_allocation_estimate(self):
        records=engine._sidecar_scan(self.source,engine.Cancellation())
        cleaned,_=sidecar.clean_document(sidecar.parse_json_bytes(self.file.read_bytes()),sidecar.MRI_PHYSICAL_V1)
        self.assertEqual(records[0].estimated_output_bytes,len((sidecar.serialize_json(cleaned)+'\n').encode()))
        self.assertGreater(engine.estimate_disk_space([],4096,sidecars=records),engine.estimate_disk_space([],4096))

    def test_space_shortage_includes_sidecars_before_allocation(self):
        with patch.object(engine.shutil,'disk_usage') as disk, patch.object(engine.tempfile,'mkdtemp',side_effect=AssertionError('allocated staging')):
            disk.return_value.free=engine.estimate_disk_space([],4096)
            with patch.object(engine,'allocation_unit',return_value=4096):
                with self.assertRaises(engine.BatchError) as caught:self.run_batch()
        self.assertEqual(caught.exception.output_issue,'space')
        self.assert_not_published()

    def test_write_failure_preserves_destination_recovery_and_cleanup(self):
        with patch.object(sidecar.os,'write',side_effect=OSError(errno.ENOSPC,'/private/sensitive')):
            with self.assertRaises(engine.BatchError) as caught:self.run_batch()
        self.assertEqual(caught.exception.output_issue,'space')
        self.assertNotIn('/private',str(caught.exception))
        self.assert_not_published()

    def test_removed_source_during_processing_is_safe_recovery(self):
        original=sidecar.clean_sidecars_to_staging
        def remove(records,*args,**kwargs):
            self.file.unlink()
            return original(records,*args,**kwargs)
        with patch.object(sidecar,'clean_sidecars_to_staging',side_effect=remove):
            with self.assertRaises(engine.BatchError) as caught:self.run_batch()
        self.assertNotIn(str(self.root),str(caught.exception))
        self.assertIsNone(caught.exception.output_issue)
        self.assert_not_published()

    def test_discovery_walk_error_is_not_silently_ignored(self):
        def walk(*args,**kwargs):
            kwargs['onerror'](PermissionError('/private/sensitive'))
            return iter(())
        with patch.object(sidecar.os,'walk',side_effect=walk):
            with self.assertRaisesRegex(engine.BatchError,'cannot be listed'):self.run_batch()
        self.assert_not_published()

    def test_discovery_cancellation_preserves_cancelled_state(self):
        cancellation=engine.Cancellation();cancellation.requested=True
        with self.assertRaises(engine.BatchError) as caught:self.run_batch(cancellation=cancellation)
        self.assertTrue(caught.exception.cancelled)
        self.assert_not_published()

    def test_audit_failure_prevents_publication_and_cleans(self):
        with patch.object(sidecar,'audit_sidecars',side_effect=sidecar.SidecarError('Synthetic audit failure')):
            with self.assertRaisesRegex(engine.BatchError,'Synthetic audit failure'):self.run_batch()
        self.assert_not_published()

    def test_cancel_during_new_audit_keeps_owned_cleanup(self):
        cancellation=engine.Cancellation()
        with patch.object(sidecar,'audit_sidecars',side_effect=lambda *a,**k:cancellation.cancel()):
            with self.assertRaises(engine.BatchError) as caught:self.run_batch(cancellation=cancellation)
        self.assertTrue(caught.exception.cancelled)
        self.assert_not_published()

    def test_final_seal_blocks_post_audit_change(self):
        original=sidecar.seal_staging_inventory
        def mutate(staging,**kwargs):
            kwargs['sidecar_expectations'][0].output.write_text('{}')
            return original(staging,**kwargs)
        with patch.object(sidecar,'seal_staging_inventory',side_effect=mutate):
            with self.assertRaisesRegex(engine.BatchError,'changed after audit'):self.run_batch()
        self.assert_not_published()

    def test_seal_walk_error_blocks_publication(self):
        original=sidecar.seal_staging_inventory
        def seal(*args,**kwargs):
            def walk(*args,**kwargs):
                kwargs['onerror'](PermissionError(errno.EACCES, '/private/sensitive'))
                return iter(())
            with patch.object(sidecar.os,'walk',side_effect=walk):return original(*args,**kwargs)
        with patch.object(sidecar,'seal_staging_inventory',side_effect=seal):
            with self.assertRaises(engine.BatchError) as caught:self.run_batch()
        self.assertEqual(caught.exception.output_issue, 'permissions')
        self.assertNotIn('/private', str(caught.exception))
        self.assert_not_published()

    def test_enabled_zero_sidecars_is_explicit_and_audited(self):
        self.file.unlink()
        self.run_batch()
        fragment=json.loads((self.output/'anonymization-report.json').read_text())['json_sidecars']
        self.assertTrue(fragment['enabled']);self.assertEqual(fragment['files_audited'],0)

    def test_cli_flag_selects_opt_in_without_changing_legacy_default(self):
        for enabled in (False,True):
            args=['engine','--source',str(self.source),'--scan']+(['--clean-json-sidecars'] if enabled else [])
            with patch.object(sys,'argv',args),patch.object(engine.signal,'signal'),patch.object(engine,'emit') as emit:
                self.assertEqual(engine.main(),0)
            event=emit.call_args.kwargs
            self.assertEqual('sidecar_files' in event,enabled)

    def test_mixed_synthetic_dicom_and_sidecar_share_publication_and_both_audits(self):
        # New end-to-end seam case, not a repeat of an accepted DICOM-only suite.
        self.scan.stop(); self.audit.stop()
        from pydicom.dataset import FileDataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid
        meta=FileMetaDataset();meta.TransferSyntaxUID=ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID=MRImageStorage;meta.MediaStorageSOPInstanceUID=generate_uid()
        path=self.patient/'synthetic.dcm'
        ds=FileDataset(str(path),{},file_meta=meta,preamble=bytes(128))
        ds.SOPClassUID=MRImageStorage;ds.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
        ds.StudyInstanceUID=generate_uid();ds.SeriesInstanceUID=generate_uid();ds.FrameOfReferenceUID=generate_uid()
        ds.Modality='MR';ds.PatientName='Synthetic^Person';ds.PatientID='synthetic-id'
        ds.Rows=1;ds.Columns=1;ds.SamplesPerPixel=1;ds.PhotometricInterpretation='MONOCHROME2'
        ds.BitsAllocated=16;ds.BitsStored=16;ds.HighBit=15;ds.PixelRepresentation=0;ds.PixelData=bytes(2)
        ds.save_as(path,enforce_file_format=True)
        result=self.run_batch()
        self.assertEqual((result['processed'],result['audited_files'],result['sidecar_files'],result['sidecar_audited_files']),(1,1,1,1))
        self.assertEqual(len(list(self.output.rglob('*.dcm'))),1)
        self.assertEqual(len(list(self.output.rglob('*.json'))),2)
        report=json.loads((self.output/'anonymization-report.json').read_text())
        self.assertEqual(report['self_audit']['result'],'passed')
        names=[event['event'] for event in self.events]
        self.assertLess(names.index('sidecar_progress'),names.index('audit_progress'))
        self.assertLess(names.index('audit_progress'),names.index('sidecar_audit_progress'))
        self.assertEqual(names[-1],'complete')

    def test_inventory_seal_rejects_symlink_root_even_without_sidecars(self):
        outside=self.root/'outside';outside.mkdir()
        root_link=self.root/'root-link';root_link.symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(sidecar.SidecarError,'staging directory'):
            sidecar.seal_staging_inventory(root_link,dicom_paths=[],sidecar_paths=[],report_path=None)

if __name__=='__main__':unittest.main()
