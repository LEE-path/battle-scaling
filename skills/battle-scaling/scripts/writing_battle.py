"""Organize author settings and check the structure of an authored battle draft.

This is a writing assistant contract, not a prose generator or combat verifier.
The host Agent reads the complete setting pack, reasons about its meaning and
writes the story. This module checks explicit references and constraint coverage.
Only purpose='writing' opts into the contract; it cannot be used as feat evidence.
"""
from __future__ import annotations
from rating_modes import metadata as mode_metadata

import copy

from writing_fidelity import review_fidelity
from rating_preflight import review as review_ratings
from rating_pipeline import verify_execution


RATING_FIELDS = ('输出', '体防', '智力', '战斗智商', '经验', '特殊技能', '破坏', '速度', '体量')
SKILL_FIELDS = ('name', 'effect', 'activation', 'cost', 'range', 'limits')
SPECIAL_ENDINGS = {'draw', 'mutual_defeat', 'open'}
WRITING_POLICY = {
    'scope': 'purpose=writing only; independent ratings and ordinary PK retain their existing gates',
    'evidence_priority': ['qualified_matching_dossiers', 'canon_text', 'official_scripts', 'reliable_material'],
    'mandatory_media_steps': [],
    'interaction_reasoning': 'Research decisive gaps and trace attribute-matched inferences to evidence; missing direct crossover footage alone is neither a new setting nor a reason to ask the author.',
    'research_stop': 'Stop expanding research after current valid independent ratings complete the mode-specific selection and candidate review, with no unresolved material candidate, and decisive interactions are sufficiently grounded. A numeric local floor alone does not satisfy this condition; then direct the main effort to the complete story.',
    'author_questions': 'Only irreducible outcome-changing conflicts after targeted research and inference justify one minimal question at a time.',
}
VALIDATION_SCOPE = (
    'Checks the supplied writing schema, actor/skill/entity/event references, '
    'explicit required-skill actions, required-event declarations and their '
    'requested order across independent beats, and exact '
    'author-ending fields. It does not verify prose entailment, setting semantics, '
    'power consistency, tactical feasibility, emotional quality or an actual winner. '
    'Host conflict resolutions and event-fulfillment tags remain host declarations; '
    'ordered tags cannot establish the actual prose event order or causal validity. '
    'Optional canon profiles and system-interaction beat links are checked only '
    'for structural completeness, never for source accuracy, completion of the '
    'internal nine-dimensional scaling dossier, or faithful writing.'
)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _present(value):
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return isinstance(value, (int, float))


def _strings(value, path, errors):
    if not isinstance(value, list) or any(not _text(item) for item in value):
        errors.append(path + ' must be a list of nonempty strings')
        return []
    return value


