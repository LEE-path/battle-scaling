"""Independent analytic checks and misuse cases for the physics calculator."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'physics.py'
spec = importlib.util.spec_from_file_location('battle_physics', SCRIPT)
physics = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = physics
spec.loader.exec_module(physics)


class PhysicsTests(unittest.TestCase):
    def calc(self, model, **inputs):
        return physics.calculate({'model': model, 'inputs': inputs})

    def test_kinetic_mechanical_benchmark_and_metadata(self):
        r = self.calc('kinetic', mass={'value': 2, 'unit': 'kg', 'source': 'measured'}, speed=3)
        self.assertEqual(r['result']['value'], 9)
        self.assertEqual(r['result']['unit'], 'J')
        self.assertEqual(r['inputs']['mass']['source'], 'measured')
        self.assertTrue(r['steps'])

    def test_relativistic_gamma_and_low_speed_stability(self):
        r = self.calc('relativistic_kinetic', mass=1, speed=0.6 * 299792458)
        self.assertAlmostEqual(r['result']['value'] / 299792458**2, 0.25)
        r = self.calc('relativistic_kinetic', mass=2, speed=0.001)
        self.assertAlmostEqual(r['result']['value'], 1e-6, places=15)
        with self.assertRaises(ValueError):
            self.calc('relativistic_kinetic', mass=1, speed=299792458)
        with self.assertRaises(ValueError):
            self.calc('kinetic', mass=1, speed=0.5 * 299792458)

    def test_work_requires_distance_and_integrates_path(self):
        with self.assertRaises(ValueError):
            self.calc('work', force=20000)
        r = self.calc('work', force=100, displacement=2, angle=math.pi / 3)
        self.assertAlmostEqual(r['result']['value'], 100)
        r = self.calc('work', samples=[{'displacement': 0, 'force': 0},
                                     {'displacement': 1, 'force': 2},
                                     {'displacement': 2, 'force': 4}])
        self.assertEqual(r['result']['value'], 4)
        with self.assertRaises(ValueError):
            self.calc('work', samples=[{'displacement': 1, 'force': 1},
                                     {'displacement': 0, 'force': 1}])

    def test_mass_energy_requires_evidence_not_disappearance(self):
        req = {'model':'mass_energy','inputs':{'mass':1, 'conversion_fraction':1}}
        with self.assertRaises(ValueError):
            physics.calculate(req)
        req['applicability'] = {'physical_mass_conversion_established':True,
            'conversion_evidence':'Explicit benchmark assumption: complete conversion of 1 kg total mass.'}
        self.assertAlmostEqual(physics.calculate(req)['result']['value']/299792458**2,1)
        req['inputs']['conversion_fraction'] = 1.1
        with self.assertRaises(ValueError):
            physics.calculate(req)

    def test_impulse_does_not_invent_energy(self):
        r = self.calc('impulse', mass=3, delta_velocity=-4, contact_time=0.02)
        self.assertEqual(r['result']['value'], -600)
        self.assertEqual(r['result']['unit'], 'N')
        self.assertNotIn('tnt_equivalent', r['result'])
        with self.assertRaises(ValueError):
            self.calc('impulse', mass=3, delta_velocity=299792458, contact_time=.02)

    def test_torque_not_energy_even_though_same_dimensions(self):
        r = self.calc('torque', force=100, lever_arm=0.5, angle=math.pi/2)
        self.assertAlmostEqual(r['result']['value'], 50)
        self.assertEqual(r['result']['unit'], 'N m')
        self.assertNotIn('tnt_equivalent', r['result'])

    def test_bending_load_geometry_changes_capacity(self):
        base = {'model': 'bending', 'inputs': {'width': .1, 'height': .2,
                'length': 2, 'failure_stress': 30e6},
                'geometry': {'section': 'rectangular', 'loading': 'simply_supported_center'}}
        center = physics.calculate(base)
        self.assertAlmostEqual(center['result']['value'], 40000)
        base['geometry']['loading'] = 'cantilever_end'
        end = physics.calculate(base)
        self.assertAlmostEqual(end['result']['value'], 10000)
        base['geometry']['loading'] = 'simply_supported_uniform'
        uniform = physics.calculate(base)
        self.assertAlmostEqual(uniform['result']['value'], 80000)
        self.assertNotIn('tnt_equivalent', center['result'])

    def test_circular_bending(self):
        r = physics.calculate({'model': 'bending', 'inputs': {'diameter': .2,
            'length': 2, 'failure_stress': 30e6},
            'geometry': {'section': 'circular', 'loading': 'cantilever_end'}})
        self.assertAlmostEqual(r['result']['value'], 30e6 * math.pi * .2**3 / 32 / 2)

    def test_fracture_is_conditional_and_wood_caution_explicit(self):
        request = {'model': 'fracture_I', 'inputs': {'toughness': 1e6,
            'crack_length': .01, 'geometry_factor': 1, 'young_modulus': 10e9,
            'poisson_ratio': .3}, 'applicability': {'linear_elastic': True,
            'small_scale_yielding': True, 'isotropic_approximation': True,
            'material': 'wood', 'plane_condition': 'plane_strain'}}
        r = physics.calculate(request)
        self.assertAlmostEqual(r['result']['value'], 1e6/math.sqrt(math.pi*.01))
        self.assertTrue(any('orthotropic' in v for v in r['limitations']))
        self.assertNotIn('tnt_equivalent', r['result'])
        request['applicability']['isotropic_approximation'] = False
        with self.assertRaises(ValueError):
            physics.calculate(request)

    def test_thermal_and_uniform_gravity(self):
        r = self.calc('thermal', mass=2, specific_heat=1000, delta_temperature=10,
                      latent_heat=10000, phase_fraction=.5)
        self.assertEqual(r['result']['value'], 30000)
        r = self.calc('gravitational_binding', mass=5.972e24, radius=6.371e6)
        self.assertAlmostEqual(r['result']['value']/1e32, 2.24, delta=.01)
        self.assertTrue(any('uniform' in x for x in r['limitations']))

    def test_explosion_requires_matching_calibration(self):
        req = {'model': 'explosion_scaled_distance', 'inputs': {'reference_mass': 8,
            'reference_distance': 10, 'target_distance': 20}}
        with self.assertRaises(ValueError):
            physics.calculate(req)
        req['applicability'] = {'calibration_source': 'published matched experiment',
            'same_overpressure': True, 'similar_charge_geometry': True,
            'same_environment': True}
        r = physics.calculate(req)
        self.assertEqual(r['result']['value'], 64)
        self.assertEqual(r['result']['unit'], 'kg TNT')

    def test_sensitivity_is_reproducible_and_not_probability(self):
        req = {'model':'kinetic', 'inputs':{'mass':2, 'speed':3},
               'intervals':{'mass':[1,3], 'speed':[2,4]}}
        r = physics.calculate(req)
        self.assertEqual(r['sensitivity']['sampled_min'], 2)
        self.assertEqual(r['sensitivity']['sampled_max'], 24)
        self.assertEqual(len(r['sensitivity']['cases']), 4)
        self.assertIn('not a probability', r['sensitivity']['meaning'])

    def test_rejects_nonfinite_units_typoes_and_invalid_quantities(self):
        for bad in [math.nan, math.inf, -1, True, '2']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.calc('kinetic', mass=bad, speed=1)
        with self.assertRaises(ValueError):
            self.calc('kinetic', mass={'value': 2, 'unit':'g'}, speed=1)
        with self.assertRaises(ValueError):
            self.calc('kinetic', mass=2, speeed=1)
        with self.assertRaises(ValueError):
            self.calc('kinetic', mass=1e308, speed=1e100)


if __name__ == '__main__':
    unittest.main()
