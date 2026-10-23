import contextlib,copy,io,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from evidence import analyze_case,validate_case
from rating_fixtures import rated_fixture, rated_call
analyze_case = rated_call(analyze_case)
from battle import main,render_report,export_case,compute_case
from rating_fixtures import legacy_analyze_case
analyze_case = rated_call(legacy_analyze_case)  # Historical mode with real fixture ratings
from rating_fixtures import legacy_compute_case as compute_case

@rated_fixture
def case(rank=2):
    request=json.loads((ROOT/'assets/cases/hax-ceiling-synthetic.json').read_text(encoding='utf-8'))
    request.update(actor_id='a',target_id='b')
    request['target_level']['rank']=rank
    request['sources'][0]['locator']='Synthetic rules sections 1-4'
    source=request['sources'][0]
    estimate={'method':'reasoned_estimate','basis':'synthetic conditional estimate','evidence_ids':['source'],
        'assumptions':[],'outcomes':[{'outcome':'a','min':.6,'best':.7,'max':.8},{'outcome':'b','min':.2,'best':.3,'max':.4}]}
    assessment={'winner':'a','status':'reasoned_estimate','reasoning':'synthetic control path',
        'evidence_ids':['source'],'hax_requirements':['control'],'win_estimate':estimate}
    return {'schema_version':1,'case_id':'synthetic-hax-integration','fixture_kind':'synthetic',
      'characters':[{'id':who,'name':who,'version':'synthetic-v1','state':'active'} for who in ('a','b')],
      'sources':[source],'anchors':[],'edges':[],
      'hax_checks':[{'id':'control','request':request}],
      'matchup':{'win_paths':[{'id':'control-path','winner':'a','is_hax':True,'hax_requirements':['control'],
        'evidence_ids':['source'],'requirements':[{'claim':'mechanism','status':'supported','evidence_ids':['source']}]}],
        'mode_assessments':{mode:copy.deepcopy(assessment) for mode in ('normal','highest','lowball')}}}