def _host_tasks(unresolved, response):
    tasks = [
        'Read every fighter persona, current state, nine-dimensional rating, skill mechanism, activation, cost, range and limit before outlining.',
        'Before plotting prose, follow the same independent single-character rating workflow for each selected version, state and equipment, completing or reusing an actually reviewed full nine-dimensional dossier. Establish one specific main tier and evidence-backed concrete conservative floor tiers for applicable output, durability and destruction; keep unknown ceilings separate. Review the configuration, credible materially higher feats and transfer chains, and explain the mode-specific selection before treating any local floor as representative. Record sourced completion_review findings and candidate dispositions, bind host acceptance to its exact revision, and freshly read the current dossier status before reuse; a withdrawn or superseded acceptance cannot be revived by an old ready receipt. Reuse qualified matching dossiers first, then prioritize canon text, official scripts and reliable material with source locations, calculations or scaling arguments, relevant counterfeats and uncertainties retained internally. Only this story route has no mandatory image viewing, video downloading, frame extraction or visual verification. Do not automatically start new media analysis to fill gaps; use fresh visual analysis only when the user explicitly requests analysis of supplied or new media, without expanding that request into a full visual review of the story. Accepted image-derived dossier conclusions can be reused. Missing ratings still require research before plotting, never a default truce or draw. Quantify where evidence permits; never invent numbers for intelligence, experience or unknown parameters. Nonempty ratings and ready_for_host do not establish that this work is complete.',
        'When a key fact is missing, identify which conclusion depends on it and actively seek other sources, related feats or defensible bounds before treating it as an author conflict; use references/evidence-gap-recovery.md to recover the evidence chain. For weapon damage, check established material without inventing a named alloy, actual destruction feats, the target\'s prior injuries and resistances, and the injuring agent\'s material, edge, energy, output, contact area and condition. Match the relevant attributes and trace cross-inferences through sourced premises, limits and alternatives; material names alone do not rank cutting or durability, and an unconfirmed material remains unknown while demonstrated feats can still bound the interaction. A grounded inference without a direct crossover scene is not an added setting. Ask only after targeted research and inference leave an irreducible conflict that changes the outcome.',
        'Track intent, knowledge, resources, injuries, location, cooldowns and available actions across the full battle. Reveal pivotal tactics through action; provide a concise separate design summary only if the author asks.',
        'Once the full ratings and decisive interactions are sufficiently grounded, stop expanding research. Put the main effort into character choices, natural dialogue, tension, pacing, spectacular readable action, a clear battle result and character-consistent aftermath. Show action, activation, contact or evasion, response and resulting state changes through the scene; do not turn the story into a terminology manual or audit report. Do not invent a decisive environmental advantage to manufacture a tactical solution.',
        'Unless the author sets a length limit, let characterization, dialogue, reactions and necessary causality determine the space needed, including a substantially longer story. Do not compress speech into uniformly clipped or cryptic one-liners to appear concise. Let each character respond naturally and express what the situation warrants while preserving their established degree of talkativeness. Make essential motives and consequences understandable within the prose. Avoid padding, explanatory lectures, invented counterplay or extra combat rounds merely to fill length; concise design summaries do not impose a prose length cap.',
        'Deliver the requested actual matchup through the named participants and their available actions, abilities and consequences. Let characters, settings and author requirements determine narrative form without prescribing plot types or a fixed structure. Other narrative achievements must not replace the core confrontation or its victory conditions. Match the declared outcome to its actual scope, preserve faction relations and explicit author constraints, and ground the resolution in the realized fight. One-sided control or ineffective resistance can be decisive combat; never manufacture reciprocal damage or resistance.',
        'Treat explicit author settings as the creative authority. Reuse qualified matching canon dossiers, supplement changes, and prioritize the novel-refpack pipeline for novel characters lacking a complete accepted dossier. Targeted voice and combat samples supplement rather than replace full internal scaling. Original or author-fixed adapted rules need the same coherent nine-dimensional assessment without fabricated canon sources; overrides replace only what the author changed. Never silently add abilities, weaknesses, allies or breakthroughs.',
        'Let characterization shape the whole narrative rhythm, choices, setbacks, event causality and aftermath, not merely inserted quips. Preserve evidenced fourth-wall awareness, media knowledge, presentation interactions and cartoon effects within their demonstrated scope; distinguish awareness, actual information access and manipulation power. Do not suppress legitimate meta knowledge under the narrator-knowledge rule or grant omniscience, plot control or gag invincibility. Preserve the other fighter persona. Make the reason for fighting and the decisive outcome clear before the closing joke or afterbeat.',
        'Preserve the distinct combat grammar of each power system. Define contact, information, activation, applicable resistance and consequences before plotting responses. Enforce established or author-fixed coverage and resulting cognitive freedom; a response may be wholly ineffective or confined to an imposed role. Do not force reciprocal counterplay or damage.',
        'Distinguish noticing an anomaly, understanding its mechanism, locating its controller, resisting and escaping. Intelligence, personality, narrator knowledge or mental equipment does not grant these capacities. Complete role immersion preserves only compatible in-role agency; never invent out-of-story awareness or resistance to prolong a fight. Author-fixed interactions remain story premises, not canon tier evidence or a universal AP rule.',
        'Check choices and postbattle threat handling against concrete character behavior. Do not force mercy, execution, escalation or restraint from a generic personality label.',
        'Keep counterexamples, qualification language, probability estimates and audit checklists out of the finished prose; retain setting limits and uncertainty in the planning/audit layer.',
        'Review the prose against the structured outline: a name mentioned in narration or a fulfillment tag alone does not prove that a skill was used or a tactic worked.',
        'Do not promote this invented battle, its fixed ending or its author ratings into original-work evidence or a battle-scaling conclusion.',
    ]
    if unresolved and response == 'keep_settings':
        tasks.append('The author elected to retain all settings. Continue searching for established tactical, environmental, objective, withdrawal or psychological routes; do not invent a new capability or decisive environmental advantage, change a fixed victory condition, or claim an unresolved hard conflict is solved.')
    elif unresolved:
        tasks.append('Only after targeted research and evidence-chain inference fail to resolve an outcome-changing conflict, ask the author the smallest concrete question, one conflict at a time. The author supplies any additions; the Agent must not add them automatically.')
    return tasks


