"""Only r2 deltas against the already accepted host integration."""
import errno
from pathlib import Path
import unittest
from unittest.mock import patch
import test_sidecar_integration as base
engine, sidecar = base.engine, base.sidecar

class SidecarR2Tests(unittest.TestCase):
    setUp = base.SidecarIntegrationTests.setUp
    run_batch = base.SidecarIntegrationTests.run_batch
    assert_not_published = base.SidecarIntegrationTests.assert_not_published

    def test_aggregate_cleaned_budget_rejects_before_staging(self):
        second=self.file.with_name('second.json');second.write_bytes(self.file.read_bytes())
        one=sidecar.scan_sidecars(self.source)[0].estimated_output_bytes
        limits=sidecar.BatchLimits(max_total_output_bytes=one*2-1)
        def scan(source,cancellation,progress=None):
            return engine._sidecar_call(sidecar.scan_sidecars,source,limits=limits,progress=progress)
        with patch.object(engine,'_sidecar_scan',side_effect=scan),patch.object(engine.tempfile,'mkdtemp',side_effect=AssertionError('staging allocated')):
            with self.assertRaisesRegex(engine.BatchError,'output byte limit'):self.run_batch()
        self.assert_not_published()

    def test_audit_read_io_error_retains_output_location_recovery(self):
        original=sidecar.audit_sidecars
        def audit(*args,**kwargs):
            with patch.object(sidecar.os,'read',side_effect=OSError(errno.EIO,'/private/sensitive')):
                return original(*args,**kwargs)
        with patch.object(sidecar,'audit_sidecars',side_effect=audit):
            with self.assertRaises(engine.BatchError) as caught:self.run_batch()
        self.assertEqual(caught.exception.output_issue,'unavailable')
        self.assertNotIn('/private',str(caught.exception));self.assert_not_published()

    def test_seal_lstat_error_retains_permissions_recovery(self):
        original=sidecar.seal_staging_inventory;real_lstat=Path.lstat
        def lstat(path,*args,**kwargs):
            if path.name=='anonymization-report.json':raise PermissionError(errno.EACCES,'/private/sensitive')
            return real_lstat(path,*args,**kwargs)
        def seal(*args,**kwargs):
            with patch.object(Path,'lstat',lstat):return original(*args,**kwargs)
        with patch.object(sidecar,'seal_staging_inventory',side_effect=seal):
            with self.assertRaises(engine.BatchError) as caught:self.run_batch()
        self.assertEqual(caught.exception.output_issue,'permissions')
        self.assertNotIn('/private',str(caught.exception));self.assert_not_published()

    def test_seal_walk_io_error_retains_unavailable_recovery(self):
        original=sidecar.seal_staging_inventory
        def seal(*args,**kwargs):
            def walk(*args,**kwargs):
                kwargs['onerror'](OSError(errno.ENODEV,'/private/sensitive'));return iter(())
            with patch.object(sidecar.os,'walk',side_effect=walk):return original(*args,**kwargs)
        with patch.object(sidecar,'seal_staging_inventory',side_effect=seal):
            with self.assertRaises(engine.BatchError) as caught:self.run_batch()
        self.assertEqual(caught.exception.output_issue,'unavailable');self.assert_not_published()

    def test_empty_discovery_honors_pending_cancel(self):
        self.file.unlink();cancellation=engine.Cancellation();cancellation.requested=True
        with self.assertRaises(engine.BatchError) as caught:engine._sidecar_scan(self.source,cancellation)
        self.assertTrue(caught.exception.cancelled)

    def test_seal_honors_cancel_within_single_directory(self):
        stage=self.root/'stage';stage.mkdir()
        first=stage/'one';second=stage/'two';first.write_text('a');second.write_text('b')
        calls=[];cancellation=engine.Cancellation()
        def cancel_check():
            calls.append(1)
            # initial + two expected-file callbacks + directory callback + first file callback
            if len(calls)==5:cancellation.cancel()
        with self.assertRaises(engine.BatchError) as caught:
            sidecar.seal_staging_inventory(stage,dicom_paths=[first,second],sidecar_paths=[],report_path=None,cancel_check=cancel_check)
        self.assertTrue(caught.exception.cancelled);self.assertEqual(len(calls),5)

    def test_destination_write_error_still_classifies_through_existing_callback(self):
        with patch.object(sidecar.os,'write',side_effect=OSError(errno.ENOSPC,'/private/sensitive')):
            with self.assertRaises(engine.BatchError) as caught:self.run_batch()
        self.assertEqual(caught.exception.output_issue,'space');self.assert_not_published()

if __name__=='__main__':unittest.main()
