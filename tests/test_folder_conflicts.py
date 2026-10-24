"""Folder-assignment reports: specific, locatable, actionable, and free of source identity. All inputs are synthetic."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import unicodedata
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydicom.uid import CTImageStorage, generate_uid

from test_engine import ENGINE, engine, make_dicom

# Invented source identities (PatientID, PatientName). None of these may ever appear in a message.
QUILL = ('40417719', 'QUILL^AURELIA')
ROE = ('55120334', 'ROE^BARNABY')
VANCE = ('61872005', 'VANCE^CORDELIA')
PEOPLE = [(f'8{i:07d}', f'{surname}^{given}') for i, (surname, given) in enumerate(
    [('ZEPHYRINE', 'ODALYS'), ('KESTRELLA', 'MAXIMO'), ('THIBODEAUX', 'LUCIENNE'), ('WINTERBOURNE', 'ALARIC'),
     ('MARGOLIS', 'TAMSIN'), ('ORLANDOVA', 'BENEDIKT'), ('FAIRWEATHER', 'ISOLDE'), ('BLACKTHORNE', 'CASIMIR')])]
STUDY_DATE = '20260102'
# Real-style exports, as in the project's example data: NAME^NAME_MRN_MR_date_time_<protocol suffix>.
ALDER = ('16400001', 'ALDER^EDMUND')
BRAMBLE = ('14300002', 'BRAMBLE^OTTILIE')
DWI = 'T2.3D.Tra.Fast_DWI.RSI_n4__00000'
T2 = 'T2.3D.Tra.Fast_T2.3D.Tra.CS8pr.2mm.18cm.FOR.DIL_n3__00000'


def exported(person, suffix, kind='MR'):
    return f'{person[1]}_{person[0]}_{kind}_2026-01-02_101010_{suffix}'


def ordinal(number):
    return f'{number}{"th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")}'


class FolderConflictTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # The batch folder's own name can carry identity and dates too; it must never be shown.
        self.source = self.root / 'Batch 01.02.2026 QUILL'
        self.source.mkdir()
        self.output = self.root / 'output'
        self.datasets = []

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, relative, person, study, series, number, description, modality='MR', ref=None):
        path = self.source / relative
        ds = make_dicom(path, identity=person[0], study=study, series=series, ref=ref if modality == 'RTSTRUCT' else None)
        ds.PatientName = person[1]
        if not person[1].isascii():
            ds.SpecificCharacterSet = 'ISO_IR 192'
        ds.AccessionNumber = 'ACN' + person[0]
        ds.SeriesNumber = number
        ds.SeriesDescription = description
        ds.StudyDate = STUDY_DATE
        if modality == 'CT':
            ds.Modality = 'CT'
            ds.SOPClassUID = ds.file_meta.MediaStorageSOPClassUID = CTImageStorage
        ds.save_as(path, enforce_file_format=True)
        self.datasets.append(ds)
        return ds

    def series(self, folder, person, study, number, description, count, modality='MR'):
        uid = generate_uid()
        return [self.add(f'{folder}/IM-{i:04d}.dcm', person, study, uid, number, description, modality)
                for i in range(1, count + 1)]

    def rtstruct(self, relative, person, study, image, description='Structures'):
        return self.add(relative, person, study, generate_uid(), 1, description, 'RTSTRUCT', ref=image.SOPInstanceUID)

    def exported_patient(self, folder, person, study):
        self.series(f'{folder}/{exported(person, DWI)}', person, study, 301, 'DWI_RSI', 4)
        self.series(f'{folder}/{exported(person, T2)}', person, study, 201, 'T2 3D Tra', 3)

    def patients(self):
        return {row['id']: (row['files'], row['series']) for row in engine.scan(self.source)[1]}

    def conflict(self):
        """Scan and run the batch: both must stop with one identical, safe message and leave nothing behind."""
        before = {p: p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        with self.assertRaises(engine.BatchError) as scanned:
            engine.scan(self.source)
        with self.assertRaises(engine.BatchError) as ran:
            engine.run(self.source, self.output, progress=lambda *a, **k: None)
        message = str(scanned.exception)
        self.assertEqual(str(ran.exception), message)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.dicom-batch-*')), [])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assert_no_source_identity(message)
        lines = message.splitlines()
        self.assertLessEqual(len(lines), engine.MESSAGE_LINES)
        fixes = [line for line in lines if line.startswith('To fix:')]
        self.assertEqual(len(fixes), 1, message)
        self.assertIn('choose Check Again', fixes[0])
        return lines

    def assert_no_source_identity(self, message):
        forbidden = {str(self.root), str(self.source), self.source.name, '01.02.2026', STUDY_DATE, '2026-01-02', '101010',
                     '1.2.3.4.5', 'Nested'}
        forbidden |= {p.stem for p in self.source.rglob('*.dcm') if re.fullmatch(r'[\d.]+', p.stem)}
        for ds in self.datasets:
            forbidden |= {ds.PatientID, ds.AccessionNumber, ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.SOPInstanceUID}
            forbidden |= {part for part in re.split(r'[\W_]+', unicodedata.normalize('NFC', str(ds.PatientName))) if part}
        forbidden.discard('')
        folded = engine.fold(message)
        for value in forbidden:
            self.assertNotIn(engine.fold(value), folded, f'{value!r} leaked into:\n{message}')
        self.assertIsNone(re.search(r'\d+\.\d+\.\d+', message), message)
        self.assertNotIn(' /', message)
        self.assertFalse(any(line.startswith('/') for line in message.splitlines()))

    # (1) One study in more than one patient folder -------------------------------------------------------
    def test_split_study_names_folders_locations_counts_series_and_likely_misfiled_files(self):
        study = generate_uid()
        images = self.series('90001/T2 Axial', QUILL, study, 201, 'T2 3D Tra', 4)
        self.rtstruct('90002/RT Structures/RS.dcm', QUILL, study, images[0], description='ADTRef_2026-01-02')
        # Exporters name folders after the patient, record number and date; those parts must be masked.
        exporter = 'QUILL^AURELIA_40417719_MR_2026-01-02_101010_DWI.RSI_n2__00000'
        self.series(f'90002/{exporter}', QUILL, study, 301, 'DWI_RSI', 2)
        self.series('90002/Own T2', ROE, generate_uid(), 201, 'T2 3D Tra', 3)
        lines = self.conflict()
        self.assertEqual(lines[0], 'Patient folders 90001 and 90002 contain images from the same study.')
        self.assertIn('• 90001/T2 Axial (4 files, MR series 201 "T2 3D Tra")', lines)
        self.assertIn('• 90002/RT Structures (1 file, RTSTRUCT series 1 "ADTRef_…"), likely misfiled', lines)
        self.assertIn('• 90002/…_MR_…_DWI.RSI_n2__00000 (2 files, MR series 301 "DWI_RSI"), likely misfiled', lines)
        message = '\n'.join(lines)
        self.assertNotIn('Own T2', message)      # 90002's own study is not part of the problem
        self.assertNotIn('Also found', message)  # identity conflicts caused by the split are not repeated
        fix = lines[-1]
        self.assertTrue(fix.startswith('To fix: move the files in 90002/…_MR_…_DWI.RSI_n2__00000 and in 90002/RT Structures '
                                       'into 90001. They most likely belong there, because 90001 holds more of this study\'s files'), fix)
        for phrase in ('they carry a different source patient ID from the other files in 90002',
                       'If 90001 and 90002 are the same person, combine the folders under one number instead.',
                       'Then choose Check Again.'):
            self.assertIn(phrase, fix)
        self.assertEqual(lines[-2], 'One study must stay in one patient folder, or the output would link different patient numbers.')

    def test_split_study_file_directly_inside_a_patient_folder(self):
        study = generate_uid()
        images = self.series('90001/MR', QUILL, study, 201, 'T2', 3)
        self.rtstruct('90002/RS.dcm', QUILL, study, images[0])
        self.series('90002/Own', ROE, generate_uid(), 5, 'Own', 2)
        lines = self.conflict()
        self.assertIn('• directly inside 90002 (1 file, RTSTRUCT series 1 "Structures"), likely misfiled', lines)
        self.assertTrue(lines[-1].startswith('To fix: move the files directly inside 90002 into 90001. They most likely belong there'), lines[-1])

    def test_split_study_rtstruct_only_group_is_the_likely_stray_without_patient_ids(self):
        # Without source patient IDs, the folder holding the study's images is the likely home.
        study = generate_uid()
        images = self.series('90001/MR', ('', 'QUILL^AURELIA'), study, 201, 'T2', 1)
        self.rtstruct('90002/RT/RS.dcm', ('', 'QUILL^AURELIA'), study, images[0])
        lines = self.conflict()
        self.assertIn('• 90002/RT (1 file, RTSTRUCT series 1 "Structures"), likely misfiled', lines)
        self.assertIn('because 90001 holds this study\'s images', lines[-1])

    def test_split_study_copied_series_suggests_deleting_the_copies(self):
        study = generate_uid()
        self.series('90001/MR', QUILL, study, 201, 'T2', 3)
        shutil.copytree(self.source / '90001' / 'MR', self.source / '90002' / 'MR copy')
        self.series('90002/Own', ROE, generate_uid(), 5, 'Own', 2)
        lines = self.conflict()
        self.assertIn('• 90002/MR copy (3 files, MR series 201 "T2"), likely misfiled (copies of files in 90001)', lines)
        self.assertTrue(lines[-1].startswith('To fix: delete the files in 90002/MR copy; they are copies of files already in 90001.'), lines[-1])
        shutil.rmtree(self.source / '90002' / 'MR copy')
        self.assertEqual(self.patients(), {'90001': (3, 1), '90002': (2, 1)})

    def test_split_study_across_three_folders_names_every_stray_and_why(self):
        study = generate_uid()
        self.series('90001/MR', QUILL, study, 201, 'T2', 5)
        self.series('90002/MR', QUILL, study, 202, 'T2 b', 3)
        self.series('90003/Stray', QUILL, study, 203, 'DWI', 8)   # the most files, but inside another patient's folder
        self.series('90003/Own', ROE, generate_uid(), 5, 'Own', 2)
        lines = self.conflict()
        self.assertEqual(lines[0], 'Patient folders 90001, 90002 and 90003 contain images from the same study.')
        self.assertEqual(lines[1], '• 90001/MR (5 files, MR series 201 "T2")')
        self.assertIn('• 90002/MR (3 files, MR series 202 "T2 b"), likely misfiled', lines)
        self.assertIn('• 90003/Stray (8 files, MR series 203 "DWI"), likely misfiled', lines)
        self.assertTrue(lines[-1].startswith(
            'To fix: move the files in 90002/MR and in 90003/Stray into 90001. They most likely belong there, because this study\'s '
            'files in 90003 carry a different source patient ID from the other files in 90003. If 90001, 90002 and 90003 are the '
            'same person'), lines[-1])

    def test_split_study_with_no_clear_home_says_so(self):
        study = generate_uid()
        self.series('90001/A', QUILL, study, 3, 'T2', 2)
        self.series('90002/B', QUILL, study, 4, 'DWI', 2)
        lines = self.conflict()
        self.assertIn('• 90001/A (2 files, MR series 3 "T2")', lines)
        self.assertIn('• 90002/B (2 files, MR series 4 "DWI")', lines)
        self.assertNotIn('likely misfiled', '\n'.join(lines))
        self.assertTrue(lines[-1].startswith('To fix: decide which patient this study belongs to; 90001 and 90002 hold equal '
                                             'parts of it, so it is unclear.'), lines[-1])

    def test_multiple_split_studies_reported_in_one_message(self):
        pairs = [('90001', '90002'), ('90003', '90004'), ('90005', '90006')]
        for (home, stray), person in zip(pairs, PEOPLE):
            study = generate_uid()
            images = self.series(f'{home}/MR', person, study, 201, 'T2', 3)
            self.rtstruct(f'{stray}/RT Structures/RS.dcm', person, study, images[0])
        lines = self.conflict()
        self.assertEqual(lines[0], 'Images from 3 studies are split across patient folders 90001, 90002, 90003, 90004, 90005 and 90006.')
        for number, (home, stray) in enumerate(pairs, 1):
            self.assertIn(f'Study {number} in {home}/MR (3 files, MR series 201 "T2"), also in:', lines)
            self.assertIn(f'• {stray}/RT Structures (1 file, RTSTRUCT series 1 "Structures"), likely misfiled', lines)
        self.assertNotIn('more split studies', '\n'.join(lines))
        # With several studies the fix points back to each study's line, and no separate explanation takes up space.
        self.assertTrue(lines[-1].startswith('To fix: for each study, move the files marked "likely misfiled" into the folder '
                                             'named on that study\'s "Study N in …" line.'), lines[-1])
        self.assertEqual(len(lines), 1 + 2 * len(pairs) + 1)

    def test_many_split_studies_are_capped_but_every_folder_is_named(self):
        folders = [f'9{i:04d}' for i in range(1, 17)]
        for index, person in enumerate(PEOPLE):
            study = generate_uid()
            images = self.series(f'{folders[2 * index]}/MR', person, study, 201, 'T2', 2)
            self.rtstruct(f'{folders[2 * index + 1]}/RT/RS.dcm', person, study, images[0])
        lines = self.conflict()
        message = '\n'.join(lines)
        self.assertTrue(lines[0].startswith('Images from 8 studies are split across patient folders'), lines[0])
        self.assertEqual(sum(line.startswith('Study ') for line in lines), engine.CONFLICT_LIMIT)
        self.assertIn('• and 3 more split studies: 90011 and 90012; 90013 and 90014; 90015 and 90016', lines)
        for folder in folders:
            self.assertIn(folder, message)

    # (2) One source patient ID in more than one patient folder ---------------------------------------------
    def test_same_source_patient_id_in_two_folders(self):
        self.series('90001/T2 Axial', QUILL, generate_uid(), 201, 'T2 3D Tra', 3)
        self.series('90002/T2 Axial', ROE, generate_uid(), 201, 'T2 3D Tra', 2)
        follow_up = generate_uid()
        self.series('90004/Follow-up/DWI', QUILL, follow_up, 301, 'DWI_RSI', 2)
        self.series('90004/Follow-up/T2', QUILL, follow_up, 201, 'T2 3D Tra', 2)
        lines = self.conflict()
        self.assertEqual(lines[0], 'Patient folders 90001 and 90004 contain images with the same source patient ID.')
        self.assertIn('• 90001/T2 Axial (3 files, MR series 201 "T2 3D Tra")', lines)
        self.assertIn('• 90004/Follow-up/DWI and 90004/Follow-up/T2 (4 files, MR series 201 "T2 3D Tra", '
                      'MR series 301 "DWI_RSI")', lines)
        self.assertNotIn('90002', '\n'.join(lines))
        for phrase in ('To fix: if 90001 and 90004 are the same person, combine the folders under one number.',
                       'If they are different people, the source export gave two patients the same patient ID, so check the export.',
                       'Then choose Check Again.'):
            self.assertIn(phrase, lines[-1])

    # (3) More than one source patient identity inside one patient folder ----------------------------------
    def test_conflicting_identities_in_one_folder_are_grouped_by_identity(self):
        self.series('90003/Prostate MR', QUILL, generate_uid(), 201, 'T2 3D Tra', 4)
        self.series('90003/Outside CT', VANCE, generate_uid(), 2, 'Pelvis 3mm', 2, modality='CT')
        self.series('90004/CT', VANCE, generate_uid(), 2, 'Pelvis 3mm', 3, modality='CT')
        lines = self.conflict()
        self.assertEqual(lines[0], 'Patient folder 90003 contains images with 2 different source patient IDs.')
        self.assertIn('• identity 1: 90003/Prostate MR (4 files, MR series 201 "T2 3D Tra")', lines)
        self.assertIn('• identity 2: 90003/Outside CT (2 files, CT series 2 "Pelvis 3mm"), also in 90004', lines)
        self.assertIn('To fix: give each identity its own numeric folder. Keep identity 1 in 90003 and move the identity 2 '
                      'files into 90004 (which already holds that patient).', lines[-1])
        self.assertNotIn('Also found', '\n'.join(lines))

    def test_different_names_under_one_id_and_a_shared_subfolder(self):
        study = generate_uid()
        self.series('90007/Scan', ('77310042', 'LINDQVIST^OSWIN'), study, 3, 'T1', 2)
        self.add('90007/Scan/IM-0099.dcm', ('77310042', 'LINDQVIST^OSWINA'), study, generate_uid(), 4, 'T1 post')
        self.add('90007/IM-0100.dcm', ('', ''), study, generate_uid(), 5, 'Loose')
        lines = self.conflict()
        self.assertEqual(lines[0], 'Patient folder 90007 contains images with 2 different source patient names under one '
                                   'source patient ID.')
        self.assertIn('• identity 1: 90007/Scan (2 files, MR series 3 "T1")', lines)
        self.assertIn('• identity 2: 90007/Scan (1 file, MR series 4 "T1 post")', lines)
        self.assertIn('• no patient name: directly inside 90007 (1 file, MR series 5 "Loose")', lines)
        self.assertEqual(lines[-1], 'To fix: these files share one source patient ID, so they are most likely one person whose '
                                    'patient name was recorded differently (the names are spelled differently). Moving files into '
                                    'another folder will not clear this, because the same ID would then be in two folders. Correct '
                                    'the patient name in the source system so all files match and re-export this patient; if they '
                                    'are different people, correct the patient ID instead. Then choose Check Again.')

    def test_one_person_recorded_two_ways_is_not_told_to_move_files(self):
        # The scanner and the planning system often write the same patient's name differently. Moving files apart can
        # never clear that: the same ID or the same study would then be in two folders. The fix must say so.
        for studies, next_stop in ((1, 'contain images from the same study.'),
                                   (2, 'contain images with the same source patient ID.')):
            with self.subTest(studies=studies):
                shutil.rmtree(self.source)
                self.source.mkdir()
                study = generate_uid()
                images = self.series('90001/MR', ('77310042', 'LINDQVIST^OSWIN'), study, 201, 'T2', 3)
                other = study if studies == 1 else generate_uid()
                self.rtstruct('90001/RT/RS.dcm', ('77310042', 'LINDQVIST^OSWIN^^^'), other, images[0])
                lines = self.conflict()
                self.assertEqual(lines[0], 'Patient folder 90001 contains images with 2 different source patient names '
                                           'under one source patient ID.')
                self.assertIn('• identity 2: 90001/RT (1 file, RTSTRUCT series 1 "Structures")', lines)
                self.assertIn('(the names differ only in spaces or empty ^ components)', lines[-1])
                self.assertIn('Moving files into another folder will not clear this', lines[-1])
                self.assertNotIn('numeric folder', lines[-1])
                # Following the old advice (move identity 2 into a new numeric folder) only trades one stop for another.
                shutil.move(self.source / '90001' / 'RT', self.source / '90007')
                self.assertTrue(self.conflict()[0].endswith(next_stop))

    def test_two_patient_ids_in_one_study_are_treated_as_one_person(self):
        study = generate_uid()
        images = self.series('90001/MR', ('0040417719', QUILL[1]), study, 201, 'T2', 3)
        self.rtstruct('90001/RT/RS.dcm', QUILL, study, images[0])
        lines = self.conflict()
        self.assertEqual(lines[0], 'Patient folder 90001 contains images with 2 different source patient IDs in one study.')
        self.assertTrue(lines[-1].startswith('To fix: these files belong to the same study, so they are most likely one person '
                                             'whose patient ID was recorded differently. Moving files into another folder will '
                                             'not clear this, because the study would then be split across folders.'), lines[-1])
        self.assertNotIn('numeric folder', lines[-1])
        shutil.move(self.source / '90001' / 'RT', self.source / '90007')
        self.assertEqual(self.conflict()[0], 'Patient folders 90001 and 90007 contain images from the same study.')

    def test_name_difference_is_described_without_the_names(self):
        cases = {
            ('DOE^JANE', 'DOE^JANE^^^'): 'the names differ only in spaces or empty ^ components',
            ('DOE^JANE', 'Doe^Jane'): 'the names differ only in capitalization or accents',
            ('GARCÍA^JOSÉ', 'GARCIA^JOSE'): 'the names differ only in capitalization or accents',
            ('DOE^JANE', 'DOE^JANE^M'): 'the names differ after the family and given names, such as a middle name, prefix or suffix',
            ('DOE^JANE', 'Doe^Jane^M'): 'the names differ after the family and given names, such as a middle name, prefix or '
                                        'suffix and in capitalization or accents',
            ('DOE^JANE', 'DOE^JOAN'): 'the names are spelled differently',
        }
        for names, expected in cases.items():
            self.assertEqual(engine.name_difference(names), expected, names)
            for name in names:
                for part in re.split(r'[\W_]+', name):
                    if len(part) >= 3:
                        self.assertNotIn(engine.fold(part), engine.fold(expected))

    def test_folder_of_many_patients_stays_within_the_line_budget(self):
        people = PEOPLE + [(f'7{i:07d}', f'{surname}^ZED') for i, surname in enumerate(
            ['ABERNATHY', 'BRIGHTWATER', 'COLDHARBOUR', 'DUNSTABLE', 'EVERSHOLT', 'FROBISHER'])]
        for index, person in enumerate(people):
            self.series(f'90001/Patient {index:02d}', person, generate_uid(), 201, 'T2', 2)
        lines = self.conflict()
        self.assertEqual(lines[0], f'Patient folder 90001 contains images with {len(people)} different source patient IDs.')
        self.assertEqual(sum(line.startswith('• identity ') for line in lines), 9)
        self.assertIn(f'• and {len(people) - 9} more identities in 90001 ({2 * (len(people) - 9)} files)', lines)
        self.assertIn(f'move the files of identity 2 to identity {len(people)} each into a new numeric folder of its own.', lines[-1])

    # (4) The same instance stored twice -------------------------------------------------------------------
    def test_duplicate_image_reports_both_relative_file_paths(self):
        self.series('90005/T2 Axial', QUILL, generate_uid(), 201, 'T2 3D Tra', 3)
        (self.source / '90005' / 'Extra').mkdir()
        shutil.copyfile(self.source / '90005' / 'T2 Axial' / 'IM-0002.dcm', self.source / '90005' / 'Extra' / 'IM-0002 copy.dcm')
        self.series('90006/T2 Axial', ROE, generate_uid(), 201, 'T2 3D Tra', 2)
        self.assertEqual(self.conflict(), [
            'Patient folder 90005 contains the same image twice.',
            '• 90005/Extra/IM-0002 copy.dcm and 90005/T2 Axial/IM-0002.dcm (MR series 201 "T2 3D Tra")',
            'To fix: remove one of the two copies (90005/Extra holds only copies, so it can be deleted), then choose Check Again.'])

    def test_duplicated_folder_of_uid_named_files_is_grouped_and_masked(self):
        study, series = generate_uid(), generate_uid()
        for _ in range(3):
            self.add(f'90005/T2/{generate_uid()}.dcm', QUILL, study, series, 201, 'T2')
        shutil.copytree(self.source / '90005' / 'T2', self.source / '90005' / 'T2 copy')
        lines = self.conflict()
        self.assertEqual(lines[0], 'Patient folder 90005 contains 3 duplicate images.')
        self.assertEqual(lines[1], '• 3 files in 90005/T2 copy repeat files in 90005/T2 (MR series 201 "T2"), '
                                   'for example 90005/T2/….dcm and 90005/T2 copy/….dcm')
        self.assertEqual(lines[2], 'To fix: remove one of the two copies of each image (90005/T2 copy holds only copies, '
                                   'so it can be deleted), then choose Check Again.')

    # Names stored decomposed (HFS+), without accents, or with accents replaced -------------------------------
    def test_decomposed_accent_stripped_and_replaced_names_are_masked(self):
        # macOS HFS+ volumes store file names decomposed; exporters often drop accents or replace them with '_'.
        person = ('12345', 'GARCÍA^JOSÉ')
        decomposed = (person[0], unicodedata.normalize('NFD', person[1]))
        study = generate_uid()
        images = self.series('90001/MR', person, study, 201, 'T2', 6)
        stray = {unicodedata.normalize('NFD', 'GARCÍA^JOSÉ_12345_RTst_T2'): '90002/…_RTst_T2',
                 'GARCIA^JOSE_12345_MR_DWI': '90002/…_MR_DWI',
                 'GARC_A^JOS__12345_MR_ADC': '90002/…_MR_ADC'}
        folders = list(stray)
        self.rtstruct(f'90002/{folders[0]}/RS.dcm', decomposed, study, images[0])
        self.series(f'90002/{folders[1]}', person, study, 301, 'DWI', 1)
        self.series(f'90002/{folders[2]}', person, study, 401, 'ADC', 1)
        self.series('90002/Own', ROE, generate_uid(), 5, 'Own', 2)
        self.assertIn(folders[0], os.listdir(self.source / '90002'))    # still decomposed on disk
        lines = self.conflict()
        message = '\n'.join(lines)
        self.assertEqual(lines[0], 'Patient folders 90001 and 90002 contain images from the same study.')
        for shown in stray.values():
            self.assertTrue(any(line.startswith(f'• {shown} (1 file, ') for line in lines), message)
        for fragment in ('garc', 'jos', '12345'):
            self.assertNotIn(fragment, engine.fold(message))

    def test_decomposed_file_name_in_a_duplicate_pair_is_masked(self):
        person = ('12345', 'GARCÍA^JOSÉ')
        self.series('90005/T2', person, generate_uid(), 201, 'T2', 2)
        name = unicodedata.normalize('NFD', 'GARCÍA^JOSÉ copia.dcm')
        shutil.copyfile(self.source / '90005' / 'T2' / 'IM-0001.dcm', self.source / '90005' / 'T2' / name)
        lines = self.conflict()
        self.assertEqual(lines[1], '• 90005/T2/… copia.dcm and 90005/T2/IM-0001.dcm (MR series 201 "T2")')
        for fragment in ('garc', 'jos'):
            self.assertNotIn(fragment, engine.fold('\n'.join(lines)))

    # Folders that look alike once patient details are masked -----------------------------------------------
    def test_look_alike_folders_are_told_apart_by_their_hidden_name_start(self):
        # Every patient's export has the same protocol suffixes, so a misfiled series looks like the patient's own.
        self.exported_patient('90001', ALDER, generate_uid())
        self.exported_patient('90006', BRAMBLE, generate_uid())
        shutil.move(self.source / '90001' / exported(ALDER, DWI), self.source / '90006')
        lines = self.conflict()
        shown = f'90006/…_MR_…_{DWI}'
        hint = 'of 2 folders that look alike here, the one whose full name starts like the folder names in 90001'
        self.assertIn(f'• {shown} (4 files, MR series 301 "DWI_RSI"; {hint}), likely misfiled', lines)
        self.assertTrue(lines[-1].startswith(f'To fix: move the files in {shown} ({hint}) into 90001. They most likely belong '
                                             'there, because they carry a different source patient ID'), lines[-1])
        # Following the fix clears the batch and leaves the receiving patient's own look-alike folder in place.
        shutil.move(self.source / '90006' / exported(ALDER, DWI), self.source / '90001')
        self.assertEqual(self.patients(), {'90001': (7, 2), '90006': (7, 2)})

    def test_copied_look_alike_folder_is_named_for_deletion(self):
        self.exported_patient('90001', ALDER, generate_uid())
        self.exported_patient('90006', BRAMBLE, generate_uid())
        shutil.copytree(self.source / '90001' / exported(ALDER, T2), self.source / '90006' / exported(ALDER, T2))
        lines = self.conflict()
        shown = f'90006/…_MR_…_{T2}'
        hint = 'of 2 folders that look alike here, the one whose full name starts like the folder names in 90001'
        self.assertIn(f'• {shown} (3 files, MR series 201 "T2 3D Tra"; {hint}), likely misfiled (copies of files in 90001)', lines)
        self.assertTrue(lines[-1].startswith(f'To fix: delete the files in {shown} ({hint}); they are copies of files '
                                             'already in 90001.'), lines[-1])
        shutil.rmtree(self.source / '90006' / exported(ALDER, T2))
        self.assertEqual(self.patients(), {'90001': (7, 2), '90006': (7, 2)})

    def test_copies_that_cannot_be_told_apart_are_never_called_deletable(self):
        # The home folder keeps its files directly inside, so no folder name identifies the copy: only its position does.
        study = generate_uid()
        self.series('90001', ALDER, study, 201, 'T2 3D Tra', 3)
        self.series(f'90006/{exported(BRAMBLE, T2)}', BRAMBLE, generate_uid(), 201, 'T2 3D Tra', 3)
        copy = self.source / '90006' / exported(ALDER, T2)
        shutil.copytree(self.source / '90001', copy)
        lines = self.conflict()
        shown = f'90006/…_MR_…_{T2}'
        hint = 'the 1st of 2 folders that look alike here, sorted by name'
        self.assertIn(f'• {shown} (3 files, MR series 201 "T2 3D Tra"; {hint}), likely misfiled (copies of files in 90001)', lines)
        self.assertTrue(lines[-1].startswith(f'To fix: move the files in {shown} ({hint}) into 90001.'), lines[-1])
        self.assertIn('they are copies of files already in 90001', lines[-1])
        self.assertNotIn('delete', lines[-1].casefold())

    def test_mixed_identity_look_alike_folders_are_given_their_position(self):
        self.exported_patient('90006', BRAMBLE, generate_uid())
        self.series(f'90006/{exported(ALDER, DWI)}', ALDER, generate_uid(), 301, 'DWI_RSI', 4)
        lines = self.conflict()
        shown = f'90006/…_MR_…_{DWI}'
        self.assertEqual(lines[1], f'• identity 1: {shown} (the 2nd of 2 folders that look alike here, sorted by name) and '
                                   f'90006/…_MR_…_{T2} (7 files, MR series 201 "T2 3D Tra", MR series 301 "DWI_RSI")')
        self.assertEqual(lines[2], f'• identity 2: {shown} (4 files, MR series 301 "DWI_RSI"; the 1st of 2 folders that look '
                                   'alike here, sorted by name)')
        # Finder lists the identity 2 folder first when sorted by name.
        self.assertEqual(sorted(os.listdir(self.source / '90006'))[0], exported(ALDER, DWI))

    def test_duplicate_with_look_alike_file_names_gives_each_position(self):
        study, series = generate_uid(), generate_uid()
        names = [f'{generate_uid()}.dcm' for _ in range(5)]
        for name in names:
            self.add(f'90005/T2/{name}', QUILL, study, series, 201, 'T2')
        copy = f'{generate_uid()}.dcm'
        shutil.copyfile(self.source / '90005' / 'T2' / names[2], self.source / '90005' / 'T2' / copy)
        lines = self.conflict()
        def natural(name):      # Finder compares runs of digits by value
            return [(0, int(run), '') if run.isdigit() else (1, 0, run) for run in re.findall(r'\d+|\D', name)]
        order = sorted(names + [copy], key=natural)
        first, again = sorted([names[2], copy])     # the walk meets them in this order
        self.assertEqual(lines[1], f'• MR series 201 "T2": 90005/T2/….dcm (the {ordinal(order.index(first) + 1)} of 6 files '
                                   f'that look alike here, sorted by name) and 90005/T2/….dcm (the '
                                   f'{ordinal(order.index(again) + 1)} of 6 files that look alike here, sorted by name)')
        self.assertEqual(lines[2], 'To fix: remove one of the two copies, then choose Check Again.')

    # Reporting behaviour shared by all four ----------------------------------------------------------------
    def test_unrelated_problems_are_named_after_the_main_one(self):
        study = generate_uid()
        images = self.series('90001/MR', QUILL, study, 201, 'T2', 3)
        self.rtstruct('90002/RT/RS.dcm', QUILL, study, images[0])
        self.series('90005/T2', ROE, generate_uid(), 201, 'T2', 2)
        shutil.copyfile(self.source / '90005' / 'T2' / 'IM-0001.dcm', self.source / '90005' / 'T2' / 'IM-0001 copy.dcm')
        self.series('90007/A', PEOPLE[0], generate_uid(), 1, 'T2', 1)
        self.series('90007/B', PEOPLE[1], generate_uid(), 1, 'T2', 1)
        lines = self.conflict()
        self.assertEqual(lines[0], 'Patient folders 90001 and 90002 contain images from the same study.')
        self.assertEqual(lines[-1], 'Also found: 90007 holds more than one source patient identity; duplicate images in 90005. '
                                    'Choose Check Again after the fix above to see the details.')

    def test_other_scan_errors_keep_their_fixed_messages(self):
        study = generate_uid()
        images = self.series('90001/MR', QUILL, study, 201, 'T2', 2)
        self.rtstruct('90002/RT/RS.dcm', QUILL, study, images[0])
        (self.source / '90003').mkdir()
        (self.source / '90003' / 'bad.dcm').write_bytes(b'not dicom')
        with self.assertRaisesRegex(engine.BatchError, r'^A DICOM file could not be read\. Repair or remove the malformed input before retrying\.$'):
            engine.scan(self.source)
        (self.source / '90003' / 'bad.dcm').unlink()
        with self.assertRaisesRegex(engine.BatchError, r'^A patient folder contains no readable DICOM files\.$'):
            engine.scan(self.source)
        (self.source / '90003').rmdir()
        self.assertTrue(self.conflict()[0].startswith('Patient folders 90001 and 90002'))

    def test_cli_scan_reports_the_same_message_without_absolute_paths(self):
        study = generate_uid()
        images = self.series('90001/MR', QUILL, study, 201, 'T2', 2)
        self.rtstruct('90002/RT/RS.dcm', QUILL, study, images[0])
        result = subprocess.run([sys.executable, str(ENGINE), '--source', str(self.source), '--scan'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, '')
        event = json.loads(result.stdout)
        self.assertEqual(event['event'], 'error')
        with self.assertRaises(engine.BatchError) as caught:
            engine.scan(self.source)
        self.assertEqual(event['message'], str(caught.exception))
        self.assertNotIn(str(self.root), result.stdout)
        self.assert_no_source_identity(result.stdout)

    def test_redact_masks_names_ids_dates_and_uids(self):
        terms = {'quill', 'aurelia', '40417719', 'no'}
        cases = {
            'QUILL^AURELIA_40417719_RTst_2026-01-02_101010_T2.3D.Tra.Fast_ADTRef.2026-01-02_n1__00000':
                '…_RTst_…_T2.3D.Tra.Fast_ADTRef.…_n1__00000',
            '1.3.46.670589.11.79167.5.0.6624.2026091408421134107.dcm': '….dcm',
            'Scan 09.14.2026': 'Scan …', '14-Sep-2026 CT': '… CT', 'Sep 14, 2026 CT': '… CT', 'MRN12345678': 'MRN…',
            'AureliaQ T2': '… T2', 'No contrast': '… contrast', 'Nordic T2': 'Nordic T2',
            'RT Structures': 'RT Structures', 'DWI_RSI': 'DWI_RSI', 'T2 3D Tra CS8pr 2mm 18cm': 'T2 3D Tra CS8pr 2mm 18cm',
        }
        for text, expected in cases.items():
            self.assertEqual(engine.redact(text, terms), expected, text)
        # Terms are folded; names match composed, decomposed, accent-stripped, transliterated or partly replaced.
        terms = {engine.fold(word) for word in ('GARCÍA', 'JOSÉ', 'ÖBERG', '山田', '12012345')}
        cases = {
            unicodedata.normalize('NFD', 'GARCÍA^JOSÉ_RTst'): '…_RTst', 'GARCIA^JOSE_RTst': '…_RTst',
            'garcía josé RTst': '… RTst', 'GARC_A^JOS__RTst': '…__RTst', 'ØBERG T2': '… T2', 'OEBERG T2': 'OEBERG T2',
            '山田太郎_MR': '…_MR', 'Series 201': 'Series 201', 'T2 Axial': 'T2 Axial',
        }
        for text, expected in cases.items():
            self.assertEqual(engine.redact(text, terms), expected, text)


if __name__ == '__main__':
    unittest.main()
