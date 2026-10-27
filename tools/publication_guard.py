"""Offline release-only privacy scan and complete static inventory check.

Diagnostics contain locations and classifications, never matched values.
This module does not read credentials outside the supplied package, contact
providers, inspect Git history, delete runtime data or change Git tracking.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

METADATA = {'docs/distribution-manifest.json', 'docs/sync-summary.json'}
CACHE_PARTS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.cache', 'python_libs'}
TEXT_SUFFIXES = {'.md', '.txt', '.json', '.jsonl', '.yaml', '.yml', '.toml',
    '.ini', '.cfg', '.conf', '.config', '.env', '.py', '.js', '.mjs', '.cjs',
    '.ts', '.tsx', '.jsx', '.ps1', '.psm1', '.cmd', '.bat', '.sh', '.css',
    '.html', '.xml', '.svg', '.csv', '.lock', '.log', '.map', '.sql', '.rst', ''}
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.avif', '.tif', '.tiff'}
MAX_SCAN_BYTES = 64 * 1024 * 1024
SENSITIVE_NAME = re.compile(r'^(?:cookies?\.(?:txt|json)|(?:credentials?|tokens?|auth|secrets?)\.(?:json|ya?ml|toml)|id_rsa|id_ed25519|\.npmrc|\.pypirc)$', re.I)

# Exact, reviewed, loopback test literals only. No directory-wide exemption.
# Each entry is (relative path, finding kind, SHA256 of the captured value).
REVIEWED_FIXTURES = {
    ('skills/battle-scaling/tests/test_vision_adapter.py', 'credential_literal',
     'b3c53c08828847f11b3083a5b1fa83ddf6751112653f0fd9d563754092ec65f7'),
    ('skills/battle-scaling/tests/test_vision_adapter.py', 'bearer_literal',
     'b3c53c08828847f11b3083a5b1fa83ddf6751112653f0fd9d563754092ec65f7'),
    ('skills/battle-scaling/tests/test_site_registry.py', 'url_credentials',
     'e0f9334d61a8b8b13f0b2863bd438e840508dcb387487fe91e044dfd874a0ea5'),
    ('skills/battle-scaling/tests/test_sources.py', 'url_credentials',
     '15b1851243b6887ef198fb5dae6d37c8e52fbf55466c3774a8e92df54eee5c1f'),
    ('skills/battle-scaling/tests/test_vision_adapter.py', 'url_credentials',
     'c8463db03ad18d871afe17cdba9aeffbff28ff6fa75d2245bd389686b8b6e62b'),
}
# Public upstream author contacts are reviewed by exact address fingerprint;
# these are not user contacts and must remain in license/provenance notices.
REVIEWED_CONTACTS = {
    ('tools/battle-video-studio/public/fonts/SmileySans-Oblique.ttf',
     'db00f782d951acd164ff110080c15090e02f0746974cf2fc9b24498aac75d20b'),
    ('skills/battle-scaling/assets/media/fonts/SmileySans-Oblique.ttf',
     'db00f782d951acd164ff110080c15090e02f0746974cf2fc9b24498aac75d20b'),
}

PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'provider_key': re.compile(r'\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{25,}|glpat-[A-Za-z0-9_-]{16,}|(?:AKIA|ASIA)[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,}|hf_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{16,})\b'),
    'jwt': re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'),
    'credential_literal': re.compile(r'''["']?\b(?:[A-Za-z_][A-Za-z0-9_.-]*?(?:API[_-]?KEY|ACCESS[_-]?KEY(?:[_-]?ID)?|SECRET[_-]?KEY|PRIVATE[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD)|api[_-]?key|apikey|access[_-]?key|secret[_-]?key|private[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|passwd|authorization|cookie|SESSDATA|bili_jct|DedeUserID|BDUSS|STOKEN|SKEY|_authToken|secret|token)\b["']?\s*[:=]\s*["']([^"'\r\n]{1,400})["']''', re.I),
    'unquoted_credential': re.compile(r'(?im)^\s*(?:export\s+|\$env:)?(?=[A-Za-z_])[A-Za-z0-9_]*(?:API_KEY|ACCESS_KEY(?:_ID)?|SECRET_KEY|PRIVATE_KEY|TOKEN|SECRET|PASSWORD|PASSWD)\s*(?:=|:[ \t]+)\s*([A-Za-z0-9_+./:@?%&=${}<>-]+)[ \t]*(?:#[^\r\n]*)?$'),
    'bearer_literal': re.compile(r'\bBearer\s+([A-Za-z0-9_.=-]{8,})\b', re.I),
    'url_credentials': re.compile(r'https?://[^\s/@:"\']{1,100}:[^/@\s"\']{1,200}@[^/\s"\'<>]+', re.I),
    'url_auth_query': re.compile(r'[?&](?:api[_-]?key|access[_-]?key|secret[_-]?key|access_token|refresh_token|token|auth|auth_key|signature|sig|sign|x-amz-security-token|x-amz-credential|x-amz-signature|SESSDATA|bili_jct)=([^&#\s"\'<>]+)', re.I),
    'windows_user_path': re.compile(r'\b[A-Z]:[/\\]+Users[/\\]+[^/\\\s"<>`|;,()\[\]]+', re.I),
    'private_workspace_path': re.compile(r'\b(?:D:[/\\]+(?:论战专用|Deepseek工作区|BaiduNetdiskDownload|Codex)|E:[/\\]+(?:外部待测论战skill|AI))(?=[/\\])', re.I),
    'wechat_identity': re.compile(r'\bwxid_[A-Za-z0-9_]{5,}\b'),
    'clipboard_reference': re.compile(r'codex-clipboard-[a-f0-9-]{20,}', re.I),
    'email': re.compile(r'(?<![\w.+-])[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+'),
    'phone': re.compile(r'(?<![A-Za-z0-9_.+-])(?:\+?86[- ]?)?1[3-9]\d{9}(?![A-Za-z0-9_.])'),
    'identity_number': re.compile(r'(?<![A-Za-z0-9_.])[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![A-Za-z0-9_.])'),
    'private_session_id': re.compile(r'''["'](?:thread_id|conversation_id|rollout_id)["']\s*:\s*["']([0-9a-f-]{32,36})["']''', re.I),
}


def confidential_path(relative):
    p = PurePosixPath(relative.replace('\\', '/').lower())
    name = p.name
    return (bool(set(p.parts) & {'runtime', 'credentials', '.ssh'})
        or any('/'.join(p.parts[i:i+2]) in {'data/site-experience', 'data/media-sourcing'} for i in range(len(p.parts)-1))
        or bool(SENSITIVE_NAME.fullmatch(name))
        or (name.startswith('.env') and name != '.env.example')
        or bool(re.search(r'\.local\.(?:json|ya?ml|toml|md)$', name))
        or p.suffix in {'.dpapi', '.pem', '.key', '.pfx', '.p12', '.kdbx', '.keystore', '.jks'})


def safe_relative(relative):
    p = PurePosixPath(relative)
    return (bool(relative) and bool(p.parts) and not p.is_absolute() and '\\' not in relative
            and ':' not in relative and not any(part in {'..', '.'} for part in p.parts)
            and p.as_posix() == relative)


def linked(path, root):
    # Reject junctions as well as symlinks, including a linked parent folder.
    for p in (path, *path.parents):
        if p == root:
            break
        if p.is_symlink() or (p.exists() and getattr(p.lstat(), 'st_file_attributes', 0) & 0x400):
            return True
    return False


def inventory(root):
    root = Path(root).resolve()
    try:
        probe = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], capture_output=True)
    except FileNotFoundError:
        probe = None
    if (root/'.git').exists() and (probe is None or probe.returncode):
        raise ValueError('git_inventory_failed')
    if probe is not None and probe.returncode == 0 and Path(os.fsdecode(probe.stdout).strip()).resolve() == root:
        paths = set()
        for args in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
            result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
            if result.returncode:
                raise ValueError('git_inventory_failed')
            paths.update(v.decode('utf-8') for v in result.stdout.split(b'\0') if v)
        return sorted(paths), 'git_tracked_and_untracked_not_ignored'
    files = []
    for folder, dirs, names in os.walk(root, followlinks=False):
        for name in list(dirs):
            p = Path(folder)/name
            if p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400:
                files.append(p.relative_to(root).as_posix())
                dirs.remove(name)
            elif name in CACHE_PARTS:
                dirs.remove(name)
        files.extend((Path(folder)/name).relative_to(root).as_posix() for name in names)
    return sorted(files), 'standalone_static_directory'


def placeholder(value):
    value = value.strip()
    if value.lower() in {'', 'none', 'null', 'true', 'false', 'redacted', 'placeholder',
            'api_key', 'apikey', 'token', 'secret', 'password', 'passwd', 'bearer',
            'sessdata', 'bili_jct', 'token_value', 'not-a-key', 'sk-xxx'}:
        return True
    return bool(re.fullmatch(r'(?:<[^<>\r\n]+>|\$\{[A-Z_][A-Z0-9_]*\}|\{\{[^{}]+\}\}|YOUR_[A-Z_]+|your[-_](?:api[-_])?(?:key|token|password))', value))


def scan_text(relative, text):
    errors = []
    # Decode JSON string escapes as well: a literal hidden with \uXXXX still
    # needs review. Retain the original line number of the enclosing string.
    views = [(text, None)]
    string_pattern = re.compile(r'"(?:[^"\\]|\\.)*"')
    def decode_string(m):
        try:
            return json.dumps(json.loads(m[0]), ensure_ascii=False)
        except ValueError:
            return m[0]
    decoded = string_pattern.sub(decode_string, text)
    if decoded != text:
        views.append((decoded, None))
    for m in string_pattern.finditer(text):
        if '\\' in m[0]:
            try:
                value = json.loads(m[0])
            except (ValueError, TypeError):
                continue
            if isinstance(value, str) and value != m[0][1:-1]:
                views.append((value, text.count('\n', 0, m.start())+1))
    for view, enclosing_line in views:
        for kind, pattern in PATTERNS.items():
            for m in pattern.finditer(view):
                value = m.group(1) if m.lastindex else m[0]
                if kind == 'credential_literal' and not any(c.isalnum() for c in value):
                    continue
                if kind in {'credential_literal', 'unquoted_credential', 'bearer_literal', 'url_auth_query'} and placeholder(value):
                    continue
                fingerprint = hashlib.sha256(value.encode()).hexdigest()
                if (relative, kind, fingerprint) in REVIEWED_FIXTURES:
                    continue
                if kind == 'email':
                    domain = value.rsplit('@', 1)[-1].lower()
                    if domain in {'example.com', 'example.org', 'example.net', 'users.noreply.github.com', 'noreply.github.com'} or (relative, fingerprint) in REVIEWED_CONTACTS:
                        continue
                errors.append({'path': relative, 'line': enclosing_line or view.count('\n', 0, m.start())+1, 'error': kind})
    return list({(e['path'], e['line'], e['error']): e for e in errors}.values())


def scan_file(relative, data):
    if confidential_path(relative):
        return [{'path': relative, 'error': 'confidential_file'}]
    if len(data) > MAX_SCAN_BYTES:
        return [{'path': relative, 'error': 'file_exceeds_scan_limit'}]
    suffix = PurePosixPath(relative).suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                metadata = {str(k): str(v) for k, v in image.info.items() if k not in {'icc_profile', 'exif'}}
                exif = image.getexif()
                for k, v in exif.items():
                    if k == 34853:
                        return [{'path': relative, 'error': 'image_gps_metadata'}]
                    metadata['exif_'+str(k)] = str(v)
                errors = scan_text(relative, json.dumps(metadata, ensure_ascii=False))
            # Metadata access can consume the PNG stream; verify a fresh handle.
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            return errors
        except ImportError:
            return [{'path': relative, 'error': 'image_scan_requires_Pillow'}]
        except Exception:
            return [{'path': relative, 'error': 'image_metadata_unreadable'}]
    if suffix in {'.ttf', '.otf', '.woff', '.woff2'}:
        # Preserve licensed fonts. Check embedded ASCII strings for credentials;
        # image/font rendering itself remains a visual release review.
        text = '\n'.join(x.decode('ascii') for x in re.findall(rb'[\x20-\x7e]{8,}', data))
        return scan_text(relative, text)
    try:
        text = data.decode('utf-16') if data.startswith((b'\xff\xfe', b'\xfe\xff')) else data.decode('utf-8-sig')
        if '\0' in text:
            raise UnicodeError()
    except UnicodeError:
        return [{'path': relative, 'error': 'unscannable_binary'}]
    return scan_text(relative, text)


def scan_payload(files):
    errors = []
    for relative, data in sorted(files.items()):
        if not safe_relative(relative):
            errors.append({'path': relative, 'error': 'invalid_relative_path'})
        else:
            errors.extend(scan_file(relative, data))
    return errors


def audit(root):
    root = Path(root).resolve()
    errors = []
    try:
        candidates, mode = inventory(root)
    except (OSError, ValueError, UnicodeError):
        return {'valid': False, 'errors': [{'path': '.', 'error': 'inventory_failed'}]}
    manifest_path = root/'docs/distribution-manifest.json'
    try:
        if linked(manifest_path, root):
            raise ValueError()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))['files']
        if not isinstance(manifest, dict) or not all(isinstance(k,str) for k in manifest):
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError):
        manifest = {}
        errors.append({'path': 'docs/distribution-manifest.json', 'error': 'missing_or_invalid_distribution_manifest'})
    candidate_set = set(candidates)
    for relative in sorted(candidate_set - set(manifest) - METADATA):
        errors.append({'path': relative, 'error': 'unlisted_upload_candidate'})
    for relative in sorted(set(manifest) - candidate_set):
        errors.append({'path': relative, 'error': 'manifest_file_not_in_upload_candidates'})
    for relative in sorted(candidate_set | set(manifest)):
        if not safe_relative(relative):
            errors.append({'path': relative, 'error': 'invalid_relative_path'})
            continue
        path = root/relative
        if linked(path, root) or not path.resolve().is_relative_to(root):
            errors.append({'path': relative, 'error': 'linked_or_outside_file'})
            continue
        if not path.is_file():
            errors.append({'path': relative, 'error': 'missing_file'})
            continue
        try:
            data = path.read_bytes()
        except OSError:
            errors.append({'path': relative, 'error': 'unreadable_file'})
            continue
        errors.extend(scan_file(relative, data))
        if relative in manifest:
            expected = manifest[relative]
            if not isinstance(expected, dict) or len(data) != expected.get('bytes') or hashlib.sha256(data).hexdigest() != expected.get('sha256'):
                errors.append({'path': relative, 'error': 'distribution_hash_or_size_mismatch'})
    return {'valid': not errors, 'inventory_mode': mode, 'upload_candidates': len(candidates),
            'manifest_files': len(manifest), 'metadata_exceptions': sorted(METADATA), 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    result = audit(parser.parse_args().root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
