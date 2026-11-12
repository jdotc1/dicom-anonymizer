#!/usr/bin/env python3
"""Manual, bounded performance benchmark on entirely synthetic data.

Not a test, not a gate and not part of CI: run it by hand to see how the engine
behaves on a small generated batch. It builds the batch inside a scratch folder,
runs the engine scan and anonymization in a fresh child process, and prints one JSON
document with per-phase CPU time, files per second and peak resident memory.

Results depend on the host, its load and the generated shape. CPU time (user plus
system time of the child process) is the primary figure because wall time is
inflated by other load. Nothing here describes clinical data.

Writes only inside the folder given by --scratch-dir (a fresh run-* subfolder that is
removed afterwards unless --keep is given). Refuses sizes above the caps below.
"""
import argparse
import importlib.util
import json
import os
import platform
import random
import resource
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO / 'engine'

# Hard caps. Sizes above these are refused, not clamped.
MAX_FILES = 600
MAX_BYTES = 64 * 1024 ** 2          # estimated pixel + contour payload
MAX_ROWS = 256
MAX_ROIS = 20
MAX_POINTS = 5000
MAX_PATIENTS = 20
MAX_SLICES = 100
FREE_SPACE_RESERVE = 2 * 1024 ** 3  # refuse if less than this would remain free

PRESETS = {
    'default': dict(patients=2, slices=10, rows=64, rois=3, points=100),
    # RTSTRUCT-heavy: many decimal-string values per file.
    'ds-heavy': dict(patients=2, slices=5, rows=32, rois=10, points=2000),
}
SHAPE_KEYS = ('patients', 'slices', 'rows', 'rois', 'points')


class Refusal(SystemExit):
    pass


def refuse(message):
    print(json.dumps({'refused': message}), file=sys.stderr)
    raise Refusal(2)


def plan(shape):
    """Return (file_count, estimated_bytes) for a shape, or refuse."""
    for key, cap in (('patients', MAX_PATIENTS), ('slices', MAX_SLICES), ('rows', MAX_ROWS),
                     ('rois', MAX_ROIS), ('points', MAX_POINTS)):
        if shape[key] < 1:
            refuse(f'{key} must be at least 1')
        if shape[key] > cap:
            refuse(f'{key}={shape[key]} exceeds the cap of {cap}')
    files = shape['patients'] * (2 * shape['slices'] + 1)
    image_bytes = 2 * shape['patients'] * shape['slices'] * (shape['rows'] ** 2 * 2 + 4096)
    contour_bytes = shape['patients'] * shape['rois'] * shape['slices'] * (shape['points'] * 24 + 512)
    total = image_bytes + contour_bytes
    if files > MAX_FILES:
        refuse(f'{files} files exceeds the cap of {MAX_FILES}')
    if total > MAX_BYTES:
        refuse(f'estimated {total} bytes exceeds the cap of {MAX_BYTES}')
    return files, total


def check_storage(scratch, estimated):
    usage = shutil.disk_usage(scratch)
    # Generated input plus one anonymized copy, with headroom.
    needed = estimated * 3 + FREE_SPACE_RESERVE
    if usage.free < needed:
        refuse('not enough free space for the scratch directory')
    guard = os.environ.get('STORAGE_GUARD') or shutil.which('storage-guard')
    if guard:
        result = subprocess.run([guard, 'check', '--path', str(scratch)], capture_output=True)
        if result.returncode != 0:
            refuse('storage-guard check refused the scratch directory')


