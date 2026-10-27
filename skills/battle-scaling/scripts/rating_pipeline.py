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
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
from pathlib import Path
import re

from rating_preflight import review as review_ratings, RATING_FIELDS
from rule_profiles import resolve, snapshot_content
from rating_modes import metadata as mode_metadata
from rating_dossier import subject_views

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
_CALL_CHECKS = ContextVar('battle_rating_file_checks', default=None)


def handoff_scoped(function):
    """Share file reads only within one public call, including nested consumers.

    The scope is private process state, never a request-provided ready token.
    A later public call creates a fresh scope and checks changed bytes/targets.
    """
    @wraps(function)
    def scoped(*args, **kwargs):
        if _CALL_CHECKS.get() is not None:
            return function(*args, **kwargs)
        token = _CALL_CHECKS.set(_FileChecks())
        try:
            return function(*args, **kwargs)
        finally:
            _CALL_CHECKS.reset(token)
    return scoped


def _call_checks():
    return _CALL_CHECKS.get() or _FileChecks()


def _dependency_fingerprint(profile):
    """Hash current engine/rule bytes, never mtime or a request's success flag."""
    paths = set((ROOT / 'scripts').glob('*.py'))
    paths.update((ROOT / 'rulesets').glob('*.json'))
    if profile.get('document_manifest'):
        paths.add(_path(profile['document_manifest']))
    checks = _call_checks()
    return digest({str(path.resolve()): checks.hash(path) for path in sorted(paths)})


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
    if not isinstance(request, dict):
        raise ValueError('rating pipeline consumer must be a request object')
    purpose = request.get('purpose')
    if purpose not in ('writing', 'rating'):
        raise ValueError('rating-pipeline research takes purpose=rating or purpose=writing')
    standard, mode = request.get('standard', 'wangba'), request.get('mode', 'integrated')
    if mode not in ('integrated', 'normal', 'highest', 'lowball'):
        raise ValueError('rating pipeline selects integrated; legacy normal/highest/lowball require an explicit historical replay')
    profile = resolve(request.get('ruleset_profile'), standard)
    subjects = request.get('fighters' if purpose == 'writing' else 'characters', [])
    if not isinstance(subjects, list) or not subjects or any(not isinstance(s, dict) or
            not _text(s.get('id')) for s in subjects):
        raise ValueError('rating pipeline requires explicitly identified fighters')
    if len({s['id'] for s in subjects}) != len(subjects):
        raise ValueError('rating pipeline fighter IDs must be unique')
    return standard, mode, profile, subjects


def _research_plan(subject, mode):
    """Use the ordinary research planner for both callers, without narrative input."""
    from research import plan
    target = {'entity_id': subject['id'], 'name': subject.get('name', subject['id'])}
    for key in ('work', 'work_id', 'continuity', 'period', 'state', 'version',
                'equipment', 'medium', 'ending_locator', 'related_entities'):
        if key in subject:
            value = subject[key]
            if not (isinstance(value, dict) and value.get('needs_isolated_scope')):
                target[key] = copy.deepcopy(value)
    return plan({'target': target, 'modes': [mode]})


