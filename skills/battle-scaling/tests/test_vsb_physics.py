"""Policy branches and independent physical benchmarks for the VSB adapter."""
import copy
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import physics
import vsb_physics

C = 299792458
PRIMARY = [{"id": "chapter", "title": "Synthetic original-work fixture",
            "origin": "primary", "access": "provided", "locator": "Fixture statement A; not a real work"}]


def exception():
    return {"explicit_energy_statement": True, "statement": "Synthetic fixture explicitly states the moving object's energy, independently of its speed.", "source_ids": ["chapter"]}


def conversion():
    return {"explicit_conversion_mechanism": True, "statement": "Synthetic fixture explicitly describes physical conversion of the stated mass fraction into energy.", "source_ids": ["chapter"]}


class VSBPhysicsTests(unittest.TestCase):
    def kinetic(self, speed, **extra):
        return {"model": "relativistic_kinetic", "inputs": {"mass": 1, "speed": speed}, **extra}

    def mass_energy(self, policy=True, **extra):
        request = {"model": "mass_energy", "inputs": {"mass": 1, "conversion_fraction": 1}, **extra}
        if policy:
            request["vsb_policy"] = {"mass_energy_conversion": conversion()}
        return request

    def test_newtonian_benchmark_is_compatible_and_does_not_mutate_request(self):
        request = {"model": "kinetic", "inputs": {"mass": {"value": 2, "unit": "kg", "source": "fixture"}, "speed": 3}}
        original = copy.deepcopy(request)
        result = vsb_physics.calculate(request)
        self.assertEqual(result["result"]["value"], 9)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["standard"], "vsb")
        self.assertTrue(result["eligible_for_attachment"])
        self.assertEqual(request, original)

    def test_relativistic_below_cap_preserves_true_ke(self):
        request = self.kinetic(0.6 * C)
        result = vsb_physics.calculate(request)
        self.assertAlmostEqual(result["result"]["value"] / C ** 2, 0.25)
        self.assertFalse(result["policy_review"]["kinetic_cap"]["cap_applied"])
        self.assertEqual(result["result"]["value"], result["raw_calculation"]["result"]["value"])

    def test_high_relativistic_ke_is_capped_and_both_values_retained(self):
        request = self.kinetic(0.99 * C)
        result = vsb_physics.calculate(request)
        expected = 4 * 0.5 * (0.99 * C) ** 2
        self.assertEqual(result["result"]["value"], expected)
        self.assertTrue(result["policy_review"]["kinetic_cap"]["cap_applied"])
        self.assertGreater(result["raw_calculation"]["result"]["value"], expected)
        self.assertEqual(result["result"]["tnt_equivalent"]["value"], expected / physics.TNT_J_PER_TONNE)
        self.assertEqual(result["steps"][-1]["value"], expected)

    def test_cap_is_evaluated_by_formula_not_an_approximate_point_93_switch(self):
        # At .93c the exact ratio has already slightly exceeded four; using
        # a literal speed > .93c switch would incorrectly admit that excess.
        result = vsb_physics.calculate(self.kinetic(0.93 * C))
        accepted = min(physics.calculate(self.kinetic(0.93 * C))["result"]["value"], 2 * (0.93 * C) ** 2)
        self.assertEqual(result["result"]["value"], accepted)

    def test_exact_lightspeed_and_ftl_are_blocked_even_with_exception(self):
        for speed in [C, C * 1.0001, C * 1000]:
            with self.subTest(speed=speed):
                request = self.kinetic(speed, vsb_policy={"relativistic_exception": exception()})
                result = vsb_physics.calculate(request, sources=PRIMARY)
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(result["eligible_for_attachment"])
                self.assertNotIn("result", result)

    def test_readable_primary_energy_statement_is_required_to_uncap(self):
        request = self.kinetic(0.99 * C, vsb_policy={"relativistic_exception": exception()})
        result = vsb_physics.calculate(request, sources=PRIMARY)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["policy_review"]["kinetic_cap"]["cap_applied"])
        self.assertGreater(result["result"]["value"], 2 * (0.99 * C) ** 2)
        self.assertEqual(result["policy_review"]["source_ids"], ["chapter"])

    def test_unsourced_indexed_secondary_and_ambiguous_exceptions_are_withheld(self):
        request = self.kinetic(0.99 * C, vsb_policy={"relativistic_exception": exception()})
        for catalog in [None, [{**PRIMARY[0], "access": "indexed"}], [{**PRIMARY[0], "origin": "community"}],
                        [PRIMARY[0], PRIMARY[0]], [{**PRIMARY[0], "locator": ""}]]:
            with self.subTest(catalog=catalog):
                result = vsb_physics.calculate(request, sources=catalog)
                self.assertEqual(result["status"], "undetermined")
                self.assertNotIn("result", result)
                self.assertFalse(result["eligible_for_attachment"])
                self.assertIn("mathematical_reference", result)

    def test_empty_statement_or_missing_explicit_energy_flag_does_not_uncap(self):
        for node in [{**exception(), "statement": ""}, {**exception(), "source_ids": []},
                     {**exception(), "explicit_energy_statement": False}]:
            with self.subTest(node=node):
                result = vsb_physics.calculate(self.kinetic(.99 * C, vsb_policy={"relativistic_exception": node}), sources=PRIMARY)
                self.assertEqual(result["status"], "undetermined")
                self.assertNotIn("result", result)

    def test_interval_corners_are_capped_and_extrema_recomputed(self):
        request = self.kinetic(.95 * C, intervals={"speed": [.8 * C, .99 * C], "mass": [1, 2]})
        result = vsb_physics.calculate(request)
        sensitivity = result["sensitivity"]
        self.assertTrue(sensitivity["policy_applied_to_all_corners"])
        self.assertEqual(len(sensitivity["cases"]), 4)
        for case in sensitivity["cases"]:
            cap = 2 * case["inputs"]["mass"] * case["inputs"]["speed"] ** 2
            self.assertLessEqual(case["value"], cap)
        self.assertEqual(sensitivity["sampled_max"], 4 * (.99 * C) ** 2)
        self.assertGreater(result["raw_calculation"]["sensitivity"]["sampled_max"], sensitivity["sampled_max"])

    def test_ftl_interval_endpoint_blocks_whole_computation(self):
        request = self.kinetic(.95 * C, intervals={"speed": [.8 * C, C]})
        result = vsb_physics.calculate(request)
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("result", result)

    def test_mass_creation_without_explicit_conversion_has_no_attachable_result(self):
        for description in ["A house appears", "The character grows larger", "The wound regenerates", "The target vanishes"]:
            with self.subTest(description=description):
                request = self.mass_energy(policy=False, assumptions=[description])
                result = vsb_physics.calculate(request, sources=PRIMARY)
                self.assertEqual(result["status"], "undetermined")
                self.assertNotIn("result", result)
                self.assertFalse(result["eligible_for_attachment"])
                self.assertEqual(result["mathematical_reference"]["result"]["value"], float(C) ** 2)
                self.assertIn("COUNTERFACTUAL", result["mathematical_reference"]["applicability"]["conversion_evidence"])

    def test_old_applicability_flag_alone_does_not_bypass_vsb_source_gate(self):
        request = self.mass_energy(policy=False, applicability={"physical_mass_conversion_established": True,
                                                               "conversion_evidence": "Unbound assertion"})
        result = vsb_physics.calculate(request)
        self.assertEqual(result["status"], "undetermined")
        self.assertNotIn("result", result)
        self.assertFalse(result["eligible_for_attachment"])

    def test_sourced_mass_conversion_returns_compatible_result_and_interval(self):
        request = self.mass_energy(intervals={"conversion_fraction": [.25, 1], "mass": [1, 2]})
        original = copy.deepcopy(request)
        result = vsb_physics.calculate(request, sources={"chapter": PRIMARY[0]})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"]["quantity"], "converted_rest_energy")
        self.assertEqual(result["result"]["value"], float(C) ** 2)
        self.assertEqual(result["sensitivity"]["sampled_min"], .25 * float(C) ** 2)
        self.assertEqual(request, original)

    def test_mass_conversion_missing_primary_source_is_withheld(self):
        result = vsb_physics.calculate(self.mass_energy())
        self.assertEqual(result["status"], "undetermined")
        self.assertNotIn("result", result)
        self.assertFalse(result["eligible_for_attachment"])

    def test_known_non_conversion_cannot_be_overridden_by_a_positive_policy_flag(self):
        request = self.mass_energy(applicability={"physical_mass_conversion_established": False})
        result = vsb_physics.calculate(request, sources=PRIMARY)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["eligible_for_attachment"])
        self.assertNotIn("result", result)

    def test_nested_source_catalog_and_inapplicable_policy_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            vsb_physics.calculate({**self.mass_energy(), "sources": PRIMARY}, sources=[])
        with self.assertRaises(ValueError):
            vsb_physics.calculate({"model": "thermal", "inputs": {}, "vsb_policy": {"relativistic_exception": exception()}})
        with self.assertRaises(ValueError):
            vsb_physics.calculate({**self.mass_energy(), "vsb_policy": {"already_accepted": True}})

    def test_unrelated_models_keep_original_result_and_do_not_create_energy(self):
        requests = [
            {"model": "thermal", "inputs": {"mass": 2, "specific_heat": 1000, "delta_temperature": 10}},
            {"model": "work", "inputs": {"force": 100, "displacement": 2}},
            {"model": "torque", "inputs": {"force": 100, "lever_arm": .5}},
        ]
        for request in requests:
            with self.subTest(model=request["model"]):
                self.assertEqual(vsb_physics.calculate(request)["result"], physics.calculate(request)["result"])

    def test_general_physics_module_has_not_acquired_vsb_caps_or_source_requirements(self):
        request = self.kinetic(.99 * C)
        raw = physics.calculate(request)
        adapted = vsb_physics.calculate(request)
        self.assertGreater(raw["result"]["value"], adapted["result"]["value"])
        self.assertNotIn("standard", raw)
        self.assertNotIn("policy_review", raw)
        generic_mass = self.mass_energy(policy=False, applicability={"physical_mass_conversion_established": True,
                                                                     "conversion_evidence": "Mathematical fixture"})
        self.assertEqual(physics.calculate(generic_mass)["result"]["value"], float(C) ** 2)


if __name__ == "__main__":
    unittest.main()
