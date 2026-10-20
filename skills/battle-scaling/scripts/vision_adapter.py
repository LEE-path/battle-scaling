#!/usr/bin/env python3
"""Opt-in OpenAI-compatible image reader for hosts without native vision.

No credentials, model or paid endpoint are supplied by the Skill. Configure
BATTLE_VISION_BASE_URL and BATTLE_VISION_MODEL; API key is optional for local
servers and read only from BATTLE_VISION_API_KEY. Nothing is sent until run().
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import sys
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

MAX_IMAGE = 20 * 1024 * 1024
MAX_RESPONSE = 4 * 1024 * 1024


def build_payload(images, prompt, model):
    if not isinstance(images, list) or not 1 <= len(images) <= 12:
        raise ValueError('provide 1 to 12 local image paths')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 50000:
        raise ValueError('provide a nonempty prompt no longer than 50000 characters')
    content = [{'type': 'text', 'text': prompt}]
    records = []
    total = 0
    for filename in images:
        p = Path(filename).resolve()
        if not p.is_file() or not 0 < p.stat().st_size <= MAX_IMAGE:
            raise ValueError('image must exist and be at most 20 MiB')
        data = p.read_bytes()
        mime = mimetypes.guess_type(p.name)[0]
        if mime not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'):
            raise ValueError('supported images: PNG, JPEG, WEBP, GIF; extract animated frames first')
        total += len(data)
        if total > 32 * 1024 * 1024:
            raise ValueError('combined image size must be at most 32 MiB')
        content.append({'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')}})
        records.append({'path': str(p), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'mime': mime})
    return {'model': model, 'messages': [{'role': 'user', 'content': content}], 'stream': False}, records


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('API redirects are disabled; configure the final base URL')


def run(request, environ=None):
    env = os.environ if environ is None else environ
    base = env.get('BATTLE_VISION_BASE_URL', '').strip()
    model = env.get('BATTLE_VISION_MODEL', '').strip()
    if not base or not model:
        return {'status': 'needs_configuration', 'missing': [k for k, v in
                (('BATTLE_VISION_BASE_URL', base), ('BATTLE_VISION_MODEL', model)) if not v],
                'alternative': 'Use the host native vision tool; no external model has been called.'}
    try:
        parts = urllib.parse.urlsplit(base)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('base URL must be HTTP(S) without credentials, query or fragment')
        if parts.scheme == 'http' and parts.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('remote endpoints require HTTPS')
        if not isinstance(request, dict):
            raise ValueError('request must be an object')
        payload, records = build_payload(request.get('images'), request.get('prompt'), model)
        timeout = request.get('timeout_seconds', 45)
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
            raise ValueError('timeout_seconds must be between 1 and 120')
        headers = {'Content-Type': 'application/json'}
        key = env.get('BATTLE_VISION_API_KEY', '')
        if key:
            headers['Authorization'] = 'Bearer ' + key
        url = base.rstrip('/') + '/chat/completions'
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        handlers=[NoRedirect()]
        # Loopback model servers stay local even on machines with an OS proxy.
        if parts.hostname in ('localhost','127.0.0.1','::1'):
            handlers.append(urllib.request.ProxyHandler({}))
        with urllib.request.build_opener(*handlers).open(req, timeout=timeout) as response:
            data = response.read(MAX_RESPONSE + 1)
        if len(data) > MAX_RESPONSE:
            raise ValueError('vision response exceeded 4 MiB')
        parsed = json.loads(data)
        text = parsed['choices'][0]['message']['content']
        if not isinstance(text, (str, list)) or not text:
            raise ValueError('endpoint returned no assistant content')
        return {'status': 'ok', 'model': model, 'endpoint_origin': parts.scheme + '://' + parts.netloc,
                'images': records, 'response': text,
                'validation': 'Model observations require original-image and continuity checks; this is not a physical measurement.',
                'usage': parsed.get('usage')}
    except urllib.error.HTTPError as exc:
        return {'status': 'error', 'error': f'vision endpoint HTTP {exc.code}; inspect provider configuration', 'model': model}
    except (ValueError, TypeError, KeyError, IndexError, OSError) as exc:
        # Never include URL credentials, auth headers or provider error bodies.
        message = str(exc)
        secret = env.get('BATTLE_VISION_API_KEY', '')
        if secret:
            message = message.replace(secret, '[redacted]')
        if 'parts' in locals() and (parts.username or parts.password):
            message = 'invalid credential-bearing base URL'
        return {'status': 'error', 'error': message}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--output')
    a = p.parse_args()
    if a.output and Path(a.input).resolve() == Path(a.output).resolve():
        p.error('output must not overwrite the input request')
    result = run(json.loads(Path(a.input).read_text(encoding='utf-8-sig')))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if result['status'] == 'ok' else 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
