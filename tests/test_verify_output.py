import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pydicom
from pydicom.uid import generate_uid

TESTS = Path(__file__).resolve().parent
ENGINE = TESTS.parents[0] / 'engine' / 'engine.py'
spec = importlib.util.spec_from_file_location('bulk_engine_verify_output', ENGINE)
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)
verify_output = engine._verify_module()

helper_spec = importlib.util.spec_from_file_location('engine_test_helpers_vo', TESTS / 'test_engine.py')
helpers = importlib.util.module_from_spec(helper_spec)
helper_spec.loader.exec_module(helpers)
make_dicom = helpers.make_dicom


def tree_state(root):
    state = {}
    for current, dirs, files in os.walk(root):
        for name in dirs + files:
            path = Path(current) / name
            info = path.lstat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''
            state[path.relative_to(root).as_posix()] = (info.st_mtime_ns, info.st_size, digest)
    return state


class VerifyOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'))
        cls.addClassCleanup(temporary.cleanup)
        cls.base = Path(temporary.name)
        source = cls.base / 'input'
        image = generate_uid()
        study = generate_uid()
        make_dicom(source / '00001' / 'a.dcm', study=study, sop=image)
        make_dicom(source / '00001' / 'rt.dcm', study=study, ref=image)
        make_dicom(source / '00002' / 'b.dcm', identity='other-source-id')
        cls.published = cls.base / 'published'
        engine.run(source, cls.published, progress=lambda *a, **k: None)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ.get('DICOM_TEST_TMPDIR'))
        self.addCleanup(temporary.cleanup)
        self.copy = Path(temporary.name) / 'copy'
        shutil.copytree(self.published, self.copy)
        self.events = []

    def verify(self, root=None):
        return verify_output.verify(root or self.copy, engine, progress=lambda e, **v: self.events.append((e, v)))

    def message(self):
        with self.assertRaises(engine.BatchError) as caught:
            self.verify()
        text = str(caught.exception)
        self.assertNotIn(str(self.base), text)
        self.assertNotIn('00001', text)
        return text

    def edit(self, relative, change):
        path = self.copy / relative
        ds = pydicom.dcmread(path)
        change(ds)
        ds.save_as(path, enforce_file_format=True)

    def edit_report(self, change):
        path = self.copy / 'anonymization-report.json'
        report = json.loads(path.read_text())
        change(report)
        path.write_text(json.dumps(report))

    def rt_path(self):
        for path in sorted(self.copy.rglob('*.dcm')):
            if pydicom.dcmread(path, stop_before_pixels=True).Modality == 'RTSTRUCT':
                return path.relative_to(self.copy)

    def test_published_tree_passes_with_terminal_event(self):
        result = self.verify()
        self.assertEqual(result['files_audited'], 3)
        self.assertEqual(result['patients'], 2)
        self.assertEqual(result['rtstruct_files'], 1)
        self.assertEqual(result['rtstruct_references_resolved'], 1)
        self.assertEqual(result['source_uid_check'], 'not_performed')
        self.assertEqual(result['independent_conformance_check'], 'not_performed')
        names = [name for name, _ in self.events]
        self.assertEqual(names[0], 'scan')
        self.assertIn('audit_progress', names)
        self.assertEqual(names[-1], 'verify_complete')
        self.assertEqual(names.count('verify_complete'), 1)
        self.assertNotIn('complete', names)
        self.assertEqual(self.verify()['tree_sha256'], result['tree_sha256'])

    def test_read_only(self):
        before = tree_state(self.copy)
        self.verify()
        self.assertEqual(tree_state(self.copy), before)

    def test_pixel_edit_passes_audit_but_changes_tree_digest(self):
        baseline = self.verify()['tree_sha256']
        mr = next(p for p in sorted(self.copy.rglob('*.dcm')) if pydicom.dcmread(p, stop_before_pixels=True).Modality == 'MR')
        self.edit(mr.relative_to(self.copy), lambda ds: setattr(ds, 'PixelData', b'\x09\0\2\0\3\0\4\0'))
        self.assertNotEqual(self.verify()['tree_sha256'], baseline)

    def test_single_edit_tampering_fails_with_distinct_fixed_messages(self):
        mr = Path('00001/Series_0001/Image_000001.dcm')
        cases = {}

        def run_case(name, change):
            shutil.rmtree(self.copy)
            shutil.copytree(self.published, self.copy)
            change()
            cases[name] = self.message()

        run_case('private', lambda: self.edit(mr, lambda ds: ds.add_new((0x0011, 0x0010), 'LO', 'PRIVATE')))
        run_case('date', lambda: self.edit(mr, lambda ds: setattr(ds, 'StudyDate', '20200101')))
        run_case('patient_id', lambda: self.edit(mr, lambda ds: setattr(ds, 'PatientID', '00009')))
        run_case('free_text', lambda: self.edit(mr, lambda ds: setattr(ds, 'PatientComments', 'x')))
        run_case('extra_dcm', lambda: shutil.copy(self.copy / mr, self.copy / '00001' / 'Series_0001' / 'Image_000009.dcm'))
        run_case('rename_folder', lambda: (self.copy / '00002').rename(self.copy / '00003'))
        run_case('bad_reference', lambda: self.edit(self.rt_path(), self.set_reference))
        run_case('total_files', lambda: self.edit_report(lambda r: r.update(total_files=r['total_files'] + 1)))
        run_case('policy', lambda: self.edit_report(lambda r: r['policy'].update(version='0')))
        run_case('missing_report', lambda: (self.copy / 'anonymization-report.json').unlink())
        run_case('stray_file', lambda: (self.copy / 'notes.txt').write_text('x'))
        self.assertEqual(len(set(cases.values())), 9, cases)
        self.assertEqual(cases['stray_file'], cases['extra_dcm'])
        self.assertEqual(cases['free_text'], verify_output.E_AUDIT)
        self.assertEqual(cases['private'], verify_output.E_PRIVATE)
        self.assertEqual(cases['date'], verify_output.E_DATES)
        self.assertEqual(cases['patient_id'], verify_output.E_IDENTITY)
        self.assertEqual(cases['rename_folder'], verify_output.E_COUNTS)
        self.assertEqual(cases['bad_reference'], verify_output.E_CLOSURE)

    @staticmethod
    def set_reference(ds):
        for element in ds.iterall():
            if element.keyword == 'ReferencedSOPInstanceUID':
                element.value = generate_uid()

    def test_symlink_and_missing_root_refused(self):
        with self.assertRaises(engine.BatchError) as caught:
            self.verify(self.copy / 'absent')
        self.assertEqual(str(caught.exception), verify_output.E_ROOT)
        link = self.copy.parent / 'link'
        link.symlink_to(self.copy)
        with self.assertRaises(engine.BatchError):
            self.verify(link)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(ENGINE), *args], capture_output=True, text=True)

    def test_cli_success_and_failure_shapes(self):
        done = self.run_cli('--verify-output', str(self.copy))
        self.assertEqual(done.returncode, 0, done.stderr)
        events = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual(events[-1]['event'], 'verify_complete')
        self.assertEqual(events[-1]['source_uid_check'], 'not_performed')
        self.edit(Path('00001/Series_0001/Image_000001.dcm'), lambda ds: setattr(ds, 'StudyDate', '20200101'))
        failed = self.run_cli('--verify-output', str(self.copy))
        self.assertEqual(failed.returncode, 1)
        last = json.loads(failed.stdout.splitlines()[-1])
        self.assertEqual((last['event'], last['message']), ('error', verify_output.E_DATES))
        self.assertNotIn(str(self.base), failed.stdout)

    def test_existing_argument_shapes_unchanged(self):
        self.assertEqual(self.run_cli('--scan').returncode, 2)
        self.assertEqual(self.run_cli('--destination', str(self.base / 'x')).returncode, 2)
        self.assertEqual(self.run_cli('--verify-output', str(self.copy), '--source', str(self.base)).returncode, 2)
        self.assertEqual(self.run_cli('--verify-output', str(self.copy), '--scan').returncode, 2)


if __name__ == '__main__':
    unittest.main()
