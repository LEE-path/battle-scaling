"""Synthetic hax-gate contract tests; no fictional feats or external model calls."""
import copy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from combat_trace import _Trace, run
from rating_fixtures import rated_call
run = rated_call(run)
from test_combat_trace import actor, attack, fact, request


class HaxCombatTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.build_calls = []
        helper = types.ModuleType('hax_gate')

        def build(entries, sources, mode, standard='wangba'):
            # This helper supplies synthetic legacy checks only. VSB routing is
            # exercised against the real VSB policy in test_standards.py.
            self.assertEqual(standard, 'wangba')
            self.build_calls.append((copy.deepcopy(entries), copy.deepcopy(sources), mode, standard))
            return {entry['id']: {'request': copy.deepcopy(entry['request']),
                    'scope': {key: entry['request'].get(key) for key in ('actor_id', 'target_id')},
                    'status': entry['request'].get('test_status', 'supported_by_packet')}
                    for entry in entries if mode in entry.get('modes', ['normal', 'highest', 'lowball'])}

        def review(item, checks, owner=None, target=None):
            owner = owner if owner is not None else item.get('ability_owner')
            target = target if target is not None else item.get('affected_target')
            ids = item.get('hax_requirements', [])
            result = {'status': 'not_declared', 'reasons': [], 'assumptions': [],
                      'source_ids': [], 'check_ids': list(ids)}
            if ids or item.get('is_hax'):
                result['status'] = 'supported_by_packet' if ids else 'undetermined'
                for rid in ids:
                    output = checks.get(rid)
                    if not output:
                        result.update(status='undetermined', reasons=['missing check'])
                        break
                    scope = output['request']
                    if (owner is not None and scope.get('actor_id') != owner) or (
                            target is not None and scope.get('target_id') != target):
                        result.update(status='undetermined', reasons=['scope mismatch'])
                        break
                    if output['status'] in ('blocked', 'undetermined'):
                        result.update(status=output['status'], reasons=['synthetic gate restriction'])
                        break
                    if output['status'] == 'conditional':
                        result.update(status='conditional', assumptions=['synthetic mechanism premise'])
                result['source_ids'] = ['s-game']
            self.calls.append({'item': copy.deepcopy(item), 'owner': owner, 'target': target,
                               'review': copy.deepcopy(result)})
            return result

        helper.build_checks = build
        helper.review = review
        self.helper_patch = patch.dict(sys.modules, {'hax_gate': helper})
        self.helper_patch.start()
        self.addCleanup(self.helper_patch.stop)

    def checked(self, actions=None, steps=None, status='supported_by_packet', owner='a', target='b'):
        req = request(actions, steps)
        req['hax_checks'] = [{'id': 'ability', 'request': {'actor_id': owner, 'target_id': target,
                              'test_status': status, 'sources': ['untrusted'], 'mode': 'highest'}}]
        return req

    def test_legacy_trace_is_explicitly_unreviewed(self):
        out = run(request([attack(amount=1)]))
        self.assertTrue(out['hax_review_coverage']['unreviewed_locations'])
        self.assertFalse(out['hax_review_coverage']['declared_locations'])
        self.assertEqual(out['hax_reviews'], {})

    def test_precomputed_results_are_rejected(self):
        req = request(); req['hax_results'] = {'ability': {'status': 'supported_by_packet'}}
        with self.assertRaises(ValueError):
            run(req)

    def test_builds_real_checks_with_trace_sources_and_mode(self):
        req = self.checked([attack(amount=1, hax_requirements=['ability'])])
        out = run(req)
        self.assertEqual(self.build_calls[0][1], req['sources'])
        self.assertEqual(self.build_calls[0][2], 'normal')
        self.assertEqual(self.build_calls[0][3], 'wangba')
        self.assertIn('ability', out['hax_reviews'])

    def test_action_has_hax_only_gate_without_requiring_status(self):
        req = self.checked([attack(hax_requirements=['ability'])], status='blocked')
        out = run(req)
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertFalse(out['needs'])
        self.assertIsNone(out['terminal']['winner'])
        self.assertIn('hax', out['trace'][0]['actions'][0]['outcome'])

    def test_is_hax_without_review_is_unresolved(self):
        out = run(request([attack(is_hax=True)]))
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertTrue(out['needs'])

    def test_assumed_cannot_bypass_each_gate(self):
        for gate in ('activation', 'hit', 'defense'):
            with self.subTest(gate=gate):
                judgment = {'status': 'assumed', 'assumptions': ['please allow it'],
                            'hax_requirements': ['ability']}
                if gate == 'defense':
                    judgment.update(outcome='not_prevented', ability_owner='a', affected_target='b')
                out = run(self.checked([attack(**{gate: judgment})], status='blocked'))
                self.assertEqual(out['final_state']['b']['hp'], 10)
                self.assertFalse(out['needs'])
                self.assertIsNone(out['terminal']['winner'])

    def test_conditional_check_carries_its_premise(self):
        out = run(self.checked([attack(amount=1, hax_requirements=['ability'])], status='conditional'))
        self.assertEqual(out['final_state']['b']['hp'], 9)
        self.assertEqual(out['status'], 'conditional')
        self.assertIn('synthetic mechanism premise', out['assumptions'])

    def test_blocked_defense_is_not_recorded_as_successful_defense(self):
        defense = fact(outcome='prevented', hax_requirements=['ability'])
        out = run(self.checked([attack(defense=defense)], status='blocked', owner='b', target='a'))
        self.assertNotEqual(out['trace'][0]['actions'][0]['outcome'], 'defended')
        self.assertFalse(out['needs'])
        self.assertEqual(out['terminal']['winner'], 'a')
        call = next(call for call in self.calls if call['item'].get('outcome') == 'prevented')
        self.assertEqual((call['owner'], call['target']), ('b', 'a'))

    def test_counterevidence_uses_defender_scope_and_cannot_publish_false_protection(self):
        counter = fact(claim='synthetic immunity', hax_requirements=['ability'])
        out = run(self.checked([attack(counterevidence=[counter])], status='blocked', owner='b', target='a'))
        self.assertNotEqual(out['trace'][0]['actions'][0]['outcome'], 'counterevidence')
        self.assertFalse(out['needs'])
        self.assertEqual(out['terminal']['winner'], 'a')
        call = next(call for call in self.calls if call['item'].get('claim') == 'synthetic immunity')
        self.assertEqual((call['owner'], call['target']), ('b', 'a'))

    def test_blocked_effect_cannot_be_assumed(self):
        effect = {'type': 'state', 'target': 'b', 'state': 'sealed', 'status': 'assumed',
                  'assumptions': ['synthetic seal'], 'hax_requirements': ['ability']}
        out = run(self.checked([attack(effects=[effect])], status='blocked'))
        self.assertEqual(out['final_state']['b']['state'], 'active')
        self.assertIsNone(out['terminal']['winner'])

    def test_delayed_effect_keeps_parent_requirements(self):
        action = attack(amount=1, hax_requirements=['ability'])
        action['effects'][0]['delay'] = 1
        out = run(self.checked(steps=[{'actions': [action]}, {'actions': []}]))
        delayed = out['trace'][0]['actions'][0]['follow_up']['pending_effects'][0]['effect']
        self.assertEqual(delayed['hax_requirements'], ['ability'])
        self.assertEqual(out['final_state']['b']['hp'], 9)

    def test_tick_and_expiry_cannot_drop_parent_requirements(self):
        ongoing = fact(type='ongoing', target='b', id='duration', duration=1,
                       tick=fact(type='damage', amount=1, hax_requirements=['child']),
                       on_expire=[fact(type='injury', part='arm', description='synthetic injury')])
        req = self.checked(steps=[{'actions': [attack(hax_requirements=['ability'], effects=[ongoing])]},
                                  {'actions': []}])
        req['hax_checks'].append({'id': 'child', 'request': {'actor_id': 'a', 'target_id': 'b'}})
        out = run(req)
        ticking = [call for call in self.calls if call['item'].get('type') == 'damage']
        expiry = [call for call in self.calls if call['item'].get('description') == 'synthetic injury']
        self.assertTrue(ticking)
        self.assertEqual(set(ticking[-1]['review']['check_ids']), {'ability', 'child'})
        self.assertEqual(expiry[-1]['review']['check_ids'], ['ability'])
        self.assertEqual(out['final_state']['b']['hp'], 9)

    def test_unknown_recovery_is_not_consumed_or_scheduled(self):
        req = self.checked([attack()], status='undetermined', owner='b', target='b')
        req['actors'][1]['recoveries'] = [fact(id='return', trigger_states=['incapacitated'],
                          hp=10, uses=1, delay=1, hax_requirements=['ability'])]
        trace = _Trace(req); out = trace.execute()
        self.assertEqual(trace.remaining[('b', 'return')], 1)
        self.assertEqual(out['pending'], [])
        self.assertEqual(out['terminal']['kind'], 'undetermined')
        self.assertIsNone(out['terminal']['winner'])

    def test_recovery_generated_revive_keeps_requirements(self):
        req = self.checked(steps=[{'actions': [attack()]}, {'actions': []}], owner='b', target='b')
        req['actors'][1]['recoveries'] = [fact(id='return', trigger_states=['incapacitated'],
                          hp=10, uses=1, delay=1, hax_requirements=['ability'])]
        out = run(req)
        revived = [call for call in self.calls if call['item'].get('type') == 'revive']
        self.assertTrue(revived)
        self.assertEqual(revived[-1]['review']['check_ids'], ['ability'])
        self.assertEqual(out['final_state']['b']['state'], 'active')


