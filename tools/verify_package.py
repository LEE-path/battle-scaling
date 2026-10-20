"""Verify exactly the static files shipped in this public Skill package."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'battle-scaling'

def main():
    manifest=json.loads((SKILL/'package-manifest.json').read_text(encoding='utf-8-sig'))
    errors=[]
    for relative, expected in manifest['files'].items():
        path=(SKILL/relative).resolve()
        if not path.is_relative_to(SKILL.resolve()):
            errors.append({'path':relative,'error':'outside_package'})
            continue
        if not path.is_file():
            errors.append({'path':relative,'error':'missing'})
            continue
        data=path.read_bytes()
        if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:
            errors.append({'path':relative,'error':'hash_or_size_mismatch'})
    result={'valid':not errors,'version':manifest['version'],'checked_files':len(manifest['files']),'errors':errors}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if not errors else 1

if __name__=='__main__':
    sys.exit(main())
