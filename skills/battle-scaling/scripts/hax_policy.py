"""Audit host-supplied hax limits without inventing a total tier order or a win."""
from __future__ import annotations

import copy
import math

from pk_modes import READABLE

POLICY_ID = 'user_confirmed_hax_ceiling_20261020'
from rating_modes import MODES, applies, metadata as mode_metadata
CHECKS = ('object', 'compatibility', 'activation', 'resistance')
AXIS = 'affected_entity_tier'
VALIDATION_SCOPE = (
    'Checks this packet for sourced, comparable ability/world ceilings and separate mechanism premises; '
    'does not independently read the original work, authenticate host metadata, establish semantic '
    'entailment, certify all community standards, or prove an effect succeeds or a character wins.'
)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _number(value):
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and math.isfinite(value))


class _Audit:
    def __init__(self, request):
        self.request = request
        self.mode = request.get('mode', 'integrated')
        self.source_map = {}
        self.used = set()
        self.reasons = []
        self.tasks = []
        self.assumptions = []
        self.hard_failures = []
        self.trace = []
        sources = request.get('sources', [])
        if isinstance(sources, dict):
            sources = [dict(item, id=sid) for sid, item in sources.items()
                       if _text(sid) and isinstance(item, dict) and item.get('id', sid) == sid]
        if not isinstance(sources, list):
            sources = []
        duplicates = set()
        for source in sources:
            if not isinstance(source, dict) or not _text(source.get('id')):
                continue
            sid = source['id']
            if sid in self.source_map:
                duplicates.add(sid)
            else:
                self.source_map[sid] = source
        for sid in duplicates:
            del self.source_map[sid]

    def gap(self, path, reason):
        message = f'{path}: {reason}'
        if message not in self.reasons:
            self.reasons.append(message)
        task = {'field': path, 'task': reason}
        if task not in self.tasks:
            self.tasks.append(task)

    def block(self, path, reason):
        message = f'{path}: {reason}'
        if message not in self.hard_failures:
            self.hard_failures.append(message)
        if message not in self.reasons:
            self.reasons.append(message)

    def mode_allowed(self, node, path):
        modes = node.get('modes')
        if modes is None:
            return True
        if (not isinstance(modes, list) or not modes or
                any(not isinstance(mode, str) or mode not in MODES for mode in modes)):
            self.gap(path + '.modes', 'Provide a nonempty list of valid evidence modes.')
            return False
        if not applies(node, self.mode):
            self.gap(path + '.modes', f'Provide evidence admitted in mode {self.mode}.')
            return False
        return True

    def evidence(self, node, path, fallback=None):
        if not isinstance(node, dict):
            self.gap(path, 'Provide an object with readable source_ids.')
            return False
        valid = self.mode_allowed(node, path)
        ids = node.get('source_ids', fallback)
        if not isinstance(ids, list) or not ids or any(not _text(sid) for sid in ids):
            self.gap(path + '.source_ids', 'Provide nonempty source IDs bound to this claim.')
            return False
        for sid in ids:
            source = self.source_map.get(sid)
            if not source or not isinstance(source.get('access'), str) or source['access'] not in READABLE:
                self.gap(path + '.source_ids', f'Read or replace unavailable/ambiguous source {sid}.')
                valid = False
            elif self.mode_allowed(source, 'sources.' + sid):
                self.used.add(sid)
            else:
                valid = False
        return valid

    def level(self, node, path, fallback=None):
        if not isinstance(node, dict):
            self.gap(path, 'Provide a sourced level; do not substitute infinity, zero, caster AP, or area/count.')
            return None
        valid = self.evidence(node, path, fallback)
        if not all(_text(node.get(key)) for key in ('system', 'ruleset', 'label')):
            self.gap(path, 'Name the tier system, ruleset, and level label.')
            valid = False
        if node.get('axis') != AXIS:
            self.gap(path + '.axis', 'Use affected_entity_tier; area/count and caster AP are separate dimensions.')
            valid = False
        if 'rank' in node and not _number(node['rank']):
            self.gap(path + '.rank', 'Use a finite numeric rank, excluding booleans, or a sourced explicit partial-order comparison.')
            valid = False
        return node if valid else None

    def limit(self, name):
        node = self.request.get(name)
        if not isinstance(node, dict):
            self.gap(name, 'Provide the ability limit or the achieved strongest-character ceiling with evidence.')
            return None
        valid = self.evidence(node, name)
        if name == 'observed_limit':
            if node.get('basis') not in ('demonstrated', 'supported_scaling'):
                self.gap(name + '.basis', 'Use demonstrated or supported_scaling with the actual ability evidence.')
                valid = False
            if not _text(node.get('statement')):
                self.gap(name + '.statement', 'Record what this ability has demonstrated or has sourced scaling to affect.')
                valid = False
            if node.get('ability_id', self.request.get('ability_id')) != self.request.get('ability_id'):
                self.gap(name + '.ability_id', 'Bind the limit to the requested ability rather than another ability or caster AP.')
                valid = False
        else:
            if node.get('kind') != 'strongest_character':
                self.gap(name + '.kind', 'Use strongest_character; cosmology_structure is not a character ceiling.')
                valid = False
            if not _text(node.get('character_id')):
                self.gap(name + '.character_id', 'Identify the strongest character whose achieved level sets this ceiling.')
                valid = False
            attainment = node.get('attainment')
            if not isinstance(attainment, dict):
                self.gap(name + '.attainment', 'Provide achieved-level evidence for the identified strongest character.')
                valid = False
            else:
                attained_sources = self.evidence(attainment, name + '.attainment')
                if attainment.get('kind') != 'achieved' or not _text(attainment.get('statement')):
                    self.gap(name + '.attainment', 'Use kind=achieved and describe what the strongest character actually reached.')
                    valid = False
                valid = valid and attained_sources
        tier = self.level(node.get('level'), name + '.level', node.get('source_ids'))
        return tier if valid and tier is not None else None

    def comparison(self, target, ceiling, name):
        record = {'left': 'target_level', 'right': name, 'result': None, 'method': None,
                  'target_level': copy.deepcopy(self.request.get('target_level')),
                  'ceiling_level': copy.deepcopy((self.request.get(name) or {}).get('level'))
                  if isinstance(self.request.get(name), dict) else None,
                  'source_ids': []}
        self.trace.append(record)
        if target is None or ceiling is None:
            return None
        for key in ('system', 'ruleset', 'axis'):
            if target[key] != ceiling[key]:
                self.gap(name + '.comparison', f'Provide a comparison within the same named system/ruleset/axis; {key} differs.')
                return None
        ids = list(target.get('source_ids', []))
        ids += ceiling.get('source_ids', (self.request.get(name) or {}).get('source_ids', []))
        record['source_ids'] = sorted(set(ids))
        rank_result = None
        if 'rank' in target and 'rank' in ceiling:
            rank_result = target['rank'] <= ceiling['rank']
            record.update(method='sourced_rank', result=rank_result,
                          target_rank=target['rank'], ceiling_rank=ceiling['rank'])
        explicit_results = []
        comparisons = self.request.get('explicit_comparisons', [])
        if not isinstance(comparisons, list):
            self.gap('explicit_comparisons', 'Provide a list of sourced local partial-order comparisons.')
            comparisons = []
        for index, item in enumerate(comparisons):
            if not isinstance(item, dict) or item.get('left') != 'target_level' or item.get('right') != name:
                continue
            path = f'explicit_comparisons[{index}]'
            valid = self.evidence(item, path)
            if item.get('relation') not in ('le', 'gt') or not _text(item.get('explanation')):
                self.gap(path, 'Use relation le/gt and explain the sourced comparison; no total ordering is inferred.')
                valid = False
            if valid:
                explicit_results.append(item['relation'] == 'le')
                record['source_ids'] = sorted(set(record['source_ids'] + item['source_ids']))
        results = ([rank_result] if rank_result is not None else []) + explicit_results
        if False in results:
            # A sourced known exceedance cannot be escaped by a contradictory assumption or relation.
            record['result'] = False
            if rank_result is None:
                record['method'] = 'explicit_comparison'
            if True in results:
                self.reasons.append(name + '.comparison: Conflicting comparisons include a known exceedance; do not assume it away.')
            self.block(name, 'The target exceeds this supported ceiling; highest mode and assumptions cannot override it.')
            return False
        if rank_result is not None:
            return rank_result
        if explicit_results:
            record.update(method='explicit_comparison', result=True)
            return True
        self.gap(name + '.comparison', 'Supply sourced comparable ranks or a sourced explicit comparison; no total order is invented.')
        return None

    def mechanisms(self):
        checks = self.request.get('checks')
        if not isinstance(checks, dict):
            checks = {}
        for name in CHECKS:
            path = 'checks.' + name
            node = checks.get(name)
            if not isinstance(node, dict):
                self.gap(path, 'Record this separate object/mechanism/activation/resistance check as pass/fail/unknown.')
                continue
            if not _text(node.get('explanation')):
                self.gap(path + '.explanation', 'Explain the separate premise and its scope.')
            state = node.get('state')
            if state not in ('pass', 'fail', 'unknown'):
                self.gap(path + '.state', 'Use exactly pass, fail, or unknown; missing resistance is not a pass.')
                continue
            if state == 'unknown':
                # This is a stated hypothetical premise, not a newly sourced fact.
                assumption = node.get('assumption')
                if _text(assumption) and self.mode_allowed(node, path):
                    self.assumptions.append(assumption)
                    self.reasons.append(path + ': Unknown premise is explicit and conditional, not established.')
                else:
                    self.gap(path, 'Research the unknown premise; missing resistance records do not establish absent resistance.')
                continue
            if not self.evidence(node, path):
                continue
            if state == 'fail':
                self.block(path, 'A sourced known incompatibility, failed activation, or resisting mechanism blocks this use.')
        scope = self.request.get('effect_scope')
        if not isinstance(scope, dict):
            self.gap('effect_scope', 'Describe the affected scope and resistance interaction independently of the tier comparison.')
            return
        self.evidence(scope, 'effect_scope')
        for field in ('description', 'resistance_interaction'):
            if not _text(scope.get(field)):
                self.gap('effect_scope.' + field, 'Provide the independent scope/resistance statement; a tier match alone proves no success.')


