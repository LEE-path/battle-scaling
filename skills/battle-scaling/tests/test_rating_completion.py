"""Completion admission regressions, using invented feats rather than real tiers.

The gate checks a host's submitted audit, never whether an invented or real feat
is true. These tests distinguish a targeted complete rating from a local floor,
and prevent stale acceptance from overriding a supplied withdrawal.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from rating_fixtures import with_independent_ratings
from rating_preflight import review
from evidence import analyze_case
from writing_battle import run as writing
from combat_trace import run as process
from rating_fixtures import legacy_analyze_case as analyze_case  # Explicit legacy regression


def packet():
    return with_independent_ratings({
        'schema_version': 1, 'case_id': 'completion-audit-fiction',
        'characters': [{'id': who, 'name': who, 'version': 'invented-v1', 'state': 'active', 'equipment': []}
                       for who in ('a', 'b')],
        'sources': [], 'anchors': [], 'edges': [],
        'matchup': {'teams': ['a', 'b'], 'win_paths': []},
    }, modes=('normal', 'highest', 'lowball'))


def gate(request, mode='normal'):
    return review(request['characters'], request['independent_ratings'], request['sources'],
                  standard=request.get('standard', 'wangba'), mode=mode,
                  **({'rating_status': request['rating_status']}
                                if 'rating_status' in request else {}))


def candidate(row, disposition='open', impact='material'):
    return {'id': 'higher-physical-chain', 'affects': ['main_tier', '输出', '体防'],
            'disposition': disposition, 'impact': impact,
            'reasoning': 'A separate same-state feat and its physical injury transfer may change the selected tier; its actual attack contribution must be reviewed.',
            'evidence_ids': list(row['main_tier']['evidence_ids'])}


class CompletionTests(unittest.TestCase):
    def route_inputs(self):
        overview = packet()
        trace = packet()
        trace['actors'] = copy.deepcopy(trace.pop('characters'))
        trace['steps'] = []
        story = json.loads((ROOT / 'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))
        story.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        return (
            ('overview', overview, lambda value: analyze_case(value)['matchup']),
            ('process', trace, process),
            ('writing', story, writing),
        )

    def test_unresolved_material_higher_feat_blocks_every_combat_route(self):
        for name, request, run in self.route_inputs():
            row = request['independent_ratings'][0]
            row['completion_review']['candidates'] = [candidate(row)]
            # A numerical local floor and all nine labels still exist.
            row['main_tier']['model'] = {'local_energy_J': 150000}
            result = run(request)
            with self.subTest(route=name):
                self.assertEqual(result['rating_preflight']['status'], 'needs_research')
                self.assertIn('open material candidate', ' '.join(result['rating_preflight']['needs']))
                if name == 'overview':
                    self.assertIsNone(result['assessment'])
                    self.assertEqual(result['win_paths'], [])
                elif name == 'process':
                    self.assertEqual(result['trace'], [])
                    self.assertNotIn('final_state', result)
                else:
                    self.assertEqual(result['status'], 'needs_independent_rating')
                    self.assertFalse(result['narrative_generated'])

    def test_legacy_complete_looking_packets_require_a_new_completion_review(self):
        for name, request, run in self.route_inputs():
            request['independent_ratings'][0].pop('completion_review')
            result = run(request)
            with self.subTest(route=name):
                self.assertEqual(result['rating_preflight']['status'], 'needs_research')
                self.assertIn('legacy labels', ' '.join(result['rating_preflight']['needs']))

    def test_local_floor_alone_is_not_a_completed_rating_in_any_mode(self):
        request = packet()
        for row in request['independent_ratings']:
            row['completion_review']['selected_basis'] = 'local_floor'
        for mode in ('normal', 'highest', 'lowball'):
            self.assertEqual(gate(request, mode)['status'], 'needs_research')

    def test_established_floor_after_targeted_complete_review_can_be_selected(self):
        request = packet()
        row = request['independent_ratings'][0]
        row['completion_review']['selection_findings']['reasoning'] = (
            'Review of the supplied final-state feats finds the measured physical showing '
            'is its highest repeated credible feat. Its exact ceiling is unmeasured; '
            'this is a specific established lower bound selected after comparing candidates.')
        self.assertEqual(row['main_tier']['basis'], 'lower_bound')
        self.assertEqual(gate(request)['status'], 'ready')

    def test_rejected_group_hax_or_wrong_version_chain_does_not_force_inflation(self):
        reasons = (
            'The higher event is two actors jointly discharging electricity. It establishes a group electrical effect, not this actor alone delivering equal blunt impact.',
            'The shield deletes incoming energy through a special mechanism, so its absorbed total does not establish bodily impact durability.',
            'The claim belongs to a later enhanced version whose equipment is absent in the reviewed ending configuration.',
        )
        for reason in reasons:
            request = packet()
            row = request['independent_ratings'][0]
            high = candidate(row, 'excluded')
            high['reasoning'] = reason
            row['completion_review']['candidates'] = [high]
            row['completion_review']['selection_findings']['reasoning'] = (
                'The reviewed higher candidate does not transfer to these attributes for '
                'the documented causal reason; retain the established physical tier.')
            with self.subTest(reason=reason):
                result = gate(request)
                self.assertEqual(result['status'], 'ready')
                self.assertFalse(result['semantic_rating_verified'])

    def test_adopted_qualitative_scaling_does_not_require_invented_joules(self):
        request = packet()
        row = request['independent_ratings'][0]
        adopted = candidate(row, 'adopted')
        adopted['reasoning'] = 'The same target without its special shield survives the established physical reference attack, and this configuration repeatedly injures it physically; the source-backed transfer sets the selected tier.'
        row['completion_review']['candidates'] = [adopted]
        self.assertEqual(gate(request)['status'], 'ready')

    def test_explicit_nonmaterial_open_candidate_does_not_require_exhaustive_search(self):
        request = packet()
        row = request['independent_ratings'][0]
        note = candidate(row, 'open', 'non_material')
        note['affects'] = ['经验']
        note['reasoning'] = 'The optional count of otherwise identical training matches is unverified, but cannot alter the fixed experience category or the requested battle comparison.'
        row['completion_review']['candidates'] = [note]
        self.assertEqual(gate(request)['status'], 'ready')

    def test_incomplete_and_revoked_audits_override_embedded_host_acceptance(self):
        for status in ('partial', 'withdrawn', 'superseded', 'invented-status', None):
            request = packet()
            request['independent_ratings'][0]['completion_review']['status'] = status
            with self.subTest(status=status):
                self.assertEqual(gate(request)['status'], 'needs_research')

    def test_host_acceptance_must_bind_exact_reviewed_revision(self):
        request = packet()
        row = request['independent_ratings'][0]
        row['completion_review']['revision'] = 'new-review-r2'
        self.assertEqual(gate(request)['status'], 'needs_research')
        row['host_review']['reviewed_revision'] = 'new-review-r2'
        self.assertEqual(gate(request)['status'], 'ready')

    def test_supplied_withdrawal_blocks_all_routes_even_if_every_row_is_accepted(self):
        for name, request, run in self.route_inputs():
            request['rating_status'] = {'status': 'needs_research',
                                       'accepted_complete_normal_ratings': False}
            result = run(request)
            with self.subTest(route=name):
                self.assertEqual(result['rating_preflight']['status'], 'needs_research')
                self.assertEqual(result['rating_preflight']['accepted_subject_ids'], [])
                self.assertTrue(result['rating_preflight']['current_status_supplied'])
                self.assertFalse(result['rating_preflight']['latest_external_status_verified'])

    def test_false_normal_acceptance_is_not_silently_defaulted_to_true(self):
        request = packet()
        request['rating_status'] = {'status': 'current', 'accepted_complete_normal_ratings': False}
        self.assertEqual(gate(request)['status'], 'needs_research')
        # This boolean has normal-specific scope; a separately complete highest
        # packet can still pass when the supplied overall status is current.
        self.assertEqual(gate(request, 'highest')['status'], 'ready')

    def test_malformed_current_status_is_blocked_without_crashing(self):
        for status in (None, False, [], {}, {'status': 'ready'}, {'status': 'withdrawn'},
                       {'status': 'superseded'}, {'status': 'current', 'revisions': []},
                       {'status': 'current', 'revisions': {'a': ''}},
                       {'status': 'current', 'accepted_complete_normal_ratings': 0},
                       {'status': 'current', 'accepted_complete_normal_ratings': 'false'}):
            request = packet()
            request['rating_status'] = status
            with self.subTest(status=status):
                self.assertEqual(gate(request)['status'], 'needs_research')

    def test_current_status_revision_cannot_be_ignored_by_newer_embedded_packet(self):
        request = packet()
        request['rating_status'] = {'status': 'current', 'revisions': {'a': 'accepted-r2', 'b': 'synthetic-scope-v1'}}
        self.assertEqual(gate(request)['status'], 'needs_research')
        row = request['independent_ratings'][0]
        row['completion_review']['revision'] = 'accepted-r2'
        row['host_review']['reviewed_revision'] = 'accepted-r2'
        self.assertEqual(gate(request)['status'], 'ready')
        request['rating_status']['revisions'].pop('b')
        self.assertEqual(gate(request)['status'], 'needs_research')

    def test_source_and_candidate_contracts_are_not_checklist_booleans(self):
        mutations = (
            lambda a: a.update(scope_findings=True),
            lambda a: a['selection_findings'].update(evidence_ids=[]),
            lambda a: a['scope_findings'].update(reasoning=''),
            lambda a: a.update(candidates=True),
            lambda a: a.update(candidates=[{'id': 'high', 'affects': ['输出'], 'disposition': 'excluded', 'impact': 'material', 'reasoning': 'Not the same mechanism.', 'evidence_ids': ['unread-source']}]),
            lambda a: a.update(candidates=[{'id': 'high', 'affects': ['invented-field'], 'disposition': 'excluded', 'impact': 'material', 'reasoning': 'Different configuration.', 'evidence_ids': ['independent-rating-fixture']}]),
        )
        for mutation in mutations:
            request = packet()
            mutation(request['independent_ratings'][0]['completion_review'])
            with self.subTest(mutation=mutation):
                self.assertEqual(gate(request)['status'], 'needs_research')

    def test_macro_process_forwarding_and_writing_author_pack_preserve_current_status(self):
        request = json.loads((ROOT / 'assets/cases/pk-dual-presentation-synthetic.json').read_text(encoding='utf-8'))
        request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        request['matchup']['presentation'] = 'process'
        request['rating_status'] = {'status': 'current', 'revisions': {'a': 'synthetic-scope-v2', 'b': 'synthetic-scope-v2'}}
        result = analyze_case(request)['matchup']['process']
        self.assertEqual(result['rating_preflight']['status'], 'ready')
        self.assertTrue(result['rating_preflight']['current_status_supplied'])
        story = json.loads((ROOT / 'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))
        story.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        story['rating_status'] = {'status': 'current'}
        authored = writing(story)
        self.assertEqual(authored['author_pack']['rating_status'], {'status': 'current'})
        authored['author_pack']['rating_status']['status'] = 'withdrawn'
        self.assertEqual(story['rating_status']['status'], 'current')

    def test_review_never_mutates_inputs_or_discovers_external_status(self):
        request = packet()
        request['rating_status'] = {'status': 'current', 'revisions': {'a': 'synthetic-scope-v1', 'b': 'synthetic-scope-v1'}}
        before = copy.deepcopy(request)
        result = gate(request)
        self.assertEqual(request, before)
        self.assertTrue(result['completion_review_is_declaration'])
        self.assertFalse(result['latest_external_status_verified'])
        request.pop('rating_status')
        self.assertFalse(gate(request)['current_status_supplied'])

    def test_explicit_non_property_reference_cannot_supply_main_or_physical_tiers(self):
        for standard in ('wangba', 'vsb'):
            for mode in ('normal', 'highest', 'lowball'):
                for field in ('main_tier', '输出', '体防', '破坏'):
                    request = packet()
                    request['standard'] = standard
                    request = with_independent_ratings(request, modes=('normal', 'highest', 'lowball'))
                    self.assertEqual(gate(request, mode)['status'], 'ready')
                    row = next(row for row in request['independent_ratings']
                               if row['character_id'] == 'a' and row['mode'] == mode)
                    node = row['main_tier'] if field == 'main_tier' else row['dimensions'][field]
                    node['proves_character_property'] = False
                    with self.subTest(standard=standard, mode=mode, field=field):
                        result = gate(request, mode)
                        self.assertEqual(result['status'], 'needs_research')
                        self.assertIn('does not prove a character property', ' '.join(result['needs']))

    def test_wangba_energy_mapping_cannot_impersonate_property_but_vsb_rule_is_separate(self):
        for standard in ('wangba', 'vsb'):
            for field in ('main_tier', '输出', '体防', '破坏'):
                request = packet()
                request['standard'] = standard
                request = with_independent_ratings(request)
                row = request['independent_ratings'][0]
                node = row['main_tier'] if field == 'main_tier' else row['dimensions'][field]
                node['mapping_kind'] = 'energy_reference'
                with self.subTest(standard=standard, field=field):
                    result = gate(request)
                    self.assertEqual(result['status'], 'needs_research' if standard == 'wangba' else 'ready')
                # Reference metadata may remain in supporting material when the
                # main/physical assessment itself is independently established.
                node.pop('mapping_kind')
                node['supporting_energy_reference'] = {'mapping_kind': 'energy_reference',
                                                       'proves_character_property': False}
                self.assertEqual(gate(request)['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
