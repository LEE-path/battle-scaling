"""Build full and Skill-only ZIPs from the verified static distribution.

No Git commits, uploads or publishing. Runtime folders are never traversed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

from publication_guard import safe_relative, linked
from verify_package import verify

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write_archive(target, entries):
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(target) as archive:
        if set(archive.namelist()) != set(entries) or len(archive.namelist()) != len(entries):
            raise ValueError('Archive entry coverage differs from the planned distribution.')
        for name, data in entries.items():
            if archive.read(name) != data:
                raise ValueError('Archive bytes differ from the verified input: '+name)
    return {'name': target.name, **digest(target.read_bytes()), 'entries': len(entries)}


def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError('Release assets must be written outside the repository/distribution tree.')
    checked = verify(root)
    if not checked['valid']:
        raise ValueError('Distribution verification failed: '+json.dumps(checked['errors'], ensure_ascii=False))
    whole = json.loads((root/'docs/distribution-manifest.json').read_text(encoding='utf-8-sig'))
    skill = json.loads((root/'skills/battle-scaling/package-manifest.json').read_text(encoding='utf-8-sig'))
    version = whole['version']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-.][A-Za-z0-9.-]+)?', version) or skill['version'] != version:
        raise ValueError('Release versions must match and be filename-safe.')
    full_entries = {}
    for relative, expected in whole['files'].items():
        path = root/relative
        if not safe_relative(relative) or linked(path, root) or not path.resolve().is_relative_to(root):
            raise ValueError('Unsafe distribution member.')
        data = path.read_bytes()
        if digest(data) != expected:
            raise ValueError('Source changed since verification: '+relative)
        full_entries['battle-scaling/'+relative] = data
    full_entries['battle-scaling/docs/distribution-manifest.json'] = (root/'docs/distribution-manifest.json').read_bytes()
    skill_entries = {}
    for relative, expected in skill['files'].items():
        data = full_entries['battle-scaling/skills/battle-scaling/'+relative]
        if digest(data) != expected:
            raise ValueError('Skill and full manifests disagree: '+relative)
        skill_entries['battle-scaling/'+relative] = data
    skill_entries['battle-scaling/package-manifest.json'] = (root/'skills/battle-scaling/package-manifest.json').read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    names = [f'battle-scaling-v{version}.zip', f'battle-scaling-skill-v{version}.zip', 'SHA256SUMS.txt']
    if any((output/name).exists() for name in names):
        raise ValueError('Choose a fresh release output directory; existing artifacts are preserved.')
    results = [write_archive(output/names[0], full_entries), write_archive(output/names[1], skill_entries)]
    (output/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in results), encoding='ascii')
    return {'version': version, 'output': str(output), 'archives': results,
            'note': 'Full ZIP includes installation tools and video project; Skill-only ZIP does not include that external project.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.out), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
