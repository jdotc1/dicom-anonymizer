"""Changed-boundary visibility fixtures; no GitHub, app or accepted package use."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_publication_automation as fixtures

publication = fixtures.publication


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PublicationTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.hidden = dict(create=0, upload=0, publish=0, tag=0)
        self.waits = []
        self.read_hook = None
        self.wait_hook = None

    def wait(self, delay):
        self.waits.append(delay)
        if self.wait_hook:
            self.wait_hook()

    def api(self, args):
        result = self.fixture.api(args)
        if '--method' in args:
            return result
        endpoint = args[0]
        if self.read_hook:
            result = self.read_hook(endpoint, result)
        kind = None
        if '/releases?' in endpoint and self.fixture.item:
            kind = 'create'
        elif '/assets?' in endpoint and self.fixture.assets:
            kind = 'upload'
        elif endpoint.endswith('/releases/1') and not self.fixture.item['draft']:
            kind = 'publish'
        elif '/git/ref/' in endpoint and self.fixture.tag:
            kind = 'tag'
        if kind and self.hidden[kind] > 0:
            self.hidden[kind] -= 1
            if kind in ('create', 'upload'):
                return []
            if kind == 'tag':
                raise subprocess.CalledProcessError(1, args, stderr='HTTP 404')
            result = dict(result, draft=True)
        return copy.deepcopy(result)

    def invoke(self, **kwargs):
        return publication.publish(self.fixture.root, 'Preview', 'Notes', authorize=True,
                                   api=self.api, wait=self.wait, **kwargs)

    def state(self):
        return json.loads((self.fixture.root / 'publication.json').read_text())

    def mutations(self):
        return [c for c in self.fixture.calls if '--method' in c]

    def test_delayed_create_upload_and_publish_complete_without_repeated_writes(self):
        self.hidden.update(create=3, upload=3, publish=3)
        state = self.invoke()
        self.assertEqual(self.waits, [1, 2, 4] * 3)
        self.assertEqual(len(self.mutations()), 3)
        self.assertTrue(all(v['status'] == 'completed' for v in state['operations'].values()))

    def test_create_timeout_preserves_journal_and_resume_does_not_recreate(self):
        self.hidden['create'] = 20
        with self.assertRaisesRegex(ValueError, 'create: visibility timeout.*identical'):
            self.invoke()
        state = self.state()
        self.assertEqual(state['operations'], {'create': {'status': 'started'}})
        self.assertEqual(len(self.mutations()), 1)
        self.hidden['create'] = 0
        final = self.invoke()
        self.assertEqual(state['asset_label'], final['asset_label'])
        self.assertEqual(state['selection'], final['selection'])
        self.assertEqual(len(self.mutations()), 3)

    def test_upload_timeout_and_resume_never_upload_twice(self):
        self.hidden['upload'] = 20
        with self.assertRaisesRegex(ValueError, 'upload: visibility timeout'):
            self.invoke()
        self.assertEqual(self.state()['operations']['upload']['status'], 'started')
        self.assertEqual(len(self.mutations()), 2)
        self.hidden['upload'] = 0
        self.invoke()
        self.assertEqual(len(self.mutations()), 3)

    def test_publish_timeout_and_resume_never_publish_twice(self):
        self.hidden['publish'] = 20
        with self.assertRaisesRegex(ValueError, 'publish: visibility timeout'):
            self.invoke()
        self.assertEqual(self.state()['operations']['publish']['status'], 'started')
        self.hidden['publish'] = 0
        self.invoke()
        self.assertEqual(len(self.mutations()), 3)

    def test_lost_publish_response_and_stale_draft_resume_only_reads(self):
        self.fixture.fail = 'PATCH'
        with self.assertRaises(OSError):
            self.invoke()
        self.hidden['publish'] = 4
        def stale_listing(endpoint, result):
            if '/releases?' in endpoint:
                return [dict(self.fixture.item, draft=True)]
            return result
        self.read_hook = stale_listing
        final = self.invoke()
        self.assertEqual(len(self.mutations()), 3)
        self.assertEqual(self.waits, [1, 2, 4])
        self.assertEqual(final['operations']['publish']['status'], 'completed')

    def test_resumed_stale_draft_timeout_never_repeats_patch(self):
        self.fixture.fail = 'PATCH'
        with self.assertRaises(OSError):
            self.invoke()
        self.hidden['publish'] = 20
        def stale_listing(endpoint, result):
            if '/releases?' in endpoint:
                return [dict(self.fixture.item, draft=True)]
            return result
        self.read_hook = stale_listing
        with self.assertRaisesRegex(ValueError, 'publish: visibility timeout'):
            self.invoke()
        self.assertEqual(len(self.mutations()), 3)
        self.assertEqual(self.state()['operations']['publish']['status'], 'started')

    def test_missing_tag_after_publish_is_reconciled_by_reads(self):
        self.hidden['tag'] = 3
        self.invoke()
        self.assertEqual(self.waits, [1, 2, 4])
        self.assertEqual(len(self.mutations()), 3)

    def test_published_resume_waits_for_tag_without_new_mutations(self):
        self.invoke()
        self.hidden['tag'] = 4
        final = self.invoke()
        self.assertEqual(self.waits, [1, 2, 4])
        self.assertEqual(len(self.mutations()), 3)
        self.assertEqual(final['operations']['publish']['status'], 'completed')

    def test_metadata_change_during_final_wait_is_conflict(self):
        self.hidden['publish'] = 1
        def conflict(endpoint, result):
            if self.waits and endpoint.endswith('/releases/1'):
                return dict(result, body='changed during publication')
            return result
        self.read_hook = conflict
        with self.assertRaisesRegex(ValueError, 'metadata differs during publication'):
            self.invoke()
        self.assertEqual(len(self.mutations()), 3)
        self.assertEqual(self.state()['operations']['publish']['status'], 'started')

    def test_remote_read_failure_during_wait_is_not_absence(self):
        self.hidden['create'] = 2
        def fail(endpoint, result):
            if self.waits and '/releases?' in endpoint:
                raise subprocess.CalledProcessError(1, [endpoint], stderr='HTTP 403')
            return result
        self.read_hook = fail
        with self.assertRaises(subprocess.CalledProcessError):
            self.invoke()
        self.assertEqual(self.waits, [1])
        self.assertEqual(len(self.mutations()), 1)
        self.assertEqual(self.state()['operations']['create']['status'], 'started')

    def test_conflicting_release_after_delay_stops_before_upload(self):
        self.hidden['create'] = 1
        def conflict(endpoint, result):
            if self.waits and '/releases?' in endpoint:
                return [dict(self.fixture.item, body='unrelated')]
            return result
        self.read_hook = conflict
        with self.assertRaisesRegex(ValueError, 'metadata differs'):
            self.invoke()
        self.assertEqual(len(self.mutations()), 1)

    def test_conflicting_asset_after_delay_never_publishes(self):
        self.hidden['upload'] = 1
        def conflict(endpoint, result):
            if self.waits and '/assets?' in endpoint:
                return [dict(self.fixture.assets[0], label='unrelated')]
            return result
        self.read_hook = conflict
        with self.assertRaisesRegex(ValueError, 'asset conflicts'):
            self.invoke()
        self.assertEqual(len(self.mutations()), 2)

    def test_duplicate_asset_during_confirmation_is_conflict(self):
        def duplicate(endpoint, result):
            if '/assets?' in endpoint and self.fixture.assets:
                return result * 2
            return result
        self.read_hook = duplicate
        with self.assertRaisesRegex(ValueError, 'asset conflicts'):
            self.invoke()
        self.assertEqual(len(self.mutations()), 2)

    def test_tag_change_during_publish_wait_stops_reconciliation(self):
        self.hidden['publish'] = 1
        self.wait_hook = lambda: setattr(self.fixture, 'tag', 'b' * 40)
        with self.assertRaisesRegex(ValueError, 'tag points to another commit'):
            self.invoke()
        self.assertEqual(len(self.mutations()), 3)
        self.assertEqual(self.state()['operations']['publish']['status'], 'started')

    def test_archive_change_during_create_wait_blocks_upload(self):
        self.hidden['create'] = 1
        self.wait_hook = lambda: (self.fixture.root / 'download.zip').write_bytes(b'changed archive')
        with self.assertRaisesRegex(ValueError, 'Selected archive changed'):
            self.invoke()
        self.assertEqual(len(self.mutations()), 1)

    def test_absent_started_operation_requires_explicit_retry_even_after_wait(self):
        self.fixture.fail = 'POST'
        with self.assertRaises(OSError):
            self.invoke()
        self.fixture.item = None
        with self.assertRaisesRegex(ValueError, 'visibility timeout'):
            self.invoke()
        self.assertEqual(len(self.mutations()), 1)
        self.invoke(retry_absent=True)
        self.assertEqual(len(self.mutations()), 4)

    def test_completed_missing_create_is_never_retried(self):
        self.invoke()
        self.fixture.item = None
        with self.assertRaisesRegex(ValueError, 'remote outcome absent/uncertain'):
            self.invoke(retry_absent=True)
        self.assertEqual(len(self.mutations()), 3)


if __name__ == '__main__':
    unittest.main()
