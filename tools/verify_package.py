"""Verify public static files, licensing exceptions and distribution boundaries."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
from sync_public import excluded,FORBIDDEN_SUFFIXES
from publication_guard import audit, linked, safe_relative

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=re.compile(r'(?:C:[/\\]+Users[/\\]+[^/\\\s]+[/\\]+\.codex|D:[/\\]+(?:论战专用|Codex|Deepseek工作区|BaiduNetdiskDownload)|E:[/\\]+外部待测论战skill)',re.I)

def verify(root):
    root=Path(root).resolve()
    privacy=audit(root)
    errors=list(privacy['errors'])
    skill=root/'skills/battle-scaling'
    manifest_path=skill/'package-manifest.json'
    try:
        if linked(manifest_path,root):raise ValueError()
        manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        if not isinstance(manifest.get('files'),dict):raise ValueError()
    except (OSError,ValueError,TypeError):
        errors.append({'path':'skills/battle-scaling/package-manifest.json','error':'missing_or_invalid_skill_manifest'})
        return {'valid':False,'errors':errors,'privacy':privacy}
    checked=[]
    for relative,expected in manifest['files'].items():
        path=(skill/relative).resolve()
        if not safe_relative(relative) or linked(skill/relative,root) or not path.is_relative_to(skill.resolve()):errors.append({'path':relative,'error':'outside_package'});continue
        if not path.is_file():errors.append({'path':relative,'error':'missing'});continue
        data=path.read_bytes();checked.append(path)
        if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:errors.append({'path':relative,'error':'hash_or_size_mismatch'})
        if excluded(relative) and relative!='references/writing-experience.md':errors.append({'path':relative,'error':'excluded_file_in_manifest'})
    for path in checked:
        if path.suffix in {'.md','.json','.yaml','.yml','.py','.ps1','.mjs','.ts','.tsx','.js','.html'}:
            text=path.read_text(encoding='utf-8-sig')
            if PRIVATE.search(text):errors.append({'path':path.relative_to(root).as_posix(),'error':'machine_specific_path'})
            if 'writing-excellent-examples.md' in text:errors.append({'path':path.relative_to(root).as_posix(),'error':'retired_writing_link'})
    high=skill/'data/wangba-handbook-2026-07-30/high-rules-curated.json'
    if high.is_file():
        data=json.loads(high.read_text(encoding='utf-8-sig'))
        if data.get('cases'):errors.append({'path':str(high.relative_to(root)),'error':'excluded_historical_cases'})
        if not data.get('rulesets') or not data.get('mathematical_bridges'):errors.append({'path':str(high.relative_to(root)),'error':'functional_rules_missing'})
    prompts=skill/'benchmarks/semantic-boundaries/prompts.json'
    if prompts.is_file():
        data=json.loads(prompts.read_text(encoding='utf-8-sig'))
        for source in data.get('sources',[]):
            if source.get('id') in {'scp-3143','scp-3812'} and not(all(source.get(k) for k in ('author','author_url','url')) and 'CC BY-SA 3.0' in source.get('license','')):
                errors.append({'path':str(prompts.relative_to(root)),'error':'scp_attribution_missing','source':source.get('id')})
    video=root/'tools/battle-video-studio'
    if video.exists():
        for p in video.rglob('*'):
            if not p.is_file() or 'node_modules' in p.parts or '__pycache__' in p.parts or '.cache' in p.parts:continue
            rel=p.relative_to(video).as_posix()
            if rel.startswith(('public/projects/','public/uploads/','public/music/','public/references/')) or p.suffix.lower() in FORBIDDEN_SUFFIXES:
                errors.append({'path':p.relative_to(root).as_posix(),'error':'user_media_or_runtime_in_distribution'})
        for required in ('licenses/Remotion-LICENSE.md','public/fonts/SmileySans-OFL.txt','public/fonts/SmileySans-Oblique.ttf','scripts/import-music.mjs','scripts/bootstrap.mjs'):
            if not (video/required).is_file():errors.append({'path':f'tools/battle-video-studio/{required}','error':'missing'})
    distribution=root/'docs/distribution-manifest.json';distribution_files=0
    if distribution.is_file() and not linked(distribution,root):
        try:
            whole=json.loads(distribution.read_text(encoding='utf-8-sig'))
            if not isinstance(whole.get('files'),dict):raise ValueError()
        except (OSError,ValueError,TypeError):
            return {'valid':False,'errors':errors,'privacy':privacy}
        distribution_files=len(whole['files'])
        prefix='skills/battle-scaling/'
        actual={rel[len(prefix):] for rel in whole['files'] if rel.startswith(prefix)}-{'package-manifest.json'}
        for rel in sorted(actual-set(manifest['files'])):errors.append({'path':prefix+rel,'error':'unlisted_skill_file'})
        for rel in sorted(set(manifest['files'])-actual):errors.append({'path':prefix+rel,'error':'skill_file_not_in_distribution'})
    return {'valid':not errors,'version':manifest.get('version'),'checked_files':len(checked),'distribution_files':distribution_files,'video_code_present':video.exists(),'privacy':{k:v for k,v in privacy.items() if k!='errors'},'errors':errors}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args()
    result=verify(args.root.resolve());print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['valid'] else 1

if __name__=='__main__':raise SystemExit(main())
