"""Small descriptor-admission fixtures; no application launch or corpus reads."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_engine as fixtures

sys.path.insert(0, str(fixtures.ENGINE.parent))
import sidecar_deid

engine = fixtures.engine


class DescriptorReadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ['DICOM_TEST_TMPDIR'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'input'
        self.path = self.source / '00043' / 'image.dcm'
        self.dataset = fixtures.make_dicom(self.path)

    def test_replacement_during_dicom_decode_is_rejected(self):
        original_read = engine.pydicom.dcmread
        replaced = []

        def read(*args, **kwargs):
            if not replaced:
                replacement = self.root / 'replacement.dcm'
                replacement.write_bytes(self.path.read_bytes())
                os.replace(replacement, self.path)
                replaced.append(True)
            return original_read(*args, **kwargs)

        with patch.object(engine.pydicom, 'dcmread', read):
            with self.assertRaises(engine.BatchError):
                engine.checked_read(self.path)

    def test_in_place_change_after_dicom_decode_is_rejected(self):
        original_read = engine.pydicom.dcmread

        def read(*args, **kwargs):
            result = original_read(*args, **kwargs)
            with self.path.open('ab') as stream:
                stream.write(b'CHANGED')
            return result

        with patch.object(engine.pydicom, 'dcmread', read):
            with self.assertRaises(engine.BatchError):
                engine.checked_read(self.path)

    def fifo_child(self, mode):
        script = r'''
import importlib.util
import os
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location('descriptor_engine', sys.argv[1])
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)
target = Path(sys.argv[2])
source = Path(sys.argv[3])
mode = sys.argv[4]
swapped = False
def swap():
    global swapped
    if not swapped:
        swapped = True
        target.rename(target.with_name('original-kept'))
        os.mkfifo(target)
original_read = engine.pydicom.dcmread
def read(*args, **kwargs):
    if mode == 'decode' or (mode == 'probe' and kwargs.get('stop_before_pixels')):
        swap()
    return original_read(*args, **kwargs)
engine.pydicom.dcmread = read
original_fingerprint = engine.fingerprint
def fingerprint(path):
    result = original_fingerprint(path)
    if mode == 'header' and path == target:
        swap()
    return result
engine.fingerprint = fingerprint
original_is_file = Path.is_file
def is_file(path):
    result = original_is_file(path)
    if mode == 'resource' and path == target:
        swap()
    return result
Path.is_file = is_file
try:
    if mode == 'decode':
        engine.checked_read(target)
    else:
        engine.scan(source)
except engine.BatchError:
    print('rejected')
else:
    raise SystemExit('non-regular admission was accepted')
'''
        if mode == 'probe':
            self.path = self.path.rename(self.path.with_name('extensionless'))
            self.path.write_bytes(self.path.read_bytes()[132:])
        elif mode == 'resource':
            self.path = self.source / '._resource'
            self.path.write_bytes(b'\x00\x05\x16\x07')
        try:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
                                     str(fixtures.ENGINE), str(self.path), str(self.source), mode],
                                    capture_output=True, text=True, timeout=2)
        except subprocess.TimeoutExpired:
            self.fail('FIFO substitution blocked file admission before rejection')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'rejected')

    def test_fifo_substitution_at_dicom_decode_does_not_block(self):
        self.fifo_child('decode')

    def test_fifo_substitution_at_extensionless_probe_does_not_block(self):
        self.fifo_child('probe')

    def test_fifo_substitution_before_scan_header_does_not_block(self):
        self.fifo_child('header')

    def test_fifo_substitution_before_resource_header_does_not_block(self):
        self.fifo_child('resource')

    def test_sidecar_fifo_open_is_nonblocking(self):
        fifo = self.root / 'input.json'
        os.mkfifo(fifo)
        script = '''
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
import sidecar_deid
try:
    sidecar_deid._read_regular_nofollow(Path(sys.argv[2]))
except sidecar_deid.SidecarError:
    print('rejected')
else:
    raise SystemExit('FIFO accepted')
'''
        try:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
                                     str(fixtures.ENGINE.parent), str(fifo)],
                                    capture_output=True, text=True, timeout=2)
        except subprocess.TimeoutExpired:
            self.fail('Sidecar admission blocked on a FIFO before checking its type')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'rejected')

    def test_sidecar_path_replacement_during_read_is_rejected(self):
        path = self.root / 'input.json'
        path.write_bytes(b'{"EchoTime":0.003}')
        original_read = os.read
        replaced = []

        def read(*args):
            data = original_read(*args)
            if not replaced:
                other = self.root / 'other.json'
                other.write_bytes(b'{"EchoTime":0.004}')
                os.replace(other, path)
                replaced.append(True)
            return data

        with patch.object(sidecar_deid.os, 'read', read):
            with self.assertRaises(sidecar_deid.SidecarError):
                sidecar_deid._read_regular_nofollow(path)

    def test_sidecar_postread_inspection_error_retains_destination_errno(self):
        path = self.root / 'output.json'
        path.write_bytes(b'{}')
        original_read, original_stat = os.read, Path.stat
        read_started = []

        def read(*args):
            data = original_read(*args)
            read_started.append(True)
            return data

        def inspect(candidate, *args, **kwargs):
            if candidate == path and read_started:
                raise PermissionError(errno.EACCES, 'SYNTHETIC_PRIVATE_LOCATION')
            return original_stat(candidate, *args, **kwargs)

        with patch.object(sidecar_deid.os, 'read', read), patch.object(Path, 'stat', inspect):
            with self.assertRaises(sidecar_deid.SidecarDestinationError) as caught:
                sidecar_deid._read_regular_nofollow(path, destination=True)
        self.assertEqual(caught.exception.os_error.errno, errno.EACCES)
        self.assertNotIn('SYNTHETIC_PRIVATE_LOCATION', str(caught.exception))

    def test_valid_regular_and_headerless_reads_keep_decoded_payload_available(self):
        result = engine.checked_read(self.path)
        self.assertEqual(str(result.SOPInstanceUID), str(self.dataset.SOPInstanceUID))
        self.assertEqual(result.PixelData, b'\1\0\2\0\3\0\4\0')
        self.assertEqual(str(result.filename), str(self.path))
        headerless = self.path.with_name('headerless')
        headerless.write_bytes(self.path.read_bytes()[132:])
        result = engine.checked_read(headerless)
        self.assertEqual(str(result.SOPInstanceUID), str(self.dataset.SOPInstanceUID))
        self.assertEqual(result.PixelData, b'\1\0\2\0\3\0\4\0')

    def test_sidecar_maximum_keeps_existing_one_byte_overflow_contract(self):
        path = self.root / 'input.json'
        path.write_bytes(b'123456')
        data, signature = sidecar_deid._read_regular_nofollow(path, maximum=3)
        self.assertEqual(data, b'1234')
        self.assertEqual(signature[2], 6)

    def test_replaced_staged_dicom_blocks_publication(self):
        original_read = engine.pydicom.dcmread
        auditing = []
        replaced = []

        def progress(event, **values):
            if event == 'audit_progress' and values['audited_files'] == 0:
                auditing.append(True)

        def read(*args, **kwargs):
            if auditing and not replaced:
                [stage] = list(self.root.glob('.dicom-batch-*'))
                [path] = list(stage.rglob('*.dcm'))
                kept = self.root / 'kept-original.dcm'
                path.rename(kept)
                path.write_bytes(kept.read_bytes())
                replaced.append(True)
            return original_read(*args, **kwargs)

        output = self.root / 'output'
        with patch.object(engine.pydicom, 'dcmread', read):
            with self.assertRaises(engine.BatchError):
                engine.run(self.source, output, progress=progress)
        self.assertTrue(replaced)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])


if __name__ == '__main__':
    unittest.main()
