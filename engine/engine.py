#!/usr/bin/env python3
"""Local bulk DICOM pseudonymization. Source data is never modified."""
import argparse
import errno
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import tempfile
import time
import unicodedata
import warnings
from dataclasses import dataclass

import pydicom
from pydicom.uid import generate_uid

warnings.filterwarnings('ignore', module='pydicom')
logging.getLogger('pydicom').disabled = True
POLICY = {
    'version': '2.0-build5', 'modalities': ['MR', 'CT', 'RTSTRUCT'],
    'patient_identity': 'Exact numeric patient folder identifier in PatientName and PatientID',
    'private_tags': 'removed recursively', 'dates_times': 'cleared recursively',
    'free_text': 'LT/ST/UT text, URLs and PS3.15 Annex E Basic Profile identifying attributes removed or cleared recursively',
    'uids': 'non-class UIDs consistently remapped; shared patient-relative frame UIDs across patient folders rejected',
    'filenames': 'generated independently of original names',
    'retained': 'SeriesDescription, ProtocolName, SequenceName, ContrastBolusAgent, SoftwareVersions, Manufacturer, pixel data, contour geometry, quantitative measurements, ROI names and observation labels',
    'limitation': 'Pseudonymization; not certified DICOM confidentiality-profile conformance. Review retained image, contour, and ROI content before sharing.'
}

class BatchError(Exception):
    def __init__(self, message, *, cancelled=False, cleanup_failed=False, staging_path=None, output_published=False,
                 output_issue=None, required_bytes=None, available_bytes=None):
        super().__init__(message)
        self.cancelled = cancelled
        self.cleanup_failed = cleanup_failed
        self.staging_path = staging_path
        self.output_published = output_published
        self.output_issue = output_issue
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes


CANCELLED = 'Processing was cancelled. No completed output was published.'
PROCESSING_FAILURE = ('Processing failed. Check input integrity, output permissions and available '
                      'disk space; no completed output was published.')


def output_error(error):
    """Classify only errors from a known destination operation; never source reads."""
    if error.errno in {errno.ENOSPC, errno.EDQUOT}:
        issue = 'space'
        message = 'The output location ran out of available space or its storage quota was reached. Free space or choose another output location, then retry.'
    elif error.errno in {errno.EACCES, errno.EPERM, errno.EROFS}:
        issue = 'permissions'
        message = 'The output location cannot be written to. Check its permissions or choose another writable output location, then retry.'
    elif error.errno in {errno.ENOENT, errno.ENOTDIR, errno.ENODEV, errno.ENXIO, errno.ESTALE, errno.EIO}:
        issue = 'unavailable'
        message = 'The output location could not be accessed. Check that it is available or choose another output location, then retry.'
    elif error.errno == errno.EEXIST:
        issue = 'conflict'
        message = 'The output folder already exists. Choose a new output folder, then retry.'
    else:
        issue = 'unknown'
        message = 'The output location could not be used. Check the location or choose another writable output location, then retry.'
    return BatchError(message + ' No completed output was published.', output_issue=issue)


def destination_operation(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except OSError as error:
        raise output_error(error) from None


def approximate_storage(value):
    # Use a human-readable estimate; events retain the original byte counts.
    for unit, scale in [('TiB', 1024 ** 4), ('GiB', 1024 ** 3), ('MiB', 1024 ** 2)]:
        if value >= scale:
            return f'{value / scale:.1f} {unit}'
    return f'{value} bytes'


class Cancellation:
    """Defer cancellation across atomic publication and while recovering a failed batch."""
    def __init__(self):
        self.deferred = False
        self.requested = False

    def cancel(self, _signum=None, _frame=None):
        self.requested = True
        if not self.deferred:
            raise BatchError(CANCELLED, cancelled=True)

    def begin_publication(self):
        # The boundary starts before rename: an interrupt cannot split a successful
        # rename from its complete event. A request already received still cancels.
        self.deferred = True
        if self.requested:
            raise BatchError(CANCELLED, cancelled=True)


class StagingOwnershipError(OSError):
    pass


def remove_staging(staging, identity):
    """Remove only the directory created by this operation, never a replacement."""
    try:
        current = staging.lstat()
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) != identity or not stat.S_ISDIR(current.st_mode):
        raise StagingOwnershipError('The staging directory was replaced.')
    shutil.rmtree(staging)


@dataclass
class Record:
    path: Path
    patient: str
    series: tuple
    sop: str
    identity: str
    signature: tuple
    estimated_output_bytes: int | None = None


def emit(event, **values):
    print(json.dumps(dict(event=event, **values)), flush=True)


def fingerprint(path):
    s = path.stat(follow_symlinks=False)
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


INPUT_CHANGED = 'The input changed during scanning or processing. Keep input files unchanged and retry.'


def require_stable_input(path, signature):
    """Detect ordinary concurrent changes; this is not an atomic filesystem snapshot."""
    try:
        stable = not path.is_symlink() and fingerprint(path) == signature
    except OSError:
        stable = False
    if not stable:
        raise BatchError(INPUT_CHANGED)


def stable_read(path, signature):
    require_stable_input(path, signature)
    try:
        ds = checked_read(path)
    except Exception as error:
        if isinstance(error, BatchError) and error.cancelled:
            raise
        # Prefer actionable recovery when a concurrent change caused the read failure.
        # Preserve the original failure (including cancellation) if identity is stable.
        require_stable_input(path, signature)
        raise
    require_stable_input(path, signature)
    return ds


def checked_read(path):
    if path.is_symlink():
        raise BatchError('Symbolic links are not supported. Use a local copy of the input folders.')
    try:
        if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
            raise BatchError('Input files cannot be read. Check permissions and available local storage.')
        try:
            ds = pydicom.dcmread(path)
        except pydicom.errors.InvalidDicomError:
            ds = pydicom.dcmread(path, force=True)
            if not all(ds.get(k) for k in ('SOPClassUID', 'SOPInstanceUID', 'StudyInstanceUID', 'SeriesInstanceUID')):
                raise ValueError('Unrecognized dataset')
        # Force lazy elements to decode before accepting input.
        list(ds.iterall())
        return ds
    except BatchError:
        raise
    except Exception:
        raise BatchError('A DICOM file could not be read. Repair or remove the malformed input before retrying.') from None


def validate(ds):
    if str(ds.get('Modality', '')) not in POLICY['modalities']:
        raise BatchError('An unsupported modality was found. This version accepts MR, CT and RTSTRUCT only.')
    for key in ('SOPClassUID', 'SOPInstanceUID', 'StudyInstanceUID', 'SeriesInstanceUID'):
        value = ds.get(key)
        if not value or not pydicom.uid.UID(str(value)).is_valid:
            raise BatchError('A DICOM file lacks a valid required class, instance, study or series UID.')
    if getattr(ds, 'file_meta', None) is None or not ds.file_meta.get('TransferSyntaxUID'):
        raise BatchError('A DICOM file lacks a transfer syntax. Repair the input before retrying.')
    for element in ds.iterall():
        if element.keyword == 'BurnedInAnnotation' and str(element.value).strip().upper() == 'YES':
            raise BatchError('Burned-in annotations are declared. Review and clean the image content before retrying.')
        if 0x6000 <= element.tag.group <= 0x601E:
            raise BatchError('An overlay was found. Review and remove potentially identifying overlays before retrying.')


# Patient-relative spatial identities, including nested RTSTRUCT/registration references.
# Synchronization/equipment frame identifiers do not imply patient-relative geometry.
PATIENT_FRAME_UID_KEYS = frozenset({
    'FrameOfReferenceUID', 'ReferencedFrameOfReferenceUID',
    'RelatedFrameOfReferenceUID', 'SourceFrameOfReferenceUID',
})
FRAME_COLLISION = ('The same patient frame of reference occurs in multiple patient folders. '
                   'Resolve the folder assignments before retrying.')


def claim_patient_frames(ds, patient, owners):
    for element in ds.iterall():
        if element.VR != 'UI' or element.keyword not in PATIENT_FRAME_UID_KEYS:
            continue
        values = element.value if element.VM > 1 else [element.value]
        for value in values:
            uid = str(value).strip() if value is not None else ''
            if uid and owners.setdefault(uid, patient) != patient:
                raise BatchError(FRAME_COLLISION)


# Folder-assignment reports name patient folder numbers and batch-relative locations so the files can be
# found in Finder, but never absolute paths or UIDs. Real exports often name subfolders and files after the
# patient, a record number, a date or a UID, so every subfolder name, file name and series label passes
# through redact() first. Names are compared in folded form (composed, accents and case removed), because
# HFS+ volumes store file names decomposed and exporters often drop accents or replace them with '_'.
CONFLICT_LIMIT = 5        # conflicts described in detail; any others are listed by folder number
MESSAGE_LINES = 15        # keeps the message readable in the app's error area
MASK = '…'
IDENTITY_KEYS = ('PatientName', 'PatientID', 'OtherPatientIDs', 'OtherPatientNames', 'PatientBirthName', 'AccessionNumber')
_WORD = re.compile(r'[^\W_]+')
_SEPARATOR = re.compile(r'[\W_]+')
_DATE_OR_NUMBER = re.compile(
    r'\d+(?:\.\d+){2,}'                                   # UIDs and other dotted numbers
    r'|\d{4}[-_./ ]\d{1,2}[-_./ ]\d{1,2}'                 # 2026-09-14
    r'|\d{1,2}[-_./ ]\d{1,2}[-_./ ]\d{2,4}'               # 09.14.2026
    r'|\d{1,2}[-_. ]?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_. ]?\d{2,4}'
    r'|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_. ]?\d{1,2}[-_., ]+\d{2,4}'
    r'|\d{6,}',                                           # compact dates, times and record numbers
    re.IGNORECASE)
# Letters that Unicode does not decompose but exporters commonly transliterate.
_TRANSLITERATE = str.maketrans({'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'Æ': 'AE', 'œ': 'oe', 'Œ': 'OE', 'ł': 'l', 'Ł': 'L',
                                'đ': 'd', 'Đ': 'D', 'ð': 'd', 'Ð': 'D', 'þ': 'th', 'Þ': 'TH', 'ı': 'i'})


def fold(text):
    """Comparable form of a name: composed or decomposed, with or without accents, in any case."""
    text = unicodedata.normalize('NFKD', str(text).translate(_TRANSLITERATE))
    return ''.join(char for char in text if not unicodedata.combining(char)).casefold()


def identifying(word, terms):
    """True if a folded word contains a source name/ID term, or is a fragment (3+ letters) of one."""
    fragment = len(word) >= 3 and not word.isdigit()
    for term in terms:
        # Short Latin terms (such as a two-letter surname) must match a whole word; CJK names have no separators.
        if word == term or ((len(term) >= 3 or not term.isascii()) and term in word) or (fragment and word in term):
            return True
    return False


