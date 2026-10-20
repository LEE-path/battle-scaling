"""Synthetic packets test explicit premise handling, never fictional truth."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from feat_audit import run


def claim(status=True, basis='observed', **extra):
    return {'status': status, 'basis': basis, 'reason': 'Host recorded the cited fact.',
            'source_ids': ['panel'], **extra}


def packet(*uses):
    return {
        'id': 'synthetic-hit', 'mode': 'normal',
        'sources': [{'id': 'panel', 'title': 'Synthetic panel', 'access': 'provided', 'origin': 'primary',
                     'locator': 'synthetic fixture, panel 1'}],
        'event': {'actor_id': 'actor-A', 'version': 'synthetic-v1',
                  'state': 'tired, ordinary form', 'locator': 'panel 1',
                  'description': 'A strikes a target; a visible chip detaches.',
                  'observed_output': claim()},
        'causal_chain': {'action': 'strike', 'transmission': 'contact',
                         'target_response': 'a chip detaches', 'attribution': claim()},
        'requested_uses': list(uses) or ['observed_output'],
    }


class FeatAuditTests(unittest.TestCase):
    def status(self, request, use='observed_output'):
        return run(request)['admissions'][use]['status']

    def test_direct_output_needs_no_material_or_full_effort(self):
        result = run(packet())
        self.assertEqual(result['admissions']['observed_output']['status'], 'supported_by_packet')
        self.assertEqual(set(result['admissions']), {'observed_output'})
        self.assertIn('does not', result['validation_scope'])

    def test_fatigue_does_not_erase_observed_output_or_invent_discount(self):
        request = packet()
        request['actor_state'] = {'fatigue': claim(), 'prime_condition': claim(False)}
        result = run(request)
        self.assertEqual(result['admissions']['observed_output']['status'], 'supported_by_packet')
        self.assertNotIn('multiplier', result)
        self.assertTrue(any(x['path'] == 'actor_state.fatigue' for x in result['ledger']))

    def test_no_killing_intent_does_not_mean_half_effort(self):
        request = packet('observed_output', 'full_effort')
        request['combat_intent'] = {'killing_intent': claim(False)}
        self.assertEqual(self.status(request), 'supported_by_packet')
        self.assertEqual(self.status(request, 'full_effort'), 'undetermined')
        self.assertNotIn('0.5', str(run(request)))

    def test_pre_damage_requires_incremental_attribution(self):
        request = packet()
        request['causal_chain']['confounders'] = [
            {'kind': 'pre_damage', 'description': 'The target was already fractured.',
             'accounted_for': claim(None)}]
        result = run(request)
        self.assertEqual(result['admissions']['observed_output']['status'], 'undetermined')
        self.assertTrue(result['research_tasks'])
        self.assertEqual(result['event']['observed_output']['status'], True)

    def test_whole_effect_known_not_attributable_is_blocked(self):
        request = packet()
        request['causal_chain']['attribution'] = claim(False)
        self.assertEqual(self.status(request), 'blocked')

    def test_explicitly_isolated_increment_can_survive_external_energy(self):
        request = packet()
        request['causal_chain'].update(
            incremental_effect_isolated=claim(),
            confounders=[{'kind': 'external_energy', 'description': 'External charge present.',
                          'accounted_for': claim()}])
        self.assertEqual(self.status(request), 'supported_by_packet')

    def test_character_boast_does_not_objectively_establish_full_effort(self):
        request = packet('full_effort')
        request['effort'] = {'actual_output': 'one strike',
                             'full_effort': claim(basis='character_statement')}
        self.assertEqual(self.status(request, 'full_effort'), 'conditional')

    def test_expression_and_failure_cannot_be_automatic_full_effort(self):
        request = packet('full_effort')
        request['effort'] = {'actual_output': 'grimacing after one failed attempt'}
        self.assertEqual(self.status(request, 'full_effort'), 'undetermined')

    def test_known_not_full_effort_stays_blocked_in_highest(self):
        request = packet('full_effort')
        request.update(mode='highest', effort={'full_effort': claim(False)})
        result = run(request)
        self.assertEqual(result['admissions']['full_effort']['status'], 'blocked')
        self.assertFalse(result['conditional_branches'])

    def test_unknown_highest_is_only_a_separate_conditional_branch(self):
        request = packet('full_effort')
        request['mode'] = 'highest'
        result = run(request)
        self.assertEqual(result['admissions']['full_effort']['status'], 'undetermined')
        self.assertEqual(result['conditional_branches'][0]['use'], 'full_effort')
        self.assertFalse(result['conditional_branches'][0]['admitted'])

    def test_reasoned_estimate_is_preserved_as_conditional(self):
        request = packet()
        request['causal_chain']['attribution'] = claim(
            basis='estimated', assumptions=['The visible chip came from this contact.'])
        result = run(request)
        self.assertEqual(result['admissions']['observed_output']['status'], 'conditional')
        self.assertIn('The visible chip came from this contact.',
                      result['admissions']['observed_output']['assumptions'])

    def test_explicit_unknown_assumption_can_be_conditionally_used(self):
        request = packet('full_effort')
        request['effort'] = {'full_effort': claim(
            None, basis='assumed', assumptions=['Assume no remaining output reserve.'])}
        self.assertEqual(self.status(request, 'full_effort'), 'conditional')

    def test_unreadable_sources_block_only_dependent_use(self):
        request = packet('observed_output', 'full_effort')
        request['sources'].append({'id': 'locked', 'access': 'blocked'})
        request['effort'] = {'full_effort': claim(source_ids=['locked'])}
        result = run(request)
        self.assertEqual(result['admissions']['observed_output']['status'], 'supported_by_packet')
        self.assertEqual(result['admissions']['full_effort']['status'], 'blocked')

    def test_unknown_source_id_is_input_error(self):
        request = packet()
        request['event']['observed_output']['source_ids'] = ['missing']
        with self.assertRaises(ValueError):
            run(request)

    def test_source_access_alone_does_not_supply_a_locator(self):
        request = packet()
        request['sources'] = [{'id': 'panel', 'access': 'provided'}]
        self.assertEqual(self.status(request), 'undetermined')

    def test_source_and_event_structured_locators_are_accepted(self):
        request = packet()
        request['sources'][0]['locator'] = {'chapter': 1, 'page': 0, 'panel': 2}
        request['event']['locator'] = {'chapter': 1, 'page': 0, 'panel': 2}
        self.assertEqual(self.status(request), 'supported_by_packet')

    def test_malformed_inference_reason_is_value_error(self):
        request = packet()
        request['causal_chain']['attribution'] = claim(
            basis='reasonable_inference', evidence_claim_ids=['inference'])
        request['evidence_claims'] = [{'id': 'inference', 'kind': 'reasonable_inference',
                                      'reason': ['wrong type'], 'source_ids': ['panel'],
                                      'premises': [claim()],
                                      'checks': {'alternatives_considered': claim()}}]
        with self.assertRaises(ValueError):
            run(request)

    def test_claim_status_is_not_truthy_string(self):
        request = packet()
        request['event']['observed_output']['status'] = 'true'
        with self.assertRaises(ValueError):
            run(request)

    def test_material_mismatch_blocks_model_but_not_direct_output(self):
        request = packet('observed_output', 'material_model')
        request['materials'] = [{'id': 'target', 'identity_candidates': ['stone'],
                                  'identification': claim(), 'geometry': claim(),
                                  'condition': {'description': 'layered, edge-supported',
                                                'accounted_for': claim()},
                                  'properties': claim(), 'property_match': claim(False)}]
        result = run(request)
        self.assertEqual(result['admissions']['material_model']['status'], 'blocked')
        self.assertEqual(result['admissions']['observed_output']['status'], 'supported_by_packet')

    def test_material_missing_does_not_become_zero(self):
        result = run(packet('material_model'))
        self.assertEqual(result['admissions']['material_model']['status'], 'undetermined')
        self.assertNotIn('energy', result)

    def author_packet(self):
        request = packet('full_effort')
        request['effort'] = {'full_effort': claim(
            basis='author_statement', evidence_claim_ids=['author-note'])}
        request['evidence_claims'] = [{
            'id': 'author-note', 'kind': 'author_statement', 'source_ids': ['panel'],
            'reason': 'A screenshot attributed to the creator.',
            'checks': {'identity_verified': claim(None), 'original_context': claim(),
                       'version_applicable': claim(), 'serious': claim(),
                       'consistent_with_original': claim()}}]
        return request

    def test_unverified_author_screenshot_does_not_gain_authority(self):
        result = run(self.author_packet())
        self.assertNotEqual(result['admissions']['full_effort']['status'], 'supported_by_packet')
        self.assertTrue(any(x['code'] == 'author_identity_unverified' for x in result['issues']))

    def test_assuming_author_identity_does_not_grant_conditional_authority(self):
        request = self.author_packet()
        request['evidence_claims'][0]['checks']['identity_verified'] = claim(
            None, basis='assumed', assumptions=['Suppose the screenshot is genuine.'])
        self.assertEqual(self.status(request, 'full_effort'), 'undetermined')

    def test_negative_context_facts_are_not_contradicted_requirements(self):
        request = packet()
        request['actor_state'] = {'fatigue': claim(False)}
        result = run(request)
        record = next(x for x in result['ledger'] if x['path'] == 'actor_state.fatigue')
        self.assertEqual(record['status'], False)
        self.assertEqual(record['review_status'], 'supported_by_packet')
        self.assertEqual(self.status(request), 'supported_by_packet')

    def test_malformed_boolean_claim_is_not_treated_as_missing(self):
        request = packet()
        request['event']['observed_output'] = False
        with self.assertRaises(ValueError):
            run(request)

    def test_percent_is_not_used_to_extrapolate_or_establish_full_effort(self):
        request = packet('full_effort')
        request['effort'] = {'percent': 50, 'actual_output_fraction': 0.5}
        result = run(request)
        self.assertEqual(result['admissions']['full_effort']['status'], 'undetermined')
        self.assertTrue(any(x['code'] == 'effort_fraction_not_consumed' for x in result['issues']))

    def test_author_statement_cannot_override_known_original_conflict(self):
        request = self.author_packet()
        request['mode'] = 'highest'
        request['evidence_claims'][0]['checks'].update(
            identity_verified=claim(), consistent_with_original=claim(False))
        self.assertEqual(self.status(request, 'full_effort'), 'blocked')

    def test_narrator_requires_scope_and_knowledge(self):
        request = packet('full_effort')
        request['effort'] = {'full_effort': claim(
            basis='narrator_statement', evidence_claim_ids=['narrator'])}
        request['evidence_claims'] = [{'id': 'narrator', 'kind': 'narrator_statement',
                                      'source_ids': ['panel'], 'checks': {}}]
        self.assertEqual(self.status(request, 'full_effort'), 'undetermined')

    def test_reasonable_inference_requires_premises_and_alternatives(self):
        request = packet()
        request['causal_chain']['attribution'] = claim(
            basis='reasonable_inference', evidence_claim_ids=['inference'])
        request['evidence_claims'] = [{'id': 'inference', 'kind': 'reasonable_inference',
                                      'source_ids': ['panel'], 'premises': [claim()],
                                      'checks': {'alternatives_considered': claim()}}]
        self.assertEqual(self.status(request), 'conditional')

    def test_state_transfer_requires_justification_not_fatigue_multiplier(self):
        request = packet('observed_output', 'state_transfer')
        request['actor_state'] = {'fatigue': claim()}
        request['state_transfer'] = {'target_state': 'healthy ordinary form',
                                      'compatible': claim(None)}
        result = run(request)
        self.assertEqual(result['admissions']['observed_output']['status'], 'supported_by_packet')
        self.assertEqual(result['admissions']['state_transfer']['status'], 'undetermined')

    def test_failure_cannot_become_general_upper_bound(self):
        request = packet('upper_bound')
        request['upper_bound'] = {'scope': 'this attack against this target',
                                  'failure_observed': claim(), 'opportunity': claim(),
                                  'same_configuration': claim(), 'mechanism_applicable': claim()}
        self.assertEqual(self.status(request, 'upper_bound'), 'undetermined')
        request['effort'] = {'full_effort': claim()}
        self.assertEqual(self.status(request, 'upper_bound'), 'supported_by_packet')
        request['upper_bound']['same_configuration'] = claim(False)
        request['mode'] = 'highest'
        self.assertEqual(self.status(request, 'upper_bound'), 'blocked')

    def test_upper_bound_requires_an_attributable_observed_event(self):
        request = packet('upper_bound')
        request['upper_bound'] = {'scope': 'this contact and configuration',
                                  'failure_observed': claim(), 'opportunity': claim(),
                                  'same_configuration': claim(), 'mechanism_applicable': claim()}
        request['effort'] = {'full_effort': claim()}
        request['causal_chain']['attribution'] = claim(False)
        self.assertEqual(self.status(request, 'upper_bound'), 'blocked')

    def test_author_null_check_is_unknown_and_malformed_check_is_value_error(self):
        request = self.author_packet()
        request['evidence_claims'][0]['checks']['identity_verified'] = None
        self.assertEqual(self.status(request, 'full_effort'), 'undetermined')
        request['evidence_claims'][0]['checks']['identity_verified'] = False
        with self.assertRaises(ValueError):
            run(request)

    def test_malformed_enum_types_raise_value_error(self):
        for value in ([], {}):
            request = packet()
            request['mode'] = value
            with self.assertRaises(ValueError):
                run(request)
            request = packet()
            request['sources'][0]['access'] = value
            with self.assertRaises(ValueError):
                run(request)
            request = packet()
            request['event']['observed_output']['basis'] = value
            with self.assertRaises(ValueError):
                run(request)

    def test_input_not_mutated_and_source_mapping_accepted(self):
        request = packet()
        request['sources'] = {x['id']: x for x in request['sources']}
        before = copy.deepcopy(request)
        run(request)
        self.assertEqual(request, before)

    def test_context_preserves_action_and_actual_output_without_interpreting_it(self):
        request = packet()
        request['effort'] = {'actual_output': 'one visible strike, no numerical extrapolation'}
        result = run(request)
        self.assertEqual(result['recorded_context']['effort'], request['effort'])
        self.assertEqual(result['recorded_context']['causal_chain'], request['causal_chain'])

    def test_invalid_mode_and_requested_use(self):
        request = packet()
        request['mode'] = 'all'
        with self.assertRaises(ValueError):
            run(request)
        request['mode'] = 'normal'
        request['requested_uses'] = ['universal_power']
        with self.assertRaises(ValueError):
            run(request)


if __name__ == '__main__':
    unittest.main()
