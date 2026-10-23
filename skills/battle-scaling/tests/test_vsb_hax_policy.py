"""Synthetic VSB mechanism packets test audit boundaries, not fictional truth."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from vsb_hax_policy import CHECKS, run


def check(state='pass', **extra):
    return {'state': state, 'explanation': 'Synthetic host review of this specific mechanism.',
            'source_ids': ['source'], **extra}


def packet(mode='normal'):
    return {
        'mode': mode, 'ability_id': 'synthetic-mind-hax',
        'actor_id': 'a', 'target_id': 'b',
        'sources': [{'id': 'source', 'access': 'provided', 'origin': 'primary',
                     'title': 'Synthetic source, no real character is cited.'}],
        'effect_evidence': {'ability_id': 'synthetic-mind-hax', 'basis': 'demonstrated',
                            'statement': 'An actual successful use is recorded in the synthetic fixture.',
                            'mechanism': 'Acts on a nonphysical mind, independently of ordinary durability.',
                            'source_ids': ['source']},
        'target': {'description': 'A target with the relevant nonphysical mind in range.',
                   'source_ids': ['source']},
        'checks': {name: check() for name in CHECKS},
        'effect_scope': {'description': 'One target mind.',
                         'range_interaction': 'The exact target aspect is in the documented range.',
                         'resistance_interaction': 'Relevant resistance mechanism and potency were compared.',
                         'source_ids': ['source']},
    }


class VSBHaxPolicyTests(unittest.TestCase):
    def test_supported_packet_has_no_world_ceiling(self):
        result = run(packet())
        self.assertEqual(result['status'], 'supported_by_packet')
        self.assertIs(result['world_ceiling_applied'], False)
        self.assertEqual(result['source_ids'], ['source'])

    def test_caster_ap_and_strongest_character_do_not_cap_a_mechanism(self):
        request = packet()
        request.update(caster_ap={'rank': 1}, target_level={'rank': 100},
                       world_ceiling={'level': {'rank': 2}})
        self.assertEqual(run(request)['status'], 'supported_by_packet')

    def test_missing_source_is_unknown_not_pass(self):
        request = packet()
        request['checks']['resistance']['source_ids'] = ['absent']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_index_only_and_unreadable_sources_do_not_pass(self):
        for access in ('indexed', 'indexed_only', 'blocked', 'error', 'fetched_unreviewed', None):
            with self.subTest(access=access):
                request = packet()
                request['sources'][0]['access'] = access
                result = run(request)
                self.assertEqual(result['status'], 'undetermined')
                self.assertEqual(result['source_ids'], [])

    def test_all_readable_access_methods_are_admitted(self):
        for access in ('verified', 'provided', 'read', 'verified_via_host_browser'):
            request = packet()
            request['sources'][0]['access'] = access
            self.assertEqual(run(request)['status'], 'supported_by_packet')

    def test_each_separate_sourced_failure_blocks(self):
        for name in CHECKS:
            with self.subTest(check=name):
                request = packet()
                request['checks'][name] = check('fail', assumption='Pretend it works.')
                request['assumptions'] = ['Pretend every failure is removed.']
                self.assertEqual(run(request)['status'], 'blocked')

    def test_highest_and_lowball_do_not_override_failure(self):
        for mode in ('normal', 'highest', 'lowball'):
            request = packet(mode)
            request['checks']['no_limits'] = check('fail')
            self.assertEqual(run(request)['status'], 'blocked')

    def test_unsourced_failure_is_not_established(self):
        request = packet()
        request['checks']['activation'] = check('fail', source_ids=['unread'])
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_explicit_unknown_assumption_is_conditional(self):
        request = packet()
        request['checks']['compatibility'] = check('unknown', assumption='Assume these two specified energies are compatible.')
        result = run(request)
        self.assertEqual(result['status'], 'conditional')
        self.assertEqual(len(result['assumptions']), 1)

    def test_unknown_without_local_assumption_remains_unknown(self):
        request = packet()
        request['checks']['resistance'] = check('unknown')
        request['assumptions'] = ['A general hope is not a local premise.']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_missing_core_evidence_is_not_assumable(self):
        for key in ('effect_evidence', 'target', 'effect_scope'):
            request = packet()
            del request[key]
            request['assumptions'] = ['Assume the missing evidence exists.']
            self.assertEqual(run(request)['status'], 'undetermined')

    def test_scope_range_and_resistance_are_independent(self):
        for key in ('range_interaction', 'resistance_interaction', 'description'):
            request = packet()
            del request['effect_scope'][key]
            self.assertEqual(run(request)['status'], 'undetermined')

    def test_source_and_check_modes_do_not_leak(self):
        for location in ('source', 'check', 'effect'):
            request = packet()
            node = request['sources'][0] if location == 'source' else (
                request['checks']['activation'] if location == 'check' else request['effect_evidence'])
            node['modes'] = ['highest']
            self.assertEqual(run(request)['status'], 'undetermined')

    def test_invalid_mode_is_not_accepted(self):
        self.assertEqual(run(packet('wank'))['status'], 'undetermined')

    def test_missing_or_other_ability_evidence_is_not_reused(self):
        request = packet()
        request['effect_evidence']['ability_id'] = 'another-power'
        self.assertEqual(run(request)['status'], 'undetermined')
        request = packet()
        del request['ability_id']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_malformed_values_return_gaps(self):
        for value in (None, [], 'forged', 1):
            self.assertEqual(run(value)['status'], 'undetermined')
        for name in CHECKS:
            request = packet()
            request['checks'][name]['state'] = True
            self.assertEqual(run(request)['status'], 'undetermined')
        request = packet()
        request['sources'][0]['access'] = {'forged': 'read'}
        self.assertEqual(run(request)['status'], 'undetermined')
        request = packet()
        request['effect_evidence']['basis'] = ['demonstrated']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_missing_explanation_cannot_pass(self):
        request = packet()
        del request['checks']['no_limits']['explanation']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_duplicate_ids_are_ambiguous(self):
        request = packet()
        request['sources'].append(copy.deepcopy(request['sources'][0]))
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_precomputed_result_cannot_be_supplied_at_root_or_in_check(self):
        request = packet()
        request['status'] = 'supported_by_packet'
        self.assertEqual(run(request)['status'], 'undetermined')
        request = packet()
        request['checks']['activation']['source_access_checked'] = True
        self.assertEqual(run(request)['status'], 'undetermined')
        self.assertEqual(run(run(packet()))['status'], 'undetermined')

    def test_verified_is_only_host_metadata(self):
        request = packet()
        request['sources'][0]['access'] = 'verified'
        result = run(request)
        self.assertIs(result['original_source_verified'], False)
        self.assertIs(result['input_declares_primary_verified'], True)
        self.assertIn('does not independently', result['validation_scope'])

    def test_source_map_is_supported_and_input_is_unchanged(self):
        request = packet()
        request['sources'] = {'source': request['sources'][0]}
        before = copy.deepcopy(request)
        result = run(request)
        self.assertEqual(result['status'], 'supported_by_packet')
        self.assertEqual(request, before)
        self.assertEqual(result['request_snapshot'], before)

    def test_unknown_mechanism_never_uses_caster_ap_as_a_substitute(self):
        request = packet()
        request['caster_ap'] = {'label': 'Tier 0'}
        del request['effect_evidence']['mechanism']
        self.assertEqual(run(request)['status'], 'undetermined')

    def test_fail_precedes_unrelated_unknown(self):
        request = packet()
        request['checks']['resistance'] = check('fail')
        del request['effect_scope']
        self.assertEqual(run(request)['status'], 'blocked')

    def test_raw_layer_counts_are_not_automatically_compared(self):
        request = packet()
        request.update(attacker_layers=100, defender_layers=1)
        request['checks']['resistance'] = check('unknown')
        self.assertEqual(run(request)['status'], 'undetermined')


if __name__ == '__main__':
    unittest.main()
