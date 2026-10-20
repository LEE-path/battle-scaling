"""Synthetic hax packets test policy boundaries, never fictional truth."""
import copy
import json
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from hax_policy import run


def level(rank, label):
    return {'system': 'synthetic-tiers', 'ruleset': 'synthetic-v1',
            'axis': 'affected_entity_tier', 'rank': rank, 'label': label,
            'source_ids': ['source']}


def check(state='pass', **extra):
    return {'state': state, 'explanation': 'Host-recorded synthetic mechanism check.',
            'source_ids': ['source'], **extra}


def packet(mode='normal'):
    return {
        'mode': mode, 'ability_id': 'mind-control',
        'sources': [{'id': 'source', 'access': 'provided', 'origin': 'primary',
                     'title': 'Synthetic packet; no real work is cited.'}],
        'caster_ap': level(1, 'building'),
        'observed_limit': {'basis': 'demonstrated', 'ability_id': 'mind-control',
                           'statement': 'The ability demonstrably controlled a city-tier entity.',
                           'source_ids': ['source'], 'level': level(2, 'city')},
        'world_ceiling': {'kind': 'strongest_character', 'character_id': 'world-strongest',
                          'source_ids': ['source'], 'level': level(3, 'star'),
                          'attainment': {'kind': 'achieved',
                                         'statement': 'The strongest character achieved star tier.',
                                         'source_ids': ['source']}},
        'target_level': level(2, 'city'),
        'checks': {key: check() for key in ('object', 'compatibility', 'activation', 'resistance')},
        'effect_scope': {'description': 'One target entity; entity tier is distinct from area/count.',
                         'resistance_interaction': 'Mind-control resistance checked separately.',
                         'source_ids': ['source']},
    }


