import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('battle_setup',Path(__file__).with_name('setup.py'))
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def source(self,folder):
        root=folder/'source';root.mkdir()
        data=b'# skill\n';(root/'SKILL.md').write_bytes(data)
        (root/'package-manifest.json').write_text(json.dumps({'files':{'SKILL.md':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}}))
        return root

    def test_install_and_upgrade_preserve_runtime_and_back_up_changed_static_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=self.source(root);target=root/'installed'
            result=setup.install_skill(source,target)
            self.assertEqual(result['changed_files'],2)
            (target/'runtime').mkdir();(target/'runtime/user-setting.json').write_text('keep')
            (target/'SKILL.md').write_text('custom previous skill')
            with self.assertRaises(ValueError): setup.install_skill(source,target)
            result=setup.install_skill(source,target,upgrade=True)
            self.assertEqual((Path(result['backup'])/'SKILL.md').read_text(),'custom previous skill')
            self.assertEqual((target/'runtime/user-setting.json').read_text(),'keep')
            self.assertEqual((target/'SKILL.md').read_bytes(),(source/'SKILL.md').read_bytes())

    def test_install_refuses_source_destination_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            source=self.source(Path(td))
            for target in (source,source/'nested',source.parent):
                with self.assertRaises(ValueError):setup.install_skill(source,target)

    def test_binding_uses_the_downloaded_project_and_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);skill=root/'installed';(skill/'runtime').mkdir(parents=True)
            (skill/'runtime/media-tools.local.json').write_text(json.dumps({'other_setting':'preserve'}))
            setup.bind_runtime(skill,root)
            self.assertEqual(json.loads((skill/'runtime/video-studio.local.json').read_text())['project_root'],str(root/'tools/battle-video-studio'))
            self.assertEqual(json.loads((skill/'runtime/media-tools.local.json').read_text())['other_setting'],'preserve')

    def test_run_rejects_tool_paths(self):
        with self.assertRaises(SystemExit):setup.main(['run','../outside'])

    def test_install_verification_preserves_unrelated_user_runtime_but_rejects_static_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'skills/battle-scaling';source.mkdir(parents=True)
            data=b'# fixture';(source/'SKILL.md').write_bytes(data)
            digest=lambda b:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
            skill={'files':{'SKILL.md':digest(data)}}
            (source/'package-manifest.json').write_text(json.dumps(skill))
            (root/'docs').mkdir()
            files={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in source.rglob('*') if p.is_file()}
            (root/'docs/distribution-manifest.json').write_text(json.dumps({'files':files}))
            (root/'runtime').mkdir();(root/'runtime/private-notes.txt').write_text('not part of the installation')
            self.assertTrue(setup.verify_static(root)['valid'])
            (source/'SKILL.md').write_text('tampered')
            self.assertFalse(setup.verify_static(root)['valid'])


if __name__=='__main__':unittest.main()
