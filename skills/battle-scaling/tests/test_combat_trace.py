import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from combat_trace import run
from rating_fixtures import rated_fixture, rated_call

# Explicit synthetic independent dossiers precede unrelated combat regressions.
run = rated_call(run)


def fact(**extra):
    return {'status': 'supported', 'evidence_ids': ['s-game'], **extra}


def actor(name, hp=10, **extra):
    return {'id': name, 'initial': {'state': 'active', 'hp': hp, 'max_hp': hp,
                                   'resources': {}},
            'hp_model': {'kind': 'game', 'zero_state': 'incapacitated',
                         'evidence_ids': ['s-game'],
                         'assumptions': ['HP<=0 means incapacitated in this branch']},
            **extra}


def attack(who='a', target='b', amount=10, **extra):
    return {'actor': who, 'target': target, 'intent': 'synthetic attack',
            'activation': fact(), 'hit': fact(),
            'defense': fact(outcome='not_prevented'),
            'effects': [fact(type='damage', target=target, amount=amount)], **extra}


@rated_fixture
def request(actions=None, steps=None):
    return {'mode': 'normal',
            'sources': [{'id': 's-game', 'origin': 'synthetic', 'access': 'provided',
                         'locator': 'synthetic game rules'}],
            'actors': [actor('a'), actor('b')],
            'steps': steps if steps is not None else [{'id': 'exchange', 'actions': actions or []}],
            'victory': {'defeated_states': ['incapacitated', 'dead', 'sealed', 'withdrawn']},
            'max_steps': 20}


