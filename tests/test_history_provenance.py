"""New history-translation boundary only; no real releases or binaries."""
import unittest
import test_release_automation as fixtures

r = fixtures.r


class HistoryProvenanceTests(unittest.TestCase):
    setUp = fixtures.AssemblyTests.setUp
    git = fixtures.AssemblyTests.git
    save = fixtures.AssemblyTests.save
    assemble = fixtures.AssemblyTests.assemble

    def qualify(self):
        self.original = 'a' * 40
        self.native = 'b' * 40
        self.receipt['public_commit'] = self.original
        self.receipt['builds']['native_source_commits'] = {'public': self.native}
        self.metadata.update(source_commit=self.original, native_source_commit=self.native)
        r.write(self.root / 'receipt.json', self.receipt)
        r.write(self.app / 'Contents/Resources/BuildInfo.json', self.metadata)
        self.qualification = dict(schema=1, accepted_verification_reused=True, entries=[
            dict(original_commit=original, sanitized_commit=self.commit, scope=scope,
                 accepted=True, qualification='scoped-history-review')
            for original, scope in ((self.original, 'engine'), (self.native, 'native'))])
        self.manifest['accepted']['history_translation'] = 'qualification.json'
        self.save_qualification()

    def save_qualification(self):
        r.write(self.root / 'qualification.json', self.qualification)
        self.save()

    def test_assembly_preserves_original_build_identity_and_uses_sanitized_engine(self):
        self.qualify()
        before = (self.root / 'receipt.json').read_bytes()
        info = self.assemble()
        self.assertEqual(info['engine_source_commit'], self.commit)
        self.assertEqual(info['native_source_commit'], self.native)
        self.assertEqual(info['native_sanitized_source_commit'], self.commit)
        self.assertEqual(info['accepted_source_commit'], self.original)
        self.assertEqual((self.root / 'receipt.json').read_bytes(), before)
        resources = self.output / 'DICOM Anonymizer 2.0.app/Contents/Resources'
        self.assertEqual((resources / 'engine/worker.py').read_text(), 'accepted engine\n')
        self.assertNotIn('qualification.json', (resources / 'ReleaseInfo.json').read_text())
        self.assertNotIn(str(self.root), (resources / 'BuildInfo.json').read_text())
        self.assertEqual((resources.parent / 'MacOS/DICOMAnonymizer2').read_bytes(), b'accepted product')

    def test_missing_or_duplicate_mapping_is_rejected(self):
        self.qualify()
        for entries in (self.qualification['entries'][:1],
                        self.qualification['entries'] + self.qualification['entries'][:1]):
            with self.subTest(entries=len(entries)):
                self.qualification['entries'] = entries
                self.save_qualification()
                with self.assertRaises(ValueError): r.plan(self.manifest_path, self.repo)

    def test_unaccepted_or_unqualified_mapping_is_rejected(self):
        for key, value in (('accepted', False), ('qualification', ''),
                           ('sanitized_commit', 'main'), ('sanitized_commit', '0' * 40)):
            with self.subTest(key=key, value=value):
                self.qualify()
                self.qualification['entries'][0][key] = value
                self.save_qualification()
                with self.assertRaises((ValueError, r.subprocess.CalledProcessError)):
                    r.plan(self.manifest_path, self.repo)

    def test_translation_cannot_repair_mismatched_original_metadata(self):
        self.qualify()
        self.metadata['native_source_commit'] = self.original
        r.write(self.app / 'Contents/Resources/BuildInfo.json', self.metadata)
        with self.assertRaises(ValueError): r.plan(self.manifest_path, self.repo)

    def test_public_source_cannot_hold_private_qualification(self):
        self.qualify()
        r.write(self.repo / 'qualification.json', self.qualification)
        self.manifest['accepted']['history_translation'] = 'repo/qualification.json'
        self.save()
        with self.assertRaises(ValueError): r.plan(self.manifest_path, self.repo)

    def test_nonancestor_mapping_is_rejected(self):
        self.qualify()
        self.git('checkout', '-qb', 'unselected')
        (self.repo / 'new-file').write_text('fixture')
        self.git('add', 'new-file')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'other')
        other = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '--detach', self.commit)
        self.qualification['entries'][0]['sanitized_commit'] = other
        self.save_qualification()
        with self.assertRaises(r.subprocess.CalledProcessError): r.plan(self.manifest_path, self.repo)

    def test_translation_requires_reuse_attestation(self):
        self.qualify()
        self.qualification['accepted_verification_reused'] = False
        self.save_qualification()
        with self.assertRaises(ValueError): r.plan(self.manifest_path, self.repo)

    def test_replacement_ref_cannot_redirect_qualified_engine_archive(self):
        self.qualify()
        (self.repo / 'engine/worker.py').write_text('replacement engine must not ship\n')
        self.git('add', 'engine/worker.py')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'replacement')
        replacement = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '--detach', self.commit)
        self.git('replace', self.commit, replacement)
        info = self.assemble()
        self.assertEqual(info['engine_source_commit'], self.commit)
        self.assertEqual(info['release_source_commit'], self.commit)
        self.assertEqual((self.output / 'DICOM Anonymizer 2.0.app/Contents/Resources/engine/worker.py').read_text(),
                         'accepted engine\n')
