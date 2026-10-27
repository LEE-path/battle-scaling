"""Explicit invented rating preconditions for regression fixtures, never canon.

Tests exercising other gates use this common factory so their old inputs remain
independently rated. Admission-gate tests call production entry points with and
without these packets and never patch/bypass the production gate.
"""
import copy
from functools import wraps
import atexit
import json
from pathlib import Path
import tempfile

_EXECUTED_FIXTURE_DIRS = []

FIELDS = ('输出', '体防', '智力', '战斗智商', '经验', '特殊技能', '破坏', '速度', '体量')


def with_independent_ratings(request, *, writing=False, modes=None, standards=None):
    request = copy.deepcopy(request)
    request.setdefault('fixture_kind', 'synthetic_explicit_invented_test')
    request.setdefault('mode', 'normal')  # Explicit historical fixture; production defaults to integrated.
    standard = request.get('standard', 'wangba')
    if standard not in ('wangba', 'vsb'):
        standard = 'wangba'
    modes = modes or (request.get('mode', 'normal'),)
    subjects = request.get('fighters' if writing else 'characters', request.get('actors', []))
    if not isinstance(subjects, list):
        return request
    source_id = 'independent-rating-fixture'
    request['sources'] = [source for source in request.get('sources', [])
                          if source.get('id') != source_id]
    request['sources'].append({
        'id': source_id, 'title': 'Explicit invented independent rating fixture',
        'origin': 'author_settings' if writing else 'synthetic', 'access': 'provided',
        'locator': 'tests/rating_fixtures.py: invented fixture definitions, not canon',
    })
    # Some historical tests use the word primary to exercise access semantics;
    # explicitly identify those invented records instead of relaxing real-source
    # admission or rewriting provenance in the production checker.
    for source in request['sources']:
        source['fixture_kind'] = 'synthetic_explicit_invented_test_source'
    rows = []
    for subject in subjects:
        if not isinstance(subject, dict) or not isinstance(subject.get('id'), str):
            continue
        subject.setdefault('version', 'synthetic-v1')
        subject.setdefault('state', 'active')
        subject.setdefault('equipment', [])
        labels = subject.get('ratings', {}) if writing else {}
        for standard in standards or (standard,):
          for mode in modes:
            def node(label, physical=False):
                return {'label':label, 'kind':'tier' if physical else 'level', 'basis':'lower_bound',
                        'evidence_ids':[source_id], 'reasoning':'Explicit fixture lower bound, established independently of the matchup outcome.'}
            dims = {}
            for field in FIELDS:
                physical = field in ('输出', '体防', '破坏')
                label = labels.get(field, ('9-B (Wall level)' if standard == 'vsb' else '标准爆墙') if physical else '明确的回归测试能力等级')
                if physical and standard == 'vsb':
                    label = '9-B (Wall level)'
                dims[field] = node(label, physical)
            rows.append({'character_id':subject['id'], 'standard':standard, 'mode':mode,
                         'version':subject['version'], 'state':subject['state'], 'equipment':copy.deepcopy(subject['equipment']),
                         'basis_type':'author_settings' if writing else 'canon',
                         'main_tier':node('9-B (Wall level)' if standard == 'vsb' else '标准爆墙', True),
                         'dimensions':dims,
                         'completion_review':{
                            'status':'complete','revision':'synthetic-scope-v1','selected_basis':'mode_representative',
                            'scope_findings':{'reasoning':'The invented test source defines the complete supplied version, state and equipment; there are no other canon feats in this fixture.',
                                              'evidence_ids':[source_id], 'basis_type':'author_settings' if writing else 'canon'},
                            'selection_findings':{'reasoning':'For this mode the source-defined physical floor and explicit ability levels are the representative limits of this invented configuration, independently of its opponent.',
                                                  'evidence_ids':[source_id], 'basis_type':'author_settings' if writing else 'canon'},
                            'candidates':[]},
                         'host_review':{'status':'accepted','reviewer':'synthetic-test-author','reviewed_revision':'synthetic-scope-v1',
                            'dossier_ref':'tests/rating_fixtures.py#independent-fixture-not-canon'}})
    request['independent_ratings'] = rows
    return with_executed_ratings(request) if writing else request


