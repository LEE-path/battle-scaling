"""Independent mathematical and inference boundary checks for high_tier."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import high_tier as ht


def rule(name):
    return json.loads((ROOT / "rulesets" / name).read_text(encoding="utf-8"))


class OrdinalTests(unittest.TestCase):
    def calc(self, s):
        return ht.analyze({"kind": "ordinal", "expression": s})

    def test_noncommutative_addition(self):
        self.assertEqual(self.calc("1+omega")["result"]["canonical"], "omega")
        self.assertEqual(self.calc("omega+1")["result"]["canonical"], "omega + 1")

    def test_noncommutative_multiplication(self):
        self.assertEqual(self.calc("2*omega")["result"]["canonical"], "omega")
        self.assertEqual(self.calc("omega*2")["result"]["canonical"], "omega*2")
        self.assertEqual(self.calc("(omega+1)*2")["result"]["canonical"], "omega*2 + 1")

    def test_polynomial_product_and_power(self):
        self.assertEqual(self.calc("(omega+1)^2")["result"]["canonical"], "omega^2 + omega + 1")
        self.assertEqual(self.calc("omega^3*omega^2")["result"]["canonical"], "omega^5")
        self.assertEqual(self.calc("omega^2+omega^3")["result"]["canonical"], "omega^3")

    def test_tower_limit_remains_countable(self):
        r = self.calc("tower(omega,omega)")
        self.assertEqual(r["result"]["canonical"], "epsilon0")
        self.assertEqual(r["result"]["countability"], "countable")
        self.assertEqual(r["status"], "exact")

    def test_finite_tower_symbolic_without_fake_value(self):
        r = self.calc("tower(omega,3)")
        self.assertEqual(r["result"]["countability"], "countable")
        self.assertEqual(r["status"], "symbolic")

    def test_power_associates_right(self):
        a = self.calc("omega^2^3")
        b = self.calc("(omega^2)^3")
        self.assertEqual(a["result"]["canonical"], "omega^8")
        self.assertEqual(b["result"]["canonical"], "omega^6")

    def test_large_ordinal_exact_result_not_claimed(self):
        r = self.calc("omega^omega")
        self.assertEqual(r["status"], "symbolic")
        self.assertEqual(r["result"]["countability"], "countable")

    def test_unknown_ordinal_is_symbolic_not_solved(self):
        self.assertEqual(self.calc("Veblen(omega,0)")["status"], "symbolic")

    def test_ordinal_tower_not_aleph1(self):
        r = ht.analyze({"kind": "ordinal", "expression": "tower(omega,omega)"}, rule("high-zerozhi2025-old.json"))
        self.assertEqual(r["mappings"], [])

    def test_cant_mix_cardinal_tokens(self):
        self.assertEqual(self.calc("aleph0+omega")["status"], "invalid")


class CardinalTests(unittest.TestCase):
    def calc(self, s, axioms=None):
        return ht.analyze({"kind": "cardinal", "expression": s, "axioms": axioms or []})

    def test_countable_sum_and_product(self):
        self.assertEqual(self.calc("aleph0*aleph0")["result"]["canonical"], "aleph0")
        self.assertEqual(self.calc("aleph0+aleph0")["result"]["canonical"], "aleph0")

    def test_countable_power_without_ch(self):
        r = self.calc("aleph0^aleph0")
        self.assertEqual(r["result"]["canonical"], "powerset(aleph0)")
        self.assertEqual(r["result"]["lower_bound"], "aleph1")
        self.assertEqual(r["result"]["countability"], "uncountable")

    def test_ch_dependency(self):
        self.assertEqual(self.calc("aleph0^aleph0", ["CH"])["result"]["canonical"], "aleph1")
        r = self.calc("powerset(aleph1)", ["CH"])
        self.assertEqual(r["result"]["canonical"], "powerset(aleph1)")
        self.assertEqual(self.calc("powerset(aleph1)", ["GCH"])["result"]["canonical"], "aleph2")

    def test_infinite_exponent_finite_base(self):
        self.assertEqual(self.calc("7^aleph0")["result"]["canonical"], "powerset(aleph0)")

    def test_simple_cardinal_finite_zero(self):
        self.assertEqual(self.calc("aleph1*0")["result"]["canonical"], "0")
        self.assertEqual(self.calc("aleph1^0")["result"]["canonical"], "1")

    def test_unproved_cardinal_power_is_symbolic(self):
        self.assertEqual(self.calc("aleph4^aleph1")["status"], "symbolic")

    def test_old_rule_uncountability(self):
        r = ht.analyze({"kind": "cardinal", "expression": "aleph0^aleph0"}, rule("high-zerozhi2025-old.json"))
        self.assertEqual(r["mappings"][0]["label"], "论外三线及以上")
        self.assertIn("2025", r["mappings"][0]["ruleset"])

    def test_cardinal_not_ordinal(self):
        self.assertEqual(self.calc("omega^omega")["status"], "invalid")

    def test_conflicting_ch_invalid(self):
        self.assertEqual(self.calc("aleph0", ["GCH", "not_CH"])["status"], "invalid")

    def test_choice_not_silently_added_to_zf_request(self):
        r = self.calc("aleph0*aleph0", ["ZF", "not_AC"])
        self.assertEqual(r["result"]["canonical"], "aleph0")
        self.assertNotIn("ZFC", r["axioms"])

    def test_zf_continuum_no_aleph1_injection_asserted(self):
        r = ht.analyze({"kind": "cardinal", "expression": "powerset(aleph0)", "axioms": ["ZF"]}, rule("high-zerozhi2025-old.json"))
        self.assertEqual(r["result"]["countability"], "uncountable")
        self.assertNotIn("lower_bound", r["result"])
        self.assertEqual(r["mappings"], [])

    def test_zf_aleph1_still_above_threshold(self):
        r = ht.analyze({"kind": "cardinal", "expression": "aleph1", "axioms": ["ZF"]}, rule("high-zerozhi2025-old.json"))
        self.assertTrue(r["mappings"])


class StructureTests(unittest.TestCase):
    def test_weak_vs_strong_inaccessible(self):
        req = {"kind": "inaccessible", "facts": {"uncountable": True, "regular": True, "limit": True}}
        weak = ht.analyze(req)
        self.assertEqual(weak["result"]["classification"], "weakly_inaccessible")
        self.assertFalse(weak["result"]["strongly_inaccessible"])
        strong = ht.analyze(dict(req, axioms=["GCH"]))
        self.assertTrue(strong["result"]["strongly_inaccessible"])
        self.assertIn("GCH", str(strong["steps"]))

    def test_strong_limit_direct(self):
        r = ht.analyze({"kind": "inaccessible", "facts": {"uncountable": True, "regular": True, "strong_limit": True}})
        self.assertTrue(r["result"]["strongly_inaccessible"])

    def test_missing_regularity_no_inaccessible(self):
        r = ht.analyze({"kind": "inaccessible", "facts": {"uncountable": True, "limit": True}})
        self.assertEqual(r["result"]["classification"], "not_established")

    def test_theories_and_proper_classes_not_scalar(self):
        for kind in ("theory", "proper_class"):
            r = ht.analyze({"kind": kind, "name": "Ultimate L", "expression": "UltimateL*aleph1"})
            self.assertEqual(r["status"], "symbolic")
            self.assertIsNone(r["result"]["scalar_value"])
            self.assertEqual(r["mappings"], [])

    def test_theory_no_choice_axiom_imposed(self):
        r = ht.analyze({"kind": "theory", "name": "ZF+Reinhardt", "axioms": ["ZF", "Reinhardt"]})
        self.assertNotIn("ZFC", r["axioms"])
        self.assertEqual(r["status"], "symbolic")
        blank = ht.analyze({"kind": "proper_class", "name": "V"})
        self.assertEqual(blank["axioms"], [])

    def test_native_phi_not_veblen(self):
        case = json.loads((ROOT / "assets/cases/high-godbox-stage4.json").read_text(encoding="utf-8"))
        r = ht.analyze(case, rule("high-wiki-aos404.json"))
        self.assertEqual(r["status"], "conditional")
        self.assertEqual(r["mappings"][0]["label"], "论外一线")
        self.assertEqual(r["mappings"][0]["basis"], "named_anchor_identity")
        self.assertIn("Veblen", str(r["limits"]))
        self.assertEqual(r["result"]["combat_properties"], {})

    def test_expected_answer_not_used(self):
        case = json.loads((ROOT / "assets/cases/high-godbox-stage4.json").read_text(encoding="utf-8"))
        a = ht.analyze(case)
        case["expected"] = {"label": "FAKE"}
        self.assertEqual(a, ht.analyze(case))

    def test_native_default_no_mathematical_axiom_imposed(self):
        r = ht.analyze({"kind": "native", "nodes": [{"id": "b", "operation": "base"}]})
        self.assertEqual(r["axioms"], [])

    def identity_case(self, relation="becomes", **extra):
        src = {"url": "https://www.rudyrucker.com/whitelight/sample/whitelight.xhtml", "locator": "Franx's report of becoming White Light"}
        return {"kind": "native", "nodes": [{"id": "white", "operation": "base", "source": src}], "character_relations": [{"character": "Franx", "node": "white", "relation": relation, "state": "White Light", "duration": "temporary scene", "scope": "this reported transformation", "source": src, **extra}]}

    def test_becomes_retains_state_and_duration_without_combat_transfer(self):
        r = ht.analyze(self.identity_case(properties=["attack", "durability"], mechanism="identity", bridge="assume equality"))
        p = r["result"]["combat_properties"]
        self.assertEqual(list(p), ["state_identity"])
        identity = p["state_identity"][0]
        self.assertEqual(identity["state"], "White Light")
        self.assertEqual(identity["duration"], "temporary scene")
        self.assertEqual(identity["scope"], "this reported transformation")
        self.assertEqual(identity["status"], "source_conditioned")
        self.assertIn("blocked_identity_to_combat_transfer", str(r["warnings"]))

    def test_merges_is_fusion_not_control(self):
        r = ht.analyze(self.identity_case("merges", conditions=["while the merger holds"]))
        p = r["result"]["combat_properties"]
        self.assertEqual(list(p), ["fusion_state"])
        self.assertEqual(p["fusion_state"][0]["conditions"], ["while the merger holds"])
        self.assertNotIn("control_scope", p)

    def test_identity_missing_state_duration_warns_explicitly(self):
        req = self.identity_case()
        del req["character_relations"][0]["state"]
        del req["character_relations"][0]["duration"]
        r = ht.analyze(req)
        self.assertIn("identity_relation_missing_state", str(r["warnings"]))
        self.assertIn("identity_relation_missing_duration", str(r["warnings"]))

    def test_unsourced_or_ineligible_identity_remains_candidate(self):
        req = self.identity_case("merges")
        del req["character_relations"][0]["source"]
        r = ht.analyze(req)
        self.assertEqual(r["result"]["combat_properties"]["fusion_state"][0]["status"], "candidate_unsourced")
        req = self.identity_case()
        req["nodes"][0].update(operation="adjective", aggressive=True, assumptions=["strong interpretation"])
        req["mode"] = "normal"  # Explicit historical filtering regression
        r = ht.analyze(req)
        self.assertEqual(r["result"]["combat_properties"]["state_identity"][0]["status"], "candidate_unsourced")

    def test_narrative_no_numeric_threshold(self):
        case = json.loads((ROOT / "assets/cases/high-scp3812.json").read_text(encoding="utf-8"))
        r = ht.analyze(case, rule("high-zerozhi2025-old.json"))
        self.assertEqual(r["mappings"], [])
        self.assertIsNone(r["result"]["cardinal"])

    def test_whitelight_range_not_attack(self):
        case = json.loads((ROOT / "assets/cases/high-whitelight.json").read_text(encoding="utf-8"))
        r = ht.analyze(case, rule("high-zerozhi2025-old.json"))
        self.assertIn("range", r["result"]["combat_properties"])
        self.assertNotIn("attack", r["result"]["combat_properties"])
        self.assertEqual(r["mappings"][0]["basis"], "typed_source_interpretation")

    def test_cycle_rejected(self):
        r = ht.analyze({"kind": "native", "nodes": [{"id": "a", "operation": "transcends", "depends_on": ["b"]}, {"id": "b", "operation": "transcends", "depends_on": ["a"]}]})
        self.assertEqual(r["status"], "invalid")

    def test_unknown_anchor_refused(self):
        r = ht.analyze({"kind": "native", "nodes": [{"id": "a", "operation": "base"}], "anchor_claims": [{"node": "a", "anchor_id": "universal-super-tier", "relation": "equal"}]}, rule("high-wiki-aos404.json"))
        self.assertEqual(r["mappings"], [])
        self.assertIn("unknown_anchor", str(r["warnings"]))

    def test_highest_accepts_but_marks_adjectival_premise(self):
        req = {"kind": "native", "mode": "highest", "nodes": [{"id": "a", "operation": "base"}, {"id": "b", "operation": "adjective", "depends_on": ["a"], "description": "超越一切", "assumptions": ["一切涵盖已列结构"]}]}
        r = ht.analyze(req)
        self.assertTrue(r["assumptions"])
        self.assertEqual(r["mappings"], [])
        self.assertIn("aggressive", str(r["steps"]))

    def test_identical_anchor_needs_matching_version(self):
        r = ht.analyze({"kind": "native", "nodes": [{"id": "a", "operation": "base", "identity": {"work": "神盒世界", "version": "新版", "stage": "4"}, "source": {"url": "https://example.org", "locator": "4"}}], "anchor_claims": [{"node": "a", "anchor_id": "old_godbox_stage4", "relation": "equal", "basis": "identity"}]}, rule("high-wiki-aos404.json"))
        self.assertEqual(r["mappings"][0]["status"], "candidate")

    def test_unadmitted_aggressive_ancestor_blocks_mapping(self):
        case = json.loads((ROOT / "assets/cases/high-godbox-stage4.json").read_text(encoding="utf-8"))
        case["mode"] = "normal"
        case["nodes"][2]["aggressive"] = True
        case["nodes"][2]["assumptions"] = ["force scope"]
        r = ht.analyze(case)
        self.assertEqual(r["mappings"][0]["status"], "candidate")

    def test_lower_anchor_is_upper_bound_not_earned_tier(self):
        case = json.loads((ROOT / "assets/cases/high-godbox-stage4.json").read_text(encoding="utf-8"))
        case["anchor_claims"][0]["relation"] = "less_than"
        r = ht.analyze(case)
        self.assertIn("低于", r["mappings"][0]["label"])

    def test_no_inaccessible_from_conflicting_supplied_facts(self):
        r = ht.analyze({"kind": "inaccessible", "facts": {"uncountable": True, "regular": True, "limit": False, "strong_limit": True}})
        self.assertEqual(r["status"], "invalid")

    def test_formal_n_not_cardinal_n(self):
        r = ht.analyze({"kind": "formal_box", "expression": "N^(N^2)"}, rule("high-zerozhi2025-new.json"))
        self.assertEqual(r["mappings"][0]["label"], "无限层无限盒子")
        self.assertEqual(r["result"]["domain"], "community_formal_structure")
        self.assertIsNone(r["result"]["cardinal"])

    def test_tetration_formal_mapping(self):
        r = ht.analyze({"kind": "formal_box", "expression": "N^^N"}, rule("high-zerozhi2025-new.json"))
        self.assertEqual(r["mappings"][0]["label"], "指数塔")

    def test_unsupported_tower_returns_symbolic(self):
        r = ht.analyze({"kind": "formal_box", "expression": "N^^^N"}, rule("high-zerozhi2025-new.json"))
        self.assertEqual(r["status"], "invalid")


class InputTests(unittest.TestCase):
    def test_no_eval_injection(self):
        for expr in ("__import__('os').system('echo bad')", "open(x)", "omega[0]", "omega;9"):
            self.assertEqual(ht.analyze({"kind": "ordinal", "expression": expr})["status"], "invalid")

    def test_expression_resource_limit(self):
        r = ht.analyze({"kind": "ordinal", "expression": "("*100+"omega"+")"*100})
        self.assertEqual(r["status"], "invalid")

    def test_large_integer_no_hang(self):
        self.assertEqual(ht.analyze({"kind": "ordinal", "expression": "2^99999999"})["status"], "symbolic")

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.json"
            o = Path(d) / "output.json"
            p.write_text(json.dumps({"kind": "ordinal", "expression": "1+omega"}), encoding="utf-8")
            completed = subprocess.run([sys.executable, str(ROOT / "scripts/high_tier.py"), "--input", str(p), "--output", str(o)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(o.read_text(encoding="utf-8"))["result"]["canonical"], "omega")


if __name__ == "__main__":
    unittest.main()
