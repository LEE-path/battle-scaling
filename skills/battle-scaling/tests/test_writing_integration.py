"""Keep author-directed creative work separate from source-backed PK defaults."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from battle import SKILL_VERSION,doctor,main
from combat_trace import run as process
from evidence import analyze_case,validate_case
from pk_modes import PRESENTATIONS
from writing_battle import run as writing
from rating_fixtures import with_executed_ratings
from rating_fixtures import legacy_analyze_case as analyze_case  # Explicit legacy regression


def evidence_case():
    return {'schema_version':1,'case_id':'writing-separation-synthetic',
            'characters':[{'id':'a','name':'A','version':'fixture','state':'active'}],
            'sources':[],'anchors':[],'edges':[]}


def text_only_story_request():
    """Invented prose-source dossier, not real canon or automatic verification."""
    request=json.loads((ROOT/'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))
    request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
    request['fixture_kind']='synthetic_original_text_not_character_evidence'
    request['operation']='prepare'
    request.pop('draft',None)
    for source in request['sources']:
        source.update(title='Synthetic original-text fixture',origin='original_text',access='read',
                      locator='Invented prose fixture, chapter 1: independent settings and feats')
    for rating in request['independent_ratings']:
        rating['basis_type']='canon'
    return with_executed_ratings(request)


class WritingIntegrationTests(unittest.TestCase):
    def test_doctor_exposes_separate_task_without_changing_defaults(self):
        data=doctor()
        self.assertEqual(data['skill_version'],SKILL_VERSION)
        self.assertEqual(data['rule_profile']['standard'],'wangba')
        self.assertEqual(data['pk_presentations']['default'],'overview')
        self.assertEqual(PRESENTATIONS,('overview','process'))
        self.assertEqual(data['writing_assistance']['purpose'],'writing')
        self.assertTrue(data['writing_assistance']['separate_from_evidence_modes_and_pk'])
        self.assertTrue(data['writing_assistance']['canon_fidelity']['structural_checker'])
        self.assertFalse(data['writing_assistance']['canon_fidelity']['semantic_verification'])
        self.assertEqual(data['writing_assistance']['mandatory_media_steps'],[])
        self.assertEqual(data['pk_presentations'],{
            'default':'overview','on_explicit_request':'process',
            'default_rating_mode':'integrated',
            'independent_evidence_modes':['integrated','normal','highest','lowball'],
            'legacy_modes':['normal','highest','lowball'],
            'independent_rating_required':True,
            'rating_workflow':'references/character-rating-workflow.md'})
        self.assertNotIn('writing_policy',data['pk_presentations'])
        self.assertEqual(data['host_capabilities']['vision'],'host must supply or configure an external VLM')

    def test_author_directed_scene_is_rejected_as_evidence_case(self):
        request={**evidence_case(),'purpose':'writing'}
        self.assertTrue(any('author-directed' in error for error in validate_case(request)))
        with self.assertRaisesRegex(ValueError,'Writing requests'):
            analyze_case(request)

    def test_author_directed_scene_does_not_disable_process_evidence_gates(self):
        with self.assertRaisesRegex(ValueError,'battle.py writing'):
            process({'purpose':'writing'})

    def test_old_evidence_case_keeps_normal_wangba_analysis(self):
        result=analyze_case(evidence_case())
        self.assertEqual(result['standard'],'wangba')
        self.assertEqual(list(result['modes']),['normal'])

    def test_cli_writing_prepare_exports_task_without_modifying_author_input(self):
        request=json.loads((ROOT/'assets/cases/writing-battle-synthetic.json').read_text(encoding='utf-8'))
        request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        request['operation']='prepare'
        request.pop('draft',None)
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            original=directory/'author.json';output=directory/'writing.json'
            raw=json.dumps(request,ensure_ascii=False).encode('utf-8')
            original.write_bytes(raw)
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                exit_code=main(['writing','--input',str(original),'--output',str(output)])
            self.assertEqual(exit_code,0)
            self.assertEqual(original.read_bytes(),raw)
            data=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(data['purpose'],'writing')
            self.assertEqual(data['skill_version'],SKILL_VERSION)
            self.assertFalse(data['canon_evidence'])
            self.assertFalse((directory/'report.md').exists())

    def test_cli_writing_cannot_overwrite_author_input(self):
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'author.json'
            raw=b'{"purpose":"writing"}'
            original.write_bytes(raw)
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                exit_code=main(['writing','--input',str(original),'--output',str(original)])
            self.assertEqual(exit_code,2)
            self.assertEqual(original.read_bytes(),raw)

    def test_text_only_cli_uses_full_rating_gate_without_media_requirements(self):
        mutations=(
            ('complete',lambda request:None,'ready_for_host'),
            ('missing_dossiers',lambda request:request.pop('independent_ratings'),'needs_independent_rating'),
            ('missing_dimension',lambda request:request['independent_ratings'][0]['dimensions'].pop('体防'),'needs_independent_rating'),
            ('unread_text',lambda request:request['sources'][0].update(access='indexed'),'needs_independent_rating'),
            ('wrong_state',lambda request:request['independent_ratings'][0].update(state='another state'),'needs_independent_rating'),
        )
        for name,mutate,expected in mutations:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as directory:
                request=text_only_story_request()
                mutate(request)
                def keys(value):
                    if isinstance(value,dict):
                        for key,item in value.items():
                            yield key
                            yield from keys(item)
                    elif isinstance(value,list):
                        for item in value:yield from keys(item)
                self.assertTrue(set(keys(request)).isdisjoint({
                    'media','images','video','frames','visual_verification'}))
                directory=Path(directory)
                original=directory/'text-only.json';output=directory/'writing.json'
                original.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    exit_code=main(['writing','--input',str(original),'--output',str(output)])
                self.assertEqual(exit_code,0)
                data=json.loads(output.read_text(encoding='utf-8'))
                self.assertEqual(data['status'],expected)
                self.assertEqual(data['writing_policy']['mandatory_media_steps'],[])
                self.assertFalse(data['rating_preflight']['source_authenticity_verified'])
                self.assertFalse(data['rating_preflight']['semantic_rating_verified'])
                if name=='complete':
                    self.assertEqual(data['rating_preflight']['status'],'ready')
                    self.assertEqual(data['rating_preflight']['accepted_subject_ids'],['lan','shuo'])
                else:
                    self.assertEqual(data['rating_preflight']['status'],'needs_research')
                    self.assertTrue(data['rating_preflight']['needs'])

    def test_writing_policy_does_not_open_ordinary_pk_rating_gate(self):
        policy=writing(text_only_story_request())['writing_policy']
        for presentation in PRESENTATIONS:
            with self.subTest(presentation=presentation):
                request=evidence_case()
                request['characters'].append({'id':'b','name':'B','version':'fixture','state':'active'})
                request['writing_policy']=policy
                request['matchup']={'presentation':presentation,'teams':['a','b'],'win_paths':[]}
                result=analyze_case(request)['matchup']
                self.assertEqual(result['verdict'],'needs_independent_rating')
                self.assertFalse(result['combat_analysis_started'])
                self.assertIsNone(result['assessment'])
                self.assertNotIn('writing_policy',result)
                if presentation=='process':self.assertEqual(result['process']['trace'],[])

    def test_canon_extension_is_merged_and_retained_without_semantic_certification(self):
        request=json.loads((ROOT/'assets/cases/writing-fidelity-synthetic.json').read_text(encoding='utf-8'))
        request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        request = with_executed_ratings(request)
        result=writing(request)
        self.assertEqual(result['status'],'structure_checked')
        self.assertTrue(result['canon_fidelity']['requested'])
        self.assertEqual(result['author_pack']['canon_profiles'],request['canon_profiles'])
        self.assertEqual(result['author_pack']['style_plan'],request['style_plan'])
        self.assertFalse(result['canon_fidelity']['semantic_fidelity_verified'])
        self.assertFalse(result['canon_evidence'])

    def test_missing_canon_profile_blocks_readiness_in_main_contract(self):
        request=json.loads((ROOT/'assets/cases/writing-fidelity-synthetic.json').read_text(encoding='utf-8'))
        request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        request['operation']='prepare'
        request['canon_profiles'][0]['support'].pop('decisions')
        result=writing(request)
        self.assertEqual(result['status'],'needs_input')
        self.assertTrue(any('support.decisions' in item for item in result['needs']))

    def test_unrealized_interaction_causes_main_revision_without_pretending_to_read_prose(self):
        request=json.loads((ROOT/'assets/cases/writing-fidelity-synthetic.json').read_text(encoding='utf-8'))
        request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        request = with_executed_ratings(request)
        for beat in request['draft']['beats']:
            beat.pop('system_interactions',None)
        result=writing(request)
        self.assertEqual(result['status'],'needs_revision')
        self.assertTrue(any('system interaction' in item for item in result['revision_tasks']))
        self.assertFalse(result['canon_fidelity']['prose_implementation_verified'])

    def test_unknown_interaction_is_invalid_in_main_contract(self):
        request=json.loads((ROOT/'assets/cases/writing-fidelity-synthetic.json').read_text(encoding='utf-8'))
        request.setdefault('mode', 'normal')  # Historical fixture, explicit replay
        request['draft']['beats'][0]['system_interactions']=['invented-new-rule']
        result=writing(request)
        self.assertEqual(result['status'],'invalid')
        self.assertTrue(any('unknown interaction' in item for item in result['errors']))


if __name__=='__main__':
    unittest.main()
