import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from handbook_finite import classify


def run(value, unit='t_TNT', **context):
    context.setdefault('release','violent')
    return classify({'quantity': {'value': value, 'unit': unit}, 'context': context})


class HandbookFiniteTests(unittest.TestCase):
    def test_edition_and_reviewed_source_coverage(self):
        rules=json.loads((ROOT/'rulesets/wangba-handbook-2026-07-30-finite.json').read_text(encoding='utf-8'))
        self.assertEqual([p['printed_page'] for p in rules['page_reviews']], list(range(248,271)))
        self.assertTrue(all(p['page_number_visually_confirmed'] for p in rules['page_reviews']))
        self.assertTrue(all(c['source']['visually_verified'] for c in rules['clauses']))

    def test_actual_small_boundary_decimal(self):
        self.assertEqual(run('0.2499999999999999999999','g_TNT',fictional=False)['energy_reference']['tier_id'],None)
        self.assertEqual(run('0.25','g_TNT',fictional=False)['energy_reference']['tier_id'],'brick-0')
        self.assertEqual(run('0.5','g_TNT',fictional=False)['energy_reference']['tier_id'],'brick-1')

    def test_real_city_boundary_and_no_7000_rounding_replacement(self):
        self.assertEqual(run('1399999.999999999999',fictional=False)['energy_reference']['tier_id'],'weak-street')
        self.assertEqual(run('1400000',fictional=False)['energy_reference']['tier_id'],'weak-city')
        self.assertEqual(run('9800000000',fictional=False)['energy_reference']['tier_id'],'weak-city')
        self.assertEqual(run('10000000000',fictional=False)['energy_reference']['tier_id'],'weak-country')

    def test_energy_units_legacy_and_common(self):
        for value,unit in [('1400000','t_TNT'),('1400000000','kg_TNT'),('1.4','Mt_TNT'),('1400','kt_TNT'),('5.8576e15','J'),('5.8576e12','kJ'),('5.8576e9','MJ'),('5857600','GJ')]:
            with self.subTest(unit=unit):
                self.assertEqual(run(value,unit,fictional=False)['energy_reference']['tier_id'],'weak-city')

    def test_force_and_power_never_become_energy(self):
        for unit in ['N','W','m/s','g','kg','t']:
            self.assertEqual(run('1e50',unit,fictional=False)['status'],'unsupported_quantity')

    def test_bare_mass_needs_explicit_tnt_equivalent(self):
        r=classify({'quantity':{'value':'1400000000','unit':'kg','equivalent':'TNT'},'context':{'fictional':False,'release':'violent'}})
        self.assertEqual(r['energy_reference']['tier_id'],'weak-city')

    def test_more_than_100_decimal_places_below_threshold_never_round_up(self):
        value='1399999.'+'9'*180
        r=run(value,fictional=False)
        self.assertEqual(r['energy_reference']['tier_id'],'weak-street')
        self.assertEqual(r['arithmetic']['decimal_precision'],1024)

    def test_fictional_missing_scale_withholds_final_tier(self):
        r=run('1400000')
        self.assertEqual(r['energy_reference']['tier_id'],'weak-city')
        self.assertIsNone(r['conclusion'])
        self.assertEqual(r['status'],'requires_review')

    def test_fictional_lower_of_energy_and_area(self):
        r=run('10000000000',fictional=True,geometry='built_area',area_m2='400000000',destruction_requirement_confirmed=True,material='RC')
        self.assertEqual(r['scale_reference']['tier_id'],'standard-city')
        self.assertEqual(r['conclusion']['tier_id'],'standard-city')
        low=run('200',fictional=True,geometry='built_area',area_m2='70000000',destruction_requirement_confirmed=True,material='RC')
        self.assertEqual(low['conclusion']['tier_id'],'weak-street')

    def test_area_boundary_weak_city(self):
        ctx=dict(fictional=True,geometry='built_area',destruction_requirement_confirmed=True,material='RC')
        self.assertEqual(run('1400000',area_m2='69999999.999999999999',**ctx)['conclusion']['tier_id'],'super-street')
        self.assertEqual(run('1400000',area_m2='70000000',**ctx)['conclusion']['tier_id'],'weak-city')

    def test_weak_city_volume_discrepancy_is_not_hidden(self):
        r=run('1400000',fictional=True,geometry='crater_volume',volume_m3='2220000000',destruction_requirement_confirmed=True)
        self.assertEqual(r['status'],'requires_review')
        self.assertTrue(any(a['code']=='weak_city_volume_rounding_conflict' for a in r['ambiguities']))
        self.assertIsNone(r['conclusion'])

    def test_above_country_requires_volume(self):
        r=run('7e13',fictional=True,geometry='built_area',area_m2='8e12',destruction_requirement_confirmed=True,material='RC')
        self.assertEqual(r['scale_reference']['tier_id'],'weak-country')
        self.assertNotEqual(r['conclusion']['tier_id'],'weak-continent')

    def test_country_volume_and_continent_geological_scope(self):
        ctx=dict(fictional=True,geometry='crater_volume',destruction_requirement_confirmed=True)
        r=run('7e13',volume_m3='121600000000000',**ctx)
        self.assertEqual(r['conclusion']['tier_id'],'standard-country')
        r=run('7e13',volume_m3='8e15',**ctx)
        self.assertEqual(r['status'],'requires_review')
        r=run('7e13',volume_m3='8e15',geological_requirement_confirmed=True,**ctx)
        self.assertEqual(r['conclusion']['tier_id'],'weak-continent')

    def test_giant_crater_exception_is_explicit(self):
        ctx=dict(fictional=True,geometry='crater_volume',volume_m3='8e15',destruction_requirement_confirmed=True,obvious_continental_giant_crater=True)
        self.assertEqual(run('7e13',**ctx)['conclusion']['tier_id'],'weak-continent')

    def test_material_equivalence_is_required(self):
        r=run('1400000',fictional=True,geometry='built_area',area_m2='70000000',material='wood',destruction_requirement_confirmed=True)
        self.assertEqual(r['status'],'requires_review')
        r=run('1400000',fictional=True,geometry='built_area',area_m2='70000000',material='wood',equivalent_area_m2='70000000',material_equivalence_confirmed=True,destruction_requirement_confirmed=True)
        self.assertEqual(r['conclusion']['tier_id'],'weak-city')

    def test_slow_release_grade_ambiguity(self):
        r=run('1400000',fictional=False,release='slow')
        self.assertIsNone(r['conclusion'])
        self.assertTrue(any(a['code']=='slow_release_grade_undefined' for a in r['ambiguities']))

    def test_unknown_release_withholds_final_classification(self):
        r=classify({'quantity':{'value':'1400000','unit':'t_TNT'},'context':{'fictional':False}})
        self.assertEqual(r['status'],'requires_review')
        self.assertIsNone(r['conclusion'])
        self.assertTrue(any(a['code']=='release_duration_unverified' for a in r['ambiguities']))

    def test_no_invented_energy_subtier_cutoffs(self):
        r=run('1200000',fictional=False)
        self.assertEqual(r['energy_reference']['tier_id'],'weak-street')
        self.assertTrue(r['energy_reference']['subtier_cutoffs_unspecified'])

    def test_equivalent_cloud_mass_scope(self):
        ctx=dict(fictional=True,geometry='equivalent_volume',destruction_requirement_confirmed=True,cloud=True,cloud_airflow_observed=False,droplet_mass_kg='1250000000')
        r=run('200',**ctx)
        self.assertEqual(r['scale_measurement']['equivalent_volume_m3'],'1250000')
        self.assertEqual(r['conclusion']['tier_id'],'weak-street')
        ctx['cloud_airflow_observed']=True
        self.assertEqual(run('200',**ctx)['status'],'requires_review')

    def test_building_collapse_exception_is_only_building(self):
        r=run('0.01','J',fictional=True,mechanism='impact_collapse',observed_building_collapse=True)
        self.assertEqual(r['conclusion']['label'],'楼级（直观坍塌豁免）')
        self.assertEqual(r['conclusion']['scope_limit'],'building_collapse_only')
        r=run('0.01','J',fictional=True,mechanism='material_fragmentation',observed_building_collapse=True)
        self.assertIsNone(r['conclusion'])

    def test_sequential_total_does_not_classify_as_one_hit(self):
        r=run('1400000',fictional=False,attack_pattern='sequential',attack_count='1000',duration_seconds='10')
        self.assertEqual(r['status'],'requires_review')
        self.assertEqual(r['attack_analysis']['single_attack_energy_j'],'5857600000000')
        self.assertEqual(r['attack_analysis']['average_power_w'],'585760000000000')
        self.assertIsNone(r['conclusion'])

    def test_distributed_blast_requires_per_scope_model(self):
        r=run('1e8',fictional=False,attack_pattern='distributed_simultaneous',attack_count='10000',area_m2='7e7')
        self.assertEqual(r['status'],'requires_review')
        self.assertEqual(r['attack_analysis']['scope_per_attack_m2'],'7000')
        self.assertTrue(any(a['code']=='distributed_scope_needs_energy_model' for a in r['ambiguities']))

    def test_fixed_binding_simultaneous_aggregation_is_conditional(self):
        r=run('3500000000000000000000',fictional=False,attack_pattern='distributed_simultaneous',fixed_binding_energy_confirmed=True)
        self.assertEqual(r['conclusion']['tier_id'],'weak-planet')
        self.assertEqual(r['attack_analysis']['aggregation'],'conditional_fixed_binding_energy')

    def test_sources_include_page_specific_clauses(self):
        r=run('1400000',fictional=True,geometry='built_area',area_m2='70000000',material='RC',destruction_requirement_confirmed=True)
        self.assertTrue(all('printed_page' in s and 'pdf_page' in s and s['sha256'] for s in r['sources']))
        self.assertIn(249,{s['printed_page'] for s in r['sources']})
        self.assertIn(250,{s['printed_page'] for s in r['sources']})
        self.assertIn(267,{s['printed_page'] for s in r['sources']})

    def test_invalid_inputs_do_not_make_a_tier(self):
        for value in ['NaN','Infinity','-1',True]:
            self.assertEqual(run(value,fictional=False)['status'],'invalid')
        self.assertEqual(classify({'quantity':{'min':'3','best':'2','max':'4','unit':'J'}})['status'],'invalid')


if __name__=='__main__':
    unittest.main()
