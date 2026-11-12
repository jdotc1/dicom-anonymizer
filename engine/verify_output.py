"""Source-free, read-only verification of an already published output tree.

This re-runs the engine's own header and dataset audit over every output file,
checks the tree layout against ``anonymization-report.json``, checks that
RTSTRUCT references resolve inside the same patient folder, and computes a
SHA-256 tree digest that can be compared out-of-band.

It is NOT an independent conformance check: it reuses the engine's audit, so a
defect in that audit is shared. The source-UID leak check needs the source and
is never performed here; the terminal event says so. Errors use fixed text and
never contain a path or a value from the tree.

The engine module is passed in (not imported) so exception classes and policy
data are those of the running engine, whether it was started as a script or
loaded by filename.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

REPORT_NAME = 'anonymization-report.json'
REPORT_LIMIT = 16 * 1024 * 1024
_PATIENT = re.compile(r'[0-9]{1,64}\Z')
_SERIES = re.compile(r'Series_([0-9]{4})\Z')
_IMAGE = re.compile(r'Image_([0-9]{6})\.dcm\Z')

E_ROOT = 'The output folder to verify must be an existing local folder, without symbolic links.'
E_UNREADABLE = 'The output folder could not be read for verification. Check that it is available and readable.'
E_REPORT = 'The output folder has no readable anonymization-report.json of the expected form.'
E_POLICY = 'The report policy version differs from this engine, or the report does not record a passed self-audit.'
E_SIDECARS = 'The output contains JSON sidecar output, which output verification does not cover.'
E_LAYOUT = 'The output folder layout is not the engine layout: an unexpected, missing or non-regular entry was found.'
E_COUNTS = 'The output folder does not match the file, series or patient counts in anonymization-report.json.'
E_UNREAD = 'An output DICOM file could not be re-read for verification.'
E_IDENTITY = 'An output file does not carry its patient folder identifier as PatientName and PatientID.'
E_PRIVATE = 'An output file contains private attributes.'
E_DATES = 'An output file contains dates or times.'
E_AUDIT = 'The output audit found retained identifying metadata or an invalid file header in an output file.'
E_STRUCTURE = 'Output files disagree with their folders: series membership, duplicate instance UIDs or shared patient frames.'
E_CLOSURE = 'An RTSTRUCT file references an image instance that is not present in the same patient folder.'

NOT_PERFORMED = 'not_performed'


def _fail(engine, message):
    return engine.BatchError(message)


def _lstat(engine, path):
    try:
        return path.lstat()
    except OSError:
        raise _fail(engine, E_UNREADABLE) from None


def _listing(engine, path):
    try:
        with os.scandir(path) as entries:
            return sorted(((entry.name, entry.path) for entry in entries))
    except OSError:
        raise _fail(engine, E_UNREADABLE) from None


def _load_report(engine, root):
    path = root / REPORT_NAME
    info = _lstat(engine, path) if os.path.lexists(path) else None
    if info is None or not stat.S_ISREG(info.st_mode) or info.st_size > REPORT_LIMIT:
        raise _fail(engine, E_REPORT)
    try:
        data = path.read_bytes()
        report = json.loads(data.decode('utf-8'))
    except (OSError, ValueError):
        raise _fail(engine, E_REPORT) from None
    if not isinstance(report, dict) or not isinstance(report.get('patients'), list):
        raise _fail(engine, E_REPORT)
    for key in ('patient_count', 'total_files'):
        if type(report.get(key)) is not int:
            raise _fail(engine, E_REPORT)
    audit = report.get('self_audit')
    if not isinstance(audit, dict) or not isinstance(report.get('policy'), dict):
        raise _fail(engine, E_REPORT)
    return report, hashlib.sha256(data).hexdigest()


def _inventory(engine, root):
    """Strictly walk the engine layout; returns {patient: {series_no: [paths]}}."""
    tree = {}
    for name, path in _listing(engine, root):
        info = _lstat(engine, Path(path))
        if name == REPORT_NAME and stat.S_ISREG(info.st_mode):
            continue
        if not stat.S_ISDIR(info.st_mode) or not _PATIENT.match(name):
            raise _fail(engine, E_LAYOUT)
        series_map = {}
        for series_name, series_path in _listing(engine, path):
            match = _SERIES.match(series_name)
            series_info = _lstat(engine, Path(series_path))
            if not match or not stat.S_ISDIR(series_info.st_mode):
                raise _fail(engine, E_LAYOUT)
            images = []
            for image_name, image_path in _listing(engine, series_path):
                image_match = _IMAGE.match(image_name)
                image_info = _lstat(engine, Path(image_path))
                if not image_match or not stat.S_ISREG(image_info.st_mode):
                    raise _fail(engine, E_LAYOUT)
                images.append((int(image_match.group(1)), Path(image_path)))
            if [number for number, _ in images] != list(range(1, len(images) + 1)) or not images:
                raise _fail(engine, E_LAYOUT)
            series_map[int(match.group(1))] = [path_ for _, path_ in images]
        if sorted(series_map) != list(range(1, len(series_map) + 1)) or not series_map:
            raise _fail(engine, E_LAYOUT)
        tree[name] = series_map
    if not tree:
        raise _fail(engine, E_LAYOUT)
    return tree


def _check_report(engine, report, tree):
    if report['policy'].get('version') != engine.POLICY['version']:
        raise _fail(engine, E_POLICY)
    audit = report['self_audit']
    if audit.get('result') != 'passed':
        raise _fail(engine, E_POLICY)
    sidecars = report.get('json_sidecars')
    if isinstance(sidecars, dict) and (sidecars.get('enabled') or sidecars.get('files_written')):
        raise _fail(engine, E_SIDECARS)
    total = sum(len(paths) for series in tree.values() for paths in series.values())
    declared = {}
    for item in report['patients']:
        if (not isinstance(item, dict) or type(item.get('files')) is not int or
                type(item.get('series')) is not int or not isinstance(item.get('id'), str) or item['id'] in declared):
            raise _fail(engine, E_REPORT)
        declared[item['id']] = (item['files'], item['series'])
    actual = {patient: (sum(len(p) for p in series.values()), len(series)) for patient, series in tree.items()}
    if (declared != actual or report['patient_count'] != len(tree) or report['total_files'] != total or
            audit.get('files_audited') != total):
        raise _fail(engine, E_COUNTS)
    return total


def _digest(path):
    sha = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            sha.update(block)
    return sha.hexdigest()


def _classify(ds, patient, engine):
    """Give common tampering distinct fixed messages before the engine's own audit decides."""
    for element in ds.iterall():
        if element.tag.is_private:
            raise _fail(engine, E_PRIVATE)
    for element in ds.iterall():
        if element.VR in ('DA', 'DT', 'TM') and any(engine.audit_values(element)):
            raise _fail(engine, E_DATES)
    for keyword in ('PatientName', 'PatientID'):
        if keyword not in ds or engine.audit_values(ds.data_element(keyword)) != [patient]:
            raise _fail(engine, E_IDENTITY)
    if str(ds.get('PatientIdentityRemoved', '')).strip() != 'YES':
        raise _fail(engine, E_AUDIT)