def _worker_instructions(mode, standard, text_only):
    """Supply the real common research workflow, rather than a packaging checklist.

    A host dispatches this task to its Agent tool (or performs it sequentially).
    This function is deliberately not a model runtime or a semantic validator.
    """
    instructions = (ROOT / 'references/character-rating-worker.md').read_text(encoding='utf-8-sig')
    instructions += ('\n\nEvidence medium: use texts and previously qualified evidence; do not '
                     'start new image/video downloads, frame extraction or pixel measurement.\n'
                     if text_only else '\n\nEvidence medium: use the ordinary evidence workflow; '
                     'inspect original images when the disputed proposition requires it.\n')
    instructions += '\nSkill root: ' + str(ROOT) + '\n'
    # Both callers use the same real references. Do not embed four complete
    # manuals again in every task; workers have the host's file-reading tools.
    instructions += '\nRead the shared workflow first; open the following references from disk as needed. Paths are not a claim that their contents have already been read.\n'
    for relative in ('references/character-rating-workflow.md',
                     'references/scaling-principles.md',
                     'references/evidence-gap-recovery.md',
                     'references/rating-card.md'):
        instructions += '\nSource: ' + str(ROOT / relative) + '\n'
    instructions += (f'\n\nAfter substantive research and coordinator review, any needed local '
                     f'CASE analysis uses --mode {mode} --standard {standard}. '
                     'Do not populate accepted host-review statements in a research worker.\n')
    return instructions


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
        for key in ('work', 'work_id', 'continuity', 'period', 'medium', 'ending_locator',
                    'related_entities', 'author_settings'):
            if key in subject:
                isolated[key] = copy.deepcopy(subject[key])
        # Do not seed canonical research with the writer's draft ratings/skill
        # selections. Explicit original/adapted settings remain authoritative
        # author inputs and keep the existing author_settings/basis_type route.
        authored = (bool(subject.get('author_settings')) or
                    subject.get('basis_type') == 'author_settings' or
                    any(isinstance(row, dict) and row.get('character_id') == subject['id']
                        and row.get('basis_type') == 'author_settings'
                        for row in request.get('independent_ratings', [])))
        provided = ({key: copy.deepcopy(subject[key]) for key in ('persona', 'skills', 'ratings')
                     if key in subject} if authored else {})
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
        text_only = request.get('mandatory_media_steps',
                                [] if request['purpose'] == 'writing' else None) == []
        packet = {'schema_version': 1, 'task_type': 'standalone_character_rating',
                  'character': isolated, 'standard': standard, 'mode': mode, **mode_metadata(mode),
                  'ruleset_profile': profile['id'],
                  'rules_fingerprint': digest(_profile_key(profile)),
                  'mandatory_media_steps': [] if text_only else ['original_visuals_when_needed'],
                  'scope_needs_host_isolation': masked,
                  'required_products': ['report.md', 'sources.json'],
                  'required_workflow': 'references/character-rating-workflow.md',
                  'semantic_work_performed_by': 'host; never the Python task planner',
                  'research_plan': _research_plan(isolated, mode)}
        instructions = _worker_instructions(mode, standard, text_only)
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


class _FileChecks:
    """Per-call only: resolve each declaration afresh, hash a target once.

    No mtime cache survives the call, so byte changes, source withdrawals and
    redirected Windows junctions still invalidate the next handoff.
    """
    def __init__(self):
        self.hashes, self.json, self.text = {}, {}, {}

    def hash(self, path):
        path = Path(path).resolve()
        if path not in self.hashes:
            self.hashes[path] = file_hash(path)
        return self.hashes[path]

    def read_json(self, path):
        path = Path(path).resolve()
        if path not in self.json:
            self.json[path] = _read(path)
        return self.json[path]

    def read_text(self, path):
        path = Path(path).resolve()
        if path not in self.text:
            # Refpack coordinates count the exact normalized UTF-8 characters,
            # not universal-newline-translated text or UTF-16 code units.
            self.text[path] = path.read_bytes().decode('utf-8')
        return self.text[path]


