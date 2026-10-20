import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from li_metrics import token_metrics,manual_dewater,assess_li


def fixture_rule():
    return {'id':'synthetic-li-fixture','ambiguous_A_boundaries':[4000,10000],
            'small_A_boundary':4000,'large_A_boundary':10000,'large_A_floor':'论天下','large_A_floor_score':4000,
            'mid_negative_label':'下调一线，具体程度待判','mathematics_label':'三线','philosophy_label':'二线',
            'score_thresholds':[{'minimum':500,'label':'一线'},{'minimum':1000,'label':'强一线'},{'minimum':4000,'label':'论天下'}],
            'manual_thresholds':[{'minimum':500,'label':'一线'},{'minimum':1000,'label':'强一线'}],
            'sources':[{'kind':'synthetic_fixture'}]}


class LiMetricTests(unittest.TestCase):
    def test_types_tokens_and_repetition_penalty(self):
        result=token_metrics(['甲','乙','甲','甲','乙'])
        self.assertEqual((result['A_types'],result['B_tokens'],result['E_2A_minus_B']),(2,5,-1))

    def test_characters_are_not_implicitly_words(self):
        with self.assertRaises(ValueError):token_metrics('中文不能自动当成一串词')

    def test_manual_review_requires_complete_source_coverage(self):
        with self.assertRaises(ValueError):manual_dewater('甲乙丙',[{'start':0,'end':2,'decision':'keep','reason':'保留'}])
        with self.assertRaises(ValueError):manual_dewater('甲乙',[{'start':1,'end':2,'decision':'keep','reason':'保留'}])

    def test_manual_global_dedup_and_annotation_preserved(self):
        source='甲规则。相同意思。乙规则。'
        segments=[{'start':0,'end':4,'decision':'keep','canonical':'甲规则','dedupe_key':'same','reason':'具体新增规则'},
                  {'start':4,'end':9,'decision':'keep','canonical':'同义复述','dedupe_key':'same','reason':'归入相同语义类'},
                  {'start':9,'end':13,'decision':'keep','canonical':'乙规则','dedupe_key':'other','reason':'新的独立机制'}]
        result=manual_dewater(source,segments)
        self.assertEqual(result['effective_characters'],6)
        self.assertTrue(result['annotations'][1]['duplicate'])

    def test_missing_scope_evidence_prevents_wordcount_only_tier(self):
        result=assess_li({'tokens':[str(i) for i in range(600)]},fixture_rule())
        self.assertIsNone(result['label'])
        self.assertEqual(result['status'],'needs_scope_evidence')

    def test_undefined_A_boundary_remains_explicit(self):
        result=assess_li({'tokens':[str(i) for i in range(4000)],
                         'scope_facts':{'transcends_existing_mathematics':True,'evidence_ids':['s']}},fixture_rule())
        self.assertTrue(result['machine']['boundary_ambiguity'])
        self.assertIsNone(result['machine']['label'])

    def test_manual_result_has_priority_over_machine(self):
        source='字'*500
        request={'tokens':['重复']*3,'scope_facts':{'transcends_existing_mathematics':True,'evidence_ids':['s']},
                 'source_text':source,'manual_segments':[{'start':0,'end':500,'decision':'keep','reason':'合成计数夹具'}]}
        result=assess_li(request,fixture_rule())
        self.assertEqual(result['priority'],'manual_over_machine')
        self.assertEqual(result['label'],'一线')


if __name__=='__main__':unittest.main()
