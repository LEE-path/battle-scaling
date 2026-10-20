import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research

def target():
    return {'entity_id':'work:hero:end','name':'甲','work_id':'work-v1','work':'示例书',
            'continuity':'novel','period':'ending','state':'final','medium':'novel'}

class DiscoveryPlanTests(unittest.TestCase):
    def test_known_equipment_and_opponent_create_distinct_scoped_routes(self):
        value=target();value['related_entities']=[
            {'entity_id':'work:blade','name':'乙剑','relation':'equipment'},
            {'entity_id':'work:rival','name':'丙','relation':'opponent','work_id':'other-unconfirmed'}]
        result=research.run({'op':'plan','target':value})
        self.assertEqual(result['status'],'ok')
        routes=result['discovery_routes']['nodes']
        self.assertEqual([node['entity_id'] for node in routes],['work:hero:end','work:blade','work:rival'])
        self.assertIsNone(routes[1]['declared_scope']['version'])
        self.assertEqual(routes[2]['declared_scope']['work_id'],'other-unconfirmed')
        self.assertTrue(all(node['search_executed'] is False for node in routes))
        self.assertTrue(any(task['polarity']=='counter' for task in routes[2]['queries']))
        self.assertTrue(routes[1]['requires_attribution_bridge'])

    def test_no_known_opponents_does_not_invent_five(self):
        result=research.run({'op':'plan','target':target()})
        self.assertEqual(len(result['discovery_routes']['nodes']),1)
        self.assertFalse(result['discovery_routes']['node_identity_verified'])
        self.assertFalse(result['search_executed'])

    def test_duplicate_or_untyped_relations_are_rejected(self):
        for extra in ([{'entity_id':'work:hero:end','name':'重复','relation':'opponent'}],
                      [{'entity_id':'x','name':'未知','relation':'automatically_superior'}]):
            value=target();value['related_entities']=extra
            self.assertEqual(research.run({'op':'plan','target':value})['status'],'error')

    def test_hax_discovery_is_a_question_matrix_without_adjudicated_priority(self):
        result=research.run({'op':'plan','target':target()})
        matrix=result['discovery_routes']['interaction_questions']
        self.assertIn('own_effect_limit',matrix)
        self.assertIn('world_strongest_achieved',matrix)
        self.assertIn('resistance_and_counterexamples',matrix)
        self.assertEqual(result['discovery_routes']['admission'],'discovery_only')

if __name__=='__main__':unittest.main()