def _mask(text, terms):
    """The text in composed (NFC) form and, for each character, whether it must be hidden."""
    text = unicodedata.normalize('NFC', str(text))
    hidden, named = [False] * len(text), [False] * len(text)
    for match in _DATE_OR_NUMBER.finditer(text):
        start, end = match.span()
        hidden[start:end] = [True] * (end - start)
    words = list(_WORD.finditer(text))
    for match in words:
        if identifying(fold(match.group()), terms):
            start, end = match.span()
            hidden[start:end] = named[start:end] = [True] * (end - start)
    # A one- or two-letter word between two name words is hidden too: an initial, or the rest of a name whose
    # accented letter an exporter replaced with '_' (GARC_A^JOS_).
    for before, match, after in zip(words, words[1:], words[2:]):
        if len(match.group()) <= 2 and named[before.end() - 1] and named[after.start()]:
            start, end = match.span()
            hidden[start:end] = [True] * (end - start)
    for match in _SEPARATOR.finditer(text):
        start, end = match.span()
        if 0 < start and end < len(text) and hidden[start - 1] and hidden[end]:
            hidden[start:end] = [True] * (end - start)
    return text, hidden


def redact(text, terms):
    """Mask words containing or forming part of a source name/ID, and anything shaped like a date, long number or UID."""
    text, hidden = _mask(text, terms)
    out, previous = [], False
    for flag, char in zip(hidden, text):
        if not flag:
            out.append(char)
        elif not previous:
            out.append(MASK)
        previous = flag
    return ''.join(out)


def lead(text, terms):
    """The folded hidden text a name starts with (such as a patient name and record number), or None. Never shown."""
    text, hidden = _mask(text, terms)
    if not hidden or not hidden[0]:
        return None
    return fold(text[:hidden.index(False)] if False in hidden else text)


def finder_order(name):
    """Approximates Finder's name order: case- and accent-insensitive, numbers by value, punctuation first."""
    return [(1, int(run), '') if run[0].isdecimal() else (2, 0, run) if run.isalpha() else (0, 0, run)
            for run in re.findall(r'\d+|\D', fold(name))]


def ordinal(number):
    return f'{number}{"th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")}'


def join_words(items):
    items = [str(item) for item in items]
    return ', '.join(items[:-1]) + ' and ' + items[-1] if len(items) > 1 else ''.join(items)


def plural(count, noun, nouns=None):
    return f'{count} {noun if count == 1 else nouns or noun + "s"}'


def folder_list(folders, limit=8):
    folders = list(folders)
    if len(folders) > limit:
        return ', '.join(folders[:limit]) + f' and {len(folders) - limit} more'
    return join_words(folders)


def name_difference(names):
    """How differently recorded source patient names differ, described without showing any of them."""
    def components(name):
        groups = [[' '.join(part.split()) for part in group.split('^')] for group in str(name).split('=')]
        for group in groups:
            while group and not group[-1]:
                group.pop()
        while groups and not groups[-1]:
            groups.pop()
        return groups
    forms = [components(name) for name in names]
    if all(form == forms[0] for form in forms):
        return 'the names differ only in spaces or empty ^ components'
    folded = [[[fold(part) for part in group] for group in form] for form in forms]
    if all(form == folded[0] for form in folded):
        return 'the names differ only in capitalization or accents'
    if all(len(form) == 1 and len(form[0]) >= 2 and form[0][:2] == folded[0][0][:2] for form in folded):
        cased = '' if all(form[0][:2] == forms[0][0][:2] for form in forms) else ' and in capitalization or accents'
        return f'the names differ after the family and given names, such as a middle name, prefix or suffix{cased}'
    return 'the names are spelled differently'


