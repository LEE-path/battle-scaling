import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import high_tier as ht

SOURCE = {'url': 'https://example.org/work', 'locator': 'chapter 4, complete structure'}


class NativePremiseTests(unittest.TestCase):
    def chain(self):
        return {'kind': 'native', 'nodes': [
            {'id': 'base', 'operation': 'base', 'description': 'unverified base scale'},
            {'id': 'outer', 'operation': 'contains', 'depends_on': ['base'], 'source': SOURCE},
        ], 'character_relations': [
            {'character': 'C', 'node': 'outer', 'relation': 'destroys', 'source': SOURCE},
        ]}

    def support(self, result, node):
        return result['result']['node_support'][node]

    def test_unsourced_base_propagates_to_sourced_contains_and_character_scope(self):
        r = ht.analyze(self.chain())
        steps = {s['node']: s for s in r['steps'] if s['rule'].startswith('native_')}
        self.assertFalse(steps['base']['admitted'])
        self.assertFalse(steps['outer']['admitted'])
        p = r['result']['combat_properties']['destructive_capacity'][0]
        self.assertEqual(p['status'], 'candidate_unsourced')
        self.assertEqual(p['event_status'], 'source_conditioned')
        self.assertTrue(any(g['node'] == 'base' and g['code'] == 'unsourced_node' for g in p['unresolved_premises']))

    def test_source_repair_releases_only_dependent_scope(self):
        req = self.chain()
        req['nodes'][0]['source'] = SOURCE
        req['nodes'][0]['assumptions'] = ['base counts actual worlds']
        req['nodes'][1]['conditions'] = ['complete containment']
        r = ht.analyze(req)
        sup = self.support(r, 'outer')
        self.assertTrue(sup['admitted'])
        self.assertEqual(sup['unresolved_premises'], [])
        self.assertEqual(sup['established_premises'], ['base', 'outer'])
        self.assertIn('base counts actual worlds', str(sup['conditions']))
        self.assertIn('complete containment', str(sup['conditions']))
        self.assertEqual(r['result']['combat_properties']['destructive_capacity'][0]['status'], 'source_conditioned')

    def test_independent_complete_anchor_can_bypass_unrelated_parent(self):
        req = self.chain()
        req['nodes'][1]['independent_anchor'] = {
            'definition': 'The complete outer structure has an independently specified scale.',
            'scope': 'complete outer structure, independently of base', 'source': SOURCE,
        }
        r = ht.analyze(req)
        self.assertFalse(self.support(r, 'base')['admitted'])
        sup = self.support(r, 'outer')
        self.assertTrue(sup['admitted'])
        self.assertEqual(sup['active_dependencies'], [])
        self.assertEqual(sup['established_premises'], ['outer'])
        self.assertEqual(sup['unresolved_premises'], [])
        self.assertEqual(r['result']['combat_properties']['destructive_capacity'][0]['status'], 'source_conditioned')

    def test_existing_anchor_operation_supplies_independent_definition(self):
        req = self.chain()
        req['nodes'][1].update(operation='anchor', definition='independently defined whole', scope='complete outer object')
        r = ht.analyze(req)
        self.assertTrue(self.support(r, 'outer')['admitted'])
        self.assertEqual(self.support(r, 'outer')['active_dependencies'], [])

    def test_typed_mapping_obeys_dependencies_and_uses_anchor_source(self):
        req = self.chain()
        req['nodes'][1]['typed_object'] = {'kind': 'cardinal', 'expression': 'aleph1', 'interpretation': 'whole outer object'}
        old_rule = json.loads((ROOT / 'rulesets/high-zerozhi2025-old.json').read_text(encoding='utf-8'))
        handbook_rule = json.loads((ROOT / 'rulesets/high-wangba-handbook-2026-07-30.json').read_text(encoding='utf-8'))
        for rule in (old_rule, handbook_rule):
            with self.subTest(rule=rule['id']):
                self.assertEqual(ht.analyze(req, rule)['mappings'], [])
                independent = dict(req['nodes'][1], operation='anchor', definition='independently defined whole', scope='complete outer object')
                fixed = dict(req, nodes=[req['nodes'][0], independent])
                self.assertTrue(ht.analyze(fixed, rule)['mappings'])
                nested = dict(req['nodes'][1])
                nested.pop('source')
                nested['independent_anchor'] = {
                    'definition': 'independently defined whole', 'scope': 'complete outer object', 'source': SOURCE,
                }
                self.assertTrue(ht.analyze(dict(req, nodes=[req['nodes'][0], nested]), rule)['mappings'])

    def test_flag_or_incomplete_anchor_does_not_erase_dependency(self):
        for anchor in (True, {'source': SOURCE}, {'definition': 'complete', 'scope': 'complete'}):
            with self.subTest(anchor=anchor):
                req = self.chain()
                req['nodes'][1]['independent_anchor'] = anchor
                r = ht.analyze(req)
                self.assertFalse(self.support(r, 'outer')['admitted'])
                self.assertEqual(self.support(r, 'outer')['active_dependencies'], ['base'])

    def test_unknown_source_blocks_only_affected_branch(self):
        req = self.chain()
        req['nodes'].append({'id': 'good', 'operation': 'base', 'source': SOURCE})
        req['character_relations'].append({'character': 'D', 'node': 'good', 'relation': 'creates', 'source': SOURCE})
        r = ht.analyze(req)
        self.assertTrue(self.support(r, 'good')['admitted'])
        self.assertFalse(self.support(r, 'outer')['admitted'])
        self.assertEqual(r['result']['combat_properties']['creation_scope'][0]['status'], 'source_conditioned')

    def test_property_bridge_is_retained_as_conditional_without_laundering_scope(self):
        req = self.chain()
        req['character_relations'][0].update(properties=['attack'], mechanism='direct energy release', bridge='same energy acts on the stated structure')
        r = ht.analyze(req)
        p = r['result']['combat_properties']['attack'][0]
        self.assertEqual(p['status'], 'candidate_unsourced')
        self.assertEqual(p['event_status'], 'source_conditioned')
        self.assertTrue(p['unresolved_premises'])
        req['nodes'][0]['source'] = SOURCE
        p = ht.analyze(req)['result']['combat_properties']['attack'][0]
        self.assertEqual(p['status'], 'source_conditioned')
        self.assertEqual(p['unresolved_premises'], [])

    def test_unsourced_character_event_remains_unsourced_on_good_structure(self):
        req = self.chain()
        req['nodes'][0]['source'] = SOURCE
        req['character_relations'][0].pop('source')
        p = ht.analyze(req)['result']['combat_properties']['destructive_capacity'][0]
        self.assertEqual(p['status'], 'candidate_unsourced')
        self.assertEqual(p['event_status'], 'candidate_unsourced')
        self.assertTrue(any(g['code'] == 'unsourced_character_relation' for g in p['unresolved_premises']))


if __name__ == '__main__':
    unittest.main()