def run(request) -> dict:
    """Return a packet audit; ``None`` means unknown, never infinity or zero."""
    snapshot = copy.deepcopy(request)
    if not isinstance(request, dict):
        request = {}
    audit = _Audit(request)
    if not isinstance(audit.mode, str) or audit.mode not in MODES:
        audit.gap('mode', 'Use integrated (or explicit legacy replay); no lens overrides a known ceiling.')
    if not _text(request.get('ability_id')):
        audit.gap('ability_id', 'Identify the exact ability whose own supported effect ceiling is being tested.')
    assumptions = request.get('assumptions', [])
    if not isinstance(assumptions, list) or any(not _text(item) for item in assumptions):
        audit.gap('assumptions', 'Provide explicit nonempty assumption strings.')
    else:
        audit.assumptions.extend(assumptions)
    observed = audit.limit('observed_limit')
    world = audit.limit('world_ceiling')
    target = audit.level(request.get('target_level'), 'target_level')
    within_observed = audit.comparison(target, observed, 'observed_limit')
    within_world = audit.comparison(target, world, 'world_ceiling')
    audit.mechanisms()
    status = ('blocked' if audit.hard_failures else 'undetermined' if audit.tasks
              else 'conditional' if audit.assumptions else 'supported_by_packet')
    if status == 'supported_by_packet':
        audit.reasons.append('The target is within both sourced packet ceilings and every separate mechanism premise passes in this packet; success is not guaranteed.')
    used = sorted(audit.used)
    return {
        'status': status, 'within_observed_limit': within_observed,
        'within_world_ceiling': within_world,
        'assumptions': list(dict.fromkeys(audit.assumptions)), 'reasons': audit.reasons,
        'source_ids': used, 'research_tasks': audit.tasks, 'policy_id': POLICY_ID,
        'policy_identity': 'user_confirmed_policy', 'mode': audit.mode, **mode_metadata(audit.mode),
        'ability_id': request.get('ability_id'), 'validation_scope': VALIDATION_SCOPE,
        'source_access_checked': True, 'original_source_verified': False,
        'input_declares_primary_verified': bool(used) and all(
            audit.source_map[sid].get('access') == 'verified' and
            audit.source_map[sid].get('origin') == 'primary' for sid in used),
        'request_snapshot': snapshot, 'comparison_trace': audit.trace,
    }
