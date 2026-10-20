import contextlib,hashlib,io,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from battle import main

class NovelCliTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.refpack=self.root/'book'
        (self.refpack/'raw').mkdir(parents=True);(self.refpack/'canon').mkdir()
        (self.refpack/'raw/_all.txt').write_text('第一章 开始\n甲不能破门。\n第二章 转折\n甲击碎护具。\n第三章 终局\n甲的终局能力失效。\n',encoding='utf-8')
        (self.refpack/'canon/00_正典边界.md').write_text('项目只保留前两章，另写终局。',encoding='utf-8')

    def cli(self,value,expected=0):
        request=self.root/'request.json';output=self.root/'result.json'
        request.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['novel','--input',str(request),'--output',str(output)]),expected)
        return json.loads(output.read_text(encoding='utf-8'))

    def indexed(self):
        return self.cli({'op':'index','source':str(self.refpack),'output_dir':str(self.root/'bundles'),
                         'work_id':'fixture-work','edition_id':'raw-edition'})

    def test_cli_indexes_original_candidate_without_applying_project_canon(self):
        before={p.relative_to(self.refpack).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.refpack.rglob('*') if p.is_file()}
        indexed=self.indexed()
        result=self.cli({'op':'search','bundle':indexed['bundle'],'query':'终局','context_lines':0,'limit':1})
        self.assertEqual(result['status'],'ok')
        self.assertIn('能力失效',result['results'][0]['exact_text'])
        self.assertIn('第三章',result['results'][0]['chapter']['title'])
        self.assertFalse(result['original_verified'])
        self.assertFalse(result['coverage']['whole_book_read'])
        after={p.relative_to(self.refpack).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.refpack.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_cli_reads_requested_source_window_and_checks_snapshot(self):
        indexed=self.indexed();source=indexed['sources'][0]
        result=self.cli({'op':'read','bundle':indexed['bundle'],'source_id':source['id'],'line_start':3,'line_end':4})
        original=(self.refpack/'raw/_all.txt').read_bytes().decode('utf-8')
        self.assertEqual(result['window']['exact_text'],''.join(original.splitlines(keepends=True)[2:4]))
        self.assertEqual(self.cli({'op':'verify','bundle':indexed['bundle']})['snapshot_integrity'],True)

    def test_cli_tampering_withholds_the_passage_and_returns_failure(self):
        indexed=self.indexed();source=indexed['sources'][0]
        (Path(indexed['bundle'])/source['text_snapshot']).write_text('伪造终局。',encoding='utf-8')
        result=self.cli({'op':'search','bundle':indexed['bundle'],'query':'终局'},expected=2)
        self.assertEqual(result['status'],'tampered')
        self.assertEqual(result['results'],[])

if __name__=='__main__':unittest.main()
