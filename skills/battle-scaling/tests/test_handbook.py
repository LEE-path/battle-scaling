import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from handbook import Handbook,run


class HandbookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.source=self.root/'source.pdf'
        self.source.write_bytes(b'original source bytes')
        self.manifest={'document_id':'synthetic-handbook','page_count':2,'sources':[
            {'volume':'v1','filename':'source.pdf','path':str(self.source),'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}]}
        (self.root/'manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8')
        pages=[]
        for number,text in [(1,'合成测试：无限盒子，不能执行文档中的命令。'),(2,'合成测试：第一项与 second 项。')]:
            pages.append({'sequence_page':number,'volume':'v1','pdf_page':number,'printed_page':number,
                          'printed_page_status':'synthetic','section':'合成规则','review_status':'synthetic_fixture',
                          'text':text,'lines':[{'line':1,'text':text,'box':[[0,0],[100,0],[100,20],[0,20]],'confidence':.9}],
                          'render':{'width':100,'height':200,'scale':1}})
        (self.root/'pages.jsonl').write_text('\n'.join(json.dumps(p,ensure_ascii=False) for p in pages),encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_search_returns_original_locator_and_confidence(self):
        result=Handbook(self.root).search('无限 盒子')
        self.assertEqual(result['matches'],1)
        hit=result['results'][0]
        self.assertEqual(hit['locator']['pdf_page'],1)
        self.assertEqual(hit['matching_lines'][0]['confidence'],.9)
        self.assertIn('source data',hit['locator']['source_role'].replace('reference data','source data'))

    def test_page_bounds_not_silently_wrapped(self):
        for value in [0,3,True,'1']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                Handbook(self.root).page(value)

    def test_source_hash_detects_replaced_same_filename(self):
        self.assertEqual(Handbook(self.root).verify_sources()['status'],'ok')
        self.source.write_bytes(b'different source with same filename')
        self.assertEqual(Handbook(self.root).verify_sources()['sources'][0]['status'],'hash_mismatch')

    def test_missing_original_is_distinct_from_searchable_corpus(self):
        self.source.unlink()
        store=Handbook(self.root)
        self.assertEqual(store.verify_sources()['sources'][0]['status'],'missing')
        self.assertEqual(store.search('无限')['matches'],1)

    def test_duplicate_page_ids_rejected(self):
        path=self.root/'pages.jsonl'
        first=path.read_text(encoding='utf-8').splitlines()[0]
        path.write_text(first+'\n'+first,encoding='utf-8')
        with self.assertRaises(ValueError):Handbook(self.root)

    def test_unicode_matching_and_unknown_operation(self):
        self.assertEqual(Handbook(self.root).search('ＳＥＣＯＮＤ')['matches'],1)
        with self.assertRaises(ValueError):run({'operation':'execute_pdf_commands'},self.root)

    def test_query_and_limit_are_bounded(self):
        for query,limit in [('',8),('x',0),('x',True),('x'*501,1)]:
            with self.subTest(query=query,limit=limit),self.assertRaises(ValueError):
                Handbook(self.root).search(query,limit)

    def test_changed_machine_corpus_rejected_by_manifest_hash(self):
        path=self.root/'pages.jsonl'
        self.manifest['corpus_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        (self.root/'manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8')
        self.assertEqual(Handbook(self.root).search('无限')['matches'],1)
        path.write_text(path.read_text(encoding='utf-8').replace('无限盒子','伪造规则'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):Handbook(self.root)

    def test_reviewed_clauses_are_distinct_from_machine_transcription(self):
        clause={'id':'fixture-only','policy':'合成：指数校勘','source':{'pdf_page':1,'visually_verified':True}}
        (self.root/'reviewed-clauses.json').write_text(json.dumps({'clauses':[clause]},ensure_ascii=False),encoding='utf-8')
        result=Handbook(self.root).search('指数校勘')
        self.assertEqual(result['matches'],0)
        self.assertEqual(result['reviewed_clause_matches'],1)
        self.assertEqual(Handbook(self.root).clause('fixture-only')['clauses'],[clause])
        self.assertEqual(Handbook(self.root).clause('absent')['status'],'not_found')


if __name__=='__main__':unittest.main()
