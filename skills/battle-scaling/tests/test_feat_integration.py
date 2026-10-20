import contextlib,copy,hashlib,io,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from evidence import analyze_case,validate_case
from battle import main,export_case


def case():
    return {'schema_version':1,'case_id':'feat-review-integration','fixture_kind':'synthetic',
      'characters':[{'id':x,'name':x,'version':'v1','state':'scene-state'} for x in ('a','b')],
      'sources':[{'id':'s','title':'自创规则','origin':'synthetic','access':'provided','locator':'§1'}],
      'anchors':[{'id':'observed','subject':'a','attribute':'raw_energy','kind':'credible_feat',
                  'quantity':{'value':100,'unit':'J'},'evidence_ids':['s'],
                  'review_requirements':[{'review_id':'r','use':'observed_output'}]}],
      'edges':[], 'feat_reviews':[{'id':'r','request':{
         'event':{'actor_id':'a','version':'v1','state':'scene-state','locator':'§1'},
         'requested_uses':['observed_output']}}]}


def audit(status='supported_by_packet',use='observed_output'):
    return {'schema_version':1,'status':status,'admissions':{use:{'status':status,
        'reasons':['synthetic reviewed premise'],'assumptions':['本分支明确假设'] if status=='conditional' else [],
        'source_ids':['s']}},'validation_scope':'packet only','research_tasks':[]}


