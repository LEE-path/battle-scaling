import contextlib,io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import battle,sources,research

class SiteIntegrationTests(unittest.TestCase):
    def receipt(self,root):
        metadata=root/'receipt.json';metadata.write_text('{}',encoding='utf-8')
        return {'status':'ok','original_url':'https://example.org/book/chapter/2','final_url':'https://example.org/book/chapter/2',
          'accessed_at':'2026-10-20T10:00:00Z','http_status':200,'source_kind':'http','sha256':'a'*64,
          'paths':{'metadata':str(metadata)},'warnings':[],'errors':[],'needs':[]}

    def test_sources_records_acquisition_without_claiming_readable(self):
        from site_registry import run
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);db=root/'sites.sqlite3'
            with patch.object(sources,'fetch_source',return_value=self.receipt(root)):
                result=sources.fetch_and_record('https://example.org/book/chapter/2',root,site_db=str(db))
            self.assertEqual(result['status'],'ok')
            self.assertEqual(result['site_experience']['status'],'ok')
            history=run({'op':'history','db':str(db),'domain':'example.org','include_seeds':False})
            self.assertEqual([event['outcome'] for event in history['events']],['fetched_unreviewed'])

    def test_registry_failure_is_visible_without_losing_source_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(sources,'fetch_source',return_value=self.receipt(root)),patch('site_registry.record_fetch',side_effect=OSError('read only registry')):
                result=sources.fetch_and_record('https://example.org/book/chapter/2',root,site_db=str(root/'bad.sqlite3'))
            self.assertEqual(result['status'],'ok')
            self.assertEqual(result['site_experience']['status'],'error')
            self.assertTrue(any('registry' in message.lower() for message in result['warnings']))

    def test_cli_sites_has_persistent_lookup_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);db=root/'sites.sqlite3'
            event={'url':'https://example.org/book/chapter/2','method':'host_browser','outcome':'readable',
                'observed_at':'2026-10-20T10:00:00Z','categories':['novel'],'works':['fixture novel'],
                'notes':['confirmed actual chapter text'],'evidence':{'kind':'host_tool_result','ref':'fixture:actual-receipt'}}
            request=root/'record.json';output=root/'written.json'
            request.write_text(json.dumps({'op':'record','event':event,'db':str(db),'include_seeds':False}),encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(battle.main(['sites','--input',str(request),'--output',str(output)]),0)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['status'],'ok')
            request.write_text(json.dumps({'op':'find','work':'fixture novel','db':str(db),'include_seeds':False}),encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(battle.main(['sites','--input',str(request),'--output',str(output)]),0)
            result=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(len(result['results']),1)
            self.assertTrue(result['results'][0]['recheck_required'])

    def test_research_plan_routes_site_lookup_without_claiming_search(self):
        result=research.run({'op':'plan','target':{'entity_id':'novel:nm','work_id':'lanshenfuti','work':'懒神附体',
            'name':'南冥','continuity':'novel','medium':'novel','period':'ending','state':'final'}})
        request=result['site_experience']['lookup_request']
        self.assertEqual(request,{'op':'find','category':'novel','work':'懒神附体'})
        self.assertFalse(result['search_executed'])
        self.assertTrue(result['site_experience']['recheck_current_target'])

    def test_sources_cli_uses_recording_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(sources,'fetch_and_record',return_value={'status':'ok'}) as wrapped:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(sources.main(['--url','https://example.org/work','--output',directory]),0)
                wrapped.assert_called_once()
            with patch.object(sources,'fetch_and_record',return_value={'status':'ok'}) as wrapped:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(battle.main(['sources','--url','https://example.org/work','--output',directory]),0)
                wrapped.assert_called_once()

if __name__=='__main__':unittest.main()
