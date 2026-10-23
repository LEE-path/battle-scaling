"""Resolve bundled rule versions and record immutable source fingerprints."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def file_record(path):
    raw=Path(path).read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def resolve(profile=None, standard=None):
    config_path=ROOT/'rulesets/profiles.json'
    if not config_path.exists():
        return {'id':'legacy-2024-2025','finite_ruleset':'wangba-energy-2024-03-18.json',
                'high_default':None,'selection_source':'legacy_compatibility_no_profile_file'}
    config=json.loads(config_path.read_text(encoding='utf-8'))
    from standards import normalize
    requested=normalize(standard) if standard is not None else None
    standard_profiles=config.get('standard_profiles',{'wangba':config['default_profile']})
    if profile in ('wangba','vsb'):
        alias=profile
        if requested and alias!=requested:raise ValueError('standard conflicts with ruleset_profile')
        requested=alias
        profile=standard_profiles.get(alias)
    selected=profile or (standard_profiles.get(requested) if requested else config['default_profile'])
    if not isinstance(selected,str) or selected not in config['profiles']:
        raise ValueError('Unknown ruleset_profile; select a named profile from rulesets/profiles.json')
    result={**config['profiles'][selected],'id':selected,
            'selection_source':'explicit_profile' if profile else 'installed_default'}
    result.setdefault('standard','wangba')
    if requested and requested!=result['standard']:
        raise ValueError('standard conflicts with the selected named ruleset_profile')
    if standard is not None and not profile:result['selection_source']='explicit_standard'
    result['profile_configuration']=file_record(config_path)
    finite=result.get('finite_ruleset')
    if finite:
        if Path(finite).name!=finite:
            raise ValueError('Bundled finite rule filename must not contain a path')
        result['finite_rule_snapshot']=file_record(ROOT/'rulesets'/finite)
    doc=result.get('document_manifest')
    if doc:
        path=(ROOT/doc).resolve()
        if not path.is_relative_to(ROOT):raise ValueError('Document manifest escapes the package')
        manifest=json.loads(path.read_text(encoding='utf-8'))
        result['document_snapshot']={'document_id':manifest['document_id'],
            'combined_source_sha256':manifest['combined_source_sha256'],
            'corpus_sha256':manifest['corpus_sha256'],
            'sources':[{k:s[k] for k in ('volume','filename','sha256','pages')} for s in manifest['sources']]}
    return result


def finite_path(profile):
    return ROOT/'rulesets'/profile['finite_ruleset']


def snapshot_content(profile,computations=()):
    files={}
    if profile.get('finite_ruleset'):
        p=finite_path(profile)
        files[profile['finite_ruleset']]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                                        'data':json.loads(p.read_text(encoding='utf-8'))}
    for name in profile.get('extra_rule_files',[]):
        if not isinstance(name,str) or Path(name).name!=name:
            raise ValueError('Bundled extra rule file must be a plain filename')
        p=ROOT/'rulesets'/name
        files[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'data':json.loads(p.read_text(encoding='utf-8'))}
    for name in profile.get('extra_rule_modules',[]):
        if not isinstance(name,str) or Path(name).name!=name:
            raise ValueError('Bundled rule module must be a plain filename')
        p=ROOT/'scripts'/name
        files['scripts/'+name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                                'data':{'kind':'first_party_executable_policy_snapshot','source_code':p.read_text(encoding='utf-8')}}
    for c in computations:
        if c.get('type')!='high':continue
        name=c.get('request',{}).get('ruleset')
        if not name:continue
        if not isinstance(name,str) or Path(name).name!=name:continue
        if not name.endswith('.json'):name+='.json'
        p=ROOT/'rulesets'/name
        if p.is_file():
            files[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                         'data':json.loads(p.read_text(encoding='utf-8'))}
    return {'profile':profile,'rules':files}
