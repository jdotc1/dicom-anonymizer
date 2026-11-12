"""UID-chain checks for the synthetic RT-family, Segmentation, Registration and PT builders.

Authored, not yet run beyond the focused run that accompanied it. Runs engine.clean() in
memory over one patient's set with a single shared uid_map (the way run() shares it across a
batch) and checks that in-batch references follow the remapped targets and that references
to objects outside the batch receive fresh, consistent UIDs. No files are written.
"""
import copy
import unittest

import pydicom
from pydicom.uid import generate_uid

import canary_fixtures as fx
from test_engine import engine


class CanaryChainTests(unittest.TestCase):
    def setUp(self):
        self.chain = fx.build_chain()
        self.source = {k: copy.deepcopy(v) for k, v in self.chain.datasets.items()}
        self.cleaned = {k: copy.deepcopy(v) for k, v in self.chain.datasets.items()}
        self.uid_map = {}
        for ds in self.cleaned.values():   # one map for the whole batch, as run() does
            engine.clean(ds, '12345', self.uid_map)

    def target_value(self, target):
        kind = target[0]
        if kind == 'sop':
            return str(self.cleaned[target[1]].SOPInstanceUID)
        if kind == 'series':
            return str(self.cleaned['ct1' if target[1] == 'ct' else target[1]].SeriesInstanceUID)
        if kind == 'study':
            return str(self.cleaned['plan'].StudyInstanceUID)
        if kind == 'frame':
            holder = 'ct1' if target[1] == 'a' else 'pt'
            return str(self.cleaned[holder].FrameOfReferenceUID)
        raise AssertionError(target)

    def test_builders_cover_the_requested_object_types(self):
        classes = {ds.Modality for ds in self.source.values()}
        self.assertTrue({'CT', 'RTSTRUCT', 'RTPLAN', 'RTDOSE', 'RTIMAGE', 'RTRECORD', 'REG', 'SEG', 'PT'} <= classes)

    def test_source_chain_is_faithful_before_cleaning(self):
        # Every non-external reference points at a UID that really exists in the source set.
        sops = {str(d.SOPInstanceUID) for d in self.source.values()}
        series = {str(d.SeriesInstanceUID) for d in self.source.values()}
        frames = {str(d.FrameOfReferenceUID) for d in self.source.values()}
        study = {str(d.StudyInstanceUID) for d in self.source.values()}
        self.assertEqual(len(study), 1)
        for ref in self.chain.refs:
            value = str(fx.resolve(self.source[ref.owner], ref.path))
            kind = ref.target[0]
            pool = {'sop': sops, 'series': series, 'frame': frames, 'study': study}.get(kind)
            if kind == 'external':
                self.assertEqual(value, self.chain.external[ref.target[1]])
                self.assertNotIn(value, sops | series | frames | study)
            else:
                self.assertIn(value, pool, ref)

    def test_every_instance_uid_changes_and_is_unique(self):
        old = [str(d.SOPInstanceUID) for d in self.source.values()]
        new = [str(d.SOPInstanceUID) for d in self.cleaned.values()]
        self.assertEqual(len(set(new)), len(new))


        self.assertTrue(set(new).isdisjoint(old))
    def test_study_series_and_frame_are_consistent_across_the_batch(self):
        self.assertEqual({str(d.StudyInstanceUID) for d in self.cleaned.values()}, {str(self.cleaned['plan'].StudyInstanceUID)})
        self.assertNotEqual(str(self.cleaned['plan'].StudyInstanceUID), str(self.source['plan'].StudyInstanceUID))
        self.assertEqual(str(self.cleaned['ct1'].SeriesInstanceUID), str(self.cleaned['ct2'].SeriesInstanceUID))
        frame_a = {str(self.cleaned[k].FrameOfReferenceUID) for k in ('ct1', 'ct2', 'rtstruct', 'plan', 'dose', 'rtimage', 'record', 'reg', 'seg')}
        self.assertEqual(len(frame_a), 1)
        self.assertNotEqual(str(self.cleaned['pt'].FrameOfReferenceUID), next(iter(frame_a)))

    def test_in_batch_references_follow_remapped_targets(self):
        checked = 0
        for ref in self.chain.refs:
            if ref.target[0] == 'external':
                continue
            self.assertEqual(str(fx.resolve(self.cleaned[ref.owner], ref.path)), self.target_value(ref.target), ref)
            checked += 1
        self.assertEqual(checked, 23)

    def test_out_of_batch_references_get_fresh_consistent_uids(self):
        batch_uids = set()
        for ds in self.cleaned.values():
            batch_uids |= {str(ds.SOPInstanceUID), str(ds.SeriesInstanceUID), str(ds.StudyInstanceUID), str(ds.FrameOfReferenceUID)}
        seen = {}
        for ref in self.chain.refs:
            if ref.target[0] != 'external':
                continue
            label = ref.target[1]
            value = str(fx.resolve(self.cleaned[ref.owner], ref.path))
            original = self.chain.external[label]
            self.assertTrue(value and value != original)
            self.assertNotIn(value, batch_uids)
            self.assertTrue(pydicom.uid.UID(value).is_valid)
            self.assertEqual(seen.setdefault(label, value), value, 'the same outside UID must map to one fresh UID')
        self.assertEqual(len(seen), len(self.chain.external))
        self.assertEqual(len(set(seen.values())), len(seen))
        # outside_image is referenced from two different files and must agree.
        self.assertEqual([r.owner for r in self.chain.refs if r.target == ('external', 'outside_image')], ['rtimage', 'seg'])

    def test_sop_classes_are_retained(self):
        for key, ds in self.cleaned.items():
            self.assertEqual(str(ds.SOPClassUID), str(self.source[key].SOPClassUID))

    def test_cleaned_chain_passes_the_engine_audit(self):
        forbidden = set()
        for ds in self.source.values():
            engine.source_uids(ds, forbidden)
        for ds in self.cleaned.values():
            ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
            engine.audit_dataset(ds, '12345', forbidden)

    def test_a_missed_remap_would_be_caught(self):
        # Negative control: a reference left at its source value no longer matches the target.
        ds = self.cleaned['dose']
        ds.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID = self.source['plan'].SOPInstanceUID
        ref = next(r for r in self.chain.refs if r.owner == 'dose' and r.target == ('sop', 'plan'))
        self.assertNotEqual(str(fx.resolve(ds, ref.path)), self.target_value(ref.target))


if __name__ == '__main__':
    unittest.main()
