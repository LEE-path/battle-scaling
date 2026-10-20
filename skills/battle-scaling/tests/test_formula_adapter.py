import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import formula_adapter as formula


def tiny_png():
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00' + b'\xff' * 6 + b'\x00' + b'\xff' * 6))
            + chunk(b'IEND', b''))


class FormulaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.image = self.root / 'formula.png'
        self.image.write_bytes(tiny_png())
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.root_patch = patch.object(formula, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def models(self):
        directory = self.root / 'models'
        directory.mkdir(exist_ok=True)
        for name in ('encoder.onnx', 'decoder.onnx', 'image_resizer.onnx', 'tokenizer.json'):
            (directory / name).write_bytes(b'local fixture, never used for inference')
        return directory

    def test_unconfigured_reports_missing_without_outbound(self):
        with patch.object(formula, '_runtime_available', return_value=False), \
             patch('socket.create_connection', side_effect=AssertionError('outbound')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('outbound')), \
             patch.object(formula.subprocess, 'run', side_effect=AssertionError('unexpected worker')):
            result = formula.run({'image': str(self.image)})
        self.assertEqual(result['status'], 'needs_configuration')
        self.assertTrue(result['needs_review'])
        self.assertIn('formula_model_dir', result['missing'])

    def test_invalid_request_is_structured(self):
        for request in (None, [], 'text', {'image': 42}, {'image': ''}):
            with self.subTest(request=request):
                result = formula.run(request)
                self.assertEqual(result['status'], 'error')
                self.assertIsInstance(result['error']['code'], str)

    def test_url_unc_and_nonfile_rejected_before_child(self):
        with patch.object(formula.subprocess, 'run') as child:
            for filename in ('https://example.invalid/formula.png', 'file:///tmp/formula.png',
                             'data:image/png;base64,AAAA', r'\\server\share\formula.png',
                             str(self.root), str(self.root / 'missing.png')):
                with self.subTest(filename=filename):
                    self.assertEqual(formula.run({'image': filename})['status'], 'error')
            child.assert_not_called()

    def test_disguised_text_is_not_an_image(self):
        self.image.write_text('not a PNG image', encoding='utf-8')
        with patch.object(formula.subprocess, 'run') as child:
            result = formula.run({'image': str(self.image)})
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error']['code'], 'invalid_image')
        child.assert_not_called()

    def test_truncated_png_is_rejected(self):
        self.image.write_bytes(tiny_png()[:34])
        self.assertEqual(formula.run({'image': str(self.image)})['status'], 'error')

    def test_nonfinite_or_boolean_timeouts_are_rejected(self):
        for timeout in (True, float('nan'), float('inf'), 0, 121, '30'):
            with self.subTest(timeout=timeout):
                result = formula.run({'image': str(self.image), 'timeout_seconds': timeout})
                self.assertEqual(result['status'], 'error')

    def test_missing_models_never_instantiates_or_downloads(self):
        os.environ['BATTLE_FORMULA_PYTHON'] = sys.executable
        with patch.object(formula.subprocess, 'run') as child, \
             patch('urllib.request.urlopen', side_effect=AssertionError('outbound')):
            result = formula.run({'image': str(self.image), 'model_dir': str(self.root / 'absent')})
        self.assertEqual(result['status'], 'needs_configuration')
        self.assertEqual(len(result['missing_model_files']), 4)
        child.assert_not_called()

    def test_remote_model_path_is_rejected(self):
        result = formula.run({'image': str(self.image), 'models': {'encoder_path': 'https://example.invalid/e.onnx'}})
        self.assertEqual(result['status'], 'error')

    def test_runtime_config_dispatches_same_script_worker_without_shell(self):
        model_dir = self.models()
        runtime = self.root / 'runtime'
        runtime.mkdir()
        (runtime / 'local-tools.json').write_text(json.dumps({
            'formula_python': sys.executable, 'formula_model_dir': str(model_dir)}), encoding='utf-8')
        returned = {'status': 'ok', 'latex': r'x^{2}', 'needs_review': False}
        with patch.object(formula, '_runtime_available', return_value=False), \
             patch.object(formula.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(returned), '')) as child:
            result = formula.run({'image': str(self.image)})
        command = child.call_args.args[0]
        self.assertEqual(command[0], sys.executable)
        self.assertIn('--worker', command)
        self.assertEqual(Path(command[-2]).resolve(), Path(formula.__file__).resolve())
        self.assertFalse(child.call_args.kwargs.get('shell', False))
        self.assertEqual(child.call_args.kwargs['env']['HF_HUB_OFFLINE'], '1')
        sent = json.loads(child.call_args.kwargs['input'])
        self.assertEqual(Path(sent['models']['encoder_path']), model_dir / 'encoder.onnx')
        self.assertEqual(result['latex'], r'x^{2}')
        self.assertTrue(result['needs_review'])

    def test_environment_overrides_runtime_python(self):
        directory = self.models()
        os.environ['BATTLE_FORMULA_PYTHON'] = sys.executable
        os.environ['BATTLE_FORMULA_MODEL_DIR'] = str(directory)
        with patch.object(formula, '_runtime_available', return_value=False), \
             patch.object(formula.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"status":"ok","latex":"x"}', '')) as child:
            result = formula.run({'image': str(self.image)})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(child.call_args.args[0][0], sys.executable)

    def test_worker_invalid_json_and_timeout_are_structured(self):
        os.environ['BATTLE_FORMULA_PYTHON'] = sys.executable
        os.environ['BATTLE_FORMULA_MODEL_DIR'] = str(self.models())
        with patch.object(formula, '_runtime_available', return_value=False):
            with patch.object(formula.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'not JSON', 'sensitive diagnostic')):
                result = formula.run({'image': str(self.image)})
                self.assertEqual(result['error']['code'], 'worker_invalid_response')
                self.assertNotIn('sensitive diagnostic', json.dumps(result))
            with patch.object(formula.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', 3)):
                result = formula.run({'image': str(self.image)})
                self.assertEqual(result['error']['code'], 'worker_timeout')

    def test_bad_runtime_config_is_structured(self):
        runtime = self.root / 'runtime'
        runtime.mkdir()
        (runtime / 'local-tools.json').write_text('{oops', encoding='utf-8')
        result = formula.run({'image': str(self.image)})
        self.assertEqual(result['error']['code'], 'configuration_error')

    def test_cli_error_output_cannot_overwrite_a_model(self):
        directory = self.models()
        target = directory / 'encoder.onnx'
        before = target.read_bytes()
        self.image.write_bytes(b'not an image')
        request = self.root / 'request.json'
        request.write_text(json.dumps({'image': str(self.image), 'model_dir': str(directory)}), encoding='utf-8')
        completed = subprocess.run([sys.executable, str(Path(formula.__file__)), '--input', str(request),
                                    '--output', str(target)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(target.read_bytes(), before)

    def test_import_does_not_initialize_optional_runtime(self):
        code = ('import sys;sys.path.insert(0,sys.argv[1]);import formula_adapter;'
                'assert "rapid_latex_ocr" not in sys.modules;assert "onnxruntime" not in sys.modules')
        completed = subprocess.run([sys.executable, '-c', code, str(ROOT / 'scripts')], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)


class RealWorkerSmoke(unittest.TestCase):
    def test_optional_real_worker_offline_cpu_smoke(self):
        python = os.environ.get('BATTLE_FORMULA_TEST_PYTHON')
        models = os.environ.get('BATTLE_FORMULA_TEST_MODELS')
        image = os.environ.get('BATTLE_FORMULA_TEST_IMAGE')
        if not python or not models or not image or not all(Path(p).exists() for p in (python, models, image)):
            self.skipTest('Set BATTLE_FORMULA_TEST_PYTHON/MODELS/IMAGE for the installed optional runtime smoke test')
        # The actual worker process denies outbound connections at the socket
        # boundary. Real local models must still load and run successfully.
        code = ('import socket,runpy,sys; '
                'socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError("outbound forbidden")); '
                'sys.argv=[sys.argv[1],"--worker"]; runpy.run_path(sys.argv[0],run_name="__main__")')
        request = {'image': image, 'model_dir': models, 'timeout_seconds': 90}
        completed = subprocess.run([python, '-X', 'utf8', '-c', code, str(ROOT / 'scripts/formula_adapter.py')],
                                   input=json.dumps(request), text=True, encoding='utf-8', capture_output=True, timeout=100)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result['status'], 'ok', result)
        self.assertTrue(result['latex'])
        self.assertTrue(result['needs_review'])
        self.assertEqual(result['image']['sha256'], hashlib.sha256(Path(image).read_bytes()).hexdigest())
        self.assertTrue(all(v == ['CPUExecutionProvider'] for v in result['backend']['sessions'].values()))
        self.assertEqual(len(result['models']), 4)
        self.assertTrue(all(len(m['sha256']) == 64 for m in result['models'].values()))
        self.assertEqual(result['engine']['version'], '0.0.9')


if __name__ == '__main__':
    unittest.main()
