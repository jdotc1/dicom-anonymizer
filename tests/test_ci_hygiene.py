"""Static guards for the manual CI workflow and test timeout hygiene (stdlib only)."""
import ast
import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

import timeouts

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'tests.yml'
TESTS = Path(__file__).resolve().parent
SHA = re.compile(r'^[0-9a-f]{40}$')
TAG = re.compile(r'^v\d+(\.\d+){0,2}$')
WAIT_CALLS = {'run', 'call', 'check_call', 'check_output', 'communicate', 'wait', 'Popen'}


def workflow_problems(text):
    """Return the list of invariant violations found in a workflow's text."""
    problems = []
    lines = text.split('\n')

    def block(header):
        for index, line in enumerate(lines):
            if line.rstrip() == header:
                found = []
                for later in lines[index + 1:]:
                    if later.strip() and not later.startswith(' '):
                        break
                    found.append(later)
                return found
        return None

    on = block('on:')
    if on is None:
        problems.append('missing on: block')
    else:
        triggers = [line.strip().rstrip(':') for line in on if re.match(r'^  \S', line)]
        if triggers != ['workflow_dispatch']:
            problems.append(f'triggers must be only workflow_dispatch, found {triggers}')
        joined = '\n'.join(on)
        if not re.search(r'acknowledge:(.|\n)*?required: true', joined):
            problems.append('acknowledge input must be required')
    if 'pull_request_target' in text:
        problems.append('pull_request_target is forbidden')
    permissions = block('permissions:') or []
    if [line.strip() for line in permissions if line.strip()] != ['contents: read']:
        problems.append('top-level permissions must be exactly contents: read')
    if not re.search(r'^concurrency:', text, re.M):
        problems.append('missing concurrency')
    jobs = block('jobs:') or []
    names = [line for line in jobs if re.match(r'^  \S', line)]
    gates = [line for line in jobs if re.match(r'^    if: ', line)]
    timeouts_found = [line for line in jobs if re.match(r'^    timeout-minutes: \d+', line)]
    if not names or len(gates) != len(names):
        problems.append('every job needs an if gate')
    if len(timeouts_found) != len(names):
        problems.append('every job needs timeout-minutes')
    if any('inputs.acknowledge' not in gate for gate in gates):
        problems.append('every job gate must test inputs.acknowledge')
    job_env = [index for index, line in enumerate(jobs) if re.match(r'^    env:', line)]
    for index in job_env:
        for line in jobs[index + 1:]:
            if not line.startswith('      '):
                break
            if 'runner.' in line:
                problems.append('job-level env must not use the runner context')
    for line in lines:
        match = re.match(r'^\s*-?\s*uses:\s*(\S+)', line)
        if not match:
            continue
        ref = match.group(1).partition('@')[2]
        if not (SHA.match(ref) or TAG.match(ref)):
            problems.append(f'unpinned action reference: {match.group(1)}')
    if 'DICOM_TEST_TMPDIR' not in text:
        problems.append('DICOM_TEST_TMPDIR must be set in a step')
    return problems


def literal_timeouts(source, filename='<test>'):
    """Return line numbers where a wait/subprocess call passes a numeric literal timeout."""
    found = []
    for node in ast.walk(ast.parse(source, filename)):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
        if name not in WAIT_CALLS:
            continue
        for keyword in node.keywords:
            if keyword.arg == 'timeout' and isinstance(keyword.value, (ast.Constant, ast.UnaryOp)):
                found.append(node.lineno)
        if name in {'communicate', 'wait'} and node.args and isinstance(node.args[0], ast.Constant):
            found.append(node.lineno)
    return found


class WorkflowInvariantTests(unittest.TestCase):
    def test_workflow_has_no_problems(self):
        self.assertEqual(workflow_problems(WORKFLOW.read_text()), [])

    def test_synthetic_push_trigger_is_rejected(self):
        text = WORKFLOW.read_text().replace('on:\n', 'on:\n  push:\n', 1)
        self.assertTrue(any('only workflow_dispatch' in p for p in workflow_problems(text)))

    def test_synthetic_violations_are_rejected(self):
        text = WORKFLOW.read_text()
        self.assertTrue(any('pull_request_target' in p for p in workflow_problems(text + '\n# pull_request_target\n')))
        self.assertTrue(any('unpinned' in p for p in workflow_problems(text.replace('checkout@v4', 'checkout@main'))))
        self.assertTrue(any('runner context' in p for p in workflow_problems(
            text.replace('    env:\n', '    env:\n      X: ${{ runner.temp }}\n', 1))))
        self.assertTrue(any('if gate' in p for p in workflow_problems(text.replace('    if: ${{ inputs.acknowledge }}\n', ''))))
        self.assertTrue(any('required' in p for p in workflow_problems(text.replace('required: true', 'required: false'))))


class TimeoutHygieneTests(unittest.TestCase):
    def test_no_literal_timeouts_in_tests(self):
        offenders = []
        for path in sorted(TESTS.glob('*.py')):
            if path.name in {Path(__file__).name, 'timeouts.py'}:
                continue
            for line in literal_timeouts(path.read_text(), str(path)):
                offenders.append(f'{path.name}:{line}')
        self.assertEqual(offenders, [], 'wrap subprocess timeouts in timeouts.scaled()')

    def test_detector_flags_literals_and_accepts_scaled(self):
        self.assertEqual(literal_timeouts('subprocess.run(a, timeout=2)'), [1])
        self.assertEqual(literal_timeouts('p.communicate(5)'), [1])
        self.assertEqual(literal_timeouts('subprocess.run(a, timeout=scaled(2))'), [])

    def test_scale_arithmetic(self):
        def with_scale(value):
            env = {} if value is None else {'DICOM_TEST_TIMEOUT_SCALE': value}
            with patch.dict(os.environ, env):
                if value is None:
                    os.environ.pop('DICOM_TEST_TIMEOUT_SCALE', None)
                return timeouts.scaled(10)
        self.assertEqual(with_scale(None), 10)
        self.assertEqual(with_scale('3'), 30)
        self.assertEqual(with_scale('2.5'), 25)
        for bad in ('x', '0', '-4', 'nan', 'inf', '0.5'):
            self.assertEqual(with_scale(bad), 10, bad)
        self.assertEqual(with_scale('1000'), 1000)


if __name__ == '__main__':
    unittest.main()
