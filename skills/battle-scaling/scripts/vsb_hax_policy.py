"""Audit a sourced VSB hax packet; never inherit a Wangba world-tier ceiling.

Input is a host-written claim packet, not an already adjudicated result. Required:
``ability_id``, ``effect_evidence``, ``target``, ``checks`` and ``effect_scope``.
The five checks are object, compatibility, activation, resistance and no_limits.
Each uses state=pass/fail/unknown, an explanation and bound source_ids. Only an
explicit assumption attached to an unknown premise makes that premise conditional.
The host must still read sources and assess semantic entailment.
"""
from __future__ import annotations

import copy

POLICY_ID = 'vsb_hax_mechanism_20261021'
POLICY_REVISIONS = {'Hax': 9692470, 'Resistance': 9313371,
                    'Fallacies': 9363140, 'Standard_Battle_Assumptions': 9377396}
from rating_modes import MODES, applies, metadata as mode_metadata
CHECKS = ('object', 'compatibility', 'activation', 'resistance', 'no_limits')
READABLE = {'verified', 'provided', 'read', 'verified_via_host_browser'}
BASES = {'demonstrated', 'supported_mechanism', 'supported_scaling'}
VALIDATION_SCOPE = (
    'Audits source-access metadata, required mechanism premises and explicit assumptions in this '
    'packet; does not independently read original works, authenticate host claims, establish '
    'semantic entailment, infer resistance from AP, certify a community-approved profile, '
    'or prove an effect succeeds or a character wins. No strongest-character world ceiling is applied.'
)
_RESULT_FIELDS = {
    'status', 'policy_id', 'policy_identity', 'validation_scope', 'research_tasks',
    'source_access_checked', 'original_source_verified', 'request_snapshot',
    'within_observed_limit', 'within_world_ceiling', 'comparison_trace',
    'effective_request_sha256', 'input_declares_primary_verified',
}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


class _Audit:
    def __init__(self, request):
        self.request = request
        self.mode = request.get('mode', 'integrated')
        self.sources = {}
        self.used = set()
        self.reasons = []
        self.tasks = []
        self.assumptions = []
        self.failures = []
        self.trace = []
        sources = request.get('sources', [])
        if isinstance(sources, dict):
            sources = [dict(item, id=sid) for sid, item in sources.items()
                       if _text(sid) and isinstance(item, dict) and item.get('id', sid) == sid]
        if not isinstance(sources, list):
            self.gap('sources', 'Provide a list or keyed map of actual source metadata.')
            sources = []
        duplicates = set()
        for item in sources:
            if not isinstance(item, dict) or not _text(item.get('id')):
                self.gap('sources', 'Each source needs a unique nonempty string ID.')
                continue
            sid = item['id']
            if sid in self.sources:
                duplicates.add(sid)
            else:
                self.sources[sid] = item
        for sid in duplicates:
            del self.sources[sid]
            self.gap('sources.' + sid, 'Duplicate IDs make provenance ambiguous; use unique IDs.')

    def gap(self, path, reason):
        message = path + ': ' + reason
        if message not in self.reasons:
            self.reasons.append(message)
        task = {'field': path, 'task': reason}
        if task not in self.tasks:
            self.tasks.append(task)

    def block(self, path, reason):
        message = path + ': ' + reason
        if message not in self.reasons:
            self.reasons.append(message)
        if message not in self.failures:
            self.failures.append(message)

    def modes(self, node, path):
        selected = node.get('modes')
        if selected is None:
            return True
        if (not isinstance(selected, list) or not selected or
                any(not isinstance(item, str) or item not in MODES for item in selected)):
            self.gap(path + '.modes', 'Provide a nonempty list selecting integrated or explicit legacy lenses.')
            return False
        if not applies(node, self.mode):
            self.gap(path + '.modes', 'This evidence is not admitted in the selected evidence mode.')
            return False
        return True

    def evidence(self, node, path):
        if not isinstance(node, dict):
            self.gap(path, 'Provide an object with source_ids bound to this claim.')
            return False
        valid = self.modes(node, path)
        source_ids = node.get('source_ids')
        if (not isinstance(source_ids, list) or not source_ids or
                any(not _text(sid) for sid in source_ids)):
            self.gap(path + '.source_ids', 'Bind nonempty readable source IDs to this exact claim.')
            return False
        for sid in source_ids:
            source = self.sources.get(sid)
            if (source is None or not isinstance(source.get('access'), str) or
                    source.get('access') not in READABLE):
                self.gap(path + '.source_ids', 'Read or replace unavailable, index-only or ambiguous source ' + sid + '.')
                valid = False
            elif self.modes(source, 'sources.' + sid):
                self.used.add(sid)
            else:
                valid = False
        return valid

    def required_text(self, node, name, path):
        if not isinstance(node, dict) or not _text(node.get(name)):
            self.gap(path + '.' + name, 'Provide a specific, independently explained statement.')
            return False
        return True

    def main_evidence(self):
        node = self.request.get('effect_evidence')
        self.evidence(node, 'effect_evidence')
        if isinstance(node, dict):
            if node.get('ability_id', self.request.get('ability_id')) != self.request.get('ability_id'):
                self.gap('effect_evidence.ability_id', 'Bind this evidence to the ability under review.')
            if not isinstance(node.get('basis'), str) or node.get('basis') not in BASES:
                self.gap('effect_evidence.basis', 'Use demonstrated, supported_mechanism or supported_scaling.')
        for name in ('statement', 'mechanism'):
            self.required_text(node, name, 'effect_evidence')
        target = self.request.get('target')
        self.evidence(target, 'target')
        self.required_text(target, 'description', 'target')
        scope = self.request.get('effect_scope')
        self.evidence(scope, 'effect_scope')
        for name in ('description', 'range_interaction', 'resistance_interaction'):
            self.required_text(scope, name, 'effect_scope')

    def check(self, name, node):
        path = 'checks.' + name
        record = {'check': name, 'state': 'unknown', 'accepted': False, 'source_ids': []}
        self.trace.append(record)
        if not isinstance(node, dict):
            self.gap(path, 'Supply a separate pass/fail/unknown check; no premise is inferred from tier.')
            return
        if _RESULT_FIELDS.intersection(node):
            self.gap(path, 'Use raw premise state and evidence, not a precomputed policy result.')
            return
        explained = self.required_text(node, 'explanation', path)
        state = node.get('state')
        if state not in ('pass', 'fail', 'unknown'):
            self.gap(path + '.state', 'Use exactly pass, fail or unknown.')
            return
        record['state'] = state
        if state == 'unknown':
            assumption = node.get('assumption')
            if explained and _text(assumption) and self.modes(node, path):
                self.assumptions.append(assumption)
                self.reasons.append(path + ': Explicit hypothetical premise; not an established fact.')
                record['conditional'] = True
            else:
                self.gap(path, 'Research the unknown premise or attach a specific local assumption.')
            return
        sourced = self.evidence(node, path)
        record['source_ids'] = list(dict.fromkeys(node.get('source_ids', []))) if sourced else []
        record['accepted'] = sourced and explained
        # A sourced counterexample cannot be erased by an assumption or a selected evidence mode.
        if state == 'fail' and sourced:
            self.block(path, 'A sourced known failure or incompatibility blocks this use; assumptions do not override it.')
        elif state == 'pass' and _text(node.get('assumption')):
            self.assumptions.append(node['assumption'])
            self.reasons.append(path + ': Its extra assumption keeps this premise conditional.')


