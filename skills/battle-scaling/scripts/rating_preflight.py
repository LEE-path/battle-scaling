"""Shared admission gate for already completed independent character ratings.

This does not derive tiers, read dossier files, authenticate sources, or verify a
host's semantic acceptance. A declaration of a winner is never a rating dossier.
Both evidence PK and authored fiction must supply the same scoped nine-field
packet before their downstream combat work can be marked ready.
"""
from __future__ import annotations

import copy
from functools import lru_cache
import json
from pathlib import Path
import re
from rating_modes import metadata as mode_metadata

RATING_FIELDS = ('输出', '体防', '智力', '战斗智商', '经验', '特殊技能', '破坏', '速度', '体量')
PHYSICAL_FIELDS = {'输出', '体防', '破坏'}
BASES = {'lower_bound', 'estimate', 'exact'}
READ_ACCESS = {'provided', 'read', 'readable', 'verified', 'verified_via_host_browser'}
VAGUE = ('未知', '未定', '待定', '不明', '待核', '无法衡量', '无法量化', '不清楚',
         'unknown', 'undetermined', 'uncertain', 'tbd', 'unspecified', 'needs_research')
VAGUE_LEVELS = {'高速', '极快', '高等超人类', '人形', '超人类', '强大', '巨大',
                'high speed', 'very fast', 'superhuman', 'humanoid'}
STATUS_UNSET = object()
SCOPE = ('Checks declared independent-rating scope, nine dimensions, named tier '
         'membership, completion and selection audits, supplied current-status '
         'revision bindings, usable source references and host acceptance only. It does '
         'not authenticate sources, read a referenced dossier, verify derivations, '
         'or establish that the host actually performed the semantic review.')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _concrete(value):
    return (_text(value) and not any(word in value.casefold() for word in VAGUE)
            and value.strip().casefold() not in {'?', '??', 'n/a', 'na', '特殊', '很强', '很弱', '高', '低', '强', '弱'} | VAGUE_LEVELS)


@lru_cache(maxsize=16)
def _tiers(standard, ruleset=None):
    """Reuse bundled named rules; no second tier calculation algorithm."""
    root = Path(__file__).resolve().parents[1] / 'rulesets'
    if standard == 'vsb':
        if ruleset and ruleset not in ('vsb-current-2026-10-21', 'vsb-high-current-2026-10-21'):
            return frozenset()
        table = json.loads((root / 'vsb-current-2026-10-21.json').read_text(encoding='utf-8'))
        codes = {row['tier'] for row in table['attack_potency']['finite_tiers']}
        from vsb_high import RULES
        return frozenset(codes | set(RULES))
    names = {'普通人级', '普通人', '运动员级', '运动员', '人类极限级', '人类极限'}
    def add(label):
        label = re.sub(r'（[^（）]+）$', '', label.replace('标准', '标'))
        names.add(label)
        if label.startswith('论外天花板'):
            names.add(label.removeprefix('论外'))
    def collect(value):
        if isinstance(value, dict):
            for key in ('label', 'name'):
                if _text(value.get(key)):
                    names.add(value[key].replace('标准', '标'))
                    add(value[key])
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    finite = json.loads((root / 'wangba-handbook-2026-07-30-finite.json').read_text(encoding='utf-8'))
    collect(finite.get('energy_references', []))
    collect(finite.get('astronomical_references', []))
    collect(finite.get('qualitative_astronomical_references', []))
    base_name = 'high-wangba-handbook-2026-07-30'
    base = json.loads((root / (base_name + '.json')).read_text(encoding='utf-8'))
    collect(base.get('ordinal_patterns', []))
    if _text(base.get('outer_label')):
        names.add(base['outer_label'])
        add(base['outer_label'])
    if ruleset:
        if not isinstance(ruleset, str) or Path(ruleset).name != ruleset:
            return frozenset()
        path = root / (ruleset if ruleset.endswith('.json') else ruleset + '.json')
        if not path.is_file() or not path.name.startswith('high-wangba-'):
            return frozenset()
        selected = json.loads(path.read_text(encoding='utf-8'))
        collect(selected.get('rules', []))
    return frozenset(names)


def _tier(value, standard, ruleset=None):
    if not _concrete(value):
        return False
    if standard == 'vsb':
        # Accept the code or the code followed by the official display label.
        match = re.fullmatch(r'((?:(?:Low|High) )?\d+(?:-[ABC])?)(?: \([^()]+\))?', value.strip())
        return bool(match and match.group(1) in _tiers(standard, ruleset))
    label = value.strip().replace('标准', '标')
    # Handbook rows abbreviate e.g. 标墙; user-facing cards use 标准爆墙.
    names = _tiers(standard, ruleset)
    return label in names or re.sub(r'^(弱|标|强|超)爆', r'\1', label) in names


