from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import one_image
import video_studio


class MediaPortabilityTests(unittest.TestCase):
    def test_collage_uses_the_bundled_ofl_font(self):
        expected=Path(one_image.__file__).resolve().parents[1]/'assets/media/fonts/SmileySans-Oblique.ttf'
        self.assertTrue(expected.is_file())
        self.assertEqual(Path(one_image.font_file()),expected)
        self.assertTrue(expected.with_name('SmileySans-OFL.txt').is_file())

    def test_video_bridge_discovers_the_full_repository(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);skill=root/'skills/battle-scaling';skill.mkdir(parents=True)
            server=root/'tools/battle-video-studio/scripts/server.mjs'
            server.parent.mkdir(parents=True);server.write_text('// fixture')
            with patch.object(video_studio,'SKILL',skill),patch.dict(video_studio.os.environ,{},clear=True):
                self.assertEqual(video_studio.studio_root(),server.parent.parent.resolve())

    def test_configured_path_remains_authoritative(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);skill=root/'skills/battle-scaling';skill.mkdir(parents=True)
            server=root/'tools/battle-video-studio/scripts/server.mjs'
            server.parent.mkdir(parents=True);server.write_text('// fixture')
            with patch.object(video_studio,'SKILL',skill),patch.dict(video_studio.os.environ,{'BATTLE_VIDEO_STUDIO_ROOT':str(root/'missing')},clear=True):
                with self.assertRaises(RuntimeError):video_studio.studio_root()


if __name__=='__main__':unittest.main()