class FolderConflicts:
    """Collects folder-assignment problems while scan() walks the batch and explains them in one message.

    Four problems stop a batch: one study in several patient folders, one source patient ID in several
    patient folders, more than one source patient ID or name inside one folder, and the same SOP instance
    stored twice. The message reports the most fundamental of these in detail (folders, batch-relative
    locations, file counts, series and a suggested fix) and names any unrelated remaining problem briefly.
    """

    def __init__(self, source):
        self.source = source
        self.terms = set()      # folded fragments of source names and IDs, used only for masking
        self.series = {}        # series UID -> (modality, series number, description)
        self.studies = {}       # study UID -> {patient folder}
        self.ids = {}           # source PatientID -> {patient folder: [records]}
        self.names = {}         # source PatientName -> {patient folder: [records]}
        self.first = {}         # SOP instance UID -> first record stored
        self.duplicates = []    # (first record, repeated record)
        self.mixed = {}         # patient folder -> ('id' or 'name', {source value: [records]})
        self.folder = []        # (record, PatientName) for the patient folder being walked
        self.shown = {}         # file or folder name -> masked name
        self.listings = {}      # folder -> the names Finder shows in it

    def add(self, record, ds, name):
        for key in IDENTITY_KEYS:
            words = _WORD.findall(unicodedata.normalize('NFC', str(ds.get(key) or '')))
            self.terms.update(fold(word) for word in words if len(word) > 1)
        self.series.setdefault(record.series[1], (str(ds.Modality), str(ds.get('SeriesNumber') or '').strip(),
                                                  str(ds.get('SeriesDescription') or '').strip()))
        self.studies.setdefault(record.series[0], set()).add(record.patient)
        if record.sop in self.first:
            self.duplicates.append((self.first[record.sop], record))
        else:
            self.first[record.sop] = record
        self.folder.append((record, name))

    def close_folder(self, patient):
        entries, self.folder = self.folder, []
        for record, name in entries:
            if record.identity:
                self.ids.setdefault(record.identity, {}).setdefault(patient, []).append(record)
            if name:
                self.names.setdefault(name, {}).setdefault(patient, []).append(record)
        ids = {record.identity for record, _ in entries if record.identity}
        names = {name for _, name in entries if name}
        if len(ids) > 1 or len(names) > 1:
            grouping, groups = 'id' if len(ids) > 1 else 'name', {}
            for record, name in entries:
                groups.setdefault(record.identity if grouping == 'id' else name, []).append(record)
            self.mixed[patient] = (grouping, groups)

    # -- Locations and series, always masked -----------------------------------------------------------
    def parts(self, record):
        return record.path.relative_to(self.source).parts

    def masked(self, name):
        if name not in self.shown:
            self.shown[name] = redact(name, self.terms)
        return self.shown[name]

    def twins(self, location):
        """(level, other names) for each part of a location that looks the same as a sibling once masked."""
        found = []
        for level in range(1, len(location)):
            parent = self.source.joinpath(*location[:level])
            if parent not in self.listings:
                try:
                    # Finder hides dot files (.DS_Store, AppleDouble companions), so they cannot be confused.
                    self.listings[parent] = [name for name in os.listdir(parent) if not name.startswith('.')]
                except OSError:
                    self.listings[parent] = []
            same = [name for name in self.listings[parent]
                    if name != location[level] and self.masked(name) == self.masked(location[level])]
            if same:
                found.append((level, same))
        return found

    def tell_apart(self, location, level, same, like=None):
        """(hint, certain) telling one part of a location from look-alike siblings, without showing what was masked.

        like = (patient folder, folder locations of the same patient's files). Misfiled files usually carry that
        patient's name and record number at the start of their folder name, which the look-alikes do not.
        Otherwise the hint gives the position in name order, which is less certain.
        """
        name, group = location[level], [location[level]] + same
        kind = 'folders' if self.source.joinpath(*location[:level + 1]).is_dir() else 'files'
        if like:
            folder, references = like
            keys = {lead(part, self.terms) for reference in references for part in reference[1:]} - {None}
            if lead(name, self.terms) in keys and not any(lead(other, self.terms) in keys for other in same):
                return (f'of {len(group)} {kind} that look alike here, the one whose full name starts like the '
                        f'folder names in {folder}'), True
        position = sorted(group, key=lambda other: (finder_order(other), other)).index(name) + 1
        return f'the {ordinal(position)} of {len(group)} {kind} that look alike here, sorted by name', False

    def locate(self, location, like=None):
        """(masked location, hint, certain). The hint tells look-alike folders or files apart."""
        if len(location) == 1:
            return f'directly inside {location[0]}', '', True
        shown = '/'.join((location[0],) + tuple(self.masked(part) for part in location[1:]))
        hints = [self.tell_apart(location, level, same, like) for level, same in self.twins(location)]
        return shown, '; '.join(hint for hint, _ in hints), all(certain for _, certain in hints)

    def where(self, location, like=None):
        shown, hint, _ = self.locate(location, like)
        return f'{shown} ({hint})' if hint else shown

    def clear(self, locations, like=None):
        """True if every location can be found without guessing: unique once masked, or told apart by like."""
        return all(self.locate(location, like)[2] for location in locations)

    def file_path(self, record, hint=True):
        return self.where(self.parts(record)) if hint else self.locate(self.parts(record))[0]

    def by_location(self, records):
        groups = {}
        for record in records:
            groups.setdefault(self.parts(record)[:-1], []).append(record)
        return sorted(groups.items())

    def series_label(self, uid):
        modality, number, description = self.series[uid]
        number, description = redact(number, self.terms), redact(description, self.terms).strip()
        if len(description) > 40:
            description = description[:39].rstrip() + MASK
        label = f'{modality} series {number}' if number else f'{modality} series'
        return f'{label} "{description}"' if description else label

    def details(self, records, count=True):
        counts = {}
        for record in records:
            counts[record.series[1]] = counts.get(record.series[1], 0) + 1
        def order(uid):
            number = self.series[uid][1]
            return (int(number) if number.isascii() and number.isdigit() else float('inf'), self.series[uid][2])
        labels = {}             # identical labels (same modality, number and description) are merged
        for uid in sorted(counts, key=order):
            label = self.series_label(uid)
            labels[label] = labels.get(label, 0) + 1
        shown = [label if n == 1 else f'{n} {label}' for label, n in list(labels.items())[:2]]
        rest = sum(list(labels.values())[2:])
        if rest:
            shown.append(f'and {rest} more series')
        return ', '.join(([plural(len(records), 'file')] if count else []) + shown)

    def describe(self, records, like=None):
        """Where a group of files is, how many there are and which series, e.g. '90002/RT (1 file, RTSTRUCT series 1)'."""
        groups = self.by_location(records)
        details = self.details(records)
        if len(groups) == 1:
            shown, hint, _ = self.locate(groups[0][0], like)
            return f'{shown} ({details}; {hint})' if hint else f'{shown} ({details})'
        if len(groups) <= 3:
            return f'{join_words(self.where(location, like) for location, _ in groups)} ({details})'
        return f'{records[0].patient}, {len(groups)} locations ({details})'

    def bullet(self, records, label='', note='', like=None):
        return f'• {label}{self.describe(records, like)}{note}'

    def places(self, locations, like=None):
        """Prose form of locations: 'in 90002/RT and directly inside 90002'."""
        return join_words(self.where(location) if len(location) == 1 else f'in {self.where(location, like)}'
                          for location in locations)

    # -- The four problems ------------------------------------------------------------------------------
    def split_report(self, split, records):
        files, folder_ids, copies = {}, {}, {}
        for record in records:
            if record.series[0] in split:
                files.setdefault(record.series[0], {}).setdefault(record.patient, []).append(record)
            if record.identity:
                folder_ids.setdefault(record.patient, {}).setdefault(record.series[0], set()).add(record.identity)
        for first, again in self.duplicates:
            if first.patient != again.patient:
                copies.setdefault(first.sop, set()).update((first.patient, again.patient))
        studies = sorted(split, key=lambda study: (sorted(split[study]), str(files[study][min(files[study])][0].path)))
        single, blocks, unclear = len(studies) == 1, [], False
        for number, study in enumerate(studies, 1):
            folders = files[study]
            def foreign(folder):
                # The study's source patient IDs appear nowhere else in this folder.
                ids = folder_ids.get(folder, {})
                others = set().union(*(values for key, values in ids.items() if key != study))
                return bool(ids.get(study) and others and not ids[study] & others)
            def weight(folder):
                # Hedged heuristic for the study's home: consistent patient ID, then images (not only RTSTRUCT), then most files.
                return (not foreign(folder), any(self.series[r.series[1]][0] != 'RTSTRUCT' for r in folders[folder]),
                        len(folders[folder]))
            ranked = sorted(folders, key=weight, reverse=True)
            home = ranked[0] if weight(ranked[0]) > weight(ranked[1]) else None
            unclear |= home is None
            if home is None:
                lines = [] if single else [f'Study {number}, in {join_words(sorted(folders))} (unclear which folder is right):']
                lines += [self.bullet(folders[folder]) for folder in sorted(folders)]
                blocks.append((sorted(folders), lines))
                continue
            # Misfiled files are named like the home folder's files, which tells them from look-alike folders.
            like = (home, [self.parts(record)[:-1] for record in folders[home]])
            lines = [self.bullet(folders[home])] if single else [f'Study {number} in {self.describe(folders[home])}, also in:']
            strays = [folder for folder in sorted(folders) if folder != home]
            stray_locations, all_copies = [], True
            for folder in strays:
                groups = self.by_location(folders[folder])
                for location, group in groups[:3]:
                    copied = sum(home in copies.get(r.sop, ()) for r in group)
                    all_copies &= copied == len(group)
                    note = (f' (copies of files in {home})' if copied == len(group)
                            else f' ({copied} are copies of files in {home})' if copied else '')
                    lines.append(self.bullet(group, note=', likely misfiled' + note, like=like))
                if len(groups) > 3:
                    all_copies = False
                    lines.append(f'• and {len(groups) - 3} more locations in {folder}, also likely misfiled')
                stray_locations += [location for location, _ in groups]
            blocks.append((sorted(folders), lines))
        if not single:
            headline = (f'Images from {len(studies)} studies are split across patient folders '
                        f'{folder_list(sorted(set().union(*split.values())))}.')
            fix = ('To fix: for each study, move the files marked "likely misfiled" into the folder named on that study\'s '
                   '"Study N in …" line. They are marked because they hold fewer of the study\'s files, only its RTSTRUCT, '
                   'or a source patient ID that differs from the rest of their folder. If a study\'s folders are the same '
                   'person, combine them under one number instead.'
                   + (' Where nothing is marked, decide which patient the study belongs to.' if unclear else '')
                   + ' Then choose Check Again.')
            return headline, blocks, None, fix, 'split studies'
        everyone = join_words(sorted(files[studies[0]]))
        headline = f'Patient folders {everyone} contain images from the same study.'
        if len(files[studies[0]]) > 3:
            everyone = 'these folders'
        why = 'One study must stay in one patient folder, or the output would link different patient numbers.'
        if home is None:
            if all(r.sop in copies for group in folders.values() for r in group):
                fix = (f'To fix: {everyone} hold copies of the same images. Keep them only in the folder of the patient they '
                       f'belong to and delete the other copies. If {everyone} are the same person, also combine the folders '
                       'under one number. Then choose Check Again.')
            else:
                fix = (f'To fix: decide which patient this study belongs to; {everyone} hold equal parts of it, so it is unclear. '
                       'If they are the same person, combine the folders under one number. Otherwise move the study\'s files '
                       'into the folder of the patient it belongs to. Then choose Check Again.')
            return headline, blocks, why, fix, 'split studies'
        where = self.places(stray_locations, like) if len(stray_locations) <= 3 else f'of this study in {join_words(strays)}'
        # Never suggest deleting a folder the user cannot tell apart from a look-alike: the other one may be the patient's own.
        if all_copies and len(stray_locations) <= 3 and self.clear(stray_locations, like):
            fix = (f'To fix: delete the files {where}; they are copies of files already in {home}. If {everyone} are the '
                   'same person, also combine the folders under one number. Then choose Check Again.')
        else:
            # State every signal that favours the main folder, not only the one that decided it.
            reasons, foreigners = [], [f for f in strays if foreign(f)]
            if len(folders[home]) > max(len(folders[f]) for f in strays):
                reasons.append(f'{home} holds more of this study\'s files')
            elif weight(home)[1] and not all(weight(f)[1] for f in strays):
                reasons.append(f'{home} holds this study\'s images')
            if foreigners and not foreign(home):
                reasons.append(('they carry' if foreigners == strays else f'this study\'s files in {join_words(foreigners)} carry')
                               + ' a different source patient ID from the other files in '
                               + (join_words(foreigners) if len(foreigners) <= 3 else 'their folders'))
            if all_copies:
                reasons.append(f'they are copies of files already in {home}')
            reason = join_words(reasons) or f'{home} holds more of this study\'s files than {ranked[1]}'
            fix = (f'To fix: move the files {where} into {home}. They most likely belong there, because {reason}. '
                   f'If {everyone} are the same person, combine the folders under one number instead. Then choose Check Again.')
        return headline, blocks, why, fix, 'split studies'

    def shared_report(self, shared, records):
        files = {}
        for record in records:
            if record.identity in shared:
                files.setdefault(record.identity, {}).setdefault(record.patient, []).append(record)
        keys = sorted(shared, key=lambda value: sorted(shared[value]))
        blocks = []
        for value in keys:
            folders = sorted(files[value])
            lines = [] if len(keys) == 1 else [f'Same source patient ID in {join_words(folders)}:']
            blocks.append((folders, lines + [self.bullet(files[value][folder]) for folder in folders]))
        if len(keys) == 1:
            everyone = join_words(blocks[0][0])
            headline = f'Patient folders {everyone} contain images with the same source patient ID.'
            why = 'One source patient ID in more than one folder would give one person more than one patient number.'
            fix = (f'To fix: if {everyone} are the same person, combine the folders under one number. If they are different '
                   'people, the source export gave two patients the same patient ID, so check the export. Then choose Check Again.')
        else:
            headline = (f'{len(keys)} source patient IDs each appear in more than one patient folder: '
                        f'{folder_list(sorted(set().union(*shared.values())))}.')
            why = None
            fix = ('To fix: for each group, if its folders are the same person, combine them under one number; if they are '
                   'different people, the source export gave two patients the same patient ID, so check the export. '
                   'Then choose Check Again.')
        return headline, blocks, why, fix, 'shared patient IDs'

    def mixed_report(self, folders):
        labels = {}
        def label(grouping, value):
            if not value:
                return 'no patient ID' if grouping == 'id' else 'no patient name'
            return labels.setdefault((grouping, value), f'identity {len(labels) + 1}')
        blocks, variants, headline, why, fix = [], [], '', None, ''
        for folder in folders:
            grouping, groups = self.mixed[folder]
            index = self.ids if grouping == 'id' else self.names
            elsewhere = {value: sorted(set(index.get(value, {})) - {folder}) for value in groups if value}
            # Keep the identity not found in any other folder, then the one with the most files.
            named = sorted(elsewhere, key=lambda value: (bool(elsewhere[value]), -len(groups[value])))
            ids = {r.identity for records in groups.values() for r in records if r.identity}
            studies = [{r.series[0] for r in groups[value]} for value in named]
            same_study = any(a & b for i, a in enumerate(studies) for b in studies[i + 1:])
            # One person recorded two ways. Moving files apart would only trade this stop for a shared-ID or split-study one.
            variant = (grouping == 'name' and len(ids) == 1) or same_study
            if variant:
                variants.append(folder)
            lines = [] if len(folders) == 1 else [f'In {folder}' + (' (likely one patient recorded two ways):' if variant else ':')]
            values = named + ([''] if '' in groups else [])
            limit = 10 if len(folders) == 1 else 4      # keeps a folder of many patients within the message's line budget
            rest = values[limit - 1:] if len(values) > limit else []
            for value in values[:len(values) - len(rest)]:
                note, like = '', None
                if value and elsewhere[value]:
                    note = f', also in {join_words(elsewhere[value])}'
                    like = (elsewhere[value][0], [self.parts(r)[:-1] for r in index[value][elsewhere[value][0]]])
                lines.append(self.bullet(groups[value], label=f'{label(grouping, value)}: ', note=note, like=like))
            if rest:
                lines.append(f'• and {len(rest)} more identities in {folder} '
                             f'({plural(sum(len(groups[value]) for value in rest), "file")})')
            blocks.append(([folder], lines))
            if len(folders) > 1:
                continue
            kind = 'IDs' if grouping == 'id' else 'names'
            headline = f'Patient folder {folder} contains images with {len(named)} different source patient {kind}'
            if variant:
                shared_id = grouping == 'name' and len(ids) == 1
                headline += ' under one source patient ID.' if shared_id else ' in one study.'
                what = 'patient name' if grouping == 'name' else 'patient ID'
                detail = f' ({name_difference(named)})' if grouping == 'name' else ''
                blocked = ('the same ID would then be in two folders' if shared_id
                           else 'the study would then be split across folders')
                why = 'The app cannot tell whether differently recorded patient details belong to one person, so it stops.'
                fix = (f'To fix: these files {"share one source patient ID" if shared_id else "belong to the same study"}, so '
                       f'they are most likely one person whose {what} was recorded differently{detail}. Moving files into '
                       f'another folder will not clear this, because {blocked}. Correct the {what} in the source system so '
                       'all files match and re-export this patient'
                       + ('; if they are different people, correct the patient ID instead' if shared_id else '')
                       + '. Then choose Check Again.')
                continue
            headline += '.'
            why = 'Every file in a patient folder receives that folder\'s number, so each folder must hold one patient.'
            moves, new = [], [label(grouping, value) for value in named[1:] if not elsewhere[value]]
            for value in named[1:]:
                if elsewhere[value]:
                    target = (f'{elsewhere[value][0]} (which already holds that patient)' if len(elsewhere[value]) == 1
                              else f'one of {join_words(elsewhere[value])} (which already hold that patient)')
                    moves.append(f'the {label(grouping, value)} files into {target}')
            if len(new) == 1:
                moves.append(f'the {new[0]} files into a new numeric folder')
            elif new:
                span = join_words(new) if len(new) <= 3 else f'{new[0]} to {new[-1]}'
                moves.append(f'the files of {span} each into a new numeric folder of its own')
            fix = (f'To fix: give each identity its own numeric folder. Keep {label(grouping, named[0])} in {folder} and '
                   f'move {join_words(moves)}.')
            if '' in groups:
                fix += f' Check which patient the files with {label(grouping, "")} belong to.'
            counts = {}
            for records in groups.values():
                for location in {self.parts(r)[:-1] for r in records}:
                    counts[location] = counts.get(location, 0) + 1
            shared_places = [self.where(location) for location in sorted(counts) if counts[location] > 1]
            if shared_places:
                fix += (f' {join_words(shared_places[:2])} {"holds" if len(shared_places) == 1 else "hold"} files of more '
                        'than one identity, so separate those files by series first.')
            fix += ' Then choose Check Again.'
        if len(folders) > 1:
            headline = f'Patient folders {folder_list(folders)} each contain images with more than one source patient identity.'
            steps = []
            if len(variants) < len(folders):
                steps.append(('In the other folders' if variants else 'In each folder') + ', keep the first identity listed and '
                             'move the others into a new numeric folder, or into the "also in" folder that already holds that patient.')
            if variants:
                steps.append(f'In {join_words(variants)}, the files are most likely one patient whose details were recorded '
                             'differently; moving files will not clear this, so correct the patient details in the source system '
                             'and re-export.')
            fix = 'To fix: ' + ' '.join(steps) + ' Then choose Check Again.'
        return headline, blocks, why, fix, 'folders'

    def duplicate_report(self, duplicates, records):
        pairs, sizes = {}, {}
        for first, again in duplicates:
            pairs.setdefault((self.parts(first)[:-1], self.parts(again)[:-1]), []).append((first, again))
        for record in records:
            location = self.parts(record)[:-1]
            sizes[location] = sizes.get(location, 0) + 1
        blocks, spare = [], []
        for (original, repeat), group in sorted(pairs.items()):
            first, again = group[0]
            series = self.details([r for pair in group for r in pair], count=False)
            # In a group the example only illustrates the pattern; the folders locate the files.
            example = f'{self.file_path(first, hint=False)} and {self.file_path(again, hint=False)}'
            if len(group) == 1:
                paths = f'{self.file_path(first)} and {self.file_path(again)}'
                # Look-alike file names carry a position hint in parentheses, so the series goes first.
                line = f'• {series}: {paths}' if paths != example else f'• {paths} ({series})'
            elif original == repeat:
                line = f'• {len(group)} images are stored twice in {self.where(original)} ({series}), for example {example}'
            else:
                line = (f'• {len(group)} files in {self.where(repeat)} repeat files in {self.where(original)} ({series}), '
                        f'for example {example}')
            # A location holding nothing but these copies can simply be deleted, if it cannot be mistaken for another.
            for location in (repeat, original) if original != repeat else ():
                if sizes[location] == len(group) and self.clear([location]):
                    spare.append(self.where(location))
                    break
            blocks.append((sorted({first.patient, again.patient}), [line]))
        folders = sorted({r.patient for pair in duplicates for r in pair})
        what = 'the same image twice' if len(duplicates) == 1 else f'{len(duplicates)} duplicate images'
        headline = (f'Patient folder {folders[0]} contains {what}.' if len(folders) == 1
                    else f'Patient folders {folder_list(folders)} contain {what}.')
        fix = 'To fix: remove one of the two copies' + (' of each image' if len(duplicates) > 1 else '')
        if spare:
            fix += (f' ({join_words(spare[:3])} {"holds" if len(spare) == 1 else "hold"} only copies, so '
                    f'{"it" if len(spare) == 1 else "they"} can be deleted)')
        return headline, blocks, None, fix + ', then choose Check Again.', 'duplicate groups'

    # -- One message -------------------------------------------------------------------------------------
    def message(self, records):
        """Return one plain-text report of the batch's folder-assignment problems, or None if there are none."""
        split = {study: folders for study, folders in self.studies.items() if len(folders) > 1}
        shared = {value: set(folders) for value, folders in self.ids.items() if len(folders) > 1}
        mixed, duplicates = sorted(self.mixed), list(self.duplicates)
        # Report the most fundamental problem in full. Problems it causes are not repeated.
        if split:
            report = self.split_report(split, records)
            covered = set().union(*split.values())
            mixed = [folder for folder in mixed if folder not in covered]
            shared = {value: folders for value, folders in shared.items() if not folders <= covered}
            duplicates = [(a, b) for a, b in duplicates if a.patient == b.patient or a.series[0] not in split]
        elif mixed:
            report = self.mixed_report(mixed)
            shared = {value: folders for value, folders in shared.items() if len(folders - set(mixed)) > 1}
            mixed = []
        elif shared:
            report, shared = self.shared_report(shared, records), {}
        elif duplicates:
            report, duplicates = self.duplicate_report(duplicates, records), []
        else:
            return None
        return self.compose(*report, also=self.also_found(mixed, shared, duplicates))

    @staticmethod
    def also_found(mixed, shared, duplicates):
        notes = []
        if mixed:
            notes.append(f'{folder_list(mixed)} {"holds" if len(mixed) == 1 else "each hold"} more than one source patient identity')
        if shared:
            groups = sorted(sorted(folders) for folders in shared.values())
            notes.append(f'{plural(len(groups), "source patient ID")} shared between folders ('
                         + '; '.join(join_words(group) for group in groups[:3]) + ('; …' if len(groups) > 3 else '') + ')')
        if duplicates:
            notes.append(f'duplicate images in {folder_list(sorted({r.patient for pair in duplicates for r in pair}))}')
        if not notes:
            return None
        return 'Also found: ' + '; '.join(notes) + '. Choose Check Again after the fix above to see the details.'

    @staticmethod
    def compose(headline, blocks, why, fix, noun, also=None):
        budget = MESSAGE_LINES - 2 - bool(why) - bool(also)
        shown = []
        for index, (_, lines) in enumerate(blocks):
            reserve = 1 if index + 1 < len(blocks) else 0
            if shown and (len(shown) == CONFLICT_LIMIT or sum(map(len, shown)) + len(lines) + reserve > budget):
                break
            shown.append(lines)
        text = [headline] + [line for lines in shown for line in lines]
        rest = blocks[len(shown):]
        if rest:
            separator = '; ' if any(len(folders) > 1 for folders, _ in rest) else ', '
            text.append(f'• and {len(rest)} more {noun}: ' + separator.join(join_words(folders) for folders, _ in rest[:6])
                        + (separator + MASK if len(rest) > 6 else ''))
        return '\n'.join(text + [line for line in (why, fix, also) if line])