class CombatTraceTests(unittest.TestCase):
    def test_simultaneous_hits_do_not_cancel_second_attack(self):
        out = run(request([attack(), attack('b', 'a')]))
        self.assertEqual(out['final_state']['a']['hp'], 0)
        self.assertEqual(out['final_state']['b']['hp'], 0)
        self.assertEqual(out['terminal']['kind'], 'mutual_defeat')
        self.assertIsNone(out['terminal']['winner'])
        self.assertFalse(out['canon_evidence'])

    def test_simultaneous_input_order_does_not_select_winner(self):
        first = run(request([attack(), attack('b', 'a')]))
        second = run(request([attack('b', 'a'), attack()]))
        self.assertEqual(first['final_state'], second['final_state'])
        self.assertEqual(first['terminal'], second['terminal'])

    def test_sequential_steps_stop_incapacitated_attacker(self):
        out = run(request(steps=[{'id': 'first', 'actions': [attack()]},
                                 {'id': 'second', 'actions': [attack('b', 'a')]}]))
        self.assertEqual(out['final_state']['a']['hp'], 10)
        self.assertEqual(out['terminal']['winner'], 'a')
        self.assertEqual(len(out['trace']), 1)

    def test_explicit_failure_cannot_be_overridden_by_assumption(self):
        action = attack(hit={'status': 'failed', 'evidence_ids': ['s-game'],
                             'assumptions': ['please still apply damage']})
        out = run(request([action]))
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertEqual(out['trace'][0]['actions'][0]['outcome'], 'hit_failed')

    def test_missing_hit_check_is_an_unresolved_branch(self):
        action = attack(); del action['hit']
        out = run(request([action]))
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertTrue(out['needs'])

    def test_explicit_assumption_branch_can_run(self):
        action = attack(hit={'status': 'assumed', 'assumptions': ['in this branch the strike lands']})
        out = run(request([action]))
        self.assertEqual(out['final_state']['b']['hp'], 0)
        self.assertEqual(out['status'], 'conditional')
        self.assertIn('in this branch the strike lands', out['assumptions'])

    def test_assumed_without_assumptions_is_not_executable(self):
        out = run(request([attack(hit={'status': 'assumed'})]))
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertTrue(out['needs'])

    def test_blocked_source_cannot_support_hit(self):
        req = request([attack(hit={'status': 'supported', 'evidence_ids': ['blocked']})])
        req['sources'].append({'id': 'blocked', 'origin': 'primary', 'access': 'blocked'})
        out = run(req)
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertTrue(out['needs'])

    def test_supported_counterevidence_prevents_effects(self):
        out = run(request([attack(counterevidence=[fact(claim='this attack cannot affect B')])]))
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertEqual(out['trace'][0]['actions'][0]['outcome'], 'counterevidence')

    def test_successful_defense_prevents_damage(self):
        out = run(request([attack(defense=fact(outcome='prevented'))]))
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertEqual(out['trace'][0]['actions'][0]['outcome'], 'defended')

    def test_unproved_effect_is_not_applied(self):
        out = run(request([attack(effects=[{'type': 'damage', 'target': 'b', 'amount': 10}])]))
        self.assertEqual(out['final_state']['b']['hp'], 10)
        self.assertTrue(out['needs'])

    def test_real_body_cannot_be_assigned_invented_hp(self):
        req = request([attack()]); req['actors'][1]['hp_model']['kind'] = 'real_body'
        with self.assertRaises(ValueError): run(req)

    def test_hp_requires_usable_game_source(self):
        req = request(); req['sources'][0]['access'] = 'blocked'
        out = run(req)
        self.assertNotIn('hp', out['final_state']['a'])
        self.assertTrue(out['needs'])

    def test_qualitative_sealing_does_not_require_hp(self):
        req = request([attack(effects=[fact(type='state', target='b', state='sealed')])])
        req['actors'] = [{'id': 'a', 'initial': {'state': 'active'}},
                         {'id': 'b', 'initial': {'state': 'active'}}]
        out = run(req)
        self.assertEqual(out['final_state']['b']['state'], 'sealed')
        self.assertEqual(out['terminal']['winner'], 'a')

    def test_resource_cost_is_paid_on_activated_but_missed_attack(self):
        action = attack(amount=1, hit=fact(status='failed'),
                        costs=[fact(resource='ammo', amount=1)])
        req = request([action]); req['actors'][0]['initial']['resources'] = {'ammo': 1}
        req['actors'][0]['resource_evidence_ids'] = ['s-game']
        out = run(req)
        self.assertEqual(out['final_state']['a']['resources']['ammo'], 0)
        self.assertEqual(out['final_state']['b']['hp'], 10)

    def test_resource_exhaustion_prevents_later_action(self):
        action = attack(amount=1, costs=[fact(resource='ammo', amount=1)])
        req = request(steps=[{'actions': [action]}, {'actions': [copy.deepcopy(action)]}])
        req['actors'][0]['initial']['resources'] = {'ammo': 1}
        req['actors'][0]['resource_evidence_ids'] = ['s-game']
        out = run(req)
        self.assertEqual(out['final_state']['b']['hp'], 9)
        self.assertEqual(out['trace'][1]['actions'][0]['outcome'], 'resource_exhausted')

    def test_same_step_resource_cannot_be_double_spent(self):
        action = attack(amount=1, costs=[fact(resource='ammo', amount=1)])
        req = request([action, copy.deepcopy(action)])
        req['actors'][0]['initial']['resources'] = {'ammo': 1}
        req['actors'][0]['resource_evidence_ids'] = ['s-game']
        out = run(req)
        self.assertEqual(out['final_state']['b']['hp'], 9)
        self.assertEqual(out['final_state']['a']['resources']['ammo'], 0)

    def test_duration_one_ticks_next_step_not_application_step(self):
        effect = fact(type='ongoing', target='b', id='poison', duration=1,
                      tick=fact(type='damage', amount=3))
        req = request(steps=[{'actions': [attack(effects=[effect])]}, {'actions': []}, {'actions': []}])
        out = run(req)
        self.assertEqual(out['trace'][0]['state_after']['b']['hp'], 10)
        self.assertEqual(len(out['trace'][0]['state_after']['b']['effects']), 1)
        self.assertEqual(out['trace'][1]['state_after']['b']['hp'], 7)
        self.assertEqual(out['final_state']['b']['hp'], 7)
        self.assertEqual(out['final_state']['b']['effects'], [])

    def test_delayed_revival_is_pending_not_permanent_death(self):
        req = request([attack()])
        req['actors'][1]['recoveries'] = [fact(id='one-return', trigger_states=['incapacitated'],
                                              delay=2, hp=10, uses=1)]
        out = run(req)
        self.assertEqual(out['terminal']['kind'], 'recovery_pending')
        self.assertFalse(out['terminal']['is_terminal'])
        self.assertIsNone(out['terminal']['winner'])
        self.assertEqual(out['pending'][0]['due_step'], 3)

    def test_delayed_revival_occurs_at_due_step(self):
        req = request(steps=[{'actions': [attack()]}, {'actions': []}, {'actions': []}])
        req['actors'][1]['recoveries'] = [fact(id='return', trigger_states=['incapacitated'],
                                              delay=2, hp=6, uses=1)]
        out = run(req)
        self.assertEqual(out['trace'][1]['state_after']['b']['state'], 'incapacitated')
        self.assertEqual(out['trace'][2]['state_after']['b']['state'], 'active')
        self.assertEqual(out['final_state']['b']['hp'], 6)

    def test_simultaneous_incapacitation_with_revival_is_not_mutual_terminal(self):
        req = request([attack(), attack('b', 'a')])
        req['actors'][0]['recoveries'] = [fact(id='return', trigger_states=['incapacitated'],
                                              delay=1, hp=10, uses=1)]
        out = run(req)
        self.assertEqual(out['terminal']['kind'], 'recovery_pending')
        self.assertFalse(out['terminal']['is_terminal'])

    def test_blocked_revival_is_unknown_not_confirmed_permanent_defeat(self):
        req = request([attack()])
        req['sources'].append({'id': 'blocked', 'access': 'blocked', 'origin': 'primary'})
        req['actors'][1]['recoveries'] = [fact(id='return', trigger_states=['incapacitated'],
                                              delay=1, hp=10, uses=1, evidence_ids=['blocked'])]
        out = run(req)
        self.assertEqual(out['terminal']['kind'], 'undetermined')
        self.assertIsNone(out['terminal']['winner'])
        self.assertTrue(out['needs'])

    def test_incomplete_victory_conditions_do_not_force_winner(self):
        req = request([attack()]); del req['victory']
        out = run(req)
        self.assertIsNone(out['terminal']['winner'])
        self.assertEqual(out['terminal']['adjudication'], 'undetermined')

    def test_max_steps_truncation_is_not_draw(self):
        req = request(steps=[{'actions': []}, {'actions': []}]); req['max_steps'] = 1
        out = run(req)
        self.assertEqual(out['status'], 'truncated')
        self.assertEqual(out['terminal']['kind'], 'truncated')
        self.assertIsNone(out['terminal']['winner'])

    def test_optional_narrative_is_derived_and_never_evidence(self):
        req = request([attack()]); req['include_narrative'] = True
        out = run(req)
        self.assertIn('narrative', out)
        self.assertEqual(out['narrative_status'], 'illustrative_not_canon')
        self.assertFalse(out['canon_evidence'])
        self.assertNotIn('narrative', run(request([attack()])))

    def test_request_is_not_mutated(self):
        req = request([attack()]); before = copy.deepcopy(req)
        run(req)
        self.assertEqual(req, before)

    def test_invalid_numeric_values_and_unknown_target_raise(self):
        for amount in (True, float('nan'), -1):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError): run(request([attack(amount=amount)]))
        with self.assertRaises(ValueError): run(request([attack(target='missing')]))

    def test_each_recorded_action_retains_all_five_stages(self):
        out = run(request([attack()]))
        row = out['trace'][0]['actions'][0]
        for key in ('intent', 'activation', 'hit', 'defense', 'state_changes', 'follow_up',
                    'evidence_ids', 'assumptions'):
            self.assertIn(key, row)

    def test_read_and_host_browser_sources_are_usable(self):
        for access in ('read', 'verified_via_host_browser'):
            req = request([attack()]); req['sources'][0]['access'] = access
            self.assertEqual(run(req)['final_state']['b']['hp'], 0)

    def test_launched_delayed_attack_must_resolve_before_victory(self):
        delayed = attack('b', 'a', effects=[fact(type='damage', target='a', amount=10, delay=1)])
        out = run(request([attack(), delayed]))
        self.assertFalse(out['terminal']['is_terminal'])
        self.assertEqual(out['terminal']['kind'], 'effects_pending')
        out = run(request(steps=[{'actions': [attack(), delayed]}, {'actions': []}]))
        self.assertEqual(out['terminal']['kind'], 'mutual_defeat')

    def test_ongoing_damage_is_not_canceled_by_casters_incapacitation(self):
        poison = attack('b', 'a', effects=[fact(type='ongoing', id='venom', target='a', duration=1,
                                             tick=fact(type='damage', amount=10))])
        out = run(request(steps=[{'actions': [attack(), poison]}, {'actions': []}]))
        self.assertEqual(len(out['trace']), 2)
        self.assertEqual(out['terminal']['kind'], 'mutual_defeat')

    def test_zero_hp_damage_does_not_remove_seal(self):
        req = request(steps=[{'actions': [attack(effects=[fact(type='state', target='b', state='sealed'),
                                                          fact(type='damage', target='b', amount=10)])]}])
        req['actors'][1]['recoveries'] = [fact(id='return', trigger_states=['incapacitated'],
                                              delay=0, hp=10)]
        out = run(req)
        self.assertEqual(out['final_state']['b']['state'], 'sealed')

    def test_unknown_initial_states_do_not_resolve_ending(self):
        req = request()
        req['actors'] = [{'id': 'a'}, {'id': 'b'}]
        out = run(req)
        self.assertFalse(out['terminal']['is_terminal'])
        self.assertIsNone(out['terminal']['winner'])

    def test_resource_exhaustion_can_express_explicit_exit(self):
        req = request([attack(amount=1, costs=[fact(resource='stamina', amount=1)])])
        req['actors'][0]['initial']['resources'] = {'stamina': 1}
        req['actors'][0]['resource_evidence_ids'] = ['s-game']
        req['actors'][0]['resource_exhaustion'] = {'stamina': 'withdrawn'}
        out = run(req)
        self.assertEqual(out['final_state']['a']['state'], 'withdrawn')
        self.assertEqual(out['final_state']['b']['hp'], 9)

    def test_expiring_effect_can_explicitly_release_seal(self):
        timed = fact(type='ongoing', target='b', id='seal-window', duration=1,
                     tick=fact(type='heal', amount=0),
                     on_expire=[fact(type='state', state='active')])
        req = request(steps=[{'actions': [attack(effects=[fact(type='state', target='b', state='sealed'), timed])]},
                             {'actions': []}])
        out = run(req)
        self.assertEqual(len(out['trace']), 2)
        self.assertEqual(out['final_state']['b']['state'], 'active')

    def test_multiple_survivors_on_one_team_can_win(self):
        req = request([attack(effects=[fact(type='state', target='b', state='incapacitated')])])
        req['actors'].append(actor('ally'))
        req['teams'] = {'a': 'left', 'ally': 'left', 'b': 'right'}
        out = run(req)
        self.assertEqual(out['terminal']['winner'], 'left')
        self.assertTrue(out['terminal']['is_terminal'])

    def test_team_order_does_not_break_simultaneous_mutual_defeat(self):
        req = request([attack(), attack('b', 'a')]); req['teams'] = {'b': 'right', 'a': 'left'}
        out = run(req)
        self.assertEqual(out['terminal']['kind'], 'mutual_defeat')
        self.assertIsNone(out['terminal']['winner'])

    def test_multiple_unteamed_survivors_are_not_a_single_winner(self):
        req = request([attack()]); req['actors'].append(actor('third'))
        self.assertFalse(run(req)['terminal']['is_terminal'])

    def test_qualitative_body_injury_has_provenance_and_no_invented_hp(self):
        injury = fact(type='injury', target='b', part='left forearm', description='visible wound',
                      limitations=['grip limitation is a host assumption'],
                      assumptions=['test branch: affected grip, without a numerical damage scale'])
        req = request([attack(effects=[injury])])
        req['actors'] = [{'id': 'a', 'initial': {'state': 'active'}},
                         {'id': 'b', 'initial': {'state': 'active'}}]
        out = run(req)
        self.assertNotIn('hp', out['final_state']['b'])
        recorded = out['final_state']['b']['injuries'][0]
        self.assertEqual(recorded['part'], 'left forearm')
        self.assertEqual(recorded['evidence_ids'], ['s-game'])
        self.assertEqual(recorded['limitations'], injury['limitations'])
        self.assertEqual(out['final_state']['b']['state'], 'active')

    def test_unproved_injury_is_not_added(self):
        injury = {'type': 'injury', 'target': 'b', 'part': 'arm', 'description': 'unverified fracture'}
        out = run(request([attack(effects=[injury])]))
        self.assertEqual(out['final_state']['b']['injuries'], [])
        self.assertTrue(out['needs'])


if __name__ == '__main__':
    unittest.main()
