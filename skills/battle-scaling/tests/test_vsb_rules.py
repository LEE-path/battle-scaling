import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from vsb_rules import run


class VSBQuantitativeRulesTests(unittest.TestCase):
    def energy(self, value, **kwargs):
        return run({"operation": "energy", "energy_j": value, **kwargs})

    def speed(self, value, unit="m/s", speed_type="combat", **kwargs):
        return run({"operation": "speed", "value": value, "unit": unit, "speed_type": speed_type, **kwargs})

    def test_info_records_actual_primary_source_revisions(self):
        info = run({"operation": "info"})
        self.assertEqual(info["ruleset"], "vsb-current-2026-10-21")
        self.assertEqual(info["sources"]["attack_potency"]["revision_id"], 9632883)
        self.assertEqual(info["sources"]["speed"]["revision_id"], 9439168)
        self.assertEqual(info["sources"]["lifting_strength"]["revision_id"], 9680934)
        self.assertTrue(all(s["access"] == "readable" for s in info["sources"].values()))
        self.assertIn("numeric", info["classification_scope"])

    def test_building_boundary_preserves_180_decimal_places(self):
        below = "1045999999." + "9" * 180
        self.assertEqual(self.energy(below)["classification"]["tier"], "9-A")
        self.assertEqual(self.energy("1046000000")["classification"]["tier"], "8-C")

    def test_small_human_boundaries_are_not_old_vsb_chart(self):
        for value, tier in [("59.99", "10-C"), ("60", "10-B"), ("106", "10-A"),
                            ("300", "9-C"), ("15000", "9-B"), ("20920000", "9-A")]:
            with self.subTest(value=value):
                self.assertEqual(self.energy(value)["classification"]["tier"], tier)

    def test_new_brown_dwarf_boundary_and_labels(self):
        self.assertEqual(self.energy("6.90599999999999999e37")["classification"]["tier"], "5-A")
        brown = self.energy("6.906e37")["classification"]
        self.assertEqual(brown["tier"], "High 5-A")
        self.assertEqual(brown["label"], "Brown Dwarf level")
        self.assertEqual(self.energy("3.139e40")["classification"]["tier"], "Low 4-C")

    def test_large_finite_number_never_creates_higher_structure(self):
        self.assertEqual(self.energy("1e10000")["classification"]["tier"], "3-A")

    def test_energy_conversion_keeps_decimal_and_attribute_separate(self):
        r = run({"operation": "energy", "value": "0.25", "unit": "t_TNT", "attribute": "durability"})
        self.assertEqual(r["classification"]["tier"], "8-C")
        self.assertEqual(r["attribute"], "durability")
        self.assertIn("none", r["attribute_propagation"])

    def test_energy_does_not_accept_force_power_or_bare_mass(self):
        for unit in ["N", "W", "kg", "m/s"]:
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                run({"operation": "energy", "value": "1e40", "unit": unit})

    def test_strict_plus_midpoint_and_equality_disclosure(self):
        midpoint = self.energy("27196000000")["classification"]  # 6.5 tons TNT
        self.assertEqual(midpoint["tier"], "High 8-C")
        self.assertFalse(midpoint["plus"])
        self.assertTrue(midpoint["midpoint_equality_requires_editorial_review"])
        self.assertTrue(self.energy("27196000000.00000000000000001")["classification"]["plus"])

    def test_all_nonfinite_negative_boolean_and_conflicting_inputs_rejected(self):
        for invalid in ["NaN", "Infinity", "-Infinity", "-1", True, None, {}, []]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.energy(invalid)
        with self.assertRaises(ValueError):
            run({"operation": "energy", "energy_j": "100", "value": "200"})

    def test_quantity_interface_and_interval_crosses_building_threshold(self):
        r = run({"operation": "energy", "quantity": {"min": "0.24999999999999999999999", "best": "0.25", "max": "2", "unit": "t_TNT"}})
        self.assertEqual(r["classification"]["tier"], "8-C")
        self.assertEqual(r["interval"]["min"]["classification"]["tier"], "9-A")
        self.assertEqual(r["interval"]["max"]["classification"]["tier"], "High 8-C")
        self.assertEqual(r["input_quantity"]["min"], "0.24999999999999999999999")
        single = run({"operation": "energy", "quantity": {"value": "1046000", "unit": "kJ"}})
        self.assertEqual(single["classification"]["tier"], "8-C")
        for invalid in [{"min": "2", "best": "1"}, {"best": "2", "max": "1"}, {"min": "1", "max": "2"}, {"value": "1", "best": "1"}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                run({"operation": "energy", "quantity": invalid})

    def test_exact_speed_border_examples_from_source(self):
        self.assertEqual(self.speed("10", "Mach")["classification"]["label"], "Hypersonic+")
        self.assertEqual(self.speed("100", "Mach")["classification"]["label"], "Massively Hypersonic")
        self.assertEqual(self.speed("9.999999999999999999999999", "Mach")["classification"]["label"], "Hypersonic")

    def test_lightspeed_and_zero_are_singletons(self):
        self.assertEqual(self.speed("0")["classification"]["label"], "Immobile")
        self.assertEqual(self.speed("1", "c")["classification"]["label"], "Speed of Light")
        self.assertEqual(self.speed("1.00000000000000000000001", "c")["classification"]["label"], "FTL")
        self.assertEqual(self.speed("0.99999999999999999999999", "c")["classification"]["label"], "Relativistic+")

    def test_relativistic_canonical_ratios_and_printed_table_are_explicit(self):
        self.assertEqual(self.speed("0.01", "c")["classification"]["label"], "Sub-Relativistic")
        self.assertEqual(self.speed("0.01", "c", boundary_basis="printed_m_s")["classification"]["label"], "Massively Hypersonic+")
        self.assertEqual(self.speed("1000", "c")["classification"]["label"], "Massively FTL+")
        self.assertEqual(self.speed("1000", "c", boundary_basis="printed_m_s")["classification"]["label"], "Massively FTL")

    def test_finite_speed_arbitrary_size_is_not_infinite(self):
        self.assertEqual(self.speed("1e9999")["classification"]["label"], "Massively FTL+")

    def test_five_speed_types_do_not_propagate(self):
        for kind in ["attack", "combat", "reaction", "travel", "flight"]:
            with self.subTest(kind=kind):
                r = self.speed("3430", speed_type=kind)
                self.assertEqual(r["classification"]["speed_type"], kind)
                self.assertEqual(r["speed_type"], kind)
                self.assertIn("none", r["attribute_propagation"])
        for kind in [None, "perception", "all", "user"]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.speed("100", speed_type=kind)

    def test_reaction_time_not_automatically_speed(self):
        with self.assertRaises(ValueError):
            self.speed("0.000001", "s", "reaction")

    def test_flight_kmh_conversion_and_precision(self):
        self.assertEqual(self.speed("12348", "km/h", "flight")["classification"]["label"], "Hypersonic+")
        self.assertEqual(self.speed("12347." + "9" * 180, "km/h")["classification"]["label"], "Hypersonic")

    def test_lifting_mass_and_telekinesis_do_not_transfer_to_ap(self):
        r = run({"operation": "lifting", "mass_kg": "1000", "mechanism": "telekinesis"})
        self.assertEqual(r["classification"]["label"], "Class 5")
        self.assertEqual(r["mechanism"], "telekinesis")
        self.assertNotIn("tier", r["classification"])
        self.assertIn("independent", r["attribute_propagation"])

    def test_lifting_exact_classes_and_larger_finite_value(self):
        for value, label in [("545.199999999999999", "Peak Human"), ("545.2", "Class 1"),
                             ("5000", "Class 10"), ("2e29", "Stellar"), ("1e9000", "Universal")]:
            with self.subTest(value=value):
                self.assertEqual(run({"operation": "lifting", "mass_kg": value})["classification"]["label"], label)

    def test_lifting_force_needs_separate_model_and_infinity_needs_proof(self):
        with self.assertRaises(ValueError):
            run({"operation": "lifting", "value": "9810", "unit": "N"})
        with self.assertRaises(ValueError):
            run({"operation": "lifting", "mass_kg": "Infinity"})


if __name__ == "__main__":
    unittest.main()
