"""Executed standalone files, not accepted flags, precede authored combat.

All sources and reports here are explicitly authored synthetic test settings.
Tests run the actual analysis/export/import path and never patch its gates.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from rating_pipeline import run, verify_execution, _read, _write, file_hash, HASH_FIELDS
from rating_fixtures import with_executed_ratings, with_independent_ratings
from writing_battle import run as writing
from rating_fixtures import legacy_analyze_case as analyze_case  # Explicit legacy regression
from rating_fixtures import legacy_compute_case as compute_case


def story():
    request = _read(ROOT / 'assets/cases/writing-battle-synthetic.json')
    request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
    request['operation'] = 'prepare'
    request.pop('draft', None)
    request.pop('rating_execution', None)
    return request


def materialized(directory):
    return with_executed_ratings(story(), directory)


def artifact_path(request, name, index=0):
    return Path(request['rating_execution']['artifacts'][index]['artifact_dir']) / name


def reaccept(directory):
    row = _read(directory / 'rating.json')
    acceptance = {'status': 'accepted', 'reviewer': row['host_review']['reviewer'],
                  'reviewed_revision': row['completion_review']['revision']}
    acceptance.update({field: file_hash(directory / name) for name, field in HASH_FIELDS.items()})
    _write(directory / 'host-acceptance.json', acceptance)


class RatingPipelineTests(unittest.TestCase):
    def test_accepted_complete_json_without_executed_products_returns_tasks(self):
        request = story()
        result = writing(request)
        self.assertEqual(result['status'], 'needs_independent_rating')
        self.assertEqual(result['rating_preflight']['status'], 'needs_research')
        self.assertEqual([t['character_id'] for t in result['rating_execution']['character_tasks']],
                         [s['id'] for s in request['fighters']])
        self.assertFalse(result['narrative_generated'])

    def test_plan_writes_actual_isolated_task_inputs_without_story_or_other_actor(self):
        request = story()
        request['constraints']['ending']['result'] = 'SECRET_AUTHOR_ENDING'
        with tempfile.TemporaryDirectory() as directory:
            result = run({'operation': 'plan', 'writing_request': request, 'output_dir': directory})
            self.assertEqual(result['status'], 'needs_host_scope_isolation')
            self.assertFalse(result['semantic_work_executed'])
            for task in result['character_tasks']:
                data = _read(task['input_file'])
                self.assertTrue(Path(task['task_file']).is_file())
                self.assertEqual(data['character']['id'], task['character_id'])
                serialized = json.dumps(data, ensure_ascii=False)
                self.assertNotIn('SECRET_AUTHOR_ENDING', serialized)
                self.assertNotIn('constraints', data)
                for subject in request['fighters']:
                    if subject['id'] != task['character_id']:
                        self.assertNotIn(subject['name'], serialized)
                self.assertEqual(data['mandatory_media_steps'], [])

    def test_own_author_material_is_preserved_and_outcome_opponent_do_not_bias_task(self):
        from rating_pipeline import tasks_for
        request = story()
        first = tasks_for(request)[0]['input']
        supplied = first['character']['provided_author_material']
        self.assertEqual(supplied['origin'], 'author_settings')
        self.assertEqual(supplied['material']['skills'], request['fighters'][0]['skills'])
        self.assertEqual(supplied['material']['ratings'], request['fighters'][0]['ratings'])
        changed = copy.deepcopy(request)
        changed['fighters'][1] = {'id': 'unrelated', 'name': 'Another opponent', 'version': 'different',
                                  'state': 'different', 'equipment': ['different']}
        changed['constraints']['ending'] = {'winner': 'unrelated', 'result': 'opposite ending'}
        self.assertEqual(tasks_for(changed)[0]['input'], first)

    def test_real_full_files_import_and_replay_are_ready_without_semantic_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            before = copy.deepcopy(request)
            result = writing(request)
            self.assertEqual(result['status'], 'ready_for_host')
            self.assertEqual(result['rating_execution']['status'], 'ready')
            self.assertTrue(result['rating_execution']['local_analysis_verified'])
            self.assertFalse(result['rating_execution']['local_analysis_replayed'])
            self.assertTrue(result['rating_preflight']['dossier_contents_read_by_checker'])
            self.assertFalse(result['rating_execution']['semantic_rating_verified'])
            self.assertEqual(request, before)

    def test_each_real_product_hash_and_presence_are_bound(self):
        for filename in HASH_FIELDS:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                request = materialized(directory)
                path = artifact_path(request, filename)
                path.write_bytes(path.read_bytes() + b'\n')
                result = writing(request)
                self.assertEqual(result['status'], 'needs_independent_rating')
                self.assertTrue(result['rating_execution']['character_tasks'])
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            artifact_path(request, 'analysis.json').unlink()
            self.assertEqual(writing(request)['status'], 'needs_independent_rating')

    def test_forged_hashes_cannot_substitute_for_reproducible_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            out = artifact_path(request, 'analysis.json').parent
            analysis = _read(out / 'analysis.json')
            analysis['qualitative_claims'][0]['reasoning'] = 'Forged analyzed conclusion'
            _write(out / 'analysis.json', analysis)
            reaccept(out)
            supplied = [{'character_id': item['character_id'], 'artifact_dir': item['artifact_dir']}
                        for item in request['rating_execution']['artifacts']]
            result = run({'operation': 'assemble', 'writing_request': story(), 'artifacts': supplied})
            self.assertEqual(result['status'], 'needs_independent_rating')
            self.assertTrue(any('reproducible' in need for need in result['needs']))

    def test_missing_participant_cannot_import_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            artifacts = request['rating_execution']['artifacts'][:1]
            result = run({'operation': 'assemble', 'writing_request': story(), 'artifacts': artifacts})
            self.assertEqual(result['status'], 'needs_independent_rating')
            request['rating_execution']['artifacts'] = artifacts
            self.assertEqual(writing(request)['status'], 'needs_independent_rating')

    def test_version_mode_standard_equipment_and_import_changes_invalidate(self):
        changes = [lambda r: r.update(mode='highest'), lambda r: r.update(standard='vsb'),
                   lambda r: r['fighters'][0].update(version='a different version'),
                   lambda r: r['fighters'][0].update(equipment=['new weapon']),
                   lambda r: r['independent_ratings'][0]['main_tier'].update(label='标准爆楼'),
                   lambda r: r['sources'][0].update(locator='different source text')]
        with tempfile.TemporaryDirectory() as directory:
            original = materialized(directory)
            for mutate in changes:
                request = copy.deepcopy(original)
                mutate(request)
                self.assertEqual(writing(request)['status'], 'needs_independent_rating')

    def test_current_file_withdrawal_and_global_withdrawal_invalidate_old_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            request['rating_status'] = {'status': 'withdrawn'}
            self.assertEqual(writing(request)['status'], 'needs_independent_rating')
            request.pop('rating_status')
            path = artifact_path(request, 'host-acceptance.json')
            acceptance = _read(path)
            acceptance['status'] = 'withdrawn'
            _write(path, acceptance)
            self.assertEqual(writing(request)['status'], 'needs_independent_rating')
            artifacts = request['rating_execution']['artifacts']
            result = run({'operation': 'assemble', 'writing_request': story(), 'artifacts': artifacts})
            self.assertEqual(result['status'], 'needs_independent_rating')

    def test_actual_local_source_text_and_source_retraction_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            text = directory / 'author-source.txt'
            text.write_text('Explicit independent authored settings for the synthetic source.', encoding='utf-8')
            request = story()
            request['sources'][0]['path'] = str(text)
            request = with_executed_ratings(request, directory / 'artifacts')
            self.assertEqual(writing(request)['status'], 'ready_for_host')
            text.write_text('Source withdrawn by its author.', encoding='utf-8')
            self.assertEqual(writing(request)['status'], 'needs_independent_rating')
        with tempfile.TemporaryDirectory() as directory:
            request = story()
            request['sources'][0]['status'] = 'retracted'
            with self.assertRaisesRegex(AssertionError, 'withdrawn'):
                with_executed_ratings(request, directory)

    def test_valid_old_files_can_be_read_and_reimported_without_new_research(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            artifacts = [{'character_id': item['character_id'], 'artifact_dir': item['artifact_dir']}
                         for item in request['rating_execution']['artifacts']]
            result = run({'operation': 'assemble', 'writing_request': story(), 'artifacts': artifacts})
            self.assertEqual(result['status'], 'assembled')
            self.assertEqual(writing(result['writing_request'])['status'], 'ready_for_host')

    def test_both_standards_and_all_three_evidence_modes_execute_the_same_pipeline(self):
        for standard in ('wangba', 'vsb'):
            for mode in ('normal', 'highest', 'lowball'):
                with self.subTest(standard=standard, mode=mode):
                    request = story()
                    request.update(standard=standard, mode=mode)
                    request = with_independent_ratings(request, writing=True)
                    self.assertEqual(writing(request)['status'], 'ready_for_host')

    def test_canonical_reference_characters_are_allowed_in_single_target_analysis(self):
        from battle import compute_case, export_case
        from evidence import analyze_case
        from rule_profiles import resolve, snapshot_content
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            out = artifact_path(request, 'CASE.json').parent
            case = _read(out / 'CASE.json')
            case['characters'].append({'id': 'canonical-reference', 'name': 'Canonical reference',
                                       'version': 'same setting', 'state': 'comparison state', 'equipment': []})
            report = (out / 'report.md').read_text(encoding='utf-8')
            original = Path(directory) / 'reference-case-input.json'
            _write(original, case)
            profile = resolve(case['ruleset_profile'], case['standard'])
            computed = compute_case(case, 'normal', profile)
            analysis = analyze_case(computed, 'normal', profile)
            analysis['rule_snapshot'] = snapshot_content(profile, computed.get('computations', []))
            export_case(analysis, out, original, original.read_bytes())
            (out / 'report.md').write_text(report, encoding='utf-8')
            reaccept(out)
            result = run({'operation': 'assemble', 'writing_request': story(),
                          'artifacts': request['rating_execution']['artifacts']})
            self.assertEqual(result['status'], 'assembled')
            self.assertEqual(writing(result['writing_request'])['status'], 'ready_for_host')

    def test_same_rule_bytes_can_be_reused_after_install_path_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            out = artifact_path(request, 'analysis.json').parent
            analysis = _read(out / 'analysis.json')
            snapshot = _read(out / 'rules-snapshot.json')
            for profile in (analysis['ruleset_profile'], snapshot['profile'],
                            analysis['rule_snapshot']['profile']):
                for key in ('profile_configuration', 'finite_rule_snapshot'):
                    profile[key]['path'] = 'X:/previous-install/' + Path(profile[key]['path']).name
            _write(out / 'analysis.json', analysis)
            _write(out / 'rules-snapshot.json', snapshot)
            reaccept(out)
            result = run({'operation': 'assemble', 'writing_request': story(),
                          'artifacts': request['rating_execution']['artifacts']})
            self.assertEqual(result['status'], 'assembled')
            self.assertEqual(writing(result['writing_request'])['status'], 'ready_for_host')
            analysis['ruleset_profile']['finite_rule_snapshot']['sha256'] = '0' * 64
            _write(out / 'analysis.json', analysis)
            reaccept(out)
            result = run({'operation': 'assemble', 'writing_request': story(),
                          'artifacts': request['rating_execution']['artifacts']})
            self.assertEqual(result['status'], 'needs_independent_rating')

    def test_empty_case_or_missing_dimension_derivations_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            out = artifact_path(request, 'CASE.json').parent
            case = _read(out / 'CASE.json')
            case['qualitative_claims'] = []
            _write(out / 'CASE.json', case)
            reaccept(out)
            result = run({'operation': 'assemble', 'writing_request': story(),
                          'artifacts': request['rating_execution']['artifacts']})
            self.assertEqual(result['status'], 'needs_independent_rating')
            self.assertTrue(any('all nine' in need for need in result['needs']))


if __name__ == '__main__':
    unittest.main()
