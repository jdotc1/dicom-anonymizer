"""Permanent policy-table lint and sidecar-policy consistency test.

Run once per policy change (manual; not part of any automatic job). It reads
the engine tables as text, so it needs no DICOM fixtures and does not change
the tables. Authored for the pinned pydicom 3.0.2 dictionary; a different
pydicom skips the dictionary-dependent checks instead of guessing.
"""
import copy
import json
import sys
import unittest

import pydicom

import policy_lint
from test_engine import ENGINE, engine

sys.path.insert(0, str(ENGINE.parent))
import sidecar_deid  # noqa: E402

POLICY_JSON = ENGINE.parent / 'policy' / 'mri-physical-v1.json'
PINNED_PYDICOM = '3.0.2'

# Numeric policy tags that the pinned dictionary does not name. Listed explicitly so a
# seventh unknown tag, or one that becomes known, fails the lint instead of passing silently.
UNKNOWN_NUMERIC_TAGS = frozenset({
    0x0040B03F,  # CLEAR_TAGS: MontageChannelLabel
    0x3004007F,  # CLEAR_TAGS: DoseCalculationModelName
    0x00081301,  # REMOVE_TAGS: PrincipalDiagnosisCodeSequence
    0x00081302,  # REMOVE_TAGS: PrimaryDiagnosisCodeSequence
    0x00081303,  # REMOVE_TAGS: SecondaryDiagnosesCodeSequence
    0x00081304,  # REMOVE_TAGS: HistologicalDiagnosesCodeSequence
})
# Numeric tags whose comment may differ from the dictionary keyword (none today).
COMMENT_ALLOWLIST = {}

# REMOVE_KEYS entries that the VR rules in clean() would already blank. Not a defect; pinned so a
# new redundant entry (or a removed one) is noticed and reviewed. Names only.
REDUNDANT_BY_VR = frozenset({
    'AcquisitionComments',
    'AdditionalPatientHistory',
    'ClinicalTrialTimePointDescription',
    'CommentsOnThePerformedProcedureStep',
    'ContributionDescription',
    'DerivationDescription',
    'FrameComments',
    'IdentifyingComments',
    'ImageComments',
    'ImagingServiceRequestComments',
    'InstitutionAddress',
    'InterpretationDiagnosisDescription',
    'InterpretationText',
    'LabelText',
    'PatientComments',
    'PatientTelecomInformation',
    'PerformedStationAETitle',
    'PersonAddress',
    'PersonTelecomInformation',
    'ROIDescription',
    'ROIObservationDescription',
    'ReferringPhysicianAddress',
    'RequestedProcedureComments',
    'ResultsComments',
    'RetrieveURI',
    'RetrieveURL',
    'StructureSetDescription',
    'StudyComments',
    'TextComments',
    'TextValue',
    'TopicSubject',
    'VisitComments',
})
REDUNDANT_BY_REMOVE_TAGS = frozenset({'DataSetTrailingPadding'})


def tables():
    return policy_lint.read_tables(ENGINE.read_text(encoding='utf-8'))


def dictionary_checks(test):
    if pydicom.__version__ != PINNED_PYDICOM:
        test.skipTest(f'dictionary checks are pinned to pydicom {PINNED_PYDICOM}')


