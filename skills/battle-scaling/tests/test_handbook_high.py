"""Handbook source gates, typed math boundaries, and count/predicate audits."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import high_tier as ht
import handbook_high as hh

BASE = "high-wangba-handbook-2026-07-30"


def rule(suffix=""):
    return json.loads((ROOT / "rulesets" / (BASE + suffix + ".json")).read_text(encoding="utf-8"))


def gaps(result):
    return {g["code"] for g in result.get("structured_gaps", [])}


SOURCE = {"path": "fixture-fiction.txt", "locator": "chapter1; explicit scope"}
SCOPE = {"transcends_existing_mathematics": True, "evidence_ids": ["e1"]}


class TypedHandbookTests(unittest.TestCase):
    def calc(self, kind, expression, suffix="", **extra):
        return ht.analyze({"kind": kind, "expression": expression, **extra}, rule(suffix))

    def test_two_countable_factors_not_uncountable(self):
        r = self.calc("ordinal", "omega*omega")
        self.assertEqual(r["result"]["canonical"], "omega^2")
        self.assertEqual([m["label"] for m in r["mappings"]], ["多元"])
        self.assertIn("countable_not_outer", gaps(r))
        r = self.calc("cardinal", "aleph0*aleph0")
        self.assertEqual(r["result"]["canonical"], "aleph0")
        self.assertFalse(r["mappings"])

    def test_same_power_symbols_keep_their_types(self):
        ordinal = self.calc("ordinal", "omega^omega")
        cardinal = self.calc("cardinal", "aleph0^aleph0")
        self.assertEqual(ordinal["result"]["countability"], "countable")
        self.assertEqual(ordinal["mappings"][0]["label"], "无限盒子")
        self.assertFalse(any("论外" in m["label"] for m in ordinal["mappings"]))
        self.assertTrue(any("主文250" in m["label"] for m in cardinal["mappings"]))
        outer = next(m for m in cardinal["mappings"] if m["clause_id"] == "HR-P250-02")
        self.assertEqual(outer["source"]["clause_id"], outer["clause_id"])
        self.assertIn("aleph1", outer["source"]["short_excerpt"])

    def test_finer_aleph_mapping_has_appendix_not_p250_source(self):
        r = self.calc("cardinal", "aleph1")
        finer = next(m for m in r["mappings"] if m["clause_id"] == "HR-NEW-01")
        self.assertEqual(finer["source"]["global_page"], 285)
        self.assertEqual(finer["source"]["clause_id"], "HR-NEW-01")

    def test_ordinal_tower_not_outer(self):
        r = self.calc("ordinal", "tower(omega,omega)")
        self.assertEqual(r["result"]["canonical"], "epsilon0")
        self.assertEqual(r["mappings"][0]["label"], "指数塔")
        self.assertFalse(any("论外" in m["label"] for m in r["mappings"]))

    def test_formal_N_has_no_imported_handbook_pattern(self):
        r = self.calc("formal_box", "N^(N^2)")
        self.assertFalse(r["mappings"])
        self.assertIn("formal_N_not_handbook_ordinal", gaps(r))

    def test_infinite_layer_recurrence_remains_a_gap(self):
        r = self.calc("ordinal", "omega^omega", handbook_stage="无限层无限盒子")
        self.assertIn("handbook_recurrence_undefined", gaps(r))
        self.assertFalse(any(m["label"] == "无限层无限盒子" for m in r["mappings"]))

    def test_finer_inaccessible_mapping_uses_appendix_source(self):
        r = ht.analyze({"kind": "inaccessible", "facts": {"uncountable": True, "regular": True, "strong_limit": True}}, rule())
        finer = next(m for m in r["mappings"] if m["ruleset"].endswith("-new"))
        self.assertEqual(finer["label"], "新标论外二线")
        self.assertEqual(finer["source"]["global_page"], 285)

    def test_countable_aleph_not_new_outer_by_literal_name(self):
        r = self.calc("cardinal", "aleph0", "-new")
        self.assertFalse(r["mappings"])
        self.assertIn("aleph_index_and_gate_gap", gaps(r))

    def test_weak_inaccessible_does_not_silently_become_strong(self):
        r = ht.analyze({"kind": "inaccessible", "facts": {"uncountable": True, "regular": True, "limit": True}}, rule("-new"))
        self.assertFalse(r["mappings"])
        self.assertIn("inaccessible_terminology_ambiguous", gaps(r))

    def test_phi_native_dag_does_not_prove_a_cardinal(self):
        r = ht.analyze({"kind": "native", "nodes": [{"id": "p", "operation": "base", "description": "Phi infinity everywhere", "source": SOURCE}]}, rule())
        self.assertFalse(r["mappings"])
        self.assertIn("native_no_mathematical_bridge", gaps(r))
        self.assertIsNone(r["result"]["cardinal"])


class NamedStandardTests(unittest.TestCase):
    def test_outer_assumptions_and_all_call_sources_are_preserved(self):
        second = {"url": "https://example.org/fiction", "locator": "chapter2"}
        r = hh.analyze({"kind": "handbook_case", "case": "洛晨曦", "assumptions": ["caller continuity assumption"],
                        "source": SOURCE, "sources": [second]}, rule())
        self.assertIn("caller continuity assumption", r["assumptions"])
        self.assertIn(SOURCE, r["provenance"])
        self.assertIn(second, r["provenance"])

    def test_nested_core_assumptions_merge_with_outer_assumptions(self):
        r = hh.analyze({"kind": "handbook_constructive", "assumptions": ["outer work interpretation"], "source": SOURCE,
                        "mathematical_object": {"kind": "cardinal", "expression": "aleph1", "assumptions": ["inner premise"]}}, rule("-new"))
        self.assertIn("outer work interpretation", r["assumptions"])
        self.assertIn("inner premise", r["assumptions"])
        self.assertIn(SOURCE, r["provenance"])

    def test_invalid_call_provenance_is_not_silently_dropped(self):
        r = hh.analyze({"kind": "handbook_case", "source": {"url": "https://example.org"}}, rule())
        self.assertEqual(r["status"], "invalid")
        r = hh.analyze({"kind": "handbook_case", "assumptions": "not a list"}, rule())
        self.assertEqual(r["status"], "invalid")

    def test_table_names_are_not_construction_proofs(self):
        r = hh.analyze({"kind": "handbook_constructive", "object_name": "Ultimate_L"}, rule("-new"))
        self.assertFalse(r["mappings"])
        self.assertIn("name_only_not_construction", gaps(r))

    def test_explicit_object_definition_remains_conditional(self):
        r = hh.analyze({"kind": "handbook_constructive", "object_name": "V_logic", "definition": "Explicit supplied framework with cited domain", "scope_facts": {"definition_verified": True, "evidence_ids": ["e1"]}}, rule("-new"))
        self.assertTrue(r["mappings"])
        self.assertIn("handbook_named_criterion_underspecified", gaps(r))
        self.assertIsNone(r["result"]["scalar_value"])

    def test_historical_stage_depends_on_selected_table(self):
        req = {"kind": "handbook_standard", "identity": {"work": "神盒世界", "version": "旧版", "stage": "infinite"}, "source": SOURCE}
        aos = hh.analyze(req, rule("-aos"))
        f404 = hh.analyze(req, rule("-404"))
        self.assertEqual(aos["mappings"][0]["label"], "论天上（论外天花板上层）")
        self.assertEqual(f404["mappings"][0]["label"], "论外超一线")

    def test_new_box_version_cannot_claim_old_stage(self):
        r = hh.analyze({"kind": "handbook_standard", "identity": {"work": "神盒世界", "version": "新版", "stage": "4"}, "source": SOURCE}, rule("-aos"))
        self.assertFalse(r["mappings"])
        self.assertIn("old_box_identity_not_established", gaps(r))

    def test_case_chapter_has_no_fake_stack_formula(self):
        r = hh.analyze({"kind": "handbook_case", "case": "洛晨曦"}, rule())
        self.assertEqual(r["result"]["construction_status"], "derivation_not_provided")
        self.assertFalse(r["mappings"])
        self.assertIn("case_chapter_no_full_stack", gaps(r))


class LiTests(unittest.TestCase):
    def assess(self, **kw):
        return hh.analyze({"kind": "li", **kw}, rule("-li"))

    def test_positive_E_without_scope_does_not_qualify(self):
        r = self.assess(tokens=[str(i) for i in range(600)], preliminary_dewatering="completed")
        self.assertEqual(r["result"]["machine"]["metrics"]["E_2A_minus_B"], 600)
        self.assertIsNone(r["result"]["label"])
        self.assertIn("li_scope_evidence_missing", gaps(r))

    def test_words_are_not_characters(self):
        r = self.assess(tokens=["天地玄黄宇宙洪荒"] * 500, scope_facts=SCOPE, preliminary_dewatering="completed")
        metrics = r["result"]["machine"]["metrics"]
        self.assertEqual((metrics["A_types"], metrics["B_tokens"]), (1, 500))
        self.assertLess(metrics["E_2A_minus_B"], 0)
        self.assertIn("无量级", r["result"]["label"])

    def test_A_boundary_is_explicit(self):
        r = self.assess(tokens=["t" + str(i) for i in range(4000)], scope_facts=SCOPE, preliminary_dewatering="completed")
        self.assertTrue(r["result"]["machine"]["boundary_ambiguity"])
        self.assertIn("li_source_endpoint_undefined", gaps(r))
        self.assertTrue(all("candidate" in m["status"] for m in r["mappings"]))
        self.assertEqual(r["mappings"][0]["basis"], "explicit_scope_baseline")
        self.assertEqual(r["mappings"][0]["clause_id"], "HR-LI-03")
        self.assertEqual(r["mappings"][0]["source"]["clause_id"], "HR-LI-03")

    def test_manual_count_below_anchor_has_only_scope_provenance(self):
        r = self.assess(scope_facts=SCOPE, source_text="甲乙", manual_segments=[
            {"start": 0, "end": 2, "decision": "keep", "reason": "accept distinct supplied scope description"}])
        self.assertEqual(r["result"]["manual"]["effective_characters"], 2)
        self.assertEqual(r["mappings"][0]["basis"], "explicit_scope_baseline")
        self.assertEqual(r["mappings"][0]["clause_id"], "HR-LI-03")

    def test_mid_negative_branch_original_says_one_line(self):
        tokens = ["t" + str(i) for i in range(5000)] * 3
        r = self.assess(tokens=tokens, scope_facts=SCOPE, preliminary_dewatering="completed")
        self.assertEqual(r["result"]["machine"]["metrics"]["E_2A_minus_B"], -5000)
        self.assertEqual(r["result"]["label"], "一线")

    def test_manual_count_overrides_machine_and_is_annotated(self):
        text = "甲" * 1000
        r = self.assess(tokens=["same"] * 20, scope_facts=SCOPE, source_text=text,
            manual_segments=[{"start": 0, "end": len(text), "decision": "keep", "reason": "Reviewer explicitly accepts this supplied fictional passage's distinct content."}])
        self.assertEqual(r["result"]["priority"], "manual_over_machine")
        self.assertEqual(r["result"]["manual"]["effective_characters"], 1000)
        self.assertEqual(r["result"]["label"], "强一线")

    def test_manual_cannot_omit_source_tail(self):
        r = self.assess(scope_facts=SCOPE, source_text="甲乙", manual_segments=[{"start": 0, "end": 1, "decision": "keep", "reason": "accept"}])
        self.assertEqual(r["status"], "invalid")


class DaoTests(unittest.TestCase):
    def assess(self, count=5000, **kw):
        facts = {**SCOPE, "dewatered": True}
        return hh.analyze({"kind": "dao", "effective_characters": count, "count_unit": "dewatered_characters", "count_policy": "audited character count", "scope_facts": facts, **kw}, rule("-dao"))

    def test_count_below_5000_is_insufficient(self):
        r = self.assess(4999)
        self.assertIsNone(r["result"]["label"])
        self.assertFalse(r["mappings"])

    def test_raw_length_is_not_a_dewatered_count(self):
        r = hh.analyze({"kind": "dao", "text": "甲" * 10000, "effective_characters": 10000, "scope_facts": SCOPE}, rule("-dao"))
        self.assertFalse(r["mappings"])
        self.assertIn("dao_dewatered_count_missing", gaps(r))

    def test_5000_with_qualified_scope_has_only_first_tier(self):
        r = self.assess()
        self.assertEqual(r["result"]["label"], "战力设定三线")
        self.assertEqual(r["mappings"][0]["clause_id"], "HR-DAO-01")

    def test_count_cannot_replace_presentation_predicates(self):
        r = self.assess(10000, presentation_forms_count=2, predicates={"presentation_forms_verified": True})
        self.assertEqual(r["result"]["label"], "战力设定三线")
        r = self.assess(10000, presentation_forms_count=2, predicates={"presentation_forms_verified": True, "progressive_presentation": True})
        self.assertEqual(r["result"]["label"], "战力设定二线")

    def test_boolean_is_not_a_count(self):
        self.assertEqual(self.assess(True)["status"], "invalid")

    def test_predicate_one_is_not_boolean_proof(self):
        r = self.assess(predicates={"beyond_current_mathematics": {"value": 1, "evidence_ids": ["e1"]}})
        self.assertEqual(r["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