def _referenced_instances(ds):
    found = set()
    for element in ds.iterall():
        if element.keyword == 'ReferencedSOPInstanceUID':
            values = element.value if element.VM > 1 else [element.value]
            found.update(str(v).strip() for v in values if v)
    return found


def verify(root, engine, progress=None):
    """Verify a published output tree; raise engine.BatchError (fixed text) on any failure."""
    emit = progress or (lambda *_a, **_k: None)
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise _fail(engine, E_ROOT)
    report, report_digest = _load_report(engine, root)
    tree = _inventory(engine, root)
    total = _check_report(engine, report, tree)
    emit('scan', patients=report['patients'], total_files=total, excluded_files=0)
    emit('audit_progress', audited_files=0, total_files=total)

    sops, frame_owners, rt_refs = {}, {}, []
    tree_hash = hashlib.sha256()
    tree_hash.update(f'{REPORT_NAME}\0{report_digest}\n'.encode())
    audited = rtstruct_files = 0
    for patient in sorted(tree):
        sops[patient] = set()
        for series_no in sorted(tree[patient]):
            series_uid = None
            for path in tree[patient][series_no]:
                try:
                    ds = engine.checked_read(path)
                    engine.validate(ds)
                    file_digest = _digest(path)
                except engine.BatchError:
                    raise _fail(engine, E_UNREAD) from None
                except OSError:
                    raise _fail(engine, E_UNREAD) from None
                _classify(ds, patient, engine)
                try:
                    engine.audit_file_header(ds)
                    # An empty set, never None: the file-meta loop is not None-guarded.
                    engine.audit_dataset(ds, patient, set())
                except engine.BatchError:
                    raise _fail(engine, E_AUDIT) from None
                sop, series = str(ds.SOPInstanceUID), str(ds.SeriesInstanceUID)
                if series_uid is None:
                    series_uid = series
                if series != series_uid or sop in sops[patient] or any(sop in other for other in sops.values()):
                    raise _fail(engine, E_STRUCTURE)
                try:
                    engine.claim_patient_frames(ds, patient, frame_owners)
                except engine.BatchError:
                    raise _fail(engine, E_STRUCTURE) from None
                sops[patient].add(sop)
                if str(ds.get('Modality', '')) == 'RTSTRUCT':
                    rtstruct_files += 1
                    rt_refs.append((patient, _referenced_instances(ds)))
                rel = path.relative_to(root).as_posix()
                tree_hash.update(f'{rel}\0{file_digest}\n'.encode())
                audited += 1
                if audited % 10 == 0 or audited == total:
                    emit('audit_progress', audited_files=audited, total_files=total)
    references = 0
    for patient, refs in rt_refs:
        references += len(refs)
        if not refs <= sops[patient]:
            raise _fail(engine, E_CLOSURE)
    result = dict(
        files_audited=audited, patients=len(tree), report_policy_version=report['policy']['version'],
        rtstruct_files=rtstruct_files, rtstruct_references_resolved=references,
        report_cross_check='passed', tree_sha256=tree_hash.hexdigest(),
        source_uid_check=NOT_PERFORMED, independent_conformance_check=NOT_PERFORMED)
    emit('verify_complete', **result)
    return result
