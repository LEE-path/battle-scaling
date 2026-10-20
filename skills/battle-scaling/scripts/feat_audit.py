#!/usr/bin/env python3
"""Offline, explicit-premise review of ONE fictional event, without semantic inference."""
from __future__ import annotations

import copy
import hashlib
import json
from pk_modes import READABLE

USES = ('observed_output', 'material_model', 'full_effort', 'state_transfer', 'upper_bound')
MODES = {'normal', 'highest', 'lowball'}
BASES = {'observed', 'measured', 'documented', 'estimated', 'assumed',
         'host_interpretation', 'author_statement', 'narrator_statement',
         'character_statement', 'reasonable_inference', 'unknown'}
KINDS = {'direct_observation', 'author_statement', 'narrator_statement',
         'character_statement', 'reasonable_inference'}
RANK = {'supported_by_packet': 0, 'conditional': 1, 'undetermined': 2, 'blocked': 3}


def _object(value, path):
    if not isinstance(value, dict):
        raise ValueError(path + ' must be an object')
    return value


def _array(value, path):
    if not isinstance(value, list) or len(value) > 2048:
        raise ValueError(path + ' must be an array of at most 2048 entries')
    return value


def _strings(value, path):
    if any(not isinstance(x, str) or not x.strip() for x in _array(value, path)):
        raise ValueError(path + ' must contain nonempty strings')
    return list(dict.fromkeys(value))


def _locator(value):
    return (isinstance(value, str) and bool(value.strip())) or (isinstance(value, dict) and bool(value))


def _result(status='supported_by_packet', reason=None, assumptions=None, source_ids=None, unknown=None):
    return {'status': status, 'reasons': [reason] if reason else [],
            'assumptions': assumptions or [], 'source_ids': source_ids or [],
            '_unknown': unknown or []}


def _merge(*items):
    result = _result()
    for item in items:
        if RANK[item['status']] > RANK[result['status']]:
            result['status'] = item['status']
        for key in ('reasons', 'assumptions', 'source_ids', '_unknown'):
            result[key] = list(dict.fromkeys(result[key] + item[key]))
    return result


