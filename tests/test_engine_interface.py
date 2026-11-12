"""Conformance of engine events and report keys with docs/ENGINE-INTERFACE.md."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import test_engine as fixtures

REPO = Path(fixtures.ENGINE).parents[1]
DOC = (REPO / 'docs' / 'ENGINE-INTERFACE.md').read_text()


def section(title):
    match = re.search(r'^## %s\n(.*?)(?=^## |\Z)' % re.escape(title), DOC, re.S | re.M)
    return match.group(1)


def table_names(title):
    return set(re.findall(r'^\| `([a-z_]+)`', section(title), re.M))


def emitted_names():
    names = set()
    for name in ('engine.py', 'sidecar_deid.py'):
        tree = ast.parse((REPO / 'engine' / name).read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                    node.func.id in {'emit', 'progress'} and node.args and
                    isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                names.add(node.args[0].value)
    return names


class EngineInterfaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'input'
        fixtures.make_dicom(self.source / '00001' / 'image.dcm')
        (self.source / '00001' / 'side.json').write_text('{"EchoTime": 0.003}')

    def cli(self, *args):
        result = subprocess.run([sys.executable, '-B', str(fixtures.ENGINE), '--source', str(self.source), *args],
                                capture_output=True, text=True)
        lines = result.stdout.splitlines()
        events = [json.loads(line) for line in lines]
        for event in events:
            self.assertIsInstance(event, dict)
            self.assertIsInstance(event['event'], str)
        return result.returncode, events

    def check_counters(self, events):
        last = {}
        for event in events:
            for key in ('files_examined', 'folders_examined', 'processed', 'audited_files'):
                if key in event:
                    marker = (event['event'], key)
                    self.assertGreaterEqual(event[key], last.get(marker, 0))
                    last[marker] = event[key]

    def test_documented_events_match_engine_code(self):
        self.assertEqual(emitted_names(), table_names('Events'))

    def test_scan_run(self):
        code, events = self.cli('--scan', '--clean-json-sidecars')
        self.assertEqual(code, 0)
        self.check_counters(events)
        self.assertEqual([e['event'] for e in events].count('scan'), 1)
        self.assertEqual(events[-1]['event'], 'scan')
        self.assertTrue({e['event'] for e in events} <= table_names('Events'))

    def test_processing_run_events_and_report_keys(self):
        output = self.root / 'output'
        code, events = self.cli('--destination', str(output), '--clean-json-sidecars')
        self.assertEqual(code, 0)
        self.check_counters(events)
        names = [e['event'] for e in events]
        self.assertEqual(names[-1], 'complete')
        self.assertEqual(sum(n in {'complete', 'error'} for n in names), 1)
        self.assertTrue(set(names) <= table_names('Events'))
        # Every documented event except error appears in a sidecar-enabled run, plus the scan.
        self.assertEqual(set(names), table_names('Events') - {'error'})
        report = json.loads((output / 'anonymization-report.json').read_text())
        self.assertEqual(set(report), table_names('Report keys'))
        self.assertEqual(report['audit_coverage']['schema_version'], 1)
        coverage_line = [l for l in section('Report keys').splitlines() if l.startswith('| `audit_coverage`')][0]
        for key in report['audit_coverage']:
            self.assertIn('`%s`' % key, coverage_line)

    def test_default_run_report_has_no_sidecar_key(self):
        output = self.root / 'output'
        code, events = self.cli('--destination', str(output))
        self.assertEqual(code, 0)
        report = json.loads((output / 'anonymization-report.json').read_text())
        self.assertEqual(set(report), table_names('Report keys') - {'json_sidecars'})

    def test_failing_run_has_one_terminal_error(self):
        output = self.root / 'output'
        output.mkdir()
        code, events = self.cli('--destination', str(output))
        self.assertEqual(code, 1)
        names = [e['event'] for e in events]
        self.assertEqual(names[-1], 'error')
        self.assertEqual(sum(n in {'complete', 'error'} for n in names), 1)
        self.assertNotIn('complete', names)
        self.assertEqual({'message', 'cancelled', 'cleanup_failed'} - set(events[-1]), set())
        self.assertNotIn(str(self.root), events[-1]['message'])

    def test_documented_flags_exist(self):
        flags = set(re.findall(r'^\| `(--[a-z-]+)', section('Flags'), re.M))
        text = (fixtures.ENGINE).read_text()
        self.assertEqual(flags, set(re.findall(r"add_argument\('(--[a-z-]+)'", text)))


if __name__ == '__main__':
    unittest.main()
