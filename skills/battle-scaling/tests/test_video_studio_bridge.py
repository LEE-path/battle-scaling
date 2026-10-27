import io
import json
import sys
import unittest
import urllib.error
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import video_studio


class VideoBridgeTests(unittest.TestCase):
    def test_local_cli_keeps_gaps_and_can_prepare_without_changing_active_project(self):
        details={'code':'MEDIA_GAPS','error':'Need finish','gaps':[{'role':'finish','missingSeconds':2}]}
        fake=SimpleNamespace(returncode=1,stdout=json.dumps(details),stderr='')
        with patch.dict(video_studio.os.environ,{'BATTLE_VIDEO_NODE':'node'}), \
             patch.object(video_studio.subprocess,'run',return_value=fake) as run:
            with self.assertRaises(video_studio.VideoStudioError) as caught:
                video_studio.prepare_local(Path('.'),Path('job.json'),activate=False)
        self.assertEqual(caught.exception.details,details)
        self.assertIn('--json',run.call_args.args[0])
        self.assertIn('--no-activate',run.call_args.args[0])

    def test_prepare_uses_current_cli_without_restarting_or_using_cached_http(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'job.json';source.write_text('{}',encoding='utf-8')
            with patch.object(sys,'argv',['video_studio.py','prepare','--job',str(source)]), \
                 patch.object(video_studio,'studio_root',return_value=Path(folder)), \
                 patch.object(video_studio,'api') as api, \
                 patch.object(video_studio,'open_studio') as launcher, \
                 patch.object(video_studio,'prepare_local',create=True,return_value={'id':'prepared-current-cli'}) as prepare:
                video_studio.main()
            prepare.assert_called_once()
            api.assert_not_called()
            launcher.assert_not_called()

    def test_material_gaps_remain_actionable_without_parsing_error_text(self):
        details={'code':'MEDIA_GAPS','error':'Need finish footage',
                 'gaps':[{'side':'a','role':'finish','missingSeconds':1.25}],'notes':[]}
        failure=urllib.error.HTTPError('http://127.0.0.1:3210/api/prepare',400,'bad input',{},
                                      io.BytesIO(json.dumps(details).encode()))
        with patch.object(video_studio.urllib.request,'urlopen',side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:video_studio.api('/api/prepare',{})
        self.assertEqual(getattr(caught.exception,'details',None),details)


if __name__=='__main__':unittest.main()
