import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from handbook import DATA, Handbook, OptionalCorpusMissing, run
from rule_profiles import resolve

_spec = importlib.util.spec_from_file_location('public_corpus_import', REPO/'tools/import_handbook_corpus.py')
importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importer)


class OptionalHandbookTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.skill = self.root/'skill'
        self.data = self.skill/importer.DATA_RELATIVE
        self.data.mkdir(parents=True)
        self.source = self.root/'authorized-local-corpus'
        self.source.mkdir()
        pages = [{'sequence_page':n, 'text':f'synthetic page {n}'} for n in (1, 2)]
        self.payload = ('\n'.join(json.dumps(page) for page in pages)+'\n').encode('utf-8')
        self.manifest = {'document_id':'synthetic-optional-handbook', 'page_count':2,
                         'sources':[], 'corpus_sha256':hashlib.sha256(self.payload).hexdigest()}
        self.manifest_path = self.data/'manifest.json'
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        (self.data/'reviewed-clauses.json').write_text(json.dumps({'clauses':[{'id':'synthetic-rule', 'text':'reviewed fixture'}]}), encoding='utf-8')
        (self.source/'pages.jsonl').write_bytes(self.payload)

    def tearDown(self):
        self.temporary.cleanup()

    def test_missing_corpus_preserves_info_and_reviewed_rules(self):
        self.assertFalse(run({'operation':'info'}, self.data)['corpus_installed'])
        self.assertEqual(run({'operation':'rule', 'clause_id':'synthetic-rule'}, self.data)['status'], 'ok')
        for request in ({'operation':'search', 'query':'x'}, {'operation':'page', 'sequence_page':1},
                        {'operation':'render', 'sequence_page':1, 'output':str(self.root/'page.png')}):
            with self.subTest(operation=request['operation']), self.assertRaisesRegex(OptionalCorpusMissing, 'import_handbook_corpus.py --source-dir'):
                run(request, self.data)

    def test_default_rule_profile_remains_locked_without_optional_corpus(self):
        self.assertEqual(resolve()['id'], 'wangba-handbook-2026-07-30')
        self.assertEqual(resolve()['document_snapshot']['document_id'], 'wangba-handbook-2026-07-30-9d9440127d33')

    def test_import_checks_locked_hash_and_does_not_modify_manifest(self):
        before = self.manifest_path.read_bytes()
        result = importer.import_corpus(self.source, self.skill)
        self.assertEqual(result['status'], 'installed')
        self.assertEqual((self.data/'pages.jsonl').read_bytes(), self.payload)
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.assertFalse(result['rule_version_changed'])
        self.assertEqual(importer.import_corpus(self.source, self.skill)['status'], 'already_installed')

    def test_import_rejects_mismatched_payload_without_creating_destination(self):
        (self.source/'pages.jsonl').write_bytes(b'wrong corpus')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            importer.import_corpus(self.source, self.skill)
        self.assertFalse((self.data/'pages.jsonl').exists())

    def test_import_never_overwrites_different_existing_corpus(self):
        destination = self.data/'pages.jsonl'
        destination.write_bytes(b'preserve this existing file')
        with self.assertRaisesRegex(ValueError, 'refusing to replace'):
            importer.import_corpus(self.source, self.skill)
        self.assertEqual(destination.read_bytes(), b'preserve this existing file')

    def test_import_rejects_urls_and_network_shares(self):
        for source in ('https://example.invalid/corpus', r'\\server\share\corpus', '//server/share/corpus'):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'local directory'):
                importer.import_corpus(source, self.skill)

    def test_import_refuses_unlocked_manifest(self):
        self.manifest.pop('corpus_sha256')
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'locked corpus_sha256'):
            importer.import_corpus(self.source, self.skill)
        self.assertFalse((self.data/'pages.jsonl').exists())

    @unittest.skipIf((DATA/'pages.jsonl').exists(), 'This case exercises an installation without optional OCR')
    def test_cli_missing_corpus_returns_actionable_error_without_legacy_fallback(self):
        request = self.root/'request.json'
        request.write_text(json.dumps({'operation':'search', 'query':'弱爆城'}), encoding='utf-8')
        result = subprocess.run([sys.executable, str(ROOT/'scripts/battle.py'), 'handbook', '--input', str(request)], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stderr)
        self.assertIn('optional_handbook_corpus_missing', error['error'])
        self.assertIn('no automatic download or legacy fallback', error['error'])


class OptionalCorpusIntegrationTests(unittest.TestCase):
    @unittest.skipUnless((DATA/'pages.jsonl').is_file(), 'Optional locked 310-page OCR corpus is not distributed; import your own local copy to run this test')
    def test_installed_original_corpus_matches_pinned_manifest(self):
        store = Handbook()
        self.assertTrue(store.corpus_installed)
        self.assertEqual(len(store.pages), 310)
        self.assertEqual(store.manifest['corpus_sha256'], 'df0f64e7320e83d39338aff996475e041642a341ff4f768191564eaf35c8119a')
        self.assertEqual(store.search('弱爆城')['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
