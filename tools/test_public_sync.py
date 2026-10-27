"""Focused publication boundaries; never modifies installed sources."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sync_public as s

class DistributionTests(unittest.TestCase):
    def test_runtime_and_full_corpus_are_excluded(self):
        for rel in ('runtime/auth.local.json','data/site-experience/db.sqlite','data/media-sourcing/download.mp4','data/wangba-handbook-2026-07-30/pages.jsonl','assets/writing-examples/a.md','assets/handbook-review/a.png','assets/formula-ocr-validation/a.png','models/m.onnx','references/song.ogg','references/footage.mov','weights.gguf'):
            self.assertTrue(s.excluded(rel),rel)
        for rel in ('scripts/high_tier.py','data/wangba-handbook-2026-07-30/high-rules-curated.json','assets/cases/high-scp3812.json'):
            self.assertFalse(s.excluded(rel),rel)

    def test_high_rules_keep_functional_structure_and_strip_history(self):
        value={'rulesets':[{'code':'X','formula':'2**n'}],'mathematical_bridges':[{'x':7}],'cases':[{'account':'not-a-rule'}],'page_inventory':[{'page_id':'p1','printed':3,'chat':'not-a-rule'}]}
        result=json.loads(s.transform('skills/battle-scaling/data/wangba-handbook-2026-07-30/high-rules-curated.json',s.dumps(value).encode()))
        self.assertEqual(result['rulesets'],value['rulesets']);self.assertEqual(result['mathematical_bridges'],value['mathematical_bridges']);self.assertEqual(result['cases'],[])
        self.assertEqual(result['page_inventory'],[{'page_id':'p1','printed':3}])

    def test_writing_points_to_methods_without_full_story_claims(self):
        data='**优秀文本范例**：写作时从[用户认可范例索引](writing-excellent-examples.md)选读全文。入选全文均随包内置。'
        result=s.transform('skills/battle-scaling/references/writing-entry.md',data.encode()).decode()
        self.assertIn('writing-experience.md',result);self.assertNotIn('随包内置',result)

    def test_runnable_novel_demo_uses_real_repo_and_temp_roots(self):
        raw="### 可运行的隔离示例\n$skillRoot = (Resolve-Path -LiteralPath './skills/battle-scaling').Path\n$demoRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('demo-' + [guid]::NewGuid())\n"
        result=s.transform('skills/battle-scaling/references/novel-evidence.md',raw.encode()).decode()
        self.assertIn("Resolve-Path -LiteralPath './skills/battle-scaling'",result)
        self.assertIn('[System.IO.Path]::GetTempPath()',result)
        self.assertNotIn("= 'SKILL_ROOT'",result);self.assertNotIn("Join-Path 'LOCAL_RESEARCH_ROOT'",result)

    def test_private_book_audit_becomes_a_general_evidence_rule(self):
        raw='本次 2026-10-20 实机核查的 `private-project` 中，项目记录了一段工作版本删改。该书包只是本次本地审计样本，不能从此推断其他包都经过同样改写。'
        result=s.transform('skills/battle-scaling/references/novel-evidence.md',raw.encode()).decode()
        self.assertNotIn('private-project',result)
        self.assertIn('文件齐全检查通过，不等于原作结尾正确',result)
        self.assertIn('不能把工作版本当成原版',result)

    def test_installed_target_is_rejected_and_unchanged_copy_is_not_written(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);source=folder/'source';source.mkdir()
            with self.assertRaises(ValueError):s.safe_target(folder/'.codex/skills/other',[source])
            target=folder/'out/f.txt';self.assertTrue(s.write_if_changed(target,b'keep'))
            stamp=target.stat().st_mtime_ns;self.assertFalse(s.write_if_changed(target,b'keep'));self.assertEqual(target.stat().st_mtime_ns,stamp)

    def test_standalone_core_uses_skill_authority_and_preserves_methods_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);skill=root/'skill';novel=root/'novel';pub=root/'publication'
            for p in (skill/'scripts/combat_refpack',novel/'combat_refpack',pub/'tools',pub/'skills/battle-scaling/references'):p.mkdir(parents=True,exist_ok=True)
            (skill/'scripts/combat_refpack/core.py').write_bytes(b'# authoritative core\n')
            (novel/'combat_refpack/core.py').write_bytes(b'# older independent copy\n')
            (novel/'README.md').write_bytes(b'# independent wrapper\n')
            writing=b'# independently written methods\r\nKeep existing edits.\r\n'
            (pub/'skills/battle-scaling/references/writing-experience.md').write_bytes(writing)
            (pub/'LICENSE').write_bytes(b'Original permission text\n')
            for name in ('sync_public.py','verify_package.py','publication_guard.py','test_publication_guard.py','test_public_sync.py','import_handbook_corpus.py','setup.py','test_setup.py'):(pub/'tools'/name).write_bytes(b'# fixture\n')
            with patch.object(s,'PUBLICATION',pub),patch.object(s,'video_payload',return_value={}):
                files,_=s.build_payload(skill,root/'video',novel,'1.21.0')
            self.assertEqual(files['tools/combat-novel-refpack/combat_refpack/core.py'],b'# authoritative core\n')
            self.assertEqual(files['skills/battle-scaling/references/writing-experience.md'],writing)
            self.assertEqual(files['skills/battle-scaling/LICENSE'],b'Original permission text\n')
            self.assertEqual(files['tools/combat-novel-refpack/LICENSE'],b'Original permission text\n')
            self.assertEqual((novel/'combat_refpack/core.py').read_bytes(),b'# older independent copy\n')

if __name__=='__main__':unittest.main()