def with_executed_ratings(request, directory=None):
    """Actually create/report/analyze/import invented standalone test dossiers.

    No gate is patched. These are authored synthetic settings and authored
    reports, clearly identified as test fixtures, never fictional-canon evidence.
    Persistent asset generation passes a directory; runtime tests use temporary
    files kept alive until process exit so writing can re-read their contents.
    """
    from battle import compute_case, export_case
    from evidence import analyze_case
    from rating_pipeline import run, _write, file_hash, HASH_FIELDS
    from rule_profiles import resolve, snapshot_content
    request = copy.deepcopy(request)
    request.setdefault('mode', 'normal')  # Legacy asset fixture is intentionally replayed.
    if request.get('purpose') != 'writing':
        return request  # Opt-in rejection tests must reach writing itself.
    subjects = request.get('fighters', [])
    if (not isinstance(subjects, list) or any(not isinstance(s, dict) or not s.get('id') for s in subjects)
            or len({s['id'] for s in subjects}) != len(subjects)):
        return request  # Malformed-input tests must reach the real validation.
    if directory is None:
        temp = tempfile.TemporaryDirectory(prefix='battle-rating-fixture-')
        _EXECUTED_FIXTURE_DIRS.append(temp)
        directory = Path(temp.name)
    else:
        directory = Path(directory)
    profile = resolve(request.get('ruleset_profile'), request.get('standard', 'wangba'))
    mode = request.get('mode', 'normal')
    artifacts = []
    for index, subject in enumerate(request.get('fighters', [])):
        row = next(row for row in request['independent_ratings'] if
                   row.get('character_id') == subject['id'] and row.get('mode') == mode and
                   row.get('standard') == profile['standard'])
        needed = set()
        def references(value):
            if isinstance(value, dict):
                needed.update(value.get('evidence_ids', []))
                for child in value.values():
                    references(child)
            elif isinstance(value, list):
                for child in value:
                    references(child)
        references(row)
        sources = [source for source in request['sources'] if source['id'] in needed]
        own = {key: copy.deepcopy(subject.get(key)) for key in
               ('id', 'name', 'version', 'state', 'equipment')}
        claims = []
        for attribute, node in [('main_tier', row['main_tier']), *row['dimensions'].items()]:
            claims.append({'id': 'rating-' + str(len(claims)), 'subject': subject['id'],
                           'attribute': attribute, 'reasoning': node['reasoning'],
                           'evidence_ids': node['evidence_ids'], 'assessment': copy.deepcopy(node)})
        case = {'schema_version': 1, 'case_id': 'authored-fixture-' + subject['id'],
                'fixture_kind': 'synthetic_author_settings_not_character_evidence',
                'standard': profile['standard'], 'ruleset_profile': profile['id'],
                'rating_target_id': subject['id'], 'characters': [own], 'sources': sources,
                'independent_ratings': [row], 'anchors': [], 'edges': [],
                'qualitative_claims': claims,
                'limitations': ['Explicitly authored synthetic fixture; no real canon research is claimed.']}
        out = directory / (str(index + 1) + '-' + subject['id'])
        out.mkdir(parents=True, exist_ok=True)
        original = directory / ('case-input-' + str(index + 1) + '.json')
        _write(original, case)
        computed = compute_case(case, mode, profile)
        analysis = analyze_case(computed, mode, profile)
        analysis['rule_snapshot'] = snapshot_content(profile, computed.get('computations', []))
        export_case(analysis, out, original, original.read_bytes())
        _write(out / 'rating.json', row)
        report = ['# Explicitly authored independent synthetic rating', '',
                  'This report assesses only ' + subject['name'] + ' in the supplied version/state/equipment.',
                  'The test author defines all evidence; this is not an actual canon dossier.', '',
                  'Main tier: ' + row['main_tier']['label'], row['main_tier']['reasoning'], '']
        for field, node in row['dimensions'].items():
            report.extend([field + ': ' + node['label'], node['reasoning'],
                           'Sources: ' + ', '.join(node['evidence_ids']), ''])
        report.extend(['Scope review: ' + row['completion_review']['scope_findings']['reasoning'],
                       'Selection review: ' + row['completion_review']['selection_findings']['reasoning'],
                       'Candidates: ' + json.dumps(row['completion_review']['candidates'], ensure_ascii=False)])
        (out / 'report.md').write_text('\n'.join(report), encoding='utf-8')
        acceptance = {'status': 'accepted', 'reviewer': row['host_review']['reviewer'],
                      'reviewed_revision': row['completion_review']['revision'],
                      'fixture_kind': 'explicit_authored_test_acceptance_not_canon'}
        acceptance.update({key: file_hash(out / name) for name, key in HASH_FIELDS.items()})
        _write(out / 'host-acceptance.json', acceptance)
        manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
        for name in ('report.md', 'rating.json', 'host-acceptance.json'):
            path = out / name
            manifest['files'][name] = {'bytes': path.stat().st_size, 'sha256': file_hash(path)}
        _write(out / 'manifest.json', manifest)
        artifacts.append({'character_id': subject['id'], 'artifact_dir': str(out)})
    result = run({'operation': 'assemble', 'writing_request': request, 'artifacts': artifacts})
    if result['status'] != 'assembled':
        raise AssertionError('Synthetic fixture did not pass the production import: ' + repr(result['needs']))
    return result['writing_request']


def _cleanup_executed_fixtures():
    for directory in _EXECUTED_FIXTURE_DIRS:
        directory.cleanup()


atexit.register(_cleanup_executed_fixtures)


def rated_fixture(function):
    """Give unrelated regression fixtures explicit preconditions for CLI reuse."""
    @wraps(function)
    def build(*args, **kwargs):
        return with_independent_ratings(function(*args, **kwargs),
            modes=('normal', 'highest', 'lowball'), standards=('wangba', 'vsb'))
    return build


def rated_call(function, *, writing=False):
    """Rate runtime-added synthetic actors before calling the real entry point.

    Admission tests do not use this helper. It supplies invented independent
    source packets; it never patches or bypasses the production gate.
    """
    @wraps(function)
    def call(request, *args, **kwargs):
        return function(with_independent_ratings(request, writing=writing,
            modes=('normal', 'highest', 'lowball'), standards=('wangba', 'vsb')),
            *args, **kwargs)
    return call


def legacy_analyze_case(case, mode='normal', profile=None):
    """Exercise the preserved historical algorithm explicitly, never its default."""
    from evidence import analyze_case
    return analyze_case(case, mode, profile)


def legacy_compute_case(case, mode='normal', profile=None):
    from battle import compute_case
    return compute_case(case, mode, profile)
