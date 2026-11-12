"""Static lint helpers for the engine policy tables (test support only; nothing here is imported by the engine).

The lint reads engine.py as text so that duplicate literal entries and the
numeric-tag comments are visible; a set literal silently collapses duplicates
and Python drops comments. Every function takes plain data so a test can feed
it a deliberately broken copy and check that the lint objects.
"""
import ast
import io
import json
import tokenize
from decimal import Decimal

from pydicom.datadict import dictionary_VR, keyword_for_tag, tag_for_keyword

TABLE_NAMES = ('REMOVE_KEYS', 'CLEAR_TAGS', 'REMOVE_TAGS')
# VRs that clean() already blanks or removes before it consults REMOVE_KEYS.
VR_HANDLED_BEFORE_KEYS = frozenset({'PN', 'DA', 'DT', 'TM', 'AE', 'UN', 'LT', 'ST', 'UT', 'UR'})


def read_tables(engine_source):
    """Return {name: [(value, line, comment_or_None), ...]} for the three policy set literals."""
    tree = ast.parse(engine_source)
    comments = {}
    for token in tokenize.generate_tokens(io.StringIO(engine_source).readline):
        if token.type == tokenize.COMMENT:
            comments[token.start[0]] = token.string.lstrip('#').strip()
    tables = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], 'id', None) in TABLE_NAMES:
            if not isinstance(node.value, ast.Set):
                raise AssertionError(f'{node.targets[0].id} is no longer a set literal')
            tables[node.targets[0].id] = [(ast.literal_eval(e), e.lineno, comments.get(e.lineno)) for e in node.value.elts]
    missing = set(TABLE_NAMES) - set(tables)
    if missing:
        raise AssertionError(f'policy tables not found: {sorted(missing)}')
    return tables


def lint_tables(tables, *, unknown_tags=(), comment_allowlist=None):
    """Return a sorted list of problems; empty means the tables are internally consistent.

    unknown_tags: numeric tags allowed to be absent from the pinned dictionary.
    comment_allowlist: {tag: comment} pairs whose comment deliberately differs from the dictionary keyword.
    """
    comment_allowlist = comment_allowlist or {}
    problems = []
    for name, entries in tables.items():
        seen = set()
        for value, line, _ in entries:
            if value in seen:
                problems.append(f'{name}: duplicate entry {value!r} (line {line})')
            seen.add(value)
    for value, line, _ in tables['REMOVE_KEYS']:
        if not isinstance(value, str) or tag_for_keyword(value) is None:
            problems.append(f'REMOVE_KEYS: keyword {value!r} does not resolve in the dictionary (line {line})')
    numeric = {}
    for name in ('CLEAR_TAGS', 'REMOVE_TAGS'):
        for value, line, comment in tables[name]:
            numeric.setdefault(value, []).append(name)
            if not isinstance(value, int):
                problems.append(f'{name}: non-numeric entry {value!r} (line {line})')
                continue
            keyword = keyword_for_tag(value)
            if not keyword:
                if value not in unknown_tags:
                    problems.append(f'{name}: tag {value:#010X} is not in the dictionary and not allow-listed (line {line})')
            elif value in unknown_tags:
                problems.append(f'{name}: tag {value:#010X} is allow-listed as unknown but now resolves to {keyword}')
            if comment is None:
                problems.append(f'{name}: tag {value:#010X} has no comment (line {line})')
            elif keyword and comment != keyword and comment_allowlist.get(value) != comment:
                problems.append(f'{name}: tag {value:#010X} comment {comment!r} != dictionary keyword {keyword!r} (line {line})')
            elif not keyword and value in comment_allowlist and comment_allowlist[value] != comment:
                problems.append(f'{name}: tag {value:#010X} comment {comment!r} differs from the allow-listed name (line {line})')
    for value, names in numeric.items():
        if len(names) > 1 and 'CLEAR_TAGS' in names and 'REMOVE_TAGS' in names:
            problems.append(f'tag {value:#010X} is in both CLEAR_TAGS and REMOVE_TAGS')
    return sorted(problems)


def redundant_remove_keys(remove_keys, remove_tags):
    """Classify REMOVE_KEYS entries that clean() would neutralize without them.

    Returns {'vr_rule': keywords whose VR clean() already blanks, removes or empties,
             'remove_tags_overlap': keywords whose tag is also in REMOVE_TAGS}.
    The group 0010 rule is not counted here because it is a group-wide default rather than a per-VR rule.
    """
    vr_rule, overlap = set(), set()
    for keyword in remove_keys:
        tag = tag_for_keyword(keyword)
        if tag is None:
            continue
        if dictionary_VR(tag) in VR_HANDLED_BEFORE_KEYS:
            vr_rule.add(keyword)
        if tag in remove_tags:
            overlap.add(keyword)
    return {'vr_rule': vr_rule, 'remove_tags_overlap': overlap}


def policy_json_differences(document, policy):
    """Compare the shipped policy JSON document to a SidecarPolicy; return a sorted list of differences."""
    differences = []
    for key in ('policy_id', 'policy_version', 'catalog_revision', 'description'):
        if document.get(key) != getattr(policy, key):
            differences.append(f'{key} differs')
    fields = document.get('fields', {})
    for name in sorted(set(fields) | set(policy.fields)):
        if name not in fields:
            differences.append(f'{name}: only in Python policy')
            continue
        if name not in policy.fields:
            differences.append(f'{name}: only in JSON')
            continue
        rule, entry = policy.fields[name], fields[name]
        expected = {'shape': rule.shape, 'category': rule.category}
        if rule.unit is not None:
            expected['unit'] = rule.unit
        if rule.allowed_values is not None:
            expected['allowed_values'] = sorted(rule.allowed_values)
        if rule.pattern is not None:
            expected['pattern'] = rule.pattern
        for attr in ('minimum', 'maximum'):
            value = getattr(rule, attr)
            if value is not None:
                expected[attr] = value
        if rule.min_items != 1:
            expected['min_items'] = rule.min_items
        if rule.max_items is not None:
            expected['max_items'] = rule.max_items
        actual = dict(entry)
        if 'allowed_values' in actual:
            actual['allowed_values'] = sorted(actual['allowed_values'])
        for attr in ('minimum', 'maximum'):
            if attr in actual and attr in expected:
                try:
                    if Decimal(str(actual[attr])) == Decimal(str(expected[attr])):
                        actual[attr] = expected[attr]
                except ArithmeticError:
                    pass
        for attr in sorted(set(expected) | set(actual)):
            if expected.get(attr) != actual.get(attr):
                differences.append(f'{name}.{attr} differs')
    return differences


def load_policy_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)