class _Review:
    def __init__(self, request):
        self.request = copy.deepcopy(_object(request, 'request'))
        self.mode = request.get('mode', 'normal')
        if not isinstance(self.mode, str) or self.mode not in MODES:
            raise ValueError('mode must be normal, highest or lowball')
        self.uses = _strings(request.get('requested_uses', ['observed_output']), 'requested_uses')
        if not self.uses or any(x not in USES for x in self.uses):
            raise ValueError('requested_uses must name at least one supported use')
        raw = request.get('sources', [])
        if isinstance(raw, dict):
            if any(not isinstance(key, str) or not key for key in raw):
                raise ValueError('sources mapping needs nonempty string IDs')
            raw = [dict(_object(value, 'sources.' + key), id=key) for key, value in raw.items()]
        self.sources = {}
        for item in _array(raw, 'sources'):
            item = _object(item, 'sources[]')
            sid = item.get('id')
            if not isinstance(sid, str) or not sid or sid in self.sources:
                raise ValueError('sources need unique nonempty IDs')
            if item.get('access') is not None and not isinstance(item['access'], str):
                raise ValueError('source access must be a string')
            self.sources[sid] = item
        self.evidence = {}
        for item in _array(request.get('evidence_claims', []), 'evidence_claims'):
            item = _object(item, 'evidence_claims[]')
            eid = item.get('id')
            if not isinstance(eid, str) or not eid or eid in self.evidence:
                raise ValueError('evidence_claims need unique nonempty IDs')
            if not isinstance(item.get('kind'), str) or item['kind'] not in KINDS:
                raise ValueError('unsupported evidence_claim kind')
            if not isinstance(item.get('reason', ''), str):
                raise ValueError('evidence_claim reason must be a string')
            self.evidence[eid] = item
        for name in ('event', 'causal_chain', 'actor_state', 'combat_intent',
                     'effort', 'state_transfer', 'upper_bound'):
            _object(request.get(name, {}), name)
        self.materials = _array(request.get('materials', []), 'materials')
        seen = set()
        for item in self.materials:
            item = _object(item, 'materials[]')
            mid = item.get('id')
            if not isinstance(mid, str) or not mid or mid in seen:
                raise ValueError('materials need unique nonempty IDs')
            seen.add(mid)
            _strings(item.get('identity_candidates', []), 'materials.identity_candidates')
            _object(item.get('condition', {}), 'materials.condition')
        self.issues, self.tasks, self.ledger = [], [], []
        self.cache, self.active = {}, set()

    def issue(self, code, path, message, status='undetermined'):
        item = {'code': code, 'path': path, 'message': message, 'severity': status}
        if item not in self.issues:
            self.issues.append(item)

    def task(self, path, question, ids=None):
        task_key = json.dumps([path, question], ensure_ascii=False).encode('utf-8')
        item = {'task_id': 'feat-' + hashlib.sha256(task_key).hexdigest()[:12],
                'kind': 'feat_premise_review', 'target_path': path, 'query': question,
                'required_fields': ['status', 'basis', 'reason', 'source_ids'],
                'completion_criterion': 'Host reads the cited original context; records support, '
                                        'counterevidence or an explicit unresolved assumption.',
                'source_ids': ids or [], 'executor': 'host_research_or_vision', 'status': 'pending'}
        if item not in self.tasks:
            self.tasks.append(item)

    def refs(self, raw, path):
        ids = _strings(raw, path + '.source_ids')
        if any(sid not in self.sources for sid in ids):
            raise ValueError(path + ' references unknown source IDs')
        bad = [sid for sid in ids if self.sources[sid].get('access') not in READABLE]
        if bad:
            self.issue('source_unreadable', path, 'Source access metadata is not readable: ' + ', '.join(bad), 'blocked')
            self.task(path, 'Retrieve and read the source before admitting this premise.', bad)
            return _result('blocked', path + ': unreadable supporting source.', source_ids=ids)
        if not ids:
            self.issue('missing_source_binding', path, 'Bind a readable source to this explicit premise.')
            self.task(path, 'Find the original locator for this premise.')
            return _result('undetermined', path + ': no source binding.', unknown=[path])
        incomplete = [sid for sid in ids if any(not isinstance(self.sources[sid].get(key), str)
                      or not self.sources[sid][key].strip() for key in ('title', 'origin'))
                      or not _locator(self.sources[sid].get('locator'))]
        if incomplete:
            self.issue('source_metadata_incomplete', path,
                       'Source title, origin and original locator are required: ' + ', '.join(incomplete))
            self.task(path, 'Complete source identity and original page/panel/time locator.', incomplete)
            return _result('undetermined', path + ': incomplete source identity/locator.',
                           source_ids=ids, unknown=[path + '.source_metadata'])
        return _result(source_ids=ids)

    def claim(self, raw, path, required_true=True):
        if path in self.cache:
            return self.cache[path]
        raw = _object({} if raw is None else raw, path)
        status = raw.get('status')
        if status is not None and type(status) is not bool:
            raise ValueError(path + '.status must be true, false or null')
        basis = raw.get('basis', 'unknown')
        if not isinstance(basis, str) or basis not in BASES:
            raise ValueError(path + ': unsupported basis')
        reason = raw.get('reason', '')
        if not isinstance(reason, str):
            raise ValueError(path + '.reason must be a string')
        assumptions = _strings(raw.get('assumptions', []), path + '.assumptions')
        evidence_ids = _strings(raw.get('evidence_claim_ids', []), path + '.evidence_claim_ids')
        if any(eid not in self.evidence for eid in evidence_ids):
            raise ValueError(path + ' references unknown evidence_claim IDs')
        ids = _strings(raw.get('source_ids', []), path + '.source_ids')
        # A referenced evidence record is also an explicit source binding.
        for eid in evidence_ids:
            ids += _strings(self.evidence[eid].get('source_ids', []), 'evidence_claims.' + eid + '.source_ids')
        ids = list(dict.fromkeys(ids))
        parts = []
        if status is False and required_true:
            self.issue('contradicted_premise', path, 'Known false premise remains false in every mode.', 'blocked')
            parts.append(_result('blocked', path + ': explicitly false.', source_ids=ids))
        elif status is None:
            conditional = bool(assumptions)
            parts.append(_result('conditional' if conditional else 'undetermined',
                                 path + ': unresolved premise.', assumptions=assumptions,
                                 source_ids=ids, unknown=[] if conditional else [path]))
            self.issue('unknown_premise', path, 'Preserve this as an assumption or obtain evidence.',
                       'conditional' if conditional else 'undetermined')
            self.task(path, 'Establish or refute this event-specific premise.', ids)
        elif basis == 'unknown' or not reason.strip():
            parts.append(_result('undetermined', path + ': basis and reason are required.', unknown=[path]))
            self.task(path, 'Record why the source supports this premise.', ids)
        if ids or status is not None:
            parts.append(self.refs(ids, path))
        if basis in {'estimated', 'assumed', 'host_interpretation', 'reasonable_inference'}:
            parts.append(_result('conditional', path + ': explicitly interpretive or estimated.',
                                 assumptions=assumptions or [reason or ('Assume ' + path + '.')]))
        if basis in {'author_statement', 'narrator_statement', 'character_statement'}:
            matching = [eid for eid in evidence_ids if self.evidence[eid]['kind'] == basis]
            if not matching:
                unknown_author = basis == 'author_statement'
                parts.append(_result('undetermined' if unknown_author else 'conditional',
                                     path + ': statement authority/context not established.',
                                     assumptions=[] if unknown_author else
                                     ['Treat ' + path + ' as a statement awaiting contextual corroboration.'],
                                     unknown=[path + '.author_identity'] if unknown_author else []))
                if unknown_author:
                    self.issue('author_identity_unverified', path,
                               'Unverified attribution cannot acquire author authority through an assumption.')
                self.task(path, 'Classify the speaker and verify identity, context, knowledge and original conflicts.', ids)
        for eid in evidence_ids:
            parts.append(self.review_evidence(eid))
        result = _merge(*parts)
        if reason.strip() and result['status'] == 'supported_by_packet':
            result['reasons'].append(path + ': ' + reason)
        normalized = {**raw, 'status': status, 'basis': basis, 'reason': reason,
                      'source_ids': ids, 'review_status': result['status']}
        self.ledger.append({'path': path, **normalized})
        self.cache[path] = result
        return result

    def at(self, section, key):
        return self.claim(self.request.get(section, {}).get(key), section + '.' + key)

    def text(self, value, path):
        if path.endswith('.locator') and _locator(value):
            return _result()
        if not isinstance(value, str) or not value.strip():
            self.issue('missing_scope', path, 'Provide an explicit event, mechanism or configuration scope.')
            self.task(path, 'Record the event-specific identity, state or scope.')
            return _result('undetermined', path + ': scope is missing.', unknown=[path])
        return _result()

    def review_evidence(self, eid):
        path = 'evidence_claims.' + eid
        if path in self.cache:
            return self.cache[path]
        if eid in self.active:
            raise ValueError('circular evidence_claim references cannot establish a premise')
        self.active.add(eid)
        item = self.evidence[eid]
        kind = item['kind']
        checks = _object(item.get('checks', {}), path + '.checks')
        parts = [self.refs(item.get('source_ids', []), path)]
        requirements = {
            'direct_observation': (),
            'author_statement': ('identity_verified', 'original_context', 'version_applicable',
                                 'serious', 'consistent_with_original'),
            'narrator_statement': ('scope_applicable', 'knowledge_sufficient', 'consistent_with_original'),
            'character_statement': ('scope_applicable', 'knowledge_sufficient', 'consistent_with_original',
                                    'independent_corroboration'),
            'reasonable_inference': ('alternatives_considered',),
        }[kind]
        for key in requirements:
            parts.append(self.claim(checks.get(key), path + '.checks.' + key))
        identity = checks.get('identity_verified')
        identity_status = identity.get('status') if isinstance(identity, dict) else None
        if kind == 'author_statement' and identity_status is not True:
            self.issue('author_identity_unverified', path,
                       'An attributed screenshot is a lead; it does not authenticate the author.')
            parts.append(_result('undetermined', path + ': author authority is not established; '
                                 'a non-authoritative inference requires a separate evidence claim.',
                                 unknown=[path + '.checks.identity_verified']))
        if kind == 'reasonable_inference':
            premises = _array(item.get('premises', []), path + '.premises')
            if not premises:
                parts.append(_result('undetermined', path + ': inference premises missing.', unknown=[path + '.premises']))
                self.task(path + '.premises', 'List the inference premises and alternative explanations.')
            for i, premise in enumerate(premises):
                parts.append(self.claim(premise, path + '.premises.' + str(i)))
            parts.append(_result('conditional', path + ': reasonable inference remains conditional.',
                                 assumptions=_strings(item.get('assumptions', []), path + '.assumptions')
                                 or [item.get('reason') or ('Accept the listed inference at ' + path + '.')]))
        result = _merge(*parts)
        self.active.remove(eid)
        self.cache[path] = result
        return result

    def observed(self):
        event, chain = self.request.get('event', {}), self.request.get('causal_chain', {})
        parts = [self.at('event', 'observed_output'), self.at('causal_chain', 'attribution')]
        for key in ('actor_id', 'version', 'state', 'locator', 'description'):
            parts.append(self.text(event.get(key), 'event.' + key))
        for key in ('action', 'transmission', 'target_response'):
            parts.append(self.text(chain.get(key), 'causal_chain.' + key))
        confounders = _array(chain.get('confounders', []), 'causal_chain.confounders')
        for i, item in enumerate(confounders):
            path = 'causal_chain.confounders.' + str(i)
            item = _object(item, path)
            if not isinstance(item.get('kind'), str) or item['kind'] not in {
                    'pre_damage', 'environment', 'external_energy', 'other_actor', 'other'}:
                raise ValueError(path + ': unsupported confounder kind')
            parts.append(self.text(item.get('description'), path + '.description'))
            parts.append(self.claim(item.get('accounted_for'), path + '.accounted_for'))
        if confounders:
            parts.append(self.at('causal_chain', 'incremental_effect_isolated'))
        return _merge(*parts)

    def material(self):
        parts = []
        if not self.materials:
            self.task('materials', 'Identify the concrete material, geometry, condition and applicable property model.')
            return _result('undetermined', 'materials: no material model packet.', unknown=['materials'])
        for i, item in enumerate(self.materials):
            path = 'materials.' + str(i)
            for key in ('identification', 'geometry', 'properties', 'property_match'):
                parts.append(self.claim(item.get(key), path + '.' + key))
            condition = item.get('condition', {})
            parts.append(self.text(condition.get('description'), path + '.condition.description'))
            parts.append(self.claim(condition.get('accounted_for'), path + '.condition.accounted_for'))
        return _merge(*parts)

    def full(self):
        return self.at('effort', 'full_effort')

    def transfer(self):
        item = self.request.get('state_transfer', {})
        return _merge(self.text(item.get('target_state'), 'state_transfer.target_state'),
                      self.at('state_transfer', 'compatible'))

    def upper(self):
        item = self.request.get('upper_bound', {})
        parts = [self.observed(), self.full(), self.text(item.get('scope'), 'upper_bound.scope')]
        parts += [self.at('upper_bound', key) for key in
                  ('failure_observed', 'opportunity', 'same_configuration', 'mechanism_applicable')]
        return _merge(*parts)

    def execute(self):
        # Retain volunteered state/intent facts without converting their truth value
        # into output loss, intent-to-effort equivalence, or numerical multipliers.
        for section in ('actor_state', 'combat_intent'):
            for key, value in self.request.get(section, {}).items():
                if isinstance(value, dict):
                    self.claim(value, section + '.' + key, required_true=False)
        for key in ('actual_output_fraction', 'percent'):
            if key in self.request.get('effort', {}):
                self.issue('effort_fraction_not_consumed', 'effort.' + key,
                           'This metadata is not consumed: no full-output extrapolation is computed.', 'conditional')
        handlers = {'observed_output': self.observed, 'material_model': self.material,
                    'full_effort': self.full, 'state_transfer': self.transfer, 'upper_bound': self.upper}
        admissions, branches = {}, []
        for use in self.uses:
            result = handlers[use]()
            admissions[use] = {key: value for key, value in result.items() if not key.startswith('_')}
            if self.mode == 'highest' and result['status'] == 'undetermined' and result['_unknown']:
                branches.append({'use': use, 'status': 'conditional', 'admitted': False,
                                 'requires': result['_unknown'],
                                 'assumptions': ['Assume ' + path + ' is established in the stated scope.'
                                                 for path in result['_unknown']],
                                 'reason': 'Separate hypothetical branch; does not replace the admission or any known false premise.'})
        status = max((item['status'] for item in admissions.values()), key=RANK.get)
        return {'schema_version': 1, 'engine': 'battle-scaling.feat_audit',
                'operation': 'feat_review', 'id': self.request.get('id'), 'mode': self.mode,
                'status': status, 'requested_uses': self.uses, 'admissions': admissions,
                'event': self.request.get('event', {}), 'ledger': self.ledger,
                'recorded_context': {key: self.request[key] for key in
                    ('causal_chain', 'actor_state', 'combat_intent', 'effort', 'materials',
                     'state_transfer', 'upper_bound') if key in self.request},
                'evidence_claims': copy.deepcopy(list(self.evidence.values())),
                'issues': self.issues, 'research_tasks': self.tasks, 'conditional_branches': branches,
                'validation_scope': 'Offline structure, source-access metadata, explicit premise and reference checks; '
                    'does not read images, infer unstated facts, authenticate an author or establish semantic entailment. '
                    'supported_by_packet means declared premises pass these checks, not independently verified truth. '
                    'No damage formula, tier, numerical state discount or full-output extrapolation is computed.'}


def run(request):
    """Review one packet. Raises ValueError for malformed structure or unknown IDs."""
    return _Review(request).execute()


if __name__ == '__main__':
    import argparse
    import sys
    from pathlib import Path
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.output and Path(args.output).resolve()==Path(args.input).resolve():
        parser.error('output must not overwrite the input request')
    with open(args.input, encoding='utf-8-sig') as stream:
        output = run(json.load(stream))
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as stream:
            stream.write(rendered + '\n')
    else:
        print(rendered)