def _sources_valid(sources, directory, _checks=None):
    if not isinstance(sources, list) or not sources:
        raise ValueError('sources.json must contain actual standalone source records')
    seen, local_files = set(), []
    checks = _checks if _checks is not None else _call_checks()
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
            actual = checks.hash(path)
            # path from a novel refpack is its normalized text, whereas
            # source_sha256 identifies the original uploaded TXT/EPUB/PDF.
            for field in ('sha256', 'file_sha256', 'text_sha256'):
                expected = source.get(field)
                if field in source and actual != expected:
                    raise ValueError('local standalone source ' + field + ' hash differs: ' + source['id'])
            quote = source.get('quote')
            declared = (re.search(r'\[(\d+),\s*(\d+)\)', source.get('locator', ''))
                        if source.get('text_sha256') and isinstance(source.get('locator', ''), str) else None)
            coordinate = 'start' in source or 'end' in source or declared is not None
            if quote is not None or coordinate:
                text = checks.read_text(path)
                if coordinate:
                    start = source.get('start', int(declared[1]) if declared else None)
                    end = source.get('end', int(declared[2]) if declared else None)
                    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)):
                        raise ValueError('local source quote coordinates are invalid: ' + source['id'])
                    if declared and (start, end) != (int(declared[1]), int(declared[2])):
                        raise ValueError('local source quote coordinates disagree with its locator: ' + source['id'])
                    if quote is not None and (not _text(quote) or text[start:end] != quote):
                        raise ValueError('local source quote differs at its coordinates: ' + source['id'])
                    for field, offset in (('line_start', start), ('line_end', end - 1)):
                        if field in source and source[field] != text.count('\n', 0, offset) + 1:
                            raise ValueError('local source quote line coordinates differ: ' + source['id'])
                elif not _text(quote) or quote not in text:
                    raise ValueError('local source quote is absent from the supplied text: ' + source['id'])
            local_files.append({'path': _stored_path(path), 'sha256': actual, 'source_id': source['id']})
        elif 'text_sha256' in source or 'start' in source or 'end' in source:
            raise ValueError('normalized-text fingerprints and coordinates require their actual path: ' + source['id'])
        if source.get('source_path'):
            raw = _path(source['source_path'], directory)
            actual = checks.hash(raw)
            if 'source_sha256' in source and source['source_sha256'] != actual:
                raise ValueError('original standalone source hash differs: ' + source['id'])
            local_files.append({'path': _stored_path(raw), 'sha256': actual, 'source_id': source['id']})
        status_file = source.get('status_file')
        if status_file:
            path = _path(status_file, directory)
            status = checks.read_json(path)
            if not isinstance(status, dict) or status.get('status') != 'current':
                raise ValueError('source status file does not confirm current source: ' + source['id'])
            local_files.append({'path': _stored_path(path), 'sha256': checks.hash(path), 'source_id': source['id']})
    return local_files