class HaxPolicyTests(unittest.TestCase):
    def test_city_effect_is_not_limited_by_building_caster_ap(self):
        result = run(packet())
        self.assertEqual(result['status'], 'supported_by_packet')
        self.assertIs(result['within_observed_limit'], True)
        self.assertIs(result['within_world_ceiling'], True)

    def test_world_star_does_not_raise_city_ability_to_star(self):
        request = packet()
        request['target_level'] = level(3, 'star')
        result = run(request)
        self.assertEqual(result['status'], 'blocked')
        self.assertIs(result['within_observed_limit'], False)
        self.assertIs(result['within_world_ceiling'], True)

    def test_galaxy_target_is_blocked_by_both_caps(self):
        request = packet()
        request['target_level'] = level(4, 'galaxy')
        result = run(request)
        self.assertEqual(result['status'], 'blocked')
        self.assertIs(result['within_world_ceiling'], False)

    def test_world_cap_is_hard_in_all_modes(self):
        for mode in ('normal', 'highest', 'lowball'):
            with self.subTest(mode=mode):
                request = packet(mode)
                request['observed_limit']['level'] = level(5, 'universe')
                request['target_level'] = level(4, 'galaxy')
                request['assumptions'] = ['Assume no ceiling.']
                self.assertEqual(run(request)['status'], 'blocked')

    def test_highest_can_use_supported_raised_limits(self):
        request = packet('highest')
        request['observed_limit']['basis'] = 'supported_scaling'
        request['observed_limit']['statement'] = 'Mode-appropriate sourced scaling supports star tier.'
        request['observed_limit']['level'] = level(3, 'star')
        request['target_level'] = level(3, 'star')
        self.assertEqual(run(request)['status'], 'supported_by_packet')

    def test_highest_cannot_override_known_ability_cap(self):
        request = packet('highest')
        request['target_level'] = level(3, 'star')
        request['observed_limit']['assumption'] = 'Assume stronger.'
        self.assertEqual(run(request)['status'], 'blocked')

    def test_cosmology_structure_cannot_be_character_ceiling(self):
        request = packet()
        request['world_ceiling']['kind'] = 'cosmology_structure'
        result = run(request)
        self.assertEqual(result['status'], 'undetermined')
        self.assertIsNone(result['within_world_ceiling'])
        self.assertTrue(result['research_tasks'])

    def test_world_ceiling_needs_character_identity(self):
        request = packet()
        del request['world_ceiling']['character_id']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_world_ceiling_needs_achieved_evidence(self):
        request = packet()
        request['world_ceiling']['attainment']['kind'] = 'cosmology_exists'
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_world_ceiling_needs_achievement_statement(self):
        request = packet()
        del request['world_ceiling']['attainment']['statement']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_missing_observed_limit_is_not_infinity_or_caster_ap(self):
        request = packet()
        del request['observed_limit']
        result = run(request)
        self.assertEqual(result['status'], 'undetermined')
        self.assertIsNone(result['within_observed_limit'])
        self.assertTrue(result['research_tasks'])

    def test_world_exceedance_blocks_even_when_observed_limit_missing(self):
        request = packet()
        del request['observed_limit']
        request['target_level'] = level(4, 'galaxy')
        self.assertEqual(run(request)['status'], 'blocked')

    def test_different_ability_limit_cannot_be_reused(self):
        request = packet()
        request['observed_limit']['ability_id'] = 'teleportation'
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_known_incompatible_object_is_blocked(self):
        request = packet()
        request['checks']['object'] = check('fail', assumption='Pretend it works.')
        self.assertEqual(run(request)['status'], 'blocked')

    def test_all_mechanism_checks_remain_separate(self):
        for key in ('object', 'compatibility', 'activation', 'resistance'):
            with self.subTest(check=key):
                request = packet('highest')
                request['checks'][key] = check('fail')
                self.assertEqual(run(request)['status'], 'blocked')

    def test_unknown_resistance_is_not_automatically_no_resistance(self):
        request = packet()
        request['checks']['resistance'] = check('unknown')
        result = run(request)
        self.assertEqual(result['status'], 'undetermined')
        self.assertTrue(result['research_tasks'])

    def test_explicit_unknown_mechanism_assumption_is_conditional(self):
        request = packet()
        request['checks']['resistance'] = check('unknown', assumption='Assume no relevant resistance.')
        result = run(request)
        self.assertEqual(result['status'], 'conditional')
        self.assertIn('Assume no relevant resistance.', result['assumptions'])

    def test_assumption_cannot_replace_missing_cap(self):
        request = packet()
        del request['world_ceiling']
        request['assumptions'] = ['Assume world ceiling is infinite.']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_equal_tier_alone_does_not_prove_success(self):
        request = packet()
        request['checks'] = {}
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_scope_and_resistance_need_independent_statements(self):
        request = packet()
        del request['effect_scope']['resistance_interaction']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_cross_ruleset_rank_comparison_is_undetermined(self):
        request = packet()
        request['target_level']['ruleset'] = 'another-ruleset'
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_cross_system_rank_comparison_is_undetermined(self):
        request = packet()
        request['target_level']['system'] = 'another-system'
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_area_and_count_are_not_entity_tier(self):
        for axis in ('affected_area', 'target_count', 'caster_ap'):
            with self.subTest(axis=axis):
                request = packet()
                request['observed_limit']['level']['axis'] = axis
                self.assertEqual(run(request)['status'], 'undetermined')

    def test_nan_infinity_and_bool_are_not_ranks(self):
        for value in (float('nan'), float('inf'), float('-inf'), True, False):
            with self.subTest(rank=value):
                request = packet()
                request['target_level']['rank'] = value
                self.assertEqual(run(request)['status'], 'undetermined')

    def test_rank_must_have_a_readable_source(self):
        request = packet()
        request['target_level']['source_ids'] = ['missing']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_blocked_sources_are_not_admitted(self):
        request = packet()
        request['sources'][0]['access'] = 'blocked'
        result = run(request)
        self.assertEqual(result['status'], 'undetermined')
        self.assertEqual(result['source_ids'], [])

    def test_source_access_vocabulary_is_shared_with_pk_modes(self):
        from pk_modes import READABLE
        for access in READABLE:
            with self.subTest(access=access):
                request = packet()
                request['sources'][0]['access'] = access
                self.assertEqual(run(request)['status'], 'supported_by_packet')

    def test_primary_verified_is_only_host_metadata(self):
        request = packet()
        request['sources'][0]['access'] = 'verified'
        result = run(request)
        self.assertIs(result['original_source_verified'], False)
        self.assertIs(result['input_declares_primary_verified'], True)
        self.assertIn('does not', result['validation_scope'])

    def test_mode_specific_source_cannot_leak_to_normal(self):
        request = packet()
        request['sources'][0]['modes'] = ['highest']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_mode_specific_limit_cannot_leak_to_normal(self):
        request = packet()
        request['observed_limit']['modes'] = ['highest']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_limit_level_can_inherit_its_bound_provenance(self):
        request = packet()
        del request['observed_limit']['level']['source_ids']
        del request['world_ceiling']['level']['source_ids']
        self.assertEqual(run(request)['status'], 'supported_by_packet')

    def test_explicit_partial_order_comparison_without_rank(self):
        request = packet()
        for name in ('observed_limit', 'world_ceiling'):
            del request[name]['level']['rank']
        del request['target_level']['rank']
        request['explicit_comparisons'] = [
            {'left': 'target_level', 'relation': 'le', 'right': right,
             'explanation': 'Host sourced this local partial-order relation.', 'source_ids': ['source']}
            for right in ('observed_limit', 'world_ceiling')]
        result = run(request)
        self.assertEqual(result['status'], 'supported_by_packet')
        self.assertTrue(all(item['method'] == 'explicit_comparison' for item in result['comparison_trace']))

    def test_explicit_comparison_cannot_bridge_rulesets(self):
        request = packet()
        request['target_level']['ruleset'] = 'other'
        request['explicit_comparisons'] = [
            {'left': 'target_level', 'relation': 'le', 'right': right,
             'explanation': 'Unsupported standard bridge.', 'source_ids': ['source']}
            for right in ('observed_limit', 'world_ceiling')]
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_explicit_comparison_cannot_override_rank_exceedance(self):
        request = packet('highest')
        request['target_level'] = level(4, 'galaxy')
        request['explicit_comparisons'] = [
            {'left': 'target_level', 'relation': 'le', 'right': right,
             'explanation': 'Claimed exception.', 'source_ids': ['source']}
            for right in ('observed_limit', 'world_ceiling')]
        self.assertEqual(run(request)['status'], 'blocked')

    def test_explicit_partial_order_above_cap_blocks(self):
        request = packet()
        del request['observed_limit']['level']['rank']
        request['explicit_comparisons'] = [
            {'left': 'target_level', 'relation': 'gt', 'right': 'observed_limit',
             'explanation': 'The target exceeds the supported ability ceiling.', 'source_ids': ['source']}]
        self.assertEqual(run(request)['status'], 'blocked')

    def test_unsupported_total_order_is_not_invented(self):
        request = packet()
        del request['observed_limit']['level']['rank']
        result = run(request)
        self.assertEqual(result['status'], 'undetermined')
        self.assertIsNone(result['within_observed_limit'])

    def test_source_dict_is_supported(self):
        request = packet()
        request['sources'] = {'source': request['sources'][0]}
        self.assertEqual(run(request)['status'], 'supported_by_packet')

    def test_input_is_not_mutated_and_raw_packet_is_preserved(self):
        request = packet()
        original = copy.deepcopy(request)
        result = run(request)
        self.assertEqual(request, original)
        self.assertEqual(result['request_snapshot'], original)
        self.assertTrue(result['comparison_trace'])

    def test_unknown_mode_and_malformed_packets_do_not_pass(self):
        for request in (None, [], {}, {'mode': 'whatever'}, {'sources': 'bad'}):
            with self.subTest(request=request):
                result = run(request)
                self.assertEqual(result['status'], 'undetermined')
                self.assertTrue(result['research_tasks'])

    def test_unhashable_mode_is_a_gap_not_an_exception(self):
        request = packet()
        request['mode'] = ['highest']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_malformed_access_metadata_cannot_pass_or_crash(self):
        request = packet()
        request['sources'][0]['access'] = ['verified']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_duplicate_source_ids_are_ambiguous_not_arbitrarily_trusted(self):
        request = packet()
        request['sources'].append({'id': 'source', 'access': 'blocked'})
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_unreadable_failure_is_not_a_known_blocker(self):
        request = packet()
        request['checks']['object'] = check('fail', source_ids=['unreadable'])
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_unsourced_explicit_comparison_is_not_an_order(self):
        request = packet()
        del request['observed_limit']['level']['rank']
        request['explicit_comparisons'] = [
            {'left': 'target_level', 'relation': 'le', 'right': 'observed_limit',
             'explanation': 'A host suggestion without readable evidence.', 'source_ids': ['missing']}]
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_synthetic_case_fixture_runs_and_identifies_itself(self):
        path = pathlib.Path(__file__).resolve().parents[1] / 'assets' / 'cases' / 'hax-ceiling-synthetic.json'
        request = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(request['fixture_kind'], 'synthetic_not_original_evidence')
        self.assertEqual(run(request)['status'], 'supported_by_packet')


if __name__ == '__main__':
    unittest.main()
