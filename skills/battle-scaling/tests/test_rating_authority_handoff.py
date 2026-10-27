"""Adversarial handoff regressions; all settings/reports are invented in temp dirs."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
import rating_pipeline as pipeline
from rating_preflight import _tier
from rating_fixtures import with_independent_ratings
from evidence import analyze_case
from test_rating_pipeline import story, materialized
from writing_battle import run as writing


def compact_artifacts(request, directory):
    from rule_profiles import resolve
    profile = resolve(request.get('ruleset_profile'), request.get('standard', 'wangba'))
    artifacts = []
    for index, subject in enumerate(request['fighters']):
        row = next(row for row in request['independent_ratings']
                   if row['character_id'] == subject['id'] and row['mode'] == request['mode'])
        packet = {'schema_version': 1, 'ruleset_profile': profile['id'],
                  'rules_fingerprint': pipeline.digest(pipeline._profile_key(profile)),
                  'character': {key: copy.deepcopy(subject.get(key)) for key in pipeline.SCOPE_FIELDS},
                  'rating': copy.deepcopy(row), 'sources': copy.deepcopy(request['sources']),
                  'report': '# Invented independent research report\n' + subject['name'] + '\n' +
                            '\n'.join(node['label'] + ': ' + node['reasoning']
                                      for node in [row['main_tier'], *row['dimensions'].values()])}
        packet['acceptance'] = {'status': 'accepted', 'reviewer': row['host_review']['reviewer'],
                                'reviewed_revision': row['completion_review']['revision'],
                                'content_sha256': pipeline.digest(packet)}
        path = Path(directory) / (str(index) + '-dossier.json')
        pipeline._write(path, packet)
        artifacts.append({'character_id': subject['id'], 'dossier_file': str(path)})
    return artifacts


class RatingAuthorityHandoffTests(unittest.TestCase):
    def test_all_bundled_vsb_plus_codes_and_display_names_are_accepted(self):
        for code in ('High 1-B+', '1-A+', 'High 1-A+'):
            with self.subTest(code=code):
                self.assertTrue(_tier(code, 'vsb'))
                self.assertTrue(_tier(code + ' (Bundled tier display)', 'vsb'))
        self.assertFalse(_tier('1-C+', 'vsb'))
        self.assertFalse(_tier('High 1-A++', 'vsb'))

    def test_same_attribute_conflict_cannot_be_ready(self):
        case = {'schema_version': 1, 'case_id': 'rating-conflict',
                'characters': [{'id': 'a', 'name': 'A', 'version': 'one', 'state': 'active', 'equipment': []}],
                'sources': [], 'anchors': [], 'edges': []}
        case = with_independent_ratings(case, modes=('integrated',))
        case['qualitative_claims'] = [{'id': 'contradiction', 'subject': 'a', 'attribute': 'main_tier',
            'reasoning': 'Invented incompatible selected conclusion.',
            'evidence_ids': ['independent-rating-fixture'],
            'assessment': {**case['independent_ratings'][0]['main_tier'], 'label': '标准爆楼'}}]
        result = analyze_case(case)
        self.assertEqual(result['rating_completion']['status'], 'needs_research')
        self.assertEqual(result['integrated_ratings'], [])
        self.assertTrue(any('assessment' in need for need in result['rating_completion']['needs']))
        case['qualitative_claims'][0]['assessment_role'] = 'candidate'
        self.assertEqual(analyze_case(case)['rating_completion']['status'], 'ready')
        # High showings and a different state are evidence, not another copy of
        # the selected integrated/current-state conclusion.
        claim = case['qualitative_claims'][0]
        claim.pop('assessment_role')
        claim['modes'] = ['highest']
        self.assertEqual(analyze_case(case)['rating_completion']['status'], 'ready')
        claim.pop('modes')
        claim['state'] = 'an earlier limited form'
        self.assertEqual(analyze_case(case)['rating_completion']['status'], 'ready')

    def test_stale_fighter_views_are_derived_from_accepted_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            request['fighters'][0]['ratings']['输出'] = 'obsolete weak draft'
            before = copy.deepcopy(request)
            result = writing(request)
            self.assertEqual(result['status'], 'ready_for_host')
            row = result['author_pack']['independent_ratings'][0]
            self.assertEqual(result['author_pack']['fighters'][0]['ratings']['输出'], row['dimensions']['输出']['label'])
            self.assertEqual(request, before)

    def test_compact_report_is_shared_by_pk_and_story_and_bound_to_current_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            request = story()
            artifacts = compact_artifacts(request, directory)
            assembled = pipeline.run({'operation': 'assemble', 'writing_request': request, 'artifacts': artifacts})
            self.assertEqual(assembled['status'], 'assembled', assembled.get('needs'))
            complete = assembled['writing_request']
            self.assertEqual(writing(complete)['status'], 'ready_for_host')
            pk = {'schema_version': 1, 'case_id': 'real-handoff', 'purpose': 'rating',
                  'standard': complete.get('standard', 'wangba'), 'mode': complete['mode'],
                  'characters': copy.deepcopy(complete['fighters']), 'sources': complete['sources'],
                  'independent_ratings': complete['independent_ratings'],
                  'rating_execution': complete['rating_execution'], 'anchors': [], 'edges': [],
                  'matchup': {'teams': [s['id'] for s in complete['fighters']], 'win_paths': []}}
            self.assertEqual(analyze_case(pk, pk['mode'])['matchup']['rating_preflight']['status'], 'ready')
            Path(artifacts[0]['dossier_file']).write_text('{}', encoding='utf-8')
            self.assertEqual(writing(complete)['status'], 'needs_independent_rating')
            self.assertEqual(analyze_case(pk, pk['mode'])['matchup']['verdict'], 'needs_independent_rating')

    def test_real_pk_declaration_alone_does_not_substitute_for_research(self):
        case = {'schema_version': 1, 'case_id': 'real-declaration',
                'characters': [{'id': who, 'name': who, 'version': 'one', 'state': 'active', 'equipment': []}
                               for who in ('a', 'b')], 'sources': [], 'anchors': [], 'edges': [],
                'matchup': {'teams': ['a', 'b'], 'win_paths': []}}
        case = with_independent_ratings(case, modes=('integrated',))
        case['fixture_kind'] = 'research'
        for source in case['sources']:
            source.update(origin='primary', locator='Invented stand-in for a real canon citation')
        result = analyze_case(case)['matchup']
        self.assertEqual(result['verdict'], 'needs_independent_rating')
        self.assertFalse(result['combat_analysis_started'])
        # An ordinary research CASE cannot opt out by changing source origin.
        for source in case['sources']:
            source['origin'] = 'synthetic'
        self.assertEqual(analyze_case(case)['matchup']['verdict'], 'needs_independent_rating')

    def test_explicit_partial_author_overlay_keeps_the_base_row_and_its_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            request = story()
            artifacts = compact_artifacts(request, directory)
            complete = pipeline.assemble({'writing_request': request, 'artifacts': artifacts})['writing_request']
            original_rows = copy.deepcopy(complete['independent_ratings'])
            complete['sources'].append({'id': 'author-change', 'origin': 'author_settings', 'access': 'provided',
                                         'locator': 'Invented author message: change only output in this story'})
            override = {'label': '标准爆楼', 'kind': 'tier', 'basis': 'exact', 'basis_type': 'author_settings',
                        'evidence_ids': ['author-change'],
                        'reasoning': 'The invented author explicitly sets only output; unknown other parameters are unchanged.'}
            complete['fighters'][0]['author_rating_overrides'] = {'输出': override}
            result = writing(complete)
            self.assertEqual(result['status'], 'ready_for_host', result['rating_preflight']['needs'])
            fighter = result['author_pack']['fighters'][0]
            self.assertEqual(fighter['ratings']['输出'], '标准爆楼')
            self.assertEqual(fighter['ratings']['体防'], original_rows[0]['dimensions']['体防']['label'])
            self.assertEqual(result['author_pack']['independent_ratings'], original_rows)
            self.assertEqual(fighter['rating_ref']['author_override_fields'], ['输出'])
            self.assertNotIn('host_review', override)
            for malformed in ({'main_tier': 'bare unreviewed label'}, {'输出': {**override, 'evidence_ids': ['missing']}}):
                changed = copy.deepcopy(complete)
                changed['fighters'][0]['author_rating_overrides'] = malformed
                self.assertEqual(writing(changed)['status'], 'needs_independent_rating')
            complete['sources'][-1]['status'] = 'withdrawn'
            self.assertEqual(writing(complete)['status'], 'needs_independent_rating')

    def test_nonwriting_assembly_reads_the_same_dossiers_without_eight_file_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            story_request = story()
            artifacts = compact_artifacts(story_request, directory)
            rating_request = {'purpose': 'rating', 'mode': story_request['mode'],
                              'characters': copy.deepcopy(story_request['fighters']),
                              'sources': copy.deepcopy(story_request['sources'])}
            result = pipeline.run({'operation': 'assemble', 'rating_request': rating_request, 'artifacts': artifacts})
            self.assertEqual(result['status'], 'assembled', result.get('needs'))
            self.assertIn('rating_request', result)
            self.assertNotIn('writing_request', result)
            gate = pipeline.verify_execution(result['rating_request'])
            self.assertEqual(gate['status'], 'ready')
            self.assertTrue(gate['dossier_contents_read_by_checker'])
            self.assertFalse(gate['local_analysis_verified'])
            self.assertFalse(gate['local_analysis_replayed'])

    def test_compact_acceptance_cannot_be_reimported_under_different_rule_content(self):
        with tempfile.TemporaryDirectory() as directory:
            request = story()
            artifacts = compact_artifacts(request, directory)
            path = Path(artifacts[0]['dossier_file'])
            document = pipeline._read(path)
            document['rules_fingerprint'] = '0' * 64
            document['acceptance']['content_sha256'] = pipeline.digest({k: v for k, v in document.items() if k != 'acceptance'})
            pipeline._write(path, document)
            result = pipeline.run({'operation': 'assemble', 'writing_request': request, 'artifacts': artifacts})
            self.assertEqual(result['status'], 'needs_independent_rating')
            self.assertTrue(any('rule' in need for need in result['needs']))

    def test_compact_calculations_reference_and_replay_existing_case_without_duplicate_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = materialized(root / 'existing')
            artifacts = compact_artifacts(request, root / 'compact')
            for compact, old in zip(artifacts, request['rating_execution']['artifacts']):
                path = Path(compact['dossier_file'])
                case_path = Path(old['artifact_dir']) / 'CASE.json'
                document = pipeline._read(path)
                document['calculation_case'] = {'path': str(case_path), 'sha256': pipeline.file_hash(case_path)}
                document['acceptance']['content_sha256'] = pipeline.digest({k: v for k, v in document.items() if k != 'acceptance'})
                pipeline._write(path, document)
            result = pipeline.assemble({'writing_request': story(), 'artifacts': artifacts})
            pipeline._ARTIFACT_CACHE.clear()
            gate = pipeline.verify_execution(result['writing_request'])
            self.assertTrue(gate['local_analysis_verified'])
            self.assertEqual(gate['replay_count_this_call'], 2)
            case_path.write_bytes(case_path.read_bytes() + b'\n')
            self.assertEqual(writing(result['writing_request'])['status'], 'needs_independent_rating')

    def test_one_handoff_hashes_a_shared_source_and_status_only_once_across_characters(self):
        from rating_fixtures import with_executed_ratings
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text, status = root / 'shared.txt', root / 'current.json'
            text.write_bytes(b'Invented independently reviewed source.')
            pipeline._write(status, {'status': 'current'})
            request = story()
            for source in request['sources']:
                source.update(path=str(text), status_file=str(status))
            complete = with_executed_ratings(request, root / 'artifacts')
            pipeline._ARTIFACT_CACHE.clear()
            with patch.object(pipeline, 'file_hash', wraps=pipeline.file_hash) as hashed:
                self.assertEqual(writing(complete)['status'], 'ready_for_host')
            paths = [Path(call.args[0]).resolve() for call in hashed.call_args_list]
            self.assertEqual(paths.count(text.resolve()), 1)
            self.assertEqual(paths.count(status.resolve()), 1)

    def test_normalized_text_contract_coordinates_and_one_hash_per_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, status = root / 'full.txt', root / 'status.json'
            path.write_bytes('第一行\n第二行证据\n'.encode('utf-8'))
            pipeline._write(status, {'status': 'current'})
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            sources = [{'id': str(i), 'path': str(path), 'status_file': str(status),
                        'text_sha256': expected, 'source_sha256': '0' * 64,
                        'quote': '第二行证据', 'start': 4, 'end': 9} for i in range(12)]
            with patch.object(pipeline, 'file_hash', wraps=pipeline.file_hash) as hashed:
                pipeline._sources_valid(sources, root)
            self.assertEqual(hashed.call_count, 2)
            bad = copy.deepcopy(sources[:1]); bad[0]['text_sha256'] = 'f' * 64
            with self.assertRaisesRegex(ValueError, 'hash'):
                pipeline._sources_valid(bad, root)
            bad = copy.deepcopy(sources[:1]); bad[0]['start'] = 0; bad[0]['end'] = 5
            with self.assertRaisesRegex(ValueError, 'quote|coordinate'):
                pipeline._sources_valid(bad, root)
            bad = copy.deepcopy(sources[:1]); bad[0]['locator'] = 'chapter-1 [0,5)'
            with self.assertRaisesRegex(ValueError, 'coordinate'):
                pipeline._sources_valid(bad, root)
            original = root / 'original.txt'
            original.write_bytes(b'Original uploaded bytes before normalization.')
            good = copy.deepcopy(sources[:1])
            good[0].update(source_path=str(original), source_sha256=pipeline.file_hash(original))
            pipeline._sources_valid(good, root)
            good[0]['source_sha256'] = 'f' * 64
            with self.assertRaisesRegex(ValueError, 'original.*hash'):
                pipeline._sources_valid(good, root)
            path.write_text('changed since last call', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash'):
                pipeline._sources_valid(sources, root)


if __name__ == '__main__':
    unittest.main()