def run(request):
    """Prepare or structurally review an explicitly authored writing request.

    Required: purpose='writing'; fighters with unique id/name, persona/state,
    ratings keyed by RATING_FIELDS, and skills keyed by id plus SKILL_FIELDS.
    Empty/absent setting details become needs instead of invented defaults.
    Optional scene.entities=[{id,...}] supplies nonfighter action targets.

    constraints: required_skills=[{fighter_id,skill_id}], required_events=
    [{id,description}], optional required_event_order=[event_id,...],
    ending={winner,result,method?}, forbidden_changes=[str]. Event-order ids must
    be unique defined events. Review requires each ordered event to have exactly
    one beat declaration and those beat indices to be strictly increasing; the
    same beat cannot demonstrate an order between two events. This checks host
    declarations only, never the semantic order of the prose.
    ending.winner is a fighter id or draw/mutual_defeat/open. There is no default
    advantage-winner restriction. draft.outcome repeats any fixed ending fields.

    review additionally accepts draft.text and draft.beats=[{id,actions:
    [{actor,target,skill_id?}],fulfills:[event_id]}]. Skill use is counted only in
    an explicit action, never through a prose substring. Event fulfillment is a
    declaration for the host to audit, not a semantic proof.

    host_conflicts=[{id,description,status:unresolved|resolved,resolution?}].
    Declare an unresolved author conflict only after targeted research and
    evidence-chain inference leave an irreducible outcome-changing conflict.
    Missing direct crossover footage alone is not such a conflict.
    author_response is ask_author (default) or keep_settings. A keep_settings
    request continues host planning but cannot mark an unresolved conflict done.
    """
    if not isinstance(request, dict):
        raise ValueError('writing request must be an object')
    request = copy.deepcopy(request)
    if request.get('purpose') != 'writing':
        raise ValueError("writing assistant requires explicit purpose='writing'")
    operation = request.get('operation', 'prepare')
    if operation not in ('prepare', 'review'):
        raise ValueError('writing operation must be prepare or review')
    standard = request.get('standard', 'wangba')
    if standard not in ('wangba', 'vsb'):
        raise ValueError('writing standard must be wangba or vsb')
    response = request.get('author_response', 'ask_author')
    if response not in ('ask_author', 'keep_settings'):
        raise ValueError('author_response must be ask_author or keep_settings')

    errors, needs, revision = [], [], []
    fighters = request.get('fighters', [])
    if not isinstance(fighters, list):
        errors.append('fighters must be a list')
        fighters = []
    if len(fighters) < 2:
        needs.append('Provide at least two fighters.')
    actors, skills = {}, {}
    for index, fighter in enumerate(fighters):
        path = f'fighters[{index}]'
        if not isinstance(fighter, dict):
            errors.append(path + ' must be an object')
            continue
        fid = fighter.get('id')
        if not _text(fid) or fid in actors or fid in SPECIAL_ENDINGS:
            errors.append(path + '.id must be unique, nonempty and not a reserved ending')
            continue
        actors[fid] = fighter
        skills[fid] = set()
        for field in ('name', 'persona', 'state'):
            if not _present(fighter.get(field)):
                needs.append(path + '.' + field + ' is missing; ask the author or leave the gap explicit.')
        ratings = fighter.get('ratings', {})
        if not isinstance(ratings, dict):
            errors.append(path + '.ratings must be an object')
            ratings = {}
        for field in RATING_FIELDS:
            if not _present(ratings.get(field)):
                needs.append(path + '.ratings.' + field + ' is missing.')
        abilities = fighter.get('skills', [])
        if not isinstance(abilities, list):
            errors.append(path + '.skills must be a list')
            abilities = []
        if 'skills' not in fighter:
            needs.append(path + '.skills is missing; an explicit empty list means no special skills.')
        for si, skill in enumerate(abilities):
            spath = f'{path}.skills[{si}]'
            if not isinstance(skill, dict):
                errors.append(spath + ' must be an object')
                continue
            sid = skill.get('id')
            if not _text(sid) or sid in skills[fid]:
                errors.append(spath + '.id must be unique within its fighter and nonempty')
                continue
            skills[fid].add(sid)
            for field in SKILL_FIELDS:
                if not _present(skill.get(field)):
                    needs.append(spath + '.' + field + ' is missing; do not invent it.')

    scene = request.get('scene', {})
    if not isinstance(scene, dict):
        errors.append('scene must be an object')
        scene = {}
    entities = scene.get('entities', [])
    if not isinstance(entities, list):
        errors.append('scene.entities must be a list')
        entities = []
    entity_ids = set()
    for index, entity in enumerate(entities):
        eid = entity.get('id') if isinstance(entity, dict) else None
        if not _text(eid) or eid in entity_ids or eid in actors:
            errors.append(f'scene.entities[{index}].id must be unique and distinct from fighter ids')
        else:
            entity_ids.add(eid)

    constraints = request.get('constraints', {})
    if not isinstance(constraints, dict):
        errors.append('constraints must be an object')
        constraints = {}
    forbidden = _strings(constraints.get('forbidden_changes', []), 'constraints.forbidden_changes', errors)
    required_skills = constraints.get('required_skills', [])
    if not isinstance(required_skills, list):
        errors.append('constraints.required_skills must be a list')
        required_skills = []
    required_skill_pairs = set()
    for index, item in enumerate(required_skills):
        if not isinstance(item, dict):
            errors.append(f'constraints.required_skills[{index}] must be an object')
            continue
        fid, sid = item.get('fighter_id'), item.get('skill_id')
        if not _text(fid) or not _text(sid) or fid not in actors or sid not in skills.get(fid, set()):
            errors.append(f'constraints.required_skills[{index}] references an unknown fighter or skill')
        else:
            required_skill_pairs.add((fid, sid))
    required_events = constraints.get('required_events', [])
    if not isinstance(required_events, list):
        errors.append('constraints.required_events must be a list')
        required_events = []
    event_ids = set()
    for index, item in enumerate(required_events):
        if not isinstance(item, dict) or not _text(item.get('id')) or not _text(item.get('description')):
            errors.append(f'constraints.required_events[{index}] needs nonempty id and description')
        elif item['id'] in event_ids:
            errors.append('required event ids must be unique')
        else:
            event_ids.add(item['id'])
    event_order = _strings(constraints.get('required_event_order', []), 'constraints.required_event_order', errors)
    if len(set(event_order)) != len(event_order):
        errors.append('constraints.required_event_order must not repeat an event id')
    if any(eid not in event_ids for eid in event_order):
        errors.append('constraints.required_event_order references an undefined required event')
    ending = constraints.get('ending')
    if ending is not None:
        if not isinstance(ending, dict):
            errors.append('constraints.ending must be an object')
            ending = None
        else:
            if not _text(ending.get('winner')) or ending['winner'] not in set(actors) | SPECIAL_ENDINGS:
                errors.append('constraints.ending.winner must name a fighter or draw/mutual_defeat/open')
            if not _text(ending.get('result')):
                needs.append('constraints.ending.result needs an explicit desired battle result.')
            if 'method' in ending and not _text(ending['method']):
                errors.append('constraints.ending.method must be a nonempty string when supplied')

    conflicts = request.get('host_conflicts', [])
    if not isinstance(conflicts, list):
        errors.append('host_conflicts must be a list')
        conflicts = []
    conflict_ids, unresolved = set(), []
    for index, conflict in enumerate(conflicts):
        if not isinstance(conflict, dict):
            errors.append(f'host_conflicts[{index}] must be an object')
            continue
        cid = conflict.get('id')
        if not _text(cid) or cid in conflict_ids or not _text(conflict.get('description')):
            errors.append('host conflicts need unique nonempty ids and descriptions')
            continue
        conflict_ids.add(cid)
        if conflict.get('status') not in ('unresolved', 'resolved'):
            errors.append('host conflict status must be unresolved or resolved')
        elif conflict['status'] == 'unresolved':
            unresolved.append(cid)
        elif not _text(conflict.get('resolution')):
            errors.append('a declared resolved conflict needs an explicit resolution for host review')

    used, fulfilled, beats_seen = set(), set(), set()
    event_positions = {eid: [] for eid in event_ids}
    order_issues = []
    if operation == 'review':
        draft = request.get('draft')
        if not isinstance(draft, dict):
            revision.append('Provide draft.text, draft.beats and draft.outcome for review.')
            draft = {}
        if not _text(draft.get('text')):
            revision.append('The complete draft text is missing.')
        beats = draft.get('beats', [])
        if not isinstance(beats, list):
            errors.append('draft.beats must be a list')
            beats = []
        if not beats:
            revision.append('Provide explicit action beats; prose mentions do not establish skill use.')
        for index, beat in enumerate(beats):
            if not isinstance(beat, dict):
                errors.append(f'draft.beats[{index}] must be an object')
                continue
            bid = beat.get('id')
            if not _text(bid) or bid in beats_seen:
                errors.append('draft beat ids must be unique nonempty strings')
            else:
                beats_seen.add(bid)
            actions = beat.get('actions', [])
            if not isinstance(actions, list) or not actions:
                errors.append(f'draft.beats[{index}].actions must be a nonempty list')
                actions = []
            for ai, action in enumerate(actions):
                apath = f'draft.beats[{index}].actions[{ai}]'
                if not isinstance(action, dict):
                    errors.append(apath + ' must be an object')
                    continue
                actor, target, skill = action.get('actor'), action.get('target'), action.get('skill_id')
                actor_known = _text(actor) and actor in actors
                target_known = _text(target) and target in set(actors) | entity_ids
                if not actor_known:
                    errors.append(apath + '.actor references an unknown fighter')
                if not target_known:
                    errors.append(apath + '.target references an unknown fighter or scene entity')
                if skill is not None:
                    if not actor_known or not _text(skill) or skill not in skills[actor]:
                        errors.append(apath + '.skill_id does not belong to its actor')
                    elif target_known:
                        used.add((actor, skill))
            tags = _strings(beat.get('fulfills', []), f'draft.beats[{index}].fulfills', errors)
            for tag in set(tags):
                if tag not in event_ids:
                    errors.append('draft fulfillment references unknown required event: ' + tag)
                else:
                    fulfilled.add(tag)
                    event_positions[tag].append(index)
        for fid, sid in sorted(required_skill_pairs - used):
            revision.append(f'Required skill {fid}/{sid} has no explicit action.')
        for eid in sorted(event_ids - fulfilled):
            revision.append('Required event has no explicit beat declaration: ' + eid)
        for eid in event_order:
            positions = event_positions.get(eid, [])
            if not positions:
                order_issues.append('Ordered required event has no explicit beat declaration: ' + eid)
            elif len(positions) != 1:
                order_issues.append('Ordered required event must identify one unambiguous beat: ' + eid)
        for previous, current in zip(event_order, event_order[1:]):
            left, right = event_positions.get(previous, []), event_positions.get(current, [])
            if len(left) == len(right) == 1 and left[0] >= right[0]:
                order_issues.append('Required event declaration order must use strictly later independent beats: '
                                    + previous + ' before ' + current)
        revision.extend(order_issues)
        outcome = draft.get('outcome')
        if not isinstance(outcome, dict):
            revision.append('Provide draft.outcome with winner and result.')
        else:
            if not _text(outcome.get('winner')) or outcome['winner'] not in set(actors) | SPECIAL_ENDINGS:
                errors.append('draft.outcome.winner references an unknown fighter or ending')
            if not _text(outcome.get('result')):
                revision.append('draft.outcome.result is missing.')
            if ending:
                for field in ('winner', 'result', 'method'):
                    if field in ending and outcome.get(field) != ending[field]:
                        revision.append('draft.outcome.' + field + ' does not match the fixed author ending.')

    fidelity = review_fidelity(request, set(actors), beats_seen)
    errors.extend(fidelity['errors'])
    needs.extend(fidelity['needs'])
    revision.extend(fidelity['revision_tasks'])

    rating_gate = review_ratings(fighters, request.get('independent_ratings', []),
                                request.get('sources', []), standard=standard,
                                mode=request.get('mode', 'integrated'), writing=True,
                                **({'rating_status':request['rating_status']} if 'rating_status' in request else {}))
    execution_gate = verify_execution(request)
    if execution_gate['status'] != 'ready':
        rating_gate['status'] = 'needs_research'
        rating_gate['accepted_subject_ids'] = []
        rating_gate['needs'] = list(dict.fromkeys(rating_gate['needs'] + execution_gate['needs']))
        rating_gate['research_tasks'].append('Execute the isolated single-character tasks and import the real report, CASE, source and replayable analysis files with battle.py rating-pipeline assemble before outlining the story.')
    rating_gate['dossier_contents_read_by_checker'] = execution_gate['dossier_contents_read_by_checker']

    if errors:
        status = 'invalid'
    elif needs:
        status = 'needs_input'
    elif rating_gate['status'] != 'ready':
        status = 'needs_independent_rating'
    elif unresolved and response != 'keep_settings':
        status = 'awaiting_author_settings'
    elif unresolved:
        status = 'unresolved_under_original_settings' if operation == 'review' else 'continue_with_original_settings'
    elif operation == 'review':
        status = 'needs_revision' if revision else 'structure_checked'
    else:
        status = 'ready_for_host'
    result = {
        'purpose': 'writing', 'operation': operation, 'standard': standard, 'status': status,
        'mode': request.get('mode', 'integrated'), **mode_metadata(request.get('mode', 'integrated')),
        'errors': errors, 'needs': needs, 'revision_tasks': revision,
        'author_pack': {key: copy.deepcopy(request[key]) for key in
                        ('fighters', 'scene', 'constraints', 'canon_fidelity', 'canon_profiles',
                         'system_interactions', 'style_plan', 'independent_ratings', 'rating_execution', 'rating_status', 'sources') if key in request},
        'rating_preflight': rating_gate,
        'rating_execution': execution_gate,
        'writing_policy': copy.deepcopy(WRITING_POLICY),
        'fixed_ending': copy.deepcopy(ending),
        'winner_selection': 'author_fixed' if ending else 'host_selects_plausible_story_outcome',
        'forbidden_changes': forbidden,
        'host_conflicts': copy.deepcopy(conflicts),
        'unresolved_conflict_ids': unresolved, 'author_response': response,
        'conflict_resolution_semantics_verified': False,
        'host_tasks': _host_tasks(unresolved, response) + fidelity['host_tasks'],
        'canon_fidelity': fidelity,
        'coverage': {
            'required_skills': [{'fighter_id': fid, 'skill_id': sid, 'action_declared': (fid, sid) in used}
                                for fid, sid in sorted(required_skill_pairs)],
            'required_events': [{'id': eid, 'beat_declared': eid in fulfilled} for eid in sorted(event_ids)],
            'required_event_order': {
                'requested': event_order,
                'declared_beat_indices': {eid: event_positions.get(eid, []) for eid in event_order},
                'declaration_order_checked': operation == 'review',
                'declared_order_matches': not order_issues if operation == 'review' else None,
                'prose_order_verified': False,
            },
            'semantic_fulfillment_verified': False,
        },
        'narrative_generated': False, 'battle_evidence': False, 'canon_evidence': False,
        'tactical_feasibility_verified': False, 'host_semantic_review_required': True,
        'validation_scope': VALIDATION_SCOPE,
    }
    if unresolved and response != 'keep_settings':
        first = next(item for item in conflicts if isinstance(item, dict) and item.get('id') == unresolved[0])
        result['author_question'] = ('关于“' + first['description'] + '”，你是否愿意自行补充设定？'
                                     '请提供你认可的新增内容；也可以要求保留现有设定继续寻找其他合理战果路径。')
    return result
