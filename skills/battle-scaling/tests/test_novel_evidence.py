"""Local book snapshots are evidence candidates, not authenticated fiction."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from novel_evidence import run


class NovelEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'bundles'

    def book(self, name='book.txt', text='前言\n第一章 开始\n甲破墙。\n\n第十章 结尾\n甲胜利。\n'):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode('utf-8'))
        return p

    def index(self, source, **kw):
        return run({'op':'index', 'source':str(source), 'output_dir':str(self.out),
                    'work_id':'synthetic:book', 'edition_id':'edition:one', **kw})

    def query(self, indexed, **kw):
        return run({'op':'search', 'bundle':indexed['bundle'], **kw})

    def test_source_copy_hash_and_original_unchanged(self):
        p = self.book(); original = p.read_bytes()
        b = self.index(p)
        self.assertEqual(b['status'], 'indexed')
        source = b['sources'][0]
        self.assertEqual(source['source_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual((Path(b['bundle']) / source['raw_snapshot']).read_bytes(), original)
        self.assertEqual(p.read_bytes(), original)
        self.assertEqual(source['authentication'], 'provided_not_authenticated')
        self.assertFalse(b['coverage']['semantic_read_verified'])

    def test_chinese_ending_order_and_prelude(self):
        b = self.index(self.book(text='前言有甲。\n第一章 初始\n甲击石。\n第十章 末尾\n甲破墙。\n'))
        r = self.query(b, query='甲', context_lines=0)
        self.assertEqual([x['chapter']['title'] for x in r['results']], ['第十章 末尾','第一章 初始','(prelude)'])
        self.assertEqual(r['order'], 'ending_backward')
        self.assertFalse(r['coverage']['whole_book_read'])

    def test_preserves_whitespace_offsets_and_exact_excerpt(self):
        text='  序言  \r\n\r\n第一章 原文\r\n  甲\t破墙。  \r\n\r\n'
        b = self.index(self.book(text=text))
        hit = self.query(b, query='甲', context_lines=0)['results'][0]
        self.assertIn('  甲\t破墙。  ', hit['exact_text'])
        self.assertEqual(text[hit['char_start']:hit['char_end']], hit['exact_text'])
        self.assertEqual(hit['line_start'], 4)
        self.assertEqual(hit['offset_space'], 'extracted_text_unicode_characters')

    def test_refpack_prefers_raw_and_reports_derived_boundary(self):
        root=self.root/'pack'; self.book('pack/raw/_all.txt', '第一章 初始\n原著。\n第二章 结局\n原作终章。\n')
        self.book('pack/chunks/chunk_01.txt','污染！')
        self.book('pack/canon/00_正典边界.md','本书用于续写，已剔除原第2章。')
        self.book('pack/notes/meta_ending.md','自写结局。')
        b=self.index(root)
        self.assertEqual(len(b['sources']),1)
        self.assertEqual(b['sources'][0]['role'],'original_text_candidate')
        self.assertGreaterEqual(len(b['derived_navigation']),2)
        self.assertTrue(any('canon' in x for x in b['warnings']))
        self.assertEqual(self.query(b,query='污染')['results'],[])
        self.assertEqual(self.query(b,query='自写结局')['results'],[])
        self.assertTrue(self.query(b,query='原作终章')['results'])

    def test_cross_chunk_natural_order_without_offset_addition(self):
        self.book('pack/chunks/chunk_2.txt','第二章\n\n甲先破墙。\n')
        self.book('pack/chunks/chunk_10.txt','第十章\n甲后破城。\n')
        b=self.index(self.root/'pack')
        rows=self.query(b,query='甲',context_lines=0)['results']
        self.assertEqual(rows[0]['chapter']['title'],'第十章')
        self.assertEqual(rows[0]['char_start'],len('第十章\n'))
        self.assertNotEqual(rows[0]['source_id'],rows[1]['source_id'])

    def test_explicit_derived_file_cannot_upgrade(self):
        p=self.book('pack/canon/04_设定判据.md','作者说甲全能。')
        b=self.index(p, source_role='original_text_candidate', authentication='verified')
        self.assertEqual(b['sources'][0]['role'],'derived_navigation_only')
        row=self.query(b,query='全能')['results'][0]
        self.assertEqual(row['role'],'derived_navigation_only')
        self.assertFalse(row['original_verified'])

    def test_inventory_never_imports_notes_as_original(self):
        self.book('pack/chunks/chunk_1.txt')
        self.book('pack/out/整书总结.md','总结。')
        r=run({'op':'inventory','source':str(self.root/'pack')})
        self.assertEqual(len(r['candidates']),1)
        self.assertEqual(r['derived_navigation'][0]['role'],'derived_navigation_only')

    def test_limit_and_truncated(self):
        b=self.index(self.book(text='第一章\n'+'甲\n'*210))
        r=self.query(b,query='甲',limit=2,context_lines=0)
        self.assertEqual(len(r['results']),2)
        self.assertTrue(r['truncated'])
        with self.assertRaises(ValueError): self.query(b,query='甲',limit=201)
        with self.assertRaises(ValueError): self.query(b,query='甲',context_lines=51)

    def test_read_bounded_actual_window_and_no_semantic_claim(self):
        b=self.index(self.book()); sid=b['sources'][0]['id']
        r=run({'op':'read','bundle':b['bundle'],'source_id':sid,'line_start':2,'line_end':3})
        self.assertEqual(r['window']['line_start'],2)
        self.assertEqual(r['window']['line_end'],3)
        self.assertEqual(r['coverage']['displayed_windows'][0]['line_start'],2)
        self.assertFalse(r['coverage']['whole_book_read'])
        self.assertFalse(r['coverage']['semantic_read_verified'])
        with self.assertRaises(ValueError): run({'op':'read','bundle':b['bundle'],'source_id':sid,'line_start':1,'line_end':1001})

    def test_text_tampering_blocks_search_and_read(self):
        b=self.index(self.book()); s=b['sources'][0]
        (Path(b['bundle'])/s['text_snapshot']).write_text('伪证。',encoding='utf-8')
        self.assertEqual(run({'op':'verify','bundle':b['bundle']})['status'],'tampered')
        self.assertEqual(self.query(b,query='伪证')['status'],'tampered')
        self.assertEqual(run({'op':'read','bundle':b['bundle'],'source_id':s['id'],'line_start':1,'line_end':1})['status'],'tampered')

    def test_raw_tamper_and_manifest_tamper_block(self):
        b=self.index(self.book()); s=b['sources'][0]
        (Path(b['bundle'])/s['raw_snapshot']).write_bytes(b'changed')
        self.assertEqual(self.query(b,query='甲')['status'],'tampered')
        b=self.index(self.book()); mp=Path(b['bundle'])/'manifest.json'
        manifest=json.loads(mp.read_text(encoding='utf-8')); manifest['edition_id']='spoof'
        mp.write_text(json.dumps(manifest),encoding='utf-8')
        self.assertEqual(run({'op':'verify','bundle':b['bundle']})['status'],'tampered')

    def test_original_change_reported_but_snapshot_stays_usable(self):
        p=self.book(); b=self.index(p); p.write_text('后来修改。',encoding='utf-8')
        r=run({'op':'verify','bundle':b['bundle'],'check_originals':True})
        self.assertEqual(r['status'],'ok')
        self.assertEqual(r['originals'][0]['status'],'changed')
        self.assertTrue(self.query(b,query='甲')['results'])

    def test_invalid_paths_and_output_inside_refpack_rejected(self):
        self.book('pack/raw/_all.txt'); root=self.root/'pack'
        with self.assertRaises(ValueError): self.index(root,output_dir=str(root/'more'))
        with self.assertRaises(ValueError): run({'op':'inventory','source':'https://example.invalid/book'})
        with self.assertRaises(ValueError): self.index(self.book('blob.bin'))

    def test_bad_encoding_requires_explicit_decoder(self):
        p=self.root/'gb.txt'; p.write_bytes('第一章\n甲破墙。'.encode('gb18030'))
        with self.assertRaises(ValueError): self.index(p)
        b=self.index(p,encoding='gb18030')
        self.assertTrue(self.query(b,query='破墙')['results'])

    def test_docx_paragraph_locator(self):
        p=self.root/'book.docx'
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>第一章 初始</w:t></w:r></w:p><w:p><w:r><w:t>甲破墙。</w:t></w:r></w:p></w:body></w:document>'
        with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml',xml)
        row=self.query(self.index(p),query='破墙',context_lines=0)['results'][0]
        self.assertEqual(row['unit_locators'][0]['paragraph'],2)
        self.assertEqual(row['unit_locators'][0]['member'],'word/document.xml')

    def test_epub_spine_order_and_locator(self):
        p=self.root/'book.epub'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>')
            z.writestr('OEBPS/book.opf','<package><manifest><item id="b" href="b.xhtml"/><item id="a" href="a.xhtml"/></manifest><spine><itemref idref="a"/><itemref idref="b"/></spine></package>')
            z.writestr('OEBPS/a.xhtml','<html><body><h2>第一章 初始</h2><p>甲破墙。</p></body></html>')
            z.writestr('OEBPS/b.xhtml','<html><body><h2>第二章 终局</h2><p>甲破城。</p></body></html>')
        rows=self.query(self.index(p),query='甲',context_lines=0)['results']
        self.assertEqual(rows[0]['unit_locators'][0]['member'],'OEBPS/b.xhtml')
        self.assertEqual(rows[0]['unit_locators'][0]['spine_index'],2)

    def test_zip_member_traversal_refused(self):
        p=self.root/'bad.epub'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('META-INF/container.xml','<container><rootfile full-path="../book.opf"/></container>')
            z.writestr('../book.opf','<package/>')
        with self.assertRaises(ValueError):self.index(p)

    def test_empty_query_and_unsupported_operations_rejected(self):
        b=self.index(self.book())
        with self.assertRaises(ValueError):self.query(b,query='')
        with self.assertRaises(ValueError):run({'op':'execute','command':'never'})

    def test_context_crosses_chapter_but_hit_chapter_is_preserved(self):
        b=self.index(self.book(text='序言。\n第一章 起始\n乙过路。\n第十章 终局\n甲破城。\n'))
        hit=self.query(b,query='破城',context_lines=10)['results'][0]
        self.assertEqual(hit['chapter']['title'],'第十章 终局')
        self.assertEqual(hit['line_start'],1)

    def test_early_limit_records_only_actual_scanned_lines(self):
        b=self.index(self.book(text='第一章\n'+'甲\n'*50))
        r=self.query(b,query='甲',limit=1,context_lines=0)
        self.assertLess(r['coverage']['scanned_lines'],10)
        self.assertEqual(r['coverage']['indexed_lines'],51)

    def test_long_line_partial_window_offsets_remain_exact(self):
        text='第一章\n'+'甲'*20000+'目标'+'乙'*20000+'\n'
        b=self.index(self.book(text=text))
        r=self.query(b,query='目标',context_lines=0)['results'][0]
        self.assertTrue(r['truncated'])
        self.assertIn('目标',r['exact_text'])
        self.assertEqual(text[r['char_start']:r['char_end']],r['exact_text'])

    def test_source_snapshot_used_for_zip_extraction(self):
        # An extractor receives already-read bytes; an altered origin must not
        # silently supply different XML while the copied raw hash stays old.
        import novel_evidence as n
        import io
        p=self.root/'book.docx'
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('word/document.xml','<document><p><t>原字节。</t></p></document>')
        p.write_bytes(b'not a zip now')
        text,locators,encoding=n._extract(p,buf.getvalue(),None)
        self.assertIn('原字节',text)

    def test_refpack_engineering_files_remain_unchanged(self):
        self.book('pack/raw/_all.txt','第一章\n正文。\n')
        self.book('pack/chunks/chunk_01.txt','第一章\n正文。\n')
        self.book('pack/canon/00_正典边界.md','项目续写约定。')
        self.book('pack/notes/chunk_01.md','派生摘要。')
        root=self.root/'pack'
        def hashes():return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        before=hashes(); b=self.index(root)
        run({'op':'inventory','source':str(root)})
        self.query(b,query='正文')
        self.assertEqual(hashes(),before)
        with self.assertRaises(ValueError):self.index(root/'raw/_all.txt',output_dir=str(root/'new-bundles'))

    def test_oversized_archive_member_rejected_before_extraction(self):
        p=self.root/'book.docx'
        with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml','<document><p><t>甲</t></p></document>')
        with patch('novel_evidence.MAX_MEMBER',10):
            with self.assertRaises(ValueError):self.index(p)

    def test_crafted_manifest_cannot_read_outside_bundle(self):
        b=self.index(self.book()); mp=Path(b['bundle'])/'manifest.json'
        other=self.book('outside.txt','不允许读取。')
        m=json.loads(mp.read_text(encoding='utf-8')); m['sources'][0]['text_snapshot']=str(other)
        data=json.dumps(m).encode('utf-8'); mp.write_bytes(data)
        (mp.parent/'manifest.sha256').write_text(hashlib.sha256(data).hexdigest(),encoding='ascii')
        r=self.query(b,query='不允许读取')
        self.assertEqual(r['status'],'tampered')
        self.assertEqual(r['results'],[])


if __name__=='__main__':unittest.main()
