import base64
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from vision_adapter import run, build_payload

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aE1sAAAAASUVORK5CYII=')


class VisionTests(unittest.TestCase):
    def test_unconfigured_is_not_available(self):
        r = run({'images': [], 'prompt': 'read'}, environ={})
        self.assertEqual(r['status'], 'needs_configuration')

    def test_image_payload_contains_real_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'page.png'
            p.write_bytes(PNG)
            payload, records = build_payload([str(p)], 'read the page', 'configured-model')
            content = payload['messages'][0]['content']
            self.assertEqual(base64.b64decode(content[1]['image_url']['url'].split(',')[1]), PNG)
            self.assertEqual(records[0]['bytes'], len(PNG))

    def test_credentials_in_url_rejected_without_network(self):
        r = run({'images': [], 'prompt': 'read'}, environ={'BATTLE_VISION_BASE_URL': 'https://key:secret@host/v1', 'BATTLE_VISION_MODEL': 'm'})
        self.assertEqual(r['status'], 'error')
        self.assertNotIn('secret', json.dumps(r))

    def test_no_implicit_model_or_fake_reply(self):
        r = run({'images': [], 'prompt': 'read'}, environ={'BATTLE_VISION_BASE_URL': 'http://localhost:11434/v1'})
        self.assertEqual(r['status'], 'needs_configuration')

    def test_real_http_contract_and_returned_observation(self):
        captured = {}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured['path'] = self.path
                captured['payload'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                captured['auth'] = self.headers.get('Authorization')
                body = json.dumps({'choices': [{'message': {'content': 'fixture observation'}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                p = Path(d)/'page.png'
                p.write_bytes(PNG)
                env = {'BATTLE_VISION_BASE_URL': f'http://127.0.0.1:{server.server_port}/v1',
                       'BATTLE_VISION_MODEL': 'fixture-model', 'BATTLE_VISION_API_KEY': 'fixture-secret'}
                result = run({'images': [str(p)], 'prompt': 'read'}, environ=env)
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['response'], 'fixture observation')
            self.assertEqual(captured['path'], '/v1/chat/completions')
            self.assertEqual(captured['auth'], 'Bearer fixture-secret')
            self.assertEqual(captured['payload']['model'], 'fixture-model')
            self.assertNotIn('fixture-secret', json.dumps(result))
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
