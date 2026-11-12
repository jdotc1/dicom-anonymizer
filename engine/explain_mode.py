"""Value-free explain mode: what a real run would do to each attribute of one file.

The file is read and validated exactly as a real run does, then the engine's own
clean() runs on a deep copy with a throwaway UID map and a fixed UID factory.
Original and cleaned copies are compared; output names only the tag path,
keyword (from the public dictionary), VR and action, never a value. Nothing is
written. The engine module is passed in so tests that patch its globals
(checked_read, validate, clean, generate_uid) govern this path as well.
"""
from copy import deepcopy
import json
import sys

ACTIONS = ('removed', 'cleared', 'pseudonym', 'uid_remapped', 'replaced', 'changed')
EXPLAIN_PSEUDONYM = 'EXPLAIN'


def _tag_text(tag):
    return '(%04X,%04X)' % (tag.group, tag.element)


def _same(a, b):
    try:
        return bool(a.value == b.value)
    except Exception:
        return False


def _classify(original, cleaned):
    if cleaned is None:
        return 'removed'
    if original.VR == 'SQ':
        return None
    if _same(original, cleaned):
        return None
    keyword = original.keyword
    new = cleaned.value
    if keyword in ('PatientName', 'PatientID'):
        return 'pseudonym'
    if original.VR == 'UI':
        return 'uid_remapped'
    if new in ('', None) or (isinstance(new, (list, tuple)) and not any(new)):
        return 'cleared'
    if keyword == 'StructureSetLabel':
        return 'replaced'
    return 'changed'


def _walk(original, cleaned, path, rows, counts):
    for element in original:
        counterpart = cleaned[element.tag] if cleaned is not None and element.tag in cleaned else None
        here = path + _tag_text(element.tag)
        action = _classify(element, counterpart)
        if element.VR == 'SQ' and counterpart is not None:
            counts['retained'] += 1
            for index, item in enumerate(element.value):
                try:
                    twin = counterpart.value[index]
                except IndexError:
                    twin = None
                _walk(item, twin, '%s[%d]/' % (here, index), rows, counts)
            continue
        if action is None:
            counts['retained'] += 1
            continue
        counts[action] += 1
        rows.append(dict(path=here, keyword=element.keyword, vr=element.VR, action=action))
        if element.VR == 'SQ':
            # Removed sequence: its nested elements go with it.
            _descend_removed(element, here, rows, counts)


def _descend_removed(element, here, rows, counts):
    for index, item in enumerate(element.value):
        for child in item:
            sub = '%s[%d]/%s' % (here, index, _tag_text(child.tag))
            counts['removed_with_parent'] += 1
            if child.VR == 'SQ':
                _descend_removed(child, sub, rows, counts)


def explain_dataset(engine, ds):
    """Return (rows, counts) for an already read and validated dataset."""
    working = deepcopy(ds)
    uid_map = {}
    serial = iter(range(1, 1 << 62))
    original_factory = engine.generate_uid
    engine.generate_uid = lambda *a, **k: '2.25.%d' % next(serial)
    try:
        engine.clean(working, EXPLAIN_PSEUDONYM, uid_map)
    finally:
        engine.generate_uid = original_factory
    counts = dict.fromkeys(ACTIONS, 0)
    counts.update(retained=0, removed_with_parent=0)
    rows = []
    _walk(ds, working, '', rows, counts)
    return rows, counts


def explain_file(engine, path):
    ds = engine.checked_read(path)
    engine.validate(ds)
    return explain_dataset(engine, ds)


def explain_main(engine, argv, out=None):
    out = out if out is not None else sys.stdout
    if len(argv) != 2 or argv[0] != '--explain':
        print('usage: engine.py --explain FILE', file=sys.stderr)
        return 2
    try:
        rows, counts = explain_file(engine, argv[1])
        print(json.dumps(dict(event='explain', attributes=rows, counts=counts)), file=out, flush=True)
        return 0
    except engine.BatchError as exc:
        print(json.dumps(dict(event='error', message=str(exc), cancelled=exc.cancelled,
                              cleanup_failed=exc.cleanup_failed)), file=out, flush=True)
    except Exception:
        print(json.dumps(dict(event='error', message=engine.PROCESSING_FAILURE, cancelled=False,
                              cleanup_failed=False)), file=out, flush=True)
    return 1
