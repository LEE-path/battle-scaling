"""Check declared canon-writing references and cross-system scene bindings.

This optional helper checks metadata only. A source id, a populated profile or
a scene tag does not establish that the host read a source, represented the
character faithfully, or wrote a causally sound fight.
"""
from __future__ import annotations


CANON_AXES = (
    'voice', 'narration', 'ability_expression', 'combat_patterns',
    'decisions', 'aftermath',
)
INTERACTION_FIELDS = ('contact_rule', 'activation', 'contestation', 'consequence')
INTERACTION_BASES = ('canon', 'creative_bridge', 'author_override')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _content(value):
    """Reject nested empty containers and whitespace-only content."""
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_content(item) for item in value.values())
    if isinstance(value, list):
        return any(_content(item) for item in value)
    return value is not None and isinstance(value, (bool, int, float))


def _description(value):
    return isinstance(value, (str, dict, list)) and _content(value)


def _strings(value, path, errors):
    if not isinstance(value, list) or any(not _text(item) for item in value):
        errors.append(path + ' must be a list of nonempty strings')
        return []
    if len(set(value)) != len(value):
        errors.append(path + ' must not contain duplicate references')
    return value


def review_fidelity(request, fighter_ids, beat_ids):
    """Review the opt-in ``canon_fidelity`` author-packet extension.

    ``canon_profiles`` is a list keyed by unique fighter_id. Each profile has
    scope, references=[{id,locator,scene,kind}], the six CANON_AXES, and a
    support={axis:[reference_id,...]} mapping into its own references. Reference
    ids must also be globally unique for unambiguous system-interaction links.

    ``system_interactions`` may be empty (e.g. same-system sparring). Entries
    have id, participants (at least two different known fighters), the four
    INTERACTION_FIELDS, and basis. Canon basis needs source_refs; a creative
    bridge or author override needs setup_refs containing concise pointers to
    existing mechanism/setup declarations. These strings are not semantically
    resolved. Optional source_refs always point into the declared references.

    In review operation, draft.beats[].system_interactions=[id,...] declares
    where each planned interaction appears. An interaction can span multiple
    beats. Bindings and reference coverage never prove prose implementation.
    ``fighter_ids`` and ``beat_ids`` are the host's already validated id sets.
    """
    if not isinstance(request, dict):
        raise ValueError('writing fidelity request must be an object')
    errors, needs, revision = [], [], []
    result = {
        'requested': False,
        'errors': errors,
        'needs': needs,
        'revision_tasks': revision,
        'coverage': {'profiles': [], 'system_interactions': []},
        'host_tasks': [],
        'semantic_fidelity_verified': False,
        'source_accuracy_verified': False,
        'sources_read_verified': False,
        'interaction_semantics_verified': False,
        'prose_implementation_verified': False,
        'validation_scope': (
            'Checks opt-in profile fields, source-reference identifiers and '
            'declared interaction-to-beat coverage only. It does not read '
            'sources, verify attribution, certify characterization or style, '
            'resolve cross-world mechanics, or inspect prose entailment.'
        ),
    }
    enabled = request.get('canon_fidelity', False)
    if not isinstance(enabled, bool):
        errors.append('canon_fidelity must be a boolean')
        return result
    if not enabled:
        return result
    result['requested'] = True
    fighter_ids, beat_ids = set(fighter_ids), set(beat_ids)
    profiles = request.get('canon_profiles', [])
    if not isinstance(profiles, list):
        errors.append('canon_profiles must be a list')
        profiles = []
    seen_fighters, reference_ids = set(), set()
    for index, profile in enumerate(profiles):
        path = f'canon_profiles[{index}]'
        if not isinstance(profile, dict):
            errors.append(path + ' must be an object')
            continue
        fid = profile.get('fighter_id')
        if not _text(fid) or fid not in fighter_ids:
            errors.append(path + '.fighter_id references an unknown fighter')
            continue
        if fid in seen_fighters:
            errors.append(path + '.fighter_id must not duplicate a fighter profile')
            continue
        seen_fighters.add(fid)
        if not _description(profile.get('scope')):
            needs.append(path + '.scope needs the specific version and state being represented.')
        for axis in CANON_AXES:
            if not _description(profile.get(axis)):
                needs.append(path + '.' + axis + ' needs a concrete canon-writing profile.')
        references = profile.get('references', [])
        if not isinstance(references, list):
            errors.append(path + '.references must be a list')
            references = []
        if not references:
            needs.append(path + '.references needs traceable representative original-work scenes.')
        local_refs = set()
        for ri, reference in enumerate(references):
            rpath = f'{path}.references[{ri}]'
            if not isinstance(reference, dict):
                errors.append(rpath + ' must be an object')
                continue
            rid = reference.get('id')
            if not _text(rid):
                errors.append(rpath + '.id must be a nonempty string')
                continue
            if rid in reference_ids:
                errors.append(rpath + '.id must be globally unique')
            reference_ids.add(rid)
            local_refs.add(rid)
            for field in ('locator', 'scene', 'kind'):
                if not _text(reference.get(field)):
                    needs.append(rpath + '.' + field + ' needs an explicit source locator or scene description.')
        support = profile.get('support', {})
        if not isinstance(support, dict):
            errors.append(path + '.support must map profile axes to reference-id lists')
            support = {}
        supported = []
        for axis in CANON_AXES:
            refs = _strings(support.get(axis, []), path + '.support.' + axis, errors)
            if not refs:
                needs.append(path + '.support.' + axis + ' needs declared representative-scene references.')
            else:
                supported.append(axis)
            for rid in refs:
                if rid not in local_refs:
                    errors.append(path + '.support.' + axis + ' references an unknown local source: ' + rid)
        result['coverage']['profiles'].append({
            'fighter_id': fid, 'reference_ids': sorted(local_refs),
            'axes_with_declared_support': supported,
            'source_content_verified': False,
        })
    for fid in sorted(fighter_ids - seen_fighters):
        needs.append('Provide a canon_profiles entry for fighter ' + fid + '.')

    interactions = request.get('system_interactions', [])
    if not isinstance(interactions, list):
        errors.append('system_interactions must be a list')
        interactions = []
    interaction_ids = set()
    for index, interaction in enumerate(interactions):
        path = f'system_interactions[{index}]'
        if not isinstance(interaction, dict):
            errors.append(path + ' must be an object')
            continue
        iid = interaction.get('id')
        if not _text(iid) or iid in interaction_ids:
            errors.append(path + '.id must be unique and nonempty')
            continue
        interaction_ids.add(iid)
        participants = _strings(interaction.get('participants', []), path + '.participants', errors)
        if len(set(participants)) < 2:
            needs.append(path + '.participants needs at least two different fighters.')
        if any(fid not in fighter_ids for fid in participants):
            errors.append(path + '.participants references an unknown fighter')
        for field in INTERACTION_FIELDS:
            if not _description(interaction.get(field)):
                needs.append(path + '.' + field + ' needs an explicit mechanism and resulting action/state.')
        basis = interaction.get('basis')
        if basis not in INTERACTION_BASES:
            errors.append(path + '.basis must be canon, creative_bridge or author_override')
        source_refs = _strings(interaction.get('source_refs', []), path + '.source_refs', errors)
        setup_refs = _strings(interaction.get('setup_refs', []), path + '.setup_refs', errors)
        if basis == 'canon' and not source_refs:
            needs.append(path + '.source_refs needs the claimed original-work interaction references.')
        if basis in ('creative_bridge', 'author_override') and not setup_refs:
            needs.append(path + '.setup_refs needs explicit existing-mechanism or author-setting pointers.')
        for rid in source_refs:
            if rid not in reference_ids:
                errors.append(path + '.source_refs references an unknown source: ' + rid)

    bindings = {iid: [] for iid in interaction_ids}
    reviewing = request.get('operation', 'prepare') == 'review'
    if reviewing:
        draft = request.get('draft', {})
        beats = draft.get('beats', []) if isinstance(draft, dict) else []
        if not isinstance(beats, list):
            errors.append('draft.beats must be a list for fidelity review')
            beats = []
        for index, beat in enumerate(beats):
            if not isinstance(beat, dict):
                continue  # The main writing checker reports invalid beats.
            path = f'draft.beats[{index}]'
            bid = beat.get('id')
            tags = _strings(beat.get('system_interactions', []), path + '.system_interactions', errors)
            known_beat = _text(bid) and bid in beat_ids
            if tags and not known_beat:
                errors.append(path + '.id must name a known beat for interaction binding')
            for iid in tags:
                if iid not in interaction_ids:
                    errors.append(path + '.system_interactions references an unknown interaction: ' + iid)
                elif known_beat:
                    bindings[iid].append(bid)
        for iid in sorted(interaction_ids):
            if not bindings[iid]:
                revision.append('Planned system interaction has no explicit beat declaration: ' + iid)
    result['coverage']['system_interactions'] = [
        {'id': iid, 'declared_beats': bindings[iid],
         'beat_declared': bool(bindings[iid]), 'prose_implementation_verified': False}
        for iid in sorted(interaction_ids)
    ]
    result['host_tasks'] = [
        'Read the cited representative scenes; verify version, context, speaker and actual behavior. A populated source id does not establish that a source was read or accurately understood.',
        'Confirm complete internal nine-dimensional scaling for each matching fighter configuration before using style samples. Reuse accepted dossiers and supplement gaps; use novel-refpack when a novel character lacks one. Targeted excerpts, nonempty ratings and approved prose examples cannot substitute for this work. Keep evidence and quantitative reasoning in the internal dossier, separate from the finished story.',
        'Verify that the requested participants actually contest the core matchup and that their abilities and actions determine an outcome at the claimed scope. Narrative form should follow characters, settings and author requirements without a prescribed plot type. Other narrative achievements must not substitute for the confrontation or expand its actual result. Preserve explicit author constraints and faction relations; do not invent counterplay to make one-sided combat reciprocal. This is a host semantic review, not a result certified by populated fields.',
        'Use concrete speech, focalization, ability activation, probing, escalation and aftermath choices from each profile. Preserve state-dependent motives; do not reduce character fidelity to trait labels or force either mercy or execution.',
        'Review dialogue as a natural exchange with character-specific phrasing, responsiveness, emotion and appropriate fullness, not just names, catchphrases or uniformly terse declarations. When no author length cap exists, allow the space needed for reactions, causality and aftermath; do not suppress essential context for implied brevity. Preserve genuinely taciturn characters and avoid making everyone verbose, repeating information, or inventing resistance and combat rounds to extend the story.',
        'Review tone across the actual events, not just dialogue: humor, evidenced meta awareness, media interactions and cartoon behavior can shape actions and consequences. Separate established knowledge from omniscience and manipulation authority; do not erase valid character knowledge or invent plot control and gag invincibility. Preserve both voices, clear conflict and an explicit realized outcome before the closing afterbeat.',
        'Keep each power system recognizable. Define contact, activation, contestation and consequences before drafting cross-system exchanges; do not silently equalize energies or turn a creative bridge into a new ability or universal resistance.',
        'Resolve control coverage and applicable resistance before choosing reactions. Enforce the resulting knowledge and agency; intelligence or personality is not meta-awareness or resistance. Fully immersed characters act only within their imposed roles. Do not require effective counterplay, reciprocal injury or an escape where no such capacity remains.',
        'Check every interaction against the prose and action/state continuity. Declared beat coverage does not establish that a mechanism was depicted, counterplay occurred, or a tactic was valid.',
        'Review the ending for remaining powers, recovery routes, upstream threats and continued control as the character would. If key precautions or canon examples are missing, retrieve or mark them explicitly rather than inventing facts.',
        'Use transferable high-level narrative features and original wording; do not reproduce distinctive source passages. Keep research qualifications and audit tags in the planning layer, separate from the finished story.',
    ]
    return result
