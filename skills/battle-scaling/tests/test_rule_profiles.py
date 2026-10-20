import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rule_profiles import resolve,snapshot_content,finite_path
from evidence import classify_energy


class ProfileTests(unittest.TestCase):
    def test_default_is_fingerprinted_user_handbook(self):
        p=resolve()
        self.assertEqual(p['id'],'wangba-handbook-2026-07-30')
        self.assertEqual(p['document_snapshot']['document_id'],'wangba-handbook-2026-07-30-9d9440127d33')
        self.assertEqual(len(p['document_snapshot']['sources']),4)
        self.assertEqual(p['finite_rule_snapshot']['sha256'],hashlib.sha256(finite_path(p).read_bytes()).hexdigest())

    def test_explicit_legacy_can_be_recomputed(self):
        p=resolve('legacy-2024-2025')
        r=classify_energy({'value':4184000000,'unit':'J'},finite_path(p))
        self.assertEqual(r['status'],'reference_mapping')
        self.assertNotIn('handbook_assessment',r)

    def test_snapshots_save_actual_selected_rule_content(self):
        p=resolve()
        snap=snapshot_content(p,[{'type':'high','request':{'ruleset':'high-zerozhi2025-old'}}])
        self.assertIn(p['finite_ruleset'],snap['rules'])
        self.assertIn('high-zerozhi2025-old.json',snap['rules'])
        for name,record in snap['rules'].items():
            actual=json.loads((Path(__file__).resolve().parents[1]/'rulesets'/name).read_text(encoding='utf-8'))
            self.assertEqual(record['data'],actual)

    def test_unknown_profile_cannot_silently_fall_back(self):
        for name in ('unknown','../old',''):
            if name:
                with self.assertRaises(ValueError):resolve(name)


if __name__=='__main__':unittest.main()
