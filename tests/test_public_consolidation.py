"""Conflict-recovery coverage for the public batch-processing interface."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from test_engine import engine, make_dicom

class PublicConsolidationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'))
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.source=self.root/'input';self.source.mkdir()
        self.destination=self.root/'output'
        self.events=[]

    def add(self,folder,identity='synthetic-source',name='Synthetic^Person'):
        path=self.source/folder/'Synthetic_Person_12345678.dcm'
        ds=make_dicom(path,identity=identity)
        ds.PatientName=name;ds.save_as(path,enforce_file_format=True)
        (path.parent/'Synthetic_Person.json').write_text('{"EchoTime":0.00500,"PatientID":"synthetic-source"}')

    def test_shared_source_patient_id_blocks_sidecar_batch_before_staging(self):
        self.add('00001');self.add('00002')
        with patch.object(engine.tempfile,'mkdtemp',side_effect=AssertionError('staging allocated')):
            with self.assertRaises(engine.BatchError) as caught:
                engine.run(self.source,self.destination,lambda event,**values:self.events.append(dict(event=event,**values)),clean_json_sidecars=True)
        message=str(caught.exception)
        self.assertIn('00001',message);self.assertIn('00002',message);self.assertIn('To fix:',message)
        self.assertNotIn('Synthetic',message);self.assertNotIn('synthetic-source',message);self.assertNotIn(str(self.root),message)
        self.assertFalse(self.destination.exists())
        self.assertNotIn('complete',[item['event'] for item in self.events])

    def test_public_cli_exposes_safe_detailed_conflict_with_sidecars_enabled(self):
        self.add('00001');self.add('00002')
        with patch.object(sys,'argv',['engine','--source',str(self.source),'--scan','--clean-json-sidecars']),patch.object(engine.signal,'signal'),patch.object(engine,'emit') as emit:
            self.assertEqual(engine.main(),1)
        self.assertEqual(emit.call_args.args[0],'error')
        message=emit.call_args.kwargs['message']
        self.assertIn('To fix:',message)
        self.assertNotIn('Synthetic',message);self.assertNotIn(str(self.source),message)
        self.assertNotIn('sidecar_files',emit.call_args.kwargs)

    def test_distinct_patients_keep_numeric_folders_and_json_counts(self):
        self.add('00001','first-source','First^Synthetic')
        self.add('00002','second-source','Second^Synthetic')
        result=engine.run(self.source,self.destination,lambda event,**values:self.events.append(dict(event=event,**values)),clean_json_sidecars=True)
        self.assertEqual((result['patients'],result['processed'],result['audited_files'],result['sidecar_files'],result['sidecar_audited_files']),(2,2,2,2,2))
        self.assertEqual({p.name for p in self.destination.iterdir() if p.is_dir()},{'00001','00002'})
        self.assertEqual(len(list(self.destination.glob('*/Sidecars/Sidecar_000001.json'))),2)
        report=json.loads((self.destination/'anonymization-report.json').read_text())
        self.assertEqual(report['json_sidecars']['files_audited'],2)
        self.assertEqual(result['excluded_files'],0)
        self.assertEqual(self.events[-1]['event'],'complete')

    def test_dicom_only_mode_uses_ported_recovery_without_sidecar_import(self):
        self.add('00001');self.add('00002')
        with patch.object(engine,'_sidecar_scan',side_effect=AssertionError('sidecar called')):
            with self.assertRaisesRegex(engine.BatchError,'To fix:'):
                engine.run(self.source,self.destination,progress=lambda *a,**k:None)
        self.assertFalse(self.destination.exists())

if __name__=='__main__':unittest.main()
