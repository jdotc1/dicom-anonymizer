"""Benchmark harness guards only: caps and scratch requirement. No engine run, synthetic shapes only."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('benchmark_script', Path(__file__).resolve().parents[1] / 'scripts/benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class BenchmarkCapTests(unittest.TestCase):
    def refused(self, shape):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            benchmark.plan(shape)
        self.assertEqual(raised.exception.code, 2)

    def test_presets_are_within_caps(self):
        for preset in benchmark.PRESETS.values():
            files, size = benchmark.plan(dict(preset))
            self.assertLessEqual(files, benchmark.MAX_FILES)
            self.assertLessEqual(size, benchmark.MAX_BYTES)

    def test_oversized_shapes_are_refused(self):
        base = dict(benchmark.PRESETS['default'])
        self.refused({**base, 'patients': benchmark.MAX_PATIENTS + 1})
        self.refused({**base, 'rows': benchmark.MAX_ROWS + 1})
        self.refused({**base, 'patients': 20, 'slices': 100})  # file-count cap
        self.refused({**base, 'points': 0})

    def test_scratch_directory_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            import sys
            old = sys.argv
            sys.argv = ['benchmark.py']
            try:
                benchmark.main()
            finally:
                sys.argv = old

    def test_not_referenced_by_workflows(self):
        workflows = Path(__file__).resolve().parents[1] / '.github/workflows'
        for path in workflows.glob('*'):
            self.assertNotIn('benchmark.py', path.read_text())


if __name__ == '__main__':
    unittest.main()
