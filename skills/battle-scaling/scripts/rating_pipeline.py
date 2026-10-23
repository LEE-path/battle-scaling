"""Two host stages: isolated character research, then checked artifact import.

No language model, network research or source interpretation runs here.  The
host actually performs standalone research and writes the report/rating.  These
tools create isolated assignments, read their real products, repeat the local
analysis and bind the imported values to files that are re-read before writing.
File integrity and reproducible calculations do not prove semantic correctness.
"""
from __future__ import annotations

import copy
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import re

from rating_preflight import review as review_ratings, RATING_FIELDS
from rule_profiles import resolve, snapshot_content
from rating_modes import metadata as mode_metadata

ROOT = Path(__file__).resolve().parents[1]
FILES = ('report.md', 'rating.json', 'sources.json', 'CASE.json', 'analysis.json',
         'derivations.json', 'rules-snapshot.json', 'host-acceptance.json')
HASH_FIELDS = {'report.md': 'report_sha256', 'rating.json': 'rating_sha256',
               'sources.json': 'sources_sha256', 'CASE.json': 'case_sha256',
               'analysis.json': 'analysis_sha256', 'derivations.json': 'derivations_sha256',
               'rules-snapshot.json': 'rules_snapshot_sha256'}
SCOPE_FIELDS = ('id', 'name', 'version', 'state', 'equipment')
INVALID_STATES = {'withdrawn', 'superseded', 'revoked', 'retracted', 'blocked', 'invalid'}
LIMIT = ('Local file reading, hashes, scope, source/rating import and reproducible '
         'analysis are checked. Host research, source truth, report entailment '
         'and semantic completeness remain the named host reviewer\'s responsibility.')

# Private, bounded, process-local results only. No receipt or request field can
# populate this cache. Another CLI process always performs its own first replay.
_ARTIFACT_CACHE = OrderedDict()
_CACHE_LIMIT = 32


def _dependency_fingerprint(profile):
    """Hash current engine/rule bytes, never mtime or a request's success flag."""
    paths = set((ROOT / 'scripts').glob('*.py'))
    paths.update((ROOT / 'rulesets').glob('*.json'))
    if profile.get('document_manifest'):
        paths.add(_path(profile['document_manifest']))
    return digest({str(path.resolve()): file_hash(path) for path in sorted(paths)})


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')


