#!/usr/bin/env python3
"""Bind physical/scaling derivations to evidence and produce missing-evidence jobs.

Standard-library-only orchestration of the existing physics, evidence and typed
high-tier engines. It never fetches sources, authenticates a caller's assertions,
selects a universally correct physical model or invents a new tier threshold.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from pk_modes import READABLE

MODES = {'normal', 'highest', 'lowball', 'all'}
MODE_ALIASES = {'常态': 'normal', '最高': 'highest', '扒下限': 'lowball'}
RAW_ATTRIBUTES = {'raw_energy', 'raw_force', 'raw_torque', 'raw_work',
                  'raw_quantity', 'raw_speed', 'raw_pressure'}
ENERGY_ATTRIBUTES = {'AP', 'DC', 'attack', 'attack_potency', 'destructive_capacity',
                     'durability', 'output', '输出', '体防', '破坏'}
RAW_UNITS = {'raw_energy': {'J', 'kg TNT'}, 'raw_work': {'J'},
             'raw_force': {'N'}, 'raw_torque': {'N m'}, 'raw_speed': {'m/s'},
             'raw_pressure': {'Pa'}}


class Audit:
    def __init__(self, operation, mode='normal'):
        self.out = {'schema_version': 1, 'engine': 'battle-scaling.derivation_audit',
                    'operation': operation, 'mode': mode, 'status': 'supported_by_packet',
                    'issues': [], 'research_tasks': [],
                    'validation_scope': 'Offline reference, binding, condition and computation checks. '
                    'Source contents and semantic entailment remain host-reviewed claims; '
                    'supported_by_packet does not mean independently authenticated.'}

    def issue(self, code, message, path='', severity='conditional'):
        item = {'code': code, 'message': message, 'path': path, 'severity': severity}
        if item not in self.out['issues']:
            self.out['issues'].append(item)
        rank = {'supported_by_packet': 0, 'conditional': 1, 'blocked': 2, 'invalid': 3}
        if rank[severity] > rank[self.out['status']]:
            self.out['status'] = severity

    def task(self, kind, query, path, required_fields, completion, source_ids=None):
        raw = json.dumps([kind, query, path], ensure_ascii=False).encode('utf-8')
        item = {'task_id': 'derive-' + hashlib.sha256(raw).hexdigest()[:12],
                'kind': kind, 'query': query, 'target_path': path,
                'required_fields': required_fields, 'completion_criterion': completion,
                'source_ids': source_ids or [], 'executor': 'host_research_or_vision',
                'status': 'pending'}
        if item not in self.out['research_tasks']:
            self.out['research_tasks'].append(item)


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(name + ' must be an object')
    return value


def _objects(value, name):
    if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
        raise ValueError(name + ' must be an array of objects')
    if len(value) > 2048:
        raise ValueError(name + ' exceeds the 2048-record audit bound; split the packet')
    return value


def _ids(value, name):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(name + ' must contain nonempty string IDs')
    return value


def _sources(raw):
    sources = {}
    for item in _objects(raw, 'sources'):
        sid = item.get('id')
        if not isinstance(sid, str) or not sid or sid in sources:
            raise ValueError('sources need unique nonempty IDs')
        sources[sid] = item
    return sources


def _refs(item, sources, name, audit, required=True):
    ids = item.get('source_ids', item.get('evidence_ids', []))
    if item.get('source_id'):
        ids = [item['source_id']] + ids
    ids = _ids(ids, name + '.source_ids')
    if any(sid not in sources for sid in ids):
        raise ValueError(name + ' references unknown source IDs')
    if required and not ids:
        audit.issue('missing_source_binding', 'Attach the supporting source and its original locator.', name)
        audit.task('verify_source', 'Locate source evidence for ' + name, name,
                   ['source_id', 'origin', 'access', 'locator'],
                   'A retrieved original or explicitly labelled secondary source is bound to this claim.')
    for sid in ids:
        source = sources[sid]
        if source.get('access') not in READABLE:
            audit.issue('source_unreadable',
                        'Unreadable or merely downloaded evidence can support a hypothetical scenario calculation, '
                        'but not an admitted source-dependent anchor or inheritance.', 'sources.' + sid, 'blocked')
        good = source.get('origin') == 'primary' and source.get('access') in {'verified', 'read', 'verified_via_host_browser'}
        if not source.get('locator') or not good:
            audit.issue('source_not_original_verified',
                        'Keep this source as a provisional lead; do not silently promote it to verified original evidence.',
                        'sources.' + sid)
            audit.task('verify_source', 'Verify original evidence: ' + source.get('title', sid),
                       'sources.' + sid, ['original_url_or_file', 'chapter_page_panel_or_pts',
                       'exact_text_or_visible_fact', 'access', 'continuity'],
                       'Read the original locator and record what it supports, contradicts or leaves unknown.', [sid])
    return list(dict.fromkeys(ids))


def _conditions(raw, sources, path, audit):
    records = []
    for i, item in enumerate(_objects(raw, path)):
        name = item.get('name')
        if not isinstance(name, str) or not name:
            raise ValueError(path + ': condition needs a name')
        status = item.get('status')
        if status is not None and type(status) is not bool:
            raise ValueError(path + '.' + name + ': status must be true, false or null')
        ids = _refs(item, sources, path + '.' + name, audit)
        if status is False:
            audit.issue('contradicted_condition', 'Known false premise cannot be admitted by highest mode: ' + name,
                        path + '.' + name, 'blocked')
        elif status is None:
            audit.issue('unknown_condition', 'The derivation is conditional on ' + name, path + '.' + name)
            audit.task('condition_evidence', 'Establish or refute ' + name, path + '.' + name,
                       ['status', 'source_ids', 'reason', 'scope'],
                       'Give a sourced true/false judgment or preserve an explicit unresolved branch.', ids)
        records.append({**item, 'source_ids': ids})
    return records


def _input_paths(inputs, prefix=''):
    for key, value in inputs.items():
        name = prefix + key
        if key == 'samples' and isinstance(value, list):
            for i, sample in enumerate(value):
                if isinstance(sample, dict):
                    yield from _input_paths(sample, name + '[' + str(i) + '].')
        else:
            yield name, value


def _quantity_at(output, path):
    quantity = output['result']
    for key in path:
        if not isinstance(quantity, dict) or key not in quantity:
            raise ValueError('result_path does not identify a computed scalar quantity')
        quantity = quantity[key]
    if not isinstance(quantity, dict) or not {'value', 'unit'} <= set(quantity):
        raise ValueError('result_path must select a computed value/unit object')
    return {**quantity, 'quantity': quantity.get('quantity', '.'.join(path) or output['result']['quantity'])}


def _physical(request, audit):
    from physics import calculate
    sources = _sources(request.get('sources', []))
    observations = {}
    for item in _objects(request.get('observations', []), 'observations'):
        oid = item.get('id')
        if not isinstance(oid, str) or not oid or oid in observations:
            raise ValueError('observations need unique nonempty IDs')
        ids = _refs(item, sources, 'observations.' + oid, audit)
        observations[oid] = {**item, 'source_ids': ids}
        if not item.get('locator') or not item.get('visible_fact'):
            audit.issue('incomplete_observation', 'Keep observation, interpretation and unknowns separate.', 'observations.' + oid)
            audit.task('visual_observation', 'Read page/panel/frame for ' + oid,
                       'observations.' + oid, ['locator', 'visible_fact', 'interpretation', 'unknowns', 'image_sha256'],
                       'Bind visible action to an actual page/panel/bbox or PTS; label assumptions.', ids)
    calculation = copy.deepcopy(_object(request.get('calculation'), 'calculation'))
    bindings = _object(request.get('parameter_bindings', {}), 'parameter_bindings')
    used_ids = set()
    ledger = []
    for name, value in _input_paths(_object(calculation.get('inputs', {}), 'calculation.inputs')):
        item = bindings.get(name)
        if item is None:
            audit.issue('parameter_unbound', 'Numerical value is supplied but its evidence is not bound: ' + name,
                        'parameter_bindings.' + name)
            audit.task('parameter_evidence', 'Find or justify ' + name + ' for ' + str(request.get('id', 'this feat')),
                       'parameter_bindings.' + name,
                       ['source_ids', 'basis', 'unit', 'range_or_uncertainty', 'reason'],
                       'Attach measured/documented evidence or an explicitly justified estimate range.')
            ledger.append({'parameter': name, 'input': value, 'status': 'unbound'})
            continue
        item = _object(item, 'parameter_bindings.' + name)
        if item.get('basis') not in {'measured', 'documented', 'estimated', 'assumed'}:
            raise ValueError('parameter_bindings.' + name + '.basis must be measured/documented/estimated/assumed')
        ids = _refs(item, sources, 'parameter_bindings.' + name, audit)
        used_ids.update(ids)
        obs = _ids(item.get('observation_ids', []), 'observation_ids')
        if any(oid not in observations for oid in obs):
            raise ValueError('parameter ' + name + ' references unknown observations')
        for oid in obs:
            used_ids.update(observations[oid]['source_ids'])
        if item['basis'] == 'measured' and not obs:
            audit.issue('measurement_without_observation', 'A measured parameter needs its page/frame measurement record.', name)
            audit.task('visual_measurement', 'Measure ' + name + ' using a justified scale/time reference',
                       'parameter_bindings.' + name, ['observation_ids', 'scale', 'coordinates_or_pts', 'uncertainty'],
                       'Save measurement endpoints and calibration; check camera/perspective/time assumptions.', ids)
        if item['basis'] in {'estimated', 'assumed'}:
            audit.issue('parameter_estimate', 'Explicit estimate/assumption remains a conditional parameter: ' + name, name)
            if not item.get('reason') or name not in calculation.get('intervals', {}) and not item.get('range_justification'):
                audit.task('parameter_range', 'Justify plausible range and material/geometry match for ' + name,
                           'parameter_bindings.' + name, ['reason', 'range_justification', 'source_ids'],
                           'Record a plausible sourced range or explain why a point assumption is appropriate.', ids)
        # The existing calculator also records readable source metadata for its scalar inputs.
        if name in calculation['inputs']:
            original = calculation['inputs'][name]
            if isinstance(original, dict) and 'value' in original:
                original['source'] = '; '.join(ids) or original.get('source', '')
        ledger.append({'parameter': name, 'input': value, **copy.deepcopy(item), 'source_ids': ids})
    audit.out['parameter_ledger'] = ledger
    audit.out['observations'] = list(observations.values())
    audit.out['model_conditions'] = _conditions(request.get('model_conditions', []), sources, 'model_conditions', audit)
    for condition in audit.out['model_conditions']:
        used_ids.update(condition['source_ids'])
    if not audit.out['model_conditions']:
        audit.issue('model_applicability_not_reviewed', 'Numerical validity does not establish the scene matches the model.', 'model_conditions')
        audit.task('model_applicability', 'Check physical model ' + str(calculation.get('model')) + ' against the scene',
                   'model_conditions', ['name', 'status', 'source_ids', 'reason'],
                   'Review mechanism, geometry, material, hidden assumptions and excluded alternative explanations.')
    # Calculate even a disputed scenario, but never advertise it as an admitted feat.
    output = calculate(calculation)
    audit.out['calculation_request'] = calculation
    audit.out['calculation'] = output
    path = _ids(request.get('result_path', []), 'result_path')
    if len(path) > 8:
        raise ValueError('result_path is too deep')
    selected = _quantity_at(output, path)
    audit.out['selected_quantity'] = selected
    if path and output.get('sensitivity'):
        # Existing sensitivity cases describe the primary quantity; recompute
        # the selected subquantity rather than assigning its units to those values.
        cases = []
        for case in output['sensitivity']['cases']:
            scenario = copy.deepcopy(calculation)
            scenario.pop('intervals', None)
            for key, value in case['inputs'].items():
                original = scenario['inputs'][key]
                if isinstance(original, dict):
                    original['value'] = value
                else:
                    scenario['inputs'][key] = value
            q = _quantity_at(calculate(scenario), path)
            cases.append({'inputs': case['inputs'], 'value': q['value'], 'unit': q['unit']})
        audit.out['selected_sensitivity'] = {
            'method': 'Existing calculator interval corner enumeration, selected subquantity recomputed.',
            'meaning': output['sensitivity']['meaning'], 'unit': selected['unit'], 'cases': cases,
            'sampled_min': min(c['value'] for c in cases), 'sampled_max': max(c['value'] for c in cases)}
    else:
        audit.out['selected_sensitivity'] = copy.deepcopy(output.get('sensitivity', {}))
    audit.out['sources'] = list(sources.values())
    target = request.get('target_anchor')
    audit.out['anchor_candidate'] = None
    if target is None:
        return
    target = _object(target, 'target_anchor')
    if any(not isinstance(target.get(k), str) or not target[k] for k in ('subject', 'version', 'state', 'attribute')):
        raise ValueError('target_anchor requires subject, version, state and attribute')
    if 'id' in target and (not isinstance(target['id'], str) or not target['id']):
        raise ValueError('target_anchor.id must be a nonempty string when supplied')
    target.setdefault('id', 'calc-' + hashlib.sha256(json.dumps(
        [request.get('id'), target, calculation, path], sort_keys=True,
        ensure_ascii=False).encode('utf-8')).hexdigest()[:16])
    if selected['value'] < 0 or audit.out['selected_sensitivity'].get('sampled_min', selected['value']) < 0:
        audit.issue('signed_quantity_not_nonnegative_anchor',
                    'Retain signed physical results; the existing feat-anchor format requires nonnegative bounds. '
                    'Do not silently take an absolute value or call negative work destructive energy.',
                    'selected_quantity', 'blocked')
        audit.task('quantity_interpretation', 'Interpret signed result before feat-anchor import',
                   'selected_quantity', ['direction', 'mechanism', 'physical_quantity', 'valid_nonnegative_bound'],
                   'Establish the relevant magnitude/energy with a sourced physical interpretation; preserve the original signed result.')
    transfer = request.get('transfer', {})
    attribute = target['attribute']
    if attribute in RAW_UNITS and selected['unit'] not in RAW_UNITS[attribute] or \
            attribute in ENERGY_ATTRIBUTES and selected['unit'] not in {'J', 'kg TNT'}:
        audit.issue('quantity_attribute_type_mismatch',
                    selected['unit'] + ' does not match the requested quantity type for ' + attribute +
                    '; same-looking dimensions or a caller bridge cannot change the computed quantity type.',
                    'target_anchor.attribute', 'blocked')
        audit.task('quantity_model', 'Find the missing physical relation for ' + attribute,
                   'calculation', ['model', 'required_measurements', 'quantity', 'unit'],
                   'Compute energy through an applicable work/fracture/impact model rather than relabel force or torque.')
    admitted = attribute in RAW_ATTRIBUTES
    if not admitted:
        transfer = _object(transfer, 'transfer')
        status = transfer.get('status')
        if status is not None and type(status) is not bool:
            raise ValueError('transfer.status must be true, false or null')
        ids = _refs(transfer, sources, 'transfer', audit, required=False)
        used_ids.update(ids)
        admitted = status is True and bool(ids) and bool(transfer.get('mechanism'))
        if status is False:
            audit.issue('attribute_transfer_refuted', 'The requested attribute transfer is explicitly refuted.', 'transfer', 'blocked')
        elif not admitted:
            audit.issue('attribute_transfer_missing', 'Calculated quantity cannot automatically become ' + attribute, 'transfer')
            audit.task('attribute_transfer', 'Establish ' + selected['quantity'] + ' -> ' + attribute,
                       'transfer', ['status', 'mechanism', 'source_ids', 'scope', 'conditions'],
                       'Show who produced/absorbed the quantity, what fraction coupled, and the matching state and target.')
    if admitted and audit.out['status'] not in {'blocked', 'invalid'}:
        scalar = selected
        sensitivity = audit.out['selected_sensitivity']
        quantity = {'min': sensitivity.get('sampled_min', scalar['value']),
                    'best': scalar['value'], 'max': sensitivity.get('sampled_max', scalar['value']),
                    'unit': scalar['unit']}
        audit.out['anchor_candidate'] = {**copy.deepcopy(target), 'kind': 'calculation',
            'quantity': quantity, 'evidence_ids': sorted(used_ids),
            'status': 'conditional' if audit.out['status'] == 'conditional' else 'supported_by_packet',
            'calculation_model': output['model'], 'bound': 'estimate',
            'result_path': path,
            'assumptions': output['assumptions'],
            'limitations': ['Candidate only: review this packet before adding it to a character CASE.',
                            'Sampled interval corners are not automatically rigorous extrema or probabilities.'],
            'tier_mapping': 'Delegate to existing evidence/handbook rules with the required destructive context.'}


def _cycles(edges):
    graph = {}
    for edge in edges:
        a = (edge['from']['subject'], edge['from']['attribute'])
        b = (edge['to']['subject'], edge['to']['attribute'])
        graph.setdefault(a, []).append((b, edge['id']))
    # Iterative DFS: no recursion-depth failure for large caller graphs.
    done, found = set(), []
    for start in graph:
        if start in done:
            continue
        stack = [(start, iter(graph.get(start, [])))]
        active, edge_path = {start: 0}, []
        while stack:
            node, iterator = stack[-1]
            try:
                nxt, edge_id = next(iterator)
            except StopIteration:
                stack.pop()
                active.pop(node, None)
                done.add(node)
                if edge_path:
                    edge_path.pop()
                continue
            if nxt in active:
                cycle = edge_path[active[nxt]:] + [edge_id]
                if cycle not in found:
                    found.append(cycle)
            elif nxt not in done:
                active[nxt] = len(stack)
                edge_path.append(edge_id)
                stack.append((nxt, iter(graph.get(nxt, []))))
    return found


def _chain(request, audit):
    from evidence import analyze_case, validate_case, REQUIREMENTS
    case = copy.deepcopy(_object(request.get('case'), 'case'))
    errors = validate_case(case)
    if errors:
        raise ValueError('; '.join(errors))
    sources = _sources(case['sources'])
    admitted_anchors = []
    for anchor in case['anchors']:
        local = Audit('chain_anchor', audit.out['mode'])
        _refs(anchor, sources, 'anchors.' + anchor['id'], local)
        if local.out['status'] != 'blocked':
            admitted_anchors.append(anchor)
        else:
            audit.issue('anchor_source_unreadable', 'Independent anchor excluded until its evidence is readable.',
                        'anchors.' + anchor['id'])
        audit.out['research_tasks'].extend(local.out['research_tasks'])
    case['anchors'] = admitted_anchors
    characters = {c['id']: c for c in case['characters']}
    audits = {}
    edge_ids = {e['id'] for e in case['edges']}
    for item in _objects(request.get('hop_audits', []), 'hop_audits'):
        eid = item.get('edge_id')
        if eid not in edge_ids or eid in audits:
            raise ValueError('hop_audits need unique existing edge_id values')
        audits[eid] = item
    ledger, accepted = [], []
    for edge in case['edges']:
        eid = edge['id']
        local = Audit('chain_hop', audit.out['mode'])
        item = audits.get(eid, {})
        ids = _refs(edge, sources, 'edges.' + eid, local)
        extra = _conditions(item.get('conditions', []), sources, 'hop_audits.' + eid, local)
        required = [{'name': name, 'status': edge.get('conditions', {}).get(name),
                     'source_ids': ids} for name in REQUIREMENTS[edge['relation']]]
        _conditions(required, sources, 'edges.' + eid + '.conditions', local)
        by_name = {c['name']: c for c in extra}
        for bridge in ('state_compatible', 'scope_compatible'):
            if bridge not in by_name:
                local.issue('missing_context_bridge', 'Explicitly check ' + bridge + ' for this hop.', eid)
                local.task('scaling_bridge', 'Check ' + bridge + ' for edge ' + eid,
                           'hop_audits.' + eid, ['name', 'status', 'source_ids', 'reason'],
                           'Compare source/target versions, states, equipment and quantified range before inheritance.', ids)
        endpoints = {}
        for end in ('from', 'to'):
            point = edge[end]
            char = characters[point['subject']]
            supplied = _object(item.get(end, {}), 'hop_audits.' + eid + '.' + end)
            if any(k in supplied and supplied[k] != point.get(k) for k in ('subject', 'attribute')):
                raise ValueError('hop endpoint identity/attribute must match its existing CASE edge')
            endpoints[end] = {**{k: char.get(k) for k in ('version', 'state', 'equipment', 'period')},
                              **point, **supplied}
            if any(k in supplied and supplied[k] != char.get(k) for k in ('version', 'state', 'equipment', 'period')):
                bridge = by_name.get('state_compatible', {})
                if bridge.get('status') is not True:
                    local.issue('endpoint_state_mismatch', 'Endpoint configuration differs from the character CASE.', eid)
        counterexamples = _objects(item.get('counterexamples', []), 'counterexamples')
        for index, counter in enumerate(counterexamples):
            _refs(counter, sources, eid + '.counterexamples.' + str(index), local)
            status = counter.get('status')
            if status not in {'confirmed', 'unresolved', 'resolved'}:
                raise ValueError('counterexample status must be confirmed/unresolved/resolved')
            if status == 'confirmed':
                local.issue('confirmed_counterexample', counter.get('reason', 'Confirmed counterexample'), eid, 'blocked')
            elif status == 'unresolved' or not counter.get('resolution'):
                local.issue('unresolved_counterexample', 'Counterexample needs a sourced resolution or a separate branch.', eid)
                local.task('counterexample_review', 'Resolve counterexample for ' + eid,
                           'hop_audits.' + eid + '.counterexamples.' + str(index),
                           ['source_ids', 'status', 'resolution', 'state_scope_comparison'],
                           'Resolve with source and scope, or keep the alternative conclusion.')
        if not item.get('mechanism') or not item.get('scope'):
            local.issue('inheritance_scope_incomplete', 'Record mechanism and exactly which attribute/range is inherited.', eid)
            local.task('scaling_bridge', 'Document inheritance mechanism and scope for ' + eid,
                       'hop_audits.' + eid, ['mechanism', 'scope', 'source_ids'],
                       'Explain this hop without treating a victory or cosmology label as all-attribute superiority.', ids)
        ledger.append({'edge_id': eid, 'relation': edge['relation'], **endpoints,
                       'source_ids': ids, 'required_conditions': required,
                       'context_conditions': extra, 'mechanism': item.get('mechanism'),
                       'scope': item.get('scope'), 'counterexamples': counterexamples,
                       'status': local.out['status'], 'issues': local.out['issues']})
        if local.out['status'] != 'blocked':
            if local.out['status'] == 'conditional':
                edge.setdefault('assumptions', []).extend(
                    'audit ' + i['code'] + ': ' + i['message'] for i in local.out['issues'])
            accepted.append(edge)
        for issue in local.out['issues']:
            # A blocked hop does not invalidate independent anchors and other paths.
            audit.issue(issue['code'], issue['message'], issue['path'])
        audit.out['research_tasks'].extend(local.out['research_tasks'])
    cycles = _cycles(case['edges'])
    if cycles:
        audit.issue('circular_scaling', 'Cycles cannot supply independent escalation; existing engine rejects revisited endpoints.', 'case.edges')
        for cycle in cycles:
            audit.task('independent_anchor', 'Find independent feat anchor for cycle ' + ' -> '.join(cycle),
                       'case.edges', ['anchor', 'source_ids', 'state', 'quantity_or_typed_object'],
                       'Break circular justification with an independently sourced starting bound.')
    case['edges'] = accepted
    audit.out['hop_ledger'] = ledger
    audit.out['cycles'] = cycles
    audit.out['chain_analysis'] = analyze_case(case, audit.out['mode'])
    audit.out['effective_case'] = case


def _inline_sources(value, path='high_request'):
    if isinstance(value, dict):
        for key, item in value.items():
            location = path + '.' + key
            if key in {'source', 'sources'}:
                for source in item if isinstance(item, list) else [item]:
                    if isinstance(source, dict):
                        yield location, source
            elif isinstance(item, (dict, list)):
                yield from _inline_sources(item, location)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _inline_sources(item, path + '[' + str(i) + ']')


def _high(request, audit):
    from high_tier import analyze
    high_request = copy.deepcopy(_object(request.get('high_request'), 'high_request'))
    if 'mode' not in high_request and audit.out['mode'] != 'all':
        high_request['mode'] = audit.out['mode']
    output = analyze(high_request)
    audit.out['high_analysis'] = output
    audit.out['proof_ledger'] = []
    if output.get('status') == 'invalid':
        audit.issue('typed_analysis_invalid', '; '.join(output.get('errors', [])), 'high_request', 'invalid')
        return
    # Exact arithmetic is independent of whether a work actually instantiates it.
    if output.get('status') != 'exact' or output.get('mappings'):
        audit.issue('qualified_high_derivation', 'Retain typed/source/ruleset qualifications instead of treating a label as a physical scalar.', 'high_request')
    for path, source in _inline_sources(high_request):
        status_text = str(source.get('access_status', source.get('access', '')))
        access = source.get('access', source.get('access_status'))
        if access not in READABLE:
            audit.issue('high_source_unreadable',
                        'Raw structural analysis remains a scenario; source-dependent mappings cannot be admitted '
                        'until supporting evidence has readable access metadata.', path, 'blocked')
        if source.get('origin', source.get('kind')) != 'primary' or access not in {'read', 'verified', 'verified_via_host_browser'} or not source.get('locator'):
            audit.issue('high_source_needs_verification', 'Source presence is not authentication: ' + status_text, path)
            audit.task('verify_source', 'Read and verify structure source ' + str(source.get('url', source.get('title', path))),
                       path, ['locator', 'exact_text', 'original_notation', 'version', 'scope', 'access'],
                       'Record the actual definition/operation and whether it matches the named rule or only a candidate interpretation.')
    bindings = _objects(request.get('proof_bindings', []), 'proof_bindings')
    nodes = {n['id']: n for n in high_request.get('nodes', [])}
    binding_by_node = {}
    for binding in bindings:
        nid = binding.get('node_id')
        if nid not in nodes or nid in binding_by_node:
            raise ValueError('proof_bindings need unique existing node_id values')
        binding_by_node[nid] = binding
        if 'contradicted' in binding and type(binding['contradicted']) is not bool:
            raise ValueError('proof_bindings.contradicted must be a boolean')
    for nid, node in nodes.items():
        binding = binding_by_node.get(nid, {})
        record = {'node_id': nid, 'operation': node.get('operation'),
                  'depends_on': node.get('depends_on', []),
                  'mathematical_object': node.get('typed_object'),
                  'source': node.get('source', node.get('sources')),
                  'scope': node.get('scope'), 'definition': node.get('definition'),
                  'binding': binding}
        audit.out['proof_ledger'].append(record)
        op = node.get('operation')
        if op in {'iteration', 'closure', 'base_reset', 'transcends', 'adjective', 'typed_structure'}:
            if not binding.get('interpretation_bridge'):
                audit.issue('missing_interpretation_bridge', 'Separate source description, mathematical interpretation and named-tier mapping.', 'nodes.' + nid)
                audit.task('mathematical_bridge', 'Audit interpretation of ' + nid + ': ' + node.get('description', ''),
                           'proof_bindings.' + nid,
                           ['source_locator', 'interpretation_bridge', 'object_type', 'domain', 'assumptions', 'rule_id'],
                           'Specify the operation/domain; distinguish finite steps, limit, closure and narrative adjectives. '
                           'Do not identify fictional Φ with Veblen φ or VSB Tier 0 with a cardinal proof.')
        if binding.get('contradicted') is True:
            audit.issue('high_bridge_refuted', 'Known refuted interpretation is not admitted even in highest mode.', 'proof_bindings.' + nid, 'blocked')
    # Native analyzer already enforces travel/identity vs action-property distinctions.
    for warning in output.get('warnings', []):
        if any(key in warning for key in ('property_transfer', 'travel_to_combat', 'identity_to_combat')):
            audit.issue('character_property_bridge_missing', warning, 'high_request.character_relations')
            audit.task('character_structure_bridge', 'Find action/resistance evidence connecting the character to this structure',
                       'high_request.character_relations', ['character_state', 'relation', 'scope', 'mechanism', 'bridge', 'source'],
                       'Show creation/destruction/control/resistance separately; travel, knowledge, identity or existence alone does not grant AP/durability.')
        elif any(key in warning for key in ('unsourced_node', 'definition', 'unknown_anchor', 'candidate_anchor', 'unadmitted_aggressive')):
            audit.issue('high_derivation_gap', warning, 'high_request')
            audit.task('high_structure_evidence', 'Resolve typed derivation gap: ' + warning,
                       'high_request', ['source', 'definition', 'scope', 'interpretation', 'rule'],
                       'Supply the missing premise or keep the disputed mapping as a named conditional branch.')
    if audit.out['status'] == 'blocked':
        audit.out['admitted_mappings'] = []
        audit.out['admitted_combat_properties'] = {}
        audit.out['high_analysis_interpretation'] = 'Raw analyzer output retained for scenario/audit only; unread sources or refuted bridges block admission.'
    else:
        audit.out['admitted_mappings'] = copy.deepcopy(output.get('mappings', []))
        audit.out['admitted_combat_properties'] = copy.deepcopy(output.get('result', {}).get('combat_properties', {}))
    audit.out['limits'] = ['This wrapper audits mappings and missing bridges; it does not formalize every fictional narrative.',
                           'Existing typed analyzer/rulesets remain authoritative for arithmetic and named conventions.',
                           'World construction and character combat attributes are separate proof obligations.']


def run(request: dict) -> dict:
    """Run physical, chain, high or bundle audit. No input mutation or network use."""
    audit = Audit('invalid')
    try:
        request = copy.deepcopy(_object(request, 'request'))
        operation = request.get('operation')
        mode = MODE_ALIASES.get(request.get('mode', 'normal'), request.get('mode', 'normal'))
        if mode not in MODES:
            raise ValueError('mode must be normal/highest/lowball/all or a Chinese alias')
        audit = Audit(operation, mode)
        if operation == 'bundle':
            results = {}
            for key in ('physical', 'chain', 'high'):
                if key in request:
                    sub = copy.deepcopy(_object(request[key], key))
                    sub.setdefault('operation', key)
                    sub.setdefault('mode', mode)
                    results[key] = run(sub)
                    for issue in results[key]['issues']:
                        audit.issue(issue['code'], issue['message'], key + '.' + issue['path'], issue['severity'])
                    audit.out['research_tasks'].extend(results[key]['research_tasks'])
            if not results:
                raise ValueError('bundle requires physical, chain or high payloads')
            audit.out['results'] = results
        elif operation == 'physical':
            _physical(request, audit)
        elif operation == 'chain':
            _chain(request, audit)
        elif operation == 'high':
            _high(request, audit)
        else:
            raise ValueError('operation must be physical/chain/high/bundle')
        # Reject non-finite values rather than serializing nonstandard JSON.
        json.dumps(audit.out, allow_nan=False)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        audit.issue('invalid_request', str(exc), 'request', 'invalid')
        audit.out['errors'] = [str(exc)]
        audit.out['anchor_candidate'] = None
    return audit.out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input == '-' else Path(args.input).read_text(encoding='utf-8-sig')
        request = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Invalid JSON constant: ' + x)))
        if args.output and args.input != '-' and Path(args.output).resolve() == Path(args.input).resolve():
            raise ValueError('Output must not overwrite the request')
        result = run(request)
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding='utf-8')
        else:
            print(rendered, end='')
        return 2 if result['status'] == 'invalid' else 0
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'invalid', 'errors': [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
