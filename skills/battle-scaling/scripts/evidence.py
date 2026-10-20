"""Scoped evidence selection and auditable constraint propagation (stdlib only)."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from decimal import Decimal,localcontext
from collections import defaultdict, deque
from pathlib import Path
from pk_modes import READABLE, select_presentation, validate_estimate, review_estimate
from hax_gate import build_checks as build_hax_checks, review as review_hax, ids as hax_ids, RANK as HAX_RANK

MODES = ('normal', 'highest', 'lowball')
REVIEW_USES = {'observed_output','material_model','full_effort','state_transfer','upper_bound'}
KINDS = {'repeated_feat', 'credible_feat', 'calculation', 'statement', 'outlier', 'anti_feat'}
REQUIREMENTS = {
    'tanked': ('actual_scale', 'effective_hit', 'body_only'),
    'damaged': ('effective_hit', 'non_hax', 'comparable_mechanism'),
    'defeated': ('direct_power', 'matched_state'),
    'strongest': ('corroborated', 'scope_compatible', 'attribute_coverage'),
    'same_tier': ('corroborated', 'scope_compatible', 'attribute_coverage'),
    'failure': ('maximal_attempt', 'opportunity', 'matched_state'),
    'explicit': ('explicit_relation',),
}
BLOCKED = {'blocked', 'unread', 'unknown', 'error'}
ENERGY_UNITS = {'J': 1, 'kJ': 1e3, 'MJ': 1e6, 'GJ': 1e9, 'kg_TNT': 4.184e6, 't_TNT': 4.184e9}
ENERGY_UNITS.update({'kt_TNT':4.184e12,'Mt_TNT':4.184e15,'Gt_TNT':4.184e18,
                     'kt TNT':4.184e12,'Mt TNT':4.184e15,'Gt TNT':4.184e18})


def _finite(x):
    return isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)


def normalize_quantity(q):
    if not isinstance(q, dict):
        raise ValueError('quantity must be an object')
    if q.get('kind') == 'tier':
        if not q.get('ruleset') or not q.get('label') or not _finite(q.get('rank')):
            raise ValueError('tier quantities require ruleset, label and a finite within-ruleset rank')
        return {**q, 'best': q['rank'], 'min': q['rank'], 'max': q['rank'], 'unit': 'tier:' + q['ruleset']}
    value = q.get('best', q.get('value'))
    low, high = q.get('min', value), q.get('max', value)
    if any(isinstance(v,str) for v in (low,value,high)):
        def numeric(v):
            if isinstance(v,str):
                if len(v)>1000:raise ValueError('decimal quantity string is excessive')
                return float(v)
            return v
        low,value,high=map(numeric,(low,value,high))
    if not all(_finite(v) and v >= 0 for v in (low, value, high)) or not low <= value <= high:
        raise ValueError('quantity needs finite nonnegative min <= best/value <= max')
    if not isinstance(q.get('unit'), str) or not q['unit']:
        raise ValueError('quantity requires a unit')
    unit = q['unit']
    factor = ENERGY_UNITS.get(unit, 1)
    result = {**q, 'min': low * factor, 'best': value * factor, 'max': high * factor,
              'unit': 'J' if unit in ENERGY_UNITS else unit}
    if not all(_finite(result[k]) for k in ('min', 'best', 'max')):
        raise ValueError('quantity overflow; use the typed high-tier tool for symbolic sizes')
    result.pop('value', None)
    return result


def validate_case(case):
    errors = []
    if not isinstance(case, dict):
        return ['case must be a JSON object']
    if case.get('schema_version') != 1:
        errors.append('schema_version must be 1')
    if not case.get('case_id'):
        errors.append('case_id is required')
    groups = {}
    for field in ('characters', 'sources', 'anchors', 'edges'):
        value = case.get(field, [])
        if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
            errors.append(field + ' must be a list of objects')
            groups[field] = []
        else:
            groups[field] = value
        ids = [x.get('id') for x in groups[field]]
        if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
            errors.append(field + ' needs unique nonempty string IDs')
    chars = {x.get('id') for x in groups['characters']}
    sources = {x.get('id') for x in groups['sources']}
    for c in groups['characters']:
        for key in ('name', 'version', 'state'):
            if not c.get(key):
                errors.append(f'character {c.get("id")}: {key} is required')
    for s in groups['sources']:
        if not s.get('title') or not s.get('locator') or not s.get('origin') or not s.get('access'):
            errors.append(f'source {s.get("id")}: title, locator, origin, access are required')
    def refs(obj, field='evidence_ids'):
        values = obj.get(field, [])
        if not isinstance(values, list) or not values or any(x not in sources for x in values):
            errors.append(f'{obj.get("id", "claim")}: {field} must cite existing sources')
    for a in groups['anchors']:
        if a.get('subject') not in chars or not a.get('attribute'):
            errors.append(f'anchor {a.get("id")}: unknown subject or missing attribute')
        if a.get('kind') not in KINDS:
            errors.append(f'anchor {a.get("id")}: invalid kind')
        if 'modes' in a and (not isinstance(a['modes'], list) or any(m not in MODES for m in a['modes'])):
            errors.append(f'anchor {a.get("id")}: invalid modes')
        if a.get('bound', 'estimate') not in ('lower', 'upper', 'estimate'):
            errors.append(f'anchor {a.get("id")}: invalid bound')
        if 'claim_scope' in a and a['claim_scope'] not in ('event','capacity'):
            errors.append('anchor claim_scope must be event or capacity')
        try:
            normalize_quantity(a.get('quantity'))
        except (ValueError, TypeError) as exc:
            errors.append(f'anchor {a.get("id")}: {exc}')
        refs(a)
    for e in groups['edges']:
        for end in ('from', 'to'):
            point = e.get(end, {})
            if not isinstance(point, dict) or point.get('subject') not in chars or not point.get('attribute'):
                errors.append(f'edge {e.get("id")}: invalid {end}')
        if e.get('relation') not in REQUIREMENTS:
            errors.append(f'edge {e.get("id")}: unsupported relation; use a separate high-tier construct for containment')
        if not isinstance(e.get('conditions', {}), dict):
            errors.append(f'edge {e.get("id")}: conditions must be an object')
        if 'modes' in e and (not isinstance(e['modes'], list) or any(m not in MODES for m in e['modes'])):
            errors.append(f'edge {e.get("id")}: invalid modes')
        mult = e.get('multiplier', 1)
        if not _finite(mult) or mult <= 0:
            errors.append(f'edge {e.get("id")}: multiplier must be finite and positive')
        if mult != 1:
            refs(e, 'multiplier_evidence_ids')
        refs(e)
    reviews=case.get('feat_reviews',[])
    if not isinstance(reviews,list) or any(not isinstance(x,dict) for x in reviews):
        errors.append('feat_reviews must be a list of objects');reviews=[]
    review_ids=[x.get('id') for x in reviews]
    if any(not isinstance(x,str) or not x for x in review_ids) or len(review_ids)!=len(set(review_ids)):
        errors.append('feat_reviews need unique nonempty IDs')
    review_map={x['id']:x for x in reviews if isinstance(x.get('id'),str)}
    for review in reviews:
        request=review.get('request')
        if not isinstance(request,dict):
            errors.append('feat review requires a request object');continue
        event=request.get('event',{})
        if not isinstance(event,dict) or event.get('actor_id') not in chars:
            errors.append(f'feat review {review.get("id")}: event actor_id must reference a character')
        if 'modes' in review and (not isinstance(review['modes'],list) or not review['modes'] or any(m not in MODES for m in review['modes'])):
            errors.append('feat review modes must select valid evidence modes')
        uses=request.get('requested_uses',['observed_output'])
        if not isinstance(uses,list) or not uses or any(x not in REVIEW_USES for x in uses):
            errors.append('feat review requested_uses must name supported purposes')
    qualitative=case.get('qualitative_claims',[])
    if not isinstance(qualitative,list):
        errors.append('qualitative_claims must be a list');qualitative=[]
    for claim in qualitative:
        if isinstance(claim,dict) and 'evidence_ids' in claim:refs(claim)
    for item in groups['anchors']+groups['edges']+[x for x in qualitative if isinstance(x,dict)]:
        requirements=item.get('review_requirements',[])
        if not isinstance(requirements,list) or any(not isinstance(x,dict) for x in requirements):
            errors.append('review_requirements must be a list of objects');continue
        for requirement in requirements:
            rid,use=requirement.get('review_id'),requirement.get('use')
            review=review_map.get(rid)
            if not review or use not in REVIEW_USES:
                errors.append('review_requirements need an existing review_id and supported use');continue
            request=review.get('request',{})
            if not isinstance(request,dict):continue
            if use not in request.get('requested_uses',['observed_output']):
                errors.append('review requirement use must be requested by its review')
            event=request.get('event',{})
            actor=event.get('actor_id')
            subjects=[item['subject']] if 'subject' in item else [item[x].get('subject') for x in ('from','to') if isinstance(item.get(x),dict)]
            if subjects and actor not in subjects:
                errors.append('review actor must match the anchor/claim subject or an edge endpoint')
            if requirement.get('allow_unproven') and not requirement.get('assumptions'):
                errors.append('allow_unproven requires explicit assumptions')
            assumptions=requirement.get('assumptions',[])
            if not isinstance(assumptions,list) or any(not isinstance(x,str) or not x.strip() for x in assumptions):
                errors.append('review requirement assumptions must be nonempty statement strings')
    if case.get('feat_review_results') is not None:
        errors.append('feat_review_results is reserved for computed output; submit feat_reviews requests')
    checks=case.get('hax_checks',[])
    if not isinstance(checks,list) or any(not isinstance(x,dict) for x in checks):
        errors.append('hax_checks must be a list of check requests');checks=[]
    check_ids=[x.get('id') for x in checks]
    if any(not isinstance(x,str) or not x for x in check_ids) or len(check_ids)!=len(set(check_ids)):
        errors.append('hax_checks need unique nonempty IDs')
    check_ids={x for x in check_ids if isinstance(x,str)}
    for check in checks:
        request=check.get('request')
        if not isinstance(request,dict):errors.append('hax check needs a request object');continue
        for field in ('actor_id','target_id'):
            if not isinstance(request.get(field),str) or request[field] not in chars:
                errors.append('hax '+field+' must reference a CASE character')
        if 'modes' in check and (not isinstance(check['modes'],list) or not check['modes'] or any(m not in MODES for m in check['modes'])):
            errors.append('hax check modes must select valid modes')
    if 'hax_results' in case or 'hax_reviews' in case:errors.append('Computed hax results cannot be supplied; use hax_checks requests')
    def hax_refs(node):
        if not isinstance(node,dict):return
        try:references=hax_ids(node.get('hax_requirements',[]))
        except ValueError as exc:errors.append(str(exc));return
        if any(x not in check_ids for x in references):errors.append('hax_requirements must cite existing hax_checks')
        if 'is_hax' in node and type(node['is_hax']) is not bool:errors.append('is_hax must be true or false')
        for key in ('ability_owner','affected_target'):
            if key in node and node[key] not in chars:errors.append(key+' must reference a CASE character')
    for node in groups['anchors']+groups['edges']+[x for x in qualitative if isinstance(x,dict)]:hax_refs(node)
    for computation in case.get('computations',[]):
        hax_refs(computation)
        if isinstance(computation,dict):hax_refs(computation.get('attach',{}))
    matchup=case.get('matchup', {})
    try:
        select_presentation(matchup)
    except ValueError as exc:
        errors.append(str(exc))
    if not isinstance(matchup,dict):
        return errors
    if any(field in matchup for field in ('process','win_estimate','probability','assessment','verdict')):
        errors.append('matchup reserved result fields cannot be supplied; use mode_assessments or mode_processes')
    processes=matchup.get('mode_processes',{})
    if not isinstance(processes,dict):
        errors.append('matchup mode_processes must be an object')
        processes={}
    for m, process in processes.items():
        if m not in MODES or not isinstance(process,dict):
            errors.append('matchup mode_processes require valid modes and object values')
        elif 'hax_checks' in process:
            errors.append('CASE process hax_checks must be centralized at CASE.hax_checks, not overridden inside a mode')
        if isinstance(process,dict):
            def walk(value):
                if isinstance(value,dict):
                    hax_refs(value)
                    for key,child in value.items():
                        if key not in ('sources','hax_checks'):walk(child)
                elif isinstance(value,list):
                    for child in value:walk(child)
            walk(process)
    for path in matchup.get('win_paths', []):
        refs(path)
        hax_refs(path)
        if path.get('probability') is not None:
            errors.append('uncalibrated matchup probabilities are unsupported')
        for req in path.get('requirements', []):
            refs(req)
            hax_refs(req)
        if 'modes' in path and (not isinstance(path['modes'], list) or any(m not in MODES for m in path['modes'])):
            errors.append(f'win path {path.get("id")}: invalid modes')
    for m, assessment in case.get('matchup', {}).get('mode_assessments', {}).items():
        if m not in MODES or not isinstance(assessment, dict):
            errors.append('matchup mode_assessments require valid modes and object values')
            continue
        refs(assessment)
        hax_refs(assessment)
        if assessment.get('probability') is not None:
            errors.append('uncalibrated matchup probabilities are unsupported')
        if assessment.get('status') not in ('reasoned_estimate', 'conditional', 'undetermined') or not assessment.get('reasoning'):
            errors.append(f'matchup {m}: assessment needs reasoning and an explicit estimate/conditional/undetermined status')
        if 'win_estimate' in assessment:
            hax_refs(assessment['win_estimate'])
            errors.extend(f'matchup {m}: {error}' for error in validate_estimate(assessment['win_estimate']))
            if isinstance(assessment['win_estimate'],dict):
                refs(assessment['win_estimate'])
    return errors


def classify_energy(quantity, ruleset_path=None, tier_context=None):
    numeric={k:(float(v) if k in ('value','min','best','max') and isinstance(v,str) else v) for k,v in quantity.items()}
    q = normalize_quantity(numeric)
    if q['unit'] != 'J':
        return None
    if ruleset_path:
        path=Path(ruleset_path)
    else:
        from rule_profiles import resolve,finite_path
        path=finite_path(resolve())
    if not path.exists():
        return {'status': 'no_ruleset', 'energy_j': q}
    rules = json.loads(path.read_text(encoding='utf-8'))
    if rules.get('engine')=='handbook_finite':
        from handbook_finite import classify
        context=tier_context or {}
        if 'context' not in context:context={'context':context}
        assessment=classify({'quantity':quantity,**context},ruleset=rules)
        # Keep the old display keys for downstream readers while exposing the
        # complete multidimensional determination and source clauses separately.
        reference=assessment.get('display_label') or assessment.get('label') or assessment.get('final_tier')
        if isinstance(reference,dict):reference=reference.get('label',reference.get('name'))
        return {'ruleset_id':rules['id'],'status':'handbook_multidimensional_mapping',
                'best_reference':reference or '新册条件待核／见逐条评定',
                'qualifier':'以该册已校勘条款同时检查能量、作用尺度与释放条件；无细分数值时不补造切点',
                'handbook_assessment':assessment,'rule_source':rules.get('source')}
    tiers = sorted(rules['references'], key=lambda x: x['energy_j'])
    def label(value):
        hits = [t for t in tiers if value >= t['energy_j']]
        return hits[-1]['name'] if hits else '低于本表最低参考点'
    return {'ruleset_id': rules['id'], 'status': 'reference_mapping',
            'min_reference': label(q['min']), 'best_reference': label(q['best']), 'max_reference': label(q['max']),
            'qualifier': '达到的粗略能量参考点；不是破坏几何或全部战斗属性的证明',
            'table_ceiling_exceeded': q['best'] > tiers[-1]['energy_j'], 'source_url': rules['source_url']}


def _usable(ids, sources):
    return bool(ids) and all(i in sources and sources[i].get('access') in READABLE for i in ids)


def _hax_combined(nodes,checks,owner=None,target=None):
    out={'status':'not_declared','check_ids':[],'reasons':[],'assumptions':[],'source_ids':[]}
    for node in nodes:
        result=review_hax(node,checks,owner=node.get('ability_owner',owner),target=node.get('affected_target',target))
        if HAX_RANK[result['status']]>HAX_RANK[out['status']]:out['status']=result['status']
        for key in ('check_ids','reasons','assumptions','source_ids'):
            out[key]=list(dict.fromkeys(out[key]+result[key]))
    return out


def _macro_hax(nodes,checks,owner,target):
    result=_hax_combined(nodes,checks,owner,target)
    if result['status']!='not_declared' and result['status']!='blocked' and owner is None and not all(
            node.get('ability_owner') for node in nodes if node.get('is_hax') or node.get('hax_requirements')):
        result['status']='undetermined'
        result['reasons'].append('A team/outcome label does not identify the actual special-ability owner; declare ability_owner.')
    return result


def _hax_scoped_case(case,checks,mode):
    scoped=copy.deepcopy(case);excluded=[];coverage={'checked_ids':[],'unreviewed_ids':[],
        'scope':'Only explicitly marked/dependent entries reviewed; undeclared abilities are not certified.'}
    for field in ('anchors','edges','qualitative_claims','computations'):
        accepted=[]
        for item in case.get(field,[]):
            if not isinstance(item,dict) or mode not in item.get('modes',MODES):accepted.append(item);continue
            if field=='computations' and item.get('mode',mode)!=mode:continue
            result=_hax_combined([item,item.get('attach',{})],checks,
                    owner=item.get('ability_owner',item.get('subject',item.get('attach',{}).get('subject'))))
            key=item.get('id',field+'-claim')
            coverage['unreviewed_ids' if result['status']=='not_declared' else 'checked_ids'].append(key)
            if result['status'] in ('blocked','undetermined'):
                excluded.append({'id':key,'field':field,'reason':'hax_'+result['status'],'hax_review':result});continue
            item=copy.deepcopy(item)
            if result['status']!='not_declared':
                item.setdefault('hax_trace',[]).append(result)
                item['evidence_ids']=list(dict.fromkeys(item.get('evidence_ids',[])+result['source_ids']))
                if result['status']=='conditional':
                    item['assumptions']=list(dict.fromkeys(item.get('assumptions',[])+result['assumptions']))
                    item['hax_status']='conditional'
            accepted.append(item)
        scoped[field]=accepted
    return scoped,excluded,coverage


def _review_case(case,mode):
    """Apply explicit event-review dependencies without inventing physical values."""
    scoped=copy.deepcopy(case)
    outputs={};requests={};excluded=[]
    for review in case.get('feat_reviews',[]):
        if mode not in review.get('modes',MODES):continue
        from feat_audit import run
        request={**copy.deepcopy(review['request']),'sources':copy.deepcopy(case['sources']),'mode':mode}
        output=run(request)
        if output.get('status') in ('invalid','error'):raise ValueError('feat review '+review['id']+': '+str(output))
        output={**output,'effective_request_sha256':hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()}
        outputs[review['id']]=output;requests[review['id']]=request
    chars={x['id']:x for x in case['characters']}
    source_ids={x['id'] for x in case['sources']}
    coverage={'reviewed_anchor_ids':[],'unreviewed_anchor_ids':[],
              'scope':'Only declared review dependencies checked; no semantic source authentication'}
    for field in ('anchors','edges','qualitative_claims'):
        accepted=[]
        for original in case.get(field,[]):
            if not isinstance(original,dict):accepted.append(original);continue
            item=copy.deepcopy(original)
            if mode not in item.get('modes',MODES):accepted.append(item);continue
            requirements=item.get('review_requirements',[])
            if field=='anchors':coverage['reviewed_anchor_ids' if requirements else 'unreviewed_anchor_ids'].append(item['id'])
            failure=None
            if field=='anchors' and requirements and item.get('bound')=='upper' and item.get('claim_scope')!='event' and not any(x['use']=='upper_bound' for x in requirements):
                excluded.append({'id':item['id'],'field':field,'reason':'feat_review_missing_upper_bound',
                    'detail':'A state-capacity upper bound requires upper_bound review; event measurement bounds must be scoped as event.'})
                continue
            for requirement in requirements:
                rid,use=requirement['review_id'],requirement['use']
                if rid not in outputs:
                    failure={'reason':'feat_review_unavailable_in_mode','review_id':rid,'use':use};break
                event=requests[rid].get('event',{})
                actor=chars.get(event.get('actor_id'),{})
                if use=='state_transfer':
                    target=requests[rid].get('state_transfer',{})
                    default_target=item.get('subject',item.get('to',{}).get('subject',event.get('actor_id')))
                    target_id=target.get('target_actor_id',default_target)
                    endpoints=[item.get(x,{}).get('subject') for x in ('from','to')] if field=='edges' else [item.get('subject',event.get('actor_id'))]
                    target_actor=chars.get(target_id,{})
                    if target_id not in endpoints or not target_actor or target.get('target_state')!=target_actor.get('state') or (
                        event.get('version')!=target_actor.get('version') and target.get('target_version')!=target_actor.get('version')):
                        failure={'reason':'feat_review_scope_mismatch','review_id':rid,
                                 'detail':'state_transfer must name the actual target state and, when changed, version'};break
                mismatch=any(event.get(k)!=actor.get(k) for k in ('version','state'))
                if mismatch and not any(x.get('review_id')==rid and x.get('use')=='state_transfer' for x in requirements):
                    failure={'reason':'feat_review_scope_mismatch','review_id':rid,
                             'detail':'Different event version/state needs an explicit state_transfer admission'};break
                admission=outputs[rid].get('admissions',{}).get(use)
                if not isinstance(admission,dict):
                    failure={'reason':'feat_review_missing_admission','review_id':rid,'use':use};break
                status=admission.get('status')
                if status=='blocked':
                    failure={'reason':'feat_review_blocked','review_id':rid,'use':use,'details':admission.get('reasons',[])};break
                if status not in ('supported_by_packet','conditional','undetermined'):
                    raise ValueError('Unsupported feat admission status: '+str(status))
                if status=='undetermined' and not requirement.get('allow_unproven'):
                    failure={'reason':'feat_review_undetermined','review_id':rid,'use':use};break
                refs=admission.get('source_ids',[])
                if not isinstance(refs,list) or any(s not in source_ids for s in refs):raise ValueError('Review admission cites unknown sources')
                if refs and not _usable(refs,{s['id']:s for s in case['sources']}):
                    failure={'reason':'feat_review_blocked','review_id':rid,'use':use,'details':['unreadable admission source']};break
                trace={'review_id':rid,'use':use,'status':status,'source_ids':refs}
                item.setdefault('review_trace',[]).append(trace)
                if refs:item['evidence_ids']=list(dict.fromkeys(item.get('evidence_ids',[])+refs))
                if status!='supported_by_packet':
                    premises=admission.get('assumptions',[])+requirement.get('assumptions',[])
                    if not premises:premises=[f'{rid}/{use}: conditional on '+str(admission.get('reasons',[]))]
                    item['assumptions']=list(dict.fromkeys(item.get('assumptions',[])+premises))
                    item['review_status']='conditional'
            if failure:excluded.append({'id':item.get('id','qualitative-claim'),'field':field,**failure})
            else:accepted.append(item)
        scoped[field]=accepted
    return scoped,outputs,excluded,coverage


def _mode_analysis(case, mode,profile=None):
    sources = {s['id']: s for s in case['sources']}
    excluded, grouped = [], defaultdict(list)
    for a in case.get('anchors', []):
        if mode not in a.get('modes', MODES):
            continue
        key = (a['subject'], a['attribute'], normalize_quantity(a['quantity'])['unit'], a.get('bound', 'estimate'))
        grouped[key].append(a)
    selected = []
    for anchors in grouped.values():
        valid = [a for a in anchors if _usable(a['evidence_ids'], sources)]
        for a in anchors:
            if a not in valid:
                excluded.append({'id': a['id'], 'reason': 'unavailable_evidence'})
        if mode == 'normal':
            repeated = [a for a in valid if a['kind'] == 'repeated_feat' or
                        (a['kind'] == 'calculation' and a.get('corroborated'))]
            pool = repeated or [a for a in valid if a['kind'] in ('credible_feat', 'calculation')]
            if not pool:
                pool = [a for a in valid if a['kind'] == 'statement' and a.get('corroborated')]
        elif mode == 'lowball':
            pool = [a for a in valid if a['kind'] == 'anti_feat'] or [a for a in valid if a['kind'] != 'statement']
        else:
            pool = valid
        for a in valid:
            if a not in pool:
                excluded.append({'id': a['id'], 'reason': 'mode_evidence_filter'})
        selected.extend(pool)
    edges = defaultdict(list)
    for e in case.get('edges', []):
        edges[(e['from']['subject'], e['from']['attribute'])].append(e)
    queue, best = deque(), {}
    for a in selected:
        queue.append({'subject': a['subject'], 'attribute': a['attribute'], 'quantity': normalize_quantity(a['quantity']),
                      'mapping_quantity':copy.deepcopy(a['quantity']),
                      'bound': a.get('bound', 'estimate'), 'anchor_id': a['id'], 'anchor_kind': a['kind'],
                      **({'claim_scope':a['claim_scope']} if 'claim_scope' in a else {}),
                      'trace': [a['id']], 'evidence_ids': list(a['evidence_ids']),
                      'assumptions': list(a.get('assumptions', [])), 'context': a.get('context', ''),
                      'review_trace':copy.deepcopy(a.get('review_trace',[])),
                      'hax_trace':copy.deepcopy(a.get('hax_trace',[])),
                      'tier_context':a.get('tier_context',case.get('tier_context',{})),
                      'visited': [(a['subject'], a['attribute'])]})
    processed, cap = 0, int(case.get('limits', {}).get('max_derivations', 5000))
    if not 1 <= cap <= 50000:
        raise ValueError('max_derivations must be between 1 and 50000')
    depth = int(case.get('limits', {}).get('max_depth', 24))
    if not 1 <= depth <= 128:
        raise ValueError('max_depth must be between 1 and 128')
    while queue and processed < cap:
        item = queue.popleft()
        processed += 1
        key = (item['subject'], item['attribute'], item['quantity']['unit'], item['bound'])
        old = best.get(key)
        better = old is None or (item['quantity']['best'] < old['quantity']['best'] if mode == 'lowball'
                                else item['quantity']['best'] > old['quantity']['best'])
        if better:
            best[key] = item
        elif old and item['quantity']['best'] == old['quantity']['best'] and len(item['trace']) < len(old['trace']):
            best[key] = item
        if len(item['trace']) >= depth:
            excluded.append({'id': item['trace'][-1], 'reason': 'depth_limit'})
            continue
        for e in edges[(item['subject'], item['attribute'])]:
            if mode not in e.get('modes', MODES):
                continue
            if not _usable(e['evidence_ids']+e.get('multiplier_evidence_ids', []), sources):
                excluded.append({'id': e['id'], 'reason': 'unavailable_evidence'})
                continue
            target = (e['to']['subject'], e['to']['attribute'])
            if target in item['visited']:
                excluded.append({'id': e['id'], 'reason': 'cycle'})
                continue
            if item['bound'] == 'upper' and e.get('bound_transfer') != 'upper':
                excluded.append({'id': e['id'], 'reason': 'upper_bound_not_a_lower_bound'})
                continue
            contradicted = [r for r in REQUIREMENTS[e['relation']] if e.get('conditions', {}).get(r) is False]
            if contradicted:
                excluded.append({'id': e['id'], 'reason': 'observed_counterfact', 'conditions': contradicted})
                continue
            missing = [r for r in REQUIREMENTS[e['relation']] if e.get('conditions', {}).get(r) is not True]
            if missing and mode == 'normal':
                excluded.append({'id': e['id'], 'reason': 'unproven_transfer_conditions', 'missing': missing})
                continue
            assumptions = item['assumptions'] + list(e.get('assumptions', []))
            assumptions += [f'{e["id"]}: assume {r}' for r in missing]
            if e['relation'] in ('strongest', 'same_tier') and mode == 'lowball' and not e.get('reverse_lowball'):
                continue
            new = copy.deepcopy(item)
            new.update(subject=target[0], attribute=target[1], assumptions=list(dict.fromkeys(assumptions)))
            if e.get('tier_context') is not None:new['tier_context']=e['tier_context']
            factor = e.get('multiplier', 1)
            if new['quantity'].get('kind') == 'tier' and factor != 1:
                excluded.append({'id': e['id'], 'reason': 'cannot_multiply_tier_rank'})
                continue
            for k in ('min', 'best', 'max'):
                new['quantity'][k] *= factor
            if new.get('mapping_quantity',{}).get('kind')!='tier':
                for k in ('value','min','best','max'):
                    if k in new.get('mapping_quantity',{}):
                        with localcontext() as arithmetic:
                            arithmetic.prec=2048
                            new['mapping_quantity'][k]=str(Decimal(str(new['mapping_quantity'][k]))*Decimal(str(factor)))
            if any(not _finite(new['quantity'][k]) for k in ('min', 'best', 'max')):
                excluded.append({'id': e['id'], 'reason': 'numeric_overflow'})
                continue
            new['trace'] += [e['id']]
            new['review_trace']+=copy.deepcopy(e.get('review_trace',[]))
            new['hax_trace']+=copy.deepcopy(e.get('hax_trace',[]))
            new['visited'] += [target]
            new['evidence_ids'] = list(dict.fromkeys(new['evidence_ids'] + e['evidence_ids'] + e.get('multiplier_evidence_ids', [])))
            new['context'] = '; '.join(x for x in (item['context'], e.get('context', '')) if x)
            queue.append(new)
    conclusions = []
    for item in best.values():
        c = {k: v for k, v in item.items() if k != 'visited'}
        from rule_profiles import finite_path
        # Reconstructible decimal inputs are preserved for threshold decisions;
        # the legacy constraint graph uses finite floats for path selection.
        mapping_q=c.get('mapping_quantity',c['quantity'])
        c['mapping'] = classify_energy(mapping_q,finite_path(profile) if profile else None,c.get('tier_context'))
        c['status'] = 'conditional' if c['assumptions'] else 'supported_by_packet'
        conclusions.append(c)
    unique_excluded = list({json.dumps(x, sort_keys=True): x for x in excluded}.values())
    return {'conclusions': conclusions, 'excluded': unique_excluded, 'processed_derivations': processed,
            'search_truncated': bool(queue), 'selection': {'normal': 'highest_of_repeated_credible_showings',
             'highest': 'maximum_with_explicit_aggressive_premises', 'lowball': 'lowest_observed_or_reverse_scaled_context'}[mode]}


def analyze_matchup(matchup, sources, mode='normal',hax_reviews=None,hax_requests=None,actor_ids=None):
    hax_reviews=hax_reviews or {}
    paths = []
    def scope(node):
        winner=node.get('winner')
        owner=node.get('ability_owner',winner if actor_ids is None or winner in actor_ids else None)
        target=node.get('affected_target')
        if target is None and actor_ids and len(actor_ids)==2 and owner in actor_ids:
            target=next(actor for actor in actor_ids if actor!=owner)
        return owner,target
    for p in matchup.get('win_paths', []):
        if mode not in p.get('modes', MODES):
            continue
        reqs = p.get('requirements', [])
        evidence_ok = _usable(p.get('evidence_ids', []), sources)
        req_ok = bool(reqs) and all(r.get('status') == 'supported' and
                    _usable(r.get('evidence_ids', []), sources) for r in reqs)
        status = 'supported' if evidence_ok and req_ok and not p.get('unresolved_counters') else 'conditional'
        if p.get('status') == 'blocked' or any(r.get('status') == 'blocked' for r in reqs):
            status = 'blocked'
        owner,target=scope(p)
        hax=_macro_hax([p,*reqs],hax_reviews,owner,target)
        if hax['status']=='blocked':status='blocked'
        elif hax['status'] in ('conditional','undetermined'):status='conditional'
        paths.append({**p, 'reviewed_status': status,'hax_review':hax})
    winners = {p.get('winner') for p in paths if p['reviewed_status'] == 'supported' and p.get('winner')}
    verdict = next(iter(winners)) if len(winners) == 1 else 'contested' if winners else 'insufficient_evidence'
    assessment = matchup.get('mode_assessments', {}).get(mode)
    if assessment:
        assessment = {**assessment, 'source_access_checked': _usable(assessment.get('evidence_ids', []), sources),
                      'validation_scope': 'source IDs and access checked; host mechanism inference is not statistically calibrated'}
        if not assessment['source_access_checked']:
            assessment.update(status='undetermined', winner=None)
        owner,target=scope(assessment)
        hax=_macro_hax([assessment,assessment.get('win_estimate',{})],hax_reviews,owner,target)
        assessment['hax_review']=hax
        if hax['status'] in ('blocked','undetermined'):assessment.update(status='undetermined',winner=None)
        elif hax['status']=='conditional':
            assessment['status']='conditional'
            assessment['critical_assumptions']=list(dict.fromkeys(assessment.get('critical_assumptions',[])+hax['assumptions']))
        if 'win_estimate' in assessment:
            assessment['win_estimate']=review_estimate(assessment['win_estimate'],sources)
            if assessment['status']=='conditional' and assessment['win_estimate'].get('status')=='reasoned_estimate':
                assessment['win_estimate']['status']='conditional'
                assessment['win_estimate']['assumptions']=list(dict.fromkeys(
                    assessment['win_estimate'].get('assumptions',[])+assessment.get('critical_assumptions',[])))
            if hax['status']!='not_declared':assessment['win_estimate']['hax_review']=copy.deepcopy(hax)
            if not assessment['source_access_checked'] or assessment['status']=='undetermined':
                assessment['win_estimate'].update(status='undetermined',outcomes=[])
    presentation=select_presentation(matchup)
    display_fields=('teams','conditions','description','victory_conditions','compatibility',
                    'critical_assumptions','unresolved_counters')
    reviewed={k:copy.deepcopy(v) for k,v in matchup.items() if k in display_fields}
    reviewed.update(mode=mode,assessment=assessment,win_paths=paths,verdict=verdict,presentation=presentation,
                    method='host-authored causal assessment; subjective ranges are not measured win frequencies',
                    hax_review_coverage={'checked_win_path_ids':[p.get('id') for p in paths if p['hax_review']['status']!='not_declared'],
                        'unreviewed_win_path_ids':[p.get('id') for p in paths if p['hax_review']['status']=='not_declared'],
                        'assessment_status':assessment.get('hax_review',{}).get('status') if assessment else None,
                        'scope':'Undeclared routes are not certified as reviewed hax or classified automatically.'})
    if presentation=='process':
        request=matchup.get('mode_processes',{}).get(mode)
        if request is None:
            reviewed['process']={'status':'needs_process_input','trace':[],
                'needs':['Host must build a sourced causal process for this evidence mode; no story is generated from a winner label.']}
        else:
            from combat_trace import run
            reviewed['process']=run({**copy.deepcopy(request),'sources':list(sources.values()),'mode':mode,
                                    'hax_checks':copy.deepcopy(hax_requests or [])})
    return reviewed


def analyze_case(case, mode='normal',profile=None):
    if mode not in MODES + ('all',):
        raise ValueError('mode must be normal, highest, lowball or all')
    errors = validate_case(case)
    if errors:
        raise ValueError('Invalid case:\n' + '\n'.join(errors))
    if profile is None:
        from rule_profiles import resolve
        profile=resolve(case.get('ruleset_profile'))
    result = {'schema_version': 1, 'case_id': case['case_id'], 'fixture_kind': case.get('fixture_kind', 'research'),
              'characters': case['characters'], 'sources': case['sources'], 'modes': {},
              'computations': [c for c in case.get('computations',[]) if not (
                  c.get('is_hax') or c.get('hax_requirements') or c.get('attach',{}).get('is_hax') or c.get('attach',{}).get('hax_requirements'))],
              'qualitative_claims': [c for c in case.get('qualitative_claims',[]) if not isinstance(c,dict) or not (
                  c.get('review_requirements') or c.get('is_hax') or c.get('hax_requirements'))],
              'coverage': case.get('coverage', {}), 'limitations': case.get('limitations', []),
              'validation_scope': 'schema, provenance references and explicit rules; source entailment requires host review'}
    result['ruleset_profile']=profile
    for field in ('derivation_audits','research_results','run_metadata'):
        if field in case:result[field]=copy.deepcopy(case[field])
    for m in MODES if mode == 'all' else (mode,):
        hax=build_hax_checks(case.get('hax_checks',[]),case['sources'],m)
        scoped,reviews,excluded,coverage=_review_case(case,m)
        scoped,hax_excluded,hax_coverage=_hax_scoped_case(scoped,hax,m)
        result['modes'][m] = _mode_analysis(scoped, m,profile)
        result['modes'][m]['excluded']+=excluded+hax_excluded
        result['modes'][m]['hax_reviews']=hax
        result['modes'][m]['hax_review_coverage']=hax_coverage
        result['modes'][m]['feat_reviews']=reviews
        result['modes'][m]['feat_review_coverage']=coverage
        result['modes'][m]['hax_computations'] = [c for c in scoped.get('computations',[]) if c.get('hax_trace')]
        result['modes'][m]['high_results'] = [c for c in scoped.get('computations', [])
            if c.get('type') == 'high' and c.get('mode', c.get('request', {}).get('mode', 'normal')) == m]
        result['modes'][m]['qualitative_claims'] = [c for c in scoped.get('qualitative_claims', [])
            if not isinstance(c, dict) or m in c.get('modes', MODES)]
    if case.get('matchup'):
        result['process_input_sha256']={m:hashlib.sha256(json.dumps(
            {k:v for k,v in request.items() if k not in ('sources','mode')},sort_keys=True,ensure_ascii=False,
            allow_nan=False).encode()).hexdigest() for m,request in case['matchup'].get('mode_processes',{}).items()
            if m in result['modes']}
        result['matchups'] = {m: analyze_matchup(case['matchup'], {s['id']: s for s in case['sources']}, m,
                                              result['modes'][m]['hax_reviews'],case.get('hax_checks',[]),
                                              {character['id'] for character in case['characters']})
                              for m in result['modes']}
        result['matchup'] = result['matchups']['normal' if mode == 'all' else mode]
    return result
