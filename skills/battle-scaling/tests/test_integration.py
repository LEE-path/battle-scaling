import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from battle import compute_case, main, render_report
from evidence import analyze_case
from rating_fixtures import rated_fixture
from rating_fixtures import legacy_analyze_case as analyze_case  # Explicit legacy regression
from rating_fixtures import legacy_compute_case as compute_case



@rated_fixture
def packet():
    return {'schema_version': 1, 'case_id': 'integration-synthetic', 'fixture_kind': 'synthetic',
            'characters': [{'id': 'a', 'name': 'A', 'version': 'one', 'state': 'base'}],
            'sources': [{'id': 's', 'title': 'Synthetic evidence', 'origin': 'synthetic',
                         'access': 'provided', 'locator': 'fixture'}], 'anchors': [], 'edges': []}


class IntegrationTests(unittest.TestCase):
    def test_high_recomputed_and_rendered_in_each_requested_mode(self):
        p = packet()
        p['computations'] = [{'id': 'ordinal', 'type': 'high',
                              'request': {'kind': 'ordinal', 'expression': 'omega+1'}}]
        p['qualitative_claims'] = [{'claim': 'aggressive interpretation', 'modes': ['highest']}]
        computed = compute_case(p, 'all')
        self.assertEqual([c['output']['mode'] for c in computed['computations']], ['normal', 'highest', 'lowball'])
        result = analyze_case(computed, 'all')
        for m in ('normal', 'highest', 'lowball'):
            self.assertEqual(len(result['modes'][m]['high_results']), 1)
        self.assertEqual(result['modes']['normal']['qualitative_claims'], [])
        self.assertEqual(len(result['modes']['highest']['qualitative_claims']), 1)
        self.assertEqual(render_report(result).count('高层构造与具名规则映射：'), 3)

    def test_matchup_mode_paths_and_inference_are_separate(self):
        p = packet()
        p['matchup'] = {'teams': ['a', 'b'], 'win_paths': [
            {'id': 'peak-only', 'winner': 'a', 'modes': ['highest'], 'evidence_ids': ['s'],
             'requirements': [{'claim': 'test condition', 'status': 'supported', 'evidence_ids': ['s']}]}],
            'mode_assessments': {'normal': {'winner': 'b', 'status': 'reasoned_estimate',
                 'reasoning': 'synthetic mechanism inference', 'evidence_ids': ['s']}}}
        result = analyze_case(p, 'all')
        self.assertEqual(result['matchups']['normal']['verdict'], 'insufficient_evidence')
        self.assertEqual(result['matchups']['highest']['verdict'], 'a')
        self.assertEqual(result['matchups']['normal']['assessment']['winner'], 'b')
        p['sources'][0]['access'] = 'blocked'
        self.assertIsNone(analyze_case(p)['matchup']['assessment']['winner'])

    def test_mode_specific_anchor_does_not_leak(self):
        p = packet()
        p['anchors'] = [{'id': 'peak', 'subject': 'a', 'attribute': 'force', 'kind': 'calculation',
                         'quantity': {'value': 100, 'unit': 'N'}, 'evidence_ids': ['s'], 'modes': ['highest']}]
        result = analyze_case(p, 'all')
        self.assertEqual(result['modes']['normal']['conclusions'], [])
        self.assertEqual(len(result['modes']['highest']['conclusions']), 1)

    def test_source_wrapper_preserves_non_success_exit_code(self):
        with patch('sources.fetch_source', return_value={'status': 'partial'}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['sources', '--url', 'https://example.com', '--output', 'unused']), 2)

    def test_input_request_cannot_be_overwritten_by_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'input.json'
            raw = '{"model":"kinetic","inputs":{"mass":1,"speed":1}}'
            path.write_text(raw, encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['physics', '--input', str(path), '--output', str(path)]), 2)
            self.assertEqual(path.read_text(encoding='utf-8'), raw)

    def test_analysis_export_cannot_overwrite_case(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'analysis.json'
            raw = json.dumps(packet())
            path.write_text(raw, encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['analyze', '--input', str(path), '--output', d]), 2)
            self.assertEqual(path.read_text(encoding='utf-8'), raw)

    def test_standalone_unicode_cli_ignores_legacy_console_encoding(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'input.json'
            path.write_text(json.dumps({'model': 'kinetic', 'inputs': {'mass': 1, 'speed': 2},
                                        'assumptions': ['Unicode ∀ ≠ 中文']}), encoding='utf-8')
            env = {**os.environ, 'PYTHONIOENCODING': 'ascii'}
            result = subprocess.run([sys.executable, str(root/'scripts/physics.py'), '--input', str(path)],
                                    capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Unicode ∀ ≠ 中文', json.loads(result.stdout.decode('utf-8'))['assumptions'])

    def test_analysis_keeps_exact_case_bytes_and_rule_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'original.json';out=Path(d)/'run'
            raw=b'\xef\xbb\xbf'+(json.dumps(packet(),ensure_ascii=False,indent=3)+'\n').encode('utf-8')
            path.write_bytes(raw)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['analyze','--input',str(path),'--mode','all','--output',str(out)]),0)
            self.assertEqual((out/'CASE.json').read_bytes(),raw)
            manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['files']['CASE.json']['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertIn('rules-snapshot.json',manifest['files'])
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['analyze','--input',str(out/'CASE.json'),'--output',str(out)]),2)
            self.assertEqual((out/'CASE.json').read_bytes(),raw)

    def test_formula_router_protects_model_even_on_error_path(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/'tokenizer.json';model.write_bytes(b'original model')
            request=Path(d)/'request.json'
            request.write_text(json.dumps({'image':str(Path(d)/'missing.png'),
                               'models':{'tokenizer_json':str(model)}}),encoding='utf-8')
            with patch('formula_adapter.run') as worker,contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['formula','--input',str(request),'--output',str(model)]),2)
            worker.assert_not_called()
            self.assertEqual(model.read_bytes(),b'original model')


if __name__ == '__main__':
    unittest.main()
