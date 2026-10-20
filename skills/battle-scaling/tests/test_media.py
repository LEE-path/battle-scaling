"""Geometry checks and a real ffmpeg extraction when optional tools exist."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'media.py'
spec = importlib.util.spec_from_file_location('battle_media', SCRIPT)
media = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = media
spec.loader.exec_module(media)
try:
    from PIL import Image
except ImportError:
    Image = None


class MediaTests(unittest.TestCase):
    def test_doctor_is_honest_about_vision(self):
        r = media.run({'operation': 'doctor'})
        self.assertFalse(r['capabilities']['semantic_vision_builtin'])
        self.assertIn('Pillow', r['capabilities'])

    @unittest.skipUnless(Image, 'Pillow not installed')
    def test_info_measure_annotation_crop_and_geometry_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            source = d/'page.png'
            Image.new('RGB', (200, 100), 'white').save(source)
            info = media.run({'operation':'image-info', 'path':str(source)})
            self.assertEqual(info['result']['width'], 200)
            self.assertEqual(info['result']['height'], 100)
            req = {'operation':'measure', 'path':str(source),
                   'reference_segment':[[0,20],[100,20]],
                   'target_segment':[[0,50],[50,50]],
                   'reference_length_m':2, 'same_plane':True,
                   'equal_projected_scale':True, 'pixel_error':1,
                   'reference_length_error_m':.1, 'output':str(d/'annotated.png')}
            measured = media.run(req)
            self.assertEqual(measured['result']['value'], 1)
            self.assertLess(measured['result']['interval_m'][0], 1)
            self.assertGreater(measured['result']['interval_m'][1], 1)
            with Image.open(d/'annotated.png') as im:
                self.assertEqual(im.size, (200,100))
            req['output'] = str(d/'other.png')
            req['same_plane'] = False
            with self.assertRaises(ValueError):
                media.run(req)
            cropped = media.run({'operation':'crop','path':str(source),
                'box':[10,20,60,50],'output':str(d/'crop.png')})
            self.assertEqual(cropped['result']['size'],[50,30])
            with self.assertRaises(ValueError):
                media.run({'operation':'crop','path':str(source),
                           'box':[0,0,201,50],'output':str(d/'bad.png')})
            with self.assertRaises(ValueError):
                media.run({'operation':'crop','path':str(source),
                           'box':[0,0,10,10],'output':str(source),'overwrite':True})

    @unittest.skipUnless(Image, 'Pillow not installed')
    def test_exif_coordinate_space_and_vision_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'rotated.jpg'
            im = Image.new('RGB',(80,40),'white')
            exif = im.getexif()
            exif[274] = 6
            im.save(path,exif=exif)
            r = media.run({'operation':'image-info','path':str(path)})
            self.assertEqual([r['result']['width'],r['result']['height']],[40,80])
            self.assertEqual(r['result']['stored_size'],[80,40])
            r = media.run({'operation':'vision-request','path':str(path),
                           'task':'Identify who hits whom and give bounding boxes.'})
            self.assertEqual(r['status'],'requires_external_vision')
            self.assertNotIn('observations',r)
            self.assertIn('required_response_schema',r)

    @unittest.skipUnless(Image, 'Pillow not installed')
    def test_nonfinite_coordinates_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'page.png'
            Image.new('RGB',(20,20),'white').save(source)
            req = {'operation':'measure','path':str(source),'reference_length_m':1,
                   'reference_segment':[[0,0],[10,0]],
                   'target_segment':[[0,1],[float('nan'),1]],
                   'same_plane':True,'equal_projected_scale':True}
            with self.assertRaises(ValueError):
                media.run(req)
            req['target_segment'] = [[0,1],[10,1]]
            req['reference_length_m'] = float('inf')
            with self.assertRaises(ValueError):
                media.run(req)

    @unittest.skipUnless(Image, 'Pillow not installed')
    def test_cli_result_cannot_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            source = d/'page.png'
            Image.new('RGB',(20,20),'white').save(source)
            before = source.read_bytes()
            request = d/'request.json'
            request.write_text(json.dumps({'operation':'image-info','path':str(source)}),encoding='utf-8')
            p = subprocess.run([sys.executable,str(SCRIPT),'--input',str(request),
                                '--output',str(source)],capture_output=True,timeout=30)
            self.assertEqual(p.returncode,2)
            self.assertEqual(source.read_bytes(),before)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),
                         'ffmpeg/ffprobe not installed')
    def test_real_video_pts_accurate_extraction_and_out_of_range(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            path = d/'sample.mkv'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi',
                '-i','testsrc=size=96x64:rate=5:duration=1','-c:v','ffv1',str(path)],
                check=True,timeout=30,capture_output=True)
            p = media.run({'operation':'video-probe','path':str(path)})
            self.assertEqual(p['result']['video_stream']['width'],96)
            r = media.run({'operation':'video-extract','path':str(path),
                'timestamp_seconds':.21,'output':str(d/'frame.png')})
            self.assertTrue((d/'frame.png').exists())
            self.assertAlmostEqual(r['result']['actual_source_pts_seconds'],.4,places=5)
            self.assertGreaterEqual(r['result']['actual_playback_seconds'],.21)
            self.assertEqual(r['result']['source_pts'],400)
            self.assertEqual(r['result']['source_time_base'],'1/1000')
            with self.assertRaises(ValueError):
                media.run({'operation':'video-extract','path':str(path),
                    'timestamp_seconds':4,'output':str(d/'missing.png')})

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),
                         'ffmpeg/ffprobe not installed')
    def test_video_nonzero_start_pts_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            path = d/'offset.mkv'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi',
                '-i','testsrc=size=32x32:rate=5:duration=1','-c:v','ffv1',
                '-output_ts_offset','10',str(path)],check=True,timeout=30,capture_output=True)
            r = media.run({'operation':'video-extract','path':str(path),
                'timestamp_seconds':.21,'output':str(d/'offset.png')})
            self.assertAlmostEqual(r['result']['actual_source_pts_seconds'],10.4,places=5)
            self.assertAlmostEqual(r['result']['actual_playback_seconds'],.4,places=5)


if __name__ == '__main__':
    unittest.main()
