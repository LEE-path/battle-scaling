"""Audit contracts, physical identities, source uncertainty and transfer counterexamples.

Synthetic fixtures test software contracts; they are not character evidence.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from derivation_audit import run


def physical_packet():
    return {
        'operation': 'physical', 'id': 'mechanical-benchmark',
        'sources': [{'id': 'video', 'title': 'Synthetic measurement fixture',
                     'origin': 'primary', 'access': 'verified',
                     'locator': {'start_pts': 1, 'end_pts': 2}}],
        'observations': [{'id': 'frame', 'source_ids': ['video'],
                          'locator': {'pts': 1, 'bbox': [0, 0, 10, 10]},
                          'visible_fact': 'Synthetic translation with known scale'}],
        'calculation': {'model': 'kinetic', 'inputs': {'mass': 2, 'speed': 3},
                        'intervals': {'mass': [1, 3], 'speed': [2, 4]}},
        'parameter_bindings': {
            'mass': {'source_ids': ['video'], 'basis': 'documented', 'reason': 'fixture prior'},
            'speed': {'source_ids': ['video'], 'observation_ids': ['frame'],
                      'basis': 'measured', 'reason': 'known calibrated displacement over PTS'}},
        'model_conditions': [{'name': 'physical_translation', 'status': True,
                              'source_ids': ['video'], 'reason': 'test premise'}],
        'target_anchor': {'id': 'energy', 'subject': 'A', 'version': 'fixture',
                          'state': 'test', 'attribute': 'raw_energy'},
    }


def chain_packet():
    return {'operation': 'chain', 'mode': 'highest', 'case': {
        'schema_version': 1, 'case_id': 'synthetic-transfer',
        'characters': [{'id': 'A', 'name': 'A', 'version': 'test', 'state': 'full'},
                       {'id': 'B', 'name': 'B', 'version': 'test', 'state': 'full'}],
        'sources': [{'id': 's', 'title': 'test', 'origin': 'primary',
                     'access': 'verified', 'locator': 'test premise'}],
        'anchors': [{'id': 'a', 'subject': 'A', 'attribute': 'AP',
                     'kind': 'credible_feat', 'quantity': {'value': 9, 'unit': 'J'},
                     'evidence_ids': ['s']}],
        'edges': [{'id': 't', 'from': {'subject': 'A', 'attribute': 'AP'},
                   'to': {'subject': 'B', 'attribute': 'durability'}, 'relation': 'tanked',
                   'conditions': {'actual_scale': True, 'effective_hit': True, 'body_only': True},
                   'evidence_ids': ['s']}]},
        'hop_audits': [{'edge_id': 't', 'mechanism': 'direct effective physical hit',
                        'scope': 'the stated attack', 'conditions': [
                            {'name': 'state_compatible', 'status': True, 'source_ids': ['s']},
                            {'name': 'scope_compatible', 'status': True, 'source_ids': ['s']}]}]}


class DerivationTests(unittest.TestCase):
    def test_real_calculator_and_interval_preserved(self):
        result = run(physical_packet())
        self.assertEqual(result['calculation']['result']['value'], 9)
        self.assertEqual(result['calculation']['sensitivity']['sampled_min'], 2)
        self.assertEqual(result['calculation']['sensitivity']['sampled_max'], 24)
        self.assertEqual(result['anchor_candidate']['quantity']['best'], 9)
        self.assertEqual(result['anchor_candidate']['attribute'], 'raw_energy')
        self.assertNotIn('tier', result['anchor_candidate'])

    def test_community_estimate_remains_conditional_and_generates_primary_task(self):
        request = physical_packet()
        request['sources'][0].update(origin='community', access='indexed')
        result = run(request)
        self.assertEqual(result['status'], 'conditional')
        self.assertIsNotNone(result['anchor_candidate'])
        self.assertTrue(any(t['kind'] == 'verify_source' for t in result['research_tasks']))

    def test_unreadable_sources_cannot_support_importable_anchor(self):
        for access in ('blocked', 'not_found', 'downloaded', 'unread', 'unknown'):
            request = physical_packet()
            request['sources'][0]['access'] = access
            result = run(request)
            self.assertEqual(result['calculation']['result']['value'], 9)
            self.assertIsNone(result['anchor_candidate'], access)

    def test_host_browser_readable_source_keeps_conditional_anchor(self):
        request = physical_packet()
        request['sources'][0]['access'] = 'verified_via_host_browser'
        self.assertIsNotNone(run(request)['anchor_candidate'])

    def test_unreadable_hop_context_cannot_inherit_true(self):
        request = chain_packet()
        request['case']['sources'].append({'id':'unread','title':'unread', 'origin':'primary',
                                           'access':'downloaded','locator':'page'})
        request['hop_audits'][0]['conditions'][0]['source_ids'] = ['unread']
        result = run(request)
        self.assertEqual(result['effective_case']['edges'], [])

    def test_high_unread_source_keeps_raw_analysis_but_no_admitted_mapping(self):
        request = json.loads((ROOT / 'assets/cases/high-godbox-stage4.json').read_text(encoding='utf-8'))
        result = run({'operation':'high','high_request':request})
        self.assertTrue(result['high_analysis']['mappings'])
        self.assertEqual(result['admitted_mappings'], [])

    def test_unknown_parameter_binding_still_computes_but_cannot_look_verified(self):
        request = physical_packet()
        del request['parameter_bindings']['mass']
        result = run(request)
        self.assertEqual(result['status'], 'conditional')
        self.assertEqual(result['calculation']['result']['value'], 9)
        self.assertTrue(any(t['kind'] == 'parameter_evidence' for t in result['research_tasks']))

    def test_known_false_model_condition_blocks_anchor_even_highest(self):
        request = physical_packet()
        request['mode'] = 'highest'
        request['model_conditions'][0]['status'] = False
        result = run(request)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['anchor_candidate'])

    def test_raw_energy_does_not_automatically_become_attack_potency(self):
        request = physical_packet()
        request['target_anchor']['attribute'] = 'AP'
        result = run(request)
        self.assertIsNone(result['anchor_candidate'])
        self.assertTrue(any(t['kind'] == 'attribute_transfer' for t in result['research_tasks']))
        request['transfer'] = {'status': True, 'mechanism': 'measured energy deposited by A',
                               'source_ids': ['video'], 'reason': 'synthetic impact premise'}
        self.assertEqual(run(request)['anchor_candidate']['attribute'], 'AP')

    def test_force_has_no_energy_tier_and_unknown_source_rejected(self):
        request = physical_packet()
        request['calculation'] = {'model': 'torque', 'inputs': {'force': 100, 'lever_arm': .5}}
        request['parameter_bindings'] = {}
        request['target_anchor']['attribute'] = 'raw_torque'
        result = run(request)
        self.assertEqual(result['calculation']['result']['unit'], 'N m')
        self.assertNotIn('tier', result)
        request = physical_packet()
        request['parameter_bindings']['mass']['source_ids'] = ['nonexistent']
        self.assertEqual(run(request)['status'], 'invalid')

    def test_quantity_type_cannot_be_renamed_to_energy_or_attack(self):
        request = physical_packet()
        request['calculation'] = {'model': 'torque', 'inputs': {'force': 100, 'lever_arm': .5}}
        request['parameter_bindings'] = {}
        self.assertIsNone(run(request)['anchor_candidate'])
        request['target_anchor']['attribute'] = 'AP'
        request['transfer'] = {'status': True, 'mechanism': 'caller claims torque is energy',
                               'source_ids': ['video']}
        self.assertIsNone(run(request)['anchor_candidate'])

    def test_nested_fracture_force_selector_preserves_correct_units_and_sensitivity(self):
        request = physical_packet()
        request['calculation'] = {'model': 'fracture_I', 'inputs': {
            'toughness': 1e6, 'crack_length': .01, 'geometry_factor': 1,
            'young_modulus': 10e9, 'poisson_ratio': .3, 'area': .01},
            'applicability': {'linear_elastic': True, 'small_scale_yielding': True,
                             'isotropic_approximation': True, 'plane_condition': 'plane_stress'},
            'intervals': {'area': [.005, .02]}}
        request['parameter_bindings'] = {}
        request['result_path'] = ['nominal_force']
        request['target_anchor']['attribute'] = 'raw_force'
        result = run(request)
        self.assertEqual(result['selected_quantity']['unit'], 'N')
        self.assertAlmostEqual(result['anchor_candidate']['quantity']['min'],
                               result['anchor_candidate']['quantity']['best'] / 2)
        self.assertAlmostEqual(result['anchor_candidate']['quantity']['max'],
                               result['anchor_candidate']['quantity']['best'] * 2)
        request['target_anchor']['attribute'] = 'AP'
        request['transfer'] = {'status': True, 'mechanism': 'caller claims force is energy',
                               'source_ids': ['video']}
        self.assertIsNone(run(request)['anchor_candidate'])

    def test_false_new_hop_condition_prevents_propagation(self):
        request = chain_packet()
        request['hop_audits'][0]['conditions'][0]['status'] = False
        result = run(request)
        conclusions = result['chain_analysis']['modes']['highest']['conclusions']
        self.assertFalse(any(c['subject'] == 'B' for c in conclusions))
        self.assertEqual(result['hop_ledger'][0]['status'], 'blocked')

    def test_unknown_hop_bridge_is_conditional_without_invented_false(self):
        request = chain_packet()
        request['hop_audits'][0]['conditions'][0]['status'] = None
        result = run(request)
        self.assertEqual(result['hop_ledger'][0]['status'], 'conditional')
        self.assertTrue(result['research_tasks'])
        conclusions = result['chain_analysis']['modes']['highest']['conclusions']
        self.assertTrue(any(c['subject'] == 'B' and c['status'] == 'conditional' for c in conclusions))

    def test_confirmed_counterexample_is_not_ignored_in_highest(self):
        request = chain_packet()
        request['hop_audits'][0]['counterexamples'] = [
            {'status': 'confirmed', 'source_ids': ['s'], 'reason': 'body shield did all the work'}]
        result = run(request)
        self.assertEqual(result['hop_ledger'][0]['status'], 'blocked')

    def test_hop_cannot_silently_change_endpoint_identity(self):
        request = chain_packet()
        request['hop_audits'][0]['from'] = {'subject': 'another-character'}
        self.assertEqual(run(request)['status'], 'invalid')

    def test_rooted_dependency_cycle_does_not_request_another_anchor(self):
        request = chain_packet()
        request['case']['edges'].append({'id': 'back',
            'from': {'subject': 'B', 'attribute': 'durability'},
            'to': {'subject': 'A', 'attribute': 'AP'}, 'relation': 'explicit',
            'conditions': {'explicit_relation': True}, 'evidence_ids': ['s']})
        result = run(request)
        self.assertTrue(result['cycles'])
        self.assertFalse(any(t['kind'] == 'independent_anchor' for t in result['research_tasks']))
        conclusions = result['chain_analysis']['modes']['highest']['conclusions']
        self.assertTrue(any(c['subject'] == 'A' and c['quantity']['best'] == 9 for c in conclusions))

    def test_existing_godbox_case_stays_qualified_and_grants_no_character_ap(self):
        request = json.loads((ROOT / 'assets/cases/high-godbox-stage4.json').read_text(encoding='utf-8'))
        result = run({'operation': 'high', 'high_request': request})
        self.assertNotEqual(result['status'], 'invalid')
        self.assertEqual(result['high_analysis']['result']['combat_properties'], {})
        self.assertEqual(result['high_analysis']['result']['cardinal'], None)
        self.assertTrue(any(t['kind'] == 'verify_source' for t in result['research_tasks']))

    def test_typed_invalid_and_travel_to_attack_not_admitted(self):
        req = {'kind': 'cardinal', 'expression': 'aleph0', 'axioms': ['ZFC', 'not_AC']}
        self.assertEqual(run({'operation': 'high', 'high_request': req})['status'], 'invalid')
        req = {'kind': 'native', 'nodes': [{'id': 'u', 'operation': 'base',
                'source': {'url': 'https://example.test', 'locator': 'test'}}],
               'character_relations': [{'character': 'A', 'node': 'u', 'relation': 'travels',
                   'properties': ['attack'], 'source': {'url': 'https://example.test', 'locator': 'test'}}]}
        result = run({'operation': 'high', 'high_request': req})
        self.assertNotIn('attack', result['high_analysis']['result']['combat_properties'])
        self.assertTrue(any(t['kind'] == 'character_structure_bridge' for t in result['research_tasks']))

    def test_refuted_high_bridge_cannot_be_admitted(self):
        request = json.loads((ROOT / 'assets/cases/high-godbox-stage4.json').read_text(encoding='utf-8'))
        result = run({'operation': 'high', 'high_request': request,
                      'proof_bindings': [{'node_id': 'stage4', 'contradicted': True}]})
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['admitted_mappings'], [])

    def test_boolean_string_is_not_accepted_as_evidence(self):
        request = physical_packet()
        request['model_conditions'][0]['status'] = 'true'
        self.assertEqual(run(request)['status'], 'invalid')

    def test_signed_work_is_kept_but_not_imported_as_nonnegative_energy_anchor(self):
        request = physical_packet()
        request['calculation'] = {'model': 'work', 'inputs': {'force': 100, 'displacement': 2, 'angle': 3.141592653589793}}
        request['parameter_bindings'] = {}
        request['target_anchor']['attribute'] = 'raw_work'
        result = run(request)
        self.assertEqual(result['selected_quantity']['value'], -200)
        self.assertIsNone(result['anchor_candidate'])

    def test_missing_candidate_id_is_stable_and_generated(self):
        request = physical_packet()
        del request['target_anchor']['id']
        first = run(request)['anchor_candidate']
        second = run(request)['anchor_candidate']
        self.assertTrue(first['id'])
        self.assertEqual(first['id'], second['id'])

    def test_bundle_is_non_mutating(self):
        request = {'operation': 'bundle', 'physical': physical_packet(), 'chain': chain_packet()}
        before = copy.deepcopy(request)
        result = run(request)
        self.assertEqual(request, before)
        self.assertIn('physical', result['results'])
        self.assertIn('chain', result['results'])


if __name__ == '__main__':
    unittest.main()
