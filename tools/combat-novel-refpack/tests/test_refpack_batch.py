"""Bounded resumable reading and cross-chapter synthesis, not model claims."""
import json
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts' if (PROJECT / 'scripts').is_dir() else PROJECT))
SCRIPT = PROJECT/'scripts/novel_refpack.py' if (PROJECT/'scripts/novel_refpack.py').exists() else PROJECT/'refpack.py'
from combat_refpack import core


class RefpackBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        source = root/'book.txt'
        source.write_text('第一章 初期\n姜炎奴获得抵抗，但尚不能恢复。\n第二章 成长\n炎奴恢复成功，发动需要接触。\n第三章 末期\n炎奴保留恢复，不再需要接触。\n', encoding='utf-8')
        self.bundle = root/'bundle'
        core.prepare(source, self.bundle, '明确合成的测试小说', 'v1')
        self.packets = core.tasks(self.bundle)['tasks']

    def review(self, packet, subject='炎奴', state='末期', polarity='positive'):
        start = packet['start'] + packet['text'].index('\n')+1
        end = packet['end']-1
        return {'schema_version':1,
            **{k:packet[k] for k in ('task_id','source_sha256','text_sha256','prompt_sha256','task_sha256')},
            'reviewer':{'name':'test reader','kind':'current_agent'}, 'status':'complete',
            'read_spans':[{'start':packet['start'],'end':packet['end']}],
            'evidence':[{'id':'e','start':start,'end':end,'quote':packet['text'][start-packet['start']:end-packet['start']], 'kind':'feat'}],
            'observations':[{'id':'o','kind':'feat','subject':subject,'attribute':'abilities','state':state,
                'claim':'实际成功或失败必须回原文。','evidence_ids':['e'],'polarity':polarity}]}

    def write(self, name, data):
        p=self.bundle/name;p.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');return p

    def test_next_batch_is_bounded_backwards_and_does_not_mark_read(self):
        n = core.next_batch(self.bundle, limit=2, max_chars=60)
        self.assertEqual(n['tasks'][0]['chapter_ordinal'],3)
        self.assertLessEqual(len(n['tasks']),2)
        self.assertLessEqual(sum(len(t['text']) for t in n['tasks']),60)
        self.assertFalse((self.bundle/'reviews/index.json').exists())
        self.assertEqual(n['semantic_read_verified'],False)

    def test_resume_carries_prior_evidence_and_batch_merges_read_spans(self):
        p=self.packets[0];review=self.review(p)
        start=review['evidence'][0]['start']
        review.update(status='partial',read_spans=[{'start':start,'end':p['end']}])
        core.accept(self.bundle,self.write('partial.json',review))
        pending=core.next_batch(self.bundle,limit=1)['tasks'][0]
        self.assertEqual(pending['previous_review']['evidence'],review['evidence'])
        self.assertEqual(pending['remaining_spans'],[{'start':p['start'],'end':start}])
        completion={**review,'status':'complete','read_spans':[{'start':p['start'],'end':start}], 'evidence':[],'observations':[]}
        core.accept_batch(self.bundle,self.write('batch.json',[completion]))
        self.assertNotEqual(core.next_batch(self.bundle,limit=1)['tasks'][0]['task_id'],p['task_id'])
        accepted=core.load_reviews(*self._review_args())
        self.assertEqual(accepted[0]['evidence'],review['evidence'])

    def _review_args(self):
        root,manifest,text,chapters=core.load_bundle(self.bundle)
        return root,core.load_tasks(root,manifest,text,chapters),text

    def test_invalid_batch_writes_no_accepted_entries(self):
        good=self.review(self.packets[0]);bad=self.review(self.packets[1]);bad['evidence'][0]['quote']='伪造引文'
        with self.assertRaises(ValueError):core.accept_batch(self.bundle,self.write('invalid.json',[good,bad]))
        self.assertFalse((self.bundle/'reviews/index.json').exists())

    def test_synthesis_merges_only_explicit_aliases_and_keeps_state_gaps(self):
        reviews=[self.review(self.packets[0]),self.review(self.packets[1],state='成长期'),
                 self.review(self.packets[2],subject='姜炎奴',state='初期',polarity='negative')]
        core.accept_batch(self.bundle,self.write('all.json',reviews))
        s=core.synthesize(self.bundle,'炎奴',aliases=['姜炎奴'],target_state='末期')
        self.assertEqual(set(s['source_names']),{'炎奴','姜炎奴'})
        self.assertEqual(len(s['observations']),3)
        self.assertEqual([o['state'] for o in s['observations']],['末期','成长期','初期'])
        self.assertTrue(any(t['kind']=='state_transfer' for t in s['research_tasks']))
        self.assertTrue(any(t['kind']=='cross_chapter_comparison' for t in s['research_tasks']))
        self.assertFalse(s['semantic_complete'])
        self.assertEqual(s['reading_coverage']['status'],'complete')
        self.assertEqual(len(core.synthesize(self.bundle,'炎奴')['observations']),2)

    def test_cli_batch_output_is_complete_on_disk_and_short_in_stdout(self):
        script=SCRIPT
        destination=self.bundle.parent/'batch-output.json'
        result=subprocess.run([sys.executable,str(script),'next','--bundle',str(self.bundle),
                               '--limit','1','--output',str(destination)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('tasks',json.loads(result.stdout))
        self.assertEqual(len(json.loads(destination.read_text(encoding='utf-8'))['tasks']),1)

    def test_cli_output_cannot_overwrite_immutable_source(self):
        script=SCRIPT
        original=self.bundle/'text/full.txt';before=original.read_bytes()
        result=subprocess.run([sys.executable,str(script),'next','--bundle',str(self.bundle),
                               '--output',str(original)],capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(original.read_bytes(),before)


if __name__ == '__main__': unittest.main()