def scan(source, progress=None):
    source = Path(source).absolute()
    if source.is_symlink() or not source.is_dir():
        raise BatchError('Select an existing local batch folder, without symbolic links.')
    files_examined, folders_examined = 0, 1
    last_progress = None

    def scan_progress(*, force=False):
        nonlocal last_progress
        if progress is None:
            return
        now = time.monotonic()
        if force or last_progress is None or now - last_progress >= 0.1:
            progress('scan_progress', files_examined=files_examined,
                     folders_examined=folders_examined)
            last_progress = now

    # Counts describe traversal work already encountered, including excluded files.
    # There is no known total while the single input walk is still in progress.
    scan_progress(force=True)
    records, excluded, patients = [], 0, {}
    # Folder-assignment problems are collected over the whole batch and reported together after the walk.
    conflicts = FolderConflicts(source)
    frame_owners = {}
    frame_conflict = False
    def appledouble(path, header=None):
        # macOS writes "._<name>" resource-fork companions on exFAT/FAT/SMB volumes.
        if not path.name.startswith('._'):
            return False
        if header is None:
            with path.open('rb') as stream:
                header = stream.read(4)
        return header[:4] == b'\x00\x05\x16\x07'
    try:
        children = sorted(source.iterdir(), key=lambda p: p.name)
        for patient in children:
            if patient.is_symlink():
                raise BatchError('Symbolic links are not supported. Use a local copy of the input folders.')
            root_file = patient.is_file()
            if root_file:
                files_examined += 1
                scan_progress()
            if root_file and (patient.name == '.DS_Store' or appledouble(patient)):
                excluded += 1
                continue
            if not patient.is_dir() or not re.fullmatch(r'[0-9]+', patient.name):
                raise BatchError('The batch folder must contain only numeric patient folders. Move unrelated root items elsewhere.')
            if len(patient.name) > 64:
                raise BatchError('A patient folder identifier exceeds 64 characters. Use a numeric identifier that fits DICOM patient fields.')
            local = []
            def walk_error(_):
                raise BatchError('An input folder cannot be listed. Check read permissions and retry.')
            for root, dirs, files in os.walk(patient, followlinks=False, onerror=walk_error):
                folders_examined += 1
                scan_progress()
                dirs.sort(); files.sort()
                if any((Path(root) / d).is_symlink() for d in dirs):
                    raise BatchError('Symbolic links are not supported. Use a local copy of the input folders.')
                for filename in files:
                    files_examined += 1
                    scan_progress()
                    path = Path(root) / filename
                    if path.is_symlink():
                        raise BatchError('Symbolic links are not supported. Use a local copy of the input folders.')
                    if not stat.S_ISREG(path.stat(follow_symlinks=False).st_mode):
                        raise BatchError('Input files cannot be read. Check permissions and available local storage.')
                    signature = fingerprint(path)
                    with path.open('rb') as stream:
                        header = stream.read(132)
                    if appledouble(path, header):
                        excluded += 1
                        continue
                    if header[128:132] != b'DICM' and path.suffix.lower() not in ('.dcm', '.dicom'):
                        # A valid DICOM dataset can lack both extension and Part 10 preamble.
                        try:
                            probe = pydicom.dcmread(path, force=True, stop_before_pixels=True)
                            candidate = any(probe.get(k) for k in ('SOPClassUID', 'SOPInstanceUID', 'StudyInstanceUID', 'SeriesInstanceUID'))
                        except BatchError:
                            raise
                        except Exception:
                            candidate = False
                        if not candidate:
                            excluded += 1
                            continue
                    ds = stable_read(path, signature)
                    validate(ds)
                    name = str(ds.get('PatientName', '')).strip()
                    identity = str(ds.get('PatientID', '')).strip()
                    try:
                        claim_patient_frames(ds, patient.name, frame_owners)
                    except BatchError:
                        frame_conflict = True
                    record = Record(path, patient.name, (str(ds.StudyInstanceUID), str(ds.SeriesInstanceUID)), str(ds.SOPInstanceUID), identity, signature)
                    record.estimated_output_bytes = estimate_output_bytes(ds, record.signature[2], patient.name)
                    conflicts.add(record, ds, name)
                    local.append(record)
            if not local:
                raise BatchError('A patient folder contains no readable DICOM files.')
            conflicts.close_folder(patient.name)
            records.extend(local)
            patients[patient.name] = {'id': patient.name, 'files': len(local), 'series': len({r.series for r in local})}
    except BatchError:
        raise
    except OSError:
        raise BatchError('Input files cannot be read. Check permissions and available local storage.') from None
    scan_progress(force=True)
    if not records:
        raise BatchError('No numeric patient folders containing DICOM data were found.')
    problem = conflicts.message(records)
    if problem:
        # Fail closed: nothing has been written yet, and run() never starts staging.
        raise BatchError(problem)
    if frame_conflict:
        raise BatchError(FRAME_COLLISION)
    return records, list(patients.values()), excluded

