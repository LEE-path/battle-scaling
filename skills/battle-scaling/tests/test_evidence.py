import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from evidence import analyze_case, validate_case, classify_energy


def packet():
    return {
        'schema_version': 1, 'case_id': 'regression-only', 'fixture_kind': 'synthetic',
        'characters': [{'id': 'a', 'name': 'A', 'version': 'one', 'state': 'base'},
                       {'id': 'b', 'name': 'B', 'version': 'one', 'state': 'base'}],
        'sources': [{'id': 's', 'title': 'Synthetic regression evidence', 'origin': 'synthetic',
                     'access': 'provided', 'locator': 'fixture event 1'}],
        'anchors': [
            {'id': 'regular', 'subject': 'a', 'attribute': 'attack_energy', 'kind': 'repeated_feat',
             'quantity': {'value': 2000, 'unit': 'J'}, 'evidence_ids': ['s']},
            {'id': 'peak', 'subject': 'a', 'attribute': 'attack_energy', 'kind': 'outlier',
             'quantity': {'value': 1e12, 'unit': 'J'}, 'evidence_ids': ['s']},
            {'id': 'low', 'subject': 'a', 'attribute': 'attack_energy', 'kind': 'anti_feat',
             'quantity': {'value': 20, 'unit': 'J'}, 'evidence_ids': ['s'], 'context': 'weakened'}
        ], 'edges': []}


class EvidenceTests(unittest.TestCase):
    def test_modes_select_different_evidence(self):
        p = packet()
        result = analyze_case(p, 'all')
        values = {m: result['modes'][m]['conclusions'][0]['quantity']['best']
                  for m in ('normal', 'highest', 'lowball')}
        self.assertEqual(values, {'normal': 2000, 'highest': 1e12, 'lowball': 20})

    def test_normal_prefers_repeated_over_solo_credible(self):
        p = packet()
        p['anchors'][1]['kind'] = 'credible_feat'
        self.assertEqual(analyze_case(p)['modes']['normal']['conclusions'][0]['quantity']['best'], 2000)

    def test_tanking_requires_actual_attack_and_body(self):
        p = packet()
        p['edges'] = [{'id': 'tank', 'from': {'subject': 'a', 'attribute': 'attack_energy'},
                       'to': {'subject': 'b', 'attribute': 'durability_blunt'}, 'relation': 'tanked',
                       'evidence_ids': ['s'], 'conditions': {'effective_hit': True}}]
        result = analyze_case(p, 'all')
        self.assertEqual(len(result['modes']['normal']['conclusions']), 1)
        inherited = [c for c in result['modes']['highest']['conclusions'] if c['subject'] == 'b'][0]
        self.assertTrue(inherited['assumptions'])

    def test_no_circular_multiplication(self):
        p = packet()
        p['edges'] = [{'id': 'ab', 'from': {'subject': 'a', 'attribute': 'attack_energy'},
                      'to': {'subject': 'b', 'attribute': 'attack_energy'}, 'relation': 'same_tier',
                      'evidence_ids': ['s'], 'conditions': {'corroborated': True},
                      'multiplier': 10, 'multiplier_evidence_ids': ['s']},
                     {'id': 'ba', 'from': {'subject': 'b', 'attribute': 'attack_energy'},
                      'to': {'subject': 'a', 'attribute': 'attack_energy'}, 'relation': 'same_tier',
                      'evidence_ids': ['s'], 'conditions': {'corroborated': True},
                      'multiplier': 10, 'multiplier_evidence_ids': ['s']}]
        result = analyze_case(p, 'highest')['modes']['highest']
        a = next(c for c in result['conclusions'] if c['subject'] == 'a')
        self.assertEqual(a['quantity']['best'], 1e12)
        self.assertTrue(any(x['reason'] == 'cycle' for x in result['excluded']))

    def test_missing_provenance_and_nan_are_rejected(self):
        p = packet()
        p['anchors'][0]['evidence_ids'] = ['missing']
        p['anchors'][1]['quantity']['value'] = float('nan')
        self.assertGreaterEqual(len(validate_case(p)), 2)

    def test_blocked_sources_cannot_establish_anchor(self):
        p = packet()
        p['sources'][0]['access'] = 'blocked'
        self.assertEqual(analyze_case(p)['modes']['normal']['conclusions'], [])

    def test_force_not_mapped_to_energy(self):
        self.assertIsNone(classify_energy({'best': 1e9, 'unit': 'N'}))

    def test_no_arbitrary_group_probability(self):
        p = packet()
        p['matchup'] = {'teams': ['a', 'b'], 'win_paths': []}
        r = analyze_case(p)['matchup']
        self.assertEqual(r['verdict'], 'insufficient_evidence')
        self.assertNotIn('probability', r)

    def test_upper_bound_not_treated_as_attack_floor(self):
        p = packet()
        p['anchors'][0]['bound'] = 'upper'
        p['edges'] = [{'id': 'ab', 'from': {'subject': 'a', 'attribute': 'attack_energy'},
                      'to': {'subject': 'b', 'attribute': 'durability_blunt'}, 'relation': 'tanked',
                      'evidence_ids': ['s'], 'conditions': {'effective_hit': True, 'actual_scale': True, 'body_only': True}}]
        r = analyze_case(p)['modes']['normal']
        self.assertFalse(any(c['subject'] == 'b' for c in r['conclusions']))

    def test_observed_counterfact_cannot_be_assumed_away(self):
        p = packet()
        p['edges'] = [{'id': 'shield', 'from': {'subject': 'a', 'attribute': 'attack_energy'},
                      'to': {'subject': 'b', 'attribute': 'durability_blunt'}, 'relation': 'tanked',
                      'evidence_ids': ['s'], 'conditions': {'effective_hit': True, 'body_only': False}}]
        r = analyze_case(p, 'highest')['modes']['highest']
        self.assertFalse(any(c['subject'] == 'b' for c in r['conclusions']))


if __name__ == '__main__':
    unittest.main()
