"""Canary-token retention survey over synthetic in-memory datasets (test support only).

Plants a unique canary value in every attribute of each class (hand-written named
list, private blocks, an unknown public tag, curve data, and every text-capable
dictionary attribute in the RT-family groups), at three nesting depths, runs
engine.clean() once, and classifies what happened to each canary by comparing the
value that came back with the value that went in. It also asks engine.audit_dataset()
whether it would have flagged the planted value, to show where the audit shares the
engine's own policy lists and is therefore blind.

Nothing here writes DICOM files or changes the engine. The answer key is in
canary_answer_key.py and does not import the engine. Run manually:
    cd tests && python -B canary_survey.py
"""
import sys
from collections import namedtuple

import pydicom
from pydicom.datadict import DicomDictionary
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence

import canary_answer_key as key

KEPT, REMOVED, BLANKED, REPLACED, REMAPPED = key.KEPT, key.REMOVED, 'BLANKED', key.REPLACED, key.REMAPPED
PATIENT = '77001'
DEPTHS = (0, 1, 2)
WRAP_1, WRAP_2 = 0x00081120, 0x00081110   # ReferencedPatientSequence, ReferencedStudySequence

Row = namedtuple('Row', 'tag keyword vr cls actions audit_sees verdict retired')


def canary(tag, vr, depth):
    """Unique, deterministic value for one (tag, depth), shaped to be valid for the VR."""
    stem = f'{tag:08X}'
    if vr == 'UI':
        return f'2.25.{9000000000000 + tag * 3 + depth}'
    if vr == 'DA':
        return f'1999090{depth + 1}'
    if vr == 'TM':
        return f'12000{depth}'
    if vr == 'DT':
        return f'1999090{depth + 1}120000'
    if vr == 'PN':
        return f'CNRY^{stem}d{depth}'
    if vr == 'AE':
        return f'CNRY{stem}d{depth}'
    if vr == 'AS':
        return '045Y'
    if vr == 'DS':
        return f'1{depth}.5'
    if vr == 'UR':
        return f'urn:cnry:{stem}:d{depth}'
    if vr == 'CS':
        return f'CNRY{stem}'[:16]
    if vr in ('SH', 'AE'):
        return f'CNRY{stem}d{depth}'
    return f'CNRY-{stem}-d{depth}'


def element_for(tag, vr, depth):
    if vr == 'SQ':
        item = Dataset()
        item.add_new(0x00104000, 'LT', f'CNRY-SQ-{tag:08X}-d{depth}')
        return DataElement(tag, 'SQ', Sequence([item]))
    if vr in ('OB', 'UN'):
        return DataElement(tag, vr, f'CNRY{tag:08X}d{depth}'.encode('ascii'))
    return DataElement(tag, vr, canary(tag, vr, depth))


def plant(root, specs):
    """Plant every (tag, vr) spec at depth 0, 1 and 2; return {(depth, tag): original_value}."""
    level2 = Dataset()
    level1 = Dataset()
    level1.add_new(WRAP_2, 'SQ', Sequence([level2]))
    root.add_new(WRAP_1, 'SQ', Sequence([level1]))
    holders = {0: root, 1: level1, 2: level2}
    originals = {}
    for depth, holder in holders.items():
        for tag, vr in specs:
            elem = element_for(tag, vr, depth)
            holder.add(elem)
            originals[(depth, tag)] = elem.value if vr != 'SQ' else None
    return holders, originals


def observe(holder, tag, vr, original):
    """Classify the fate of one planted canary from the cleaned dataset."""
    if tag not in holder:
        return REMOVED
    now = holder[tag].value
    if vr == 'SQ':
        return KEPT if len(now) else BLANKED
    if isinstance(original, bytes):
        return KEPT if now == original else BLANKED
    text = '' if now is None else str(now)
    if text == '':
        return BLANKED
    if text == str(original):
        return KEPT
    return REMAPPED if vr == 'UI' else REPLACED


def audit_sees(engine, tag, vr):
    """True if audit_dataset() would reject a minimal dataset still holding the raw canary."""
    ds = Dataset()
    ds.SOPInstanceUID = '2.25.1'
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPInstanceUID = '2.25.1'
    elem = element_for(tag, vr, 0)
    ds.add(elem)
    forbidden = {str(elem.value)} if vr == 'UI' else set()
    try:
        engine.audit_dataset(ds, PATIENT, forbidden)
    except engine.BatchError:
        return True
    return False


def meets(expect, actions):
    got = set(actions)
    if expect == key.GONE:
        return got <= {REMOVED, BLANKED, REPLACED}
    return got == {expect}


def combine(actions):
    return actions[0] if len(set(actions)) == 1 else ';'.join(f'd{d}={a}' for d, a in zip(DEPTHS, actions))