# Free text with potential identity; ROI labels and observation labels intentionally retained.
REMOVE_KEYS = {
    'AccessionNumber', 'StudyID', 'InstitutionName', 'InstitutionAddress',
    'InstitutionalDepartmentName', 'StationName', 'DeviceSerialNumber',
    'StudyDescription', 'ImageComments',
    'DerivationDescription', 'AdditionalPatientHistory', 'PatientComments',
    'RequestAttributesSequence', 'IssuerOfPatientID', 'IssuerOfPatientIDQualifiersSequence',
    'OtherPatientIDsSequence', 'OtherPatientIDs', 'PatientAddress', 'PatientTelephoneNumbers',
    'PatientTelecomInformation', 'MedicalRecordLocator', 'EthnicGroup', 'Occupation',
    'MilitaryRank', 'BranchOfService', 'CountryOfResidence', 'RegionOfResidence',
    'AdmittingDiagnosesDescription', 'RequestedProcedureDescription',
    'PerformedProcedureStepDescription', 'ScheduledProcedureStepDescription',
    'RequestedProcedureID', 'ScheduledProcedureStepID', 'PerformedProcedureStepID',
    'ClinicalTrialSponsorName', 'ClinicalTrialProtocolID', 'ClinicalTrialProtocolName',
    'ClinicalTrialSiteID', 'ClinicalTrialSiteName', 'ClinicalTrialSubjectID',
    'ClinicalTrialSubjectReadingID', 'DigitalSignaturesSequence', 'MACParametersSequence',
    'OriginalAttributesSequence', 'EncryptedAttributesSequence', 'DataSetTrailingPadding',
    'CommentsOnThePerformedProcedureStep', 'ImagingServiceRequestComments',
    'OrderCallbackPhoneNumber', 'OrderEntererLocation', 'PerformedLocation',
    'PerformedStationAETitle', 'PerformedStationName', 'PerformedProcedureTypeDescription',
    'ReasonForTheImagingServiceRequest', 'ReasonForTheRequestedProcedure',
    'RequestedProcedureComments', 'RequestedProcedureLocation', 'RequestingService',
    'SecondaryCaptureDeviceID', 'StudyComments', 'StructureSetName', 'StructureSetDescription',
    'ROIDescription', 'ROIObservationDescription', 'PositionReferenceIndicator',
    # Build 4: remaining PS3.15 Annex E Table E.1-1 Basic Profile identifiers (X/Z/D/U).
    'AdmissionID', 'IssuerOfAdmissionIDSequence', 'ServiceEpisodeID', 'ServiceEpisodeDescription',
    'CurrentPatientLocation', 'PatientInstitutionResidence', 'PatientState', 'SpecialNeeds',
    'VisitComments', 'DischargeDiagnosisDescription', 'AdmittingDiagnosesCodeSequence',
    'ReferencedPatientAliasSequence', 'ScheduledPatientInstitutionResidence',
    'ReferringPhysicianAddress', 'ReferringPhysicianTelephoneNumbers',
    'PersonAddress', 'PersonTelephoneNumbers', 'PersonTelecomInformation',
    'InstitutionCodeSequence', 'InstitutionalDepartmentTypeCodeSequence',
    'ReferringPhysicianIdentificationSequence', 'ConsultingPhysicianIdentificationSequence',
    'PerformingPhysicianIdentificationSequence', 'PhysiciansOfRecordIdentificationSequence',
    'PhysiciansReadingStudyIdentificationSequence', 'RequestingPhysicianIdentificationSequence',
    'OperatorIdentificationSequence', 'ScheduledPerformingPhysicianIdentificationSequence',
    'HumanPerformerCodeSequence', 'HumanPerformerOrganization', 'ActualHumanPerformersSequence',
    'AuthorObserverSequence', 'ParticipantSequence', 'CustodialOrganizationSequence',
    'VerifyingObserverIdentificationCodeSequence', 'ContentCreatorIdentificationCodeSequence',
    'InterpretationApproverSequence', 'DistributionAddress',
    'ReasonForStudy', 'RequestedContrastAgent', 'ScheduledStationName',
    'ScheduledProcedureStepLocation', 'FillerOrderNumberImagingServiceRequest',
    'PlacerOrderNumberImagingServiceRequest', 'InterpretationText',
    'InterpretationDiagnosisDescription', 'InterpretationID', 'ResultsID', 'ResultsIDIssuer',
    'ResultsComments', 'TopicTitle', 'TopicSubject', 'TopicAuthor', 'TopicKeywords',
    'ModifiedAttributesSequence', 'ContentSequence', 'IconImageSequence',
    'AcquisitionComments', 'AcquisitionDeviceProcessingDescription', 'ROIGenerationDescription',
    'FrameComments', 'DeviceDescription', 'DetectorID', 'GantryID', 'PlateID', 'CassetteID',
    'StorageMediaFileSetID', 'TextValue', 'TextString', 'TextComments', 'LabelText',
    'ContainerIdentifier', 'ContainerDescription', 'IssuerOfTheContainerIdentifierSequence',
    'SpecimenAccessionNumber', 'SpecimenDescriptionSequence', 'ProtocolContextSequence',
    'RetrieveURL', 'RetrieveURI', 'ClinicalTrialCoordinatingCenterName', 'ClinicalTrialSeriesID',
    'ClinicalTrialSeriesDescription', 'ClinicalTrialTimePointID',
    'ClinicalTrialTimePointDescription', 'ClinicalTrialProtocolEthicsCommitteeName',
    'ClinicalTrialProtocolEthicsCommitteeApprovalNumber',
    'TimezoneOffsetFromUTC', 'ModifyingDeviceID', 'ModifyingDeviceManufacturer',
    'ModifiedImageDescription', 'AuthorizationEquipmentCertificationNumber',
    'ReferencedDigitalSignatureSequence', 'ReferencedSOPInstanceMACSequence',
    'PatientTransportArrangements', 'ScheduledHumanPerformersSequence', 'ScheduledStudyLocation',
    'SourceSerialNumber', 'ContributionDescription', 'IdentifyingComments'
}


# Structural dictionary identifiers are not patient-specific identifiers.
PRESERVE_UID_KEYS = {
    'TransferSyntaxUID', 'ImplementationClassUID', 'CodingSchemeUID',
    'ContextGroupExtensionCreatorUID', 'MappingResourceUID', 'ContextUID',
    'SOPClassesInStudy', 'SOPClassesSupported', 'RelatedGeneralSOPClassUID',
    'OriginalSpecializedSOPClassUID'
}