class PolicyTableLintTests(unittest.TestCase):
    def setUp(self):
        dictionary_checks(self)

    def lint(self, data):
        return policy_lint.lint_tables(data, unknown_tags=UNKNOWN_NUMERIC_TAGS, comment_allowlist=COMMENT_ALLOWLIST)

    def test_current_tables_are_consistent(self):
        self.assertEqual(self.lint(tables()), [])

    def test_literals_match_runtime_tables(self):
        data = tables()
        self.assertEqual({v for v, _, _ in data['REMOVE_KEYS']}, set(engine.REMOVE_KEYS))
        self.assertEqual({v for v, _, _ in data['CLEAR_TAGS']}, set(engine.CLEAR_TAGS))
        self.assertEqual({v for v, _, _ in data['REMOVE_TAGS']}, set(engine.REMOVE_TAGS))
        self.assertEqual((len(data['REMOVE_KEYS']), len(data['CLEAR_TAGS']), len(data['REMOVE_TAGS'])), (165, 90, 38))

    def test_unknown_numeric_tags_are_exactly_the_listed_six(self):
        unknown = {v for name in ('CLEAR_TAGS', 'REMOVE_TAGS') for v, _, _ in tables()[name]
                   if not pydicom.datadict.keyword_for_tag(v)}
        self.assertEqual(unknown, set(UNKNOWN_NUMERIC_TAGS))
        self.assertEqual(len(unknown), 6)

    def test_redundant_remove_keys_are_the_pinned_lists(self):
        found = policy_lint.redundant_remove_keys(engine.REMOVE_KEYS, engine.REMOVE_TAGS)
        self.assertEqual(found['vr_rule'], set(REDUNDANT_BY_VR))
        self.assertEqual(found['remove_tags_overlap'], set(REDUNDANT_BY_REMOVE_TAGS))
        self.assertEqual(len(REDUNDANT_BY_VR), 32)

    def test_no_tag_in_both_numeric_tables(self):
        self.assertEqual(set(engine.CLEAR_TAGS) & set(engine.REMOVE_TAGS), set())

    def test_misspelled_keyword_fails(self):
        data = copy.deepcopy(tables())
        value, line, comment = data['REMOVE_KEYS'][0]
        data['REMOVE_KEYS'][0] = ('Misspelled' + value, line, comment)
        problems = self.lint(data)
        self.assertEqual(len(problems), 1)
        self.assertIn('does not resolve', problems[0])

    def test_mismatched_numeric_comment_fails(self):
        data = copy.deepcopy(tables())
        value, line, _ = data['CLEAR_TAGS'][0]
        data['CLEAR_TAGS'][0] = (value, line, 'SomeOtherName')
        problems = self.lint(data)
        self.assertEqual(len(problems), 1)
        self.assertIn('SomeOtherName', problems[0])
        # An explicit allowlist entry is the only way to accept a deliberate difference.
        self.assertEqual(policy_lint.lint_tables(data, unknown_tags=UNKNOWN_NUMERIC_TAGS,
                                                 comment_allowlist={value: 'SomeOtherName'}), [])

    def test_tag_in_both_numeric_tables_fails(self):
        data = copy.deepcopy(tables())
        value, line, comment = data['CLEAR_TAGS'][0]
        data['REMOVE_TAGS'].append((value, line, comment))
        self.assertTrue(any('both CLEAR_TAGS and REMOVE_TAGS' in p for p in self.lint(data)))

    def test_duplicate_entry_and_new_unknown_tag_fail(self):
        data = copy.deepcopy(tables())
        data['REMOVE_KEYS'].append(data['REMOVE_KEYS'][0])
        data['REMOVE_TAGS'].append((0x7777FFFF, 1, 'Invented'))
        problems = self.lint(data)
        self.assertTrue(any('duplicate entry' in p for p in problems))
        self.assertTrue(any('not in the dictionary' in p for p in problems))

    def test_missing_comment_fails(self):
        data = copy.deepcopy(tables())
        value, line, _ = data['REMOVE_TAGS'][0]
        data['REMOVE_TAGS'][0] = (value, line, None)
        self.assertTrue(any('has no comment' in p for p in self.lint(data)))


class SidecarPolicyJsonTests(unittest.TestCase):
    def document(self):
        return policy_lint.load_policy_json(POLICY_JSON)

    def test_json_equals_python_policy(self):
        document = self.document()
        self.assertEqual(policy_lint.policy_json_differences(document, sidecar_deid.MRI_PHYSICAL_V1), [])
        self.assertEqual(len(document['fields']), 44)
        self.assertEqual(document['default_action'], 'drop')
        self.assertEqual(document['known_field_wrong_shape_action'], 'reject_file')

    def test_json_is_not_the_source(self):
        # Equality is pinned; the engine keeps using the Python policy object.
        self.assertIs(sidecar_deid.clean_sidecars_to_staging.__defaults__[0], sidecar_deid.MRI_PHYSICAL_V1)

    def test_divergence_is_detected(self):
        policy = sidecar_deid.MRI_PHYSICAL_V1
        document = self.document()
        name = next(iter(document['fields']))
        for mutate, expected in (
            (lambda d: d['fields'][name].__setitem__('shape', 'boolean'), f'{name}.shape differs'),
            (lambda d: d['fields'].__setitem__('ExtraField', {'shape': 'boolean', 'category': 'x'}), 'ExtraField: only in JSON'),
            (lambda d: d['fields'].pop(name), f'{name}: only in Python policy'),
            (lambda d: d.__setitem__('catalog_revision', '0'), 'catalog_revision differs'),
            (lambda d: d['fields']['SliceThickness'].__setitem__('maximum', '9999'), 'SliceThickness.maximum differs'),
            (lambda d: d['fields']['ScanningSequence'].__setitem__('allowed_values', ['SE']), 'ScanningSequence.allowed_values differs'),
        ):
            changed = copy.deepcopy(document)
            mutate(changed)
            self.assertIn(expected, policy_lint.policy_json_differences(changed, policy))

    def test_decimal_spelling_is_not_a_divergence(self):
        document = self.document()
        document['fields']['SliceThickness']['minimum'] = '0.0'
        self.assertEqual(policy_lint.policy_json_differences(document, sidecar_deid.MRI_PHYSICAL_V1), [])


if __name__ == '__main__':
    unittest.main()
