"""Synthetic integration checks for independent Wangba/VSB rule selection."""
import argparse
import contextlib
import copy
import io
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from battle import compute_case, export_case, main, render_report, select_profile
from combat_trace import run as run_process
from evidence import analyze_case, analyze_matchup, classify_energy, normalize_quantity
from rating_fixtures import rated_fixture, rated_call, with_independent_ratings
analyze_case = rated_call(analyze_case)
run_process = rated_call(run_process)
from hax_gate import build_checks
from rule_profiles import finite_path, resolve
from standards import SBA, prepare_case, validate_case_standard, victory_review, vsb_tier_quantity
from vsb_hax_policy import CHECKS
from vsb_high import run as review_high
from rating_fixtures import legacy_analyze_case as analyze_case  # Explicit legacy regression
from rating_fixtures import legacy_compute_case as compute_case


SOURCES = [{'id': 's', 'origin': 'synthetic', 'access': 'provided',
            'title': 'Synthetic regression fixture, not a real fictional feat.',
            'locator': 'fixture event'}]


@rated_fixture
def case():
    return {'schema_version': 1, 'case_id': 'synthetic-standard-switch', 'fixture_kind': 'synthetic',
            'characters': [{'id': who, 'name': who.upper(), 'version': 'synthetic-one',
                            'state': 'synthetic-base'} for who in ('a', 'b')],
            'sources': copy.deepcopy(SOURCES),
            'anchors': [{'id': 'regular', 'subject': 'a', 'attribute': 'attack_energy',
                         'kind': 'repeated_feat', 'quantity': {'value': 2000, 'unit': 'J'},
                         'evidence_ids': ['s']}], 'edges': []}


def fact(**extra):
    return {'status': 'supported', 'evidence_ids': ['s'], **extra}


def victory(condition='knockout', duration=3600, **extra):
    return {'condition': condition, 'status': 'supported', 'evidence_ids': ['s'],
            'duration_seconds': duration, **extra}


@rated_fixture
def process(state='incapacitated', standard='vsb', check=None, simultaneous=False):
    def action(actor, target):
        return {'actor': actor, 'target': target, 'intent': 'Synthetic state transition',
                'activation': fact(), 'hit': fact(), 'defense': fact(outcome='not_prevented'),
                'effects': [fact(type='state', target=target, state=state)]}
    actions = [action('a', 'b')]
    if simultaneous:
        actions.append(action('b', 'a'))
    request = {'mode': 'normal', 'standard': standard, 'sources': copy.deepcopy(SOURCES),
               'actors': [{'id': who, 'initial': {'state': 'active'}} for who in ('a', 'b')],
               'steps': [{'id': 'one-event-not-one-second', 'actions': actions}],
               'victory': {'defeated_states': ['incapacitated', 'dead', 'sealed', 'withdrawn']}}
    if check is not None:
        request['victory']['vsb_checks'] = {'b': check}
        if simultaneous:
            request['victory']['vsb_checks']['a'] = copy.deepcopy(check)
    return request


def hax_packet():
    check = {'state': 'pass', 'explanation': 'Synthetic supported mechanism premise.', 'source_ids': ['s']}
    return {'actor_id': 'a', 'target_id': 'b', 'ability_id': 'synthetic-mind-effect',
            'effect_evidence': {'ability_id': 'synthetic-mind-effect', 'basis': 'demonstrated',
                                'statement': 'Synthetic successful effect.',
                                'mechanism': 'Synthetic nonphysical mind targeting.', 'source_ids': ['s']},
            'target': {'description': 'Synthetic target with a relevant accessible mind.', 'source_ids': ['s']},
            'checks': {name: copy.deepcopy(check) for name in CHECKS},
            'effect_scope': {'description': 'One target mind.', 'range_interaction': 'Target aspect in range.',
                             'resistance_interaction': 'Matching resistance mechanism compared.', 'source_ids': ['s']}}