def _path(value, base=ROOT):
    path = Path(value).expanduser()
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def _stored_path(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def _profile_key(profile):
    identity = copy.deepcopy({key: value for key, value in profile.items() if key != 'selection_source'})
    # Installation paths are transport details. The actual rule source bytes,
    # selected profile, document IDs and module hashes remain part of identity.
    for key in ('profile_configuration', 'finite_rule_snapshot'):
        if isinstance(identity.get(key), dict):
            identity[key].pop('path', None)
    return identity


def _replay_equal(saved, current, mode):
    """Only legacy replay tolerates absence of newly added policy disclosures.

    Historical bytes, premises, scope, numeric results and explicit existing
    flags must still match. This is not conversion to an integrated rating.
    """
    if mode == 'integrated':
        return saved == current
    disclosure = mode_metadata(mode)

    def comparable(old, new):
        if isinstance(old, dict) and isinstance(new, dict):
            return {key: comparable(old.get(key), value) for key, value in new.items()
                    if not (key not in old and key in disclosure and value == disclosure[key])}
        if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
            return [comparable(a, b) for a, b in zip(old, new)]
        return new

    return saved == comparable(saved, current)


def _configuration(request):
    if request.get('purpose') != 'writing':
        raise ValueError('rating-pipeline is the purpose=writing host route; ordinary standalone and PK keep their existing workflow')
    standard, mode = request.get('standard', 'wangba'), request.get('mode', 'integrated')
    if mode not in ('integrated', 'normal', 'highest', 'lowball'):
        raise ValueError('rating pipeline selects integrated; legacy normal/highest/lowball require an explicit historical replay')
    profile = resolve(request.get('ruleset_profile'), standard)
    subjects = request.get('fighters', [])
    if not isinstance(subjects, list) or not subjects or any(not isinstance(s, dict) or
            not _text(s.get('id')) for s in subjects):
        raise ValueError('rating pipeline requires explicitly identified fighters')
    if len({s['id'] for s in subjects}) != len(subjects):
        raise ValueError('rating pipeline fighter IDs must be unique')
    return standard, mode, profile, subjects


def _scope(subject):
    return {key: copy.deepcopy(subject.get(key)) for key in SCOPE_FIELDS}


def tasks_for(request, output_dir=None):
    """Return self-contained per-character tasks, with no complete story packet.

    Narrative fields are never copied. If a scope embeds a different participant's
    name, the offending value is masked and the host must first isolate that
    configuration; the original string is not leaked into the research task.
    """
    standard, mode, profile, subjects = _configuration(request)
    tasks = []
    for index, subject in enumerate(subjects):
        isolated = _scope(subject)
        for key in ('work', 'continuity', 'period', 'author_settings'):
            if key in subject:
                isolated[key] = copy.deepcopy(subject[key])
        # Original/adapted characters need all of their supplied material. It
        # remains author material, never an automatic canon or accepted rating.
        provided = {key: copy.deepcopy(subject[key]) for key in ('persona', 'skills', 'ratings')
                    if key in subject}
        if provided:
            isolated['provided_author_material'] = {'origin': 'author_settings',
                'material': provided,
                'adoption': 'Host distinguishes explicit author rules from unverified canon notes; supplied labels are inputs, not an executed rating.'}
        other_names = [s.get('name') for s in subjects if s['id'] != subject['id'] and
                       _text(s.get('name'))]
        masked = []
        for key, value in list(isolated.items()):
            if key in ('id', 'name'):
                continue
            serialized = json.dumps(value, ensure_ascii=False)
            def mentions(name):
                return bool(re.search(r'(?<![A-Za-z0-9_])' + re.escape(name) + r'(?![A-Za-z0-9_])', serialized)) if name.isascii() else name in serialized
            if any(mentions(name) for name in other_names):
                isolated[key] = {'needs_isolated_scope': True,
                                 'original_value_sha256': digest(value)}
                masked.append(key)
        packet = {'schema_version': 1, 'task_type': 'standalone_character_rating',
                  'character': isolated, 'standard': standard, 'mode': mode, **mode_metadata(mode),
                  'ruleset_profile': profile['id'],
                  'rules_fingerprint': digest(_profile_key(profile)),
                  'mandatory_media_steps': [],
                  'scope_needs_host_isolation': masked,
                  'required_products': list(FILES),
                  'required_workflow': 'references/character-rating-workflow.md',
                  'semantic_work_performed_by': 'host; never the Python task planner'}
        instructions = (
            '# Independent single-character rating\n\n'
            'Read input.json. Assess only its selected character/version/state/equipment, '
            'under its selected integrated rating policy and rule source (explicit legacy modes are historical replay only). No opponent, desired '
            'winner, battle outline or story is supplied. Do not infer any.\n\n'
            'Preserve the character\'s provided_author_material, including persona, '
            'skills, activation/limits and explicit authored ratings as authored '
            'inputs. Do not promote them to canon. If scope_needs_host_isolation '
            'is nonempty, stop this assignment until the coordinator isolates '
            'those fields while preserving the actual capability/state rules; '
            'masked hashes are not sufficient character settings.\n\n'
            'Actually execute the complete standalone workflow: find/read original or '
            'author-supplied sources; inventory abilities, representative feats and '
            'counterfeats as contextual evidence, not three character ratings; review meaningful higher/lower candidates, material outer relationships and transfer '
            'chains; derive one concrete main tier and all nine dimensions. Reuse an '
            'existing qualified dossier only after reading its current files and '
            'acceptance. A local floor or a filled rating packet alone is insufficient. '
            'Text evidence is permitted; this story-origin assignment mandates no '
            'new image/video download or visual measurement.\n\n'
            'Write a complete report.md and rating.json (one independent_ratings row), '
            'sources.json (list). CASE.json must contain this exact row in '
            'independent_ratings, a matching target character, no matchup or writing '
            'story, and sourced qualitative_claims or anchors/computations that cover '
            'the main tier and nine dimensions. Reference characters for canonical '
            'transfer chains are allowed. Execute battle.py analyze --input CASE.json '
            f'--mode {mode} --standard {standard} --output ANALYSIS_DIR. '
            'Retain analysis.json, derivations.json and rules-snapshot.json beside '
            'the report/rating/CASE (the authored full report may replace the generated '
            'report only before final host acceptance).\n\n'
            'Finally perform the host review of report, sources, calculations, full '
            'scope/candidate selection and nine-dimensional rating. Bind the current '
            'acceptance revision to completion_review.revision and host_review in '
            'rating.json. Write host-acceptance.json with status, reviewer, '
            'reviewed_revision and these SHA-256 fields: ' + ', '.join(HASH_FIELDS.values()) +
            '. This attests the host review; Python checks integrity and replay, '
            'not truth or reading comprehension. Withdraw/supersede this actual file '
            'when the dossier ceases to be current.\n')
        item = {'character_id': subject['id'], 'input': packet, 'instructions': instructions}
        if output_dir is not None:
            slug = re.sub(r'[^A-Za-z0-9_-]', '_', subject['id'])[:48] or 'character'
            directory = _path(output_dir) / f'{index+1:02d}-{slug}'
            directory.mkdir(parents=True, exist_ok=True)
            _write(directory / 'input.json', packet)
            (directory / 'task.md').write_text(instructions, encoding='utf-8')
            item.update(input_file=str(directory / 'input.json'),
                        task_file=str(directory / 'task.md'), artifact_dir=str(directory))
        tasks.append(item)
    return tasks


def _sources_valid(sources, directory):
    if not isinstance(sources, list) or not sources:
        raise ValueError('sources.json must contain actual standalone source records')
    seen, local_files = set(), []
    for source in sources:
        if not isinstance(source, dict) or not _text(source.get('id')) or source['id'] in seen:
            raise ValueError('standalone sources need unique nonempty IDs')
        seen.add(source['id'])
        if source.get('status') in INVALID_STATES or source.get('current_status') in INVALID_STATES:
            raise ValueError('standalone source is currently withdrawn or unavailable: ' + source['id'])
        if source.get('withdrawn') is True or source.get('retracted') is True:
            raise ValueError('standalone source is withdrawn: ' + source['id'])
        if source.get('path'):
            path = _path(source['path'], directory)
            if not path.is_file():
                raise ValueError('local standalone source is missing: ' + str(path))
            actual = file_hash(path)
            expected = source.get('sha256', source.get('file_sha256'))
            if expected and actual != expected:
                raise ValueError('local standalone source hash differs: ' + source['id'])
            local_files.append({'path': _stored_path(path), 'sha256': actual, 'source_id': source['id']})
        status_file = source.get('status_file')
        if status_file:
            path = _path(status_file, directory)
            status = _read(path)
            if status.get('status') != 'current':
                raise ValueError('source status file does not confirm current source: ' + source['id'])
            local_files.append({'path': _stored_path(path), 'sha256': file_hash(path), 'source_id': source['id']})
    return local_files


def _read_artifact_uncached(artifact, subject, request, profile, hashes):
    directory = _path(artifact['artifact_dir'])
    paths = {name: directory / name for name in FILES}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError(subject['id'] + ': missing executed standalone product ' + str(path))
    report = paths['report.md'].read_text(encoding='utf-8-sig')
    if not report.strip():
        raise ValueError(subject['id'] + ': empty standalone report')
    row, sources, case, analysis, derivations, snapshot, acceptance = (
        _read(paths[name]) for name in FILES[1:])
    if not isinstance(row, dict):
        raise ValueError('rating.json must contain one independent-rating row')
    if any(not isinstance(value, dict) for value in (case, analysis, derivations, snapshot, acceptance)):
        raise ValueError('CASE, analysis, derivations, rule snapshot and host acceptance must be JSON objects')
    if (not isinstance(case.get('characters'), list) or
            any(not isinstance(character, dict) for character in case['characters'])):
        raise ValueError('standalone CASE characters must be a list of objects')
    if acceptance.get('status') != 'accepted' or not _text(acceptance.get('reviewer')):
        raise ValueError(subject['id'] + ': current host acceptance is absent, withdrawn or superseded')
    if (acceptance.get('reviewed_revision') != row.get('completion_review', {}).get('revision') or
            acceptance.get('reviewer') != row.get('host_review', {}).get('reviewer')):
        raise ValueError(subject['id'] + ': host acceptance does not bind the current rating review')
    for name, key in HASH_FIELDS.items():
        if acceptance.get(key) != hashes[name]:
            raise ValueError(subject['id'] + ': current host acceptance hash differs for ' + name)
    standard, mode = request.get('standard', 'wangba'), request.get('mode', 'integrated')
    gate = review_ratings([subject], [row], sources, standard=standard, mode=mode,
                          writing=True, **({'rating_status': request['rating_status']}
                                          if 'rating_status' in request else {}))
    if gate['status'] != 'ready':
        raise ValueError(subject['id'] + ': ' + '; '.join(gate['needs']))
    if row.get('character_id') != subject['id']:
        raise ValueError('artifact target differs from the requested character')
    if case.get('purpose') == 'writing' or 'matchup' in case:
        raise ValueError('standalone CASE must not contain a writing request or matchup')
    targets = [c for c in case.get('characters', []) if c.get('id') == subject['id']]
    if len(targets) != 1 or _scope(targets[0]) != _scope(subject):
        raise ValueError(subject['id'] + ': standalone CASE configuration does not match')
    if case.get('rating_target_id', subject['id']) != subject['id']:
        raise ValueError('standalone CASE has a different rating target')
    if case.get('independent_ratings') != [row]:
        raise ValueError('standalone CASE must bind its exact rating.json row in independent_ratings')
    if case.get('sources') != sources or analysis.get('sources') != sources:
        raise ValueError('standalone CASE/analysis/source imports differ')
    # Ten explicitly sourced derivations must exist in the analyzed case. These
    # may be qualitative: unknown J values are never fabricated for the gate.
    claims = case.get('qualitative_claims', [])
    covered = {claim.get('attribute') for claim in claims if isinstance(claim, dict) and
               claim.get('subject') == subject['id'] and _text(claim.get('reasoning')) and
               claim.get('evidence_ids') and mode in claim.get('modes', [mode])}
    covered.update(a.get('attribute') for a in case.get('anchors', []) if a.get('subject') == subject['id']
                   and mode in a.get('modes', [mode]))
    required = {'main_tier', *RATING_FIELDS}
    if not required <= covered:
        raise ValueError('standalone analyzed derivations must cover main_tier and all nine dimensions: ' +
                         ', '.join(sorted(required - covered)))
    saved_profile = analysis.get('ruleset_profile', {})
    case_profile = resolve(case.get('ruleset_profile'), case.get('standard'))
    if (_profile_key(saved_profile) != _profile_key(profile) or
            _profile_key(case_profile) != _profile_key(profile)):
        raise ValueError('standalone analysis rule source/profile differs from the writing configuration')
    if row.get('ruleset_profile', profile['id']) != profile['id']:
        raise ValueError('standalone rating rule profile differs')
    # Replay the very same local compute -> analyze path as battle.py analyze.
    # Computation helpers are deterministic and never call a model or network.
    from battle import compute_case
    from evidence import analyze_case
    computed = compute_case(case, mode, saved_profile)
    expected = analyze_case(computed, mode, saved_profile)
    expected_snapshot = snapshot_content(saved_profile, computed.get('computations', []))
    expected['rule_snapshot'] = expected_snapshot
    if not _replay_equal(analysis, expected, mode):
        raise ValueError(subject['id'] + ': analysis.json is not the reproducible CASE analysis for this mode')
    admitted = expected['modes'][mode]
    admitted_fields = {item.get('attribute') for item in
                       admitted.get('qualitative_claims', []) + admitted.get('conclusions', [])
                       if isinstance(item, dict) and item.get('subject') == subject['id']}
    if not required <= admitted_fields:
        raise ValueError('standalone mode analysis excludes required rating derivations: ' +
                         ', '.join(sorted(required - admitted_fields)))
    if not _replay_equal(derivations, expected['modes'], mode) or snapshot != expected_snapshot:
        raise ValueError(subject['id'] + ': derivations/rule snapshot differ from actual CASE analysis')
    local_files = _sources_valid(sources, directory)
    receipt = {'character_id': subject['id'], 'artifact_dir': _stored_path(directory),
               'files': {name: {'path': _stored_path(path), 'sha256': hashes[name]} for name, path in paths.items()},
               'source_files': local_files, 'scope_sha256': digest(_scope(subject)),
               'rating_sha256': digest(row), 'sources_sha256': digest(sources),
               'reviewed_revision': acceptance['reviewed_revision']}
    return row, sources, receipt


def _read_artifact(artifact, subject, request, profile, *, _dependencies=None,
                   _expected_receipt=None, _stats=None):
    directory = _path(artifact['artifact_dir'])
    hashes = {name: file_hash(directory / name) for name in FILES}
    current_files = {name: {'path': _stored_path(directory / name), 'sha256': value}
                     for name, value in hashes.items()}
    if _expected_receipt is not None and _expected_receipt.get('files') != current_files:
        raise ValueError('executed standalone products changed from their imported receipt')
    key = digest({'directory': str(directory), 'files': hashes, 'scope': _scope(subject),
                  'standard': request.get('standard', 'wangba'),
                  'mode': request.get('mode', 'integrated'), 'profile': _profile_key(profile),
                  'rating_status': request.get('rating_status'),
                  'dependencies': _dependencies or _dependency_fingerprint(profile)})
    cached = _ARTIFACT_CACHE.get(key)
    if cached is not None:
        # Re-resolve declared source/status paths: a symlink or junction can be
        # redirected while the old resolved target and its bytes remain intact.
        try:
            current_sources = _sources_valid(cached[1], directory)
        except (ValueError, KeyError, TypeError, OSError):
            _ARTIFACT_CACHE.pop(key, None)
            raise
        if current_sources != cached[2]['source_files']:
            _ARTIFACT_CACHE.pop(key, None)
            cached = None
        if cached is not None:
            _ARTIFACT_CACHE.move_to_end(key)
            if _stats is not None:
                _stats['cache_hits'] += 1
            return copy.deepcopy(cached)
    result = _read_artifact_uncached(artifact, subject, request, profile, hashes)
    if _stats is not None:
        _stats['replays'] += 1
    _ARTIFACT_CACHE[key] = copy.deepcopy(result)
    _ARTIFACT_CACHE.move_to_end(key)
    while len(_ARTIFACT_CACHE) > _CACHE_LIMIT:
        _ARTIFACT_CACHE.popitem(last=False)
    return result


def _selected_rows(request, subjects, standard, mode):
    ids = {s['id'] for s in subjects}
    return [row for row in request.get('independent_ratings', []) if isinstance(row, dict) and
            row.get('character_id') in ids and row.get('standard') == standard and row.get('mode') == mode]


def _import_key(rows, sources):
    return digest({'ratings': sorted(rows, key=lambda row: row['character_id']),
                   'sources': sorted(sources, key=lambda source: source['id'])})


def assemble(request):
    writing = copy.deepcopy(request.get('writing_request', {}))
    standard, mode, profile, subjects = _configuration(writing)
    artifacts = request.get('artifacts', [])
    if not isinstance(artifacts, list):
        raise ValueError('artifacts must be a list of character_id/artifact_dir objects')
    mapping = {}
    for item in artifacts:
        if not isinstance(item, dict) or item.get('character_id') in mapping:
            raise ValueError('artifact character IDs must be unique')
        mapping[item.get('character_id')] = item
    if set(mapping) != {s['id'] for s in subjects}:
        raise ValueError('executed standalone artifacts must cover exactly every requested fighter')
    rows, imported_sources, receipts = [], {}, []
    dependencies = _dependency_fingerprint(profile)
    for subject in subjects:
        row, sources, receipt = _read_artifact(mapping[subject['id']], subject, writing, profile,
                                              _dependencies=dependencies)
        rows.append(row)
        receipts.append(receipt)
        for source in sources:
            sid = source['id']
            if sid in imported_sources and imported_sources[sid] != source:
                raise ValueError('conflicting standalone source records share ID: ' + sid)
            imported_sources[sid] = source
    sources = {s['id']: s for s in writing.get('sources', [])}
    for sid, source in imported_sources.items():
        if sid in sources and sources[sid] != source:
            raise ValueError('writing source conflicts with the actual standalone source: ' + sid)
        sources[sid] = source
    retained = [row for row in writing.get('independent_ratings', []) if row not in
                _selected_rows(writing, subjects, standard, mode)]
    writing['independent_ratings'] = retained + rows
    writing['sources'] = list(sources.values())
    execution = {'schema_version': 1, 'standard': standard, 'mode': mode, **mode_metadata(mode),
                 'rules_fingerprint': digest(_profile_key(profile)), 'artifacts': receipts,
                 'source_ids': sorted(imported_sources),
                 'import_sha256': _import_key(rows, list(imported_sources.values())),
                 'semantic_rating_verified': False, 'validation_scope': LIMIT}
    writing['rating_execution'] = execution
    return {'status': 'assembled', 'stage': 'standalone_rating_completed',
            'writing_request': writing, 'rating_execution': execution,
            'next_step': 'Run battle.py writing with writing_request after completing its authored settings.',
            'semantic_rating_verified': False, 'validation_scope': LIMIT}


def verify_execution(request):
    """Check current bytes every time; reuse a prior full replay only in-process."""
    needs = []
    stats = {'cache_hits': 0, 'replays': 0}
    try:
        standard, mode, profile, subjects = _configuration(request)
        execution = request.get('rating_execution')
        if not isinstance(execution, dict) or execution.get('schema_version') != 1:
            raise ValueError('Execute independent per-character rating tasks and assemble their actual files first; a completed JSON rating packet alone is insufficient.')
        if execution.get('standard') != standard or execution.get('mode') != mode:
            raise ValueError('rating execution is for another standard or evidence mode')
        if execution.get('rules_fingerprint') != digest(_profile_key(profile)):
            raise ValueError('rating execution rule source/profile has changed; return to standalone rating')
        receipts = execution.get('artifacts', [])
        if not isinstance(receipts, list) or len(receipts) != len(subjects):
            raise ValueError('rating execution does not cover every fighter')
        mapping = {entry.get('character_id'): entry for entry in receipts if isinstance(entry, dict)}
        if len(mapping) != len(receipts) or set(mapping) != {s['id'] for s in subjects}:
            raise ValueError('rating execution is missing or duplicates a requested fighter')
        rows, source_map = [], {}
        dependencies = _dependency_fingerprint(profile)
        for subject in subjects:
            stored = mapping[subject['id']]
            # Check old hashes before loading; a newly accepted revision needs
            # a fresh import rather than silently retaining the old story plan.
            file_records = stored.get('files', {})
            if not isinstance(file_records, dict) or set(file_records) != set(FILES):
                raise ValueError('rating execution must bind every required standalone product')
            row, sources, current = _read_artifact(stored, subject, request, profile,
                                                  _dependencies=dependencies,
                                                  _expected_receipt=stored, _stats=stats)
            if current != stored:
                raise ValueError('current standalone files differ from their imported execution receipt')
            rows.append(row)
            for source in sources:
                if source['id'] in source_map and source_map[source['id']] != source:
                    raise ValueError('conflicting current standalone source records')
                source_map[source['id']] = source
        selected = _selected_rows(request, subjects, standard, mode)
        supplied_sources = request.get('sources', [])
        if (not isinstance(supplied_sources, list) or any(not isinstance(s, dict) for s in supplied_sources) or
                len({s.get('id') for s in supplied_sources}) != len(supplied_sources)):
            raise ValueError('writing sources must have unique IDs')
        supplied_map = {s.get('id'): s for s in supplied_sources}
        if sorted(source_map) != execution.get('source_ids') or any(supplied_map.get(sid) != value for sid, value in source_map.items()):
            raise ValueError('writing sources differ from the read standalone source files')
        imported = _import_key(rows, list(source_map.values()))
        if execution.get('import_sha256') != imported or _import_key(selected, list(source_map.values())) != imported:
            raise ValueError('writing independent ratings differ from the executed standalone import')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        needs.append(str(exc))
    result = {'status': 'needs_research' if needs else 'ready', 'needs': needs,
              'dossier_contents_read_by_checker': not needs,
              'local_analysis_replayed': not needs and stats['replays'] > 0,
              'local_analysis_verified': not needs, 'semantic_rating_verified': False,
              'replay_performed_this_call': stats['replays'] > 0,
              'replay_count_this_call': stats['replays'],
              'in_process_reuse_count': stats['cache_hits'],
              'validation_scope': LIMIT}
    if needs:
        try:
            result['character_tasks'] = tasks_for(request)
        except (ValueError, TypeError):
            result['character_tasks'] = []
    return result


def run(request):
    if not isinstance(request, dict):
        raise ValueError('rating-pipeline request must be an object')
    operation = request.get('operation', 'plan')
    if operation == 'plan':
        if not request.get('output_dir'):
            raise ValueError('rating-pipeline plan needs an output_dir for actual task files')
        tasks = tasks_for(request.get('writing_request', {}), request['output_dir'])
        isolation_needed = any(task['input']['scope_needs_host_isolation'] for task in tasks)
        return {'status': 'needs_host_scope_isolation' if isolation_needed else 'needs_host_rating_execution', 'stage': 'isolated_standalone_tasks',
                'character_tasks': tasks, 'semantic_work_executed': False,
                'next_step': 'Host executes each standalone task, then calls operation=assemble.',
                'validation_scope': LIMIT}
    if operation in ('assemble', 'assemble-and-prepare'):
        try:
            assembled = assemble(request)
            if operation == 'assemble':
                return assembled
            from writing_battle import run as prepare_writing
            writing_request = assembled['writing_request']
            writing_request['operation'] = 'prepare'
            preparation = prepare_writing(writing_request)
            return {**assembled, 'status': preparation['status'],
                    'stage': 'writing_preparation', 'writing_preparation': preparation,
                    'next_step': 'Host writes the actual battle only after the returned writing_preparation gates are ready.'}
        except (ValueError, KeyError, TypeError, OSError) as exc:
            result = {'status': 'needs_independent_rating', 'stage': 'standalone_rating',
                      'needs': [str(exc)], 'semantic_rating_verified': False}
            try:
                result['character_tasks'] = tasks_for(request.get('writing_request', {}))
            except (ValueError, TypeError):
                result['character_tasks'] = []
            return result
    raise ValueError('rating-pipeline operation must be plan, assemble or assemble-and-prepare')