def _read_artifact_uncached(artifact, subject, request, profile, hashes, _checks=None):
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
                          writing=True, qualitative_claims=case.get('qualitative_claims', []),
                          **({'rating_status': request['rating_status']}
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
    local_files = _sources_valid(sources, directory, _checks)
    receipt = {'character_id': subject['id'], 'artifact_dir': _stored_path(directory),
               'files': {name: {'path': _stored_path(path), 'sha256': hashes[name]} for name, path in paths.items()},
               'source_files': local_files, 'scope_sha256': digest(_scope(subject)),
               'rating_sha256': digest(row), 'sources_sha256': digest(sources),
               'reviewed_revision': acceptance['reviewed_revision']}
    return row, sources, receipt


def _read_artifact(artifact, subject, request, profile, *, _dependencies=None,
                   _expected_receipt=None, _stats=None, _checks=None):
    checks = _checks if _checks is not None else _call_checks()
    if artifact.get('dossier_file'):
        return _read_compact(artifact, subject, request, profile, checks, _expected_receipt, _stats, _dependencies)
    directory = _path(artifact['artifact_dir'])
    hashes = {name: checks.hash(directory / name) for name in FILES}
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
            current_sources = _sources_valid(cached[1], directory, checks)
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
    result = _read_artifact_uncached(artifact, subject, request, profile, hashes, checks)
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


def _read_compact(artifact, subject, request, profile, checks, expected_receipt=None, stats=None, dependencies=None):
    """Read one actual research document instead of eight transport files.

    Its report, source records and adjudicated row are one content object; the
    named coordinator's acceptance binds that content. CASE is optional: textual
    reasoning needs no invented compute run. Supplied CASE calculations really
    replay, and still cannot certify source entailment.
    """
    path = _path(artifact['dossier_file'])
    current_files = {'dossier.json': {'path': _stored_path(path), 'sha256': checks.hash(path)}}
    if expected_receipt is not None and expected_receipt.get('files', {}).get('dossier.json') != current_files['dossier.json']:
        raise ValueError('executed standalone dossier changed from its imported receipt')
    document = checks.read_json(path)
    if not isinstance(document, dict) or document.get('schema_version') != 1:
        raise ValueError('standalone dossier must be a schema_version=1 research document')
    acceptance = document.get('acceptance', {})
    content = {key: value for key, value in document.items() if key != 'acceptance'}
    row, sources = document.get('rating'), document.get('sources')
    if not isinstance(row, dict) or not _text(document.get('report')):
        raise ValueError('standalone dossier requires an actual readable report and one rating object')
    if not isinstance(document.get('character'), dict) or _scope(document['character']) != _scope(subject):
        raise ValueError('standalone dossier configuration does not match the requested character')
    if (document.get('ruleset_profile') != profile['id'] or
            document.get('rules_fingerprint') != digest(_profile_key(profile))):
        raise ValueError('standalone dossier reviewed rule profile/content differs from the requested configuration')
    host = row.get('host_review', {})
    if (not isinstance(acceptance, dict) or acceptance.get('status') != 'accepted' or
            not isinstance(host, dict) or
            not _text(acceptance.get('reviewer')) or acceptance.get('reviewer') != host.get('reviewer') or
            acceptance.get('reviewed_revision') != row.get('completion_review', {}).get('revision') or
            acceptance.get('content_sha256') != digest(content)):
        raise ValueError('standalone dossier requires current named host acceptance bound to its actual report/rating/source content')
    standard, mode = request.get('standard', 'wangba'), request.get('mode', 'integrated')
    case = document.get('case')
    calculation = document.get('calculation_case')
    if calculation is not None:
        if case is not None or not isinstance(calculation, dict) or not _text(calculation.get('path')):
            raise ValueError('standalone dossier calculation_case must identify one existing CASE, without a competing embedded case')
        case_path = _path(calculation['path'], path.parent)
        case_hash = checks.hash(case_path)
        if calculation.get('sha256') != case_hash:
            raise ValueError('standalone dossier calculation CASE hash differs from its reviewed reference')
        current_files['calculation-case.json'] = {'path': _stored_path(case_path), 'sha256': case_hash}
        case = checks.read_json(case_path)
    if expected_receipt is not None and expected_receipt.get('files') != current_files:
        raise ValueError('executed standalone dossier calculation files changed from their imported receipt')
    gate = review_ratings([subject], [row], sources, standard=standard, mode=mode,
                          qualitative_claims=case.get('qualitative_claims', []) if isinstance(case, dict) else (),
                          **({'rating_status': request['rating_status']} if 'rating_status' in request else {}))
    if gate['status'] != 'ready':
        raise ValueError(subject['id'] + ': ' + '; '.join(gate['needs']))
    if row.get('ruleset_profile', profile['id']) != profile['id']:
        raise ValueError('standalone dossier rule profile differs from the requested configuration')
    local_files = _sources_valid(sources, path.parent, checks)
    key = digest({'format': 'compact', 'files': current_files, 'scope': _scope(subject),
                  'standard': standard, 'mode': mode, 'profile': _profile_key(profile),
                  'rating_status': request.get('rating_status'), 'source_files': local_files,
                  'dependencies': dependencies or _dependency_fingerprint(profile)})
    cached = _ARTIFACT_CACHE.get(key)
    if cached is not None:
        _ARTIFACT_CACHE.move_to_end(key)
        if stats is not None:
            stats['cache_hits'] += 1
        return copy.deepcopy(cached)
    if case is not None:
        if (not isinstance(case, dict) or case.get('purpose') == 'writing' or 'matchup' in case or
                case.get('independent_ratings') != [row] or case.get('sources') != sources):
            raise ValueError('standalone dossier CASE must bind its same independent rating and sources without an opponent')
        targets = [s for s in case.get('characters', []) if isinstance(s, dict) and s.get('id') == subject['id']]
        if len(targets) != 1 or _scope(targets[0]) != _scope(subject):
            raise ValueError('standalone dossier CASE target configuration differs')
        if _profile_key(resolve(case.get('ruleset_profile'), case.get('standard'))) != _profile_key(profile):
            raise ValueError('standalone dossier CASE rule profile differs')
        from battle import compute_case
        from evidence import analyze_case
        analyzed = analyze_case(compute_case(case, mode, profile), mode, profile)
        if mode == 'integrated' and analyzed['rating_completion']['status'] != 'ready':
            raise ValueError('standalone dossier CASE does not support its current completion')
        if stats is not None:
            stats['replays'] += 1
    receipt = {'character_id': subject['id'], 'dossier_file': _stored_path(path),
               'files': current_files, 'source_files': local_files,
               'scope_sha256': digest(_scope(subject)), 'rating_sha256': digest(row),
               'sources_sha256': digest(sources), 'reviewed_revision': acceptance['reviewed_revision'],
               'local_analysis_included': case is not None}
    result = copy.deepcopy(row), copy.deepcopy(sources), receipt
    _ARTIFACT_CACHE[key] = copy.deepcopy(result)
    _ARTIFACT_CACHE.move_to_end(key)
    while len(_ARTIFACT_CACHE) > _CACHE_LIMIT:
        _ARTIFACT_CACHE.popitem(last=False)
    return result


def _import_key(rows, sources):
    return digest({'ratings': sorted(rows, key=lambda row: row['character_id']),
                   'sources': sorted(sources, key=lambda source: source['id'])})


@handoff_scoped
def assemble(request):
    if 'writing_request' in request and 'rating_request' in request:
        raise ValueError('assemble takes one research consumer, not two competing requests')
    request_key = 'rating_request' if 'rating_request' in request else 'writing_request'
    writing = copy.deepcopy(request.get(request_key, {}))
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
    checks = _call_checks()
    for subject in subjects:
        row, sources, receipt = _read_artifact(mapping[subject['id']], subject, writing, profile,
                                              _dependencies=dependencies, _checks=checks)
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
    view_key = 'fighters' if writing['purpose'] == 'writing' else 'characters'
    writing[view_key], override_needs = subject_views(subjects, rows, standard, mode,
        sources=writing['sources'], allow_author_overrides=writing['purpose'] == 'writing')
    if override_needs:
        raise ValueError('; '.join(override_needs))
    execution = {'schema_version': 1, 'standard': standard, 'mode': mode, **mode_metadata(mode),
                 'rules_fingerprint': digest(_profile_key(profile)), 'artifacts': receipts,
                 'source_ids': sorted(imported_sources),
                 'import_sha256': _import_key(rows, list(imported_sources.values())),
                 'semantic_rating_verified': False, 'validation_scope': LIMIT}
    writing['rating_execution'] = execution
    return {'status': 'assembled', 'stage': 'reviewed_artifacts_imported',
            request_key: writing, 'rating_execution': execution,
            'next_step': ('Run battle.py writing with writing_request after completing its authored settings.'
                          if writing['purpose'] == 'writing' else
                          'Use rating_request as the independently researched CASE input; add the requested matchup only after every participant dossier is ready.'),
            'semantic_rating_verified': False, 'validation_scope': LIMIT}


@handoff_scoped
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
        checks = _call_checks()
        for subject in subjects:
            stored = mapping[subject['id']]
            # Check old hashes before loading; a newly accepted revision needs
            # a fresh import rather than silently retaining the old story plan.
            file_records = stored.get('files', {})
            if stored.get('dossier_file'):
                files_valid = (isinstance(file_records, dict) and 'dossier.json' in file_records and
                               not (set(file_records) - {'dossier.json', 'calculation-case.json'}))
            else:
                files_valid = isinstance(file_records, dict) and set(file_records) == set(FILES)
            if not files_valid:
                raise ValueError('rating execution must bind every required standalone product')
            row, sources, current = _read_artifact(stored, subject, request, profile,
                                                  _dependencies=dependencies,
                                                  _expected_receipt=stored, _stats=stats, _checks=checks)
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
        # Authored overlays can add provided sources after a canonical import;
        # their explicit withdrawals/local-text contracts still apply.
        extra_sources = [source for source in supplied_sources if source['id'] not in source_map]
        if extra_sources:
            _sources_valid(extra_sources, ROOT, checks)
        _, override_needs = subject_views(subjects, rows, standard, mode,
            sources=supplied_sources, allow_author_overrides=request.get('purpose') == 'writing')
        if override_needs:
            raise ValueError('; '.join(override_needs))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        needs.append(str(exc))
    result = {'status': 'needs_research' if needs else 'ready', 'needs': needs,
              'dossier_contents_read_by_checker': not needs,
              'local_analysis_replayed': not needs and stats['replays'] > 0,
              'local_analysis_verified': not needs and all(entry.get('local_analysis_included', True) for entry in receipts),
              'semantic_rating_verified': False,
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


def review_handoff(request, *, standard=None, mode=None, allow_synthetic=False):
    """Shared ordinary-PK/story handoff; no extra eight-file gate for PK.

    Explicit synthetic tool fixtures may exercise combat math without claiming
    real research. Real canon and authored characters consume the same current
    dossier (compact or historical bundle) regardless of presentation.
    """
    normalized = copy.deepcopy(request)
    normalized['standard'] = standard or normalized.get('standard', 'wangba')
    normalized['mode'] = mode or normalized.get('mode', 'integrated')
    if normalized.get('purpose') != 'writing':
        normalized['purpose'] = 'rating'
    fixture = normalized.get('fixture_kind', '')
    source_list = normalized.get('sources', [])
    if isinstance(source_list, dict):
        source_list = list(source_list.values())
        normalized['sources'] = source_list
    if (allow_synthetic and 'rating_execution' not in normalized and normalized.get('purpose') != 'writing' and
            isinstance(fixture, str) and fixture.startswith('synthetic') and source_list and
            all(isinstance(s, dict) and (s.get('origin') in ('synthetic', 'author_settings') or
                str(s.get('fixture_kind', '')).startswith('synthetic')) for s in source_list)):
        return {'status': 'ready', 'needs': [], 'dossier_contents_read_by_checker': False,
                'local_analysis_verified': False, 'semantic_rating_verified': False,
                'synthetic_fixture_only': True, 'validation_scope': 'Explicit invented tool fixture; no real character research is claimed.'}
    return verify_execution(normalized)


@handoff_scoped
def run(request):
    if not isinstance(request, dict):
        raise ValueError('rating-pipeline request must be an object')
    operation = request.get('operation', 'plan')
    if operation == 'plan':
        if not request.get('output_dir'):
            raise ValueError('rating-pipeline plan needs an output_dir for actual task files')
        if 'rating_request' in request and 'writing_request' in request:
            raise ValueError('plan takes one character research request, not two competing callers')
        tasks = tasks_for(request.get('rating_request', request.get('writing_request', {})), request['output_dir'])
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
                result['character_tasks'] = tasks_for(request.get('rating_request', request.get('writing_request', {})))
            except (ValueError, TypeError):
                result['character_tasks'] = []
            return result
    raise ValueError('rating-pipeline operation must be plan, assemble or assemble-and-prepare')