class FeatIntegrationTests(unittest.TestCase):
    def test_blocked_review_removes_only_dependent_anchor(self):
        data=case();data['anchors'].append({'id':'independent','subject':'b','attribute':'raw_energy',
            'kind':'credible_feat','quantity':{'value':50,'unit':'J'},'evidence_ids':['s']})
        with patch('feat_audit.run',return_value=audit('blocked')):
            result=analyze_case(data,'all')
        for mode in result['modes'].values():
            self.assertEqual([x['subject'] for x in mode['conclusions']],['b'])
            self.assertTrue(any(x['reason']=='feat_review_blocked' for x in mode['excluded']))

    def test_conditional_review_propagates_assumptions_and_trace(self):
        with patch('feat_audit.run',return_value=audit('conditional')):
            out=analyze_case(case())['modes']['normal']['conclusions'][0]
        self.assertEqual(out['status'],'conditional')
        self.assertIn('本分支明确假设',out['assumptions'])
        self.assertEqual(out['review_trace'][0]['review_id'],'r')

    def test_rejected_edge_does_not_propagate_in_highest(self):
        data=case();data['anchors'][0].pop('review_requirements')
        data['feat_reviews'][0]['request']['requested_uses']=['full_effort']
        data['edges']=[{'id':'scale','from':{'subject':'a','attribute':'raw_energy'},
          'to':{'subject':'b','attribute':'raw_energy'},'relation':'explicit',
          'conditions':{'explicit_relation':True},'evidence_ids':['s'],
          'review_requirements':[{'review_id':'r','use':'full_effort'}]}]
        with patch('feat_audit.run',return_value=audit('blocked','full_effort')):
            out=analyze_case(data,'highest')['modes']['highest']
        self.assertEqual([x['subject'] for x in out['conclusions']],['a'])

    def test_case_injects_mode_and_sources(self):
        data=case();data['feat_reviews'][0]['request'].update(mode='spoof',sources=[{'id':'spoof'}])
        with patch('feat_audit.run',return_value=audit()) as worker:analyze_case(data,'lowball')
        self.assertEqual(worker.call_args.args[0]['mode'],'lowball')
        self.assertEqual(worker.call_args.args[0]['sources'],data['sources'])

    def test_review_for_wrong_actor_is_rejected(self):
        data=case();data['feat_reviews'][0]['request']['event']['actor_id']='b'
        self.assertTrue(any('actor' in e for e in validate_case(data)))

    def test_cross_state_needs_explicit_state_transfer_review(self):
        data=case();data['characters'][0]['state']='prime'
        with patch('feat_audit.run',return_value=audit()):out=analyze_case(data)
        self.assertEqual(out['modes']['normal']['conclusions'],[])
        self.assertTrue(any(x['reason']=='feat_review_scope_mismatch' for x in out['modes']['normal']['excluded']))

    def test_dangling_review_and_wrong_use_are_not_silently_ignored(self):
        data=case();data['anchors'][0]['review_requirements'][0].update(review_id='missing',use='omniscient')
        self.assertTrue(validate_case(data))

    def test_unknown_admission_is_not_automatically_accepted_in_highest(self):
        with patch('feat_audit.run',return_value=audit('undetermined')):
            result=analyze_case(case(),'all')
        for report in result['modes'].values():self.assertEqual(report['conclusions'],[])

    def test_rejected_qualitative_claim_does_not_leak_via_top_level(self):
        from battle import render_report
        data=case();data['anchors']=[]
        data['qualitative_claims']=[{'id':'q','subject':'a','claim':'REJECTED_CLAIM_MARKER',
          'evidence_ids':['s'],'review_requirements':[{'review_id':'r','use':'observed_output'}]}]
        with patch('feat_audit.run',return_value=audit('blocked')):result=analyze_case(data)
        self.assertEqual(result['modes']['normal']['qualitative_claims'],[])
        self.assertNotIn('REJECTED_CLAIM_MARKER',render_report(result))

    def test_transfer_review_must_name_actual_target_state(self):
        data=case();data['characters'][0]['state']='prime'
        review=data['feat_reviews'][0]['request']
        review.update(requested_uses=['state_transfer'],state_transfer={'target_state':'some-other-state'})
        data['anchors'][0]['review_requirements']=[{'review_id':'r','use':'state_transfer'}]
        with patch('feat_audit.run',return_value=audit('supported_by_packet','state_transfer')):
            result=analyze_case(data)
        self.assertEqual(result['modes']['normal']['conclusions'],[])

    def test_capacity_upper_needs_upper_bound_admission_not_just_observed(self):
        data=case();data['anchors'][0]['bound']='upper'
        with patch('feat_audit.run',return_value=audit()):result=analyze_case(data)
        self.assertEqual(result['modes']['normal']['conclusions'],[])

    def test_cross_state_edge_checks_destination_not_source_state(self):
        data=case();data['anchors'][0].pop('review_requirements')
        data['characters'][1].update(state='prime',version='v2')
        data['feat_reviews'][0]['request'].update(requested_uses=['state_transfer'],
            state_transfer={'target_state':'prime','target_version':'v2'})
        data['edges']=[{'id':'restore','from':{'subject':'a','attribute':'raw_energy'},
            'to':{'subject':'b','attribute':'raw_energy'},'relation':'explicit',
            'conditions':{'explicit_relation':True},'evidence_ids':['s'],
            'review_requirements':[{'review_id':'r','use':'state_transfer'}]}]
        with patch('feat_audit.run',return_value=audit('conditional','state_transfer')):
            result=analyze_case(data)
        inherited=next(x for x in result['modes']['normal']['conclusions'] if x['subject']=='b')
        self.assertEqual(inherited['status'],'conditional')

    def test_event_measurement_upper_is_labelled_without_claiming_capacity(self):
        data=case();data['anchors'][0].update(bound='upper',claim_scope='event')
        with patch('feat_audit.run',return_value=audit()):result=analyze_case(data)
        self.assertEqual(result['modes']['normal']['conclusions'][0]['claim_scope'],'event')

    def test_unreviewed_legacy_anchor_is_not_marked_reviewed(self):
        data=case();data.pop('feat_reviews');data['anchors'][0].pop('review_requirements')
        out=analyze_case(data)['modes']['normal']
        self.assertEqual(out['feat_review_coverage']['unreviewed_anchor_ids'],['observed'])
        self.assertEqual(out['conclusions'][0]['quantity']['best'],100)

    def test_declared_qualitative_source_reference_is_checked(self):
        data=case();data['qualitative_claims']=[{'claim':'test','evidence_ids':['missing']}]
        self.assertTrue(any('evidence_ids' in x for x in validate_case(data)))

    def test_export_audit_and_cli_router(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);request=base/'request.json';request.write_text('{}',encoding='utf-8')
            with patch('feat_audit.run',return_value=audit()),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['feat','--input',str(request),'--output',str(base/'audit.json')]),0)
                result=analyze_case(case());export_case(result,base/'run')
            exported=base/'run/feat-reviews.json'
            self.assertTrue(exported.is_file())
            manifest=json.loads((base/'run/manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['files']['feat-reviews.json']['sha256'],hashlib.sha256(exported.read_bytes()).hexdigest())

    def test_effort_review_changes_conditions_fingerprint(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);data=case()
            with patch('feat_audit.run',return_value=audit()):
                export_case(analyze_case(data),base/'one')
                data['feat_reviews'][0]['request']['effort']={'actual_output':'different explicitly supplied event effort'}
                export_case(analyze_case(data),base/'two')
            first=json.loads((base/'one/run-ledger.json').read_text(encoding='utf-8'))
            second=json.loads((base/'two/run-ledger.json').read_text(encoding='utf-8'))
            self.assertNotEqual(first['conditions_sha256'],second['conditions_sha256'])

    def test_standalone_cli_does_not_overwrite_its_input(self):
        from test_feat_audit import packet
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'request.json';raw=json.dumps(packet()).encode('utf-8');path.write_bytes(raw)
            result=subprocess.run([sys.executable,str(ROOT/'scripts/feat_audit.py'),'--input',str(path),'--output',str(path)],capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(path.read_bytes(),raw)

    def test_standalone_cli_emits_utf8_independent_of_console(self):
        from test_feat_audit import packet
        with tempfile.TemporaryDirectory() as folder:
            data=packet();data['event']['description']='中文 ∀ → 非原作测试'
            path=Path(folder)/'request.json';path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/feat_audit.py'),'--input',str(path)],capture_output=True,
                env={**os.environ,'PYTHONIOENCODING':'ascii'})
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout.decode('utf-8'))['event']['description'],data['event']['description'])


if __name__=='__main__':unittest.main()
