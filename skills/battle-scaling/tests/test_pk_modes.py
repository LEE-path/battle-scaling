import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pk_modes import review_estimate, validate_estimate, select_presentation


class PKModesTests(unittest.TestCase):
    def setUp(self):
        self.sources={'s1':{'id':'s1','access':'provided','origin':'synthetic','locator':'rules'}}
        self.estimate={'method':'reasoned_estimate','basis':'按限定配置的命中和失能路线估计',
                       'evidence_ids':['s1'],'assumptions':['A能在B启动前形成有效攻击'],
                       'outcomes':[{'outcome':'A','min':0.6,'best':0.7,'max':0.8},
                                   {'outcome':'B','min':0.2,'best':0.3,'max':0.4}]}

    def test_overview_is_default_even_when_process_data_is_present(self):
        self.assertEqual(select_presentation({'mode_processes':{'normal':{'steps':[]}}}),'overview')
        self.assertEqual(select_presentation({'presentation':'process'}),'process')
        self.assertEqual(select_presentation({'presentation':'process'},'overview'),'overview')

    def test_evidence_mode_is_not_presentation(self):
        with self.assertRaises(ValueError):select_presentation({'presentation':'highest'})

    def test_typed_estimate_retains_range_and_truth_status(self):
        self.assertEqual(validate_estimate(self.estimate),[])
        reviewed=review_estimate(self.estimate,self.sources)
        self.assertEqual(reviewed['status'],'reasoned_estimate')
        self.assertFalse(reviewed['empirically_calibrated'])
        self.assertEqual(reviewed['outcomes'][0]['best'],0.7)

    def test_draw_and_mutual_defeat_are_explicit_outcomes(self):
        estimate=copy.deepcopy(self.estimate)
        estimate['outcomes']=[{'outcome':'A','min':0.1,'best':0.3,'max':0.5},
                              {'outcome':'B','min':0.1,'best':0.3,'max':0.5},
                              {'outcome':'mutual_defeat','min':0.2,'best':0.4,'max':0.8}]
        self.assertEqual(validate_estimate(estimate),[])
        self.assertEqual(review_estimate(estimate,self.sources)['outcomes'][2]['outcome'],'mutual_defeat')

    def test_invalid_probability_packets_are_rejected(self):
        for value in [float('nan'),float('inf'),True,-0.1,1.1]:
            estimate=copy.deepcopy(self.estimate);estimate['outcomes'][0]['best']=value
            self.assertTrue(validate_estimate(estimate))
        estimate=copy.deepcopy(self.estimate);estimate['outcomes'][1]['best']=0.2
        self.assertTrue(validate_estimate(estimate))
        estimate=copy.deepcopy(self.estimate);estimate['method']='empirically_proven'
        self.assertTrue(validate_estimate(estimate))
        estimate=copy.deepcopy(self.estimate);estimate['basis']=''
        self.assertTrue(validate_estimate(estimate))

    def test_unread_evidence_does_not_publish_numeric_estimate(self):
        reviewed=review_estimate(self.estimate,{'s1':{'access':'blocked'}})
        self.assertEqual(reviewed['status'],'undetermined')
        self.assertEqual(reviewed['outcomes'],[])
        self.assertIn('s1',reviewed['unusable_evidence_ids'])

    def test_source_index_is_usable_but_is_not_primary_verification(self):
        reviewed=review_estimate(self.estimate,{'s1':{'access':'indexed','origin':'community'}})
        self.assertEqual(reviewed['status'],'reasoned_estimate')
        self.assertFalse(reviewed['original_source_verified'])

    def test_swapping_output_order_does_not_change_outcome_values(self):
        estimate=copy.deepcopy(self.estimate);estimate['outcomes'].reverse()
        a=review_estimate(self.estimate,self.sources)
        b=review_estimate(estimate,self.sources)
        self.assertEqual({x['outcome']:x['best'] for x in a['outcomes']},{x['outcome']:x['best'] for x in b['outcomes']})

if __name__=='__main__':unittest.main()
