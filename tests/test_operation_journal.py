"""New interruption journal seams only; no accepted engine-policy suites."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_sidecar_integration as base
engine=base.engine
from operation_journal import OperationJournal, JournalError

class OperationJournalTests(unittest.TestCase):
    setUp=base.SidecarIntegrationTests.setUp
    assert_not_published=base.SidecarIntegrationTests.assert_not_published
    def journal(self):return self.root/'recovery'/'operation.json'
    def batch(self, **kwargs):return engine.run(self.source,self.output,lambda event,**values:self.events.append(dict(event=event,**values)),journal=self.journal(),**kwargs)
    def test_published_record_retains_identity_without_source_values(self):
        self.batch()
        record=json.loads(self.journal().read_text());info=self.output.lstat()
        self.assertEqual(record['phase'],'published');self.assertEqual((record['device'],record['inode']),(info.st_dev,info.st_ino))
        self.assertNotIn('Private',self.journal().read_text());self.assertNotIn(str(self.source),self.journal().read_text())
        self.assertFalse((self.output/'operation.json').exists())
    def test_interruption_after_allocation_keeps_owned_record(self):
        original=OperationJournal.mark
        def mark(operation,phase,**values):
            original(operation,phase,**values)
            if phase=='allocated':raise KeyboardInterrupt()
        with patch.object(OperationJournal,'mark',mark):
            with self.assertRaises(KeyboardInterrupt):self.batch()
        record=json.loads(self.journal().read_text());stage=Path(record['staging']);self.assertTrue(stage.is_dir())
        self.assertEqual((stage.stat().st_dev,stage.stat().st_ino),(record['device'],record['inode']));self.assertFalse(self.output.exists())
    def test_normal_failure_cleans_and_marks_record(self):
        with patch.object(engine,'self_audit',side_effect=engine.BatchError('Synthetic audit failure')):
            with self.assertRaises(engine.BatchError):self.batch()
        self.assertEqual(json.loads(self.journal().read_text())['phase'],'cleaned');self.assert_not_published()
    def test_prepublication_interruption_cannot_claim_output(self):
        original=OperationJournal.mark
        def mark(operation,phase,**values):
            original(operation,phase,**values)
            if phase=='publishing':raise KeyboardInterrupt()
        with patch.object(OperationJournal,'mark',mark):
            with self.assertRaises(KeyboardInterrupt):self.batch()
        record=json.loads(self.journal().read_text());self.assertEqual(record['phase'],'publishing');self.assertTrue(Path(record['staging']).exists());self.assertFalse(self.output.exists())
    def test_postrename_record_failure_is_published_uncertainty(self):
        original=OperationJournal.mark
        def mark(operation,phase,**values):
            if phase=='published':raise OSError('synthetic journal unavailable')
            original(operation,phase,**values)
        with patch.object(OperationJournal,'mark',mark):
            with self.assertRaises(engine.BatchError) as caught:self.batch()
        self.assertTrue(caught.exception.output_published);self.assertTrue(self.output.is_dir())
        self.assertEqual(json.loads(self.journal().read_text())['phase'],'publishing')
    def test_record_is_exclusive_and_replacement_is_rejected(self):
        journal=OperationJournal(self.journal(),self.output)
        with self.assertRaises(FileExistsError):OperationJournal(self.journal(),self.output)
        self.journal().unlink();self.journal().write_text('replacement')
        with self.assertRaises(JournalError):journal.mark('allocated')
        self.assertEqual(self.journal().read_text(),'replacement')
    def test_journal_in_input_or_output_is_rejected(self):
        for path in [self.source/'record.json',self.output/'record.json']:
            with self.assertRaisesRegex(engine.BatchError,'separately'):
                engine.run(self.source,self.output,progress=lambda *a,**k:None,journal=path)
            self.assertFalse(path.exists())
    def test_no_journal_opt_in_retains_previous_behavior(self):
        engine.run(self.source,self.output,progress=lambda *a,**k:None)
        self.assertFalse(self.journal().exists())
    def test_pending_cancel_after_recorded_allocation_cleans(self):
        cancellation=engine.Cancellation();cancellation.requested=True
        with self.assertRaises(engine.BatchError) as caught:self.batch(cancellation=cancellation)
        self.assertTrue(caught.exception.cancelled);self.assertEqual(json.loads(self.journal().read_text())['phase'],'cleaned');self.assert_not_published()

    def test_cli_forwards_local_journal_only_as_operational_state(self):
        with patch.object(sys,'argv',['engine','--source',str(self.source),'--destination',str(self.output),'--journal',str(self.journal())]),patch.object(engine.signal,'signal'),patch.object(engine,'run') as run:
            self.assertEqual(engine.main(),0)
        self.assertEqual(run.call_args.kwargs['journal'],str(self.journal()))
    def test_existing_record_blocks_run_before_staging(self):
        self.journal().parent.mkdir();self.journal().write_text('preserved')
        with patch.object(engine.tempfile,'mkdtemp',side_effect=AssertionError('staging allocated')):
            with self.assertRaisesRegex(engine.BatchError,'recovery record'):self.batch()
        self.assertEqual(self.journal().read_text(),'preserved');self.assert_not_published()

if __name__=='__main__':unittest.main()