# Numeric policy additions: PS3.15 2026d E.1-1, resolved against the shipped
# README, except ContrastBolusAgent retains the existing product behavior.
# Numeric tags also cover entries absent from pydicom 3.0.2.
# This selected tag set defines the runtime behavior; no external proposal is imported.
CLEAR_TAGS = {
    0x00081088,  # PyramidDescription
    0x00120022,  # IssuerOfClinicalTrialProtocolID
    0x00120032,  # IssuerOfClinicalTrialSiteID
    0x00120041,  # IssuerOfClinicalTrialSubjectID
    0x00120043,  # IssuerOfClinicalTrialSubjectReadingID
    0x00120055,  # IssuerOfClinicalTrialTimePointID
    0x00120073,  # IssuerOfClinicalTrialSeriesID
    0x00160071,  # GPSLatitudeRef
    0x00160072,  # GPSLatitude
    0x00160073,  # GPSLongitudeRef
    0x00160074,  # GPSLongitude
    0x00160075,  # GPSAltitudeRef
    0x00160076,  # GPSAltitude
    0x00160079,  # GPSStatus
    0x0016007A,  # GPSMeasureMode
    0x0016007B,  # GPSDOP
    0x0016007C,  # GPSSpeedRef
    0x0016007D,  # GPSSpeed
    0x0016007E,  # GPSTrackRef
    0x0016007F,  # GPSTrack
    0x00160080,  # GPSImgDirectionRef
    0x00160081,  # GPSImgDirection
    0x00160083,  # GPSDestLatitudeRef
    0x00160084,  # GPSDestLatitude
    0x00160085,  # GPSDestLongitudeRef
    0x00160086,  # GPSDestLongitude
    0x00160087,  # GPSDestBearingRef
    0x00160088,  # GPSDestBearing
    0x00160089,  # GPSDestDistanceRef
    0x0016008A,  # GPSDestDistance
    0x0016008E,  # GPSDifferential
    0x00181005,  # GeneratorID
    0x00181011,  # HardcopyCreationDeviceID
    0x001811BB,  # AcquisitionFieldOfViewLabel
    0x00189367,  # XRaySourceID
    0x00189371,  # XRayDetectorID
    0x00189937,  # RequestedSeriesDescription
    0x00200027,  # PyramidLabel
    0x00320012,  # StudyIDIssuer
    0x00380011,  # IssuerOfAdmissionID
    0x00380061,  # IssuerOfServiceEpisodeID
    0x003A0020,  # MultiplexGroupLabel
    0x003A0203,  # ChannelLabel
    0x003A020C,  # ChannelDerivationDescription
    0x00400012,  # PreMedication
    0x00400551,  # SpecimenIdentifier
    0x00400600,  # SpecimenShortDescription
    0x004006FA,  # SlideIdentifier
    0x00403001,  # ConfidentialityConstraintOnPatientDataDescription
    0x0040A027,  # VerifyingOrganization
    0x0040A354,  # TelephoneNumberTrial
    0x0040B03F,  # MontageChannelLabel
    0x0050001B,  # ContainerComponentID
    0x006A0005,  # AnnotationGroupLabel
    0x0072005F,  # SelectorASValue
    0x00720066,  # SelectorLOValue
    0x0072006C,  # SelectorSHValue
    0x04000563,  # ModifyingSystem
    0x04000564,  # SourceOfPreviousValues
    0x04000565,  # ReasonForTheAttributeModification
    0x04000600,  # InstanceOriginStatus
    0x30020121,  # PositionAcquisitionTemplateName
    0x3004007F,  # DoseCalculationModelName
    0x300A0002,  # RTPlanLabel
    0x300A0003,  # RTPlanName
    0x300A000B,  # TreatmentSites
    0x300A0016,  # DoseReferenceDescription
    0x300A0072,  # FractionGroupDescription
    0x300A00B2,  # TreatmentMachineName
    0x300A0216,  # SourceManufacturer
    0x300A0608,  # TreatmentPositionGroupLabel
    0x300A0611,  # RTAccessoryHolderSlotID
    0x300A0615,  # RTAccessoryDeviceSlotID
    0x300A0619,  # RadiationDoseIdentificationLabel
    0x300A0623,  # RadiationDoseInVivoMeasurementLabel
    0x300A062A,  # RTToleranceSetLabel
    0x300A067C,  # RadiationGenerationModeLabel
    0x300A079A,  # DisplacementReferenceLabel
    0x300C0113,  # ReasonForOmissionDescription
    0x3010001B,  # DeviceAlternateIdentifier
    0x3010002D,  # DeviceLabel
    0x30100033,  # UserContentLabel
    0x30100034,  # UserContentLongLabel
    0x30100035,  # EntityLabel
    0x30100036,  # EntityName
    0x30100038,  # EntityLongLabel
    0x30100054,  # RTPrescriptionLabel
    0x30100056,  # RTTreatmentApproachLabel
    0x30100077,  # TreatmentSite
    0x40080202,  # InterpretationIDIssuer
}
REMOVE_TAGS = {
    0x00081301,  # PrincipalDiagnosisCodeSequence
    0x00081302,  # PrimaryDiagnosisCodeSequence
    0x00081303,  # SecondaryDiagnosesCodeSequence
    0x00081304,  # HistologicalDiagnosesCodeSequence
    0x00120023,  # OtherClinicalTrialProtocolIDsSequence
    0x0016002B,  # MakerNote
    0x0016004B,  # DeviceSettingDescription
    0x00160070,  # GPSVersionID
    0x0016008B,  # GPSProcessingMethod
    0x0016008C,  # GPSAreaInformation
    0x0018100A,  # UDISequence
    0x00185011,  # TransducerIdentificationSequence
    0x00321067,  # ReasonForVisitCodeSequence
    0x00340001,  # FlowIdentifierSequence
    0x00380064,  # IssuerOfServiceEpisodeIDSequence
    0x00400555,  # AcquisitionContextSequence
    0x00400562,  # IssuerOfTheSpecimenIdentifierSequence
    0x00400610,  # SpecimenPreparationSequence
    0x0040100A,  # ReasonForRequestedProcedureCodeSequence
    0x00401011,  # IntendedRecipientsOfResultsIdentificationSequence
    0x00401101,  # PersonIdentificationCodeSequence
    0x00404025,  # ScheduledStationNameCodeSequence
    0x00404027,  # ScheduledStationGeographicLocationCodeSequence
    0x00404028,  # PerformedStationNameCodeSequence
    0x00404030,  # PerformedStationGeographicLocationCodeSequence
    0x0040A073,  # VerifyingObserverSequence
    0x0040A358,  # VerbalSourceIdentifierCodeSequenceTrial
    0x0040B020,  # WaveformAnnotationSequence
    0x00700001,  # GraphicAnnotationSequence
    0x04000310,  # CertifiedTimestamp
    0x04000404,  # MAC
    0x04000551,  # NonconformingModifiedAttributesSequence
    0x04000552,  # NonconformingDataElementValue
    0x3006004D,  # ROICreatorSequence
    0x3006004E,  # ROIInterpreterSequence
    0x30100081,  # PrescriptionNotesSequence
    0x40080118,  # ResultsDistributionListSequence
    0xFFFCFFFC,  # DataSetTrailingPadding
}


def clean(ds, patient, uid_map):
    ds.remove_private_tags()
    for element in list(ds):
        keyword = element.keyword
        if element.tag in REMOVE_TAGS or element.tag.group & 0xFF00 == 0x5000:
            del ds[element.tag]
        elif keyword in {'PatientName', 'PatientID'}:
            element.value = patient
        elif element.VR in ('PN', 'DA', 'DT', 'TM', 'AE'):
            # Keep required type-2 attributes present with empty values.
            element.value = ''
        elif element.VR == 'UN':
            # Public tags pydicom cannot interpret are uninspectable bytes that may carry identity; drop them.
            del ds[element.tag]
        elif keyword == 'StructureSetLabel':
            element.value = 'Structures'
        elif (element.tag.group == 0x0010 and keyword not in {'PatientSex', 'PatientAge', 'PatientSize', 'PatientWeight'}) or keyword in REMOVE_KEYS or element.tag in CLEAR_TAGS or element.VR in ('LT', 'ST', 'UT', 'UR'):
            # Free-text (LT/ST/UT) and URL (UR) values can carry identity; none is in the retention contract.
            if element.VR == 'SQ':
                del ds[element.tag]
            else:
                element.value = ''
        elif element.VR == 'SQ':
            for item in element.value:
                clean(item, patient, uid_map)
        elif element.VR == 'UI' and not ('SOPClassUID' in keyword or keyword in PRESERVE_UID_KEYS):
            def remap(value):
                value = str(value)
                if not value:
                    return ''
                if value not in uid_map:
                    uid_map[value] = generate_uid()
                return uid_map[value]
            element.value = [remap(v) for v in element.value] if element.VM > 1 else remap(element.value)


def _sidecar_call(operation, *args, **kwargs):
    # The app bootstrap puts the engine directory on the isolated runtime path.
    # Import only for explicit opt-in; legacy DICOM-only execution is unchanged.
    import sidecar_deid
    try:
        return operation(*args, **kwargs)
    except sidecar_deid.SidecarDestinationError as error:
        raise output_error(error.os_error) from None
    except sidecar_deid.SidecarError as error:
        raise BatchError(str(error)) from None
    except OSError:
        raise BatchError('JSON sidecar files cannot be read or checked. Keep input unchanged and retry.') from None


def _sidecar_output_operation(operation, *args):
    import sidecar_deid
    try:
        return operation(*args)
    except OSError as error:
        raise output_error(error) from None
    except sidecar_deid.SidecarError as error:
        if isinstance(error.__cause__, OSError):
            raise output_error(error.__cause__) from None
        raise


def _sidecar_scan(source, cancellation, progress=None):
    import sidecar_deid
    return _sidecar_call(sidecar_deid.scan_sidecars, source, cancel_check=lambda: _sidecar_cancel(cancellation), progress=progress)


def _sidecar_cancel(cancellation):
    if cancellation.requested:
        cancellation.cancel()


def _journal_mark(operation, phase, **values):
    if operation is None:
        return
    from operation_journal import JournalError
    try:
        operation.mark(phase, **values)
    except (OSError, JournalError):
        raise BatchError('The local recovery record could not be saved. Check local storage and permissions before retrying.') from None


