import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vsb_high import run


class VSBHighReviewTests(unittest.TestCase):
    def packet(self, tier="1-A", route=None, **kwargs):
        info = run({"operation": "criteria", "tier": tier})
        canonical, rule = next(iter(info["tiers"].items()))
        keys = list(info["common_criteria"]) + rule["required"]
        numeric = rule["numeric"].copy()
        if rule["routes"]:
            route = route or next(iter(rule["routes"]))
            selected = rule["routes"][route]
            keys += selected["required"]
            numeric.update(selected["numeric"])
        source = {"id": "canon", "title": "Isolated test-fixture canon location",
                  "origin": "primary", "access": "readable",
                  "locator": "Fixture chapter 10, paragraph 4; test only"}
        claim = {"status": True, "reason": "The host has read the cited passage and supplied the specific structural and effect argument.", "source_ids": ["canon"]}
        p = {"operation": "review", "requested_tier": canonical,
             "sources": [source], "criteria": {key: copy.deepcopy(claim) for key in keys}}
        if route is not None:
            p["route"] = route
        for key, bounds in numeric.items():
            p[key] = {"value": bounds[0], "reason": "The cited complete structure contains exactly the specified finite number.", "source_ids": ["canon"]}
        p.update(kwargs)
        return p

    def test_reference_pins_current_revisions_and_reports_semantic_boundary(self):
        r = run({"operation": "criteria"})
        refs = {s["id"]: s["revision_id"] for s in r["rule_sources"]}
        self.assertEqual(refs["vsb-tiering"], 9401765)
        self.assertEqual(refs["vsb-tiering-faq"], 9689808)
        self.assertEqual(refs["vsb-omnipotence"], 9411237)
        self.assertIn("Not semantic verification", r["validation_scope"])
        self.assertIn("High 1-A+", r["tiers"])

    def test_minimal_labels_and_dimensions_do_not_create_qualitative_tier(self):
        r = run({"operation": "review", "requested_tier": "1-A"})
        self.assertEqual(r["status"], "undetermined")
        self.assertIsNone(r["classification"])
        p = self.packet("1-A", dimensions={"value": 10**100, "reason": "This is a very large finite dimension count.", "source_ids": ["canon"]})
        with self.assertRaises(ValueError):
            run(p)

    def test_complete_claim_packet_is_supported_but_not_semantically_certified(self):
        r = run(self.packet())
        self.assertEqual(r["status"], "supported_by_packet")
        self.assertEqual(r["classification"]["tier"], "1-A")
        self.assertIn("not semantically certified", r["classification"]["qualifier"])

    def test_only_local_unknown_with_explicit_assumption_can_be_conditional(self):
        p = self.packet()
        c = p["criteria"]["no_lower_composition_access"]
        c.update(status=None, source_ids=[], reason="The particular lower-to-higher information channel remains unresolved.")
        self.assertEqual(run(p)["status"], "undetermined")
        c["assumption"] = "For this branch only, the lower information channel cannot compose or reach the higher ontology."
        r = run(p)
        self.assertEqual(r["status"], "conditional")
        self.assertIn("conditional", r["classification"]["qualifier"])

    def test_false_cannot_be_bypassed_with_assumption(self):
        p = self.packet("0")
        p["criteria"]["immutability"].update(status=False, reason="The being was created by another entity and then gained new intrinsic states.", assumption="Assume the visible changes were not real.")
        r = run(p)
        self.assertEqual(r["status"], "blocked")
        self.assertIsNone(r["classification"])

    def test_all_required_zero_properties_are_independently_required(self):
        for key in ["primacy", "unity", "immutability", "indivisibility", "trans_hierarchical_supremacy", "transcends_ontological_distinctions", "zero_counterexamples_resolved"]:
            with self.subTest(key=key):
                p = self.packet("0")
                del p["criteria"][key]
                self.assertEqual(run(p)["status"], "undetermined")

    def test_zero_has_no_ordinary_versus_combat_qualifier(self):
        r = run(self.packet("0"))
        self.assertEqual(r["status"], "supported_by_packet")
        self.assertIn("combat is inapplicable", r["classification"]["qualifier"])

    def test_indexed_blocked_partial_and_unknown_sources_are_not_adopted(self):
        for access in ["indexed", "indexed_only", "blocked", "partial", "fetched_unreviewed", "unknown"]:
            with self.subTest(access=access):
                p = self.packet()
                p["sources"][0]["access"] = access
                r = run(p)
                self.assertEqual(r["status"], "undetermined")
                self.assertEqual(r["adopted_source_ids"], [])

    def test_assumption_and_synthetic_sources_are_never_established_evidence(self):
        for origin in ["assumption", "synthetic"]:
            with self.subTest(origin=origin):
                p = self.packet()
                p["sources"][0]["origin"] = origin
                r = run(p)
                self.assertEqual(r["status"], "conditional")
                self.assertEqual(r["adopted_source_ids"], [])

    def test_source_mapping_and_existing_verified_provided_access_are_accepted(self):
        for access in ["verified", "provided", "readable"]:
            p = self.packet()
            source = p["sources"][0]
            source["access"] = access
            p["sources"] = {"canon": {k: v for k, v in source.items() if k != "id"}}
            self.assertEqual(run(p)["status"], "supported_by_packet")

    def test_incomplete_provenance_and_unknown_source_ids_do_not_pass(self):
        for field in ["title", "origin", "locator"]:
            p = self.packet()
            del p["sources"][0][field]
            self.assertEqual(run(p)["status"], "undetermined")
        p = self.packet()
        p["criteria"]["full_scope_effect"]["source_ids"] = ["missing"]
        self.assertEqual(run(p)["status"], "undetermined")

    def test_supplied_classification_or_review_result_is_rejected(self):
        for key in ["classification", "result", "review_result", "validated", "approved", "status", "wangba_tier", "auto_tier"]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                run({**self.packet(), key: "already approved"})

    def test_claim_status_is_strict_boolean_or_null_and_reason_is_required(self):
        for invalid in [1, 0, "true", "verified", [], {}]:
            p = self.packet()
            p["criteria"]["full_scope_effect"]["status"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                run(p)
        for reason in ["", "1-A", "Outerverse level", "approved", None]:
            p = self.packet()
            p["criteria"]["full_scope_effect"]["reason"] = reason
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                run(p)

    def test_tier_2_finite_count_boundaries(self):
        for tier, count, expected in [("2-C", 1, "blocked"), ("2-C", 2, "supported_by_packet"), ("2-C", 1000, "supported_by_packet"), ("2-C", 1001, "blocked"), ("2-B", 1000, "blocked"), ("2-B", 1001, "supported_by_packet"), ("2-B", 10**100, "supported_by_packet")]:
            p = self.packet(tier)
            p["count"]["value"] = count
            with self.subTest(tier=tier, count=count):
                self.assertEqual(run(p)["status"], expected)

    def test_large_finite_count_cannot_establish_two_a(self):
        p = self.packet("2-A", count={"value": 10**100, "reason": "There are very many but still finitely many spacetimes.", "source_ids": ["canon"]})
        with self.assertRaises(ValueError):
            run(p)

    def test_finite_dimensional_ranges_and_actual_superiority_both_required(self):
        rows = [("Low 1-C", 5, True), ("Low 1-C", 4, False), ("1-C", 6, True), ("1-C", 9, True), ("1-C", 10, False), ("High 1-C", 10, True), ("High 1-C", 11, True), ("High 1-C", 12, False), ("1-B", 12, True), ("1-B", 1000, True), ("1-B", 11, False)]
        for tier, dimensions, accepted in rows:
            p = self.packet(tier)
            p["dimensions"]["value"] = dimensions
            with self.subTest(tier=tier, dimensions=dimensions):
                self.assertEqual(run(p)["status"], "supported_by_packet" if accepted else "blocked")
        p = self.packet("1-B")
        del p["criteria"]["significant_dimensional_superiority"]
        self.assertEqual(run(p)["status"], "undetermined")

    def test_numeric_parameter_must_be_integer_and_bound_to_readable_source(self):
        for invalid in [5.0, "5", True, float("inf"), -5, None]:
            p = self.packet("Low 1-C")
            p["dimensions"]["value"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                run(p)
        p = self.packet("Low 1-C")
        p["dimensions"]["source_ids"] = []
        p["dimensions"]["assumption"] = "Assume this number without a source."
        self.assertEqual(run(p)["status"], "undetermined")

    def test_numeric_parameter_alone_or_unsourced_dimension_is_not_enough(self):
        p = self.packet("Low 1-C")
        p["criteria"] = {}
        self.assertEqual(run(p)["status"], "undetermined")
        del p["dimensions"]
        self.assertEqual(run(p)["status"], "undetermined")

    def test_low_one_c_continuum_route_does_not_require_a_fictitious_fifth_axis(self):
        p = self.packet("Low 1-C", route="continuum_spacetimes")
        self.assertNotIn("dimensions", p)
        r = run(p)
        self.assertEqual(r["status"], "supported_by_packet")
        self.assertEqual(r["route"], "continuum_spacetimes")

    def test_low_one_a_routes_do_not_accept_dimension_label_as_evidence(self):
        self.assertEqual(run(self.packet("Low 1-A", route="all_dimensional_spaces"))["status"], "supported_by_packet")
        self.assertEqual(run(self.packet("Low 1-A", route="valid_above_dimensions"))["status"], "supported_by_packet")
        p = self.packet("Low 1-A", route="valid_above_dimensions")
        p["criteria"]["genuine_superiority_over_dimensionality"]["status"] = False
        self.assertEqual(run(p)["status"], "blocked")

    def test_plus_modifiers_and_two_high_one_a_plus_routes_are_preserved(self):
        for tier in ["High 1-B+", "1-A+", "High 1-A+"]:
            r = run(self.packet(tier))
            self.assertIn("AP plus modifier", r["classification"]["qualifier"])
        p = self.packet("High 1-A+", route="embody_logical_space")
        p["criteria"]["no_independent_maximal_logical_spaces"].update(status=False, reason="Canon explicitly has two independent maximal all-logical frameworks with a power gap.")
        self.assertEqual(run(p)["status"], "blocked")

    def test_high_one_b_plus_higher_cardinal_route_does_not_invent_axes(self):
        p = self.packet("High 1-B+", route="higher_cardinal_structure")
        self.assertNotIn("significant_dimensional_superiority", p["criteria"])
        r = run(p)
        self.assertEqual(r["status"], "supported_by_packet")
        self.assertEqual(r["route"], "higher_cardinal_structure")

    def test_other_standards_unknown_codes_and_irrelevant_routes_are_rejected(self):
        for tier in ["无限盒子", "论外", "High 2-A", "Low 1-B", "High 0", "Outerverse level"]:
            with self.subTest(tier=tier), self.assertRaises(ValueError):
                run({"operation": "criteria", "tier": tier})
        with self.assertRaises(ValueError):
            run({**self.packet(), "standard": "wangba"})
        with self.assertRaises(ValueError):
            run({**self.packet(), "profile": "old-vsb"})
        with self.assertRaises(ValueError):
            run({**self.packet(), "route": "dimensional"})

    def test_whitespace_normalization_does_not_convert_other_standard_names(self):
        r = run({"operation": "criteria", "tier": " High1-B+ "})
        self.assertIn("High 1-B+", r["tiers"])

    def test_input_not_mutated_and_rule_reference_is_detached(self):
        p = self.packet()
        original = copy.deepcopy(p)
        r = run(p)
        r["rule_sources"][0]["revision_id"] = -1
        self.assertEqual(p, original)
        self.assertEqual(run({"operation": "criteria"})["rule_sources"][0]["revision_id"], 9401765)


if __name__ == "__main__":
    unittest.main()