class RealHaxCombatTests(unittest.TestCase):
    """Exercise the real policy and dependency gate using synthetic tier packets."""
    def checked(self, action, *, target_rank=2, mode='normal', owner='a', target='b'):
        from test_hax_policy import packet, level
        policy = packet(mode)
        policy.update(actor_id=owner, target_id=target)
        policy['target_level'] = level(target_rank, 'synthetic target')
        req = request([action]); req['mode'] = mode
        req['sources'] += policy['sources']
        req['hax_checks'] = [{'id': 'real', 'request': policy}]
        return req

    def test_real_policy_above_world_cap_never_executes_in_any_mode(self):
        for mode in ('normal', 'highest', 'lowball'):
            with self.subTest(mode=mode):
                action = attack(hax_requirements=['real'])
                action['effects'][0].update(status='assumed', assumptions=['Ignore the ceiling.'])
                out = run(self.checked(action, target_rank=4, mode=mode))
                self.assertEqual(out['hax_reviews']['real']['status'], 'blocked')
                self.assertEqual(out['final_state']['b']['hp'], 10)
                self.assertIsNone(out['terminal']['winner'])

    def test_real_policy_allows_effect_stronger_than_caster_ap(self):
        out = run(self.checked(attack(amount=1, hax_requirements=['real'])))
        self.assertEqual(out['hax_reviews']['real']['status'], 'supported_by_packet')
        self.assertEqual(out['final_state']['b']['hp'], 9)

    def test_actual_action_target_cannot_be_spoofed_by_metadata(self):
        action = attack(target='c', hax_requirements=['real'], affected_target='b')
        req = self.checked(action)
        req['actors'].append(actor('c'))
        out = run(req)
        self.assertEqual(out['final_state']['c']['hp'], 10)
        self.assertTrue(out['needs'])

    def test_actual_effect_target_cannot_be_spoofed_by_metadata(self):
        effect = fact(type='damage', target='c', amount=10, hax_requirements=['real'], affected_target='b')
        req = self.checked(attack(effects=[effect]))
        req['actors'].append(actor('c'))
        out = run(req)
        self.assertEqual(out['final_state']['c']['hp'], 10)
        self.assertTrue(out['needs'])

    def test_explicit_defense_scope_can_declare_offensive_penetration(self):
        defense = fact(outcome='not_prevented', hax_requirements=['real'],
                       ability_owner='a', affected_target='b')
        out = run(self.checked(attack(amount=1, defense=defense)))
        self.assertEqual(out['final_state']['b']['hp'], 9)
        self.assertFalse(out['needs'])

    def test_known_blocked_hax_does_not_erase_independent_physical_victory(self):
        req = self.checked(attack(hax_requirements=['real']), target_rank=4)
        req['steps'][0]['actions'].append(attack('b', 'a'))
        out = run(req)
        self.assertEqual(out['final_state']['a']['state'], 'incapacitated')
        self.assertEqual(out['terminal']['winner'], 'b')
        self.assertFalse(out['needs'])
        self.assertTrue(any(item['status'] == 'blocked' for item in out['hax_admissions']))

    def test_known_blocked_counterevidence_does_not_supply_protection(self):
        counter = fact(claim='synthetic forbidden immunity', hax_requirements=['real'])
        out = run(self.checked(attack(counterevidence=[counter]), target_rank=4, owner='b', target='a'))
        self.assertEqual(out['terminal']['winner'], 'a')
        self.assertFalse(out['needs'])

    def test_known_blocked_preventing_defense_does_not_cancel_attack(self):
        defense = fact(outcome='prevented', hax_requirements=['real'])
        out = run(self.checked(attack(defense=defense), target_rank=4, owner='b', target='a'))
        self.assertEqual(out['terminal']['winner'], 'a')
        self.assertNotEqual(out['trace'][0]['actions'][0]['outcome'], 'defended')
        self.assertFalse(out['needs'])

    def test_known_blocked_recovery_does_not_erase_physical_victory(self):
        req = self.checked(attack(), target_rank=4, owner='b', target='b')
        req['actors'][1]['recoveries'] = [fact(id='forbidden-return', trigger_states=['incapacitated'],
                            uses=1, delay=1, hp=10, hax_requirements=['real'])]
        trace = _Trace(req); out = trace.execute()
        self.assertEqual(out['terminal']['winner'], 'a')
        self.assertEqual(trace.remaining[('b', 'forbidden-return')], 1)
        self.assertFalse(out['needs'])
        self.assertEqual(out['pending'], [])


if __name__ == '__main__':
    unittest.main()