def computation_case(kind, request, selector=None):
    packet = case()
    packet['standard'] = 'vsb'
    packet['anchors'] = []
    # The source metadata is a synthetic original-work fixture; it is not a real canon citation.
    packet['sources'][0]['origin'] = 'primary'
    node = {'id': 'compute', 'type': kind, 'request': request}
    if selector is not None:
        node['attach'] = {'id': 'computed-anchor', 'subject': 'a', 'attribute': 'attack_energy',
                          'kind': 'calculation', 'evidence_ids': ['s'], 'result_path': selector}
        if kind == 'physics':
            node['attach']['unit'] = 'J'
    packet['computations'] = [node]
    return packet


def high_packet(state=True):
    info = review_high({'operation': 'criteria', 'tier': '1-A'})
    rule = info['tiers']['1-A']
    keys = list(info['common_criteria']) + rule['required']
    claim = {'status': True, 'reason': 'Synthetic fixture supplies the specified complete structural and effect argument.',
             'source_ids': ['s']}
    packet = {'operation': 'review', 'requested_tier': '1-A',
              'criteria': {key: copy.deepcopy(claim) for key in keys},
              'sources': [{**SOURCES[0], 'origin': 'primary'}]}
    if state is False:
        packet['criteria'][keys[0]]['status'] = False
        packet['criteria'][keys[0]]['reason'] = 'Synthetic fixture contradicts this required structural premise.'
    elif state is None:
        del packet['criteria'][keys[0]]
    return packet