class HaxIntegrationTests(unittest.TestCase):
    def test_target_within_both_caps_can_use_reviewed_path(self):
        result=analyze_case(case())
        self.assertEqual(result['matchup']['verdict'],'a')
        self.assertEqual(result['matchup']['win_paths'][0]['hax_review']['status'],'supported_by_packet')

    def test_world_ceiling_blocks_every_mode_and_withdraws_host_estimate(self):
        packet=case(4)
        for report in analyze_case(packet,'all')['matchups'].values():
            self.assertEqual(report['win_paths'][0]['reviewed_status'],'blocked')
            self.assertIsNone(report['assessment']['winner'])
            self.assertEqual(report['assessment']['win_estimate']['outcomes'],[])
        self.assertNotIn('约70%',render_report(analyze_case(packet,'all')))

    def test_world_star_does_not_promote_city_ability_to_star(self):
        self.assertEqual(analyze_case(case(3))['matchup']['win_paths'][0]['reviewed_status'],'blocked')

    def test_hax_assumptions_follow_the_exported_numeric_estimate(self):
        packet=case()
        packet['hax_checks'][0]['request']['checks']['compatibility']={
            'state':'unknown','explanation':'cross-fiction mechanism is not established',
            'assumption':'Assume both source types are compatible in this branch.'}
        result=analyze_case(packet)
        assessment=result['matchup']['assessment']
        self.assertEqual(assessment['status'],'conditional')
        estimate=assessment['win_estimate']
        self.assertEqual(estimate['status'],'conditional')
        self.assertIn('Assume both source types are compatible in this branch.',estimate['assumptions'])
        self.assertTrue(estimate['outcomes'])
        self.assertIn('条件分支',render_report(result))

    def test_macro_cannot_reuse_an_opponents_ability_review(self):
        packet=case()
        packet['matchup']['win_paths'][0]['winner']='b'
        packet['matchup']['mode_assessments']['normal']['winner']='b'
        result=analyze_case(packet)
        self.assertEqual(result['matchup']['win_paths'][0]['reviewed_status'],'blocked')
        self.assertIsNone(result['matchup']['assessment']['winner'])
        self.assertEqual(result['matchup']['assessment']['win_estimate']['outcomes'],[])

    def test_macro_can_explicitly_attribute_an_allied_ability(self):
        packet=case()
        packet['characters'].append({'id':'ally','name':'ally','version':'synthetic-v1','state':'active'})
        packet['hax_checks'][0]['request']['actor_id']='ally'
        for node in (packet['matchup']['win_paths'][0],packet['matchup']['mode_assessments']['normal']):
            node.update(ability_owner='ally',affected_target='b')
        self.assertEqual(analyze_case(packet)['matchup']['verdict'],'a')

    def test_team_outcome_does_not_supply_an_ability_owner(self):
        packet=case()
        packet['matchup']['win_paths'][0]['winner']='team-a'
        packet['matchup']['mode_assessments']['normal']['winner']='team-a'
        result=analyze_case(packet)
        self.assertEqual(result['matchup']['verdict'],'insufficient_evidence')
        self.assertIsNone(result['matchup']['assessment']['winner'])
        packet['hax_checks'][0]['request'].pop('actor_id')
        self.assertTrue(validate_case(packet))

    def test_computation_attach_inherits_a_rejected_hax_dependency(self):
        packet=case(4);packet.pop('matchup')
        packet['computations']=[{'id':'blocked-hax-work','type':'physics','is_hax':True,'hax_requirements':['control'],
            'request':{'model':'kinetic','inputs':{'mass':1,'speed':2}},
            'attach':{'id':'leaked-output','subject':'a','attribute':'output','kind':'calculation',
                      'evidence_ids':['source'],'result_path':'result'}}]
        computed=compute_case(packet)
        self.assertEqual(computed['anchors'][0]['hax_requirements'],['control'])
        result=analyze_case(computed)
        self.assertEqual(result['modes']['normal']['conclusions'],[])
        self.assertEqual(result['computations'],[])
        self.assertTrue(validate_case({**packet,'computations':[{**packet['computations'][0],'hax_requirements':['missing']}]}))

    def test_rejected_hax_high_result_is_not_displayed_as_adopted(self):
        packet=case(4);packet.pop('matchup')
        packet['computations']=[{'id':'blocked-high','type':'high','mode':'normal','is_hax':True,'hax_requirements':['control'],
                               'output':{'status':'mapped','result':{'claim':'REJECTED_HIGH_MARKER'}}}]
        result=analyze_case(packet)
        self.assertEqual(result['modes']['normal']['high_results'],[])
        self.assertNotIn('REJECTED_HIGH_MARKER',render_report(result))

    def test_assumed_highest_does_not_override_known_cap(self):
        packet=case(4);packet['matchup']['win_paths'][0]['assumptions']=['ignore all hax ceilings']
        self.assertEqual(analyze_case(packet,'highest')['matchup']['win_paths'][0]['reviewed_status'],'blocked')

    def test_blocked_hax_is_not_an_automatic_opponent_win(self):
        self.assertEqual(analyze_case(case(4))['matchup']['verdict'],'insufficient_evidence')

    def test_independent_physical_win_path_is_preserved(self):
        packet=case(4)
        packet['matchup']['win_paths'].append({'id':'physical','winner':'b','evidence_ids':['source'],
            'requirements':[{'status':'supported','evidence_ids':['source']} ]})
        self.assertEqual(analyze_case(packet)['matchup']['verdict'],'b')

    def test_nested_requirement_also_obeys_ceiling(self):
        packet=case(4);path=packet['matchup']['win_paths'][0]
        path.pop('hax_requirements');path.pop('is_hax')
        path['requirements'][0].update(is_hax=True,hax_requirements=['control'])
        self.assertEqual(analyze_case(packet)['matchup']['win_paths'][0]['reviewed_status'],'blocked')

    def test_qualitative_or_anchor_cannot_bypass_check(self):
        packet=case(4);packet.pop('matchup')
        packet['anchors']=[{'id':'hax-ap','subject':'a','attribute':'special_effect_scope','kind':'credible_feat',
          'quantity':{'kind':'tier','ruleset':'synthetic-v1','label':'invented','rank':4},'evidence_ids':['source'],
          'is_hax':True,'hax_requirements':['control']}]
        packet['qualitative_claims']=[{'id':'q','subject':'a','claim':'BLOCKED_HAX_CLAIM_MARKER',
          'evidence_ids':['source'],'is_hax':True,'hax_requirements':['control']}]
        result=analyze_case(packet)
        self.assertEqual(result['modes']['normal']['conclusions'],[])
        self.assertEqual(result['modes']['normal']['qualitative_claims'],[])
        self.assertNotIn('BLOCKED_HAX_CLAIM_MARKER',render_report(result))

    def test_unreviewed_declared_hax_is_not_supported(self):
        packet=case();packet['matchup']['win_paths'][0].pop('hax_requirements')
        self.assertEqual(analyze_case(packet)['matchup']['win_paths'][0]['reviewed_status'],'conditional')

    def test_dangling_or_nested_override_is_rejected(self):
        packet=case();packet['matchup']['win_paths'][0]['hax_requirements']=['missing']
        self.assertTrue(validate_case(packet))
        packet=case();packet['matchup']['mode_processes']={'normal':{'hax_checks':[]}}
        self.assertTrue(validate_case(packet))

    def test_output_contains_hax_ledger_and_cli_router(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);request=base/'hax.json';request.write_text(json.dumps(case()['hax_checks'][0]['request']),encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['hax','--input',str(request),'--output',str(base/'check.json')]),0)
                export_case(analyze_case(case()),base/'run')
            self.assertEqual(json.loads((base/'check.json').read_text(encoding='utf-8'))['status'],'supported_by_packet')
            manifest=json.loads((base/'run/manifest.json').read_text(encoding='utf-8'))
            self.assertIn('hax-checks.json',manifest['files'])

if __name__=='__main__':unittest.main()
