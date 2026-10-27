"""Writing structure regression checks use invented authors and invented fighters."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from writing_battle import RATING_FIELDS, run
from rating_fixtures import rated_call
run = rated_call(run, writing=True)


def sample():
    return json.loads((ROOT / 'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))


class WritingBattleTests(unittest.TestCase):
    def test_prepare_is_not_a_prose_generator_and_does_not_mutate_input(self):
        request = sample()
        request['operation'] = 'prepare'
        before = copy.deepcopy(request)
        result = run(request)
        self.assertEqual(request, before)
        self.assertEqual(result['status'], 'ready_for_host')
        self.assertFalse(result['narrative_generated'])
        self.assertNotIn('text', result)
        self.assertFalse(result['battle_evidence'])

    def test_writing_opt_in_is_mandatory(self):
        for purpose in (None, 'battle', 'rating', ''):
            with self.subTest(purpose=purpose), self.assertRaises(ValueError):
                request = sample()
                request['purpose'] = purpose
                run(request)

    def test_invalid_operation_and_standard_are_not_silently_coerced(self):
        for key, value in (('operation', 'generate'), ('standard', 'both')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                request = sample()
                request[key] = value
                run(request)

    def test_default_standard_and_vsb_are_both_writing_contracts(self):
        for standard in ('wangba', 'vsb', None):
            request = sample()
            if standard is None:
                del request['standard']
            else:
                request['standard'] = standard
            result = run(request)
            self.assertEqual(result['standard'], standard or 'wangba')
            self.assertEqual(result['status'], 'structure_checked')

    def test_all_nine_display_dimensions_are_derived_from_the_real_accepted_rating(self):
        request = sample()
        del request['fighters'][0]['ratings']
        result = run(request)
        self.assertEqual(result['status'], 'structure_checked')
        row = result['author_pack']['independent_ratings'][0]
        for field in RATING_FIELDS:
            self.assertEqual(result['author_pack']['fighters'][0]['ratings'][field], row['dimensions'][field]['label'])
        self.assertNotIn('ratings', request['fighters'][0])

    def test_incomplete_skill_mechanism_becomes_a_need(self):
        request = sample()
        del request['fighters'][0]['skills'][0]['limits']
        result = run(request)
        self.assertEqual(result['status'], 'needs_input')
        self.assertTrue(any('.limits' in item for item in result['needs']))

    def test_author_can_fix_the_weaker_fighters_victory(self):
        result = run(sample())
        self.assertEqual(result['status'], 'structure_checked')
        self.assertEqual(result['fixed_ending']['winner'], 'lan')
        self.assertEqual(result['winner_selection'], 'author_fixed')
        self.assertFalse(result['tactical_feasibility_verified'])

    def test_unfixed_ending_does_not_default_to_advantage_winner(self):
        request = sample()
        del request['constraints']['ending']
        result = run(request)
        self.assertEqual(result['status'], 'structure_checked')
        self.assertIsNone(result['fixed_ending'])
        self.assertEqual(result['winner_selection'], 'host_selects_plausible_story_outcome')

    def test_prose_skill_mention_cannot_satisfy_required_use(self):
        request = sample()
        for beat in request['draft']['beats']:
            for action in beat['actions']:
                action.pop('skill_id', None)
        result = run(request)
        self.assertEqual(result['status'], 'needs_revision')
        self.assertEqual(len([task for task in result['revision_tasks'] if 'Required skill' in task]), 3)
        self.assertTrue(all(not item['action_declared'] for item in result['coverage']['required_skills']))

    def test_unknown_actor_and_skill_references_are_invalid(self):
        for action in ({'actor': 'outsider', 'target': 'lan'},
                       {'actor': 'lan', 'target': 'shuo', 'skill_id': 'arc'},
                       {'actor': 'lan', 'target': 'new_ally'}):
            with self.subTest(action=action):
                request = sample()
                request['draft']['beats'][0]['actions'].append(action)
                self.assertEqual(run(request)['status'], 'invalid')

    def test_unknown_required_references_and_duplicate_ids_are_invalid(self):
        request = sample()
        request['constraints']['required_skills'].append({'fighter_id': 'lan', 'skill_id': 'new_skill'})
        request['fighters'][1]['id'] = 'lan'
        self.assertEqual(run(request)['status'], 'invalid')

    def test_malformed_reference_values_are_reported_instead_of_crashing(self):
        requests = []
        for field in ('actor', 'target', 'skill_id'):
            request = sample()
            request['draft']['beats'][0]['actions'][0][field] = ['not', 'an', 'id']
            requests.append(request)
        request = sample()
        request['constraints']['required_skills'][0]['fighter_id'] = {}
        requests.append(request)
        request = sample()
        request['constraints']['ending']['winner'] = {}
        requests.append(request)
        request = sample()
        request['draft']['outcome']['winner'] = []
        requests.append(request)
        for request in requests:
            with self.subTest(request=request['constraints']['ending']):
                self.assertEqual(run(request)['status'], 'invalid')

    def test_required_event_needs_a_structured_declaration(self):
        request = sample()
        request['draft']['beats'][1]['fulfills'] = []
        result = run(request)
        self.assertEqual(result['status'], 'needs_revision')
        self.assertFalse(result['coverage']['semantic_fulfillment_verified'])

    def test_unknown_event_tag_is_not_accepted(self):
        request = sample()
        request['draft']['beats'][1]['fulfills'].append('secret_new_event')
        self.assertEqual(run(request)['status'], 'invalid')

    def test_required_event_order_accepts_separate_ordered_beats_only_as_declarations(self):
        result = run(sample())
        review = result['coverage']['required_event_order']
        self.assertEqual(result['status'], 'structure_checked')
        self.assertEqual(review['requested'], ['counter', 'claim'])
        self.assertEqual(review['declared_beat_indices'], {'counter': [1], 'claim': [2]})
        self.assertTrue(review['declared_order_matches'])
        self.assertFalse(review['prose_order_verified'])

    def test_reversed_event_order_requires_revision(self):
        request = sample()
        request['draft']['beats'][1]['fulfills'] = ['claim']
        request['draft']['beats'][2]['fulfills'] = ['counter']
        result = run(request)
        self.assertEqual(result['status'], 'needs_revision')
        self.assertFalse(result['coverage']['required_event_order']['declared_order_matches'])
        self.assertTrue(any('strictly later' in task for task in result['revision_tasks']))

    def test_events_in_one_beat_do_not_prove_order_even_if_tags_are_ordered(self):
        request = sample()
        request['draft']['beats'][1]['fulfills'] = ['counter', 'claim']
        request['draft']['beats'][2]['fulfills'] = []
        result = run(request)
        self.assertEqual(result['status'], 'needs_revision')
        self.assertFalse(result['coverage']['required_event_order']['declared_order_matches'])
        self.assertTrue(all(item['beat_declared'] for item in result['coverage']['required_events']))

    def test_ordered_event_missing_or_repeated_across_beats_needs_revision(self):
        for tags in ([], ['counter', 'claim']):
            with self.subTest(tags=tags):
                request = sample()
                request['draft']['beats'][2]['fulfills'] = tags
                result = run(request)
                self.assertEqual(result['status'], 'needs_revision')
                self.assertFalse(result['coverage']['required_event_order']['declared_order_matches'])

    def test_unknown_duplicate_and_malformed_order_ids_are_invalid(self):
        for order in (['unknown'], ['counter', 'counter'], ['counter', {}], 'counter'):
            with self.subTest(order=order):
                request = sample()
                request['constraints']['required_event_order'] = order
                self.assertEqual(run(request)['status'], 'invalid')

    def test_prepare_retains_order_without_claiming_to_check_unwritten_beats(self):
        request = sample()
        request['operation'] = 'prepare'
        review = run(request)['coverage']['required_event_order']
        self.assertEqual(review['requested'], ['counter', 'claim'])
        self.assertFalse(review['declaration_order_checked'])
        self.assertIsNone(review['declared_order_matches'])

    def test_fixed_winner_result_and_method_must_match(self):
        for field, value in (('winner', 'shuo'), ('result', '击杀守门人。'), ('method', '新增无视防御技能。')):
            with self.subTest(field=field):
                request = sample()
                request['draft']['outcome'][field] = value
                result = run(request)
                self.assertEqual(result['status'], 'needs_revision')
                self.assertTrue(any('outcome.' + field in item for item in result['revision_tasks']))

    def test_review_without_draft_requests_host_writing(self):
        request = sample()
        del request['draft']
        result = run(request)
        self.assertEqual(result['status'], 'needs_revision')
        self.assertFalse(result['narrative_generated'])

    def test_hard_conflict_asks_author_to_supply_settings(self):
        request = sample()
        request['host_conflicts'] = [{'id': 'hard', 'description': '指定击杀但原设定没有可致死途径。', 'status': 'unresolved'}]
        result = run(request)
        self.assertEqual(result['status'], 'awaiting_author_settings')
        self.assertIn('author_question', result)
        self.assertEqual(result['unresolved_conflict_ids'], ['hard'])

    def test_author_question_names_only_first_unresolved_conflict_and_retains_full_archive(self):
        request = sample()
        request['host_conflicts'] = [
            {'id': 'done', 'description': '已经解决的限制。', 'status': 'resolved', 'resolution': '原设定已明确。'},
            {'id': 'first', 'description': '第一次冲突：无法攻击心智。', 'status': 'unresolved'},
            {'id': 'second', 'description': '第二次冲突：无法跨越距离。', 'status': 'unresolved'},
        ]
        before = copy.deepcopy(request['host_conflicts'])
        result = run(request)
        question = result['author_question']
        self.assertIn(before[1]['description'], question)
        self.assertNotIn(before[0]['description'], question)
        self.assertNotIn(before[2]['description'], question)
        self.assertEqual(question.count('？'), 1)
        self.assertEqual(result['host_conflicts'], before)
        result['host_conflicts'][0]['description'] = 'changed output'
        self.assertEqual(request['host_conflicts'], before)

    def test_keep_settings_continues_planning_without_certifying_unresolved_outcome(self):
        for operation, expected in (('prepare', 'continue_with_original_settings'), ('review', 'unresolved_under_original_settings')):
            request = sample()
            request['operation'] = operation
            request['author_response'] = 'keep_settings'
            request['host_conflicts'] = [{'id': 'hard', 'description': '强制结局仍无合法路径。', 'status': 'unresolved'}]
            result = run(request)
            self.assertEqual(result['status'], expected)
            self.assertNotIn('author_question', result)
            self.assertTrue(any('established tactical' in task for task in result['host_tasks']))
            self.assertFalse(result['tactical_feasibility_verified'])

    def test_declared_resolved_conflict_is_not_semantic_verification(self):
        request = sample()
        request['host_conflicts'] = [{'id': 'resolved', 'description': '获胜是否必须击倒对手？', 'status': 'resolved',
                                      'resolution': '作者原定任务条件允许携信标越界获胜。'}]
        result = run(request)
        self.assertEqual(result['status'], 'structure_checked')
        self.assertFalse(result['conflict_resolution_semantics_verified'])
        self.assertTrue(result['host_semantic_review_required'])

    def test_resolved_flag_requires_a_resolution_note(self):
        request = sample()
        request['host_conflicts'] = [{'id': 'bad', 'description': '未解释的冲突。', 'status': 'resolved'}]
        self.assertEqual(run(request)['status'], 'invalid')

    def test_draw_and_open_author_endings_are_supported(self):
        for winner in ('draw', 'mutual_defeat', 'open'):
            with self.subTest(winner=winner):
                request = sample()
                request['constraints']['ending'] = {'winner': winner, 'result': '作者指定的合成结尾。'}
                request['draft']['outcome'] = copy.deepcopy(request['constraints']['ending'])
                self.assertEqual(run(request)['status'], 'structure_checked')

    def test_multiple_fighters_and_environment_targets_are_supported(self):
        request = sample()
        third = copy.deepcopy(request['fighters'][0])
        third['id'], third['name'], third['skills'] = 'third', '观测者', []
        request['fighters'].append(third)
        request['draft']['beats'][0]['actions'].append({'actor': 'third', 'target': 'beacon'})
        self.assertEqual(run(request)['status'], 'structure_checked')

    def test_synthetic_fixture_cannot_be_promoted_to_evidence_by_input_flags(self):
        request = sample()
        request.update(battle_evidence=True, tactical_feasibility_verified=True, status='verified')
        result = run(request)
        self.assertEqual(result['status'], 'structure_checked')
        self.assertFalse(result['battle_evidence'])
        self.assertFalse(result['canon_evidence'])
        self.assertFalse(result['tactical_feasibility_verified'])
        self.assertIn('does not verify prose entailment', result['validation_scope'])


if __name__ == '__main__':
    unittest.main()
