"""One adjudicated rating row, with disposable presentation views.

Evidence/candidate assessments remain independent premises. A selected assessment
cannot contradict the accepted row; Python never resolves that disagreement by
rewriting canon or manufacturing a new host acceptance.
"""
from __future__ import annotations

import copy
import re


def selected_rows(request, standard, mode):
    return {row.get('character_id'): row for row in request.get('independent_ratings', [])
            if isinstance(row, dict) and row.get('standard') == standard and row.get('mode') == mode}


def _label(value, standard):
    if not isinstance(value, str):
        return value
    value = value.strip()
    if standard == 'vsb':
        return re.sub(r' \([^()]+\)$', '', value)
    return re.sub(r'^(弱|标|强|超)爆', r'\1', value.replace('标准', '标'))


def _selection(node, standard):
    if not isinstance(node, dict):
        return None
    return (_label(node.get('label'), standard), bool(node.get('not_applicable')),
            _selection(node.get('alternative'), standard) if node.get('not_applicable') else None)


def _display_label(node):
    if not isinstance(node, dict):
        return None
    if node.get('not_applicable'):
        alternative = node.get('alternative')
        return alternative.get('label') if isinstance(alternative, dict) else None
    return node.get('label')


def consistency_needs(request, standard, mode):
    """Compare only selected conclusions, never flatten evidence/counterexamples."""
    from rating_preflight import RATING_FIELDS
    rows = selected_rows(request, standard, mode)
    needs = []
    for claim in request.get('qualitative_claims', []):
        if not isinstance(claim, dict) or not isinstance(claim.get('assessment'), dict):
            continue
        if mode != 'integrated' and mode not in claim.get('modes', [mode]):
            continue
        if mode == 'integrated' and 'modes' in claim and 'integrated' not in claim['modes']:
            continue  # Historical/high/low showings remain performance evidence.
        if claim.get('assessment_role') in ('candidate', 'supporting', 'counter'):
            continue
        if (claim.get('assessment_role') != 'selected' and
                claim.get('kind') in ('feat', 'anti_feat', 'statement', 'mechanism', 'cosmology', 'encounter')):
            continue
        row = rows.get(claim.get('subject'))
        field = claim.get('attribute')
        if row is None or field not in ('main_tier', *RATING_FIELDS):
            continue
        if any(key in claim and claim[key] != row.get(key) for key in ('version', 'state', 'equipment')):
            continue
        node = row.get('main_tier') if field == 'main_tier' else row.get('dimensions', {}).get(field)
        assessment = claim['assessment']
        differs = _selection(assessment, standard) != _selection(node, standard)
        if isinstance(node, dict):
            for key in ('basis', 'basis_type', 'ruleset', 'kind', 'proves_character_property'):
                default = row.get(key) if key in ('basis_type', 'ruleset') else (
                    'tier' if key == 'kind' and field in ('main_tier', '输出', '体防', '破坏') else
                    True if key == 'proves_character_property' else None)
                if key in assessment and assessment[key] != node.get(key, default):
                    differs = True
        if differs:
            needs.append('qualitative_claims.' + str(claim.get('id', '?')) + '.assessment conflicts with '
                         'the authoritative independent_ratings.' + str(claim.get('subject')) + '.' + field +
                         '; review the actual conclusion, or identify a genuine candidate/counter assessment.')
    return needs


def subject_views(subjects, rows, standard, mode, *, sources=(), allow_author_overrides=False):
    """Return fresh views; draft labels have no authority over reviewed rows.

    A writing-only author overlay cites the actual supplied author settings and
    replaces only named fields. It never changes a canon row or copies canon's
    host acceptance onto the author's new premises.
    """
    from rating_preflight import RATING_FIELDS, PHYSICAL_FIELDS, BASES, _tier, _concrete
    mapping = selected_rows({'independent_ratings': rows}, standard, mode)
    source_list = list(sources.values()) if isinstance(sources, dict) else sources
    source_map = {s.get('id'): s for s in source_list if isinstance(s, dict)}

    def authored_assessment(node, field, physical, default_basis='author_settings'):
        if not isinstance(node, dict) or node.get('basis_type', default_basis) != 'author_settings':
            return False
        refs, reasoning = node.get('evidence_ids'), node.get('reasoning')
        if (not isinstance(reasoning, str) or not reasoning.strip() or not isinstance(refs, list) or not refs or
                not all(isinstance(ref, str) and source_map.get(ref, {}).get('origin') == 'author_settings' and
                        source_map[ref].get('access') == 'provided' and
                        isinstance(source_map[ref].get('locator'), str) and source_map[ref]['locator'].strip()
                        for ref in refs)):
            return False
        if node.get('not_applicable'):
            return field != 'main_tier' and authored_assessment(node.get('alternative'), field, False)
        if node.get('basis') not in BASES:
            return False
        if field in ('智力', '战斗智商', '经验') and node.get('kind') == 'tier':
            return False
        return (_tier(node.get('label'), standard, node.get('ruleset')) if physical or node.get('kind') == 'tier'
                else node.get('kind') == 'level' and _concrete(node.get('label')))

    views, needs = [], []
    for original in subjects:
        view = copy.deepcopy(original)
        if not isinstance(view, dict):
            views.append(view)
            continue
        row = mapping.get(view.get('id'))
        if row is None:
            views.append(view)
            continue
        overrides = view.get('author_rating_overrides', {})
        if not isinstance(overrides, dict):
            needs.append(str(view.get('id')) + '.author_rating_overrides must name explicit reviewed attributes.')
            overrides = {}
        for field, override in overrides.items():
            node = row.get('main_tier') if field == 'main_tier' else row.get('dimensions', {}).get(field)
            physical = field == 'main_tier' or field in PHYSICAL_FIELDS
            authored = (allow_author_overrides and isinstance(override, dict) and
                        override.get('basis_type') == 'author_settings' and
                        authored_assessment(override, field, physical))
            already_reviewed = (isinstance(node, dict) and isinstance(override, dict) and
                                node.get('basis_type', row.get('basis_type')) in ('author_settings', 'mixed') and
                                override == node)
            if field not in ('main_tier', *RATING_FIELDS) or not (authored or already_reviewed):
                needs.append(str(view.get('id')) + '.author_rating_overrides.' + field +
                             ' requires a specific assessment citing the actual supplied author settings; canon acceptance is not override acceptance.')
        view['ratings'] = {field: copy.deepcopy(_display_label(row.get('dimensions', {}).get(field)))
                           for field in RATING_FIELDS}
        for field, node in overrides.items():
            if field in RATING_FIELDS and isinstance(node, dict):
                view['ratings'][field] = copy.deepcopy(_display_label(node))
        view['main_tier'] = copy.deepcopy(_display_label(overrides.get('main_tier', row.get('main_tier'))))
        view['rating_ref'] = {'character_id': row['character_id'], 'standard': standard, 'mode': mode,
                              'revision': row.get('completion_review', {}).get('revision')}
        if overrides:
            view['rating_ref']['author_override_fields'] = sorted(overrides)
            view['rating_ref']['override_authority'] = 'explicit_author_settings; canonical host acceptance applies only to the unchanged canonical row'
        views.append(view)
    return views, needs
