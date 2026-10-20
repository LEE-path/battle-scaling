"""PK presentation and explicitly subjective macro estimates; no statistical model."""
from __future__ import annotations
import copy
import math

PRESENTATIONS=('overview','process')
READABLE={'verified','provided','indexed','read','verified_via_host_browser'}


def select_presentation(matchup=None, override=None):
    if matchup is not None and not isinstance(matchup,dict):
        raise ValueError('matchup must be an object')
    selected=override if override is not None else (matchup or {}).get('presentation','overview')
    if selected not in PRESENTATIONS:
        raise ValueError('PK presentation must be overview or process; evidence mode is separate')
    return selected


def _number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def validate_estimate(estimate):
    errors=[]
    if not isinstance(estimate,dict):return ['win_estimate must be an object']
    if estimate.get('method')!='reasoned_estimate':
        errors.append('win_estimate method must be reasoned_estimate; no empirical accuracy is claimed')
    if estimate.get('empirically_calibrated') is True or estimate.get('calibrated') is True:
        errors.append('reasoned estimates cannot be marked empirically calibrated')
    if not isinstance(estimate.get('basis'),str) or not estimate['basis'].strip():
        errors.append('win_estimate requires an explanation of its basis')
    ids=estimate.get('evidence_ids')
    if not isinstance(ids,list) or not ids or any(not isinstance(item,str) or not item for item in ids):
        errors.append('win_estimate requires nonempty evidence_ids')
    assumptions=estimate.get('assumptions',[])
    if not isinstance(assumptions,list) or any(not isinstance(item,str) or not item.strip() for item in assumptions):
        errors.append('win_estimate assumptions must be a list of explicit statements')
    outcomes=estimate.get('outcomes')
    if not isinstance(outcomes,list) or len(outcomes)<2:
        errors.append('win_estimate requires at least two mutually exclusive outcome categories')
        return errors
    seen=set();valid=True
    for item in outcomes:
        if not isinstance(item,dict):
            errors.append('outcome must be an object');valid=False;continue
        name=item.get('outcome')
        if not isinstance(name,str) or not name or name in seen:
            errors.append('outcome names must be unique nonempty strings')
        else:seen.add(name)
        values=[item.get(key) for key in ('min','best','max')]
        if not all(_number(value) for value in values) or not 0<=values[0]<=values[1]<=values[2]<=1:
            errors.append('outcome requires finite 0 <= min <= best <= max <= 1');valid=False
    if valid:
        if not math.isclose(sum(item['best'] for item in outcomes),1,rel_tol=0,abs_tol=1e-8):
            errors.append('central outcome estimates must sum to one')
        if sum(item['min'] for item in outcomes)>1+1e-8 or sum(item['max'] for item in outcomes)<1-1e-8:
            errors.append('outcome intervals must admit a distribution summing to one')
    return errors


def review_estimate(estimate,sources):
    errors=validate_estimate(estimate)
    if errors:return {'status':'invalid','errors':errors,'outcomes':[],'empirically_calibrated':False}
    source_map=sources if isinstance(sources,dict) else {item['id']:item for item in sources}
    unavailable=[sid for sid in estimate['evidence_ids'] if sid not in source_map or source_map[sid].get('access') not in READABLE]
    metadata_primary=all(source_map.get(sid,{}).get('access')=='verified' and source_map.get(sid,{}).get('origin')=='primary' for sid in estimate['evidence_ids'])
    result=copy.deepcopy(estimate)
    result.update(status='undetermined' if unavailable else 'reasoned_estimate',empirically_calibrated=False,
                  source_access_checked=True,unusable_evidence_ids=unavailable,
                  original_source_verified=False,input_declares_primary_verified=metadata_primary,
                  validation_scope='Checks ranges, outcome consistency and source-access metadata; does not establish entailment or a measured win frequency')
    if unavailable:result['outcomes']=[]
    return result


def format_estimate(estimate):
    if not estimate or estimate.get('status') not in ('reasoned_estimate','conditional'):
        return '胜率暂不能合理量化；按获胜路径、关键条件和反例给出倾向。'
    parts=[]
    for item in estimate['outcomes']:
        parts.append(f"{item['outcome']}：约{item['best']:.0%}（合理区间{item['min']:.0%}～{item['max']:.0%}）")
    prefix='条件分支胜率：' if estimate.get('status')=='conditional' else ''
    return prefix+'；'.join(parts)+'。性质：基于列明证据与前提的推算，非实测胜率。'
