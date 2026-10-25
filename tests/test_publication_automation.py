"""New publication-only fixtures; no remote calls or accepted package reads."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publication


class PublicationTests(unittest.TestCase):
    def setUp(self):
        gate = patch.object(publication.publication_safety, 'release_gate')
        gate.start()
        self.addCleanup(gate.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.sha = 'a' * 40
        self.item = None
        self.assets = []
        self.calls = []
        self.fail = None
        self.tag = None
        (self.root / 'download.zip').write_bytes(b'synthetic')
        self.write('state.json', {'notarization': {'status': 'Accepted'}, 'steps': {
            k: {'status': 'completed', 'command': ['ditto', str(self.root / 'download.zip')]}
            for k in ('sign', 'signature', 'staple', 'staple_validation', 'gatekeeper', 'download')}})
        self.write('assembly.json', {'variant': 'public', 'release': 'v2.0.0-preview.99',
                   'release_source_commit': self.sha, 'bundle_build': '99'})
        self.write('selection.json', {'profile': {'variant': 'public', 'bundle_identifier': 'io.github.jdotc1.dicom-anonymizer'},
            'manifest': {'release': 'v2.0.0-preview.99', 'build': 99}, 'release_source_commit': self.sha})

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def api(self, args):
        self.calls.append(args)
        endpoint = args[0]
        method = args[args.index('--method') + 1] if '--method' in args else 'GET'
        if method == 'POST' and '/assets?' in endpoint:
            fields = dict(x.split('=', 1) for x in endpoint.split('?', 1)[1].split('&'))
            self.assets.append(dict(name=fields['name'], label=fields['label'], state='uploaded', size=9))
        elif method == 'POST':
            fields = dict(args[i + 1].split('=', 1) for i, x in enumerate(args) if x in ('-f', '-F'))
            self.item = dict(id=1, tag_name=fields['tag_name'], target_commitish=fields['target_commitish'],
                             name=fields['name'], body=fields['body'], draft=True, prerelease=True, html_url='https://example.invalid/release')
        elif method == 'PATCH':
            self.item['draft'] = False
            self.tag = self.sha
        else:
            if '/git/ref/' in endpoint:
                if self.tag is None:
                    raise subprocess.CalledProcessError(1, args, stderr='HTTP 404')
                return {'object': {'type': 'commit', 'sha': self.tag}}
            if '/assets?' in endpoint:
                return self.assets
            if '/releases?' in endpoint:
                return [self.item] if self.item else []
            if endpoint.endswith('/releases/1'):
                return self.item
            return {'full_name': publication.REPOSITORY, 'private': False}
        if self.fail == method + ('upload' if '/assets?' in endpoint else ''):
            self.fail = None
            raise OSError('response lost')
        return {}

    def invoke(self, **kwargs):
        return publication.publish(self.root, 'Preview', 'Notes', authorize=True, api=self.api, **kwargs)

    def test_complete_then_resume_has_no_repeated_mutations(self):
        self.invoke()
        count = sum('--method' in c for c in self.calls)
        self.invoke()
        self.assertEqual(count, sum('--method' in c for c in self.calls))

    def test_lost_create_upload_publish_responses_reconcile(self):
        for failure in ('POST', 'POSTupload', 'PATCH'):
            with self.subTest(failure=failure):
                self.setUp()
                self.fail = failure
                with self.assertRaises(OSError):
                    self.invoke()
                self.invoke()
                self.assertEqual(3, sum('--method' in c for c in self.calls))

    def test_authority_required(self):
        with self.assertRaises(ValueError):
            publication.publish(self.root, 'Preview', 'Notes', api=self.api)
        self.assertFalse(self.calls)

    def test_unfinalized_refused(self):
        state = publication.release.read(self.root / 'state.json')
        state['steps']['gatekeeper']['status'] = 'started'
        self.write('state.json', state)
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertFalse(self.calls)

    def test_archive_changed_refused_on_resume(self):
        self.invoke()
        (self.root / 'download.zip').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.invoke()

    def test_unrelated_same_name_asset_never_overwritten(self):
        self.fail = 'POST'
        with self.assertRaises(OSError):
            self.invoke()
        self.assets = [dict(name='DICOM-Anonymizer-2.0.0-preview.99-standalone-macOS-arm64.zip', size=9, state='uploaded', label='unrelated')]
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertFalse(any('/assets?' in c[0] and '--method' in c for c in self.calls))

    def test_wrong_tag_refused(self):
        self.tag = 'b' * 40
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertFalse(any('--method' in c for c in self.calls))

    def test_absent_uncertain_operation_requires_explicit_retry(self):
        self.fail = 'POST'
        with self.assertRaises(OSError):
            self.invoke()
        self.item = None
        with self.assertRaises(ValueError):
            self.invoke()
        self.invoke(retry_absent=True)

    def test_upload_absolute_url_and_paginated_confirmation(self):
        unrelated = [dict(name='other-' + str(i)) for i in range(100)]
        def api(args):
            if '/assets?' in args[0] and '--method' not in args:
                page = int(args[0].rsplit('page=', 1)[1])
                self.calls.append(args)
                return unrelated if page == 1 else self.assets
            if '/assets?' in args[0] and '--method' in args:
                self.assertTrue(args[0].startswith('https://uploads.github.com/repos/jdotc1/dicom-anonymizer/releases/1/assets?'))
                self.assertEqual(args[args.index('--hostname') + 1], 'github.com')
                self.assertEqual(args[args.index('--input') + 1], str(self.root / 'download.zip'))
            return self.api(args)
        self.invoke_with_api = publication.publish(self.root, 'Preview', 'Notes', authorize=True, api=api)
        self.assertFalse(self.item['draft'])
        self.assertEqual(2, sum('/assets?per_page=100&page=2' in c[0] for c in self.calls))

    def test_tag_changed_during_upload_blocks_publication(self):
        def api(args):
            result = self.api(args)
            if '/assets?' in args[0] and '--method' in args:
                self.tag = 'c' * 40
            return result
        with self.assertRaises(ValueError):
            publication.publish(self.root, 'Preview', 'Notes', authorize=True, api=api)
        self.assertTrue(self.item['draft'])
        self.assertFalse(any('PATCH' in c for c in self.calls))

    def test_unowned_existing_draft_refused(self):
        self.item = dict(id=1, tag_name='v2.0.0-preview.99', draft=True)
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertFalse(any('--method' in c for c in self.calls))

    def test_remote_errors_never_treated_as_absence(self):
        def failure(args):
            raise subprocess.CalledProcessError(1, args, stderr='HTTP 403')
        with self.assertRaises(subprocess.CalledProcessError):
            publication.publish(self.root, 'Preview', 'Notes', authorize=True, api=failure)
        self.assertFalse(self.calls)

if __name__ == '__main__':
    unittest.main()
