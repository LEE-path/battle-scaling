"""Integrated grading is not a renamed normal filter or numerical extremum.

All characters, facts and authored acceptances here are invented test inputs.
The real compute/export/import/gate path runs; no semantic review is simulated.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from battle import compute_case, render_report
from combat_trace import run as process
from evidence import analyze_case
from hax_gate import build_checks
from high_tier import analyze as high
from rating_fixtures import with_independent_ratings, with_executed_ratings
from rating_pipeline import tasks_for, verify_execution
from rating_preflight import review
from research import plan
from writing_battle import run as writing


def packet():
    return {'schema_version': 1, 'case_id': 'integrated-authored-regression',
        'characters': [{'id': 'a', 'name': 'Invented A', 'version': 'one',
                        'state': 'final-active', 'equipment': []}],
        'sources': [{'id': 's', 'title': 'Invented complete setting', 'origin': 'synthetic',
                     'access': 'provided', 'locator': 'synthetic definitions, not canon'}],
        'anchors': [
            {'id': name, 'subject': 'a', 'attribute': 'attack_energy', 'kind': kind,
             'quantity': {'value': value, 'unit': 'J'}, 'evidence_ids': ['s'],
             'modes': [tag], 'context': context}
            for name, kind, value, tag, context in (
                ('typical', 'repeated_feat', 2000, 'normal', 'ordinary action'),
                ('peak', 'outlier', 1e12, 'highest', 'exceptional showing requires assessment'),
                ('low', 'anti_feat', 20, 'lowball', 'fatigue, not an automatic final-state cap'),
                ('setting', 'statement', 1e10, 'highest', 'reliable setting must be compared'))],
        'edges': []}


def rated():
    request = with_independent_ratings(packet(), modes=('integrated',))
    request.pop('mode', None)  # Exercise production API/CLI defaults.
    return request


class IntegratedRatingTests(unittest.TestCase):
    def test_default_keeps_all_contexts_without_automatic_extremum(self):
        result = analyze_case(packet())
        self.assertEqual(list(result['modes']), ['integrated'])
        rows = result['modes']['integrated']['conclusions']
        self.assertEqual({row['anchor_id'] for row in rows}, {'typical', 'peak', 'low', 'setting'})
        self.assertTrue(all(row['is_character_main_tier'] is False for row in rows))
        self.assertEqual(result['integrated_ratings'], [])
        self.assertEqual(result['rating_completion']['status'], 'needs_research')
        self.assertFalse(result['semantic_rating_verified'])

    def test_host_integrated_selection_is_the_single_main_tier(self):
        request = rated()
        row = request['independent_ratings'][0]
        row['main_tier'].update(label='指数塔', basis='estimate',
            reasoning='Invented full-scope structure and outer relationships select this tier, not a local physical floor.')
        row['completion_review']['candidates'] = [{
            'id': 'whole-outer-structure', 'affects': ['main_tier'],
            'disposition': 'adopted', 'impact': 'material',
            'reasoning': 'The authored setting supplies and relates the complete outer object.',
            'evidence_ids': ['independent-rating-fixture']}]
        result = analyze_case(request)
        self.assertEqual(result['rating_completion']['status'], 'ready')
        self.assertEqual(len(result['integrated_ratings']), 1)
        self.assertEqual(result['integrated_ratings'][0]['main_tier']['label'], '指数塔')
        report = render_report(result)
        self.assertIn('Invented A量级：指数塔', report)
        self.assertIn('| 体防 |', report)
        self.assertNotIn('## 历史最高复算', report)

    def test_old_mode_packets_are_readable_but_cannot_open_integrated_admission(self):
        request = with_independent_ratings(packet(), modes=('normal', 'highest', 'lowball'))
        integrated = analyze_case(request)
        self.assertEqual(integrated['integrated_ratings'], [])
        self.assertEqual(integrated['rating_completion']['status'], 'needs_research')
        legacy = analyze_case(request, 'all')
        self.assertTrue(legacy['legacy_mode'])
        self.assertFalse(legacy['legacy_is_integrated_reassessment'])
        self.assertEqual(list(legacy['modes']), ['normal', 'highest', 'lowball'])
        self.assertIn('历史三态复算', render_report(legacy))

    def test_local_floor_or_open_material_outer_relation_prevents_completion(self):
        for mutate in (
            lambda row: row['completion_review'].update(selected_basis='local_floor'),
            lambda row: row['completion_review']['candidates'].append({
                'id': 'outer', 'affects': ['main_tier'], 'disposition': 'open',
                'impact': 'material', 'reasoning': 'Still unassessed beyond the calculated substructure.',
                'evidence_ids': ['independent-rating-fixture']})):
            request = rated()
            mutate(request['independent_ratings'][0])
            result = analyze_case(request)
            self.assertEqual(result['rating_completion']['status'], 'needs_research')
            self.assertEqual(result['integrated_ratings'], [])

    def test_current_integrated_acceptance_can_be_withdrawn(self):
        request = rated()
        gate = review(request['characters'], request['independent_ratings'], request['sources'],
                      rating_status={'status': 'current', 'accepted_complete_integrated_ratings': False})
        self.assertEqual(gate['status'], 'needs_research')
        self.assertFalse(gate['legacy_mode'])

    def test_standalone_reference_character_does_not_need_a_second_full_card(self):
        request = rated()
        request['rating_target_id'] = 'a'
        request['characters'].append({'id': 'reference', 'name': 'Related scaling reference',
            'version': 'one', 'state': 'active', 'equipment': []})
        result = analyze_case(request)
        self.assertEqual(result['rating_completion']['status'], 'ready')
        self.assertEqual(result['rating_completion']['rating_subject_ids'], ['a'])
        request['matchup'] = {'teams': ['a', 'reference'], 'win_paths': []}
        self.assertEqual(analyze_case(request)['matchup']['verdict'], 'needs_independent_rating')

    def test_unknown_transfer_requires_explicit_premises_and_false_still_blocks(self):
        request = packet()
        request['characters'].append({'id': 'b', 'name': 'B', 'version': 'one', 'state': 'final-active', 'equipment': []})
        request['edges'] = [{'id': 'transfer', 'from': {'subject': 'a', 'attribute': 'attack_energy'},
            'to': {'subject': 'b', 'attribute': 'durability'}, 'relation': 'tanked',
            'evidence_ids': ['s'], 'conditions': {'effective_hit': True}}]
        first = analyze_case(request)['modes']['integrated']
        self.assertFalse(any(row['subject'] == 'b' for row in first['conclusions']))
        request['edges'][0]['assumptions'] = ['Body rather than equipment receives the measured attack at its actual scale.']
        conditional = analyze_case(request)['modes']['integrated']
        self.assertTrue(any(row['subject'] == 'b' and row['status'] == 'conditional' for row in conditional['conclusions']))
        request['edges'][0]['conditions']['body_only'] = False
        blocked = analyze_case(request)['modes']['integrated']
        self.assertFalse(any(row['subject'] == 'b' for row in blocked['conclusions']))

    def test_high_computation_tagged_with_old_lens_is_recomputed_for_integrated(self):
        request = packet()
        request['computations'] = [{'id': 'outer-math', 'type': 'high', 'modes': ['highest'],
            'request': {'kind': 'ordinal', 'expression': 'tower(omega,omega)', 'axioms': ['ZFC']}}]
        computed = compute_case(request)
        self.assertEqual(computed['computations'][0]['mode'], 'integrated')
        result = analyze_case(computed)
        self.assertEqual(len(result['modes']['integrated']['high_results']), 1)
        self.assertFalse(result['modes']['integrated']['high_results'][0]['output']['legacy_mode'])

    def test_standards_remain_independent(self):
        request = rated()
        request['standard'] = 'vsb'
        request = with_independent_ratings(request, modes=('integrated',), standards=('vsb',))
        request.pop('mode', None)
        result = analyze_case(request)
        self.assertEqual(result['standard'], 'vsb')
        self.assertEqual(result['integrated_ratings'][0]['main_tier']['label'], '9-B (Wall level)')
        self.assertNotIn('peak', {row['anchor_id'] for row in result['modes']['integrated']['conclusions']})

    def test_research_default_is_one_rating_with_three_evidence_contexts(self):
        result = plan({'target': {'name': 'A'}})
        self.assertEqual(result['modes'], ['integrated'])
        self.assertEqual(result['performance_contexts'], ['high_showing', 'typical_showing', 'low_showing'])
        self.assertTrue(any(task['polarity'] == 'counter' for task in result['tasks']))

    def test_hax_candidates_keep_both_ceilings_and_known_failures(self):
        from test_hax_policy import packet as hax_packet
        request = hax_packet()
        request.pop('mode')
        entries = [{'id': 'control', 'modes': ['highest'], 'request': request}]
        outputs = build_checks(entries, request['sources'], 'integrated')
        self.assertEqual(outputs['control']['status'], 'supported_by_packet')
        self.assertFalse(outputs['control']['legacy_mode'])
        request['target_level']['rank'] = 4
        outputs = build_checks(entries, request['sources'], 'integrated')
        self.assertEqual(outputs['control']['status'], 'blocked')
        self.assertFalse(outputs['control']['within_world_ceiling'])

    def test_integrated_process_executes_only_after_matching_full_ratings(self):
        from test_combat_trace import actor, attack, fact
        request = {'mode': 'integrated',
            'sources': [{'id': 's-game', 'origin': 'synthetic', 'access': 'provided',
                         'locator': 'synthetic HP and action definitions'}],
            'actors': [actor('a'), actor('b')],
            'steps': [{'id': 'first', 'actions': [attack()]}],
            'victory': {'defeated_states': ['incapacitated']}}
        request = with_independent_ratings(request, modes=('integrated',))
        request.pop('mode')
        result = process(request)
        self.assertEqual(result['terminal']['winner'], 'a')
        self.assertEqual(result['rating_preflight']['mode'], 'integrated')
        self.assertFalse(result['canon_evidence'])
        for row in request['independent_ratings']:
            row['mode'] = 'normal'
        self.assertEqual(process(request)['status'], 'needs_independent_rating')

    def test_default_cli_outputs_one_integrated_report(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'input.json'
            source.write_text(json.dumps(rated(), ensure_ascii=False), encoding='utf-8')
            proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/battle.py'),
                'analyze', '--input', str(source), '--output', str(directory / 'run')],
                capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            output = json.loads((directory / 'run/analysis.json').read_text(encoding='utf-8'))
            self.assertEqual(list(output['modes']), ['integrated'])
            self.assertEqual(len(output['integrated_ratings']), 1)
            self.assertIn('综合评定', (directory / 'run/report.md').read_text(encoding='utf-8'))

    def test_story_plan_defaults_to_real_integrated_standalone_tasks(self):
        request = json.loads((ROOT / 'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))
        request.pop('mode', None)
        tasks = tasks_for(request)
        self.assertTrue(all(task['input']['mode'] == 'integrated' for task in tasks))
        request.pop('rating_execution', None)
        result = writing(request)
        self.assertEqual(result['status'], 'needs_independent_rating')
        self.assertFalse(result['narrative_generated'])

    def test_actual_integrated_story_artifacts_are_replayed_and_imported(self):
        request = json.loads((ROOT / 'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))
        request.update(mode='integrated', operation='prepare')
        request.pop('rating_execution', None)
        request.pop('draft', None)
        complete = with_independent_ratings(request, writing=True, modes=('integrated',))
        result = writing(complete)
        self.assertEqual(result['status'], 'ready_for_host')
        self.assertEqual(result['rating_preflight']['mode'], 'integrated')
        self.assertFalse(result['rating_preflight']['semantic_rating_verified'])
        altered = copy.deepcopy(complete)
        altered['mode'] = 'normal'
        self.assertEqual(verify_execution(altered)['status'], 'needs_research')

    def test_pre_upgrade_static_artifact_remains_explicit_legacy_only(self):
        from rating_pipeline import digest, _profile_key
        from rule_profiles import resolve
        asset = ROOT / 'assets/cases/writing-fidelity-synthetic.json'
        original_bytes = asset.read_bytes()
        request = json.loads(original_bytes.decode('utf-8'))
        request['mode'] = 'normal'
        # Keep the immutable static replay contract: old rule acceptance cannot
        # silently become current merely to make a legacy fixture pass.
        static = writing(request)
        profile = resolve(request.get('ruleset_profile'), request.get('standard', 'wangba'))
        if request['rating_execution']['rules_fingerprint'] != digest(_profile_key(profile)):
            self.assertEqual(static['status'], 'needs_independent_rating')
            self.assertTrue(any('rule source/profile has changed' in need for need in static['rating_preflight']['needs']))
        else:
            self.assertEqual(static['status'], 'structure_checked')
        self.assertEqual(asset.read_bytes(), original_bytes)
        # The current-mode behavior is exercised with newly materialized,
        # explicitly invented temporary products, never by editing that archive.
        request = with_executed_ratings(request)
        result = writing(request)
        self.assertEqual(result['status'], 'structure_checked')
        self.assertTrue(result['legacy_mode'])
        self.assertFalse(result['legacy_is_integrated_reassessment'])
        request.pop('mode')
        self.assertEqual(writing(request)['status'], 'needs_independent_rating')


if __name__ == '__main__':
    unittest.main()
