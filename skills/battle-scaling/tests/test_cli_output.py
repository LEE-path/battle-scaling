import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import battle


class CliOutputTests(unittest.TestCase):
    def call(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = battle.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def request(self, directory, data=None):
        path = Path(directory) / 'input.json'
        path.write_text(json.dumps(data or {'model': 'kinetic', 'inputs': {'mass': 3, 'speed': 4}}),
                        encoding='utf-8')
        return path

    def test_no_output_keeps_complete_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.request(directory)
            code, stdout, stderr = self.call(['physics', '--input', str(path)])
            self.assertEqual((code, stderr), (0, ''))
            full = json.loads(stdout)
            self.assertIn('result', full)
            self.assertIn('ruleset_profile', full)
            self.assertNotIn('stdout', full)

    def test_saved_result_is_complete_and_identical_with_full_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.request(directory)
            compact, complete = Path(directory) / 'compact.json', Path(directory) / 'full.json'
            code, stdout, stderr = self.call(['physics', '--input', str(path), '--output', str(compact)])
            full_code, full_stdout, full_stderr = self.call(
                ['physics', '--input', str(path), '--output', str(complete), '--full-output'])
            self.assertEqual((code, full_code, stderr, full_stderr), (0, 0, '', ''))
            self.assertEqual(compact.read_bytes(), complete.read_bytes())
            receipt = json.loads(stdout)
            self.assertEqual(receipt['output'], str(compact.resolve()))
            self.assertTrue(receipt['full_result_saved'])
            self.assertEqual(receipt['stdout'], 'summary')
            self.assertNotIn('ruleset_profile', receipt)
            self.assertEqual(json.loads(full_stdout), json.loads(compact.read_text(encoding='utf-8')))

    def test_large_story_packs_stay_in_file_not_console(self):
        payload = {'status': 'needs_independent_rating', 'operation': 'prepare',
                   'author_pack': {'sources': ['原作资料' * 10000]},
                   'rating_execution': {'status': 'needs_research', 'needs': ['fresh dossier'],
                                        'artifacts': ['large artifact ' * 10000]},
                   'rating_preflight': {'status': 'needs_research', 'needs': ['tier', 'source']},
                   'errors': [], 'needs': ['rating required'], 'revision_tasks': [],
                   'host_semantic_review_required': True, 'narrative_generated': False}
        with tempfile.TemporaryDirectory() as directory:
            path = self.request(directory)
            out = Path(directory) / 'writing.json'
            with patch('writing_battle.run', return_value=payload):
                code, stdout, stderr = self.call(['writing', '--input', str(path), '--output', str(out)])
            self.assertEqual((code, stderr), (0, ''))
            self.assertLess(len(stdout), 2000)
            self.assertEqual(json.loads(out.read_text(encoding='utf-8')), payload)
            summary = json.loads(stdout)
            self.assertEqual(summary['need_count'], 1)
            self.assertEqual(summary['rating_execution'], {'status': 'needs_research', 'need_count': 1})
            self.assertEqual(summary['rating_preflight']['need_count'], 2)
            self.assertNotIn('author_pack', summary)
            self.assertFalse(summary['narrative_generated'])
            self.assertTrue(summary['host_semantic_review_required'])

    def test_pipeline_full_output_flag_is_after_subcommand(self):
        payload = {'status': 'assembled', 'writing_request': {'sources': ['all source data']},
                   'rating_execution': {'artifacts': ['all artifacts']}}
        with tempfile.TemporaryDirectory() as directory:
            path = self.request(directory)
            out = Path(directory) / 'pipeline.json'
            with patch('rating_pipeline.run', return_value=payload):
                code, stdout, stderr = self.call(
                    ['rating-pipeline', '--full-output', '--input', str(path), '--output', str(out)])
            self.assertEqual((code, stderr), (0, ''))
            self.assertEqual(json.loads(stdout), json.loads(out.read_text(encoding='utf-8')))
            self.assertIn('writing_request', json.loads(stdout))

    def test_validation_error_is_saved_with_same_failure_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.request(directory)
            out = Path(directory) / 'validation.json'
            with patch.object(battle, 'validate_case', return_value=['bad source', 'bad tier']):
                code, stdout, stderr = self.call(['validate', '--input', str(path), '--output', str(out)])
            self.assertEqual((code, stderr), (2, ''))
            self.assertEqual(json.loads(out.read_text(encoding='utf-8')),
                             {'valid': False, 'errors': ['bad source', 'bad tier']})
            summary = json.loads(stdout)
            self.assertEqual((summary['status'], summary['valid'], summary['error_count']),
                             ('invalid', False, 2))
            self.assertEqual(summary['error_preview'], ['bad source', 'bad tier'])

    def test_validation_without_output_keeps_original_error_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.request(directory)
            with patch.object(battle, 'validate_case', return_value=['invalid']):
                code, stdout, stderr = self.call(['validate', '--input', str(path)])
            self.assertEqual((code, stderr), (2, ''))
            self.assertEqual(json.loads(stdout), {'valid': False, 'errors': ['invalid']})

    def test_exception_stays_on_stderr_and_does_not_replace_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.request(directory)
            original = path.read_bytes()
            code, stdout, stderr = self.call(['physics', '--input', str(path), '--output', str(path)])
            self.assertEqual((code, stdout), (2, ''))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(json.loads(stderr)['status'], 'error')
            self.assertIn('overwrite', json.loads(stderr)['error'])

    def test_blocked_status_preserves_failure_exit_and_diagnostics(self):
        payload = {'status': 'blocked', 'error': 'source denied', 'errors': ['missing permission'],
                   'sources': ['large' * 1000]}
        with tempfile.TemporaryDirectory() as directory:
            path = self.request(directory)
            out = Path(directory) / 'research.json'
            with patch('research.run', return_value=payload):
                code, stdout, stderr = self.call(['research', '--input', str(path), '--output', str(out)])
            self.assertEqual((code, stderr), (2, ''))
            self.assertEqual(json.loads(stdout)['error_count'], 2)
            self.assertEqual(json.loads(out.read_text(encoding='utf-8')), payload)

    def test_diagnostic_previews_are_bounded_without_losing_saved_details(self):
        payload = {'status': 'invalid', 'errors': ['E' * 1000] * 100,
                   'needs': ['N' * 1000] * 100, 'warnings': ['W' * 1000] * 100}
        summary = battle.output_summary(payload, 'writing', 'result.json')
        for category in ('error', 'need', 'warning'):
            self.assertEqual(summary[category + '_count'], 100)
            self.assertEqual(len(summary[category + '_preview']), 3)
            self.assertTrue(all(len(item) == 240 for item in summary[category + '_preview']))
        self.assertEqual(len(payload['errors'][0]), 1000)

    def test_doctor_and_rules_without_output_remain_complete(self):
        doctor = {'status': 'ok', 'host_capabilities': {'search': 'host'}, 'core_tools': {'evidence': True}}
        with patch.object(battle, 'doctor', return_value=doctor):
            code, stdout, stderr = self.call(['doctor'])
        self.assertEqual((code, stderr, json.loads(stdout)), (0, '', doctor))
        rule = {'id': 'test', 'criteria': ['complete criterion']}
        with patch.object(battle, 'resolve_profile', return_value={}), \
             patch.object(battle, 'snapshot_content', return_value=rule):
            code, stdout, stderr = self.call(['rules', '--standard', 'wangba'])
        self.assertEqual((code, stderr, json.loads(stdout)), (0, '', rule))


if __name__ == '__main__':
    unittest.main()
