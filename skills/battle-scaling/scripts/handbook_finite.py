"""Source-qualified finite handbook mapping; exact Decimal comparisons, no source execution.

classify({'quantity': {'value': '1.4', 'unit': 'Mt_TNT'},
          'context': {'fictional': False}}, ruleset=None)

This checker validates numbers and declared context. It does not authenticate
fictional events, certify the cited science, or turn a reference into every AP stat.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

DEFAULT_RULESET = 'wangba-handbook-2026-07-30-finite.json'
UNIT_FACTORS = {
    'J': '1', 'kJ': '1000', 'MJ': '1000000', 'GJ': '1000000000',
    'g': '4184', 'g_TNT': '4184', 'g TNT': '4184',
    'kg': '4184000', 'kg_TNT': '4184000', 'kg TNT': '4184000',
    't': '4184000000', 't_TNT': '4184000000', 't TNT': '4184000000',
    'tonne_TNT': '4184000000', 'kt_TNT': '4184000000000', 'kt TNT': '4184000000000',
    'Mt_TNT': '4184000000000000', 'Mt TNT': '4184000000000000',
}


def _d(value, name='number'):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(name + ' must be a finite nonnegative decimal')
    if len(str(value)) > 256:
        raise ValueError(name + ' decimal is too long')
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(name + ' is not a decimal') from exc
    if not number.is_finite() or number < 0 or abs(number.adjusted()) > 10000:
        raise ValueError(name + ' must be finite, nonnegative and within exponent limits')
    return number


def _s(number):
    return format(number, 'f') if -20 <= number.adjusted() <= 80 else str(number)


def _quantities(q):
    if not isinstance(q, dict):
        raise ValueError('quantity must be an object')
    unit = q.get('unit')
    if unit in {'g','kg','t'} and q.get('equivalent') != 'TNT' and q.get('kind') != 'tnt_equivalent':
        return None
    if unit not in UNIT_FACTORS:
        return None
    value = q.get('best', q.get('value'))
    low, high = q.get('min', value), q.get('max', value)
    numbers = [_d(v, 'quantity') for v in (low, value, high)]
    if not numbers[0] <= numbers[1] <= numbers[2]:
        raise ValueError('quantity needs min <= best/value <= max')
    factor = Decimal(UNIT_FACTORS[unit])
    return [v*factor for v in numbers]


def _public(row):
    if row is None:
        return {'tier_id': None, 'label': '低于本册最低参考点', 'rank': -1}
    return {'tier_id': row['id'], 'label': row['label'], 'rank': row['rank'],
            'clause_id': row['clause_id'], 'source': row['source']}


def _energy(value, references):
    hits = [r for r in references if value >= _d(r['energy_j'])]
    row = hits[-1] if hits else None
    result = _public(row)
    result.update(energy_j=_s(value), mapping_kind='energy_reference',
                  proves_character_property=False)
    if row:
        following = next((r for r in references if _d(r['energy_j']) > value), None)
        result['next_known_reference'] = following['id'] if following else None
        result['table_ceiling_exceeded'] = following is None and value > _d(row['energy_j'])
        result['subtier_cutoffs_unspecified'] = (row['id'].startswith('weak-') and
            value > _d(row['energy_j']) and bool(following) and following['rank'] > row['rank']+1)
    return result


def _classify(request, rules):
    if not isinstance(request, dict) or not isinstance(rules, dict):
        raise ValueError('request and ruleset must be objects')
    if rules.get('engine') != 'handbook_finite':
        raise ValueError('ruleset engine must be handbook_finite')
    context = request.get('context', {})
    if not isinstance(context, dict):
        raise ValueError('context must be an object')
    # Flat context is accepted for older host adapters; nested context wins.
    context = {**{k:v for k,v in request.items() if k not in {'quantity','context'}}, **context}
    if 'fictional' in context and not isinstance(context['fictional'], bool):
        raise ValueError('context.fictional must be boolean')
    out = {'schema_version': 1, 'engine': 'handbook_finite', 'ruleset_id': rules['id'],
           'status': 'requires_review', 'display_label': '待核对规则前提',
           'energy_reference': None, 'scale_reference': None, 'conclusion': None,
           'ambiguities': [], 'sources': [], 'arithmetic':{'decimal_precision':1024,
               'unit_comparison':'Exact within the 256-character accepted finite-decimal input bound.',
               'division':'Nonterminating divisions are rounded to 1024 significant decimal digits; not arbitrary precision.'}, 'limits': [
               '原作语义、材料和破坏机制由调用方核实；本工具只检查数字、已提供前提与具名规则。',
               '能量/尺度映射不自动传给角色攻击、耐久、速度或全部能力。']}
    index = {c['id']:c for c in rules.get('clauses', [])}
    cited = set()
    def cite(cid):
        if cid in index and cid not in cited:
            cited.add(cid)
            out['sources'].append({'clause_id': cid, **index[cid]['source']})
    def issue(code, text, cid):
        out['ambiguities'].append({'code': code, 'detail': text, 'clause_id': cid})
        cite(cid)
    cite('F248-UNITS')
    cite('F250-MIN')
    values = _quantities(request.get('quantity'))
    if values is None:
        out.update(status='unsupported_quantity', display_label='此量不是支持的能量单位，不能按J分档')
        return out
    refs = sorted(rules['energy_references']+rules.get('astronomical_references', []), key=lambda r:_d(r['energy_j']))
    low, energy, high = values
    eref = _energy(energy, refs)
    out['energy_reference'] = eref
    out['energy_interval'] = {'unit':'J','min':_s(low),'best':_s(energy),'max':_s(high),
                              'min_reference':_energy(low,refs),'max_reference':_energy(high,refs)}
    if eref.get('clause_id'):
        cite(eref['clause_id'])
    if eref.get('subtier_cutoffs_unspecified'):
        cite('F249-SUBTIERS')
        out['limits'].append('弱大档之间的标/强/超能量切点未给数值；只返回达到的已知参考点。')

    # Repeated/distributed attacks need their actual energy model, not total area
    # plugged into a single-point blast curve.
    pattern = context.get('attack_pattern', 'single')
    if pattern not in {'single','sequential','distributed_simultaneous'}:
        raise ValueError('unknown attack_pattern')
    if pattern != 'single':
        analysis = {'pattern':pattern, 'total_energy_j':_s(energy)}
        out['attack_analysis'] = analysis
        count = _d(context['attack_count'],'attack_count') if 'attack_count' in context else None
        if count is not None:
            if count < 1 or count != count.to_integral_value():
                raise ValueError('attack_count must be a positive integer')
            analysis['attack_count'] = _s(count)
            analysis['single_attack_energy_j'] = _s(energy/count)
            analysis['single_attack_energy_reference'] = _energy(energy/count,refs)
            for key, label in [('area_m2','scope_per_attack_m2'),('volume_m3','scope_per_attack_m3')]:
                if key in context:
                    analysis[label] = _s(_d(context[key],key)/count)
        if 'duration_seconds' in context:
            seconds = _d(context['duration_seconds'],'duration_seconds')
            if seconds <= 0:
                raise ValueError('duration_seconds must be positive')
            analysis['average_power_w'] = _s(energy/seconds)
        if pattern == 'sequential':
            cite('F270-SEQUENTIAL')
            issue('sequential_total_not_single_attack', '逐次攻击的总能量不能当一击；单发与平均功率已分别列出，W不映射为J。', 'F270-SEQUENTIAL')
        elif context.get('fixed_binding_energy_confirmed') is True:
            analysis['aggregation'] = 'conditional_fixed_binding_energy'
            cite('F270-BINDING')
            out['limits'].append('聚合以调用方已证明这是固定结合能问题为条件，不代表所有多点攻击可聚合。')
        else:
            issue('distributed_scope_needs_energy_model', '总范围/N后须用实际子范围模型求能量再乘N；未知N按理论最低模型，本工具没有凭空补空爆曲线。', 'F270-MULTICALC')

    release = context.get('release','unknown')
    if release not in {'unknown','violent','slow'}:
        raise ValueError('release must be unknown, violent or slow')
    if release == 'slow':
        issue('slow_release_grade_undefined','册内要求慢释放降一格，但未定义时间界线或一格尺寸，不能自动选大档或小格。','F250-RELEASE')
    elif release == 'unknown':
        issue('release_duration_unverified','释放快慢未提供；无法确认可直接用当前能量，若是慢释放尚须降一格。','F250-RELEASE')

    fictional = context.get('fictional',True)
    if not fictional:
        if not out['ambiguities']:
            out.update(status='reference_mapping',conclusion={**eref,'basis':'nonfiction_actual_energy'},
                       display_label='能量参考：'+eref['label'])
        else:
            out['display_label']='能量参考：'+eref['label']+'；最终判定待核对'
        return out

    collapse = context.get('mechanism') in {'impact_collapse','crush_collapse','strike_collapse'} and context.get('observed_building_collapse') is True
    if collapse:
        cite('F268-COLLAPSE')
        if not out['ambiguities']:
            out.update(status='conditional_mapping',display_label='楼级（直观坍塌豁免）',
                conclusion={'tier_id':'building-collapse-exception','label':'楼级（直观坍塌豁免）',
                            'scope_limit':'building_collapse_only','clause_id':'F268-COLLAPSE',
                            'source':index['F268-COLLAPSE']['source']})
        return out

    geometry = context.get('geometry')
    if geometry is None:
        geometry = 'built_area' if 'area_m2' in context else 'crater_volume' if 'volume_m3' in context else None
    measurement = {'geometry':geometry}
    out['scale_measurement'] = measurement
    value = None
    field = None
    if geometry == 'built_area':
        field = 'area_m2'
        if context.get('material_equivalence_confirmed') is True and 'equivalent_area_m2' in context:
            value = _d(context['equivalent_area_m2'],'equivalent_area_m2')
            measurement['equivalent_area_m2'] = _s(value)
            cite('F268-MATERIAL')
        elif 'area_m2' in context:
            value = _d(context['area_m2'],'area_m2')
            material = context.get('material')
            if material not in {'RC','reinforced_concrete','钢筋混凝土','brick_concrete','砖混','砖混凝土'}:
                issue('building_material_needs_equivalence','面积表要求RC/砖混倒塌；材料未知或不同需等效换算，不能直接使用该面积。','F268-MATERIAL')
        cite('F259-BUILT')
    elif geometry == 'crater_volume':
        field = 'volume_m3'
        if 'volume_m3' in context:
            value = _d(context['volume_m3'],'volume_m3')
    elif geometry == 'equivalent_volume':
        field = 'volume_m3'
        cite('F257-EQUIVALENT')
        mass = None
        if context.get('cloud') is True:
            cite('F257-CLOUDS')
            airflow=context.get('cloud_airflow_observed')
            if airflow not in (True,False):
                issue('cloud_airflow_unverified','云消散是否有实际气流表现未核对，空气质量不能自动计入。','F257-CLOUDS')
            elif 'droplet_mass_kg' not in context or airflow and 'affected_air_mass_kg' not in context:
                issue('cloud_mass_missing','需水滴质量；若有气流，还需实际受影响空气质量。','F257-CLOUDS')
            else:
                mass=_d(context['droplet_mass_kg'],'droplet_mass_kg')
                if airflow:
                    mass+=_d(context['affected_air_mass_kg'],'affected_air_mass_kg')
        elif 'mass_kg' in context:
            mass=_d(context['mass_kg'],'mass_kg')
        elif 'density_kg_m3' in context and 'volume_m3' in context:
            mass=_d(context['density_kg_m3'],'density_kg_m3')*_d(context['volume_m3'],'volume_m3')
        if mass is not None:
            density=_d(context.get('reference_density_kg_m3','1000'),'reference_density_kg_m3')
            if density<=0:
                raise ValueError('reference_density_kg_m3 must be positive')
            value=mass/density
            measurement.update(mass_kg=_s(mass),reference_density_kg_m3=_s(density),equivalent_volume_m3=_s(value))
    elif geometry == 'solid_sphere':
        field='solid_sphere_diameter_m'
        if 'diameter_m' in context:
            value=_d(context['diameter_m'],'diameter_m')
    elif geometry not in (None,'verified_scope'):
        raise ValueError('unsupported geometry')

    sref=None
    if value is not None:
        measurement[field]=_s(value)
        country_rank=rules['rank_ids'].index('weak-country')
        candidates=[r for r in rules['scale_references'] if field in r and value>=_d(r[field])
                    and (field!='area_m2' or r['rank']<=country_rank)]
        row=max(candidates,key=lambda r:r['rank']) if candidates else None
        sref=_public(row)
        if row:
            cite(row['clause_id'])
        if field=='volume_m3' and Decimal('2200000000')<=value<Decimal('2240000000'):
            issue('weak_city_volume_rounding_conflict','249表弱城2.2km³，267建议2.24km³；本值落在差异区，须选明分支。','F267-SCALEDETAIL')
    elif context.get('scale_tier_id'):
        row=next((r for r in refs+rules['scale_references'] if r['id']==context['scale_tier_id']),None)
        if row is None:
            raise ValueError('scale_tier_id must belong to this ruleset')
        sref=_public(row)
        cite(row['clause_id'])
        out['limits'].append('scale_tier_id是调用方已校验范围的声明，本工具没有重新测量画面。')
    if sref is None:
        issue('scale_missing','虚拟作品缺少可核对面积/体积/球直径或已核范围，不能仅凭能量最终定档。','F250-MIN')
    else:
        out['scale_reference']=sref
        if context.get('destruction_requirement_confirmed') is not True:
            issue('destruction_requirement_unverified','表中的倒塌/板块/引力结合等破坏要求尚未由调用方核实。','F249-SCALE')
        rank=sref['rank']
        rank_map={tid:i for i,tid in enumerate(rules['rank_ids'])}
        if rank>=rank_map['weak-continent'] and rank<rank_map['weak-planet']:
            giant_exception=(sref['tier_id']=='weak-continent' and geometry=='crater_volume' and context.get('obvious_continental_giant_crater') is True)
            if giant_exception:
                cite('F268-GIANTCRATER')
                measurement['continental_giant_crater_exception']=True
            elif context.get('geological_requirement_confirmed') is not True:
                issue('geological_scope_unverified','大陆/地表还需完整板块或相应地质影响，不能只认浅表体积。','F264-LITHOSPHERE')
        if rank==rank_map['weak-planet'] and context.get('gravity_unbinding_confirmed') is not True:
            issue('gravity_unbinding_unverified','弱爆星须克服引力结合；球直径或体积本身不证明离散终态。','F249-SCALE')
        if field=='area_m2':
            cite('F268-COUNTRYSCALE')
            out['limits'].append('高于弱国取消面积自动升级；本面积路线最多给弱国尺度，后续需体积/地质证据。')
        if context.get('material') in {'brick_concrete','砖混','砖混凝土'} and sref['rank']<rank_map['weak-country'] and context.get('material_equivalence_confirmed') is not True:
            issue('below_country_requires_RC','国以下面积要求RC倒塌；砖混需换算RC等效范围。','F268-MATERIAL')

    if sref and not out['ambiguities']:
        chosen=eref if eref['rank']<=sref['rank'] else sref
        out.update(status='conditional_mapping',conclusion={**chosen,'basis':'minimum_of_energy_and_scale',
                   'conditions_supplied_by_caller':True}, display_label=chosen['label']+'（能量/尺度条件判定）')
        if eref['rank']<0 or sref['rank']<0:
            out['display_label']='低于本次可核对的参考尺度'
    else:
        out['display_label']='能量参考：'+eref['label']+'；最终判定待核对'
    return out


def classify(request: dict, ruleset: dict | None = None) -> dict:
    """Return a JSON-safe audit record; source semantics stay the host's task."""
    try:
        if ruleset is None:
            path=Path(__file__).resolve().parents[1]/'rulesets'/DEFAULT_RULESET
            ruleset=json.loads(path.read_text(encoding='utf-8-sig'))
        with localcontext() as arithmetic:
            arithmetic.prec=1024
            return _classify(request,ruleset)
    except (ValueError,TypeError,KeyError,InvalidOperation,OSError,ZeroDivisionError) as exc:
        return {'engine':'handbook_finite','status':'invalid','display_label':'输入或规则无效',
                'conclusion':None,'energy_reference':None,'scale_reference':None,
                'ambiguities':[],'sources':[],'errors':[str(exc)]}


def classify_quantity(quantity, context=None, ruleset=None):
    return classify({'quantity':quantity,'context':context or {}},ruleset)
