"""Changed sanitation boundaries only; disposable Git repositories and ZIPs."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publication_safety as safety
import publication
import release


def private_path():
    return '/'+ 'Users/' + 'fixture-person/clinical-data'


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.base = self.commit('readme', 'portable source', 'Initial')
        self.evidence = self.root / 'accepted.json'
        self.evidence.write_text('{"status":"previously accepted"}')
        safety.install(self.repo, self.base, self.evidence)

    def git(self, *args):
        return safety.git(self.repo, *args).decode().strip()

    def commit(self, name, content, message):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.git('add', '--', name)
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def gate(self, oid=None):
        with safety.ledger(self.repo) as receipts:
            safety.git_gate(self.repo, [oid or self.git('rev-parse', 'HEAD')], receipts)

    def archive(self, entries, name='app.zip'):
        path = self.root / name
        with zipfile.ZipFile(path, 'w') as z:
            for key, content in entries.items():
                z.writestr(key, content)
        return path

    def test_accepted_history_not_read_again(self):
        with patch.object(safety, 'check', side_effect=AssertionError('rescan')):
            self.gate(self.base)

    def test_new_clean_commit_and_resume_reuse(self):
        self.commit('source', 'portable', 'New source')
        self.gate()
        with patch.object(safety, 'check', side_effect=AssertionError('rescan')):
            self.gate()

    def test_new_blob_blocks_and_failed_commit_never_cached(self):
        self.commit('source', private_path(), 'New source')
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'machine-home'):
                self.gate()

    def test_deleted_leak_in_outgoing_history_still_blocks(self):
        self.commit('source', private_path(), 'First')
        self.commit('source', 'clean', 'Remove')
        with self.assertRaises(ValueError):
            self.gate()

    def test_commit_message_and_author_are_inspected(self):
        oid = self.commit('source', 'clean', private_path())
        with self.assertRaises(ValueError):
            self.gate(oid)
        self.git('reset', '--hard', self.base)
        self.git('config', 'user.email', 'fixture@' + 'icloud.com')
        oid = self.commit('other', 'clean', 'Change')
        with self.assertRaisesRegex(ValueError, 'personal-email'):
            self.gate(oid)

    def test_new_tag_on_accepted_history_is_inspected(self):
        self.git('tag', '-a', 'vfixture', '-m', private_path(), self.base)
        with self.assertRaises(ValueError):
            self.gate('vfixture')

    def test_other_ancestry_cannot_hide_behind_baseline(self):
        self.git('checkout', '--orphan', 'unrelated')
        self.git('rm', '-rf', '.')
        oid = self.commit('other', private_path(), 'Unrelated')
        with self.assertRaises(ValueError):
            self.gate(oid)

    def test_encoded_paths_and_private_markers(self):
        for text in ('%2f' + 'Users%2ffixture/foo', '~/' + 'Developer/secret',
                     'BEGIN' + '_PRIVATE', 'From ' + 'Claude (handoff)',
                     'ghp_' + 'x' * 35):
            with self.subTest(text=text[:8]), self.assertRaises(ValueError):
                safety.check(text.encode(), 'fixture')

    def test_binary_utf16_even_and_odd_offsets(self):
        for encoding in ('utf-16-le', 'utf-16-be'):
            for prefix in (b'', b'\xff'):
                with self.assertRaises(ValueError):
                    safety.check(prefix + private_path().encode(encoding), 'binary')

    def test_archive_clean_and_metadata_reuse_without_reopen(self):
        archive = self.archive({'App/engine.py': 'portable'})
        with safety.ledger(self.repo) as receipts:
            safety.archive_gate(archive, receipts)
            with patch.object(safety, 'zip_check', side_effect=AssertionError('rescan')):
                safety.archive_gate(archive, receipts)

    def test_archive_replacement_inspected(self):
        archive = self.archive({'App/engine.py': 'portable'})
        with safety.ledger(self.repo) as receipts:
            safety.archive_gate(archive, receipts)
            archive.unlink()
            self.archive({'App/engine.py': private_path()})
            with self.assertRaises(ValueError):
                safety.archive_gate(archive, receipts)

    def test_nested_archive_inspected(self):
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, 'w') as z:
            z.writestr('binary', b'\0' + private_path().encode())
        archive = self.archive({'App/runtime.zip': nested.getvalue()})
        with safety.ledger(self.repo) as receipts, self.assertRaises(ValueError):
            safety.archive_gate(archive, receipts)

    def test_archive_comment_and_unsafe_member_refused(self):
        archive = self.archive({'../escape': 'safe'})
        with safety.ledger(self.repo) as receipts, self.assertRaises(ValueError):
            safety.archive_gate(archive, receipts)
        archive = self.archive({'safe': 'safe'})
        with zipfile.ZipFile(archive, 'a') as z:
            z.comment = private_path().encode()
        with safety.ledger(self.repo) as receipts, self.assertRaises(ValueError):
            safety.archive_gate(archive, receipts)

    def test_size_limit_fails_closed(self):
        archive = self.archive({'safe': '12345'})
        with patch.object(safety, 'MAX_FILE', 4), safety.ledger(self.repo) as receipts:
            with self.assertRaises(ValueError):
                safety.archive_gate(archive, receipts)

    def test_archive_mutation_during_check_not_accepted(self):
        archive = self.archive({'safe': 'safe'})
        original = safety.zip_check
        def mutate(stream, budget):
            original(stream, budget)
            with archive.open('ab') as out:
                out.write(b'changed')
        with patch.object(safety, 'zip_check', side_effect=mutate), safety.ledger(self.repo) as receipts:
            with self.assertRaises(ValueError):
                safety.archive_gate(archive, receipts)
            self.assertFalse(receipts['archives'])

    def test_policy_change_invalidates_generated_receipts(self):
        self.commit('source', 'portable', 'Change')
        self.gate()
        with patch.object(safety, 'POLICY', 'changed'), patch.object(safety, 'check', wraps=safety.check) as checker:
            self.gate()
            self.assertTrue(checker.called)

    def test_evidence_replacement_refuses_baseline_reuse(self):
        self.evidence.write_text('changed evidence')
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            self.gate()

    def test_pre_push_all_refs_and_deletion(self):
        clean = self.base
        bad = self.commit('source', private_path(), 'Change')
        lines = ['refs/heads/a ' + clean + ' refs/heads/a ' + '0'*40,
                 'refs/heads/b ' + bad + ' refs/heads/b ' + '0'*40]
        with self.assertRaises(ValueError):
            safety.pre_push(self.repo, lines)
        safety.pre_push(self.repo, ['refs/heads/gone ' + '0'*40 + ' refs/heads/gone ' + clean])

    def test_install_preserves_unrelated_hooks(self):
        self.git('config', 'core.hooksPath', 'custom-hooks')
        with self.assertRaises(ValueError):
            safety.install(self.repo, self.base, self.evidence)
        self.assertEqual('custom-hooks', self.git('config', '--get', 'core.hooksPath'))

    def test_publication_gate_before_journal_or_api(self):
        with patch.object(publication, 'selection', return_value={'target': self.base}), \
             patch.object(publication.publication_safety, 'release_gate', side_effect=ValueError('blocked')), \
             patch.object(publication.release, 'locked') as lock:
            with self.assertRaisesRegex(ValueError, 'blocked'):
                publication.publish(self.root, 'title', 'notes', authorize=True,
                                    api=lambda _: self.fail('remote call'))
        self.assertFalse((self.root / 'publication.json').exists())

    def test_distribution_gate_before_external_commands(self):
        (self.root / 'state.json').write_text(json.dumps({'app': 'App.app', 'steps': {}}))
        (self.root / 'assembly.json').write_text(json.dumps({'release_source_commit': self.base}))
        for action in ('sign', 'notarize', 'finalize'):
            with patch.object(release.publication_safety, 'app_gate', side_effect=ValueError('blocked')), \
                 patch.object(release, 'run', side_effect=AssertionError('external command')):
                with self.assertRaisesRegex(ValueError, 'blocked'):
                    release.distribute(self.root, action)

    def test_app_checks_changed_members_and_reuses_others(self):
        app = self.root / 'App.app'
        app.mkdir()
        (app / 'binary').write_bytes(b'portable')
        safety.app_gate(self.repo, self.base, app)
        with patch.object(safety, 'check', wraps=safety.check) as checker:
            safety.app_gate(self.repo, self.base, app)
            self.assertEqual(0, checker.call_count)  # name and contents both reused
        (app / 'new').write_bytes(private_path().encode())
        with self.assertRaises(ValueError):
            safety.app_gate(self.repo, self.base, app)

    def test_errors_do_not_echo_private_match(self):
        with self.assertRaises(ValueError) as caught:
            safety.check(private_path().encode(), 'fixture')
        self.assertNotIn(private_path(), str(caught.exception))

    def test_new_release_text_rejected_and_accepted_text_reused(self):
        with safety.ledger(self.repo) as receipts:
            safety.text_gate('Public notes', receipts)
            with patch.object(safety, 'check', side_effect=AssertionError('rescan')):
                safety.text_gate('Public notes', receipts)
            with self.assertRaises(ValueError):
                safety.text_gate(private_path(), receipts)

    def test_replacement_objects_do_not_hide_original(self):
        bad = self.commit('source', private_path(), 'Unsafe source')
        self.git('checkout', '--detach', self.base)
        good = self.commit('source', 'clean', 'Safe source')
        self.git('replace', bad, good)
        with self.assertRaises(ValueError):
            self.gate(bad)

    def test_shallow_repository_refused(self):
        (self.repo / '.git/shallow').write_text(self.base + '\n')
        with self.assertRaisesRegex(ValueError, 'shallow'):
            self.gate()

    def test_git_zip_and_lfs_payloads_not_silently_accepted(self):
        archive = self.archive({'hidden': private_path()})
        (self.repo / 'forced.zip').write_bytes(archive.read_bytes())
        self.git('add', 'forced.zip')
        self.git('commit', '-qm', 'New archive')
        with self.assertRaises(ValueError):
            self.gate()
        self.git('reset', '--hard', self.base)
        self.commit('pointer', 'version https://git-lfs.github.com/spec/v1\noid sha256:' + 'a'*64, 'LFS')
        with self.assertRaisesRegex(ValueError, 'LFS'):
            self.gate()

    def test_unsupported_compression_refused(self):
        for magic in (b'\x1f\x8b', b'BZh', b'\xfd7zXZ', b'7z\xbc\xaf\x27\x1c'):
            with self.assertRaisesRegex(ValueError, 'unsupported compressed'):
                safety.payload_check(magic + b'fixture', 'fixture')

    def test_archive_overlay_not_ignored(self):
        archive = self.archive({'safe': 'safe'})
        with archive.open('ab') as stream:
            stream.write(private_path().encode())
        with safety.ledger(self.repo) as receipts, self.assertRaisesRegex(ValueError, 'machine-home'):
            safety.archive_gate(archive, receipts)

    def test_archive_private_member_types_refused(self):
        for member in ('App/.git/HEAD', 'App/selection.json', 'App/credential.p12', 'App/input.dcm'):
            archive = self.archive({member: 'safe'})
            with safety.ledger(self.repo) as receipts, self.assertRaisesRegex(ValueError, 'private (?:archive )?member'):
                safety.archive_gate(archive, receipts)

    def test_relative_symlink_escape_refused_and_internal_link_allowed(self):
        archive = self.root / 'link.zip'
        entry = zipfile.ZipInfo('App.app/link')
        entry.create_system = 3
        entry.external_attr = 0o120777 << 16
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr(entry, '../outside')
        with safety.ledger(self.repo) as receipts, self.assertRaisesRegex(ValueError, 'escaping symlink'):
            safety.archive_gate(archive, receipts)
        app = self.root / 'App.app'
        app.mkdir()
        (app / 'link').symlink_to('../outside')
        with self.assertRaises(ValueError):
            safety.app_gate(self.repo, self.base, app)
        (app / 'link').unlink()
        (app / 'file').write_text('safe')
        (app / 'link').symlink_to('file')
        safety.app_gate(self.repo, self.base, app)

    def test_finalize_sanitation_failure_preserves_pending_ownership_for_resume(self):
        app = self.root / 'App.app'
        app.mkdir()
        release.write(self.root / 'state.json', dict(app='App.app', steps={}, notarization={'status':'Accepted'}))
        release.write(self.root / 'assembly.json', dict(release_source_commit=self.base, release='vfixture', bundle_build='2'))
        def step(root, state, name, command):
            if name not in state['steps']:
                if name == 'download':
                    with zipfile.ZipFile(root / 'download.zip', 'w') as z:
                        z.writestr('App.app/file', 'safe')
                state['steps'][name] = {'status':'completed', 'command':command}
                release.write(root / 'state.json', state)
        with patch.object(release.publication_safety, 'app_gate'), \
             patch.object(release, 'step', side_effect=step), \
             patch.object(release.publication_safety, 'ledger') as ledger, \
             patch.object(release.publication_safety, 'archive_gate', side_effect=ValueError('blocked')):
            with self.assertRaisesRegex(ValueError, 'blocked'):
                release.distribute(self.root, 'finalize')
        self.assertTrue(release.read(self.root / 'state.json')['ownership_pending'])
        self.assertFalse((self.root / 'artifact-ownership.json').exists())
        with patch.object(release.publication_safety, 'app_gate'), \
             patch.object(release.publication_safety, 'ledger'), \
             patch.object(release, 'step', side_effect=step):
            release.distribute(self.root, 'finalize')
        self.assertFalse(release.read(self.root / 'state.json').get('ownership_pending'))
        self.assertTrue((self.root / 'artifact-ownership.json').is_file())

    def test_unselected_baseline_refuses_without_scanning_history(self):
        (safety.cache_root(self.repo) / 'accepted-history.json').unlink()
        with patch.object(safety, 'payload_check', side_effect=AssertionError('history scan')):
            with self.assertRaisesRegex(ValueError, 'baseline is required'):
                self.gate()

    def test_new_private_source_and_bundle_file_types_refused(self):
        self.commit('credential.p12', 'opaque secret', 'New credential')
        with self.assertRaisesRegex(ValueError, 'private member type'):
            self.gate()
        app = self.root / 'App.app'
        app.mkdir()
        (app / 'credential.p12').write_bytes(b'opaque secret')
        with self.assertRaisesRegex(ValueError, 'private member type'):
            safety.app_gate(self.repo, self.base, app)

    def test_notarization_archive_gate_runs_before_submit(self):
        app = self.root / 'App.app'
        app.mkdir()
        command = ['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app.resolve()), str((self.root / 'notarization-upload.zip').resolve())]
        release.write(self.root / 'state.json', dict(app='App.app', steps={
            'signature': {'status':'completed'},
            'upload_archive': {'status':'completed', 'command':command, 'output':''}}))
        release.write(self.root / 'assembly.json', dict(release_source_commit=self.base))
        with patch.object(release.publication_safety, 'app_gate'), \
             patch.object(release.publication_safety, 'ledger'), \
             patch.object(release.publication_safety, 'archive_gate', side_effect=ValueError('archive blocked')), \
             patch.object(release, 'run', side_effect=AssertionError('notary command')):
            with self.assertRaisesRegex(ValueError, 'archive blocked'):
                release.distribute(self.root, 'notarize', profile='fixture')
        self.assertNotIn('submission_id', release.read(self.root / 'state.json'))

    def test_release_gate_combines_source_text_and_archive(self):
        archive = self.archive({'App.app/file': 'safe'})
        safety.release_gate(self.repo, self.base, 'Public release', 'Public notes', archive)
        with self.assertRaisesRegex(ValueError, 'machine-home'):
            safety.release_gate(self.repo, self.base, 'Public release', private_path(), archive)
        archive.unlink()
        self.archive({'App.app/file': private_path()})
        with self.assertRaisesRegex(ValueError, 'machine-home'):
            safety.release_gate(self.repo, self.base, 'Public release', 'Public notes', archive)

    def test_unrelated_internal_application_names_refused(self):
        with patch.dict(safety.PATTERNS, {'unrelated-internal-app': safety.re.compile(r'\bRestrictedFixtureTool\b')}):
            with self.assertRaises(ValueError):
                safety.check(b'RestrictedFixtureTool', 'fixture')


if __name__ == '__main__':
    unittest.main()
