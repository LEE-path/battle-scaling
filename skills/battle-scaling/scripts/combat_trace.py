"""Execute an explicitly authored hypothetical state trace, not combat physics.

The host supplies actions, mechanism judgments, evidence references and branches.
This module checks those gates and applies their declared finite state effects.
It never turns a trace into a feat, estimates hit chances, or invents bodily HP.
"""
from __future__ import annotations

import copy
import math
from rating_modes import metadata as mode_metadata
from collections import defaultdict


STATES = {'active', 'incapacitated', 'dead', 'sealed', 'withdrawn', 'unknown'}
ACCESS = {'provided', 'verified', 'indexed', 'read', 'verified_via_host_browser'}
EFFECTS = {'damage', 'heal', 'state', 'resource', 'ongoing', 'revive', 'injury'}


def _number(value, name, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or value < 0 or (positive and value == 0)):
        raise ValueError(name + ' must be a finite nonnegative number' + (' > 0' if positive else ''))
    return value


def _integer(value, name, minimum=0, maximum=1000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer in [{minimum}, {maximum}]')
    return value


def _inherit_hax(parent, child, *, owner=None, target=None, depth=0):
    """Carry admission dependencies through declared effects, never infer tiers."""
    if not isinstance(child, dict) or depth > 4:
        raise ValueError('effect nesting is invalid or excessive')
    result = copy.deepcopy(child)
    parent = parent or {}
    inherited, local = parent.get('hax_requirements', []), result.get('hax_requirements', [])
    if not isinstance(inherited, list) or not isinstance(local, list):
        raise ValueError('hax_requirements must be a list')
    if inherited or local:
        if any(not isinstance(rid, str) or not rid for rid in inherited + local):
            raise ValueError('hax_requirements must contain nonempty check IDs')
        result['hax_requirements'] = list(dict.fromkeys(inherited + local))
    if parent.get('is_hax') is True:
        result['is_hax'] = True
    effect_target = result.get('target', target)
    effect_owner = result.get('ability_owner', parent.get('ability_owner', owner))
    if effect_owner is not None:
        result['ability_owner'] = effect_owner
    if result.get('affected_target') is None and effect_target is not None:
        result['affected_target'] = effect_target
    if result.get('type') == 'ongoing':
        result['tick'] = _inherit_hax(result, result.get('tick'), owner=effect_owner,
                                      target=effect_target, depth=depth + 1)
        result['on_expire'] = [_inherit_hax(result, expiry, owner=effect_owner,
                              target=effect_target, depth=depth + 1)
                              for expiry in result.get('on_expire', [])]
    return result


class _Trace:
    def __init__(self, request):
        if not isinstance(request, dict):
            raise ValueError('request must be an object')
        self.request = copy.deepcopy(request)
        from standards import normalize
        self.standard=normalize(request.get('standard','wangba'))
        self.mode = request.get('mode', 'integrated')
        if self.mode not in ('integrated', 'normal', 'highest', 'lowball'):
            raise ValueError('mode is an evidence mode, not a presentation selector')
        self.max_steps = _integer(request.get('max_steps', 100), 'max_steps', 1)
        self.needs, self.assumptions, self.pending, self.trace = [], [], [], []
        self.actors, self.specs, self.remaining, self.unresolved_recovery = {}, {}, {}, set()
        sources = request.get('sources', [])
        if isinstance(sources, dict):
            sources = list(sources.values())
        if not isinstance(sources, list) or any(not isinstance(s, dict) or not s.get('id') for s in sources):
            raise ValueError('sources must contain source objects with IDs')
        self.sources = {s['id']: s for s in sources}
        if len(self.sources) != len(sources):
            raise ValueError('source IDs must be unique')
        if 'hax_results' in request:
            raise ValueError('hax_results is computed output; submit hax_checks requests')
        from hax_gate import build_checks, review
        self.hax_reviews = build_checks(request.get('hax_checks', []), sources, self.mode,standard=self.standard)
        self._review_hax = review
        self.hax_admissions = []
        self.hax_review_coverage = {'declared_locations': [], 'unreviewed_locations': [],
            'scope': 'Only explicitly declared hax dependencies are reviewed; unmarked legacy judgments remain unreviewed. '
                     'Checks validate the supplied tier/mechanism packet, not source entailment or all abilities.'}
        actors = request.get('actors', [])
        if not isinstance(actors, list) or len(actors) < 2:
            raise ValueError('at least two actors are required')
        for spec in actors:
            who = spec.get('id')
            if not isinstance(who, str) or not who or who in self.actors:
                raise ValueError('actors need unique nonempty IDs')
            initial = spec.get('initial', {})
            state = initial.get('state', 'unknown')
            if state not in STATES:
                raise ValueError('unknown initial state for ' + who)
            self.actors[who] = {'state': state, 'resources': {}, 'effects': [], 'injuries': []}
            self.specs[who] = spec
            if state == 'unknown':
                self.need(who + '.initial.state', 'initial ability to act is unknown')
            self.add_assumptions(spec.get('assumptions', []))
            if 'hp' in initial or 'max_hp' in initial:
                model = spec.get('hp_model', {})
                if model.get('kind') != 'game':
                    raise ValueError('HP requires an explicit sourced game hp_model; no invented body HP')
                hp = _number(initial.get('hp'), who + '.initial.hp')
                maximum = _number(initial.get('max_hp', hp), who + '.initial.max_hp', positive=True)
                if hp > maximum or model.get('zero_state') not in STATES - {'active', 'unknown'}:
                    raise ValueError('invalid game HP maximum or zero_state')
                if self.check({'status': 'supported', **model}, who + '.hp_model', owner=who, target=who) == 'pass':
                    self.actors[who].update(hp=hp, max_hp=maximum)
                    if hp == 0:
                        self.actors[who]['state'] = model['zero_state']
            resources = initial.get('resources', {})
            if not isinstance(resources, dict):
                raise ValueError('initial resources must be an object')
            for key, amount in resources.items():
                _number(amount, who + '.resources.' + key)
            if resources and self.check({'status': 'supported',
                                        'evidence_ids': spec.get('resource_evidence_ids', [])},
                                       who + '.resources', owner=who, target=who) == 'pass':
                self.actors[who]['resources'] = dict(resources)
            for recovery in spec.get('recoveries', []):
                rid = recovery.get('id')
                if not rid or (who, rid) in self.remaining:
                    raise ValueError('recoveries need unique per-actor IDs')
                self.remaining[(who, rid)] = _integer(recovery.get('uses', 1), 'recovery.uses')
                _integer(recovery.get('delay', 0), 'recovery.delay')
                if not recovery.get('trigger_states') or any(s not in STATES for s in recovery['trigger_states']):
                    raise ValueError('recovery requires valid trigger_states')
        self.teams = request.get('teams', {})
        if not isinstance(self.teams, dict) or any(a not in self.actors or not isinstance(t, str) or not t
                                                   for a, t in self.teams.items()):
            raise ValueError('teams must map known actor IDs to nonempty team IDs')
        self.teams = {a: self.teams.get(a, a) for a in self.actors}
        self.steps = request.get('steps', [])
        if not isinstance(self.steps, list) or len(self.steps) > 1000:
            raise ValueError('steps must be a list of at most 1000 simultaneous groups')
        self.victory = request.get('victory', {})
        defeated = self.victory.get('defeated_states', [])
        if not isinstance(defeated, list) or any(s not in STATES - {'active', 'unknown'} for s in defeated):
            raise ValueError('victory.defeated_states contains invalid states')

    def add_assumptions(self, assumptions):
        if not isinstance(assumptions, list) or any(not isinstance(s, str) or not s.strip() for s in assumptions):
            raise ValueError('assumptions must be a list of nonempty strings')
        for item in assumptions:
            if item not in self.assumptions:
                self.assumptions.append(item)

    def need(self, where, reason):
        item = {'where': where, 'reason': reason}
        if item not in self.needs:
            self.needs.append(item)

    def hax_check(self, judgment, where, *, owner=None, target=None):
        if not isinstance(judgment, dict):
            return 'pass'  # Ordinary missing-judgment handling remains in check().
        admission = self._review_hax(judgment, self.hax_reviews, owner=owner, target=target)
        self.hax_admissions.append({'where': where, 'owner': owner, 'target': target,
                                    **copy.deepcopy(admission)})
        declared = admission['status'] != 'not_declared'
        coverage = self.hax_review_coverage['declared_locations' if declared else 'unreviewed_locations']
        if where not in coverage:
            coverage.append(where)
        if admission['status'] in ('not_declared', 'supported_by_packet'):
            return 'pass'
        if admission['status'] == 'conditional' and admission.get('assumptions'):
            self.add_assumptions(admission['assumptions'])
            return 'pass'
        status = admission['status']
        if status == 'blocked':
            # An invalid binding proves nothing about the actual use. A correctly
            # bound known failure rejects this use without poisoning an independent
            # sourced victory with an artificial information gap.
            mismatch = any(
                expected is not None and self.hax_reviews.get(rid, {}).get('scope', {}).get(key) != expected
                for rid in admission.get('check_ids', [])
                for expected, key in ((owner, 'actor_id'), (target, 'target_id')))
            if not mismatch:
                return 'hax_blocked'
        self.need(where, 'hax ' + status + ': ' + '; '.join(map(str, admission.get('reasons', []))))
        return 'hax_undetermined' if status == 'blocked' else 'hax_' + status

    def check(self, judgment, where, *, owner=None, target=None):
        if not isinstance(judgment, dict):
            self.need(where, 'missing or unknown host mechanism judgment')
            return 'unknown'
        hax = self.hax_check(judgment, where, owner=owner, target=target)
        if hax != 'pass':
            return hax
        status = judgment.get('status', 'unknown')
        self.add_assumptions(judgment.get('assumptions', []))
        if status == 'failed':
            return 'failed'  # A stated failure is never repaired by permissive assumptions.
        refs = judgment.get('evidence_ids', [])
        if not isinstance(refs, list):
            raise ValueError(where + '.evidence_ids must be a list')
        unusable = [s for s in refs if s not in self.sources or self.sources[s].get('access') not in ACCESS]
        if unusable:
            self.need(where, 'unusable evidence: ' + ', '.join(map(str, unusable)))
            return 'unknown'
        if status == 'supported' and refs:
            return 'pass'
        if status == 'assumed' and judgment.get('assumptions'):
            return 'pass'
        self.need(where, 'needs usable sources or an explicit nonempty assumed branch')
        return 'unknown'

    def target(self, effect, default=None):
        who = effect.get('target', default)
        if who not in self.actors:
            raise ValueError('unknown effect target: ' + str(who))
        return who

    def validate_effect(self, effect, default=None, depth=0):
        if depth > 4 or not isinstance(effect, dict):
            raise ValueError('effect nesting is invalid or excessive')
        kind = effect.get('type')
        if kind not in EFFECTS:
            raise ValueError('unsupported effect type: ' + str(kind))
        self.target(effect, default)
        _integer(effect.get('delay', 0), 'effect.delay')
        if kind in ('damage', 'heal'):
            _number(effect.get('amount'), 'effect.amount')
        elif kind == 'state':
            if effect.get('state') not in STATES:
                raise ValueError('invalid effect state')
        elif kind == 'injury':
            if any(not isinstance(effect.get(k), str) or not effect[k].strip()
                   for k in ('part', 'description')):
                raise ValueError('injury requires nonempty part and description')
            limits = effect.get('limitations', [])
            if not isinstance(limits, list) or any(not isinstance(s, str) or not s.strip() for s in limits):
                raise ValueError('injury limitations must be a list of nonempty strings')
        elif kind == 'resource':
            if not isinstance(effect.get('resource'), str) or not effect['resource']:
                raise ValueError('resource effect requires a resource name')
            delta = effect.get('delta')
            if isinstance(delta, bool) or not isinstance(delta, (int, float)) or not math.isfinite(delta):
                raise ValueError('resource.delta must be finite')
        elif kind == 'ongoing':
            _integer(effect.get('duration'), 'effect.duration', 1)
            if not effect.get('id'):
                raise ValueError('ongoing effects require an ID')
            self.validate_effect(effect.get('tick'), effect.get('target', default), depth + 1)
            for expiry in effect.get('on_expire', []):
                self.validate_effect(expiry, effect.get('target', default), depth + 1)
        elif kind == 'revive' and 'hp' in effect:
            _number(effect['hp'], 'revive.hp', positive=True)
        if kind == 'revive':
            if effect.get('restore_state', 'active') not in STATES:
                raise ValueError('invalid revival restore_state')
            if any(s not in STATES for s in effect.get('from_states', ['incapacitated', 'dead'])):
                raise ValueError('invalid revival from_states')

    def apply_batch(self, effects, number, changes):
        hp_delta, resource_delta, states = defaultdict(float), defaultdict(float), defaultdict(set)
        revivals = []
        for declared in effects:
            effect = _inherit_hax(None, declared)
            self.validate_effect(effect)
            who = effect['target']; kind = effect['type']
            if self.check(effect, f'step[{number}].effect.{kind}.{who}',
                          owner=effect.get('ability_owner'), target=who) != 'pass':
                continue
            delay = effect.get('delay', 0)
            if delay:
                scheduled = copy.deepcopy(effect); scheduled.pop('delay', None)
                self.pending.append({'due_step': number + delay, 'effect': scheduled})
                changes.append({'target': who, 'type': 'scheduled', 'due_step': number + delay,
                                'effect': copy.deepcopy(scheduled)})
                continue
            state = self.actors[who]
            if kind in ('damage', 'heal'):
                if 'hp' not in state:
                    self.need(f'{who}.{kind}', 'no usable sourced game HP model; no bodily HP may be inferred')
                    continue
                hp_delta[who] += effect['amount'] * (-1 if kind == 'damage' else 1)
            elif kind == 'resource':
                resource_delta[(who, effect['resource'])] += effect['delta']
            elif kind == 'state':
                states[who].add(effect['state'])
            elif kind == 'injury':
                state['injuries'].append({k: copy.deepcopy(effect.get(k, default))
                                          for k, default in (('part', ''), ('description', ''),
                                                             ('limitations', []), ('status', 'unknown'),
                                                             ('evidence_ids', []), ('assumptions', []))})
            elif kind == 'ongoing':
                existing = [e for e in state['effects'] if e['id'] == effect['id']]
                if existing:
                    self.need(who + '.effects.' + effect['id'], 'duplicate active effect ID; stacking rule is unspecified')
                    continue
                ongoing = copy.deepcopy(effect)
                ongoing.update(remaining=effect['duration'], applied_step=number, next_tick=number + 1)
                state['effects'].append(ongoing)
            elif kind == 'revive':
                revivals.append(effect)
            changes.append({'target': who, 'type': kind, 'effect': copy.deepcopy(effect)})
        # Damage and healing in a simultaneous group are aggregated before any actor is disabled.
        for who, delta in hp_delta.items():
            state = self.actors[who]
            state['hp'] = min(state['max_hp'], max(0, state['hp'] + delta))
            if state['hp'] == 0 and state['state'] == 'active':
                state['state'] = self.specs[who]['hp_model']['zero_state']
        for (who, key), delta in resource_delta.items():
            state = self.actors[who]
            if key not in state['resources'] or state['resources'][key] + delta < 0:
                self.need(who + '.resources.' + key, 'unknown resource or simultaneous resource overdraft')
                continue
            state['resources'][key] += delta
        for who, values in states.items():
            if len(values) > 1:
                self.need(who + '.state', 'conflicting simultaneous state effects need a priority rule')
            elif 'active' in values and self.actors[who].get('hp', 1) <= 0:
                self.need(who + '.state', 'active at zero HP requires an explicit usable revival')
            else:
                self.actors[who]['state'] = next(iter(values))
        for effect in revivals:
            who = effect['target']; state = self.actors[who]
            allowed = effect.get('from_states', ['incapacitated', 'dead'])
            if state['state'] not in allowed:
                continue  # A resurrection does not silently remove an unrelated seal or exit.
            if 'hp' in state:
                if 'hp' not in effect:
                    self.need(who + '.revive.hp', 'revival HP amount was not supplied')
                    continue
                state['hp'] = min(state['max_hp'], effect['hp'])
            state['state'] = effect.get('restore_state', 'active')
        for who, spec in self.specs.items():
            for resource, zero_state in spec.get('resource_exhaustion', {}).items():
                if zero_state not in STATES:
                    raise ValueError('invalid resource_exhaustion state')
                if self.actors[who]['resources'].get(resource) == 0:
                    self.actors[who]['state'] = zero_state

    def schedule_recoveries(self, number, changes):
        for who, spec in self.specs.items():
            for recovery in spec.get('recoveries', []):
                rid = recovery['id']
                if (self.remaining[(who, rid)] == 0 or
                        self.actors[who]['state'] not in recovery['trigger_states'] or
                        any(e.get('recovery_id') == [who, rid] for e in self.pending)):
                    continue
                judgment = self.check(recovery, who + '.recovery.' + rid, owner=who, target=who)
                if judgment != 'pass':
                    if judgment not in ('failed', 'hax_blocked'):
                        self.unresolved_recovery.add(who)
                    continue
                self.remaining[(who, rid)] -= 1
                effect = {k: copy.deepcopy(v) for k, v in recovery.items()
                          if k not in ('id', 'trigger_states', 'delay', 'uses')}
                effect.update(type='revive', target=who, from_states=recovery['trigger_states'])
                effect = _inherit_hax(recovery, effect, owner=who, target=who)
                if recovery.get('delay', 0) == 0:
                    self.apply_batch([effect], number, changes)
                else:
                    self.pending.append({'due_step': number + recovery['delay'], 'effect': effect,
                                         'recovery_id': [who, rid]})
                    changes.append({'target': who, 'type': 'recovery_scheduled',
                                    'due_step': number + recovery['delay'], 'recovery_id': rid})

    def advance(self, number, changes):
        due = [entry for entry in self.pending if entry['due_step'] <= number]
        self.pending = [entry for entry in self.pending if entry['due_step'] > number]
        effects = [entry['effect'] for entry in due]
        for who, state in self.actors.items():
            retained = []
            for effect in state['effects']:
                if effect['next_tick'] > number:
                    retained.append(effect); continue
                tick = copy.deepcopy(effect['tick']); tick.setdefault('target', who)
                effects.append(tick)
                effect['remaining'] -= 1
                if effect['remaining']:
                    effect['next_tick'] = number + 1
                    retained.append(effect)
                else:
                    for expiry in effect.get('on_expire', []):
                        item = copy.deepcopy(expiry); item.setdefault('target', who)
                        effects.append(item)
            state['effects'] = retained
        self.apply_batch(effects, number, changes)

    def action(self, action, snapshot, reserved, number):
        if not isinstance(action, dict) or action.get('actor') not in self.actors:
            raise ValueError('action requires a known actor')
        who = action['actor']; default = action.get('target', who)
        if default not in self.actors:
            raise ValueError('unknown action target')
        row = {'actor': who, 'target': default, 'intent': action.get('intent', ''),
               'activation': copy.deepcopy(action.get('activation', {})),
               'hit': copy.deepcopy(action.get('hit', {})),
               'defense': copy.deepcopy(action.get('defense', {})), 'state_changes': [],
               'follow_up': '', 'evidence_ids': [], 'assumptions': [], 'outcome': 'unresolved'}
        for judgment in [action, row['activation'], row['hit'], row['defense'], *action.get('effects', [])]:
            for ref in judgment.get('evidence_ids', []):
                if ref not in row['evidence_ids']:
                    row['evidence_ids'].append(ref)
            for assumption in judgment.get('assumptions', []):
                if assumption not in row['assumptions']:
                    row['assumptions'].append(assumption)
        effects = []
        for effect in action.get('effects', []):
            item = _inherit_hax(action, effect, owner=who, target=default)
            item.setdefault('target', default)
            self.validate_effect(item)
            effects.append(item)
        if snapshot[who]['state'] != 'active':
            row['outcome'] = 'actor_unavailable'; return row, []
        gate = self.hax_check(action, f'step[{number}].{who}.action', owner=who, target=default)
        if gate != 'pass':
            row['outcome'] = 'action_' + gate; return row, []
        for counter in action.get('counterevidence', []):
            verdict = self.check(counter, f'step[{number}].{who}.counterevidence',
                                 owner=counter.get('ability_owner', default),
                                 target=counter.get('affected_target', who))
            if verdict == 'pass':
                row['outcome'] = 'counterevidence'; return row, []
            if verdict not in ('failed', 'hax_blocked'):
                row['outcome'] = 'counterevidence_' + ('unresolved' if verdict == 'unknown' else verdict)
                return row, []
        gate = self.check(action.get('activation'), f'step[{number}].{who}.activation', owner=who, target=default)
        if gate != 'pass':
            row['outcome'] = 'activation_' + gate; return row, []
        costs = defaultdict(float)
        for cost in action.get('costs', []):
            amount = _number(cost.get('amount'), 'cost.amount')
            if not cost.get('resource') or self.check(cost, f'step[{number}].{who}.cost',
                                                      owner=who, target=who) != 'pass':
                row['outcome'] = 'cost_unresolved'; return row, []
            costs[cost['resource']] += amount
        for key, amount in costs.items():
            available = reserved[who].get(key)
            if available is None or available < amount:
                row['outcome'] = 'resource_exhausted'; return row, []
        for key, amount in costs.items():
            reserved[who][key] -= amount
        gate = self.check(action.get('hit'), f'step[{number}].{who}.hit', owner=who, target=default)
        if gate != 'pass':
            row['outcome'] = 'hit_' + gate; return row, []
        defense_judgment = action.get('defense')
        defense_owner = defense_judgment.get('ability_owner', default) if isinstance(defense_judgment, dict) else default
        defense_target = defense_judgment.get('affected_target', who) if isinstance(defense_judgment, dict) else who
        gate = self.check(defense_judgment, f'step[{number}].{who}.defense',
                          owner=defense_owner, target=defense_target)
        known_failed_defense = (gate == 'hax_blocked' and defense_owner == default and
                                defense_judgment.get('outcome') == 'prevented')
        if gate != 'pass' and not known_failed_defense:
            row['outcome'] = 'defense_' + gate; return row, []
        defense = 'not_prevented' if known_failed_defense else action['defense'].get('outcome', 'unknown')
        if known_failed_defense:
            row['defense']['reviewed_outcome'] = 'not_prevented'
            row['defense']['rejection'] = 'hax_blocked'
        if defense == 'prevented':
            row['outcome'] = 'defended'; return row, []
        if defense != 'not_prevented':
            self.need(f'step[{number}].{who}.defense', 'defense outcome is unknown')
            row['outcome'] = 'defense_unknown'; return row, []
        row['outcome'] = 'effects_submitted'
        return row, effects

    def review_vsb_defeat(self, actors):
        from standards import victory_review
        packets=self.victory.get('vsb_checks',{})
        if not isinstance(packets,dict):
            raise ValueError('victory.vsb_checks must map defeated actor IDs to sourced SBA condition packets')
        valid=True
        expected={'bfr':{'withdrawn','sealed'},'knockout':{'incapacitated'},'incapacitation':{'incapacitated','sealed'},'death':{'dead'}}
        for who in actors:
            packet=packets.get(who)
            review=victory_review(packet,self.sources)
            if review['status'] in ('blocked','undetermined'):
                self.need('victory.vsb_checks.'+who,'; '.join(review['reasons']))
                valid=False
            elif self.actors[who]['state'] not in expected[packet['condition']]:
                self.need('victory.vsb_checks.'+who,'The stated SBA condition does not match the recorded defeated state.')
                valid=False
            elif review['status']=='conditional':
                self.add_assumptions(review['assumptions'])
        return valid

    def terminal(self):
        active = [a for a, state in self.actors.items() if state['state'] == 'active']
        active_teams = {self.teams[a] for a in active}
        inactive = [a for a in self.actors if a not in active]
        recovery_pending = any(entry['effect']['target'] in inactive and
                               (entry['effect']['type'] == 'revive' or
                                (entry['effect']['type'] == 'state' and entry['effect'].get('state') == 'active'))
                               for entry in self.pending)
        result = {'is_terminal': False, 'kind': 'ongoing', 'winner': None,
                  'adjudication': 'undetermined'}
        if recovery_pending:
            result['kind'] = 'recovery_pending'
        elif self.pending or any(state['effects'] for state in self.actors.values()):
            # Already launched attacks and finite expiry windows survive the caster.
            # Resolving them may change a sole survivor into mutual defeat or release a seal.
            result['kind'] = 'effects_pending'
        elif self.unresolved_recovery or self.needs:
            result['kind'] = 'undetermined'
        elif not active and all(s['state'] != 'unknown' for s in self.actors.values()):
            if self.standard=='vsb':
                self.review_vsb_defeat(list(self.actors))
                self.need('victory.timing','Both actors being inactive does not establish which SBA condition was satisfied first; a sourced temporal adjudication is required.')
                result['kind']='undetermined'
                return result
            result.update(is_terminal=True, kind='mutual_defeat')
            if self.victory.get('mutual_outcome'):
                result['adjudication'] = self.victory['mutual_outcome']
        elif len(active_teams) == 1 and inactive:
            defeated = self.victory.get('defeated_states', [])
            surviving_team = next(iter(active_teams))
            opposition = [a for a in self.actors if self.teams[a] != surviving_team]
            if defeated and opposition and all(self.actors[a]['state'] in defeated for a in opposition):
                if self.standard=='vsb':
                    if not self.review_vsb_defeat(opposition):
                        result['kind']='undetermined'
                        return result
                result.update(is_terminal=True, kind='victory', winner=surviving_team, adjudication='specified_conditions')
            else:
                result['kind'] = 'undetermined'
        return result

    def execute(self):
        initial_changes = []
        self.schedule_recoveries(0, initial_changes)
        terminal = self.terminal()
        for number, step in enumerate(self.steps[:self.max_steps], 1):
            if terminal['is_terminal']:
                break
            if not isinstance(step, dict) or not isinstance(step.get('actions', []), list):
                raise ValueError('each step is an object containing an actions list')
            before = copy.deepcopy(self.actors); changes = []
            self.advance(number, changes)
            snapshot = copy.deepcopy(self.actors)
            reserved = {a: dict(state['resources']) for a, state in self.actors.items()}
            actions, effects = [], []
            for action in step.get('actions', []):
                row, declared = self.action(action, snapshot, reserved, number)
                actions.append(row); effects.extend(declared)
            for who in self.actors:
                self.actors[who]['resources'] = reserved[who]
            self.apply_batch(effects, number, changes)
            self.schedule_recoveries(number, changes)
            after = copy.deepcopy(self.actors)
            for row in actions:
                row['state_changes'] = [copy.deepcopy(c) for c in changes if c['target'] in (row['actor'], row['target'])]
                row['state_changes_scope'] = 'simultaneous_group_shared_outcome'
                row['follow_up'] = {'actor_state': after[row['actor']]['state'],
                                    'target_state': after[row['target']]['state'],
                                    'pending_effects': [copy.deepcopy(e) for e in self.pending
                                                       if e['effect']['target'] in (row['actor'], row['target'])]}
            self.trace.append({'step': number, 'id': step.get('id', str(number)),
                               'record_kind': 'hypothetical_process', 'state_before': before,
                               'actions': actions, 'changes': changes, 'state_after': after})
            terminal = self.terminal()
        truncated = len(self.trace) >= self.max_steps and len(self.steps) > len(self.trace) and not terminal['is_terminal']
        if truncated:
            terminal.update(kind='truncated', winner=None, adjudication='undetermined')
        status = 'truncated' if truncated else 'needs_information' if self.needs else 'conditional' if self.assumptions else 'recorded'
        result = {'schema_version': 1, 'mode': self.mode, 'standard':self.standard, 'presentation': 'process', 'status': status,
                  'record_kind': 'hypothetical_process', 'canon_evidence': False,
                  'trace': self.trace, 'initial_changes': initial_changes,
                  'final_state': copy.deepcopy(self.actors), 'pending': copy.deepcopy(self.pending),
                  'terminal': terminal, 'assumptions': self.assumptions, 'needs': self.needs,
                  'hax_reviews': copy.deepcopy(self.hax_reviews),
                  'hax_admissions': copy.deepcopy(self.hax_admissions),
                  'hax_review_coverage': copy.deepcopy(self.hax_review_coverage),
                  'validation_scope': 'source access, explicit host gates and declared finite effects only; '
                                      'not source entailment, hit probability, combat physics or canon verification'}
        if self.request.get('include_narrative'):
            parts = []
            for step in self.trace:
                actions = '; '.join(f"{a['actor']}: {a['intent']} ({a['outcome']})" for a in step['actions']) or 'no authored actions'
                states = ', '.join(f"{a}={s['state']}" + (f"/{s['hp']:g}HP" if 'hp' in s else '')
                                   for a, s in step['state_after'].items())
                parts.append(f"Step {step['id']}: {actions}. Recorded state: {states}.")
            result['narrative'] = ' '.join(parts)
            result['narrative_status'] = 'illustrative_not_canon'
        return result


def run(request: dict) -> dict:
    """Return an auditable hypothetical trace; raises ValueError for invalid structures.

    Unresolved evidence or mechanism gates produce ``needs`` and prevent their
    effects. ``supported`` refers only to the supplied packet, never canon truth.
    See references/combat-process.md for the input contract and time semantics.
    """
    if isinstance(request,dict) and request.get('purpose')=='writing':
        raise ValueError('Use battle.py writing for author-directed fiction; process remains the evidence-constrained PK trace')
    if not isinstance(request, dict):
        raise ValueError('request must be an object')
    from rating_preflight import review as review_ratings, process_subjects
    rating_gate = review_ratings(process_subjects(request), request.get('independent_ratings', []),
                                request.get('sources', []), standard=request.get('standard', 'wangba'),
                                mode=request.get('mode', 'integrated'),
                                **({'rating_status':request['rating_status']} if 'rating_status' in request else {}))
    if rating_gate['status'] != 'ready':
        return {'schema_version':1, 'presentation':'process', 'status':'needs_independent_rating',
                'mode':request.get('mode', 'integrated'), 'standard':request.get('standard', 'wangba'),
                'rating_preflight':rating_gate, 'trace':[], 'needs':rating_gate['needs'],
                'combat_analysis_started':False, 'canon_evidence':False}
    result = _Trace(request).execute()
    result.update(mode_metadata(request.get('mode', 'integrated')))
    result['rating_preflight'] = rating_gate
    return result
