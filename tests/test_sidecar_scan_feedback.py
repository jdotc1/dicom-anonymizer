"""Only new sidecar scan telemetry; no accepted policy or corpus suite reruns."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_sidecar_integration as base
engine, sidecar = base.engine, base.sidecar

class SidecarScanFeedbackTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'));self.addCleanup(tmp.cleanup)
        self.source=Path(tmp.name)/'input';(self.source/'00001/nested').mkdir(parents=True)
        (self.source/'00001/a.json').write_text('{"EchoTime":0.003}')
        (self.source/'00001/nested/b.JSON').write_text('{"EchoTime":0.004}')
        (self.source/'00001/nested/ignored.txt').write_text('ignored')
        self.events=[]
    def progress(self,name,**values):self.events.append(dict(event=name,**values))
    def test_initial_and_final_counts_do_not_invent_total(self):
        with patch.object(sidecar.time,'monotonic',return_value=0):records=sidecar.scan_sidecars(self.source,progress=self.progress)
        self.assertEqual(len(records),2)
        self.assertEqual(self.events,[{'event':'sidecar_scan_progress','files_examined':0,'folders_examined':0},{'event':'sidecar_scan_progress','files_examined':2,'folders_examined':2}])
    def test_intermediate_counts_are_throttled_and_monotonic(self):
        clock=iter([x*0.03 for x in range(100)])
        with patch.object(sidecar.time,'monotonic',side_effect=lambda:next(clock)):sidecar.scan_sidecars(self.source,progress=self.progress)
        self.assertLess(len(self.events),7)
        counts=[(e['files_examined'],e['folders_examined']) for e in self.events]
        self.assertEqual(counts,sorted(counts));self.assertEqual(counts[-1],(2,2))
    def test_no_callback_preserves_silent_helper(self):
        with patch.object(engine,'emit') as emit:sidecar.scan_sidecars(self.source)
        emit.assert_not_called()
    def test_host_scan_wrapper_forwards_progress(self):
        records=engine._sidecar_scan(self.source,engine.Cancellation(),progress=self.progress)
        self.assertEqual(len(records),2);self.assertEqual(self.events[-1]['files_examined'],2)
    def test_empty_numeric_folder_reports_zero_and_one_entered_folder(self):
        for p in list(self.source.rglob('*')):
            if p.is_file():p.unlink()
        sidecar.scan_sidecars(self.source,progress=self.progress)
        self.assertEqual(self.events[-1]['files_examined'],0);self.assertEqual(self.events[-1]['folders_examined'],2)
    def test_cancelled_scan_does_not_emit_final_counts(self):
        cancellation=engine.Cancellation();cancellation.requested=True
        with self.assertRaises(engine.BatchError) as caught:
            engine._sidecar_scan(self.source,cancellation,progress=self.progress)
        self.assertTrue(caught.exception.cancelled)
        self.assertLessEqual(len(self.events),1)
    def test_cli_routes_sidecar_preflight_before_completed_scan(self):
        import sys
        events=[]
        with patch.object(sys,'argv',['engine','--source',str(self.source),'--scan','--clean-json-sidecars']),patch.object(engine.signal,'signal'),patch.object(engine,'scan',return_value=([],[],2)),patch.object(engine,'emit',side_effect=lambda name,**values:events.append(dict(event=name,**values))):
            self.assertEqual(engine.main(),0)
        self.assertEqual(events[0]['event'],'sidecar_scan_progress');self.assertEqual(events[-1]['event'],'scan');self.assertEqual(events[-1]['sidecar_files'],2)
    def test_feedback_has_no_names_paths_or_values(self):
        sidecar.scan_sidecars(self.source,progress=self.progress)
        for event in self.events:self.assertEqual(set(event),{'event','files_examined','folders_examined'})

if __name__=='__main__':unittest.main()
