"""Admit existing astronomical names without inventing missing finite tiers."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from handbook_finite import classify
from rating_fixtures import with_independent_ratings
from rating_preflight import _tier, review


def packet():
    request = with_independent_ratings({
        'characters': [{'id': 'astro', 'version': 'synthetic-v1',
                        'state': 'active', 'equipment': []}],
        'sources': [],
    })
    row = request['independent_ratings'][0]
    for node in [row['main_tier'], *(row['dimensions'][field]
                                   for field in ('输出', '体防', '破坏'))]:
        node['label'] = '标准星系'
        node['reasoning'] = ('The explicit invented source establishes this character '
                             'property independently; the handbook supplies its name only.')
    return request


def gate(request):
    return review(request['characters'], request['independent_ratings'],
                  request['sources'], mode='normal')


class AstronomicalAdmissionTests(unittest.TestCase):
    def test_actual_astronomical_rows_and_existing_display_aliases(self):
        rules = json.loads((ROOT / 'rulesets' /
                            'wangba-handbook-2026-07-30-finite.json').read_text(encoding='utf-8'))
        self.assertTrue(rules['astronomical_references'])
        for row in rules['astronomical_references']:
            with self.subTest(tier_id=row['id']):
                self.assertTrue(_tier(row['label'], 'wangba'))
                alias = row['label'].replace('标准', '标')
                self.assertTrue(_tier(alias, 'wangba'))
                self.assertTrue(_tier(alias[:1] + '爆' + alias[1:], 'wangba'))
        # Existing display normalization still applies without creating new rows.
        for label in ('弱爆楼', '标准爆楼', '强爆楼', '超爆楼', '标准爆恒星',
                      '标准星系', '标星系', '标准爆星系'):
            with self.subTest(label=label):
                self.assertTrue(_tier(label, 'wangba'))

    def test_missing_subdivisions_unknown_and_annotated_labels_remain_blocked(self):
        for label in ('弱恒星', '强恒星', '超恒星', '弱爆恒星', '强爆恒星',
                      '超爆恒星', '弱星系', '强星系', '超星系', '弱爆星系',
                      '强爆星系', '超爆星系', '标准银河系', '银河系', '标准爆未知星体',
                      '未定', '高阶基底', '标准恒星（任意说明）', '标准恒星(任意说明)',
                      '标准星系（任意说明）', '标准星系(任意说明)',
                      '标准爆爆恒星', '标准恒星（能量/尺度条件判定）'):
            with self.subTest(label=label):
                self.assertFalse(_tier(label, 'wangba'))

    def test_wangba_and_vsb_names_do_not_cross_standards(self):
        for label in ('标准恒星', '标恒星', '标准爆恒星', '标准星系', '标准爆星系'):
            with self.subTest(label=label):
                self.assertFalse(_tier(label, 'vsb'))
        self.assertTrue(_tier('4-C (Star level)', 'vsb'))
        self.assertFalse(_tier('4-C (Star level)', 'wangba'))

    def test_qualitative_galaxy_is_mirrored_without_a_numeric_threshold(self):
        runtime = json.loads((ROOT / 'rulesets' /
                              'wangba-handbook-2026-07-30-finite.json').read_text(encoding='utf-8'))
        curated = json.loads((ROOT / 'data/wangba-handbook-2026-07-30' /
                              'finite-rules-curated.json').read_text(encoding='utf-8'))
        self.assertEqual(runtime.pop('curation_file'),
                         'data/wangba-handbook-2026-07-30/finite-rules-curated.json')
        self.assertEqual(runtime, curated)
        rows = runtime['qualitative_astronomical_references']
        self.assertEqual([row['label'] for row in rows], ['标准星系', '单体宇宙'])
        row = rows[0]
        clause = next(c for c in runtime['clauses'] if c['id'] == row['clause_id'])
        self.assertEqual(row['clause_id'], 'F250-ASTRO')
        self.assertEqual(row['definition'],
                         '银河系全部正发光恒星引力结合能总和，不计白矮星/中子星/黑洞。')
        self.assertEqual(row['source'], clause['source'])
        self.assertFalse(row['energy_only_mapping_allowed'])
        self.assertNotIn('energy_j', row)
        self.assertNotIn('rank', row)

    def test_single_universe_is_a_qualitative_name_not_an_energy_conversion(self):
        rules = json.loads((ROOT / 'rulesets' /
                            'wangba-handbook-2026-07-30-finite.json').read_text(encoding='utf-8'))
        row = next(r for r in rules['qualitative_astronomical_references']
                   if r['id'] == 'single-universe')
        clause = next(c for c in rules['clauses'] if c['id'] == row['clause_id'])
        self.assertTrue(row['requires_actual_infinite_extent'])
        self.assertFalse(row['energy_only_mapping_allowed'])
        self.assertEqual(row['source'], clause['source'])
        self.assertNotIn('energy_j', row)
        for label in ('单体宇宙', '单体'):
            self.assertTrue(_tier(label, 'wangba'))
            self.assertFalse(_tier(label, 'vsb'))
        for label in ('弱单体宇宙', '标准单体宇宙', '超单体宇宙', '单体宇宙（任意说明）'):
            self.assertFalse(_tier(label, 'wangba'))
        request = packet()
        for node in [request['independent_ratings'][0]['main_tier'],
                     *(request['independent_ratings'][0]['dimensions'][field]
                       for field in ('输出', '体防', '破坏'))]:
            node['label'] = '单体宇宙'
        self.assertEqual(gate(request)['status'], 'ready')
        result = classify({'quantity': {'value': '1e300', 'unit': 'J'},
                           'context': {'release': 'violent', 'fictional': False}})
        self.assertEqual(result['conclusion']['tier_id'], 'standard-star')
        self.assertTrue(result['conclusion']['table_ceiling_exceeded'])

    def test_large_energy_does_not_produce_a_qualitative_galaxy_tier(self):
        request = {'quantity': {'value': '1e100', 'unit': 'J'},
                   'context': {'release': 'violent', 'fictional': False}}
        result = classify(request)
        self.assertEqual(result['status'], 'reference_mapping')
        self.assertEqual(result['conclusion']['tier_id'], 'standard-star')
        self.assertEqual(result['conclusion']['label'], '标准恒星')
        self.assertTrue(result['conclusion']['table_ceiling_exceeded'])
        request['context'].update(fictional=True, geometry='verified_scope',
                                  scale_tier_id='standard-galaxy',
                                  destruction_requirement_confirmed=True)
        self.assertEqual(classify(request)['status'], 'invalid')

    def test_complete_independent_astro_rating_passes_real_preflight(self):
        request = packet()
        before = copy.deepcopy(request)
        result = gate(request)
        self.assertEqual(result['status'], 'ready', result['needs'])
        self.assertEqual(result['accepted_subject_ids'], ['astro'])
        self.assertEqual(request, before)
        for field in ('main_tier', '输出', '体防', '破坏'):
            unknown = copy.deepcopy(request)
            row = unknown['independent_ratings'][0]
            node = row['main_tier'] if field == 'main_tier' else row['dimensions'][field]
            node['label'] = '标准爆未知星体'
            with self.subTest(field=field):
                result = gate(unknown)
                self.assertEqual(result['status'], 'needs_research')
                self.assertIn('must name one specific tier', ' '.join(result['needs']))

    def test_handbook_reference_does_not_become_character_property(self):
        mapped = classify({'quantity': {'value': '1e41', 'unit': 'J'},
                           'context': {'release': 'violent', 'geometry': 'verified_scope',
                                       'scale_tier_id': 'standard-star',
                                       'destruction_requirement_confirmed': True}})
        self.assertEqual(mapped['status'], 'conditional_mapping')
        self.assertEqual(mapped['conclusion']['label'], '标准恒星')
        self.assertEqual(mapped['conclusion']['clause_id'], 'F250-ASTRO')
        request = packet()
        request['independent_ratings'][0]['main_tier'].update(mapped['conclusion'])
        result = gate(request)
        self.assertEqual(result['status'], 'needs_research')
        self.assertIn('does not prove a character property', ' '.join(result['needs']))
        self.assertIn('Wangba energy reference', ' '.join(result['needs']))


if __name__ == '__main__':
    unittest.main()
