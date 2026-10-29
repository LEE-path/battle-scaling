"""Release protection regression tests; all credentials below are synthesized."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import publication_guard as g
import sync_public as s


def synthetic_key():
    return 'sk-' + 'Q9b2r8M7t4L6w5X3d1V0c2N8z6F4h7K9'


def manifest(root):
    files = {p.relative_to(root).as_posix(): s.digest(p.read_bytes()) for p in root.rglob('*')
             if p.is_file() and '.git' not in p.parts and p.relative_to(root).as_posix() not in g.METADATA}
    p = root/'docs/distribution-manifest.json'
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps({'files': files}), encoding='utf-8')


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=True)


class PrivacyTests(unittest.TestCase):
    def test_private_paths_are_filtered_everywhere(self):
        for name in ('runtime/media-integrations.local.md', 'runtime/local-tools.json',
                     'data/media-sourcing/site-notes.jsonl', 'credentials.json',
                     'credential.dpapi', 'cookies.txt', '.env', 'docs/auth.json'):
            self.assertTrue(g.confidential_path(name), name)
            self.assertTrue(s.excluded(name, 'public'), name)
        self.assertFalse(g.confidential_path('.env.example'))
        self.assertFalse(g.confidential_path('tests/test_sources.py'))

    def test_credentials_are_blocked_and_diagnostics_redacted(self):
        value = synthetic_key()
        for text in (json.dumps({'OPENAI_API_KEY': value}), 'OPENAI_API_KEY='+value,
                     json.dumps({'headers': {'Authorization': 'Bearer '+value}}),
                     'https://host.invalid/?signature='+value,
                     'https://user:'+value+'@host.invalid/file',
                     '-----BEGIN '+'PRIVATE KEY-----'):
            findings = g.scan_file('notes.md', text.encode())
            self.assertTrue(findings)
            self.assertNotIn(value, json.dumps(findings))
        opaque = 'opaque' + '-session-value-7f192bd'
        self.assertTrue(g.scan_file('settings.json', json.dumps({'API_KEY': opaque}).encode()))
        self.assertTrue(g.scan_file('settings.json', json.dumps({'headers': {'Cookie': opaque}}).encode()))

    def test_json_escape_is_not_a_bypass(self):
        key = synthetic_key()
        encoded = ''.join('\\u%04x' % ord(c) for c in key)
        self.assertTrue(g.scan_file('config.json', ('{"api_key":"'+encoded+'"}').encode()))
        opaque = 'opaque'+'-value-9843'
        self.assertTrue(g.scan_file('config.json', ('{"api\\u005fkey":"'+opaque+'"}').encode()))

    def test_opaque_cloud_keys_and_unquoted_config_values(self):
        opaque = 'opaque'+'-value-8b712e9a'
        for text in (json.dumps({'AWS_SECRET_ACCESS_KEY': opaque}),
                     'API_KEY='+opaque,
                     'api_key: '+opaque,
                     '$env:MODEL_API_KEY = '+opaque,
                     'https://host.invalid/?access_key='+opaque):
            self.assertTrue(g.scan_file('config.txt', text.encode()))

    def test_env_example_allows_placeholders_but_not_keys(self):
        self.assertEqual(g.scan_file('.env.example', b'OPENAI_API_KEY=YOUR_API_KEY\n'), [])
        self.assertTrue(g.scan_file('.env.example', ('OPENAI_API_KEY='+synthetic_key()).encode()))

    def test_fixture_exemption_is_exact_and_does_not_exempt_the_file(self):
        relative = 'skills/battle-scaling/tests/test_vision_adapter.py'
        path = s.PUBLICATION/relative
        self.assertEqual(g.scan_file(relative, path.read_bytes()), [])
        # Additional provider credentials in the same approved test still fail.
        self.assertTrue(g.scan_file(relative, path.read_bytes()+('\n# '+synthetic_key()).encode()))
        self.assertTrue(g.scan_file('other-test.py', path.read_bytes()))

    def test_private_contacts_and_paths_fail_without_numeric_false_positives(self):
        phone = '139'+'12345678'
        email = 'private-user'+'@'+'mail.invalid'
        user_path = 'C:'+'\\Users\\private-person\\work'
        for value in (phone, email, user_path):
            self.assertTrue(g.scan_file('notes.md', value.encode()))
        safe = 'sha256: '+hashlib.sha256(b'physics').hexdigest()+'\n12.13912345678 J\n'
        self.assertEqual(g.scan_file('physics.md', safe.encode()), [])

    def test_image_metadata_is_scanned(self):
        from PIL import Image, PngImagePlugin
        meta = PngImagePlugin.PngInfo()
        meta.add_text('note', synthetic_key())
        buf = io.BytesIO()
        Image.new('RGB', (2, 2)).save(buf, format='PNG', pnginfo=meta)
        self.assertTrue(g.scan_file('assets/template.png', buf.getvalue()))
        buf = io.BytesIO()
        Image.new('RGB', (2, 2)).save(buf, format='PNG')
        self.assertEqual(g.scan_file('assets/template.png', buf.getvalue()), [])

    def test_gps_metadata_and_unscannable_files_fail_closed(self):
        class DummyImage:
            info = {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def getexif(self): return {34853: 1}
        with patch('PIL.Image.open', return_value=DummyImage()):
            result = g.scan_file('photo.jpg', b'fixture')
        self.assertEqual(result[0]['error'], 'image_gps_metadata')
        self.assertTrue(g.scan_file('payload.bin', b'\x80\x00\xff'))

    def test_unlisted_secret_cannot_hide_behind_a_valid_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'README.md').write_text('safe', encoding='utf-8')
            manifest(root)
            self.assertTrue(g.audit(root)['valid'])
            (root/'extra.md').write_text(synthetic_key(), encoding='utf-8')
            result = g.audit(root)
            kinds = {e['error'] for e in result['errors']}
            self.assertIn('unlisted_upload_candidate', kinds)
            self.assertIn('provider_key', kinds)

    def test_unlisted_safe_file_also_fails_completeness(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest(root)
            (root/'new-doc.md').write_text('safe', encoding='utf-8')
            self.assertFalse(g.audit(root)['valid'])

    def test_changed_static_bytes_require_manifest_refresh(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'README.md').write_text('before', encoding='utf-8')
            manifest(root)
            (root/'README.md').write_text('after', encoding='utf-8')
            self.assertIn('distribution_hash_or_size_mismatch', {e['error'] for e in g.audit(root)['errors']})

    def test_missing_manifest_and_path_escape_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertFalse(g.audit(root)['valid'])
            (root/'docs').mkdir()
            (root/'docs/distribution-manifest.json').write_text(json.dumps({'files': {'../outside.md': {}}}), encoding='utf-8')
            self.assertIn('invalid_relative_path', {e['error'] for e in g.audit(root)['errors']})

    def test_tracked_ignored_files_are_scanned_untracked_ignored_files_are_not_uploads(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            git(root, 'init', '--quiet')
            (root/'.gitignore').write_text('runtime/\n', encoding='utf-8')
            (root/'runtime').mkdir()
            private = root/'runtime/local-tools.json'
            private.write_text('{}', encoding='utf-8')
            manifest(root)
            # The ignored runtime file must never be listed as static.
            whole = json.loads((root/'docs/distribution-manifest.json').read_text())
            whole['files'].pop('runtime/local-tools.json')
            (root/'docs/distribution-manifest.json').write_text(json.dumps(whole))
            self.assertTrue(g.audit(root)['valid'])
            git(root, 'add', '--force', '--', 'runtime/local-tools.json')
            result = g.audit(root)
            self.assertIn('confidential_file', {e['error'] for e in result['errors']})

    def test_standalone_directory_cannot_rely_on_gitignore(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'.gitignore').write_text('runtime/\n', encoding='utf-8')
            (root/'runtime').mkdir()
            (root/'runtime/local-tools.json').write_text('{}', encoding='utf-8')
            manifest(root)
            self.assertFalse(g.audit(root)['valid'])

    def test_gitignore_private_examples_with_nul_protocol(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            git(root, 'init', '--quiet')
            (root/'.gitignore').write_bytes((s.PUBLICATION/'.gitignore').read_bytes())
            paths = ['skills/battle-scaling/runtime/media-integrations.local.md',
                     'skills/battle-scaling/runtime/local-tools.json',
                     'skills/battle-scaling/data/media-sourcing/site-notes.jsonl',
                     'credentials.json', 'credential.dpapi', 'cookies.txt', '.env']
            for rel in paths:
                result = subprocess.run(['git', '-C', str(root), 'check-ignore', '--no-index', '--stdin', '-z'], input=rel.encode()+b'\0', capture_output=True)
                self.assertEqual(result.returncode, 0, rel)
            result = subprocess.run(['git', '-C', str(root), 'check-ignore', '--no-index', '--stdin', '-z'], input=b'.env.example\0', capture_output=True)
            self.assertEqual(result.returncode, 1)

    def test_payload_refuses_secret_before_writing_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill = root/'skill'; novel = root/'novel'; pub = root/'publication'
            for p in (skill/'scripts/combat_refpack', novel, pub/'tools', pub/'skills/battle-scaling/references'):
                p.mkdir(parents=True, exist_ok=True)
            (pub/'skills/battle-scaling/references/writing-experience.md').write_text(synthetic_key(), encoding='utf-8')
            (pub/'LICENSE').write_text('license fixture', encoding='utf-8')
            for name in ('sync_public.py', 'verify_package.py', 'publication_guard.py', 'test_publication_guard.py', 'test_public_sync.py', 'import_handbook_corpus.py', 'setup.py', 'test_setup.py', 'build_release.py', 'test_build_release.py'):
                (pub/'tools'/name).write_text('# fixture\n', encoding='utf-8')
            with patch.object(s, 'PUBLICATION', pub), patch.object(s, 'video_payload', return_value={}):
                with self.assertRaises(ValueError) as caught:
                    s.build_payload(skill, root/'video', novel, '1.21.0')
            self.assertNotIn(synthetic_key(), str(caught.exception))
            self.assertFalse((root/'target').exists())


if __name__ == '__main__':
    unittest.main()
