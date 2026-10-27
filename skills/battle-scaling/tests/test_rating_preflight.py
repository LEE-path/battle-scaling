"""Meaningful shared-gate tests: no ungraded winner, process, or writing readiness."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from rating_fixtures import with_independent_ratings, with_executed_ratings
from rating_preflight import review, _tier
from evidence import analyze_case
from writing_battle import run as writing
from combat_trace import run as process
from rating_fixtures import legacy_analyze_case as analyze_case  # Explicit legacy regression


def case():
    return {'schema_version':1, 'case_id':'independent-rating-gate-synthetic',
            'characters':[{'id':who,'name':who,'version':'one','state':'base','equipment':[]}
                          for who in ('a','b')], 'sources':[], 'anchors':[], 'edges':[],
            'matchup':{'teams':['a','b'],'win_paths':[]}}


def rated():
    return with_independent_ratings(case(), modes=('normal','highest','lowball'))


class RatingPreflightTests(unittest.TestCase):
    def check(self, packet, mode='normal'):
        return review(packet['characters'], packet['independent_ratings'], packet['sources'],
                      standard=packet.get('standard','wangba'), mode=mode)

    def test_legacy_nonempty_writing_labels_cannot_open_gate(self):
        request=json.loads((ROOT/'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))
        request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        request.pop('independent_ratings')
        result=writing(request)
        self.assertEqual(result['status'],'needs_independent_rating')
        self.assertFalse(result['narrative_generated'])
        self.assertEqual(result['rating_preflight']['status'],'needs_research')

    def test_missing_ratings_never_yield_winner_probability_or_trace(self):
        for presentation in ('overview','process'):
            request=case();request['matchup']['presentation']=presentation
            request['sources']=[{'id':'s','title':'Synthetic action','origin':'synthetic',
                                 'access':'provided','locator':'fixture action'}]
            request['matchup']['win_paths']=[{'id':'declared-win','winner':'a','evidence_ids':['s'],
                                             'requirements':[]}]
            result=analyze_case(request)['matchup']
            self.assertEqual(result['verdict'],'needs_independent_rating')
            self.assertIsNone(result['assessment'])
            self.assertEqual(result['win_paths'],[])
            self.assertFalse(result['combat_analysis_started'])
            self.assertNotIn('probability',result)
            if presentation=='process':self.assertEqual(result['process']['trace'],[])

    def test_standalone_process_is_gated_before_state_execution(self):
        request={'actors':[{'id':'a'},{'id':'b'}], 'sources':[], 'steps':[]}
        with patch('combat_trace._Trace') as trace:
            result=process(request)
        trace.assert_not_called()
        self.assertEqual(result['status'],'needs_independent_rating')
        self.assertNotIn('final_state',result)
        self.assertEqual(result['trace'],[])

    def test_single_character_rating_analysis_remains_available_without_dossiers(self):
        request=case();request.pop('matchup');request['characters']=request['characters'][:1]
        result=analyze_case(request)
        self.assertEqual(result['modes']['normal']['conclusions'],[])
        self.assertNotIn('matchup',result)

    def test_conservative_lower_bounds_with_unknown_ceiling_are_accepted(self):
        request=rated()
        for row in request['independent_ratings']:
            row['main_tier']['ceiling_notes']='Unknown ceiling; the shown lower bound is established.'
            row['dimensions']['体量']['label']='成人体型'
            row['dimensions']['体量']['mass_notes']='No measured mass; a fake number is unnecessary.'
        result=self.check(request)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['accepted_subject_ids'],['a','b'])
        self.assertFalse(result['source_authenticity_verified'])
        self.assertFalse(result['semantic_rating_verified'])

    def test_known_upper_bound_does_not_substitute_for_established_floor(self):
        request=rated();request['independent_ratings'][0]['main_tier']['basis']='upper_bound'
        self.assertEqual(self.check(request)['status'],'needs_research')
        request['independent_ratings'][0]['main_tier']['basis']='lower_bound'
        request['independent_ratings'][0]['main_tier']['upper_bound']={'label':'标准爆楼','basis':'upper_bound'}
        self.assertEqual(self.check(request)['status'],'ready')

    def test_each_dimension_main_tier_scope_and_acceptance_are_required(self):
        mutations=[lambda row:row.pop('main_tier'),
                   lambda row:row['dimensions'].pop('体防'),
                   lambda row:row.update(version='another-version'),
                   lambda row:row.update(state='exhausted'),
                   lambda row:row.update(equipment=['unearned stone']),
                   lambda row:row['host_review'].update(status='pending'),
                   lambda row:row['host_review'].pop('dossier_ref')]
        for mutation in mutations:
            request=rated();mutation(request['independent_ratings'][0])
            with self.subTest(mutation=mutation):self.assertEqual(self.check(request)['status'],'needs_research')

    def test_unknown_vague_or_wrong_standard_tiers_do_not_pass(self):
        for label in ('未知','楼级','爆墙以上','约爆楼','unknown','9-B (Wall level)'):
            request=rated();request['independent_ratings'][0]['dimensions']['输出']['label']=label
            with self.subTest(label=label):self.assertEqual(self.check(request)['status'],'needs_research')
        request=rated();request['independent_ratings'][0]['dimensions']['智力']['label']='待核'
        self.assertEqual(self.check(request)['status'],'needs_research')

    def test_existing_display_aliases_and_selected_high_standard(self):
        for label in ('弱爆楼','标准爆楼','超爆楼','论外'):
            self.assertTrue(_tier(label,'wangba'),label)
        for label in ('弱爆爆楼','爆论外'):
            self.assertFalse(_tier(label,'wangba'),label)
        new='high-wangba-handbook-2026-07-30-new'
        self.assertTrue(_tier('天花板最上','wangba',new))
        self.assertFalse(_tier('天花板最上','wangba'))
        self.assertFalse(_tier('天花板最上','wangba','high-wangba-handbook-2026-07-30-aos'))
        request=rated()
        row=request['independent_ratings'][0]
        row['ruleset']=new
        row['main_tier']['label']='天花板最上'
        self.assertEqual(self.check(request)['status'],'ready')
        row['main_tier']['ruleset']='high-wangba-handbook-2026-07-30-aos'
        self.assertEqual(self.check(request)['status'],'needs_research')

    def test_vague_nonenergy_labels_require_research_but_specific_categories_do_not(self):
        for field,label in (('速度','高速'),('速度','极快'),('智力','高等超人类'),('体量','人形')):
            request=rated();request['independent_ratings'][0]['dimensions'][field]['label']=label
            with self.subTest(field=field,label=label):
                self.assertEqual(self.check(request)['status'],'needs_research')
        request=rated()
        for field,label in (('速度','超音速'),('智力','普通智力'),('体量','成年男性尺度')):
            request['independent_ratings'][0]['dimensions'][field]['label']=label
        self.assertEqual(self.check(request)['status'],'ready')

    def test_author_override_preserves_remaining_canon_and_mixed_derivations(self):
        request=rated()
        request['sources'].append({'id':'author-change','origin':'author_settings','access':'provided',
                                  'locator':'Synthetic author changes one ability only'})
        row=request['independent_ratings'][0]
        ability=row['dimensions']['特殊技能']
        ability.update(basis_type='author_settings',evidence_ids=['author-change'])
        self.assertEqual(self.check(request)['status'],'ready')
        ability['basis_type']='canon'
        self.assertEqual(self.check(request)['status'],'needs_research')
        ability.update(basis_type='mixed',evidence_ids=['author-change'])
        self.assertEqual(self.check(request)['status'],'needs_research')
        ability['evidence_ids'].append('independent-rating-fixture')
        self.assertEqual(self.check(request)['status'],'ready')
        row['basis_type']='author_settings'
        self.assertEqual(self.check(request)['status'],'needs_research')
        for node in [row['main_tier'],*row['dimensions'].values()]:
            node.setdefault('basis_type','canon')
        self.assertEqual(self.check(request)['status'],'ready')

    def test_unregistered_vsb_ruleset_does_not_certify_tier(self):
        self.assertFalse(_tier('9-B','vsb','vsb-invented'))
        self.assertTrue(_tier('9-B','vsb','vsb-current-2026-10-21'))

    def test_iq_and_experience_cannot_be_explosive_tiers(self):
        for field in ('智力','战斗智商','经验'):
            request=rated();request['independent_ratings'][0]['dimensions'][field].update(kind='tier',label='标准爆墙')
            self.assertEqual(self.check(request)['status'],'needs_research')

    def test_unread_indexed_missing_and_wrongly_authored_sources_are_blocked(self):
        for access in ('blocked','unread','unknown','indexed'):
            request=rated();request['sources'][0]['access']=access
            with self.subTest(access=access):self.assertEqual(self.check(request)['status'],'needs_research')
        request=rated();request['sources']=[]
        self.assertEqual(self.check(request)['status'],'needs_research')
        request=rated();request['sources'][0]['origin']='author_settings'
        self.assertEqual(self.check(request)['status'],'needs_research')

    def test_genuine_non_applicability_needs_sourced_concrete_alternative(self):
        request=rated();row=request['independent_ratings'][0]['dimensions']['体防']
        row.update(not_applicable=True,reasoning='Defined as a bodiless text construct in the invented source.')
        self.assertEqual(self.check(request)['status'],'needs_research')
        row['alternative']={'kind':'level','label':'依靠文本载体存续的无实体形态','basis':'lower_bound',
                            'reasoning':'The source fixes survival through its text carrier; no bodily HP.',
                            'evidence_ids':['independent-rating-fixture']}
        self.assertEqual(self.check(request)['status'],'ready')
        row['alternative']['label']='特殊，无法衡量'
        self.assertEqual(self.check(request)['status'],'needs_research')

    def test_authored_original_complete_ratings_preserve_writing_features(self):
        request=json.loads((ROOT/'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))
        request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        request = with_executed_ratings(request)
        result=writing(request)
        self.assertEqual(result['status'],'structure_checked')
        self.assertEqual(result['fixed_ending']['winner'],'lan')
        self.assertFalse(result['canon_evidence'])
        self.assertTrue(result['rating_preflight']['host_acceptance_is_declaration'])

    def test_vsb_uses_its_own_named_tiers_and_per_mode_scope(self):
        request=case();request['standard']='vsb'
        request=with_independent_ratings(request)
        self.assertEqual(self.check(request)['status'],'ready')
        self.assertEqual(self.check(request,'highest')['status'],'needs_research')
        request['independent_ratings'][0]['main_tier']['label']='标准爆墙'
        self.assertEqual(self.check(request)['status'],'needs_research')

    def test_gate_does_not_modify_inputs_or_accept_external_ready_boolean(self):
        request=rated();before=copy.deepcopy(request)
        self.check(request);self.assertEqual(before,request)
        request=case();request['rating_preflight']={'status':'ready'}
        self.assertEqual(analyze_case(request)['matchup']['verdict'],'needs_independent_rating')

    def test_accepted_ratings_allow_actual_process_without_skipping_other_gates(self):
        request={'mode':'normal','actors':[{'id':who,'version':'one','state':'base','equipment':[],
                  'initial':{'state':'active'}} for who in ('a','b')], 'sources':[], 'steps':[]}
        request=with_independent_ratings(request)
        result=process(request)
        self.assertEqual(result['rating_preflight']['status'],'ready')
        self.assertIn('final_state',result)


if __name__=='__main__':unittest.main()
