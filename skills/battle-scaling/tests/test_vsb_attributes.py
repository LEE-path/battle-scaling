"""Check typed report mapping and prevent unit-based attribute laundering."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vsb_attributes import map_quantity


class VSBAttributeMappingTests(unittest.TestCase):
    def test_case_quantity_value_with_bounds_remains_switchable(self):
        for attribute,unit,value in [('attack_energy','J','2000'),('combat_speed','m/s','343'),('lifting_strength','kg','1000')]:
            with self.subTest(attribute=attribute):
                a=map_quantity(attribute,{'value':value,'min':value,'max':value,'unit':unit})
                b=map_quantity(attribute,{'best':value,'min':value,'max':value,'unit':unit})
                self.assertEqual(a['best_reference'],b['best_reference'])

    def test_energy_attributes_keep_their_ownership(self):
        for attribute, target in [("attack_energy", "attack_potency"), ("attack_potency", "attack_potency"),
                                  ("striking_strength", "striking_strength"), ("body_durability", "durability"),
                                  ("durability", "durability"), ("destructive_capacity", "destructive_capacity")]:
            with self.subTest(attribute=attribute):
                result = map_quantity(attribute, {"value": "1.046e9", "unit": "J"})
                self.assertEqual(result["status"], "vsb_numerical_mapping")
                self.assertEqual(result["mapped_attribute"], target)
                self.assertEqual(result["vsb_assessment"]["attribute"], target)
                self.assertEqual(result["best_reference"], "8-C (Building level)")
                self.assertEqual(result["ruleset_id"], "vsb-current-2026-10-21")
                self.assertIn("qualifier", result)

    def test_decimal_energy_interval_and_common_tnt_unit_alias(self):
        result = map_quantity("attack_energy", {"min": "0.249999999999999999999999999999999", "best": "0.25", "max": "2", "unit": "t TNT"})
        self.assertTrue(result["min_reference"].startswith("9-A"))
        self.assertTrue(result["best_reference"].startswith("8-C"))
        self.assertTrue(result["max_reference"].startswith("High 8-C"))
        self.assertIn("249999999999999999999999999999999", result["vsb_assessment"]["input_quantity"]["min"])

    def test_all_five_speed_types_are_distinct_and_receive_labels(self):
        for kind in ("attack", "combat", "reaction", "travel", "flight"):
            with self.subTest(kind=kind):
                result = map_quantity(kind + "_speed", {"value": "10", "unit": "Mach"})
                self.assertEqual(result["best_reference"], "Hypersonic+")
                self.assertEqual(result["vsb_assessment"]["speed_type"], kind)
                self.assertEqual(result["mapped_attribute"], kind + "_speed")
                self.assertIn("qualifier", result)

    def test_generic_speed_needs_explicit_context_type(self):
        for context in [None, {}, {"speed_type": "perception"}, {"speed_type": ["combat"]}]:
            with self.subTest(context=context):
                result = map_quantity("speed", {"value": 3430, "unit": "m/s"}, context)
                self.assertEqual(result["status"], "requires_review")
                self.assertIsNone(result["vsb_assessment"])
                self.assertIn("speed_type", result["reason"])
                self.assertIn("qualifier", result)
        result = map_quantity("speed", {"value": 3430, "unit": "m/s"}, {"speed_type": "flight_speed"})
        self.assertEqual(result["mapped_attribute"], "flight_speed")
        self.assertEqual(result["best_reference"], "Hypersonic+")

    def test_explicit_speed_and_context_cannot_conflict(self):
        result = map_quantity("reaction_speed", {"value": "1000", "unit": "m/s"}, {"speed_type": "travel"})
        self.assertEqual(result["status"], "requires_review")
        self.assertIsNone(result["vsb_assessment"])

    def test_speed_interval_maps_each_endpoint_without_propagation(self):
        result = map_quantity("travel_speed", {"min": "9.999999999999999999", "best": "10", "max": "100", "unit": "Mach"})
        self.assertEqual(result["min_reference"], "Hypersonic")
        self.assertEqual(result["best_reference"], "Hypersonic+")
        self.assertEqual(result["max_reference"], "Massively Hypersonic")
        for point in result["vsb_assessment"]["interval"].values():
            self.assertEqual(point["classification"]["speed_type"], "travel")

    def test_speed_uses_canonical_c_or_explicit_printed_basis(self):
        quantity = {"value": "1000", "unit": "c"}
        canonical = map_quantity("attack_speed", quantity)
        printed = map_quantity("attack_speed", quantity, {"boundary_basis": "printed_m_s"})
        self.assertEqual(canonical["best_reference"], "Massively FTL+")
        self.assertEqual(printed["best_reference"], "Massively FTL")

    def test_lifting_strength_kg_and_t_interval(self):
        result = map_quantity("lifting_strength", {"min": "0.999999999999999999", "best": "1", "max": "5", "unit": "t"}, {"mechanism": "telekinesis"})
        self.assertEqual(result["min_reference"], "Class 1")
        self.assertEqual(result["best_reference"], "Class 5")
        self.assertEqual(result["max_reference"], "Class 10")
        self.assertEqual(result["vsb_assessment"]["mechanism"], "telekinesis")
        self.assertEqual(map_quantity("lifting_strength", {"value": 1000, "unit": "kg"})["best_reference"], "Class 5")

    def test_body_mass_hp_intelligence_range_and_unknown_are_not_recast(self):
        for attribute, unit in [("body_mass", "kg"), ("body_mass_scenario", "kg"), ("intelligence", "J"),
                                ("experience", "J"), ("range", "m/s"), ("HP", "J"), ("unrecognized", "J")]:
            with self.subTest(attribute=attribute):
                result = map_quantity(attribute, {"value": "1e40", "unit": unit})
                self.assertEqual(result["status"], "not_applicable")
                self.assertIsNone(result["best_reference"])
                self.assertIsNone(result["vsb_assessment"])

    def test_wrong_physical_units_do_not_create_a_rating(self):
        for attribute, unit in [("attack_energy", "N"), ("durability", "W"), ("flight_speed", "J"),
                                ("reaction_speed", "s"), ("lifting_strength", "N"), ("lifting_strength", "J")]:
            with self.subTest(attribute=attribute, unit=unit):
                self.assertEqual(map_quantity(attribute, {"value": 100, "unit": unit})["status"], "not_applicable")

    def test_symbolic_high_tier_never_enters_a_finite_numeric_table(self):
        result = map_quantity("attack_energy", {"kind": "tier", "rank": 50, "label": "High 1-A", "unit": "J"})
        self.assertEqual(result["status"], "not_applicable")

    def test_large_finite_values_do_not_manufacture_infinite_labels(self):
        cases = [("attack_energy", "J", "3-A (Universe level)"),
                 ("flight_speed", "m/s", "Massively FTL+"), ("lifting_strength", "kg", "Universal")]
        for attribute, unit, expected in cases:
            with self.subTest(attribute=attribute):
                self.assertEqual(map_quantity(attribute, {"value": "1e9000", "unit": unit})["best_reference"], expected)

    def test_invalid_intervals_and_nonfinite_inputs_are_rejected(self):
        for attribute, unit in [("attack_energy", "J"), ("flight_speed", "m/s"), ("lifting_strength", "kg")]:
            for quantity in [{"min": 2, "best": 1}, {"best": 2, "max": 1}, {"min": 1, "max": 2},
                             {"value": "Infinity"}, {"value": True}, {"value": 1, "best": 1}]:
                with self.subTest(attribute=attribute, quantity=quantity), self.assertRaises(ValueError):
                    map_quantity(attribute, {**quantity, "unit": unit})

    def test_single_point_references_are_complete_and_context_is_not_mutated(self):
        context = {"speed_type": "combat", "boundary_basis": "canonical"}
        result = map_quantity("speed", {"value": "1", "unit": "c"}, context)
        self.assertEqual([result[k] for k in ("min_reference", "best_reference", "max_reference")], ["Speed of Light"] * 3)
        self.assertEqual(context, {"speed_type": "combat", "boundary_basis": "canonical"})


if __name__ == "__main__":
    unittest.main()
