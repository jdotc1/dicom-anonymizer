"""New configuration/documentation boundaries; no real artifacts or history scans."""
import json
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_publication_safety import SafetyTests
import publication_safety as safety


class PrivateRulesTests(SafetyTests):
    # Inherit setup helpers, but discover only newly authored methods in this file.
    def test_private_configuration_blocks_without_publishing_terms(self):
        with safety.ledger(self.repo), self.assertRaisesRegex(ValueError, 'unrelated-internal-app'):
            safety.check(b'RestrictedFixtureTool', 'fixture')

    def test_missing_configuration_never_falls_back_to_weaker_gate(self):
        (safety.cache_root(self.repo) / 'private-rules.json').unlink()
        with patch.object(safety, 'git_gate', side_effect=AssertionError('source scan')):
            with self.assertRaisesRegex(ValueError, 'missing'):
                safety.pre_push(self.repo, ['refs/heads/source ' + self.base + ' refs/heads/source ' + '0'*40])

    def test_symlink_and_invalid_configuration_refused(self):
        target = safety.cache_root(self.repo) / 'private-rules.json'
        target.unlink(); target.symlink_to(self.private_rules)
        with self.assertRaises(ValueError):
            with safety.ledger(self.repo): pass
        target.unlink(); target.write_text('{"schema":1,"rules":{}}')
        with self.assertRaises(ValueError):
            with safety.ledger(self.repo): pass

    def test_invalid_regex_fails_without_echoing_pattern(self):
        value = json.loads(self.private_rules.read_text())
        value['rules']['unrelated-internal-app'] = '[sensitive-fixture'
        self.private_rules.write_text(json.dumps(value))
        with self.assertRaises(ValueError) as caught:
            safety.read_private_rules(self.private_rules)
        self.assertNotIn('sensitive-fixture', str(caught.exception))

    def test_unchanged_effective_policy_reuses_original_receipts(self):
        rules = safety.effective_rules(self.repo)
        prior = safety.policy_identity(rules)
        root = safety.cache_root(self.repo)
        (root / 'receipts.json').write_text(json.dumps(dict(policy=prior, objects={'accepted':'commit'}, archives={}, texts={})))
        with patch.object(safety, 'check', side_effect=AssertionError('rescan')):
            with safety.ledger(self.repo) as receipts:
                self.assertEqual({'accepted':'commit'}, receipts['objects'])
                self.assertEqual(prior, receipts['policy'])

    def test_changed_private_rule_invalidates_affected_receipts(self):
        with safety.ledger(self.repo) as receipts:
            receipts['objects']['accepted'] = 'blob'
        path = safety.cache_root(self.repo) / 'private-rules.json'
        value = json.loads(path.read_text()); value['rules']['unrelated-internal-app'] = 'AnotherFixtureTool'
        path.write_text(json.dumps(value))
        with safety.ledger(self.repo) as receipts:
            self.assertFalse(receipts['objects'])
            with self.assertRaises(ValueError): safety.check(b'AnotherFixtureTool', 'fixture')

    def test_private_patterns_are_scoped_and_not_leaked_between_contexts(self):
        public = safety.PATTERNS
        with safety.ledger(self.repo):
            self.assertIsNotNone(safety._ACTIVE_PATTERNS.get())
        self.assertIsNone(safety._ACTIVE_PATTERNS.get())
        self.assertIs(public, safety.PATTERNS)

    def test_current_documentation_uses_separate_cached_scope(self):
        oid = self.commit('guide.md', 'Public application guide.', 'Guide')
        with safety.ledger(self.repo) as receipts:
            safety.documentation_gate(self.repo, [oid], receipts)
            with patch.object(safety, 'check_documentation', side_effect=AssertionError('repeat check')):
                safety.documentation_gate(self.repo, [oid], receipts)

    def test_documentation_failure_cannot_hide_behind_accepted_source(self):
        oid = self.commit('guide.md', 'The private ' + 'app has another build.', 'Guide')
        for _ in range(2):
            with safety.ledger(self.repo) as receipts:
                receipts['objects'][oid] = 'commit'
                with self.assertRaisesRegex(ValueError, 'internal-implementation-history'):
                    safety.git_gate(self.repo, [oid], receipts)

    def test_documentation_patterns_and_legitimate_technical_terms(self):
        for text in ('The private ' + 'repository is frozen.', 'codex/' + 'fixture-lane',
                     'DICOM-Fixture-' + '20260101', 'Fixture-' + 'Handoff.zip'):
            with self.assertRaises(ValueError): safety.check_documentation(text.encode())
        safety.check_documentation(b'DICOM private tags and private vulnerability reporting. Required third-party licenses are retained.')

    def test_non_object_configuration_has_safe_failure(self):
        self.private_rules.write_text('[]')
        with self.assertRaisesRegex(ValueError, 'must be an object'):
            safety.read_private_rules(self.private_rules)

    def test_documentation_inspector_version_is_receipt_bound(self):
        expected = hashlib.sha256(json.dumps([safety.DOCUMENTATION_SCANNER_VERSION, safety.DOCUMENTATION_RULES], sort_keys=True).encode()).hexdigest()
        self.assertEqual(expected, safety.DOCUMENTATION_POLICY)


# Avoid inherited old tests being discovered: select only this class's own methods.
def load_tests(loader, tests, pattern):
    return unittest.TestSuite(PrivateRulesTests(name) for name in PrivateRulesTests.__dict__ if name.startswith('test_'))


if __name__ == '__main__':
    unittest.main()
