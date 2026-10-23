"""Keep rating standards separate from evidence modes and PK presentation."""
from __future__ import annotations

import copy
import math

STANDARDS = ('wangba', 'vsb')
ALIASES = {'wangba':'wangba', '汪吧':'wangba', 'vsb':'vsb', 'vs battles wiki':'vsb'}


def normalize(value):
    if not isinstance(value, str) or value.strip().lower() not in ALIASES:
        raise ValueError('standard must be wangba or vsb; evidence --mode is separate')
    return ALIASES[value.strip().lower()]


def family(profile):
    return normalize(profile.get('standard', 'wangba'))


def policy_id(standard):
    return 'vsb_hax_mechanism_20261021' if normalize(standard)=='vsb' else 'user_confirmed_hax_ceiling_20261020'


VSB_RULESETS = {'vsb-current-2026-10-21', 'vsb-high-current-2026-10-21'}


def vsb_tier_quantity(classification, ruleset='vsb-high-current-2026-10-21'):
    """Canonical ordinal for within-standard constraints, never a tier multiplier."""
    import json
    from pathlib import Path
    from vsb_high import RULES
    table=json.loads((Path(__file__).resolve().parents[1]/'rulesets/vsb-current-2026-10-21.json').read_text(encoding='utf-8'))
    codes=['11-C','11-B','11-A']+[row['tier'] for row in table['attack_potency']['finite_tiers']]
    codes += [code for code in RULES if code not in codes]
    tier=classification.get('tier')
    if ruleset not in VSB_RULESETS or tier not in codes:
        raise ValueError('VSB tier must use a registered ruleset and official supported tier code')
    return {'kind':'tier','ruleset':ruleset,'tier':tier,'rank':codes.index(tier),
            'label':tier+' ('+classification.get('label',tier)+')'}


SBA = {
    'rule_source': {'url':'https://vsbattles.fandom.com/wiki/Standard_Battle_Assumptions', 'revision_id':9377396},
    'version_policy':'User-specified version takes precedence; otherwise strongest listed canon tier, most recent on ties.',
    'arena':'Central Park, New York City; combatants may leave during combat.',
    'starting_distance_rule':'Higher combatant range, capped at 4000 m; melee-only higher range uses its reach plus three steps of the shorter stride.',
    'preparation':'none',
    'equipment':'standard equipment of the selected version',
    'mindset':'in character, attempting to win, not voluntarily conceding or becoming friends',
    'knowledge':'initial direction and identifying appearance only; no prior ability analysis or harmful observation effects',
    'time':'conditions favor the selected combatants at their strongest; discuss gross environmental imbalance',
    'outside_influence':'none except effects actually constituting the selected character powers/equipment',
    'verse_equalization':'similar compatible supernatural systems only; preserve actual abilities, resistances and consistent limitations',
    'speed_equalized':False,
    'victory':{'bfr_min_seconds':604800,'knockout_min_seconds':3600,'incapacitation_over_seconds':86400,
        'death':'immediate only when post-death condition would eventually satisfy one prior condition',
        'priority':'first to satisfy a victory condition'},
}


def validate_case_standard(case, profile):
    """Reject foreign tier scalars, not raw shared measurements or research notes."""
    selected = family(profile)
    for anchor in case.get('anchors', []):
        quantity = anchor.get('quantity', {})
        if quantity.get('kind') != 'tier':
            continue
        named = str(quantity.get('ruleset', '')).lower()
        is_vsb = named in VSB_RULESETS
        if (selected=='vsb') != is_vsb:
            raise ValueError('Tier anchor '+str(anchor.get('id'))+' uses another standard; reassess original evidence instead of renaming tiers')
        if selected=='vsb':
            canonical=vsb_tier_quantity(quantity,named)
            if quantity.get('rank')!=canonical['rank']:
                raise ValueError('VSB tier anchor rank must match its canonical code; ranks are not user-supplied power multipliers')
    for computation in case.get('computations', []):
        if computation.get('type')!='high':
            continue
        named = computation.get('request', {}).get('ruleset')
        if named and ((selected=='vsb') != (str(named).lower() in VSB_RULESETS)):
            raise ValueError('High-tier computation belongs to another standard; provide the selected standard evidence packet')
    if selected=='vsb':
        for entry in case.get('hax_checks', []):
            request=entry.get('request', {})
            if ('world_ceiling' in request or 'observed_limit' in request) and 'effect_evidence' not in request:
                raise ValueError('VSB hax requires mechanism/effect evidence; a Wangba two-ceiling packet cannot be reused as a VSB verdict')
        if case.get('matchup'):
            zeros=set()
            for char in case.get('characters', []):
                if str(char.get('vsb_tier','')).strip()=='0':
                    zeros.add(char['id'])
            for anchor in case.get('anchors', []):
                if anchor.get('quantity',{}).get('tier')=='0' and anchor.get('attribute') in (
                        'attack_energy','attack_potency','AP','ap','durability','body_durability','striking_strength'):
                    zeros.add(anchor.get('subject'))
            if len(zeros)>=2:
                raise ValueError('VSB treats Tier 0 true-form versus Tier 0 combat as inapplicable; compare settings or specify lower-tier avatars')