def run_survey(engine):
    """Return (rows, expectations) after one clean() pass. Deterministic apart from fresh UIDs, which are never reported."""
    rows = []
    # --- named classes ---------------------------------------------------------------
    root = Dataset()
    specs = [(e.tag, e.vr) for e in key.NAMED]
    holders, originals = plant(root, specs)
    # private blocks, unknown public tag, curve data
    private_specs = []
    for group, creator, items in key.PRIVATE_BLOCKS:
        for depth, holder in holders.items():
            holder.add_new(group << 16 | 0x0010, 'LO', creator)
            for offset, vr in items:
                tag = group << 16 | 0x1000 | offset
                holder.add(element_for(tag, vr, depth))
                private_specs.append((depth, tag, vr))
    extras = []
    for depth, holder in holders.items():
        holder.add(element_for(key.UNKNOWN_PUBLIC_TAG, 'UN', depth))
        holder.add(element_for(key.CURVE_TAG, 'OB', depth))
    engine.clean(root, PATIENT, {})
    for entry in key.NAMED:
        actions = [observe(holders[d], entry.tag, entry.vr, originals[(d, entry.tag)]) for d in DEPTHS]
        ok = meets(entry.expect, actions)
        rows.append(Row(entry.tag, entry.keyword, entry.vr, 'named:' + entry.expect, combine(actions),
                        audit_sees(engine, entry.tag, entry.vr), 'OK' if ok else 'VIOLATION', False))
    for group, creator, items in key.PRIVATE_BLOCKS:
        for offset, vr in items:
            tag = group << 16 | 0x1000 | offset
            actions = [REMOVED if tag not in holders[d] else KEPT for d in DEPTHS]
            rows.append(Row(tag, 'private', vr, 'private:GONE', combine(actions), audit_sees(engine, tag, vr),
                            'OK' if set(actions) == {REMOVED} else 'VIOLATION', False))
    for tag, label in ((key.UNKNOWN_PUBLIC_TAG, 'unknown-public'), (key.CURVE_TAG, 'curve-group')):
        vr = 'UN' if tag == key.UNKNOWN_PUBLIC_TAG else 'OB'
        actions = [REMOVED if tag not in holders[d] else KEPT for d in DEPTHS]
        rows.append(Row(tag, label, vr, 'other:GONE', combine(actions), audit_sees(engine, tag, vr),
                        'OK' if set(actions) == {REMOVED} else 'VIOLATION', False))
    # --- dictionary-driven survey of RT-family text attributes -------------------------
    survey = []
    for tag, (vr, _vm, _name, retired, keyword) in DicomDictionary.items():
        if (tag >> 16) in key.SURVEY_GROUPS and vr in key.SURVEY_VRS:
            survey.append((tag, vr, keyword, bool(retired)))
    survey.sort()
    root2 = Dataset()
    holders2, originals2 = plant(root2, [(t, v) for t, v, _k, _r in survey])
    engine.clean(root2, PATIENT, {})
    for tag, vr, keyword, retired in survey:
        actions = [observe(holders2[d], tag, vr, originals2[(d, tag)]) for d in DEPTHS]
        retained = KEPT in actions
        if not retained:
            verdict = 'OK'
        elif tag in key.SURVEY_INTENDED_RETAINED:
            verdict = 'OK-retained-by-design'
        else:
            verdict = 'GAP'
        rows.append(Row(tag, keyword, vr, 'survey', combine(actions), audit_sees(engine, tag, vr), verdict, retired))
    rows.sort(key=lambda r: (r.cls.split(':')[0] != 'named', r.tag, r.cls))
    return rows


HEADER = ('tag', 'keyword', 'vr', 'class', 'observed(d0;d1;d2)', 'audit_sees_raw', 'verdict', 'retired')


def render(rows):
    lines = ['\t'.join(HEADER)]
    for r in rows:
        lines.append('\t'.join((f'{r.tag:08X}', r.keyword, r.vr, r.cls, r.actions,
                                'yes' if r.audit_sees else 'NO', r.verdict, 'retired' if r.retired else '')))
    return '\n'.join(lines) + '\n'


def gaps(rows):
    """Survey attributes that survive although the answer key expects them gone (tag, keyword), sorted."""
    return sorted((r.tag, r.keyword) for r in rows if r.verdict == 'GAP')


def violations(rows):
    return sorted((r.tag, r.keyword, r.cls) for r in rows if r.verdict == 'VIOLATION')


if __name__ == '__main__':
    sys.path.insert(0, '.')
    from test_engine import engine
    table = run_survey(engine)
    sys.stdout.write(render(table))
    sys.stderr.write(f'pydicom {pydicom.__version__}: {len(gaps(table))} gaps, {len(violations(table))} violations\n')
