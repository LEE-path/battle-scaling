"""The fidelity helper checks declarations, never literary or source semantics."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from writing_fidelity import CANON_AXES, review_fidelity


def sample():
    profiles = []
    for fid in ('a', 'b'):
        rid = fid + '-scene'
        profiles.append({
            'fighter_id': fid, 'scope': 'Invented regression fixture, final state.',
            'references': [{'id': rid, 'locator': 'Synthetic fixture chapter 1',
                            'scene': 'A concrete fictional action and its aftermath.',
                            'kind': 'synthetic_original_scene'}],
            **{axis: {'observed_pattern': 'Specific fixture behavior.'} for axis in CANON_AXES},
            'support': {axis: [rid] for axis in CANON_AXES},
        })
    return {
        'canon_fidelity': True, 'operation': 'review', 'canon_profiles': profiles,
        'system_interactions': [{
            'id': 'collision', 'participants': ['a', 'b'],
            'contact_rule': 'The existing probe detects the already specified inscription.',
            'activation': 'A sends the existing probe after B inscribes a target.',
            'contestation': 'B can erase the inscription before the probe reaches it.',
            'consequence': 'A obtains the location only while the inscription remains.',
            'basis': 'creative_bridge', 'source_refs': ['a-scene', 'b-scene'],
            'setup_refs': ['fighters.a.skills.probe', 'fighters.b.skills.inscribe'],
        }],
        'draft': {'text': 'This deliberately unevaluated text may contradict all metadata.',
                  'beats': [{'id': 'probe', 'system_interactions': ['collision']},
                            {'id': 'answer', 'system_interactions': []}]},
    }


def check(request):
    return review_fidelity(request, {'a', 'b'}, {'probe', 'answer'})


class WritingFidelityTests(unittest.TestCase):
    def test_missing_or_false_opt_in_is_backwards_compatible(self):
        for request in ({}, {'canon_fidelity': False, 'canon_profiles': 'malformed'}):
            with self.subTest(request=request):
                result = check(request)
                self.assertFalse(result['requested'])
                self.assertEqual(result['errors'] + result['needs'] + result['revision_tasks'], [])

    def test_opt_in_requires_boolean_not_truthy_values(self):
        for value in ('true', 1, [], None, {}):
            with self.subTest(value=value):
                result = check({'canon_fidelity': value})
                self.assertTrue(any('boolean' in error for error in result['errors']))

    def test_complete_declarations_never_certify_semantics_or_sources(self):
        result = check(sample())
        self.assertTrue(result['requested'])
        self.assertEqual(result['errors'] + result['needs'] + result['revision_tasks'], [])
        for field in ('semantic_fidelity_verified', 'source_accuracy_verified',
                      'sources_read_verified', 'interaction_semantics_verified',
                      'prose_implementation_verified'):
            self.assertFalse(result[field])
        self.assertEqual(result['coverage']['system_interactions'][0]['declared_beats'], ['probe'])

    def test_input_is_not_mutated(self):
        request = sample()
        before = copy.deepcopy(request)
        check(request)
        self.assertEqual(request, before)

    def test_prepare_does_not_require_draft_bindings(self):
        request = sample()
        request['operation'] = 'prepare'
        del request['draft']
        result = check(request)
        self.assertEqual(result['revision_tasks'], [])
        self.assertFalse(result['coverage']['system_interactions'][0]['beat_declared'])

    def test_same_system_practice_can_have_no_interaction_plan(self):
        request = sample()
        request['system_interactions'] = []
        request['draft']['beats'][0]['system_interactions'] = []
        result = check(request)
        self.assertEqual(result['errors'] + result['needs'] + result['revision_tasks'], [])

    def test_missing_profiles_request_only_missing_fighters(self):
        request = sample()
        request['canon_profiles'].pop()
        request['system_interactions'][0]['source_refs'] = ['a-scene']
        result = check(request)
        self.assertEqual(result['errors'], [])
        self.assertTrue(any('fighter b' in need for need in result['needs']))
        self.assertFalse(any('fighter a.' in need for need in result['needs']))

    def test_nested_blank_axes_and_missing_scope_become_needs(self):
        request = sample()
        request['canon_profiles'][0]['voice'] = {'register': '   ', 'examples': [{}, []]}
        request['canon_profiles'][0]['scope'] = [' ']
        result = check(request)
        self.assertTrue(any('.voice ' in need for need in result['needs']))
        self.assertTrue(any('.scope ' in need for need in result['needs']))

    def test_each_axis_requires_traceable_declared_support(self):
        request = sample()
        del request['canon_profiles'][0]['support']['aftermath']
        result = check(request)
        self.assertTrue(any('.support.aftermath ' in need for need in result['needs']))

    def test_whitespace_source_locator_and_scene_are_missing(self):
        request = sample()
        request['canon_profiles'][0]['references'][0]['locator'] = '   '
        request['canon_profiles'][0]['references'][0]['scene'] = '\n\t'
        result = check(request)
        self.assertTrue(any('.locator ' in need for need in result['needs']))
        self.assertTrue(any('.scene ' in need for need in result['needs']))

    def test_unknown_or_duplicate_fighter_profile_is_invalid(self):
        for fid in ('unknown', 'a', [], {}):
            with self.subTest(fid=fid):
                request = sample()
                request['canon_profiles'][1]['fighter_id'] = fid
                self.assertTrue(check(request)['errors'])

    def test_reference_ids_are_globally_unique(self):
        request = sample()
        request['canon_profiles'][1]['references'][0]['id'] = 'a-scene'
        result = check(request)
        self.assertTrue(any('globally unique' in error for error in result['errors']))

    def test_unknown_and_duplicate_support_ids_are_invalid(self):
        for refs in (['missing'], ['a-scene', 'a-scene'], ['b-scene'], [{}]):
            with self.subTest(refs=refs):
                request = sample()
                request['canon_profiles'][0]['support']['decisions'] = refs
                self.assertTrue(check(request)['errors'])

    def test_malformed_profile_containers_do_not_crash(self):
        for key, value in (('canon_profiles', {}), ('system_interactions', {})):
            with self.subTest(key=key):
                request = sample()
                request[key] = value
                self.assertTrue(check(request)['errors'])
        for key, value in (('support', []), ('references', {})):
            with self.subTest(key=key):
                request = sample()
                request['canon_profiles'][0][key] = value
                self.assertTrue(check(request)['errors'])

    def test_interaction_participants_need_two_known_distinct_fighters(self):
        for participants in (['a'], ['a', 'a'], ['a', 'unknown'], ['a', {}]):
            with self.subTest(participants=participants):
                request = sample()
                request['system_interactions'][0]['participants'] = participants
                result = check(request)
                self.assertTrue(result['needs'] or result['errors'])

    def test_multiple_interactions_can_use_the_same_fighters(self):
        request = sample()
        another = copy.deepcopy(request['system_interactions'][0])
        another['id'] = 'second'
        request['system_interactions'].append(another)
        request['draft']['beats'][1]['system_interactions'] = ['second']
        result = check(request)
        self.assertEqual(result['errors'] + result['needs'] + result['revision_tasks'], [])

    def test_interaction_basis_requires_sources_or_setup_as_appropriate(self):
        for basis, missing in (('canon', 'source_refs'), ('creative_bridge', 'setup_refs'),
                               ('author_override', 'setup_refs')):
            with self.subTest(basis=basis):
                request = sample()
                request['system_interactions'][0]['basis'] = basis
                del request['system_interactions'][0][missing]
                self.assertTrue(any('.' + missing + ' ' in need for need in check(request)['needs']))

    def test_invalid_basis_or_unknown_source_reference_is_an_error(self):
        for key, value in (('basis', 'whatever'), ('basis', {}), ('source_refs', ['unknown'])):
            with self.subTest(key=key, value=value):
                request = sample()
                request['system_interactions'][0][key] = value
                self.assertTrue(check(request)['errors'])

    def test_missing_interaction_mechanism_becomes_need(self):
        request = sample()
        request['system_interactions'][0]['contestation'] = {'response': ' '}
        self.assertTrue(any('.contestation ' in need for need in check(request)['needs']))

    def test_duplicate_interaction_id_is_invalid(self):
        request = sample()
        request['system_interactions'].append(copy.deepcopy(request['system_interactions'][0]))
        self.assertTrue(any('.id must be unique' in error for error in check(request)['errors']))

    def test_no_prose_mention_can_replace_an_interaction_binding(self):
        request = sample()
        request['draft']['text'] = 'collision collision collision'
        request['draft']['beats'][0]['system_interactions'] = []
        result = check(request)
        self.assertEqual(len(result['revision_tasks']), 1)
        self.assertFalse(result['coverage']['system_interactions'][0]['beat_declared'])

    def test_interaction_can_span_multiple_beats(self):
        request = sample()
        request['draft']['beats'][1]['system_interactions'] = ['collision']
        result = check(request)
        self.assertEqual(result['revision_tasks'], [])
        self.assertEqual(result['coverage']['system_interactions'][0]['declared_beats'], ['probe', 'answer'])

    def test_unknown_duplicate_or_malformed_binding_is_invalid(self):
        for tags in (['unknown'], ['collision', 'collision'], 'collision', [{}]):
            with self.subTest(tags=tags):
                request = sample()
                request['draft']['beats'][0]['system_interactions'] = tags
                self.assertTrue(check(request)['errors'])

    def test_unknown_beat_does_not_fulfill_interaction_coverage(self):
        request = sample()
        request['draft']['beats'][0]['id'] = 'undeclared'
        result = check(request)
        self.assertTrue(result['errors'])
        self.assertTrue(result['revision_tasks'])

    def test_malformed_draft_beats_do_not_crash(self):
        request = sample()
        request['draft']['beats'] = {}
        result = check(request)
        self.assertTrue(result['errors'])
        self.assertTrue(result['revision_tasks'])


if __name__ == '__main__':
    unittest.main()