def run(source, destination, progress=emit, audit=True, *, cancellation=None, clean_json_sidecars=False, journal=None):
    cancellation = cancellation or Cancellation()
    source = Path(source).absolute()
    destination = Path(destination).absolute()
    if destination_operation(destination.exists) or destination_operation(destination.is_symlink):
        raise BatchError('The output folder already exists. Choose a new output folder.', output_issue='conflict')
    src_real = source.resolve()
    dst_real = destination_operation(destination.resolve)
    if src_real == dst_real or src_real in dst_real.parents or dst_real in src_real.parents:
        raise BatchError('The output must be separate from the input folder, with neither inside the other.', output_issue='conflict')
    if not destination_operation(destination.parent.is_dir):
        raise BatchError('The output parent folder does not exist. Choose an existing location.', output_issue='unavailable')
    if journal is not None:
        journal_path = Path(journal).absolute().resolve()
        if journal_path == src_real or src_real in journal_path.parents or journal_path == dst_real or dst_real in journal_path.parents:
            raise BatchError('Recovery records must be stored separately from input and completed output.')
    records, patients, excluded = scan(source, progress=progress)
    sidecars = _sidecar_scan(source, cancellation, progress=progress) if clean_json_sidecars else []
    if clean_json_sidecars:
        excluded = max(0, excluded - len(sidecars))
        progress('scan', patients=patients, total_files=len(records), excluded_files=excluded, sidecar_files=len(sidecars))
        check_disk_space(records, destination.parent, sidecars=sidecars)
    else:
        progress('scan', patients=patients, total_files=len(records), excluded_files=excluded)
        check_disk_space(records, destination.parent)
    staging = None
    staging_identity = None
    publication_succeeded = False
    operation = None
    try:
        if journal is not None:
            from operation_journal import OperationJournal, JournalError
            try:
                operation = OperationJournal(journal, destination)
            except (OSError, JournalError):
                raise BatchError('A local recovery record could not be created. Check local storage and permissions before retrying.') from None
        # Capture ownership before honoring a signal delivered during allocation.
        cancellation.deferred = True
        staging = Path(destination_operation(tempfile.mkdtemp, prefix='.dicom-batch-', dir=destination.parent))
        created = destination_operation(staging.lstat)
        staging_identity = (created.st_dev, created.st_ino)
        _journal_mark(operation, "allocated", staging=staging, identity=staging_identity)
        cancellation.deferred = False
        if cancellation.requested:
            cancellation.cancel()
        uid_map, series_map, counters = {}, {}, {}
        forbidden_uids, written = set(), []
        for index, record in enumerate(records, 1):
            ds = stable_read(record.path, record.signature)
            validate(ds)
            if str(ds.SOPInstanceUID) != record.sop or str(ds.get('PatientID', '')).strip() != record.identity:
                raise BatchError('The input changed during processing. Keep input files unchanged and retry.')
            if audit:
                source_uids(ds, forbidden_uids)
                forbidden_uids.update(str(v) for v in (ds.file_meta.get('MediaStorageSOPInstanceUID'),) if v)
            clean(ds, record.patient, uid_map)
            ds.PatientName = record.patient
            ds.PatientID = record.patient
            ds.PatientIdentityRemoved = 'YES'
            ds.DeidentificationMethod = 'Local bulk metadata pseudonymization v2; review retained content'
            ds.preamble = b'\0' * 128
            # Rebuild file meta to exclude original implementation identifiers and titles.
            transfer = ds.file_meta.TransferSyntaxUID
            ds.file_meta = pydicom.dataset.FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = transfer
            ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
            ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
            patient_series = series_map.setdefault(record.patient, {})
            if record.series not in patient_series:
                patient_series[record.series] = len(patient_series) + 1
            series_number = patient_series[record.series]
            key = (record.patient, series_number)
            counters[key] = counters.get(key, 0) + 1
            folder = staging / record.patient / f'Series_{series_number:04d}'
            destination_operation(folder.mkdir, parents=True, exist_ok=True)
            out_path = folder / f'Image_{counters[key]:06d}.dcm'
            destination_operation(ds.save_as, out_path, enforce_file_format=True)
            written.append((out_path, record.patient))
            if index % 10 == 0 or index == len(records):
                progress('progress', patient_id=record.patient, processed=index, total_files=len(records))
        sidecar_written = []
        if clean_json_sidecars:
            import sidecar_deid
            sidecar_written, sidecar_summary = _sidecar_call(
                sidecar_deid.clean_sidecars_to_staging, sidecars, staging,
                progress=progress, cancel_check=lambda: _sidecar_cancel(cancellation),
                output_operation=_sidecar_output_operation)
        audit_summary = self_audit(staging, written, forbidden_uids, progress=progress) if audit else {'result': 'skipped', 'files_audited': 0}
        if clean_json_sidecars:
            sidecar_audit = _sidecar_call(sidecar_deid.audit_sidecars, staging, sidecar_written,
                                        progress=progress, cancel_check=lambda: _sidecar_cancel(cancellation))
            sidecar_summary = sidecar_summary.with_audit(sidecar_audit.files_audited)
        progress('phase', name='finalizing')
        forbidden_uids = None
        report = {'policy': POLICY, 'software': environment_info(), 'patients': patients,
                  'patient_count': len(patients), 'total_files': len(records), 'excluded_files': excluded,
                  'self_audit': audit_summary,
                  'audit_coverage': audit_coverage(audit_summary, len(written),
                                                   sidecar_summary if clean_json_sidecars else None)}
        if clean_json_sidecars:
            report['excluded_files'] = excluded
            report['json_sidecars'] = sidecar_deid.sidecar_report(sidecar_summary)
        report_path = staging / 'anonymization-report.json'
        destination_operation(report_path.write_text, json.dumps(report, indent=2) + '\n')
        if clean_json_sidecars:
            _sidecar_call(sidecar_deid.seal_staging_inventory, staging,
                          dicom_paths=[path for path, _patient in written],
                          sidecar_paths=[item.output for item in sidecar_written], report_path=report_path,
                          sidecar_expectations=sidecar_written,
                          cancel_check=lambda: _sidecar_cancel(cancellation))
        # Recheck before publication; rename is atomic. macOS exclusive rename prevents races.
        if destination_operation(destination.exists) or destination_operation(destination.is_symlink):
            raise BatchError('The output folder appeared during processing. Choose another output folder.', output_issue='conflict')
        _journal_mark(operation, "publishing")
        cancellation.begin_publication()
        if sys.platform == 'darwin':
            import ctypes
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.renamex_np(os.fsencode(staging), os.fsencode(destination), 4) != 0:
                raise output_error(OSError(ctypes.get_errno(), 'Output publication failed.')) from None
        else:
            destination_operation(os.rename, staging, destination)
        publication_succeeded = True
        _journal_mark(operation, "published")
        staging = None
        result = dict(processed=len(records), total_files=len(records), patients=len(patients), excluded_files=excluded, audited_files=audit_summary['files_audited'])
        if clean_json_sidecars:
            result.update(sidecar_files=sidecar_summary.files_written, sidecar_audited_files=sidecar_summary.files_audited)
        progress('complete', **result)
        return result
    except Exception as original:
        # A second Cancel must not interrupt cleanup or replace the first failure.
        cancellation.deferred = True
        if publication_succeeded:
            raise BatchError(
                'The completed output was published, but completion could not be confirmed. '
                'Check the output folder before retrying.', output_published=True) from original
        if staging is not None:
            try:
                remove_staging(staging, staging_identity)
                try:
                    _journal_mark(operation, "cleaned")
                except BatchError:
                    pass  # Preserve the primary failure; a stale record is conservative.
            except OSError as cleanup_error:
                owned_path = None if staging_identity is None or isinstance(cleanup_error, StagingOwnershipError) else str(staging)
                recovery = (
                    ' The staging folder ownership could not be confirmed. Inspect the output location before retrying.'
                    if staging_identity is None else
                    ' The staging location changed and could not be cleaned safely. Inspect the output location before retrying.'
                    if owned_path is None else
                    ' Incomplete output could not be removed. Remove the staging folder before retrying.')
                message = str(original) if isinstance(original, BatchError) else PROCESSING_FAILURE
                raise BatchError(
                    message + recovery,
                    cancelled=isinstance(original, BatchError) and original.cancelled,
                    cleanup_failed=True, staging_path=owned_path,
                    output_issue=getattr(original, 'output_issue', None),
                    required_bytes=getattr(original, 'required_bytes', None),
                    available_bytes=getattr(original, 'available_bytes', None)) from original
        raise


AUDIT_FAILURE = 'The pre-publication self-audit found retained identifying metadata. No output was published.'
DISK_MARGIN_BYTES = 32 * 1024 * 1024
# Value representations that can carry a copied UID string; numeric VRs are excluded to avoid false positives.
UID_CARRYING_VRS = {'UI', 'LO', 'LT', 'SH', 'ST', 'UT', 'UC', 'UR', 'CS', 'AE'}


def source_uids(ds, found):
    """Collect source non-class UID values (the ones clean() must remap), recursively."""
    for element in ds.iterall():
        if element.VR != 'UI' or 'SOPClassUID' in element.keyword or element.keyword in PRESERVE_UID_KEYS:
            continue
        values = element.value if element.VM > 1 else [element.value]
        # Standard DICOM-defined UIDs (1.2.840.10008.*) are not patient-specific and may legitimately recur.
        found.update(u for u in (str(v).strip() for v in values if v is not None) if u and not u.startswith('1.2.840.10008.'))
    return found


# Additive allowances avoid charging pixel payloads an arbitrary growth percentage.
FILE_METADATA_ALLOWANCE = 4096
REPORT_BASE_ALLOWANCE = 64 * 1024
REPORT_PATIENT_ALLOWANCE = 512
DIRECTORY_ENTRY_ALLOWANCE = 256
DEFAULT_ALLOCATION_UNIT = 4096
DEFLATED_TRANSFER_SYNTAX = '1.2.840.10008.1.2.1.99'


