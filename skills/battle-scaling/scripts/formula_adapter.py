#!/usr/bin/env python3
"""Opt-in local formula crops to candidate LaTeX; never installs or downloads.

run({'image': local_path, 'model_dir': optional_directory}) -> dict.
Runtime: BATTLE_FORMULA_PYTHON or runtime/local-tools.json formula_python.
Models: request model_dir/models, BATTLE_FORMULA_MODEL_DIR, or the same config's
formula_model_dir. models accepts the four official LaTeXOCR path arguments.
All weights must already exist. The host only launches this file --worker on
invocation; inference and optional imports stay inside that isolated worker.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.metadata
import importlib.util
from io import BytesIO, StringIO
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import warnings

ROOT = Path(__file__).resolve().parents[1]
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MODEL_FILES = {'image_resizer_path': 'image_resizer.onnx', 'encoder_path': 'encoder.onnx',
               'decoder_path': 'decoder.onnx', 'tokenizer_json': 'tokenizer.json'}
WARNINGS = [
    'Candidate LaTeX only: verify every symbol, bracket, fraction, subscript and superscript against the original image.',
    'Local handbook experiment: 1/3 raw crops visually matched; fixed-threshold variants matched 2/3. A simple inertia formula still failed. These three cases are not a calibrated accuracy estimate.',
    'No formula confidence score is supplied by this library; successful execution does not establish mathematical or physical correctness.',
]


class AdapterError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _error(code, message):
    return {'status': 'error', 'error': {'code': code, 'message': str(message)[:1200]},
            'needs_review': True, 'warnings': list(WARNINGS)}


def _missing(names, **extra):
    return {'status': 'needs_configuration', 'missing': list(dict.fromkeys(names)),
            'needs_review': True, 'warnings': list(WARNINGS), **extra}


def _local_path(value, label):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise AdapterError('invalid_input', f'{label} must be a nonempty local path string')
    if (value.startswith(('\\\\', '//')) or '://' in value or
            re.match(r'^(?:data|file|https?|ftp):', value, re.IGNORECASE)):
        raise AdapterError('invalid_input', f'{label} must be local; URLs and UNC paths are not accepted')
    try:
        return Path(value).expanduser().resolve()
    except (OSError, ValueError) as exc:
        raise AdapterError('invalid_input', f'invalid {label}') from exc


def _read_image(value, require_decoder=False):
    path = _local_path(value, 'image')
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_IMAGE_BYTES:
        raise AdapterError('invalid_image', 'image must be an existing regular file of 1..20 MiB')
    with path.open('rb') as stream:
        data = stream.read(MAX_IMAGE_BYTES + 1)
    if not 0 < len(data) <= MAX_IMAGE_BYTES:
        raise AdapterError('invalid_image', 'image exceeds 20 MiB')
    record = {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    try:
        from PIL import Image
    except ImportError:
        if require_decoder:
            raise AdapterError('missing_decoder', 'Pillow is required in the configured formula runtime')
        record['decode_validation'] = 'deferred_to_configured_worker_before_inference'
        return data, record
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
                if image.format not in ('PNG', 'JPEG', 'WEBP', 'BMP', 'TIFF', 'GIF'):
                    raise ValueError('unsupported image format')
                if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                    raise ValueError('image must contain 1..20000000 pixels')
                if getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('provide one static formula crop, not animated or multipage imagery')
                image.verify()
                image_format = image.format
            with Image.open(BytesIO(data)) as image:
                image.load()
        record.update({'width': width, 'height': height, 'format': image_format,
                       'decode_validation': 'decoded_and_verified'})
    except Exception as exc:
        raise AdapterError('invalid_image', 'file is not a valid supported static image: ' + str(exc)) from exc
    return data, record


def _config():
    path = ROOT / 'runtime/local-tools.json'
    if not path.exists():
        return {}
    try:
        if path.stat().st_size > 1024 * 1024:
            raise ValueError('configuration exceeds 1 MiB')
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):
            raise ValueError('configuration must be an object')
        return data
    except (OSError, ValueError, TypeError) as exc:
        raise AdapterError('configuration_error', 'invalid runtime/local-tools.json: ' + str(exc)) from exc


def _models(request, config):
    supplied = request.get('models', {})
    if not isinstance(supplied, dict) or set(supplied) - set(MODEL_FILES):
        raise AdapterError('invalid_input', 'models must contain only the four official LaTeXOCR path arguments')
    directory = (request['model_dir'] if 'model_dir' in request else
                 os.environ.get('BATTLE_FORMULA_MODEL_DIR') or config.get('formula_model_dir'))
    base = _local_path(directory, 'model_dir') if directory is not None else None
    if base is not None and directory == config.get('formula_model_dir') and not Path(directory).is_absolute():
        base = (ROOT / directory).resolve()
    paths = {}
    for argument, filename in MODEL_FILES.items():
        if argument in supplied:
            paths[argument] = _local_path(supplied[argument], argument)
        elif base is not None:
            paths[argument] = base / filename
    missing = [str(paths.get(k, filename)) for k, filename in MODEL_FILES.items()
               if k not in paths or not paths[k].is_file() or paths[k].stat().st_size == 0]
    return paths, missing


def _runtime_available():
    try:
        return all(importlib.util.find_spec(name) is not None for name in
                   ('rapid_latex_ocr', 'onnxruntime', 'numpy', 'PIL'))
    except (ImportError, ValueError):
        return False


def _prepare(request, require_decoder=False):
    if not isinstance(request, dict):
        raise AdapterError('invalid_input', 'request must be an object')
    timeout = request.get('timeout_seconds', 60)
    if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or not 1 <= timeout <= 120:
        raise AdapterError('invalid_input', 'timeout_seconds must be a finite number between 1 and 120')
    data, image = _read_image(request.get('image'), require_decoder)
    config = _config()
    paths, missing = _models(request, config)
    return data, image, config, paths, missing, timeout


def run(request: dict) -> dict:
    """Launch one local, bounded worker only when explicitly invoked."""
    try:
        _, image, config, paths, missing, timeout = _prepare(request)
        python = os.environ.get('BATTLE_FORMULA_PYTHON') or config.get('formula_python')
        if not python and _runtime_available():
            python = sys.executable
        needs = ([] if python else ['formula_python']) + (['formula_model_dir'] if missing else [])
        if needs:
            return _missing(needs, missing_model_files=missing, image=image,
                            alternative='Use host visual transcription, or configure already installed local runtime and model files. Nothing was installed or downloaded.')
        interpreter = _local_path(python, 'formula_python')
        if not interpreter.is_file():
            return _missing(['formula_python'], image=image)
        child_request = {'image': image['path'], 'models': {k: str(v) for k, v in paths.items()},
                         'timeout_seconds': timeout}
        env = dict(os.environ)
        env.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1',
                    'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
                    'PYTHONIOENCODING': 'utf-8'})
        try:
            completed = subprocess.run([str(interpreter), '-X', 'utf8', str(Path(__file__).resolve()), '--worker'],
                                       input=json.dumps(child_request, ensure_ascii=False), capture_output=True,
                                       text=True, encoding='utf-8', timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return _error('worker_timeout', 'configured formula worker exceeded timeout_seconds')
        try:
            if len(completed.stdout) > 1024 * 1024:
                raise ValueError('oversized response')
            result = json.loads(completed.stdout)
            if not isinstance(result, dict) or result.get('status') not in ('ok', 'error', 'needs_configuration'):
                raise ValueError('unexpected response contract')
            if result['status'] == 'ok' and (completed.returncode or not isinstance(result.get('latex'), str) or not result['latex'].strip()):
                raise ValueError('worker returned no candidate')
        except (ValueError, TypeError):
            return _error('worker_invalid_response', 'configured formula worker returned no valid JSON candidate; inspect its local environment')
        result['needs_review'] = True
        result['warnings'] = list(dict.fromkeys(WARNINGS + result.get('warnings', [])))
        return result
    except AdapterError as exc:
        return _error(exc.code, exc)
    except (OSError, ValueError, TypeError) as exc:
        return _error('adapter_error', exc)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _worker_run(request):
    try:
        data, image, _, paths, missing, _ = _prepare(request, require_decoder=True)
        if missing:
            return _missing(['formula_model_dir'], missing_model_files=missing, image=image)
        if not _runtime_available():
            return _missing(['rapid_latex_ocr', 'onnxruntime', 'numpy', 'Pillow'], image=image)
        os.environ.update({'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'})
        model_records = {key: {'path': str(path), 'bytes': path.stat().st_size, 'sha256': _sha256(path)}
                         for key, path in paths.items()}
        with redirect_stdout(StringIO()):
            import numpy as np
            import onnxruntime as ort
            from rapid_latex_ocr import LaTeXOCR
            from rapid_latex_ocr.utils_load import OrtInferSession
            original_options = OrtInferSession._init_sess_opt
            def single_thread_options(self):
                self.num_threads = 1
                original_options(self)
                self.sess_opt.intra_op_num_threads = 1
                self.sess_opt.inter_op_num_threads = 1
                self.sess_opt.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            OrtInferSession._init_sess_opt = single_thread_options
            started = time.perf_counter()
            engine = LaTeXOCR(**paths)
            initialization = time.perf_counter() - started
            sessions = {'image_resizer': engine.image_resizer.session,
                        'encoder': engine.encoder_decoder.encoder.session,
                        'decoder': engine.encoder_decoder.decoder.session.session}
            providers = {name: session.get_providers() for name, session in sessions.items()}
            if any(p != ['CPUExecutionProvider'] for p in providers.values()):
                raise AdapterError('unexpected_backend', 'formula runtime did not use CPU-only sessions')
            np.random.seed(0)
            started = time.perf_counter()
            latex, elapsed = engine(data)
            wall = time.perf_counter() - started
        if not isinstance(latex, str) or not latex.strip():
            raise AdapterError('empty_candidate', 'formula model returned no LaTeX candidate')
        versions = {name: importlib.metadata.version(name) for name in
                    ('numpy', 'onnxruntime', 'tokenizers', 'Pillow', 'opencv-python')}
        return {'status': 'ok', 'latex': latex, 'needs_review': True,
                'elapsed_seconds': float(elapsed), 'call_wall_seconds': wall,
                'initialization_seconds': initialization, 'image': image, 'models': model_records,
                'engine': {'name': 'RapidLaTeXOCR', 'package': 'rapid-latex-ocr',
                           'version': importlib.metadata.version('rapid-latex-ocr'), 'dependencies': versions},
                'backend': {'type': 'local_onnx_cpu', 'sessions': providers, 'intra_op_threads': 1, 'inter_op_threads': 1},
                'python_executable': sys.executable, 'confidence': None, 'warnings': list(WARNINGS)}
    except AdapterError as exc:
        return _error(exc.code, exc)
    except Exception as exc:
        return _error('inference_error', str(exc))


def validate_output(request,output):
    """Protect source crops/config/weights for both this CLI and the battle router."""
    if not isinstance(request,dict):raise AdapterError('invalid_input','request must be an object')
    target=Path(output).resolve()
    protected={_local_path(request.get('image'),'image'),(ROOT/'runtime/local-tools.json').resolve(),Path(__file__).resolve()}
    paths,_=_models(request,_config());protected.update(paths.values())
    if target in protected:raise AdapterError('invalid_input','output must not overwrite an image or model')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', help='read one request JSON from stdin; never spawns another worker')
    parser.add_argument('--input', help='request JSON file for a normal configured invocation')
    parser.add_argument('--output', help='optional result JSON file')
    args = parser.parse_args()
    if not args.worker and not args.input:
        parser.error('--input or --worker is required')
    try:
        if args.output and args.input and Path(args.output).resolve() == Path(args.input).resolve():
            raise AdapterError('invalid_input', 'output must not overwrite input')
        if not args.worker and Path(args.input).stat().st_size > 1024 * 1024:
            raise AdapterError('invalid_input', 'request exceeds 1 MiB')
        raw = sys.stdin.read(1024 * 1024 + 1) if args.worker else Path(args.input).read_text(encoding='utf-8-sig')
        if len(raw) > 1024 * 1024:
            raise AdapterError('invalid_input', 'request exceeds 1 MiB')
        request = json.loads(raw)
        if args.output:
            target=validate_output(request,args.output)
        result = _worker_run(request) if args.worker else run(request)
        if args.output:
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except AdapterError as exc:
        result = _error(exc.code, exc)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        result = _error('invalid_input', exc)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result['status'] == 'ok' else 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
