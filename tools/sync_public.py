"""Build a distribution copy without modifying sources or runtime libraries.

Use --apply to write the explicitly selected target. No network or Git actions.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from publication_guard import confidential_path, scan_payload

PUBLICATION = Path(__file__).resolve().parents[1]
TEXT = {'.md','.txt','.json','.yaml','.yml','.py','.ps1','.cmd','.mjs','.js','.ts','.tsx','.css','.html'}
FORBIDDEN_PARTS = {'__pycache__','.git','.cache','node_modules','.venv','venv','models','weights','runs','outputs','work','runtime','credentials','.ssh'}
FORBIDDEN_SUFFIXES = {'.pyc','.pyo','.sqlite','.sqlite3','.db','.pdf',
    '.mp4','.m4a','.mp3','.wav','.aac','.mkv','.webm','.mov','.avi','.wmv','.m4v','.mpeg','.mpg','.ogv','.m2ts','.vob',
    '.ogg','.oga','.opus','.flac','.aif','.aiff','.wma','.alac',
    '.safetensors','.onnx','.pt','.pth','.gguf','.ckpt','.h5','.hdf5','.tflite',
    '.pem','.key','.pfx','.p12','.keystore','.jks','.zip','.rar','.7z'}
SOURCE_LOCATOR_FIELDS = {'global','vol','local','printed','viewed','page_id','printed_no','printed_no_visual','printed_no_basis'}

def dumps(value):
    return json.dumps(value,ensure_ascii=False,indent=2)+'\n'

def digest(data):
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def excluded(relative: str, kind='skill'):
    p=Path(relative);parts=set(p.parts);name=p.name.lower()
    if confidential_path(relative):return True
    if parts & FORBIDDEN_PARTS or p.suffix.lower() in FORBIDDEN_SUFFIXES:return True
    if name in {'.npmrc','.pypirc','.ds_store','thumbs.db','cookies.txt','cookies.json','credentials.json','auth.json','credential.json','credentials.dpapi','token.json','tokens.json'}:return True
    if name.startswith('.env') and name!='.env.example' or name.endswith(('.local.json','.log','.part')):return True
    if kind=='skill':
        return (relative.startswith(('runtime/','data/site-experience/','data/media-sourcing/','assets/writing-examples/'))
            or relative in {'package-manifest.json','references/writing-excellent-examples.md','references/writing-experience.md','tests/acceptance-last-run.json','assets/cases/captain-contact.png','data/wangba-handbook-2026-07-30/pages.jsonl'}
            or relative.startswith(('assets/handbook-review/','assets/formula-ocr-validation/')) and p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'})
    if kind=='novel':return relative=='tests/acceptance-last-run.json'
    return False

def private_path(value):
    # Same source-root boundaries used by the preceding publication sanitizer.
    rules=[(r'C:[/\\]+Users[/\\]+[^/\\\s]+[/\\]+\.codex[/\\]+skills[/\\]+battle-scaling','SKILL_ROOT'),
      (r'D:[/\\]+BaiduNetdiskDownload[/\\]+汪峰在吧量级册','LOCAL_REFERENCE_ROOT'),
      (r'D:[/\\]+Deepseek工作区','LOCAL_UPSTREAM_ROOT'),
      (r'D:[/\\]+Codex[/\\]+research[/\\]+battle-scaling','LOCAL_RESEARCH_ROOT'),
      (r'D:[/\\]+论战专用','LOCAL_BATTLE_WORKSPACE'),
      (r'E:[/\\]+外部待测论战skill','LOCAL_EXTERNAL_RESEARCH_ROOT'),
      (r'D:[/\\]+AI','LOCAL_TOOL_ROOT'),(r'D:[/\\]+Codex','LOCAL_WORKSPACE'),
      (r'C:[/\\]+Users[/\\]+[^/\\\s`\"<>|]+','LOCAL_USER_ROOT')]
    for pattern,replacement in rules:value=re.sub(pattern,lambda _:replacement,value,flags=re.I)
    return re.sub(r'((?:SKILL_ROOT|LOCAL_[A-Z_]+)(?:[/\\]+[^\s`\"<>|]*)?)',lambda m:re.sub(r'[/\\]+','/',m[0]),value)

def strings(value,func):
    if isinstance(value,dict):return {k:strings(v,func) for k,v in value.items()}
    if isinstance(value,list):return [strings(v,func) for v in value]
    return func(value) if isinstance(value,str) else value

def strip_quotes(value):
    if isinstance(value,dict):return {k:strip_quotes(v) for k,v in value.items() if not(k in {'short_quote','short_excerpt'} and isinstance(v,str) and len(v)>25)}
    if isinstance(value,list):return [strip_quotes(v) for v in value]
    return value

def public_markdown(text):
    text=private_path(text).replace('writing-excellent-examples.md','writing-experience.md')
    def link(m):
        label,destination=m.groups();target=destination.replace('\\','/')
        if any(v in target for v in ('assets/handbook-review/','assets/formula-ocr-validation/','assets/cases/captain-contact.png')):
            return label+'（原图需自行提供，按页号核对）'
        if re.match(r'<?(?:SKILL_ROOT|LOCAL_[A-Z_]+)(?:/|>)',target):return label+'（来源定位标识）'
        return m[0]
    return re.sub(r'!?\[([^\]]+)\]\(([^)]+)\)',link,text)

def transform(relative,data):
    suffix=Path(relative).suffix.lower()
    if suffix not in TEXT:return data
    text=data.decode('utf-8-sig')
    if suffix=='.json':
        value=json.loads(text)
        if relative.endswith('data/wangba-handbook-2026-07-30/high-rules-curated.json'):
            functional={k:value.get(k) for k in ('rulesets','mathematical_bridges')}
            value['page_inventory']=[{k:v for k,v in row.items() if k in SOURCE_LOCATOR_FIELDS} for row in value.get('page_inventory',[])]
            value['cases']=[]
            value['publication_note']='Functional rules, mathematical bridges, source page locators and source fingerprints retained.'
            assert functional=={k:value.get(k) for k in functional},'Functional rule content changed'
        if 'wangba-handbook-2026-07-30/' in relative or '/rating-fixtures/' in relative:value=strip_quotes(value)
        value=strings(value,private_path)
        if relative.endswith('assets/media/source-catalog.json'):
            for key in ('sources','sites'):
                for row in value.get(key,[]):
                    for field in ('status','result'):row.pop(field,None)
            for row in value.get('tools',[]):row.pop('status',None)
        if relative.endswith('benchmarks/semantic-boundaries/prompts.json'):
            urls={'scp-3143':'https://www.wikidot.com/user:info/the-great-hippo','scp-3812':'https://scp-wiki.wikidot.com/djkaktus'}
            for row in value.get('sources',[]):
                if row.get('id') in urls:row['author_url']=row.get('author_url') or urls[row['id']]
        return dumps(value).encode()
    text=public_markdown(text)
    if relative.endswith('references/handbook-high-review.md'):
        text=text.split('## 三案例实际提供了什么',1)[0].split('## 公开副本的来源边界',1)[0].rstrip()
        text+='\n\n## 来源使用\n\n本页保留具名规则、数学桥、条件、页码及原件指纹；原页核验需自行提供匹配原件。案例研究按[高层实战案例](high-tier-cases.md)独立搜证。\n'
    if relative.endswith('references/writing-entry.md'):
        text=re.sub(r'^\*\*优秀文本范例\*\*：.*$', '**可复用写作经验**：按当前难点选读[写作经验](writing-experience.md)，处理动作、能力反馈、人物选择、组合衔接和战后收束；不把创作战果作为原作证据。',text,flags=re.M)
        text=text.replace('专门参考与优秀全文','专门参考与可复用写作经验')
    if relative.endswith('references/writing-battle.md'):
        text=re.sub(r'^写作与核稿按需使用.*$', '写作与核稿按需使用[可复用写作经验](writing-experience.md)，按当前问题选择入场、人物声线、动作空间、反馈换招、能力组合、认知控制、幽默与完整收束的方法；不以写法替代原作核对与能力结算。',text,flags=re.M)
    if relative.endswith('references/novel-evidence.md'):
        text=re.sub(r'^本次 2026-10-20 实机核查的 .*?该书包只是本次本地审计样本，不能从此推断其他包都经过同样改写。$',
            '**文件齐全检查通过，不等于原作结尾正确，也不等于原版已被读完。** 对任何书包都应核对原件目录、末章、派生摘要与所选版本；发现删改、续写或结局冲突时分别记录，不能把工作版本当成原版。',text,flags=re.M)
    if relative.endswith('tools/combat-novel-refpack/README.md'):
        text=text.split('## 实际验收',1)[0].rstrip()+'\n\n## 测试\n\n```powershell\npython -X utf8 -m unittest discover -s tests -v\n```\n\n测试检查实现行为；不代替宿主实际阅读原文和语义复核。\n'
        text=text.replace('给常态主档和九维卡','给综合主档和九维卡')
        text=text.replace("'D:\\小说\\原文.epub'","'book.epub'")
        text=re.sub(r"'LOCAL_BATTLE_WORKSPACE/[^']*作品-版本'","'runs/book'",text)
    text=text.replace('[用户认可范例索引]','[可复用写作经验]').replace('[优秀文本范例]','[可复用写作经验]')
    if suffix=='.md':text=text.rstrip()+'\n'
    return text.encode()

def write_if_changed(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise ValueError('Refusing to overwrite a symbolic link')
    if path.exists() and path.read_bytes()==data:return False
    path.write_bytes(data);return True

def safe_target(target,sources):
    target=target.resolve()
    normalized=target.as_posix().lower()
    if any(x in normalized for x in ('/.codex/skills','/.agents/skills','/.dsh/skills')):raise ValueError('Target must be a distribution copy, not an installed Skill')
    for source in sources:
        if source.resolve()==target or source.resolve().is_relative_to(target) or target.is_relative_to(source.resolve()):raise ValueError('Source and target trees must be separate')
    if target.exists() and any(p.is_symlink() or not p.resolve().is_relative_to(target) for p in target.rglob('*')):raise ValueError('Target contains links outside its tree; use an isolated target')
    return target

def video_payload(source):
    files={}
    roots=('src/','templates/','workbench/','tests/')
    scripts={'prepare-job.mjs','select-template.mjs','render-job.mjs','review-video.mjs','server.mjs','bootstrap.mjs','import-music.mjs'}
    top={'package.json','package-lock.json','tsconfig.json','.gitignore','LICENSE','THIRD_PARTY_NOTICES.md','打开剪辑工作台.cmd','打开剪辑工作台.ps1','关闭剪辑工作台.ps1'}
    for path in sorted(source.rglob('*')):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):continue
        rel=path.relative_to(source).as_posix()
        allow=(rel in top or rel.startswith(roots) and not rel.startswith(('src/motion-lab/','src/motion-full/'))
            or rel.startswith('scripts/') and path.name in scripts
            or rel in {'data/video-presets.json','data/video-defaults.json','data/vs-layout.json','data/starter-job.json','docs/media-planning-api.md'}
            or rel.startswith(('public/fonts/','public/media/vs/','public/media/branding/')))
        if not allow or any(v in path.relative_to(source).parts for v in FORBIDDEN_PARTS):continue
        data=path.read_bytes()
        if path.suffix.lower() in TEXT:data=transform(rel,data)
        files[rel]=data
    root=files['src/Root.tsx'].decode()
    root=re.sub(r"import \{(?:MotionLabCompositions|FullMotionCompositions)\}[^\n]*\n",'',root)
    root=root.replace('<MotionLabCompositions/><FullMotionCompositions/>','')
    files['src/Root.tsx']=root.encode()
    preset=json.loads(files['data/video-presets.json'])
    for p in preset.values():
        p['title']['names']=[];p['ending']['winner']=None;p['ending'].pop('winnerText',None);p['segments']=[];p['plate']=''
    files['data/video-presets.json']=dumps(preset).encode()
    for rel in list(files):
        if rel.startswith('templates/'):
            t=json.loads(files[rel]);t['reference']=f"{t['id']} music timing preset"
            for slot in t.get('slots',[]):slot.pop('original_reveal',None)
            files[rel]=dumps(t).encode()
    example={'id':'new-battle','mode':'media-demo','templateId':'V09','characters':{'a':{'name':'A','clips':[]},'b':{'name':'B','clips':[]}},'comparisons':[{'label':s['original_label'],'winner':'tie'} for s in json.loads(files['templates/V09.json'])['slots'] if s['original_role']!='verdict'],'verdict':{'winner':'tie','subtitle':'Editing demonstration; enter your own researched result.'}}
    files['examples/reference-demo.json']=dumps(example).encode()
    remotion=source/'node_modules/remotion/LICENSE.md'
    if not remotion.is_file():raise ValueError('Installed Remotion LICENSE.md is required for the license notice copy')
    files['licenses/Remotion-LICENSE.md']=remotion.read_bytes()
    overlays=PUBLICATION/'tools/public-video'
    for path in overlays.rglob('*'):
        if path.is_file():files[path.relative_to(overlays).as_posix()]=path.read_bytes().replace(b'(../battle-video-studio/',b'(')
    return files

def build_payload(skill_source,video_source,novel_source,version):
    files={};counts={'skill':0,'novel':0};omitted={'skill':0,'novel':0}
    for kind,source,prefix in [('skill',skill_source,'skills/battle-scaling/'),('novel',novel_source,'tools/combat-novel-refpack/')]:
        for p in sorted(source.rglob('*')):
            if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(source.resolve()):continue
            rel=p.relative_to(source).as_posix()
            if kind=='novel' and rel.startswith('combat_refpack/'):omitted[kind]+=1;continue
            if excluded(rel,kind):omitted[kind]+=1;continue
            files[prefix+rel]=transform(prefix+rel,p.read_bytes());counts[kind]+=1
    # One module authority for both entry points. D05 supplies the independent
    # wrapper/docs/tests; it cannot reintroduce an older fork of the core.
    counts['novel_core']=0
    for p in sorted((skill_source/'scripts/combat_refpack').glob('*.py')):
        files['tools/combat-novel-refpack/combat_refpack/'+p.name]=transform('tools/combat-novel-refpack/combat_refpack/'+p.name,p.read_bytes())
        counts['novel_core']+=1
    # The independently written methods document is maintained in this public
    # repository. Preserve its exact bytes, including existing local edits.
    writing=PUBLICATION/'skills/battle-scaling/references/writing-experience.md'
    if not writing.is_file():raise ValueError('The publication writing-experience.md must exist')
    files['skills/battle-scaling/references/writing-experience.md']=writing.read_bytes()
    for rel,data in video_payload(video_source).items():files['tools/battle-video-studio/'+rel]=data
    for name in ('NOTICE.md','THIRD_PARTY_NOTICES.md'):
        public=PUBLICATION/'skills/battle-scaling'/name
        if public.is_file():
            notice=public.read_text(encoding='utf-8-sig')
            if 'Semantic benchmark SCP adaptations' not in notice:
                notice+='\n\n## Semantic benchmark SCP adaptations\n\n`benchmarks/semantic-boundaries/` includes short excerpts, Chinese paraphrases and adapted questions based on [SCP-3143](https://scp-wiki.wikidot.com/scp-3143) by [The Great Hippo](https://www.wikidot.com/user:info/the-great-hippo) and [SCP-3812](https://scp-wiki.wikidot.com/scp-3812) by [djkaktus](https://scp-wiki.wikidot.com/djkaktus). These SCP-derived portions and their adaptations use [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); they are not MIT. Changes: short selection, Chinese paraphrase, contextual summary and adversarial question/rubric design. No SCP images or complete stories are bundled.\n'
            files['skills/battle-scaling/'+name]=notice.encode()
    public_test=PUBLICATION/'skills/battle-scaling/tests/test_optional_handbook.py'
    if public_test.is_file():files['skills/battle-scaling/tests/test_optional_handbook.py']=public_test.read_bytes()
    # Reviewed distribution helpers can exist only in this repository. They
    # remain static, scanned and covered, rather than silently falling outside
    # the source-derived manifest.
    for relative in ('skills/battle-scaling/tests/rebuild_static_rating_fixtures.py',
                     'tools/combat-novel-refpack/tests/test_prompt_compatibility.py'):
        path=PUBLICATION/relative
        if path.is_file():files.setdefault(relative,path.read_bytes())
    # Sanitized quotation/path metadata changes the index bytes, not its rule
    # values. Bind the distributed index and retain the original index hash.
    data_prefix='skills/battle-scaling/data/wangba-handbook-2026-07-30/'
    if data_prefix+'manifest.json' in files and data_prefix+'reviewed-clauses.json' in files:
        handbook_manifest=json.loads(files[data_prefix+'manifest.json'])
        index_hash=hashlib.sha256(files[data_prefix+'reviewed-clauses.json']).hexdigest()
        original=handbook_manifest.get('reviewed_clauses_sha256')
        if original and original!=index_hash:
            handbook_manifest['original_reviewed_clauses_sha256']=original
            handbook_manifest['reviewed_clauses_sha256']=index_hash
        files[data_prefix+'manifest.json']=dumps(handbook_manifest).encode()
    # Each installable directory carries the original-project permission text;
    # upstream/component exceptions remain in their separate notices.
    for prefix in ('skills/battle-scaling/','tools/combat-novel-refpack/'):
        files[prefix+'LICENSE']=(PUBLICATION/'LICENSE').read_bytes()
    prefix='skills/battle-scaling/'
    static={rel[len(prefix):]:digest(data) for rel,data in sorted(files.items()) if rel.startswith(prefix)}
    manifest={'skill':'battle-scaling','version':version,'scope':'Distributed static files; optional runtime libraries and user media are not bundled.','mutable_paths':['runtime/**','data/site-experience/**','data/media-sourcing/**','tests/acceptance-last-run.json'],'files':static}
    source_manifest=skill_source/'package-manifest.json'
    if source_manifest.is_file():
        updated=json.loads(source_manifest.read_text(encoding='utf-8-sig')).get('updated')
        if updated:manifest['updated']=updated
    files[prefix+'package-manifest.json']=dumps(manifest).encode()
    for name in ('README.md','README.en.md','LICENSE','NOTICE.md','THIRD_PARTY_NOTICES.md','UPSTREAM-SOURCES.json','.gitignore','.gitattributes','.env.example'):
        path=PUBLICATION/name
        if path.is_file():files[name]=path.read_bytes()
    for folder in ('docs','tools/public-video','tools/requirements'):
        for path in (PUBLICATION/folder).rglob('*'):
            relative=path.relative_to(PUBLICATION).as_posix()
            if path.is_file() and not path.is_symlink() and not excluded(relative,'public') and path.name not in {'sync-summary.json','distribution-manifest.json'}:files[relative]=path.read_bytes()
    for name in ('sync_public.py','verify_package.py','publication_guard.py','test_publication_guard.py','test_public_sync.py','import_handbook_corpus.py','setup.py','test_setup.py','build_release.py','test_build_release.py'):
        files['tools/'+name]=(PUBLICATION/'tools'/name).read_bytes()
    files['docs/distribution-manifest.json']=dumps({'version':version,'scope':'Static distribution; runtime libraries and user media excluded.','files':{rel:digest(data) for rel,data in sorted(files.items())}}).encode()
    errors=scan_payload(files)
    if errors:
        raise ValueError('Publication privacy scan failed: '+dumps(errors))
    return files,{'version':version,'static_files':len(files),'copied':counts,'excluded_counts':omitted,'preserved':['skills/battle-scaling/references/writing-experience.md']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-source',type=Path,default=Path.home()/'.codex/skills/battle-scaling')
    parser.add_argument('--video-source',type=Path,required=True)
    parser.add_argument('--novel-source',type=Path,required=True)
    parser.add_argument('--target',type=Path,required=True)
    parser.add_argument('--version',default='1.21.1')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    target=safe_target(args.target,[args.skill_source,args.video_source,args.novel_source])
    files,result=build_payload(args.skill_source,args.video_source,args.novel_source,args.version)
    result['mode']='write' if args.apply else 'plan'
    if args.apply:
        changed=sum(write_if_changed(target/rel,data) for rel,data in files.items())
        result['changed_files']=changed
        write_if_changed(target/'docs/sync-summary.json',dumps(result).encode())
        # Check the real destination inventory too: a manifest cannot hide an
        # extra tracked file or a newly added, non-ignored upload candidate.
        from verify_package import verify
        validation=verify(target)
        result['validation']=validation
        if not validation['valid']:
            print(dumps(result),end='')
            return 1
    print(dumps(result),end='')
    return 0

if __name__=='__main__':raise SystemExit(main())
