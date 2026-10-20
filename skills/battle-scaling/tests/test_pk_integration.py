import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from evidence import analyze_case,validate_case
from battle import render_report


def sample():
    estimate={'method':'reasoned_estimate','basis':'同速且胜负条件对称，未证明先手优势。',
              'evidence_ids':['rule'],'assumptions':['双方采用同一随机先手规则'],
              'outcomes':[{'outcome':'a','min':.4,'best':.5,'max':.6},
                          {'outcome':'b','min':.4,'best':.5,'max':.6}]}
    return {'schema_version':1,'case_id':'pk-routing-synthetic','fixture_kind':'synthetic',
            'characters':[{'id':x,'name':x,'version':'test-only','state':'active'} for x in ('a','b')],
            'sources':[{'id':'rule','title':'用户给定的合成规则','locator':'测试1',
                        'origin':'provided','access':'provided'}],'anchors':[],'edges':[],
            'matchup':{'win_paths':[], 'mode_assessments':{m:{'status':'reasoned_estimate',
                       'winner':'even','reasoning':'对称配置，先手未知。','evidence_ids':['rule'],
                       'win_estimate':copy.deepcopy(estimate)} for m in ('normal','highest','lowball')},
                       'mode_processes':{'normal':{'actors':[{'id':'a'},{'id':'b'}],
                         'steps':[], 'include_narrative':True,'private_marker':'DO_NOT_LEAK_STORY'}}}}


class PKIntegrationTests(unittest.TestCase):
    def test_default_overview_does_not_render_process_payload(self):
        result=analyze_case(sample(),'all')
        self.assertEqual(result['matchup']['presentation'],'overview')
        report=render_report(result)
        self.assertIn('合理区间',report)
        self.assertNotIn('DO_NOT_LEAK_STORY',report)
        self.assertNotIn('具体战斗过程',report)

    def test_typed_win_estimate_validated_without_raw_probability(self):
        packet=sample()
        self.assertEqual(validate_case(packet),[])
        packet['matchup']['mode_assessments']['normal']['win_estimate']['outcomes'][0]['best']=.9
        packet['matchup']['mode_assessments']['normal']['win_estimate']['outcomes'][0]['max']=.95
        self.assertTrue(any('sum to one' in x for x in validate_case(packet)))

    def test_blocked_assessment_cannot_expose_numeric_estimate(self):
        packet=sample();packet['sources'][0]['access']='blocked'
        result=analyze_case(packet)
        assessment=result['matchup']['assessment']
        self.assertEqual(assessment['win_estimate']['outcomes'],[])
        self.assertNotIn('约50%',render_report(result))

    def test_invalid_presentation_is_not_an_evidence_mode(self):
        packet=sample();packet['matchup']['presentation']='highest'
        self.assertTrue(any('presentation' in x for x in validate_case(packet)))

    def test_unreviewed_process_and_estimate_fields_are_rejected(self):
        packet=sample()
        packet['matchup']['process']={'narrative':'DO_NOT_LEAK_STORY'}
        packet['matchup']['win_estimate']=copy.deepcopy(packet['matchup']['mode_assessments']['normal']['win_estimate'])
        self.assertTrue(any('reserved' in x for x in validate_case(packet)))

    def test_unknown_access_never_supports_a_win_path(self):
        packet=sample();packet['sources'][0]['access']='not_found'
        packet['matchup']['win_paths']=[{'id':'w','winner':'a','evidence_ids':['rule'],
          'requirements':[{'status':'supported','evidence_ids':['rule']}]}]
        result=analyze_case(packet)['matchup']
        self.assertEqual(result['verdict'],'insufficient_evidence')
        self.assertFalse(result['assessment']['source_access_checked'])

    def test_read_access_is_consistent_between_assessment_and_estimate(self):
        packet=sample();packet['sources'][0]['access']='read'
        assessment=analyze_case(packet)['matchup']['assessment']
        self.assertTrue(assessment['source_access_checked'])
        self.assertEqual(assessment['win_estimate']['status'],'reasoned_estimate')

    def test_blocked_multiplier_does_not_propagate_a_supported_value(self):
        from test_evidence import packet
        data=packet();data['sources'].append({'id':'bad','title':'unread multiplier',
           'origin':'community','access':'blocked','locator':'unavailable'})
        data['edges']=[{'id':'boost','from':{'subject':'a','attribute':'attack_energy'},
           'to':{'subject':'b','attribute':'attack_energy'},'relation':'explicit',
           'conditions':{'explicit_relation':True},'evidence_ids':['s'],
           'multiplier':1e6,'multiplier_evidence_ids':['bad']}]
        self.assertFalse(any(c['subject']=='b' for c in analyze_case(data)['modes']['normal']['conclusions']))

    def test_explicit_process_without_input_reports_gap(self):
        packet=sample();packet['matchup']['presentation']='process'
        packet['matchup'].pop('mode_processes')
        result=analyze_case(packet)
        self.assertEqual(result['matchup']['process']['status'],'needs_process_input')
        self.assertIn('具体战斗过程',render_report(result))

    def test_cli_pk_override_and_auditable_run_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'case.json';out=base/'run'
            source.write_text(json.dumps(sample()),encoding='utf-8')
            run=subprocess.run([sys.executable,str(ROOT/'scripts/battle.py'),'analyze','--input',str(source),
                               '--mode','highest','--pk','process','--output',str(out)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads((out/'analysis.json').read_text(encoding='utf-8'))
            self.assertEqual(result['matchup']['presentation'],'process')
            ledger=json.loads((out/'run-ledger.json').read_text(encoding='utf-8'))
            self.assertEqual(ledger['presentation'],'process')
            self.assertIn('CASE.json',json.loads((out/'manifest.json').read_text(encoding='utf-8'))['files'])

    def test_initial_state_changes_conditions_fingerprint(self):
        from battle import export_case
        with tempfile.TemporaryDirectory() as folder:
            packet=sample()
            packet['matchup']['mode_processes']['normal']['actors'][0]['initial']={'state':'active'}
            out=Path(folder)
            export_case(analyze_case(packet),out/'one')
            packet['matchup']['mode_processes']['normal']['actors'][0]['initial']={'state':'incapacitated'}
            export_case(analyze_case(packet),out/'two')
            first=json.loads((out/'one/run-ledger.json').read_text(encoding='utf-8'))
            second=json.loads((out/'two/run-ledger.json').read_text(encoding='utf-8'))
            self.assertNotEqual(first['conditions_sha256'],second['conditions_sha256'])

    def test_simultaneous_action_rows_do_not_claim_exclusive_damage_causation(self):
        from combat_trace import run
        from test_combat_trace import request,attack
        result=run(request([attack(),attack('b','a')]))
        for row in result['trace'][0]['actions']:
            self.assertEqual(row['state_changes_scope'],'simultaneous_group_shared_outcome')


if __name__=='__main__':unittest.main()
