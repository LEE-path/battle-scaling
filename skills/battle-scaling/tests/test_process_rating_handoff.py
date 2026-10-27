"""Direct trace, ordinary PK and story consume the same real temporary dossier."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
import battle
import combat_trace
import rating_pipeline as pipeline
from evidence import analyze_case
from rating_fixtures import with_independent_ratings
from test_rating_pipeline import materialized, story
from test_rating_authority_handoff import compact_artifacts
from writing_battle import run as writing


def process_input(complete):
    return {'mode': complete['mode'], 'standard': complete.get('standard', 'wangba'),
            'sources': copy.deepcopy(complete['sources']),
            'rating_subjects': [{key: copy.deepcopy(f.get(key)) for key in pipeline.SCOPE_FIELDS}
                                for f in complete['fighters']],
            'independent_ratings': copy.deepcopy(complete['independent_ratings']),
            'rating_execution': copy.deepcopy(complete['rating_execution']),
            'actors': [{'id': f['id'], 'initial': {'state': 'active'},
                        'ratings': {'输出': 'stale unreviewed display'}, 'main_tier': 'stale draft'}
                       for f in complete['fighters']], 'steps': []}


def pk_input(complete, presentation='overview'):
    process = process_input(complete)
    return {'schema_version': 1, 'case_id': 'shared-real-product-test',
            'mode': process['mode'], 'standard': process['standard'],
            'characters': copy.deepcopy(complete['fighters']), 'sources': process['sources'],
            'independent_ratings': process['independent_ratings'], 'rating_execution': process['rating_execution'],
            'anchors': [], 'edges': [], 'matchup': {'presentation': presentation, 'win_paths': [],
                'mode_processes': {process['mode']: {'actors': process['actors'], 'steps': []}}}}


class ProcessRatingHandoffTests(unittest.TestCase):
    def test_direct_process_cannot_execute_a_real_declaration_without_research_products(self):
        request = with_independent_ratings({'actors': [{'id': 'a'}, {'id': 'b'}], 'sources': [], 'steps': []})
        request['fixture_kind'] = 'research'
        with patch.object(combat_trace, '_Trace') as trace:
            result = combat_trace.run(request)
        self.assertEqual(result['status'], 'needs_independent_rating')
        self.assertFalse(result['combat_analysis_started'])
        trace.assert_not_called()

    def test_direct_process_overview_and_story_resolve_the_same_authoritative_values(self):
        with tempfile.TemporaryDirectory() as directory:
            request = story()
            artifacts = compact_artifacts(request, directory)
            complete = pipeline.assemble({'writing_request': request, 'artifacts': artifacts})['writing_request']
            process = process_input(complete)
            before = copy.deepcopy(process)
            with patch.object(combat_trace, '_Trace', wraps=combat_trace._Trace) as trace:
                direct = combat_trace.run(process)
            self.assertEqual(direct['rating_preflight']['status'], 'ready')
            expected = complete['independent_ratings'][0]['dimensions']['输出']['label']
            self.assertEqual(trace.call_args.args[0]['actors'][0]['ratings']['输出'], expected)
            overview = analyze_case(pk_input(complete), complete['mode'])
            story_result = writing(complete)
            self.assertEqual(direct['rating_subjects'][0]['ratings'], overview['characters'][0]['ratings'])
            self.assertEqual(direct['rating_subjects'][0]['ratings'], story_result['author_pack']['fighters'][0]['ratings'])
            self.assertEqual(process, before)
            Path(artifacts[0]['dossier_file']).write_text('{}', encoding='utf-8')
            with patch.object(combat_trace, '_Trace') as trace:
                self.assertEqual(combat_trace.run(process)['status'], 'needs_independent_rating')
            trace.assert_not_called()
            # A fixture label never discards an actual supplied execution.
            process['fixture_kind'] = 'synthetic'
            with patch.object(combat_trace, '_Trace') as trace:
                self.assertEqual(combat_trace.run(process)['status'], 'needs_independent_rating')
            trace.assert_not_called()

    def test_evidence_process_passes_execution_and_reuses_one_cold_replay_per_subject(self):
        with tempfile.TemporaryDirectory() as directory:
            complete = materialized(directory)
            request = pk_input(complete, 'process')
            pipeline._ARTIFACT_CACHE.clear()
            with patch.object(battle, 'compute_case', wraps=battle.compute_case) as compute, \
                    patch.object(pipeline, 'file_hash', wraps=pipeline.file_hash) as hashed:
                result = analyze_case(request, complete['mode'])['matchup']['process']
            self.assertEqual(result['rating_preflight']['status'], 'ready')
            self.assertEqual(result['rating_execution']['status'], 'ready')
            self.assertEqual(compute.call_count, 2)
            report = Path(complete['rating_execution']['artifacts'][0]['artifact_dir']) / 'report.md'
            self.assertEqual([Path(c.args[0]).resolve() for c in hashed.call_args_list].count(report.resolve()), 1)

    def test_overview_and_process_handoff_use_the_actual_selected_analysis_profile(self):
        from rule_profiles import resolve
        with tempfile.TemporaryDirectory() as directory:
            complete = materialized(directory)
            for presentation in ('overview', 'process'):
                request = pk_input(complete, presentation)
                result = analyze_case(request, complete['mode'], profile=resolve('legacy-2024-2025'))['matchup']
                self.assertEqual(result['verdict'], 'needs_independent_rating')
                self.assertTrue(any('rule' in need for need in result['rating_preflight']['needs']))

    def test_process_cli_rejects_declaration_and_explicit_rule_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            complete = materialized(root / 'artifacts')
            for missing, profile in ((True, None), (False, None), (False, 'legacy-2024-2025')):
                request = process_input(complete)
                if missing:
                    request.pop('rating_execution')
                source, output = root / 'input.json', root / 'output.json'
                pipeline._write(source, request)
                command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/battle.py'), 'process',
                           '--input', str(source), '--output', str(output)]
                if profile:
                    command += ['--ruleset-profile', profile]
                proc = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                result = json.loads(output.read_text(encoding='utf-8'))
                if missing or profile:
                    self.assertEqual(result['status'], 'needs_independent_rating')
                    self.assertFalse(result['combat_analysis_started'])
                else:
                    self.assertEqual(result['rating_execution']['status'], 'ready')
                    self.assertEqual(result['rating_subjects'][0]['ratings']['输出'],
                                     complete['independent_ratings'][0]['dimensions']['输出']['label'])


if __name__ == '__main__':
    unittest.main()
