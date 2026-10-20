#!/usr/bin/env python3
"""Import one explicitly supplied local OCR corpus; never download or change rules."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

DATA_RELATIVE = Path('data/wangba-handbook-2026-07-30')
DEFAULT_SKILL_ROOT = Path(__file__).resolve().parents[1]/'skills/battle-scaling'


def import_corpus(source_dir, skill_root=DEFAULT_SKILL_ROOT):
    """Install only pages.jsonl after checking the installed, locked manifest."""
    source_value = str(source_dir)
    if source_value.startswith(('\\\\', '//')) or '://' in source_value:
        raise ValueError('source-dir must be an explicit local directory, not a URL or network share')
    source = Path(source_dir).resolve(strict=True)
    if not source.is_dir():
        raise ValueError('source-dir must be a directory containing pages.jsonl')
    incoming = source/'pages.jsonl'
    if incoming.is_symlink() or not incoming.is_file():
        raise ValueError('source-dir must contain a regular pages.jsonl file')
    root = Path(skill_root).resolve(strict=True)
    data = root/DATA_RELATIVE
    manifest_file = data/'manifest.json'
    manifest_raw = manifest_file.read_bytes()
    manifest = json.loads(manifest_raw.decode('utf-8'))
    expected = manifest.get('corpus_sha256')
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('installed manifest must contain a locked corpus_sha256')
    payload = incoming.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError('source corpus hash mismatch; no files or selected rules were changed')
    pages = [json.loads(line) for line in payload.decode('utf-8').splitlines() if line.strip()]
    if len(pages) != manifest.get('page_count'):
        raise ValueError('source corpus page count differs from the installed manifest')
    numbers = [p.get('sequence_page') for p in pages]
    if any(isinstance(n, bool) or not isinstance(n, int) for n in numbers) or sorted(numbers) != list(range(1, len(pages)+1)):
        raise ValueError('source corpus must contain each locked sequence page exactly once')
    destination = data/'pages.jsonl'
    if destination.is_symlink():
        raise ValueError('refusing to import through a destination symlink')
    result = {'status':'installed', 'document_id':manifest['document_id'],
              'corpus_sha256':actual, 'pages':len(pages), 'bytes':len(payload),
              'destination':str(destination), 'download_performed':False,
              'rule_version_changed':False}
    if destination.exists():
        if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
            raise ValueError('refusing to replace an existing different corpus; inspect it explicitly')
        return {**result, 'status':'already_installed'}
    # A same-directory temporary file plus hard-link publishes the complete bytes
    # without overwriting a destination created by another process.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.corpus-import-', suffix='.tmp', dir=data, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if manifest_file.read_bytes() != manifest_raw:
            raise ValueError('installed manifest changed during import; retry after inspection')
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
        raise ValueError('installed corpus failed read-back verification; inspect destination')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', required=True, help='Your authorized local directory containing the exact pages.jsonl')
    parser.add_argument('--skill-root', default=str(DEFAULT_SKILL_ROOT), help='Installed battle-scaling directory; defaults to this repository skill')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(import_corpus(args.source_dir, args.skill_root), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'status':'error', 'error':str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
