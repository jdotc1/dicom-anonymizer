"""Canary retention survey: answer key vs. engine.clean() vs. engine.audit_dataset(), synthetic data only.

Manual run (never part of an automatic job). Authored; the survey table is deterministic and
the known-gap list in canary_known_gaps.py is pinned to pydicom 3.0.2.
"""
import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pydicom
from pydicom.datadict import dictionary_VR, keyword_for_tag

import canary_answer_key as key
import canary_known_gaps as known
import canary_survey as survey
from test_engine import engine

PINNED = pydicom.__version__ == '3.0.2'


class AnswerKeyTests(unittest.TestCase):
    def test_key_does_not_import_or_name_the_engine_tables(self):
        text = Path(key.__file__).read_text(encoding='utf-8')
        imports = [n for node in ast.walk(ast.parse(text)) for n in
                   ([a.name for a in node.names] if isinstance(node, ast.Import) else
                    [node.module or ''] if isinstance(node, ast.ImportFrom) else [])]
        self.assertFalse([i for i in imports if 'engine' in i])
        names = {n.id for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Name)}
        self.assertFalse(names & {'engine', 'REMOVE_KEYS', 'CLEAR_TAGS', 'REMOVE_TAGS'})

    @unittest.skipUnless(PINNED, 'dictionary cross-check pinned to pydicom 3.0.2')
    def test_key_entries_agree_with_the_dictionary(self):
        for entry in key.NAMED:
            self.assertEqual(keyword_for_tag(entry.tag), entry.keyword, entry)
            self.assertEqual(dictionary_VR(entry.tag), entry.vr, entry)
        self.assertEqual(len({e.tag for e in key.NAMED}), len(key.NAMED))

    def test_every_canary_is_unique_per_tag_and_depth(self):
        tokens = set()
        text = [e for e in key.NAMED if e.vr in ('LO', 'SH', 'ST', 'LT', 'UT', 'UR', 'PN', 'UI')]
        for entry in text:
            for depth in survey.DEPTHS:
                tokens.add(survey.canary(entry.tag, entry.vr, depth))
        self.assertEqual(len(tokens), len(text) * len(survey.DEPTHS))


@unittest.skipUnless(PINNED, 'survey table is pinned to pydicom 3.0.2')
class SurveyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = survey.run_survey(engine)

    def test_table_is_deterministic(self):
        again = survey.run_survey(engine)
        self.assertEqual(survey.render(self.rows), survey.render(again))
        with tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR')) as tmp:
            path = Path(tmp) / 'survivors.tsv'
            path.write_text(survey.render(self.rows), encoding='utf-8')
            self.assertEqual(path.read_text(encoding='utf-8').splitlines()[0], '\t'.join(survey.HEADER))

    def test_named_and_private_classes_follow_the_key_except_pinned_violations(self):
        self.assertEqual(tuple(survey.violations(self.rows)),
                         tuple((t, k, 'named:GONE') for t, k in known.KNOWN_NAMED_VIOLATIONS))
        classes = {r.cls.split(':')[0] for r in self.rows}
        self.assertEqual(classes, {'named', 'private', 'other', 'survey'})
        for r in self.rows:
            if r.cls in ('private:GONE', 'other:GONE'):
                self.assertEqual(r.actions, 'REMOVED', r)

    def test_survivors_match_the_pinned_known_gap_list(self):
        self.assertEqual(survey.gaps(self.rows), sorted(known.KNOWN_GAPS))

    def test_survey_reconciles_with_the_static_75_77_estimate(self):
        retained = [r for r in self.rows if r.cls == 'survey' and 'KEPT' in r.actions]
        text_retained = [r for r in retained if r.vr in ('LO', 'SH', 'UC')]
        # Every survivor is an LO/SH attribute; no ST/LT/UT/UR/PN/AE/DA/DT/TM canary survives.
        self.assertEqual(len(text_retained), len(retained))
        # 77 including retired entries; 75 once retired entries are excluded: the static estimate.
        self.assertEqual(len(retained), 77)
        self.assertEqual(len([r for r in retained if not r.retired]), 75)
        # Of the 77, two are retained by design (ROI labels); the remaining 75 are the known gaps.
        by_design = [r for r in retained if r.verdict == 'OK-retained-by-design']
        self.assertEqual(sorted(r.keyword for r in by_design), ['ROIName', 'ROIObservationLabel'])
        self.assertEqual(len(retained) - len(by_design), len(known.KNOWN_GAPS))
        # StructureSetLabel is LO/SH too but is replaced, so it is correctly not counted as retained.
        self.assertNotIn('StructureSetLabel', {r.keyword for r in retained})

    def test_audit_is_blind_to_exactly_the_survivors(self):
        blind = {r.tag for r in self.rows if r.cls == 'survey' and not r.audit_sees}
        survivors = {r.tag for r in self.rows if r.cls == 'survey' and 'KEPT' in r.actions}
        self.assertEqual(blind, survivors)
        # Everywhere else the audit does see the raw canary, because the value is not retained by design.
        for r in self.rows:
            if 'KEPT' not in r.actions and r.verdict == 'OK':
                self.assertTrue(r.audit_sees, r)

    def test_nested_depths_agree_with_top_level(self):
        for r in self.rows:
            self.assertNotIn(';', r.actions, r)

    def test_planted_gap_in_a_test_copy_is_detected(self):
        # Remove one tag and one keyword from patched copies of the policy tables, as a maintainer's slip would.
        clear = set(engine.CLEAR_TAGS) - {0x300A0002}           # RTPlanLabel
        keys = set(engine.REMOVE_KEYS) - {'InstitutionName'}
        with patch.object(engine, 'CLEAR_TAGS', clear), patch.object(engine, 'REMOVE_KEYS', keys):
            rows = survey.run_survey(engine)
        violated = {k for _t, k, _c in survey.violations(rows)}
        self.assertEqual(violated, {k for _t, k in known.KNOWN_NAMED_VIOLATIONS} | {'RTPlanLabel', 'InstitutionName'})
        new_gaps = set(survey.gaps(rows)) - set(known.KNOWN_GAPS)
        self.assertEqual(new_gaps, {(0x300A0002, 'RTPlanLabel')})
        # The audit shares the patched tables, so it is blind to the very leak it should catch.
        leaked = {r.keyword: r for r in rows if r.keyword in ('RTPlanLabel', 'InstitutionName')}
        self.assertTrue(all(not r.audit_sees for r in leaked.values()))
        # The real tables are untouched after the context exits.
        self.assertIn(0x300A0002, engine.CLEAR_TAGS)
        self.assertIn('InstitutionName', engine.REMOVE_KEYS)


if __name__ == '__main__':
    unittest.main()