class StandardSelectionTests(unittest.TestCase):
    def test_installed_default_remains_wangba(self):
        self.assertEqual(resolve()['standard'], 'wangba')
        self.assertEqual(analyze_case(case())['standard'], 'wangba')

    def test_profile_and_explicit_standard_cannot_conflict(self):
        for profile, selected in (('legacy-2024-2025', 'vsb'),
                                  ('vsb-current-2026-10-21', 'wangba'), ('wangba', 'vsb')):
            with self.subTest(profile=profile, selected=selected), self.assertRaises(ValueError):
                resolve(profile, selected)

    def test_cli_selector_overrides_case_default_without_renaming_foreign_evidence(self):
        selected = select_profile({'standard': 'wangba'},
                                  argparse.Namespace(standard='vsb', ruleset_profile=None))
        self.assertEqual(selected['standard'], 'vsb')
        self.assertEqual(selected['selection_source'], 'explicit_cli_standard')

    def test_same_joules_map_to_distinct_standards(self):
        quantity = {'value': 2000, 'unit': 'J'}
        wangba = classify_energy(quantity, finite_path(resolve(standard='wangba')))
        vsb = classify_energy(quantity, finite_path(resolve(standard='vsb')))
        self.assertIn('弱爆砖', wangba['best_reference'])
        self.assertEqual(vsb['vsb_assessment']['classification']['tier'], '9-C')
        self.assertNotEqual(wangba['ruleset_id'], vsb['ruleset_id'])

    def test_mode_and_pk_do_not_select_rule_standard(self):
        request = case()
        request['standard'] = 'vsb'
        request['matchup'] = {'teams': ['a', 'b'], 'presentation': 'process', 'win_paths': [],
                              'mode_processes': {'highest': process()}}
        result = analyze_case(request, 'highest')
        self.assertEqual(result['standard'], 'vsb')
        self.assertEqual(list(result['modes']), ['highest'])
        self.assertEqual(result['matchup']['presentation'], 'process')
        self.assertEqual(result['matchup']['process']['standard'], 'vsb')
        self.assertEqual(result['matchup']['process']['mode'], 'highest')

    def test_cli_accepts_standard_mode_and_pk_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp)
            request = case()
            request['matchup'] = {'teams': ['a', 'b'], 'win_paths': [],
                                  'mode_processes': {'lowball': process()}}
            (path / 'input.json').write_text(json.dumps(request), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = main(['analyze', '--input', str(path / 'input.json'),
                                  '--output', str(path / 'out'), '--standard', 'vsb',
                                  '--mode', 'lowball', '--pk', 'process'])
            self.assertEqual(exit_code, 0)
            result = json.loads((path / 'out' / 'analysis.json').read_text(encoding='utf-8'))
            self.assertEqual(result['standard'], 'vsb')
            self.assertEqual(list(result['modes']), ['lowball'])
            self.assertEqual(result['matchup']['presentation'], 'process')

    def test_foreign_tier_anchor_is_rejected_in_both_directions(self):
        for standard, foreign in (('vsb', 'high-wangba-handbook-2026-07-30'),
                                  ('wangba', 'vsb-high-current-2026-10-21')):
            request = case()
            request['anchors'][0]['quantity'] = {'kind': 'tier', 'ruleset': foreign,
                                                  'label': 'synthetic', 'rank': 3}
            with self.subTest(standard=standard), self.assertRaises(ValueError):
                analyze_case(request, profile=resolve(standard=standard))

    def test_vsb_prefix_does_not_certify_an_unregistered_tier_standard(self):
        request = case()
        request['anchors'][0]['quantity'] = {'kind': 'tier', 'ruleset': 'vsb-impostor-wangba',
                                              'label': '论天最上', 'rank': 999}
        with self.assertRaises(ValueError):
            validate_case_standard(request, resolve(standard='vsb'))

    def test_registered_vsb_anchor_cannot_forge_a_rank_for_its_official_code(self):
        request = case()
        quantity = vsb_tier_quantity({'tier': '1-A', 'label': 'Outerverse level'})
        quantity['rank'] += 1
        request['anchors'][0]['quantity'] = quantity
        with self.assertRaises(ValueError):
            analyze_case(request, profile=resolve(standard='vsb'))

    def test_old_wangba_hax_packet_is_not_a_vsb_verdict(self):
        request = case()
        request['hax_checks'] = [{'id': 'old', 'request': {'actor_id': 'a', 'target_id': 'b',
            'ability_id': 'old-ability', 'observed_limit': {}, 'world_ceiling': {}}}]
        with self.assertRaises(ValueError):
            analyze_case(request, profile=resolve(standard='vsb'))

    def test_nested_hax_request_cannot_change_selected_standard(self):
        request = hax_packet()
        request['standard'] = 'wangba'
        with self.assertRaises(ValueError):
            build_checks([{'id': 'h', 'request': request}], SOURCES, 'normal', standard='vsb')

    def test_vsb_gate_ignores_world_cap_but_keeps_mechanism_failures_and_unknowns(self):
        request = hax_packet()
        request.update(caster_ap={'rank': 1}, target_level={'rank': 1000}, world_ceiling={'rank': 2})
        entry = [{'id': 'h', 'request': request}]
        passed = build_checks(entry, SOURCES, 'normal', standard='vsb')['h']
        self.assertEqual(passed['status'], 'supported_by_packet')
        self.assertFalse(passed['world_ceiling_applied'])
        self.assertEqual(passed['scope'], {'actor_id': 'a', 'target_id': 'b', 'ability_id': 'synthetic-mind-effect'})
        request['checks']['resistance']['state'] = 'fail'
        self.assertEqual(build_checks(entry, SOURCES, 'highest', standard='vsb')['h']['status'], 'blocked')
        request['checks']['resistance']['state'] = 'unknown'
        self.assertEqual(build_checks(entry, SOURCES, 'normal', standard='vsb')['h']['status'], 'undetermined')

    def test_vsb_highest_excludes_explicit_outlier(self):
        request = case()
        request['anchors'].append({'id': 'excluded-peak', 'subject': 'a', 'attribute': 'attack_energy',
            'kind': 'outlier', 'quantity': {'value': 1e12, 'unit': 'J'}, 'evidence_ids': ['s']})
        vsb = analyze_case(request, 'highest', profile=resolve(standard='vsb'))
        self.assertEqual(vsb['modes']['highest']['conclusions'][0]['quantity']['best'], 2000)
        self.assertIn('excluded-peak', vsb['standard_audit']['excluded_anchor_ids'])
        wangba = analyze_case(request, 'highest', profile=resolve(standard='wangba'))
        self.assertEqual(wangba['modes']['highest']['conclusions'][0]['quantity']['best'], 1e12)

    def test_sba_packet_records_defaults_without_overwriting_explicit_thread_conditions(self):
        request = case()
        request['matchup'] = {'teams': ['a', 'b'], 'conditions': {'arena': 'synthetic ocean',
                                                                       'speed_equalized': True}}
        prepared, _ = prepare_case(request, resolve(standard='vsb'))
        conditions = prepared['matchup']['conditions']
        self.assertEqual(conditions['arena'], 'synthetic ocean')
        self.assertIs(conditions['speed_equalized'], True)
        self.assertIs(conditions['vsb_sba_defaults']['speed_equalized'], False)
        self.assertIn('Central Park', conditions['vsb_sba_defaults']['arena'])
        self.assertEqual(conditions['vsb_sba_defaults']['victory']['bfr_min_seconds'], 604800)

    def test_two_true_tier_zero_characters_are_not_normal_vs(self):
        request = case()
        for character in request['characters']:
            character['vsb_tier'] = '0'
        request['matchup'] = {'teams': ['a', 'b']}
        with self.assertRaises(ValueError):
            analyze_case(request, profile=resolve(standard='vsb'))

    def test_two_canonical_tier_zero_anchors_block_vs_without_character_tier_metadata(self):
        request = case()
        request['anchors'] = [{'id': 'zero-' + who, 'subject': who, 'attribute': 'attack_energy',
            'kind': 'repeated_feat', 'quantity': vsb_tier_quantity({'tier': '0', 'label': 'Boundless'}),
            'evidence_ids': ['s']} for who in ('a', 'b')]
        self.assertTrue(all('vsb_tier' not in character for character in request['characters']))
        request['matchup'] = {'teams': ['a', 'b'], 'win_paths': []}
        with self.assertRaises(ValueError):
            analyze_case(request, profile=resolve(standard='vsb'))

    def test_analyze_case_maps_typed_speed_and_lifting_without_reclassifying_body_mass(self):
        request = case()
        request['anchors'] = [{'id': attribute, 'subject': 'a', 'attribute': attribute,
            'kind': 'repeated_feat', 'quantity': {'value': value, 'unit': unit}, 'evidence_ids': ['s']}
            for attribute, value, unit in (('combat_speed', 343, 'm/s'),
                                           ('lifting_strength', 1000, 'kg'), ('body_mass', 1000, 'kg'))]
        result = analyze_case(request, profile=resolve(standard='vsb'))
        conclusions = {item['attribute']: item for item in result['modes']['normal']['conclusions']}
        speed = conclusions['combat_speed']['mapping']
        self.assertEqual(speed['best_reference'], 'Transonic')
        self.assertEqual(speed['vsb_assessment']['classification']['speed_type'], 'combat')
        lifting = conclusions['lifting_strength']['mapping']
        self.assertEqual(lifting['best_reference'], 'Class 5')
        body_mass = conclusions['body_mass']['mapping']
        if body_mass is not None:
            self.assertIsNone(body_mass['best_reference'])
            self.assertIsNone(body_mass['vsb_assessment'])

    def test_analyze_case_supersonic_reference_uses_actual_supersonic_velocity(self):
        request = case()
        request['anchors'][0].update(attribute='combat_speed', quantity={'value': 400, 'unit': 'm/s'})
        result = analyze_case(request, profile=resolve(standard='vsb'))
        self.assertEqual(result['modes']['normal']['conclusions'][0]['mapping']['best_reference'], 'Supersonic')

    def test_ledger_records_the_actual_standard_and_hax_policy(self):
        for standard, policy in (('wangba', 'user_confirmed_hax_ceiling_20261020'),
                                  ('vsb', 'vsb_hax_mechanism_20261021')):
            result = analyze_case(case(), profile=resolve(standard=standard))
            with tempfile.TemporaryDirectory() as tmp:
                export_case(result, tmp)
                ledger = json.loads((pathlib.Path(tmp) / 'run-ledger.json').read_text(encoding='utf-8'))
                self.assertEqual(ledger['standard'], standard)
                self.assertEqual(ledger['hax_policy_id'], policy)

    def test_vsb_report_does_not_reintroduce_wangba_world_cap(self):
        request = case()
        request['hax_checks'] = [{'id': 'h', 'request': hax_packet()}]
        report = render_report(analyze_case(request, profile=resolve(standard='vsb')))
        self.assertNotIn('最高不得超过原世界观最强角色已达量级', report)
        self.assertNotIn('角色天花板内', report)
        self.assertIn('VSB', report)


class VSBVictoryIntegrationTests(unittest.TestCase):
    def test_one_defeated_state_is_not_a_sba_duration(self):
        for state in ('incapacitated', 'sealed', 'withdrawn', 'dead'):
            with self.subTest(state=state):
                out = run_process(process(state))
                self.assertFalse(out['terminal']['is_terminal'])
                self.assertIsNone(out['terminal']['winner'])
                self.assertTrue(out['needs'])

    def test_wangba_legacy_state_rule_does_not_silently_change(self):
        out = run_process(process(standard='wangba'))
        self.assertEqual(out['terminal']['winner'], 'a')

    def test_knockout_exact_hour_qualifies_but_shorter_does_not(self):
        for seconds, qualifies in ((3599, False), (3600, True)):
            out = run_process(process(check=victory(duration=seconds)))
            self.assertEqual(out['terminal']['winner'] == 'a', qualifies)

    def test_bfr_exact_week_qualifies_but_shorter_does_not(self):
        for seconds, qualifies in ((604799, False), (604800, True)):
            out = run_process(process('withdrawn', check=victory('bfr', seconds)))
            self.assertEqual(out['terminal']['winner'] == 'a', qualifies)

    def test_incapacitation_must_exceed_one_day(self):
        for seconds, qualifies in ((86400, False), (86400.001, True)):
            out = run_process(process('sealed', check=victory('incapacitation', seconds)))
            self.assertEqual(out['terminal']['winner'] == 'a', qualifies)

    def test_death_needs_an_eventual_qualifying_condition(self):
        death = {'condition': 'death', 'status': 'supported', 'evidence_ids': ['s']}
        self.assertIsNone(run_process(process('dead', check=death))['terminal']['winner'])
        death['post_death'] = victory('knockout', 3599)
        self.assertIsNone(run_process(process('dead', check=death))['terminal']['winner'])
        death['post_death'] = victory('knockout', 3600)
        self.assertEqual(run_process(process('dead', check=death))['terminal']['winner'], 'a')

    def test_state_and_victory_condition_must_match(self):
        out = run_process(process('sealed', check=victory('knockout', 3600)))
        self.assertIsNone(out['terminal']['winner'])

    def test_unknown_or_unread_victory_evidence_is_not_adopted(self):
        for packet in (victory(status='unknown'), victory(evidence_ids=['missing'])):
            self.assertIsNone(run_process(process(check=packet))['terminal']['winner'])

    def test_steps_are_not_seconds_even_if_a_number_is_large(self):
        request = process()
        request['steps'][0]['id'] = '604800'
        request['max_steps'] = 1000
        self.assertIsNone(run_process(request)['terminal']['winner'])

    def test_mutual_ko_does_not_bypass_sba_duration(self):
        out = run_process(process(simultaneous=True))
        self.assertFalse(out['terminal']['is_terminal'])
        self.assertEqual(out['terminal']['kind'], 'undetermined')

    def test_mutual_ko_with_qualifying_durations_still_needs_first_condition_timing(self):
        out = run_process(process(simultaneous=True, check=victory('knockout', 3600)))
        self.assertFalse(out['terminal']['is_terminal'])
        self.assertIsNone(out['terminal']['winner'])
        self.assertEqual(out['terminal']['kind'], 'undetermined')
        self.assertTrue(any(need['where'] == 'victory.timing' for need in out['needs']))

    def test_explicit_blocked_macro_path_survives_unknown_duration(self):
        matchup = {'teams': ['a', 'b'], 'win_paths': [{'id': 'blocked-path', 'winner': 'a',
            'status': 'blocked', 'evidence_ids': ['s'], 'requirements': [fact(status='blocked')]}]}
        context = with_independent_ratings({**case(), 'standard':'vsb'})
        out = analyze_matchup(matchup, {s['id']:s for s in context['sources']}, standard='vsb', mode='normal', rating_context=context)
        self.assertEqual(out['win_paths'][0]['reviewed_status'], 'blocked')

    def test_macro_unknown_sba_condition_does_not_adopt_winner(self):
        matchup = {'teams': ['a', 'b'], 'win_paths': [{'id': 'p', 'winner': 'a',
            'evidence_ids': ['s'], 'requirements': [fact()]}],
            'mode_assessments': {'normal': {'status': 'reasoned_estimate', 'winner': 'a',
                'reasoning': 'Synthetic claim without duration.', 'evidence_ids': ['s']}}}
        context = with_independent_ratings({**case(), 'standard':'vsb'})
        out = analyze_matchup(matchup, {s['id']:s for s in context['sources']}, standard='vsb', mode='normal', rating_context=context)
        self.assertEqual(out['verdict'], 'insufficient_evidence')
        self.assertIsNone(out['assessment']['winner'])
        self.assertEqual(out['assessment']['status'], 'undetermined')

    def test_duration_numbers_must_be_finite_not_boolean(self):
        for duration in (True, float('nan'), float('inf'), -1, '3600'):
            self.assertEqual(victory_review(victory(duration=duration), SOURCES)['status'], 'undetermined')


class VSBComputationAttachmentIntegrationTests(unittest.TestCase):
    def test_blocked_physics_retains_audit_but_withholds_attachment(self):
        request = {'model': 'relativistic_kinetic', 'inputs': {'mass': 1, 'speed': 299792458}}
        out = compute_case(computation_case('physics', request, 'result.value'))
        self.assertEqual(out['anchors'], [])
        node = out['computations'][0]
        self.assertEqual(node['output']['status'], 'blocked')
        self.assertEqual(node['output']['standard'], 'vsb')
        self.assertEqual(node['attachment_review']['status'], 'withheld')

    def test_undetermined_mass_conversion_cannot_use_raw_mathematical_reference(self):
        request = {'model': 'mass_energy', 'inputs': {'mass': 1, 'conversion_fraction': 1},
                   'applicability': {'physical_mass_conversion_established': True,
                                     'conversion_evidence': 'Synthetic host assertion lacking bound primary conversion evidence.'}}
        for selector in ('result.value', 'mathematical_reference.result.value'):
            with self.subTest(selector=selector):
                out = compute_case(computation_case('physics', request, selector))
                self.assertEqual(out['anchors'], [])
                node = out['computations'][0]
                self.assertEqual(node['output']['status'], 'undetermined')
                self.assertEqual(node['attachment_review']['status'], 'withheld')
                self.assertIn('mathematical_reference', node['output'])

    def test_approved_physics_attaches_only_accepted_result(self):
        speed = .99 * 299792458
        request = {'model': 'relativistic_kinetic', 'inputs': {'mass': 1, 'speed': speed}}
        out = compute_case(computation_case('physics', request, 'result.value'))
        self.assertEqual(len(out['anchors']), 1)
        node = out['computations'][0]
        self.assertEqual(node['output']['status'], 'ok')
        accepted = 2 * speed * speed
        self.assertAlmostEqual(out['anchors'][0]['quantity']['value'], accepted)
        self.assertGreater(node['output']['raw_calculation']['result']['value'], accepted)
        self.assertEqual(analyze_case(out)['standard'], 'vsb')

    def test_approved_physics_cannot_attach_raw_or_policy_review_values(self):
        request = {'model': 'relativistic_kinetic', 'inputs': {'mass': 1, 'speed': .99 * 299792458}}
        for selector in ('raw_calculation.result.value',
                         'policy_review.kinetic_cap.uncapped_relativistic_energy_j',
                         'steps.0.value'):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                compute_case(computation_case('physics', request, selector))

    def test_approved_mass_conversion_receives_case_source_catalog(self):
        request = {'model': 'mass_energy', 'inputs': {'mass': 1, 'conversion_fraction': 1},
                   'vsb_policy': {'mass_energy_conversion': {'explicit_conversion_mechanism': True,
                       'statement': 'Synthetic original statement explicitly converts the stated matter into energy.',
                       'source_ids': ['s']}}}
        out = compute_case(computation_case('physics', request, 'result'))
        self.assertEqual(out['computations'][0]['output']['status'], 'ok')
        self.assertEqual(out['computations'][0]['output']['policy_review']['source_ids'], ['s'])
        self.assertEqual(len(out['anchors']), 1)
        self.assertEqual(normalize_quantity(out['anchors'][0]['quantity'])['unit'], 'J')

    def test_blocked_and_undetermined_high_packets_do_not_attach(self):
        for state, expected in ((False, 'blocked'), (None, 'undetermined')):
            with self.subTest(state=state):
                out = compute_case(computation_case('high', high_packet(state), 'classification'))
                self.assertEqual(out['anchors'], [])
                node = out['computations'][0]
                self.assertEqual(node['output']['status'], expected)
                self.assertEqual(node['attachment_review']['status'], 'withheld')

    def test_supported_high_classification_converts_to_legal_canonical_tier_quantity(self):
        out = compute_case(computation_case('high', high_packet(), 'classification'))
        self.assertEqual(out['computations'][0]['output']['status'], 'supported_by_packet')
        self.assertEqual(len(out['anchors']), 1)
        quantity = out['anchors'][0]['quantity']
        self.assertEqual(quantity['kind'], 'tier')
        self.assertEqual(quantity['ruleset'], 'vsb-high-current-2026-10-21')
        self.assertIn('1-A', (quantity.get('tier'), quantity.get('code')))
        self.assertTrue(quantity['label'])
        self.assertIsInstance(quantity['rank'], (int, float))
        self.assertEqual(normalize_quantity(quantity)['unit'], 'tier:vsb-high-current-2026-10-21')
        result = analyze_case(out)
        self.assertEqual(result['standard'], 'vsb')
        self.assertEqual(result['modes']['normal']['conclusions'][0]['quantity']['kind'], 'tier')

    def test_approved_high_must_not_attach_arbitrary_policy_or_criteria_fields(self):
        for selector in ('classification.tier', 'criteria_review.0', 'parameter_review'):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                compute_case(computation_case('high', high_packet(), selector))

    def test_conditional_high_attachment_retains_assumption_in_anchor_and_conclusion(self):
        request = high_packet()
        criterion = next(iter(request['criteria']))
        assumption = 'For this synthetic branch only, the disputed full structural scope exists.'
        request['criteria'][criterion].update(status=None,
            reason='This exact structural premise is unresolved in the synthetic fixture.', assumption=assumption)
        out = compute_case(computation_case('high', request, 'classification'))
        self.assertEqual(out['computations'][0]['output']['status'], 'conditional')
        self.assertIn(assumption, out['anchors'][0]['assumptions'])
        conclusion = analyze_case(out)['modes']['normal']['conclusions'][0]
        self.assertEqual(conclusion['status'], 'conditional')
        self.assertIn(assumption, conclusion['assumptions'])


if __name__ == '__main__':
    unittest.main()
