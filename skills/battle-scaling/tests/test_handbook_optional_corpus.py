"""A missing optional OCR corpus must not block compiled rule access."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import handbook


class HandbookOptionalCorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.clauses = b'{"clauses":[{"id":"fixture-rule","text":"reviewed fixture"}]}'
        self.pages = b'{"sequence_page":1,"text":"synthetic source"}\n'
        self.manifest = {'document_id': 'synthetic-optional', 'page_count': 1, 'sources': [],
                         'corpus_sha256': hashlib.sha256(self.pages).hexdigest(),
                         'reviewed_clauses_sha256': hashlib.sha256(self.clauses).hexdigest()}
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        (self.root / 'reviewed-clauses.json').write_bytes(self.clauses)

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_full_text_keeps_info_and_reviewed_rule(self):
        self.assertFalse(handbook.run({'operation': 'info'}, self.root)['corpus_installed'])
        self.assertEqual(handbook.run({'operation': 'rule', 'clause_id': 'fixture-rule'}, self.root)['status'], 'ok')

    def test_full_text_operations_explain_how_to_supply_the_missing_source(self):
        for request in ({'operation': 'search', 'query': 'synthetic'},
                        {'operation': 'page', 'sequence_page': 1},
                        {'operation': 'render', 'sequence_page': 1, 'output': str(self.root / 'page.png')}):
            with self.subTest(operation=request['operation']):
                with self.assertRaisesRegex(ValueError, 'optional_handbook_corpus_missing.*pages.jsonl'):
                    handbook.run(request, self.root)

    def test_reviewed_index_hash_is_still_checked_without_full_text(self):
        (self.root / 'reviewed-clauses.json').write_bytes(b'{"clauses":[]}')
        with self.assertRaisesRegex(ValueError, 'reviewed clause index hash mismatch'):
            handbook.Handbook(self.root)

    def test_present_full_text_keeps_original_hash_and_page_count_checks(self):
        (self.root / 'pages.jsonl').write_bytes(b'wrong source')
        with self.assertRaisesRegex(ValueError, 'OCR corpus hash mismatch'):
            handbook.Handbook(self.root)
        (self.root / 'pages.jsonl').write_bytes(self.pages)
        store = handbook.Handbook(self.root)
        self.assertTrue(store.corpus_installed)
        self.assertEqual(len(store.pages), 1)
        self.manifest['page_count'] = 2
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'page count/sequence IDs'):
            handbook.Handbook(self.root)


if __name__ == '__main__':
    unittest.main()
