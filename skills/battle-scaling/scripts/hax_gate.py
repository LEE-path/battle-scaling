"""Shared dependency gate for sourced special-ability checks, never a tier solver."""
from __future__ import annotations
import copy,hashlib,json

STATUSES={'supported_by_packet','conditional','blocked','undetermined'}
RANK={'not_declared':-1,'supported_by_packet':0,'conditional':1,'undetermined':2,'blocked':3}

def ids(value,name='hax_requirements'):
    if not isinstance(value,list) or any(not isinstance(x,str) or not x for x in value):
        raise ValueError(name+' must be a list of nonempty check IDs')
    return list(dict.fromkeys(value))

def build_checks(entries,sources,mode):
    if mode not in ('normal','highest','lowball'):raise ValueError('invalid hax evidence mode')
    if not isinstance(entries,list) or len(entries)>2048:raise ValueError('hax_checks must be a bounded list')
    outputs={};seen=set()
    for entry in entries:
        if not isinstance(entry,dict) or not isinstance(entry.get('id'),str) or not entry['id'] or entry['id'] in seen:
            raise ValueError('hax checks need unique nonempty IDs')
        seen.add(entry['id'])
        modes=entry.get('modes',['normal','highest','lowball'])
        if not isinstance(modes,list) or not modes or any(m not in ('normal','highest','lowball') for m in modes):
            raise ValueError('hax check modes must select normal/highest/lowball')
        if not isinstance(entry.get('request'),dict):raise ValueError('hax check needs a request object')
        if mode not in modes:continue
        from hax_policy import run
        request={**copy.deepcopy(entry['request']),'sources':copy.deepcopy(sources),'mode':mode}
        output=run(request)
        if output.get('status') not in STATUSES:raise ValueError('invalid hax policy output')
        outputs[entry['id']]={**output,'scope':{key:request.get(key) for key in ('actor_id','target_id','ability_id')},
           'effective_request_sha256':hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()}
    return outputs

def review(item,checks,owner=None,target=None):
    if not isinstance(item,dict):raise ValueError('hax-dependent item must be an object')
    if 'is_hax' in item and type(item['is_hax']) is not bool:raise ValueError('is_hax must be true or false')
    references=ids(item.get('hax_requirements',[]))
    result={'status':'supported_by_packet','reasons':[],'assumptions':[],'source_ids':[],'check_ids':references}
    if not references:
        result.update(status='undetermined' if item.get('is_hax') else 'not_declared',
            reasons=['Declared special ability has no ceiling check.'] if item.get('is_hax') else [])
        return result
    owner=owner if owner is not None else item.get('ability_owner')
    target=target if target is not None else item.get('affected_target')
    for reference in references:
        output=checks.get(reference)
        if output is None:
            current={'status':'undetermined','reasons':['Missing hax check for this evidence mode: '+reference]}
        else:
            current=output
            scope=output.get('scope',{})
            for expected,key in ((owner,'actor_id'),(target,'target_id')):
                if expected is not None and scope.get(key)!=expected:
                    current={**output,'status':'blocked','reasons':list(output.get('reasons',[]))+[
                        reference+': hax check '+key+' does not match its actual user/target.']}
                    break
        if current.get('status') not in STATUSES:raise ValueError('invalid hax dependency status')
        if RANK[current['status']]>RANK[result['status']]:result['status']=current['status']
        for key in ('reasons','assumptions','source_ids'):
            values=current.get(key,[])
            if not isinstance(values,list) or any(not isinstance(x,str) for x in values):raise ValueError('invalid hax '+key)
            result[key]=list(dict.fromkeys(result[key]+values))
    if result['status']=='conditional' and not result['assumptions']:
        result['assumptions']=['Conditional hax mechanism: '+reason for reason in result['reasons']]
    return result