def prepare_case(case, profile):
    case=copy.deepcopy(case)
    validate_case_standard(case, profile)
    selected=family(profile)
    case['standard']=selected
    audit={'standard':selected, 'hax_policy_id':policy_id(selected), 'excluded_anchor_ids':[]}
    if selected=='vsb':
        retained=[]
        for anchor in case.get('anchors', []):
            if anchor.get('kind')=='outlier':
                audit['excluded_anchor_ids'].append(anchor.get('id'))
            else:
                retained.append(anchor)
        case['anchors']=retained
        audit['outlier_policy']='Known outliers are excluded in every evidence mode; highest does not override VSB admissibility.'
        if case.get('matchup'):
            conditions=case['matchup'].get('conditions', {})
            if not isinstance(conditions, dict):
                raise ValueError('matchup.conditions must be an object')
            # Preserve explicit thread conditions; provide the actual defaults as
            # an auditable rule packet rather than inventing an unknown distance.
            case['matchup']['conditions']={'vsb_sba_defaults':copy.deepcopy(SBA), **conditions}
            case['matchup']['standard']='vsb'
    return case,audit


def victory_review(packet, sources):
    """Validate a host's sourced SBA duration claim, never turn steps into time.

    Schema: {condition:bfr|knockout|incapacitation|death, duration_seconds,
    status:supported|assumed|unknown, evidence_ids|assumptions, post_death?}.
    Death uses an independent post_death packet for its eventual condition.
    """
    READABLE={'verified','provided','read','verified_via_host_browser'}
    if isinstance(sources, list):
        sources={s['id']:s for s in sources}
    result={'status':'undetermined','reasons':[],'assumptions':[]}
    if not isinstance(packet, dict):
        result['reasons']=['Missing sourced VSB victory-condition review; a state label or process step count is insufficient.']
        return result
    condition=packet.get('condition')
    if condition not in ('bfr','knockout','incapacitation','death'):
        result['reasons']=['Specify the SBA victory condition being established.'];return result
    status=packet.get('status')
    refs=packet.get('evidence_ids', [])
    if not isinstance(refs,list) or any(not isinstance(s,str) for s in refs):
        raise ValueError('victory evidence_ids must be a list of source IDs')
    if status=='blocked':
        result.update(status='blocked',reasons=['The proposed victory condition is explicitly blocked.']);return result
    assumptions=packet.get('assumptions', [])
    if not isinstance(assumptions,list) or any(not isinstance(a,str) or not a.strip() for a in assumptions):
        raise ValueError('victory assumptions must be explicit strings')
    if status=='supported':
        if not refs or any(s not in sources or sources[s].get('access') not in READABLE for s in refs):
            result['reasons']=['Victory duration/outcome needs readable cited evidence.'];return result
        result['status']='supported_by_packet'
    elif status=='assumed' and assumptions:
        result.update(status='conditional',assumptions=assumptions)
    else:
        result['reasons']=['Victory condition remains unknown.'];return result
    if condition=='death':
        post=packet.get('post_death')
        if not isinstance(post,dict) or post.get('condition')=='death':
            result.update(status='undetermined',reasons=['Death requires a sourced eventual BFR, knockout or incapacitation condition.']);return result
        follow=victory_review(post,sources)
        if follow['status'] in ('blocked','undetermined'):
            return follow
        if follow['status']=='conditional':
            result['status']='conditional'
        result['assumptions']+=follow['assumptions']
        return result
    duration=packet.get('duration_seconds')
    if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<0:
        result.update(status='undetermined',reasons=['Supply an actual/prospective supported duration in seconds; event steps are not seconds.']);return result
    sufficient={'bfr':duration>=604800,'knockout':duration>=3600,'incapacitation':duration>86400}[condition]
    if not sufficient:
        result.update(status='blocked',reasons=['Duration does not satisfy the selected VSB SBA victory condition.'])
    return result