def run(request) -> dict:
    """Return recomputed supported/conditional/blocked/undetermined packet status.

    VSB effect potency, range and resistance depend on the documented mechanism.
    Caster AP, target AP, and a verse's strongest character are never numeric caps
    in this module. A higher-dimensional or qualitative target is not automatically
    affectable: the object, range and resistance checks must still establish it.
    """
    snapshot = copy.deepcopy(request)
    if not isinstance(request, dict):
        request = {}
    audit = _Audit(request)
    if _RESULT_FIELDS.intersection(request):
        audit.gap('request', 'Provide raw premises, not an already adjudicated result or forged audit flags.')
    if not isinstance(audit.mode, str) or audit.mode not in MODES:
        audit.gap('mode', 'Use integrated (or explicit legacy replay); none overrides a known failure.')
    if not _text(request.get('ability_id')):
        audit.gap('ability_id', 'Identify the exact ability and configuration.')
    assumptions = request.get('assumptions', [])
    if not isinstance(assumptions, list) or any(not _text(item) for item in assumptions):
        audit.gap('assumptions', 'Use a list of explicit nonempty assumption strings.')
    else:
        audit.assumptions.extend(assumptions)
    audit.main_evidence()
    checks = request.get('checks')
    if not isinstance(checks, dict):
        checks = {}
    for name in CHECKS:
        audit.check(name, checks.get(name))
    status = ('blocked' if audit.failures else 'undetermined' if audit.tasks
              else 'conditional' if audit.assumptions else 'supported_by_packet')
    if status == 'supported_by_packet':
        audit.reasons.append('All required mechanism premises are supported by the supplied readable packet; effect success is not guaranteed.')
    used = sorted(audit.used)
    return {
        'status': status, 'policy_id': POLICY_ID, 'policy_identity': 'vsb_mechanism_policy',
        'standard': 'vsb', 'mode': audit.mode, **mode_metadata(audit.mode), 'ability_id': request.get('ability_id'),
        'world_ceiling_applied': False,
        'assumptions': list(dict.fromkeys(audit.assumptions)), 'reasons': audit.reasons,
        'source_ids': used, 'research_tasks': audit.tasks, 'mechanism_trace': audit.trace,
        'policy_revisions': copy.deepcopy(POLICY_REVISIONS),
        'validation_scope': VALIDATION_SCOPE, 'source_access_checked': True,
        'original_source_verified': False,
        'input_declares_primary_verified': bool(used) and all(
            audit.sources[sid].get('access') == 'verified' and
            audit.sources[sid].get('origin') == 'primary' for sid in used),
        'request_snapshot': snapshot,
    }
