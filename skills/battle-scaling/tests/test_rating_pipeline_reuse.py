"""Reuse only private, current-byte-bound replays; preserve all admission gates."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
import battle
import rating_pipeline as pipeline
from test_rating_pipeline import story, materialized, artifact_path, reaccept
from writing_battle import run as writing


class RatingPipelineReuseTests(unittest.TestCase):
    def setUp(self):
        pipeline._ARTIFACT_CACHE.clear()

    def tearDown(self):
        pipeline._ARTIFACT_CACHE.clear()

    def test_first_read_replays_each_actor_then_same_bytes_reuse_without_compute(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            pipeline._ARTIFACT_CACHE.clear()  # Equivalent to a new CLI process.
            with patch.object(battle, 'compute_case', wraps=battle.compute_case) as compute:
                first = writing(request)
                self.assertEqual(first['status'], 'ready_for_host')
                self.assertEqual(compute.call_count, len(request['fighters']))
                self.assertTrue(first['rating_execution']['replay_performed_this_call'])
                again = writing(request)
                self.assertEqual(again['status'], 'ready_for_host')
                self.assertEqual(compute.call_count, len(request['fighters']))
                self.assertFalse(again['rating_execution']['replay_performed_this_call'])
                self.assertEqual(again['rating_execution']['in_process_reuse_count'], 2)
                # Public return objects cannot poison the private cached result.
                again['author_pack']['independent_ratings'][0]['main_tier']['label'] = 'forged'
                self.assertEqual(writing(request)['status'], 'ready_for_host')

    def test_one_process_batch_matches_separate_assemble_and_prepare(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            artifacts = request['rating_execution']['artifacts']
            pipeline._ARTIFACT_CACHE.clear()
            with patch.object(battle, 'compute_case', wraps=battle.compute_case) as compute:
                batch = pipeline.run({'operation': 'assemble-and-prepare',
                                      'writing_request': story(), 'artifacts': artifacts})
                self.assertEqual(batch['status'], 'ready_for_host')
                self.assertEqual(compute.call_count, 2)
                self.assertEqual(batch['writing_preparation']['rating_execution']['in_process_reuse_count'], 2)
                separate = pipeline.run({'operation': 'assemble',
                                         'writing_request': story(), 'artifacts': artifacts})
                self.assertEqual(batch['writing_request'], separate['writing_request'])
                self.assertEqual(batch['writing_preparation'], writing(separate['writing_request']))
                self.assertEqual(compute.call_count, 2)

    def test_every_changed_product_invalidates_a_warm_import(self):
        for name in pipeline.FILES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                request = materialized(directory)
                self.assertEqual(writing(request)['status'], 'ready_for_host')
                path = artifact_path(request, name)
                path.write_bytes(path.read_bytes() + b'\n')
                self.assertEqual(writing(request)['status'], 'needs_independent_rating')

    def test_forged_reaccepted_analysis_and_receipt_do_not_warm_the_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            out = artifact_path(request, 'analysis.json').parent
            analysis = pipeline._read(out / 'analysis.json')
            analysis['qualitative_claims'][0]['reasoning'] = 'Forged claim'
            pipeline._write(out / 'analysis.json', analysis)
            reaccept(out)
            result = pipeline.run({'operation': 'assemble-and-prepare',
                                   'writing_request': story(),
                                   'artifacts': request['rating_execution']['artifacts']})
            self.assertEqual(result['status'], 'needs_independent_rating')
            self.assertIn('reproducible', result['needs'][0])
            self.assertEqual(writing(request)['status'], 'needs_independent_rating')

    def test_rule_and_engine_content_changes_trigger_actual_replay(self):
        # Include a real temporary engine/rule byte dependency. The separate
        # fingerprint test below checks production dependency discovery itself.
        for kind in ('engine.py', 'rules.json'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                request = materialized(Path(directory) / 'artifacts')
                dependency = Path(directory) / kind
                dependency.write_text('first version', encoding='utf-8')
                original = pipeline._dependency_fingerprint
                with patch.object(pipeline, '_dependency_fingerprint',
                                  side_effect=lambda p: original(p) + pipeline.file_hash(dependency)):
                    self.assertEqual(writing(request)['status'], 'ready_for_host')
                    with patch.object(battle, 'compute_case', wraps=battle.compute_case) as compute:
                        self.assertEqual(writing(request)['status'], 'ready_for_host')
                        self.assertEqual(compute.call_count, 0)
                        dependency.write_text('second version', encoding='utf-8')
                        self.assertEqual(writing(request)['status'], 'ready_for_host')
                        self.assertEqual(compute.call_count, 2)

    def test_production_fingerprint_tracks_added_removed_and_changed_engine_rule_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / 'rulesets').mkdir()
            manifest = root / 'manifest.json'
            manifest.write_text('{}', encoding='utf-8')
            profile = {'document_manifest': str(manifest)}
            with patch.object(pipeline, 'ROOT', root):
                last = pipeline._dependency_fingerprint(profile)
                for path in (root / 'scripts' / 'compute.py', root / 'rulesets' / 'finite.json', manifest):
                    path.write_text('new bytes', encoding='utf-8')
                    current = pipeline._dependency_fingerprint(profile)
                    self.assertNotEqual(current, last)
                    last = current
                (root / 'scripts' / 'compute.py').unlink()
                self.assertNotEqual(pipeline._dependency_fingerprint(profile), last)

    def test_modes_standards_import_changes_and_withdrawal_do_not_cross_warm_results(self):
        with tempfile.TemporaryDirectory() as directory:
            request = materialized(directory)
            mutations = [lambda r: r.update(mode='highest'),
                         lambda r: r.update(standard='vsb'),
                         lambda r: r.update(rating_status={'status': 'withdrawn'}),
                         lambda r: r['fighters'][0].update(state='injured'),
                         lambda r: r['sources'][0].update(locator='different'),
                         lambda r: r['independent_ratings'][0]['main_tier'].update(label='forged')]
            for mutation in mutations:
                changed = copy.deepcopy(request)
                mutation(changed)
                self.assertEqual(writing(changed)['status'], 'needs_independent_rating')
            self.assertEqual(writing(request)['status'], 'ready_for_host')

    def test_local_source_and_status_bytes_change_invalidate_warm_import(self):
        from rating_fixtures import with_executed_ratings
        for local_kind in ('path', 'status_file'):
            with self.subTest(kind=local_kind), tempfile.TemporaryDirectory() as directory:
                local = Path(directory) / 'source.txt'
                local.write_text('{"status":"current"}' if local_kind == 'status_file' else 'Source text', encoding='utf-8')
                request = story()
                request['sources'][0][local_kind] = str(local)
                request = with_executed_ratings(request, Path(directory) / 'artifacts')
                self.assertEqual(writing(request)['status'], 'ready_for_host')
                local.write_text('{"status":"withdrawn"}' if local_kind == 'status_file' else 'Changed source', encoding='utf-8')
                self.assertEqual(writing(request)['status'], 'needs_independent_rating')

    def test_cache_is_bounded_and_batch_still_requires_real_standalone_products(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(pipeline, '_CACHE_LIMIT', 1):
            request = materialized(directory)
            self.assertEqual(len(pipeline._ARTIFACT_CACHE), 1)
            self.assertEqual(writing(request)['status'], 'ready_for_host')
            self.assertEqual(len(pipeline._ARTIFACT_CACHE), 1)
        result = pipeline.run({'operation': 'assemble-and-prepare',
                               'writing_request': story(), 'artifacts': []})
        self.assertEqual(result['status'], 'needs_independent_rating')
        self.assertNotIn('writing_preparation', result)

    def test_redirected_source_and_status_paths_do_not_reuse_old_resolved_targets(self):
        from rating_fixtures import with_executed_ratings
        for local_kind in ('path', 'status_file'):
            with self.subTest(kind=local_kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                old_target, new_target = root / 'old.txt', root / 'new.txt'
                text = '{"status":"current"}' if local_kind == 'status_file' else 'Identical source bytes'
                old_target.write_text(text, encoding='utf-8')
                new_target.write_text(text, encoding='utf-8')
                declared_path = root / 'source-link.txt'
                active_target = [old_target]
                original_resolve = Path.resolve

                def redirected_resolve(path, *args, **kwargs):
                    if str(path) == str(declared_path):
                        return original_resolve(active_target[0], *args, **kwargs)
                    return original_resolve(path, *args, **kwargs)

                # Real files remain present with identical bytes; only path
                # resolution changes, modeling a Windows junction without
                # requiring permission to create native symbolic links.
                with patch.object(Path, 'resolve', autospec=True, side_effect=redirected_resolve):
                    request = story()
                    request['sources'][0][local_kind] = str(declared_path)
                    request = with_executed_ratings(request, root / 'artifacts')
                    self.assertEqual(writing(request)['status'], 'ready_for_host')
                    active_target[0] = new_target
                    self.assertTrue(old_target.exists())
                    self.assertEqual(old_target.read_bytes(), new_target.read_bytes())
                    result = writing(request)
                    self.assertEqual(result['status'], 'needs_independent_rating')
                    self.assertIn('differ', result['rating_execution']['needs'][0])


if __name__ == '__main__':
    unittest.main()