def estimate_output_bytes(ds, source_bytes, patient=None):
    """Estimate encoded growth from an already-decoded scan dataset, without cleaning it.

    All UI values are counted conservatively, even preserved/removed ones. This
    does not duplicate the metadata policy or create replacement UIDs. Pixel
    payloads are neither decoded nor serialized for this estimate.
    """
    growth = 0
    for element in ds.iterall():
        # These existing replacements also occur in nested datasets. Original
        # character count is a conservative lower bound on encoded text bytes;
        # source character sets need not be UTF-8. Targets are ASCII.
        replacement = None
        if element.keyword in ('PatientName', 'PatientID'):
            replacement = patient if patient is not None else '0' * 64
        elif element.keyword == 'StructureSetLabel':
            replacement = 'Structures'
        if replacement is not None:
            values = element.value if element.VM > 1 else [element.value]
            original = sum(len(str(value)) if value is not None else 0 for value in values) + max(0, len(values) - 1)
            growth += max(0, ((len(replacement) + 1) // 2 - (original + 1) // 2) * 2)
        if element.VR != 'UI':
            continue
        values = element.value if element.VM > 1 else [element.value]
        lengths = [len(str(value).encode('utf-8')) if value is not None else 0 for value in values]
        original = sum(lengths) + max(0, len(lengths) - 1)
        projected = sum(max(64, length) for length in lengths) + max(0, len(lengths) - 1)
        # DICOM pads the entire value field to an even number of bytes.
        growth += ((projected + 1) // 2 - (original + 1) // 2) * 2
    transfer = str(getattr(getattr(ds, 'file_meta', None), 'TransferSyntaxUID', ''))
    # Recompressing a deflated dataset can change its ratio. Preserve the former
    # percentage allowance in this uncertain case; it is still not a bound.
    base = (source_bytes * 11 + 9) // 10 if transfer in ('', DEFLATED_TRANSFER_SYNTAX) else source_bytes
    return base + growth + FILE_METADATA_ALLOWANCE


def allocation_unit(destination_parent):
    try:
        geometry = os.statvfs(destination_parent)
        for size in (geometry.f_frsize, geometry.f_bsize):
            if type(size) is int and size > 0:
                return size
    except (OSError, AttributeError, NotImplementedError):
        pass
    # Geometry is advisory; inability to query it does not change access policy.
    return DEFAULT_ALLOCATION_UNIT


def estimate_disk_space(records, unit, *, sidecars=()):
    """Budget encoded files, allocation rounding, output directories and report."""
    def allocated(size):
        return ((size + unit - 1) // unit) * unit
    files = 0
    patients, series = set(), set()
    for index, record in enumerate(records):
        estimate = getattr(record, 'estimated_output_bytes', None)
        if type(estimate) is not int or estimate < record.signature[2]:
            # Compatibility for records constructed outside the scanner. Never
            # silently treat absent scan metadata as zero or discount source data.
            estimate = (record.signature[2] * 11 + 9) // 10 + FILE_METADATA_ALLOWANCE
        files += allocated(estimate)
        patient = getattr(record, 'patient', ('unknown', index))
        patients.add(patient)
        series.add((patient, getattr(record, 'series', ('unknown', index))))
    if sidecars:
        import sidecar_deid
        for record in sidecars:
            estimate = record.estimated_output_bytes
            files += allocated(estimate if type(estimate) is int and estimate > 0 else sidecar_deid.BatchLimits.max_output_bytes)
            patients.add(record.patient)
        sidecar_directories = len({record.patient for record in sidecars})
    else:
        sidecar_directories = 0
    directory_count = 1 + len(patients) + len(series) + sidecar_directories
    directories = directory_count * unit + allocated(
        (len(records) + len(sidecars) + directory_count + 1) * DIRECTORY_ENTRY_ALLOWANCE)
    report = allocated(REPORT_BASE_ALLOWANCE + REPORT_PATIENT_ALLOWANCE * len(patients))
    if sidecars:
        report += allocated(4096)
    return files + directories + report + DISK_MARGIN_BYTES


def check_disk_space(records, destination_parent, *, sidecars=()):
    required = estimate_disk_space(records, allocation_unit(destination_parent), sidecars=sidecars)
    try:
        free = shutil.disk_usage(destination_parent).free
    except OSError as error:
        raise output_error(error) from None
    if free < required:
        raise BatchError(
            f'Not enough free disk space at the output location. Estimated need: {approximate_storage(required)}; '
            f'available: {approximate_storage(free)}. This estimate is not a guarantee. '
            'Free space or choose another output location, then retry.',
            output_issue='space', required_bytes=required, available_bytes=free)
    return required


def audit_values(element):
    value = element.value
    if value is None:
        return []
    if isinstance(value, (list, tuple, pydicom.multival.MultiValue)):
        return [str(v).strip() for v in value if v is not None]
    return [str(value).strip()]


def audit_file_header(ds):
    """Check staged-file header guarantees without changing dataset-only policy checks."""
    if getattr(ds, 'preamble', None) != b'\0' * 128:
        raise BatchError(AUDIT_FAILURE)
    meta = getattr(ds, 'file_meta', None)
    if meta is None:
        raise BatchError(AUDIT_FAILURE)
    # The writer starts from these three fields and lets the pinned library add
    # its standard implementation defaults. Recreate that expected header in
    # isolation; never normalize or repair the staged file during its audit.
    expected = pydicom.dataset.FileMetaDataset()
    try:
        expected.TransferSyntaxUID = meta.get('TransferSyntaxUID', '')
        expected.MediaStorageSOPClassUID = ds.get('SOPClassUID', '')
        expected.MediaStorageSOPInstanceUID = ds.get('SOPInstanceUID', '')
        pydicom.dataset.validate_file_meta(expected, enforce_standard=True)
    except (AttributeError, TypeError, ValueError):
        raise BatchError(AUDIT_FAILURE) from None
    for element in expected:
        actual = meta.get(element.tag)
        if actual is None or actual.VR != element.VR or actual.value != element.value:
            raise BatchError(AUDIT_FAILURE)
    for element in meta:
        if element.tag == 0x00020000:  # The file writer also emits a group length.
            if element.VR != 'UL' or not isinstance(element.value, int) or element.value < 0:
                raise BatchError(AUDIT_FAILURE)
        elif element.tag not in expected:
            # This also rejects source AE titles, presentation addresses, private
            # information and unrecognized fields the rebuilt writer never emits.
            raise BatchError(AUDIT_FAILURE)


def audit_dataset(ds, patient, forbidden_uids):
    """Raise BatchError unless a staged dataset meets the invariants that must hold for every output."""
    for element in ds.iterall():
        if element.tag.is_private or element.tag in REMOVE_TAGS or element.tag.group & 0xFF00 == 0x5000:
            raise BatchError(AUDIT_FAILURE)
        vr, keyword = element.VR, element.keyword
        # Mirror clean()'s existing normalization, including nested occurrences.
        # Check before SQ handling so a malformed VR cannot bypass the invariant.
        if keyword == 'StructureSetLabel' and (vr != 'SH' or element.value != 'Structures'):
            raise BatchError(AUDIT_FAILURE)
        clear_value = (element.tag in CLEAR_TAGS or keyword in REMOVE_KEYS or
                       (element.tag.group == 0x0010 and keyword not in
                        {'PatientName', 'PatientID', 'PatientSex', 'PatientAge', 'PatientSize', 'PatientWeight'}) or
                       vr in ('AE', 'LT', 'ST', 'UT', 'UR'))
        if clear_value and (vr == 'SQ' or element.value not in (None, '', b'')):
            raise BatchError(AUDIT_FAILURE)
        if vr == 'SQ':
            continue
        if vr == 'UN':
            raise BatchError(AUDIT_FAILURE)
        values = audit_values(element) if vr not in ('OB', 'OW', 'OF', 'OD', 'OL', 'OV', 'UN') else []
        if keyword in ('PatientName', 'PatientID'):
            if values != [patient]:
                raise BatchError(AUDIT_FAILURE)
        elif vr == 'PN' and any(values):
            raise BatchError(AUDIT_FAILURE)
        elif vr in ('DA', 'DT', 'TM') and any(values):
            raise BatchError(AUDIT_FAILURE)
        if forbidden_uids and vr in UID_CARRYING_VRS and any(v in forbidden_uids for v in values):
            raise BatchError(AUDIT_FAILURE)
    meta = getattr(ds, 'file_meta', None)
    if meta is None or str(meta.get('MediaStorageSOPInstanceUID', '')) != str(ds.get('SOPInstanceUID', '')) or not str(ds.get('SOPInstanceUID', '')):
        raise BatchError(AUDIT_FAILURE)
    for element in meta:
        if element.tag.is_private or (element.VR in UID_CARRYING_VRS and any(v in forbidden_uids for v in audit_values(element))):
            raise BatchError(AUDIT_FAILURE)


def self_audit(staging, written, forbidden_uids, progress=None):
    """Re-read each entire staged DICOM, including metadata after Pixel Data, before publication."""
    total = len(written)
    if progress is not None:
        progress('audit_progress', audited_files=0, total_files=total)
    staged = {path for path, _ in written}
    for root, _dirs, files in os.walk(staging):
        for filename in files:
            path = Path(root) / filename
            if path.suffix == '.dcm' and path not in staged:
                raise BatchError(AUDIT_FAILURE)
    for index, (path, patient) in enumerate(written, 1):
        try:
            ds = checked_read(path)
            validate(ds)
            audit_file_header(ds)
        except BatchError:
            raise
        except Exception:
            raise BatchError('A staged output file could not be re-read for the self-audit. No output was published.') from None
        audit_dataset(ds, patient, forbidden_uids)
        if progress is not None and (index % 10 == 0 or index == total):
            progress('audit_progress', audited_files=index, total_files=total)
    return {'result': 'passed', 'files_audited': len(written),
            'checks': ['entire staged file decoded', 'removed attributes and curve groups absent',
                       'cleared policy attributes and free text empty', 'no uninterpreted UN attributes', 'no private tags', 'PatientName/PatientID equal folder identifier', 'no other person names',
                       'no dates/times', 'no source instance/study/series/frame UIDs', 'file meta instance UID synchronized',
                       '128-byte preamble zeroed', 'rebuilt file meta matches writer defaults and dataset UIDs',
                       'present StructureSetLabel normalized to Structures']}


def audit_coverage(dicom_audit, dicom_files, sidecars=None):
    """Describe completed audit scope without copying source values or claiming anonymity."""
    return {
        'schema_version': 1,
        'dicom': {
            'result': dicom_audit['result'], 'files_written': dicom_files,
            'files_audited': dicom_audit['files_audited'],
            'checks': list(dicom_audit.get('checks', [])) if dicom_audit['result'] == 'passed' else [],
        },
        'json_sidecars': {
            'enabled': sidecars is not None,
            'result': 'passed' if sidecars is not None else 'not_requested',
            'files_written': sidecars.files_written if sidecars is not None else 0,
            'files_audited': sidecars.files_audited if sidecars is not None else 0,
        },
        'retained_content': {
            'patient_folder_identifier': 'Exact numeric folder identifier retained as PatientName and PatientID; not an anonymity guarantee.',
            'dicom_attributes': ['SeriesDescription', 'ProtocolName', 'SequenceName', 'ContrastBolusAgent',
                                 'SoftwareVersions', 'Manufacturer', 'ROIName', 'ROIObservationLabel'],
            'payloads': ['pixel data', 'contour geometry', 'quantitative measurements'],
        },
        'not_assessed': {
            'pixel_and_contour_identity': 'Pixel content and contour geometry are retained; burned-in text, faces and anatomical identity are not assessed.',
            'retained_text_identity': 'Retained series, protocol and ROI labels can contain identifying content and require review.',
            'dicom_conformance': 'No complete DICOM IOD or confidentiality-profile conformance certification; encoded file-meta group length is not independently recomputed.',
            'reference_closure': 'No complete cross-file reference-closure or geometric-alignment validation.',
            'companion_file_content': 'Only supported DICOM files and explicitly enabled JSON sidecars are processed; NIfTI voxels and other companion formats are not inspected.',
            'external_linkability': 'Retained identifiers, acquisition values and other content may remain linkable with external data.',
        },
    }


def environment_info():
    return {'pydicom': pydicom.__version__, 'python': '%d.%d.%d' % sys.version_info[:3]}


def main():
    parser = argparse.ArgumentParser(description='Bulk local DICOM pseudonymization')
    parser.add_argument('--source', required=True)
    parser.add_argument('--journal', help='Private local recovery record path; never included in batch reports')
    parser.add_argument('--clean-json-sidecars', action='store_true', help='Write cleaned MRI JSON sidecar copies using mri-physical-v1')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--scan', action='store_true')
    group.add_argument('--destination')
    args = parser.parse_args()
    cancellation = Cancellation()
    signal.signal(signal.SIGTERM, cancellation.cancel)
    signal.signal(signal.SIGINT, cancellation.cancel)
    try:
        if args.scan:
            records, patients, excluded = scan(args.source, progress=emit)
            if args.clean_json_sidecars:
                sidecars = _sidecar_scan(args.source, cancellation, progress=emit)
                emit('scan', patients=patients, total_files=len(records), excluded_files=max(0, excluded - len(sidecars)), sidecar_files=len(sidecars))
            else:
                emit('scan', patients=patients, total_files=len(records), excluded_files=excluded)
        else:
            run(args.source, args.destination, cancellation=cancellation, clean_json_sidecars=args.clean_json_sidecars, journal=args.journal)
        return 0
    except BatchError as exc:
        cancellation.deferred = True
        details = dict(message=str(exc), cancelled=exc.cancelled, cleanup_failed=exc.cleanup_failed)
        if exc.cleanup_failed and exc.staging_path is not None:
            details['staging_path'] = exc.staging_path
        if exc.output_published:
            details['output_published'] = True
        elif exc.output_issue in {'space', 'permissions', 'unavailable', 'conflict', 'unknown'}:
            details['output_issue'] = exc.output_issue
            if (exc.output_issue == 'space' and type(exc.required_bytes) is int and
                    type(exc.available_bytes) is int and exc.required_bytes > exc.available_bytes >= 0):
                details['required_bytes'] = exc.required_bytes
                details['available_bytes'] = exc.available_bytes
        emit('error', **details)
    except Exception:
        cancellation.deferred = True
        emit('error', message=PROCESSING_FAILURE, cancelled=False, cleanup_failed=False)
    return 1

if __name__ == '__main__':
    sys.exit(main())
