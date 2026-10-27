"""Entry invariants, not a claim that a script understands canon or assigns tiers."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from rating_pipeline import tasks_for, run


class SharedResearchTests(unittest.TestCase):
    def subject(self):
        return {'id': 'solo', 'name': 'Research subject', 'work': 'Authored work',
                'work_id': 'authored-work', 'continuity': 'specified text',
                'version': 'ending', 'period': 'ending', 'state': 'available',
                'equipment': ['named equipment'], 'medium': 'novel',
                'related_entities': [{'entity_id': 'reference', 'name': 'Canon reference',
                                      'relation': 'opponent'}]}

    def test_standalone_and_story_dispatch_identical_research(self):
        actor = self.subject()
        standalone = {'purpose': 'rating', 'characters': [actor], 'mandatory_media_steps': []}
        story = {'purpose': 'writing', 'fighters': [copy.deepcopy(actor),
                 {'id': 'other', 'name': 'New opponent'}],
                 'constraints': {'ending': {'winner': 'other', 'result': 'Secret ending'}}}
        self.assertEqual(tasks_for(standalone)[0], tasks_for(story)[0])
        changed = copy.deepcopy(story)
        changed['fighters'][1] = {'id': 'changed', 'name': 'Replacement opponent'}
        changed['constraints']['ending'] = {'winner': 'solo', 'result': 'Different story'}
        self.assertEqual(tasks_for(story)[0], tasks_for(changed)[0])

    def test_both_dispatchers_provide_real_ordinary_research_routes(self):
        request = {'purpose': 'rating', 'characters': [self.subject()]}
        task = tasks_for(request)[0]
        plan = task['input']['research_plan']
        self.assertFalse(plan['search_executed'])
        self.assertEqual(len(plan['dimensions']), 9)
        self.assertEqual(plan['reading_order'], 'ending_backward_per_attribute')
        self.assertEqual({n['entity_id'] for n in plan['discovery_routes']['nodes']},
                         {'solo', 'reference'})
        self.assertEqual(task['input']['required_products'], ['report.md', 'sources.json'])
        with tempfile.TemporaryDirectory() as directory:
            result = run({'operation': 'plan', 'rating_request': request, 'output_dir': directory})
            self.assertFalse(result['semantic_work_executed'])
            self.assertTrue(Path(result['character_tasks'][0]['task_file']).is_file())

    def test_dispatch_references_manuals_without_copying_them_into_each_task(self):
        task=tasks_for({'purpose':'rating','characters':[self.subject()]})[0]
        reference=ROOT/'references/scaling-principles.md'
        self.assertIn(str(reference),task['instructions'])
        self.assertFalse(reference.read_text(encoding='utf-8-sig').strip() in task['instructions'],
                         'The dispatch copied an entire reference manual instead of referencing it.')

    def test_masked_scope_does_not_become_a_search_target(self):
        actor = self.subject()
        actor['related_entities'][0]['name'] = 'New opponent'
        request = {'purpose': 'writing', 'fighters': [actor, {'id': 'other', 'name': 'New opponent'}]}
        task = tasks_for(request)[0]
        self.assertIn('related_entities', task['input']['scope_needs_host_isolation'])
        self.assertEqual(len(task['input']['research_plan']['discovery_routes']['nodes']), 1)

    def test_canon_draft_labels_do_not_seed_research_but_authored_rules_survive(self):
        actor = self.subject()
        request = {'purpose': 'writing', 'fighters': [actor]}
        plain = tasks_for(request)[0]['input']
        actor.update(ratings={'输出': 'UNRESEARCHED_TIER'},
                     skills=[{'id': 'selected-to-win'}], persona={'goal': 'writer-selected'})
        self.assertEqual(tasks_for(request)[0]['input'], plain)
        actor['author_settings'] = {'技能': 'An explicit original-character rule'}
        authored = tasks_for(request)[0]['input']['character']
        self.assertEqual(authored['author_settings'], actor['author_settings'])
        self.assertEqual(authored['provided_author_material']['material']['ratings'], actor['ratings'])


if __name__ == '__main__':
    unittest.main()