def load_example():
    spec = importlib.util.spec_from_file_location('example_batch', REPO / 'examples' / 'generate_batch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate(destination, shape, seed):
    """Create a synthetic CT/MR/RTSTRUCT batch. Returns (file_count, byte_count)."""
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence
    gb = load_example()
    rng = random.Random(seed)
    destination.mkdir(parents=True)
    for p in range(1, shape['patients'] + 1):
        patient, name = f'{p:05d}', f'SYNTHETIC^PATIENT{p}'
        base = destination / patient
        for sub in ('CT', 'MR', 'RT'):
            (base / sub).mkdir(parents=True)
        cts = []
        for modality in ('CT', 'MR'):
            for i in range(1, shape['slices'] + 1):
                ds = gb.image(patient, name, modality)
                sop = gb.uid(f'{patient}/{modality}/instance/{i}')
                ds.SOPInstanceUID = sop
                ds.file_meta.MediaStorageSOPInstanceUID = sop
                ds.InstanceNumber = i
                ds.ImagePositionPatient = [0, 0, float(i)]
                ds.Rows = ds.Columns = shape['rows']
                ds.PixelData = rng.randbytes(shape['rows'] ** 2 * 2)
                ds.save_as(base / modality / f'{modality}_{i:04d}.dcm', enforce_file_format=True)
                if modality == 'CT':
                    cts.append(ds)
        rt = gb.structure(patient, name, cts[0])
        rt.SOPInstanceUID = gb.uid(f'{patient}/RTSTRUCT/instance/1')
        rt.file_meta.MediaStorageSOPInstanceUID = rt.SOPInstanceUID
        rois, roi_contours = [], []
        for number in range(1, shape['rois'] + 1):
            roi = Dataset()
            roi.ROINumber = number
            roi.ROIName = f'Synthetic ROI {number}'
            roi.ReferencedFrameOfReferenceUID = cts[0].FrameOfReferenceUID
            roi.ROIGenerationAlgorithm = 'MANUAL'
            rois.append(roi)
            contours = []
            for ct in cts:
                contour = Dataset()
                contour.ContourGeometricType = 'CLOSED_PLANAR'
                contour.NumberOfContourPoints = shape['points']
                values = []
                for _ in range(shape['points']):
                    values += ['%.3f' % rng.uniform(-100, 100), '%.3f' % rng.uniform(-100, 100),
                               '%.3f' % float(ct.InstanceNumber)]
                contour.ContourData = values
                ref = Dataset()
                ref.ReferencedSOPClassUID = ct.SOPClassUID
                ref.ReferencedSOPInstanceUID = ct.SOPInstanceUID
                contour.ContourImageSequence = Sequence([ref])
                contours.append(contour)
            rc = Dataset()
            rc.ReferencedROINumber = number
            rc.ContourSequence = Sequence(contours)
            roi_contours.append(rc)
        rt.StructureSetROISequence = Sequence(rois)
        rt.ROIContourSequence = Sequence(roi_contours)
        rt.save_as(base / 'RT' / 'RTSTRUCT_0001.dcm', enforce_file_format=True)
    paths = [p for p in destination.rglob('*.dcm')]
    return len(paths), sum(p.stat().st_size for p in paths)


def peak_rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == 'darwin' else value * 1024  # Linux reports KiB


def cpu():
    return time.process_time()


def worker(source, destination, journal):
    """Child process: import, scan, then run. Prints one JSON object."""
    t0 = cpu()
    sys.path.insert(0, str(ENGINE_DIR))
    sys.dont_write_bytecode = True
    import engine
    t_import = cpu()
    marks = {}

    def progress(event, **values):
        marks.setdefault(event + ':first', cpu())
        marks[event + ':last'] = cpu()
    records, _patients, _excluded = engine.scan(str(source))
    t_scan = cpu()
    files = len(records)
    del records
    t_run0 = cpu()
    engine.run(str(source), str(destination), progress=progress, journal=str(journal))
    t_run1 = cpu()
    audit_first, audit_last = marks.get('audit_progress:first'), marks.get('audit_progress:last')
    process_end = marks.get('progress:last', t_run1)
    audit = (audit_last - audit_first) if audit_first is not None else None
    print(json.dumps(dict(
        files=files,
        cpu_seconds=dict(
            import_engine=t_import - t0,
            scan_only=t_scan - t_import,
            run_total=t_run1 - t_run0,
            run_through_last_progress=process_end - t_run0,
            run_audit_span=audit,
            run_after_last_progress=t_run1 - process_end,
        ),
        process_cpu_seconds_total=t_run1 - t0,
        peak_rss_bytes=peak_rss_bytes(),
    )))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--scratch-dir', type=Path, help='existing or new folder for all generated data')
    parser.add_argument('--preset', choices=sorted(PRESETS), default='default')
    for key in SHAPE_KEYS:
        parser.add_argument('--' + key, type=int, help=f'override preset (cap in the script source)')
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--keep', action='store_true', help='keep the generated run folder')
    parser.add_argument('--worker', nargs=3, metavar=('SRC', 'DST', 'JOURNAL'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(*map(Path, args.worker))
    if args.scratch_dir is None:
        refuse('--scratch-dir is required')
    shape = dict(PRESETS[args.preset])
    for key in SHAPE_KEYS:
        if getattr(args, key) is not None:
            shape[key] = getattr(args, key)
    files, estimated = plan(shape)
    scratch = args.scratch_dir.absolute()
    scratch.mkdir(parents=True, exist_ok=True)
    check_storage(scratch, estimated)
    run_dir = scratch / ('run-' + uuid.uuid4().hex[:8])
    run_dir.mkdir()
    try:
        t = time.perf_counter()
        file_count, byte_count = generate(run_dir / 'input', shape, args.seed)
        generate_wall = time.perf_counter() - t
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        t = time.perf_counter()
        child = subprocess.run(
            [sys.executable, '-B', str(Path(__file__).resolve()), '--worker',
             str(run_dir / 'input'), str(run_dir / 'output'), str(run_dir / 'journal' / 'op.json')],
            capture_output=True, text=True)
        wall = time.perf_counter() - t
        if child.returncode != 0:
            print(json.dumps({'error': 'worker failed', 'returncode': child.returncode}), file=sys.stderr)
            return 1
        result = json.loads(child.stdout.strip().splitlines()[-1])
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        child_cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        run_cpu = result['cpu_seconds']['run_total']
        scan_cpu = result['cpu_seconds']['scan_only']
        report = dict(
            synthetic_data=True,
            manual_benchmark_not_a_gate=True,
            preset=args.preset, shape=shape, seed=args.seed,
            files=file_count, input_bytes=byte_count,
            host=dict(python=platform.python_version(), system=platform.system(), machine=platform.machine(),
                      load_average=list(os.getloadavg()) if hasattr(os, 'getloadavg') else None),
            cpu_seconds=result['cpu_seconds'],
            child_total_cpu_seconds=child_cpu,
            files_per_second_cpu=dict(
                scan_only=file_count / scan_cpu if scan_cpu > 0 else None,
                full_run_including_scan_and_audit=file_count / run_cpu if run_cpu > 0 else None,
            ),
            peak_rss_bytes=result['peak_rss_bytes'],
            wall_seconds_for_reference_only=dict(engine_child=wall, generation=generate_wall),
        )
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if not args.keep:
            shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
