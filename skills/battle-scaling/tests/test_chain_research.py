"""Dependency source work, not tests purporting to interpret fictional canon."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from research import chain_tasks, run
from derivation_audit import run as derive


def actor(name):
    return {'id': name, 'name': name, 'version': 'test', 'state': 'available'}


def edge(name, left, right, left_attribute='AP', right_attribute='AP'):
    return {'id': name, 'from': {'subject': left, 'attribute': left_attribute},
            'to': {'subject': right, 'attribute': right_attribute},
            'relation': 'same_tier', 'conditions': {'corroborated': True,
                'scope_compatible': True, 'attribute_coverage': True}, 'evidence_ids': ['s']}


def packet():
    return {'schema_version': 1, 'case_id': 'synthetic-research',
            'characters': [actor(x) for x in ('root', 'middle', 'target', 'unrelated')],
            'sources': [{'id': 's', 'title': 'Synthetic supplied premise',
                         'origin': 'official', 'access': 'read', 'locator': 'test'}],
            'anchors': [], 'edges': [edge('one', 'root', 'middle'), edge('two', 'middle', 'target')]}


def anchor(subject='root', attribute='AP', kind='statement'):
    return {'id': 'independent', 'subject': subject, 'attribute': attribute,
            'kind': kind, 'quantity': {'value': 100, 'unit': 'J'}, 'evidence_ids': ['s']}


def scoped_nodes(task):
    return {(c['id'], c['attribute']) for c in task['scope']}


class ChainResearchTests(unittest.TestCase):
    def test_unrooted_acyclic_chain_requests_origin_once(self):
        tasks = chain_tasks(packet(), ['target'])
        roots = [t for t in tasks if t['kind'] == 'independent_anchor']
        self.assertEqual(len(roots), 1)
        self.assertEqual(scoped_nodes(roots[0]), {('root', 'AP')})

    def test_diamond_shares_the_same_root_assignment(self):
        case = packet()
        case['characters'].append(actor('other-arm'))
        case['edges'] += [edge('three', 'root', 'other-arm'), edge('four', 'other-arm', 'target')]
        roots = [t for t in chain_tasks(case, ['target']) if t['kind'] == 'independent_anchor']
        self.assertEqual(len(roots), 1)

    def test_unrooted_cycle_one_source_assignment_and_no_fabricated_anchor(self):
        case = packet()
        case['edges'].append(edge('back', 'middle', 'root'))
        before = copy.deepcopy(case)
        roots = [t for t in chain_tasks(case, ['target']) if t['kind'] == 'independent_anchor']
        self.assertEqual(len(roots), 1)
        self.assertIn(('root', 'AP'), scoped_nodes(roots[0]))
        self.assertEqual(case, before)

    def test_readable_reliable_statement_root_is_reused_without_physical_calculation(self):
        case = packet()
        case['anchors'] = [anchor()]
        case['edges'].append(edge('back', 'middle', 'root'))
        self.assertFalse(any(t['kind'] == 'independent_anchor' for t in chain_tasks(case, ['target'])))

    def test_scope_ignores_unrelated_branch_and_known_false_route(self):
        case = packet()
        case['edges'].append(edge('other', 'unrelated', 'unrelated', 'hax', 'durability'))
        case['edges'][0]['conditions']['attribute_coverage'] = False
        roots = [t for t in chain_tasks(case, ['target']) if t['kind'] == 'independent_anchor']
        self.assertEqual([scoped_nodes(t) for t in roots], [{('middle', 'AP')}])

    def test_unreadable_anchor_does_not_suppress_source_work(self):
        case = packet()
        case['anchors'] = [anchor()]
        case['sources'][0]['access'] = 'downloaded'
        self.assertTrue(any(t['kind'] == 'independent_anchor' for t in chain_tasks(case, ['target'])))

    def test_object_scale_to_power_generates_two_step_source_work_not_truth(self):
        case = packet()
        case['anchors'] = [anchor('root', 'native_object_scale')]
        case['edges'] = [edge('association', 'root', 'target', 'native_object_scale', 'AP')]
        case['edges'][0].update(relation='explicit', conditions={'explicit_relation': True})
        before = copy.deepcopy(case)
        tasks = chain_tasks(case, ['target'])
        bridges = [t for t in tasks if t['kind'] == 'scaling_bridge']
        self.assertEqual(len(bridges), 1)
        self.assertEqual(scoped_nodes(bridges[0]), {('root', 'native_object_scale'), ('target', 'AP')})
        self.assertEqual(case, before)
        self.assertNotIn('main_tier', bridges[0])

    def test_existing_sourced_hop_context_avoids_duplicate_assignment(self):
        case = packet()
        case['anchors'] = [anchor()]
        case['edges'][0].update(relation='explicit', conditions={'explicit_relation': True})
        context = [{'edge_id': 'one', 'mechanism': 'Explicit comparable effective attack',
                    'scope': 'The stated capability only', 'conditions': [
                        {'name': k, 'status': True, 'source_ids': ['s']}
                        for k in ('state_compatible', 'scope_compatible')]}]
        self.assertEqual(chain_tasks(case, ['target'], hop_audits=context), [])
        context[0]['conditions'][0]['source_ids'] = ['unread-context']
        self.assertTrue(any(t['kind'] == 'scaling_bridge'
                            for t in chain_tasks(case, ['target'], hop_audits=context)))

    def test_research_plan_targets_dependencies_before_nine_dimension_navigation(self):
        case = packet()
        target = {'entity_id': 'target', 'name': 'target', 'work_id': 'test',
                  'continuity': 'test', 'period': 'end', 'state': 'available'}
        result = run({'op': 'plan', 'target': target, 'case': case})
        self.assertEqual(result['tasks'][0]['kind'], 'independent_anchor')
        self.assertEqual(len(result['dimensions']), 9)
        self.assertFalse(result['search_executed'])
        self.assertEqual(run({'op': 'plan', 'target': dict(target, entity_id='missing'),
                              'case': case})['status'], 'error')

    def test_added_root_clears_only_its_missing_origin_work(self):
        case = packet()
        before = chain_tasks(case, ['target'])
        case['anchors'].append(anchor())
        after = chain_tasks(case, ['target'])
        self.assertTrue(before)
        self.assertEqual(after, [])

    def test_derivation_directly_returns_missing_acyclic_origin_without_a_tier(self):
        result = derive({'operation': 'chain', 'mode': 'integrated', 'case': packet()})
        self.assertNotEqual(result['status'], 'invalid')
        self.assertTrue(any(t['kind'] == 'independent_anchor' for t in result['research_tasks']))
        self.assertEqual(result['chain_analysis']['modes']['integrated']['conclusions'], [])


if __name__ == '__main__':
    unittest.main()
