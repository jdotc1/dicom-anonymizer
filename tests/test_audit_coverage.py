"""Report-boundary coverage using small synthetic batches; no application launch."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import test_engine as fixtures

sys.path.insert(0, str(fixtures.ENGINE.parent))
engine = fixtures.engine


class AuditCoverageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'input'
        self.patient = self.source / '00043'
        fixtures.make_dicom(self.patient / 'source-image.dcm')
        self.output = self.root / 'output'

    def report(self, **options):
        result = engine.run(self.source, self.output, progress=lambda *a, **k: None, **options)
        text = (self.output / 'anonymization-report.json').read_text()
        report = json.loads(text)
        for private_value in (str(self.root), 'source-image.dcm', 'source-sidecar.json',
                              'Private^Person', 'synthetic-source-id', 'SIDE_SOURCE_PERSON'):
            self.assertNotIn(private_value, text)
        return result, report

    def add_sidecar(self):
        (self.patient / 'source-sidecar.json').write_text(
            '{"EchoTime":0.00300,"PatientName":"SIDE_SOURCE_PERSON"}')

    def test_default_report_distinguishes_completed_checks_from_retained_content(self):
        self.add_sidecar()
        result, report = self.report()
        coverage = report.get('audit_coverage')
        self.assertIsNotNone(coverage, 'Published report must state audit coverage and limitations')
        self.assertEqual(coverage['schema_version'], 1)
        self.assertEqual(coverage['dicom']['result'], 'passed')
        self.assertEqual(coverage['dicom']['files_written'], 1)
        self.assertEqual(coverage['dicom']['files_audited'], result['audited_files'])
        self.assertIn('128-byte preamble zeroed', coverage['dicom']['checks'])
        self.assertIn('rebuilt file meta matches writer defaults and dataset UIDs', coverage['dicom']['checks'])
        self.assertIn('present StructureSetLabel normalized to Structures', coverage['dicom']['checks'])
        self.assertEqual(coverage['json_sidecars'], {
            'enabled': False, 'result': 'not_requested', 'files_written': 0, 'files_audited': 0})
        self.assertNotIn('json_sidecars', report)  # Existing optional report section stays optional.
        self.assertEqual(report['excluded_files'], 1)
        self.assertIn('ROIName', coverage['retained_content']['dicom_attributes'])
        self.assertIn('SeriesDescription', coverage['retained_content']['dicom_attributes'])
        self.assertIn('pixel data', coverage['retained_content']['payloads'])
        self.assertIn('patient_folder_identifier', coverage['retained_content'])
        for code in ('pixel_and_contour_identity', 'retained_text_identity',
                     'dicom_conformance', 'reference_closure', 'companion_file_content'):
            self.assertIn(code, coverage['not_assessed'])
        self.assertEqual(report['self_audit']['result'], 'passed')
        self.assertEqual(coverage['dicom']['checks'], report['self_audit']['checks'])

    def test_skipped_dicom_audit_never_claims_completed_checks(self):
        result, report = self.report(audit=False)
        coverage = report.get('audit_coverage')
        self.assertIsNotNone(coverage, 'Skipped audit must be explicit in coverage')
        self.assertEqual(coverage['dicom'], {
            'result': 'skipped', 'files_written': 1, 'files_audited': 0, 'checks': []})
        self.assertEqual(report['self_audit'], {'result': 'skipped', 'files_audited': 0})
        self.assertEqual(result['audited_files'], 0)

    def test_enabled_sidecars_report_independent_audit_counts(self):
        self.add_sidecar()
        result, report = self.report(clean_json_sidecars=True)
        coverage = report.get('audit_coverage')
        self.assertIsNotNone(coverage, 'Sidecar coverage must accompany DICOM coverage')
        self.assertEqual(coverage['json_sidecars'], {
            'enabled': True, 'result': 'passed', 'files_written': 1, 'files_audited': 1})
        self.assertEqual(report['json_sidecars']['files_written'], 1)
        self.assertEqual(report['json_sidecars']['files_audited'], result['sidecar_audited_files'])
        self.assertEqual(report['excluded_files'], 0)
        self.assertEqual(len(list(self.output.rglob('Sidecar_*.json'))), 1)

    def test_sidecar_audit_remains_explicit_when_dicom_audit_is_skipped(self):
        self.add_sidecar()
        result, report = self.report(audit=False, clean_json_sidecars=True)
        coverage = report.get('audit_coverage')
        self.assertIsNotNone(coverage, 'Audit status must be separate for each output kind')
        self.assertEqual(coverage['dicom']['result'], 'skipped')
        self.assertEqual(coverage['dicom']['checks'], [])
        self.assertEqual(coverage['dicom']['files_audited'], 0)
        self.assertEqual(coverage['json_sidecars']['result'], 'passed')
        self.assertEqual(coverage['json_sidecars']['files_audited'], 1)
        self.assertEqual(result['audited_files'], 0)
        self.assertEqual(result['sidecar_audited_files'], 1)

    def test_enabled_sidecars_with_no_files_report_zero_not_disabled(self):
        _, report = self.report(clean_json_sidecars=True)
        coverage = report.get('audit_coverage')
        self.assertIsNotNone(coverage, 'An enabled empty sidecar pass must not look disabled')
        self.assertEqual(coverage['json_sidecars'], {
            'enabled': True, 'result': 'passed', 'files_written': 0, 'files_audited': 0})
        self.assertEqual(report['json_sidecars']['files_discovered'], 0)


if __name__ == '__main__':
    unittest.main()