def process_subjects(request):
    """Use CASE identities carried to a trace, preserving explicit actor overrides."""
    identities = request.get('rating_subjects', [])
    identities = {item['id']: item for item in identities if isinstance(item, dict) and _text(item.get('id'))} if isinstance(identities, list) else {}
    actors = request.get('actors', [])
    if not isinstance(actors, list):
        return []
    return [{**copy.deepcopy(identities.get(item.get('id'), {}) if _text(item.get('id')) else {}),
             **{key: copy.deepcopy(item[key]) for key in ('id', 'version', 'state', 'equipment') if key in item}}
            for item in actors if isinstance(item, dict)]


def review(subjects, ratings, sources, *, standard='wangba', mode='integrated', writing=False,
           rating_status=STATUS_UNSET):
    """Return ready/needs_research; missing evidence never becomes a draw.

    ratings=[{character_id,standard,mode,version,state,equipment,basis_type,
      main_tier:{label,basis,evidence_ids,reasoning}, dimensions:{Chinese field:
      {label,kind:tier|level,basis,evidence_ids,reasoning}},
      completion_review:{status:complete,revision,selected_basis:mode_representative,
        scope_findings:{reasoning,evidence_ids}, selection_findings:{reasoning,evidence_ids},
        candidates:[{id,affects,disposition,impact,reasoning,evidence_ids}]},
      host_review:{status:accepted,reviewer,dossier_ref,reviewed_revision}}].
    A genuinely inapplicable dimension additionally needs not_applicable=true,
    sourced reasoning and an explicit alternative assessment of the same form.
    Numeric masses, IQs and invented HP are deliberately not required.
    """
    needs = []
    status_supplied = rating_status is not STATUS_UNSET
    revisions_supplied = isinstance(rating_status, dict) and 'revisions' in rating_status
    revisions = {}
    if status_supplied:
        if not isinstance(rating_status, dict):
            needs.append('rating_status must be a supplied current-status object, not a ready boolean or null.')
        else:
            if rating_status.get('status') != 'current':
                needs.append('rating_status is not current: withdrawn, superseded or incomplete ratings cannot open combat admission.')
            if mode == 'integrated' and 'accepted_complete_integrated_ratings' in rating_status:
                accepted_integrated = rating_status['accepted_complete_integrated_ratings']
                if not isinstance(accepted_integrated, bool):
                    needs.append('rating_status.accepted_complete_integrated_ratings must be an explicit boolean.')
                elif accepted_integrated is False:
                    needs.append('rating_status explicitly withdraws integrated-rating acceptance.')
            if 'accepted_complete_normal_ratings' in rating_status:
                complete_normal = rating_status['accepted_complete_normal_ratings']
                if not isinstance(complete_normal, bool):
                    needs.append('rating_status.accepted_complete_normal_ratings must be an explicit boolean.')
                elif mode == 'normal' and complete_normal is False:
                    needs.append('rating_status explicitly withdraws complete normal-rating acceptance.')
            if 'revisions' in rating_status:
                revisions = rating_status['revisions']
                if (not isinstance(revisions, dict) or
                        any(not _text(key) or not _text(value) for key, value in revisions.items())):
                    needs.append('rating_status.revisions must map participant IDs to nonempty current revisions.')
                    revisions = {}
    if standard not in ('wangba', 'vsb') or mode not in ('integrated', 'normal', 'highest', 'lowball'):
        needs.append('Select a valid rating standard and evidence mode.')
    source_list = list(sources.values()) if isinstance(sources, dict) else sources
    source_map = {s.get('id'): s for s in source_list if isinstance(s, dict) and _text(s.get('id'))} if isinstance(source_list, list) else {}
    if not isinstance(ratings, list):
        needs.append('independent_ratings must be a list of completed character-rating packets.')
        ratings = []
    if not isinstance(subjects, list) or not subjects:
        needs.append('Provide the exact participant version, state and equipment scope.')
        subjects = []
    accepted = []
    status_valid = not needs
    def references(node, path, basis_type):
        refs = node.get('evidence_ids')
        if not isinstance(refs, list) or not refs or any(not _text(rid) for rid in refs):
            needs.append(path + ' needs source evidence_ids.')
            return
        origins = set()
        for rid in refs:
            source = source_map.get(rid, {})
            if source.get('access') not in READ_ACCESS or not _text(source.get('locator')) or not _text(source.get('origin')):
                needs.append(path + ': source ' + rid + ' is missing, unread, indexed-only or lacks provenance.')
            if basis_type == 'canon' and source.get('origin') == 'author_settings':
                needs.append(path + ': author settings cannot masquerade as canon evidence.')
            if basis_type == 'author_settings' and source.get('origin') != 'author_settings':
                needs.append(path + ': cite the actual author-setting source for an authored rating.')
            origins.add('author_settings' if source.get('origin') == 'author_settings' else 'canon')
        if basis_type == 'mixed' and not {'canon', 'author_settings'} <= origins:
            needs.append(path + ': mixed derivations must cite both canon and the actual author override.')
    def assessment(node, path, basis_type, require_tier=False, default_ruleset=None):
        if not isinstance(node, dict):
            needs.append(path + ' needs a completed independent assessment, not a bare label.')
            return
        basis_type = node.get('basis_type', basis_type)
        ruleset = node.get('ruleset', default_ruleset)
        if basis_type not in ('canon', 'author_settings', 'mixed'):
            needs.append(path + '.basis_type must distinguish canon, author_settings or an explicit mixed derivation.')
        if not _text(node.get('reasoning')):
            needs.append(path + ' needs a sourced derivation or conservative lower-bound argument.')
        references(node, path, basis_type)
        if require_tier and node.get('proves_character_property') is False:
            needs.append(path + ' explicitly does not prove a character property and cannot supply a main or physical attribute tier.')
        if require_tier and standard == 'wangba' and node.get('mapping_kind') == 'energy_reference':
            needs.append(path + ' is a Wangba energy reference, not an established character property; retain it as supporting reference instead.')
        if node.get('not_applicable') is True:
            if require_tier and path.endswith('.main_tier'):
                needs.append(path + ' cannot waive the main tier as not applicable.')
            alternative = node.get('alternative')
            if isinstance(alternative, dict) and alternative.get('not_applicable') is not True:
                assessment(alternative, path + '.alternative', basis_type, default_ruleset=ruleset)
            else:
                needs.append(path + ' needs a concrete alternative assessment and evidenced non-applicability.')
            return
        if node.get('basis') not in BASES:
            needs.append(path + ' needs an established lower_bound, estimate or exact result; an upper bound alone is insufficient.')
        kind = node.get('kind', 'tier' if require_tier else None)
        if require_tier or kind == 'tier':
            if standard in ('wangba', 'vsb') and not _tier(node.get('label'), standard, ruleset):
                needs.append(path + ' must name one specific tier in the selected standard, including its available subdivision.')
        elif kind != 'level' or not _concrete(node.get('label')):
            needs.append(path + ' needs a concrete evidence-backed ability level; no invented explosive tier or numbers are required.')

    def finding(node, path, basis_type):
        if not isinstance(node, dict):
            needs.append(path + ' needs a sourced completion finding.')
            return
        if not _text(node.get('reasoning')):
            needs.append(path + ' needs a reasoned scope, selection or candidate finding.')
        finding_basis = node.get('basis_type', basis_type)
        if finding_basis not in ('canon', 'author_settings', 'mixed'):
            needs.append(path + '.basis_type must distinguish canon, author_settings or mixed.')
        references(node, path, finding_basis)

    def completion(row, host, prefix, basis_type):
        audit = row.get('completion_review')
        path = prefix + '.completion_review'
        if not isinstance(audit, dict):
            needs.append(path + ' is required; legacy labels, local calculations and old ready receipts are not completed mode-specific ratings.')
            return
        if audit.get('status') != 'complete':
            needs.append(path + '.status must be complete; partial, withdrawn or superseded ratings require renewed research and acceptance.')
        revision = audit.get('revision')
        if not _text(revision):
            needs.append(path + '.revision must name the actual reviewed dossier revision.')
        if not isinstance(host, dict) or not _text(revision) or host.get('reviewed_revision') != revision:
            needs.append(prefix + '.host_review.reviewed_revision must match completion_review.revision.')
        sid = row.get('character_id')
        if revisions_supplied and sid not in revisions:
            needs.append(path + '.revision is absent from the supplied current-status revision map.')
        elif sid in revisions and revisions[sid] != revision:
            needs.append(path + '.revision differs from the supplied current-status revision.')
        if audit.get('selected_basis') != 'mode_representative':
            needs.append(path + '.selected_basis must be mode_representative; a local_floor alone is not a completed integrated assessment (or an explicitly selected historical assessment).')
        for key in ('scope_findings', 'selection_findings'):
            finding(audit.get(key), path + '.' + key, basis_type)
        items = audit.get('candidates')
        if not isinstance(items, list):
            needs.append(path + '.candidates must explicitly list reviewed material candidates, or be empty after the sourced scope review.')
            return
        seen = set()
        for index, candidate in enumerate(items):
            cpath = path + '.candidates.' + str(index)
            if not isinstance(candidate, dict):
                needs.append(cpath + ' must be an assessed candidate object.')
                continue
            cid = candidate.get('id')
            if not _text(cid) or cid in seen:
                needs.append(cpath + '.id must be nonempty and unique within the completion review.')
            else:
                seen.add(cid)
            affects = candidate.get('affects')
            if (not isinstance(affects, list) or not affects or
                    any(field not in (*RATING_FIELDS, 'main_tier') for field in affects)):
                needs.append(cpath + '.affects must name the main_tier or affected rating dimensions.')
            disposition = candidate.get('disposition')
            impact = candidate.get('impact')
            if disposition not in ('adopted', 'excluded', 'open'):
                needs.append(cpath + '.disposition must be adopted, excluded or open.')
            if impact not in ('material', 'non_material'):
                needs.append(cpath + '.impact must distinguish material from non_material candidates.')
            if disposition == 'open' and impact == 'material':
                needs.append(cpath + ': an open material candidate prevents complete mode-specific rating admission.')
            finding(candidate, cpath, basis_type)

    for subject in subjects:
        if not isinstance(subject, dict) or not _text(subject.get('id')):
            needs.append('Every rating subject needs a nonempty id.')
            continue
        sid = subject['id']
        prefix = 'independent_ratings.' + sid
        candidates = [row for row in ratings if isinstance(row, dict) and row.get('character_id') == sid
                      and row.get('mode') == mode and row.get('standard') == standard]
        if len(candidates) != 1:
            needs.append(prefix + ': provide exactly one independent rating for this participant, standard and mode.')
            continue
        row = candidates[0]
        before = len(needs)
        for field in ('version', 'state', 'equipment'):
            expected = subject.get(field)
            shape_ok = (_concrete(expected) if isinstance(expected, str) else
                        isinstance(expected, (dict, list)) and (field == 'equipment' or bool(expected)))
            if field == 'version':
                shape_ok = _concrete(expected)
            if not shape_ok or row.get(field) != expected:
                needs.append(prefix + '.' + field + ' must explicitly match the actual participant configuration.')
        basis_type = row.get('basis_type')
        if basis_type not in ('canon', 'author_settings', 'mixed'):
            needs.append(prefix + '.basis_type must distinguish canon, author_settings or mixed.')
        host = row.get('host_review', {})
        if not isinstance(host, dict) or host.get('status') != 'accepted' or not _text(host.get('reviewer')) or not _text(host.get('dossier_ref')):
            needs.append(prefix + ' requires a named host acceptance and independent dossier_ref before combat planning.')
        completion(row, host, prefix, basis_type)
        assessment(row.get('main_tier'), prefix + '.main_tier', basis_type, True, row.get('ruleset'))
        dimensions = row.get('dimensions', {})
        if not isinstance(dimensions, dict):
            dimensions = {}
        for field in RATING_FIELDS:
            assessment(dimensions.get(field), prefix + '.dimensions.' + field, basis_type, field in PHYSICAL_FIELDS, row.get('ruleset'))
            dimension = dimensions.get(field)
            if field in ('智力', '战斗智商', '经验') and isinstance(dimension, dict) and dimension.get('kind') == 'tier':
                needs.append(prefix + '.dimensions.' + field + ' must use an ability level, never an explosive tier.')
        if status_valid and len(needs) == before:
            accepted.append(sid)
    return {'status': 'needs_research' if needs else 'ready', 'standard': standard, 'mode': mode, **mode_metadata(mode),
            'accepted_subject_ids': accepted, 'needs': list(dict.fromkeys(needs)),
            'research_tasks': ['Complete each integrated dossier scope, material outer relationships, candidate and selection review, refresh its current validity, and bind host acceptance to the reviewed revision before combat planning. Preserve local floors as evidence, not substitutes for representative selection; missing ratings do not imply a draw.'] if needs else [],
            'host_acceptance_is_declaration': True, 'source_authenticity_verified': False,
            'completion_review_is_declaration': True, 'current_status_supplied': status_supplied,
            'latest_external_status_verified': False,
            'dossier_contents_read_by_checker': False, 'semantic_rating_verified': False,
            'validation_scope': SCOPE}
