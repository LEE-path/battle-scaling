import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import build_release


class ArchiveTests(unittest.TestCase):
    def test_archives_keep_all_manifest_tools_and_never_sweep_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'repo'; root.mkdir()
            payload = {'skills/battle-scaling/SKILL.md': b'skill',
                       'skills/battle-scaling/scripts/poster.py': b'poster',
                       'tools/battle-video-studio/scripts/review-video.mjs': b'review'}
            digest = lambda b: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
            skill = {'version': '1.21.1', 'files': {k.removeprefix('skills/battle-scaling/'): digest(v) for k,v in payload.items() if k.startswith('skills/')}}
            payload['skills/battle-scaling/package-manifest.json'] = json.dumps(skill).encode()
            for name, data in payload.items():
                p = root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
            (root/'docs').mkdir()
            (root/'docs/distribution-manifest.json').write_text(json.dumps({'version': '1.21.1', 'files': {k:digest(v) for k,v in payload.items()}}))
            (root/'runtime').mkdir(); (root/'runtime/user.txt').write_text('must not be archived')
            output = Path(temp)/'assets'
            with patch.object(build_release, 'verify', return_value={'valid':True}):
                result = build_release.build(root, output)
                with self.assertRaisesRegex(ValueError, 'outside'):
                    build_release.build(root, root/'bad')
                with self.assertRaisesRegex(ValueError, 'fresh'):
                    build_release.build(root, output)
            with zipfile.ZipFile(output/result['archives'][0]['name']) as z:
                self.assertIn('battle-scaling/tools/battle-video-studio/scripts/review-video.mjs', z.namelist())
                self.assertFalse(any('runtime/' in n for n in z.namelist()))
            with zipfile.ZipFile(output/result['archives'][1]['name']) as z:
                self.assertIn('battle-scaling/scripts/poster.py', z.namelist())
                self.assertFalse(any('/tools/' in n for n in z.namelist()))


if __name__ == '__main__': unittest.main()
