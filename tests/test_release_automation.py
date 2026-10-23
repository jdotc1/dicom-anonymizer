"""Isolated release-tool fixtures; never build/run/sign an actual app."""
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release', Path(__file__).resolve().parents[1] / 'scripts/release.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='release-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        (self.repo / 'engine').mkdir(parents=True)
        (self.repo / 'scripts').mkdir()
        self.profile = r.read(Path(__file__).resolve().parents[1] / 'scripts/release-profile.json')
        r.write(self.repo / 'scripts/release-profile.json', self.profile)
        (self.repo / 'engine/worker.py').write_text('accepted engine\n')
        self.git('init', '-q'); self.git('add', '.'); self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        self.commit = self.git('rev-parse', 'HEAD').strip()
        (self.repo / 'engine/worker.py').write_text('unaccepted working tree\n')
        (self.repo / 'engine/untracked.py').write_text('untracked\n')
        self.app = self.root / 'baseline.app'
        resources = self.app / 'Contents/Resources'
        resources.mkdir(parents=True)
        (self.app / 'Contents/MacOS').mkdir()
        (self.app / 'Contents/MacOS/DICOMAnonymizer2').write_bytes(b'old product')
        (self.app / 'Contents/_CodeSignature').mkdir()
        (self.app / 'Contents/_CodeSignature/CodeResources').write_text('old root signature')
        self.info = dict(CFBundleIdentifier=self.profile['bundle_identifier'], LSMinimumSystemVersion=self.profile['deployment_target'], CFBundleExecutable='DICOMAnonymizer2', CFBundleVersion='1', CFBundleIconName='AppIcon', CFBundleIconFile='AppIcon')
        (self.app / 'Contents/Info.plist').write_bytes(plistlib.dumps(self.info))
        self.metadata = dict(source_commit=self.commit, architecture='arm64', deployment_target=self.profile['deployment_target'], xcode='accepted', swift='accepted', macos_sdk='accepted', swift_language_mode='6', bundled_python={key:'accepted' for key in ('version','distribution','release','target')})
        r.write(resources / 'BuildInfo.json', self.metadata)
        for name in ('Assets.car', 'AppIcon.icns', 'Lumen.bundle/sentinel', 'Python/runtime', 'Python/_CodeSignature/CodeResources'):
            target = resources / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b'preserved')
        (resources / 'Python/link').symlink_to('runtime')
        (resources / 'engine').mkdir()
        (resources / 'engine/stale.py').write_text('old')
        (self.root / 'products').mkdir()
        self.product = self.root / 'products/accepted-native'; self.product.write_bytes(b'accepted product')
        self.receipt = dict(private_commit=self.commit, public_commit=self.commit, builds={'products':['products/accepted-native', 'products/accepted-native']})
        r.write(self.root / 'receipt.json', self.receipt)
        self.manifest = dict(schema=1, variant=self.profile['variant'], baseline_app='baseline.app', build='2', version='2.0', release='fixture-2', evidence_label='accepted-fixture', accepted=dict(receipt='receipt.json', source_pointer=self.profile['source_pointer'], product_pointer=self.profile['product_pointer'], build_metadata='baseline.app/Contents/Resources/BuildInfo.json', reuse_accepted_verification=True))
        self.manifest_path = self.root / 'manifest.json'
        self.output = self.root / 'output'
        self.save()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def save(self):
        r.write(self.manifest_path, self.manifest)

    def assemble(self):
        self.save()
        return r.assemble(self.manifest_path, self.output, self.repo)

    def test_preserves_resources_and_selects_only_accepted_objects(self):
        receipt = self.assemble()
        app = self.output / 'DICOM Anonymizer 2.0.app'
        resources = app / 'Contents/Resources'
        self.assertEqual((resources / 'engine/worker.py').read_text(), 'accepted engine\n')
        self.assertFalse((resources / 'engine/untracked.py').exists())
        self.assertFalse((resources / 'engine/stale.py').exists())
        self.assertEqual((app / 'Contents/MacOS/DICOMAnonymizer2').read_bytes(), b'accepted product')
        self.assertFalse((app / 'Contents/_CodeSignature').exists())
        for name in ('Assets.car','AppIcon.icns','Lumen.bundle/sentinel','Python/runtime','Python/_CodeSignature/CodeResources'):
            self.assertEqual((resources / name).read_bytes(), b'preserved')
        self.assertTrue((resources / 'Python/link').is_symlink())
        self.assertEqual(plistlib.loads((app / 'Contents/Info.plist').read_bytes())['CFBundleIconName'], 'AppIcon')
        self.assertEqual(receipt['source_commit'], self.commit)
        self.assertNotIn(str(self.root), (resources / 'ReleaseInfo.json').read_text())
        self.assertEqual((self.app / 'Contents/MacOS/DICOMAnonymizer2').read_bytes(), b'old product')

    def test_rejects_variant_swap(self):
        self.manifest['variant'] = 'other'
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_receipt_selector_swap(self):
        self.manifest['accepted']['source_pointer'] = '/wrong'
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_unaccepted_selection(self):
        self.manifest['accepted']['reuse_accepted_verification'] = False
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_metadata_source_mismatch(self):
        self.metadata['source_commit'] = '0'*40
        r.write(self.app / 'Contents/Resources/BuildInfo.json', self.metadata)
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_incomplete_runtime_metadata(self):
        self.metadata['bundled_python']={'version':'accepted'}
        r.write(self.app/'Contents/Resources/BuildInfo.json',self.metadata)
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_uncommitted_release_profile(self):
        (self.repo/'scripts/release-profile.json').write_text('{}')
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_wrong_bundle(self):
        self.info['CFBundleIdentifier'] = 'wrong'
        (self.app / 'Contents/Info.plist').write_bytes(plistlib.dumps(self.info))
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_existing_output(self):
        self.output.mkdir()
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_nonincreasing_build(self):
        self.manifest['build'] = '1'
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_output_inside_input(self):
        self.output = self.app / 'nested'
        with self.assertRaises(ValueError): self.assemble()

    def test_rejects_mutable_symlink_without_touching_target(self):
        target = self.app / 'Contents/Resources/ReleaseInfo.json'
        outside = self.root / 'outside'; outside.write_text('untouched')
        target.symlink_to(outside)
        with self.assertRaises(ValueError): self.assemble()
        self.assertEqual(outside.read_text(), 'untouched')
        self.assertFalse(self.output.exists())

    def test_inherited_metadata_temp_symlink_cannot_redirect_write(self):
        outside=self.root/'external'; outside.write_text('preserved external')
        (self.app/'Contents/Resources/BuildInfo.json.tmp').symlink_to(outside)
        self.assemble()
        self.assertEqual(outside.read_text(),'preserved external')

    def test_archive_failure_leaves_no_artifact(self):
        original = r.subprocess.run
        def fail_archive(command, **kwargs):
            if 'archive' in command: raise RuntimeError('fixture archive failure')
            return original(command, **kwargs)
        with patch.object(r.subprocess, 'run', side_effect=fail_archive):
            with self.assertRaises(RuntimeError): self.assemble()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.release-*')))

    def test_rejects_engine_symlink_from_git_archive(self):
        (self.repo / 'engine/link').symlink_to('/tmp/outside')
        self.git('add', 'engine/link')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','symlink fixture')
        source=self.git('rev-parse','HEAD').strip()
        self.receipt[self.profile['source_pointer'][1:]]=source
        r.write(self.root/'receipt.json',self.receipt)
        self.metadata['source_commit']=source
        r.write(self.app/'Contents/Resources/BuildInfo.json',self.metadata)
        with self.assertRaises(ValueError): self.assemble()
        self.assertFalse(self.output.exists())


    def test_pointer_escaping_and_arrays(self):
        self.assertEqual(r.pointer({'a/b': {'~x':['ok']}}, '/a~1b/~0x/0'), 'ok')


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='release-stages-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        r.write(self.root / 'state.json', dict(schema=1, app='fixture.app', steps={}))

    def test_sign_resume_reuses_completed_checks(self):
        with patch.object(r, 'run', return_value='') as run:
            # step resolves its runner at definition time: patch the injectable wrapper below.
            with patch.object(r, 'step', wraps=lambda root,state,name,command: real_step(root,state,name,command,runner=run)):
                r.distribute(self.root, 'sign', 'Developer ID Application: Fixture')
                r.distribute(self.root, 'sign', 'Developer ID Application: Fixture')
        self.assertEqual(run.call_count, 2)
        self.assertNotIn('--deep', str(run.call_args_list))

    def test_uncertain_step_is_not_repeated(self):
        state = r.read(self.root / 'state.json'); state['steps']['sign']={'status':'started'}
        with patch.object(r, 'run') as run:
            with self.assertRaises(ValueError): real_step(self.root,state,'sign',['fixture'],runner=run)
            run.assert_not_called()

    def test_notary_requires_signed_artifact(self):
        with self.assertRaises(ValueError): r.distribute(self.root, 'notarize', profile='fixture')

    def test_finalize_requires_accepted(self):
        with self.assertRaises(ValueError): r.distribute(self.root, 'finalize')

    def test_notary_submits_once_and_reuses_acceptance(self):
        state=r.read(self.root/'state.json');state['steps']['signature']={'status':'completed'};r.write(self.root/'state.json',state)
        def fake(command):
            if 'submit' in command: return json.dumps({'id':'11111111-1111-1111-1111-111111111111'})
            if 'info' in command: return json.dumps({'status':'Accepted'})
            return ''
        with patch.object(r, 'run', side_effect=fake) as run:
            with patch.object(r, 'step', wraps=lambda root,state,name,command: real_step(root,state,name,command,runner=run)):
                r.distribute(self.root,'notarize',profile='fixture')
                r.distribute(self.root,'notarize',profile='fixture')
        self.assertEqual(run.call_count,3)

    def test_finalize_reuses_each_completed_stage(self):
        state=r.read(self.root/'state.json');state['notarization']={'status':'Accepted'};r.write(self.root/'state.json',state)
        with patch.object(r,'run',return_value='') as run:
            r.distribute(self.root,'finalize')
            r.distribute(self.root,'finalize')
        self.assertEqual(run.call_count,4)

    def test_interrupted_submission_can_adopt_known_id_without_resubmit(self):
        state=r.read(self.root/'state.json')
        state['steps']['signature']={'status':'completed'}
        state['steps']['submit']={'status':'started'}
        r.write(self.root/'state.json',state)
        with patch.object(r,'run',return_value='') as run:
            with self.assertRaises(ValueError): r.distribute(self.root,'notarize',profile='fixture')
            self.assertEqual(run.call_count,1)  # upload creation only; never submit again
        with patch.object(r,'run',return_value=json.dumps({'status':'Accepted'})) as run:
            r.distribute(self.root,'notarize',profile='fixture',submission_id='11111111-1111-1111-1111-111111111111')
            self.assertEqual(run.call_count,1)
            self.assertIn('info',run.call_args.args[0])

    def test_completed_step_rejects_changed_arguments(self):
        state=r.read(self.root/'state.json')
        state['steps']['sign']={'status':'completed','command':['original'],'output':''}
        with self.assertRaises(ValueError): r.step(self.root,state,'sign',['changed'])

    def test_failed_external_step_retains_uncertain_state(self):
        state=r.read(self.root/'state.json')
        with self.assertRaises(RuntimeError):
            r.step(self.root,state,'sign',['fixture'],runner=lambda _: (_ for _ in ()).throw(RuntimeError('interrupted')))
        self.assertEqual(r.read(self.root/'state.json')['steps']['sign']['status'],'started')

    def test_lock_excludes_concurrent_mutation(self):
        with r.locked(self.root):
            with self.assertRaises(FileExistsError): r.distribute(self.root,'finalize')


real_step = r.step
if __name__ == '__main__':
    unittest.main()
