#!/usr/bin/env python3
"""Auditable, SI-only feat calculations. No network, arbitrary eval or tier claims.

Python API: calculate(request: dict) -> dict.
CLI: python physics.py --input request.json [--output result.json]
Bare numbers are interpreted in the documented SI unit; metadata dictionaries
use {value, unit, source, assumption}. Inputs are claims supplied by the caller,
not independently verified observations. See references/physics-models.md.
"""
from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
from pathlib import Path
import sys

C = 299792458.0
G = 6.67430e-11
TNT_J_PER_TONNE = 4.184e9
SOURCES = {
    'si': 'https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes',
    'tnt': 'https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8',
    'mechanics': 'https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/',
    'relativity': 'https://ocw.mit.edu/courses/8-20-introduction-to-special-relativity-january-iap-2021/',
    'wood': 'https://research.fs.usda.gov/treesearch/62244',
    'structures': 'https://research.fs.usda.gov/treesearch/62251',
    'fracture': 'https://ocw.mit.edu/courses/3-91-mechanical-behavior-of-plastics-spring-2007/ca3759efc1b8fd66d57dce1147d4a1db_23_frac.pdf',
    'fracture_energy': 'https://mooseframework.inl.gov/releases/moose/2022-06-13/modules/tensor_mechanics/FractureIntegrals.html',
    'gravity': 'https://www.mit.edu/~iancross/8901_2019A/notes_midterm.pdf',
    'thermal': 'https://ocw.mit.edu/courses/8-044-statistical-physics-i-spring-2013/',
    'constants': 'https://physics.nist.gov/cgi-bin/cuu/Value?bg',
    'blast': 'https://www.wbdg.org/ffc/army-coe/ufc/ufc-3-340-02',
    'uncertainty': 'https://www.bipm.org/en/doi/10.59161/jcgm100-2008e',
}


def _number(value, name, *, minimum=None, positive=False, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name}: a finite numeric SI value is required')
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f'{name}: finite representable value is required') from None
    if not math.isfinite(value):
        raise ValueError(f'{name}: NaN and infinity are not measurements')
    if positive and value <= 0:
        raise ValueError(f'{name}: must be positive')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name}: must be >= {minimum}')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name}: must be <= {maximum}')
    return value


def _unit(unit):
    if not isinstance(unit, str):
        raise ValueError('unit must be a string')
    return unit.replace('·', ' ').replace('*', ' ').strip()


class Inputs:
    def __init__(self, raw):
        if not isinstance(raw, dict):
            raise ValueError('inputs must be an object')
        self.raw = raw
        self.used = set()
        self.record = {}
        self.assumptions = []
        self.unsourced = []

    def get(self, key, unit, *, default=None, **bounds):
        self.used.add(key)
        if key not in self.raw:
            if default is None:
                raise ValueError(f'{key}: missing required input ({unit})')
            value = default
            metadata = {'source': 'documented model default', 'assumption': f'{key} defaulted to {default} {unit}'}
        else:
            item = self.raw[key]
            metadata = {}
            if isinstance(item, dict):
                if 'value' not in item or 'unit' not in item:
                    raise ValueError(f'{key}: metadata input requires value and unit')
                if _unit(item['unit']) != _unit(unit):
                    raise ValueError(f'{key}: expected {unit}; convert to SI explicitly before calculation')
                value = item['value']
                for field in ('source', 'assumption'):
                    if field in item:
                        if not isinstance(item[field], str):
                            raise ValueError(f'{key}.{field}: expected string')
                        metadata[field] = item[field]
            else:
                value = item
        value = _number(value, key, **bounds)
        self.record[key] = {'value': value, 'unit': unit, **metadata}
        if metadata.get('assumption'):
            self.assumptions.append(metadata['assumption'])
        if not metadata.get('source'):
            self.unsourced.append(key)
        return value

    def finish(self):
        extra = set(self.raw) - self.used
        if extra:
            raise ValueError(f'Unknown or inapplicable inputs: {sorted(extra)}')


def _step(quantity, formula, value, unit, substitution):
    return {'quantity': quantity, 'formula': formula, 'substitution': substitution,
            'value': value, 'unit': unit}


def _all_finite(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError('Result overflow: rescale the calculation or use a reviewed high-precision model')
    if isinstance(obj, dict):
        for v in obj.values():
            _all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _all_finite(v)


def _required_flags(request, flags):
    a = request.get('applicability', {})
    if not isinstance(a, dict):
        raise ValueError('applicability must be an object')
    for flag in flags:
        if a.get(flag) is not True:
            raise ValueError(f'applicability.{flag}=true must be explicitly justified')
    return a


def _single(request):
    if not isinstance(request, dict):
        raise ValueError('request must be an object')
    allowed = {'model','inputs','geometry','applicability','assumptions','intervals'}
    if set(request) - allowed:
        raise ValueError(f'Unknown request fields: {sorted(set(request)-allowed)}')
    model = request.get('model')
    if not isinstance(model, str):
        raise ValueError('model must be a supported model name')
    if 'geometry' in request and model!='bending':
        raise ValueError('geometry is applicable only to bending')
    if 'applicability' in request and model not in ('fracture_I','explosion_scaled_distance','mass_energy'):
        raise ValueError(f'applicability object is not used by {model}; put other stated conditions in assumptions')
    p = Inputs(request.get('inputs', {}))
    assumptions = request.get('assumptions', [])
    if not isinstance(assumptions, list) or not all(isinstance(s, str) for s in assumptions):
        raise ValueError('assumptions must be an array of strings')
    assumptions = list(assumptions)
    limitations = ['Caller-supplied measurements, material properties and source claims are not independently verified by this calculator.']
    sources = [SOURCES['si']]
    steps = []

    if model in ('kinetic', 'relativistic_kinetic'):
        m = p.get('mass', 'kg', positive=True)
        v = p.get('speed', 'm/s', minimum=0)
        if v >= C:
            raise ValueError('speed must be < c; massive-body superluminal kinetic energy is unsupported')
        if model == 'kinetic':
            if v >= .1*C:
                raise ValueError('Use relativistic_kinetic for speed >= 0.1 c')
            energy = .5*m*v*v
            steps.append(_step('kinetic_energy','K = m v^2 / 2',energy,'J',f'0.5 * {m} * {v}^2'))
            limitations.append('Nonrelativistic translation only; establish moving mass and physical speed, rather than apparent screen motion.')
            sources.append(SOURCES['mechanics'])
        else:
            beta2 = (v/C)**2
            root = math.sqrt(1-beta2)
            # Stable even when gamma rounds to 1 at low speeds.
            gamma_minus_1 = beta2/(root*(1+root))
            energy = gamma_minus_1*m*C*C
            steps.extend([_step('gamma_minus_one','gamma - 1 = beta^2 / [sqrt(1-beta^2)(1+sqrt(1-beta^2))]',
                                gamma_minus_1,'1',f'beta = {v}/{C}'),
                          _step('kinetic_energy','K = (gamma-1) m c^2',energy,'J',f'{gamma_minus_1} * {m} * {C}^2')])
            limitations.append('Special-relativistic inertial-body model; does not apply to apparent motion, teleportation, expanding space or massless radiation.')
            sources.append(SOURCES['relativity'])
        result = {'quantity':'kinetic_energy','value':energy,'unit':'J'}
        limitations.append('Kinetic energy is not automatically deposited into the target; impact coupling and stopping process need separate evidence.')

    elif model == 'mass_energy':
        a = _required_flags(request,['physical_mass_conversion_established'])
        if not isinstance(a.get('conversion_evidence'),str) or not a['conversion_evidence'].strip():
            raise ValueError('applicability.conversion_evidence must justify actual physical mass-energy conversion')
        m = p.get('mass','kg',positive=True)
        fraction = p.get('conversion_fraction','1',minimum=0,maximum=1)
        energy = fraction*m*C*C
        steps.append(_step('converted_rest_energy','E = f m c^2',energy,'J',f'{fraction} * {m} * {C}^2'))
        result = {'quantity':'converted_rest_energy','value':energy,'unit':'J'}
        assumptions.append('The specified fraction of the stated total mass is physically converted to energy; for annihilation include both matter and antimatter mass.')
        limitations.append('Disappearance, deletion, sealing, disintegration, teleportation or magical erasure do not establish mass-energy conversion. E=mc^2 is not a default destruction formula.')
        sources.append(SOURCES['relativity'])

    elif model == 'work':
        if 'samples' in p.raw:
            if set(p.raw) != {'samples'}:
                raise ValueError('Use either samples or constant force/displacement, not both')
            p.used.add('samples')
            samples = p.raw['samples']
            if not isinstance(samples,list) or len(samples)<2:
                raise ValueError('samples requires at least two displacement/force pairs')
            if len(samples)>10000:
                raise ValueError('Too many samples; limit is 10000')
            pairs = []
            metadata_samples = []
            for index,sample in enumerate(samples):
                if not isinstance(sample,dict) or set(sample) != {'displacement','force'}:
                    raise ValueError('Each sample must contain displacement and force')
                q = Inputs(sample)
                x = q.get('displacement','m',minimum=0)
                f = q.get('force','N')
                if pairs and x<=pairs[-1][0]:
                    raise ValueError('Sample displacements must be strictly increasing')
                pairs.append((x,f))
                metadata_samples.append(q.record)
                p.assumptions.extend(q.assumptions)
                p.unsourced.extend(f'samples[{index}].{key}' for key in q.unsourced)
            p.record['samples'] = metadata_samples
            energy = sum((x2-x1)*(f1+f2)/2 for (x1,f1),(x2,f2) in zip(pairs,pairs[1:]))
            steps.append(_step('work','W = sum[(x[i+1]-x[i]) (F[i]+F[i+1])/2]',energy,'J',str(pairs)))
            assumptions.append('Sampled force is the signed force component along displacement; linear interpolation between samples.')
        else:
            f = p.get('force','N',minimum=0)
            d = p.get('displacement','m',minimum=0)
            a = p.get('angle','rad',default=0,minimum=-math.pi,maximum=math.pi)
            energy = f*d*math.cos(a)
            steps.append(_step('work','W = F d cos(theta)',energy,'J',f'{f} * {d} * cos({a})'))
            assumptions.append('Force magnitude and its angle to displacement remain constant throughout the measured path.')
        result = {'quantity':'work','value':energy,'unit':'J'}
        sources.append(SOURCES['mechanics'])
        limitations.append('Peak force alone does not determine work. Negative work is not destructive energy, and mechanical work need not equal target damage.')

    elif model == 'impulse':
        m = p.get('mass','kg',positive=True)
        dv = p.get('delta_velocity','m/s')
        dt = p.get('contact_time','s',positive=True)
        if abs(dv)>=.1*C:
            raise ValueError('Large velocity change requires a separately reviewed relativistic momentum/force model')
        impulse = m*dv
        force = impulse/dt
        steps.extend([_step('impulse','I = m delta_v',impulse,'N s',f'{m} * {dv}'),
                      _step('average_force','F_avg = I / delta_t',force,'N',f'{impulse}/{dt}')])
        result = {'quantity':'average_force','value':force,'unit':'N','impulse':{'value':impulse,'unit':'N s'}}
        assumptions.append('Constant mass, nonrelativistic one-axis momentum change; force is averaged over the stated contact interval.')
        limitations.append('Average net force is not peak contact force. Other simultaneous impulses must be isolated; no energy is inferred without a displacement/velocity model.')
        sources.append(SOURCES['mechanics'])

    elif model == 'torque':
        f = p.get('force','N',minimum=0)
        r = p.get('lever_arm','m',minimum=0)
        a = p.get('angle','rad',default=math.pi/2,minimum=0,maximum=math.pi)
        torque = r*f*math.sin(a)
        steps.append(_step('torque','tau = r F sin(theta)',torque,'N m',f'{r} * {f} * sin({a})'))
        result = {'quantity':'torque','value':torque,'unit':'N m'}
        limitations.append('lever_arm is pivot-to-application distance; theta is the angle to force. Torque is not work or an energy feat; angular displacement is not supplied.')
        sources.append(SOURCES['mechanics'])

    elif model == 'bending':
        geometry = request.get('geometry',{})
        if not isinstance(geometry,dict) or set(geometry) != {'section','loading'}:
            raise ValueError('geometry requires exactly section and loading')
        section = geometry['section']
        loading = geometry['loading']
        if section == 'rectangular':
            b = p.get('width','m',positive=True)
            h = p.get('height','m',positive=True)
            modulus = b*h*h/6
            steps.append(_step('section_modulus','S = b h^2 / 6',modulus,'m^3',f'{b} * {h}^2 / 6'))
        elif section == 'circular':
            d = p.get('diameter','m',positive=True)
            modulus = math.pi*d**3/32
            steps.append(_step('section_modulus','S = pi d^3 / 32',modulus,'m^3',f'pi * {d}^3 / 32'))
        else:
            raise ValueError('section must be rectangular or circular')
        L = p.get('length','m',positive=True)
        sigma = p.get('failure_stress','Pa',positive=True)
        factors = {'simply_supported_center':(.25,'M_max = F L / 4'),
                   'cantilever_end':(1.0,'M_max = F L'),
                   'simply_supported_uniform':(.125,'M_max = F_total L / 8')}
        if loading not in factors:
            raise ValueError(f'Unknown loading geometry: {loading}')
        factor,mformula = factors[loading]
        moment = sigma*modulus
        force = moment/(factor*L)
        steps.extend([_step('failure_moment','M = sigma_failure S',moment,'N m',f'{sigma} * {modulus}'),
                      _step('failure_load',mformula+'; F = M_max / (factor L)',force,'N',f'{moment}/({factor} * {L})')])
        result = {'quantity':'estimated_failure_load','value':force,'unit':'N',
                  'section_modulus':{'value':modulus,'unit':'m^3'},'failure_moment':{'value':moment,'unit':'N m'}}
        assumptions.extend(['Prismatic beam, transverse load, applicable failure stress for the actual material and grain direction.',
                            'Rectangular height is the cross-section dimension along bending; length is unsupported span or cantilever length.'])
        limitations.extend(['Idealized bending failure; checks for shear, local crushing, buckling, existing cracks, large deformation and fixture slip remain separate.',
                            'An along-grain splitting scene is not automatically beam bending. Force does not determine fracture work or punching energy.'])
        sources.extend([SOURCES['wood'],SOURCES['structures']])

    elif model == 'fracture_I':
        ainfo = _required_flags(request,['linear_elastic','small_scale_yielding','isotropic_approximation'])
        plane = ainfo.get('plane_condition')
        if plane not in ('plane_stress','plane_strain'):
            raise ValueError('applicability.plane_condition must be plane_stress or plane_strain')
        toughness = p.get('toughness','Pa sqrt(m)',positive=True)
        crack = p.get('crack_length','m',positive=True)
        y = p.get('geometry_factor','1',positive=True)
        E = p.get('young_modulus','Pa',positive=True)
        nu = p.get('poisson_ratio','1',minimum=-.9999,maximum=.4999)
        sigma = toughness/(y*math.sqrt(math.pi*crack))
        eprime = E if plane == 'plane_stress' else E/(1-nu*nu)
        release = toughness*toughness/eprime
        steps.extend([_step('critical_stress','sigma_c = K_c / [Y sqrt(pi a)]',sigma,'Pa',f'{toughness}/({y} * sqrt(pi * {crack}))'),
                      _step('effective_modulus',"E_prime = E (plane stress); E/(1-nu^2) (plane strain)",eprime,'Pa',f'{plane}: E={E}, nu={nu}'),
                      _step('critical_energy_release_rate',"G_c = K_c^2/E_prime",release,'J/m^2',f'{toughness}^2/{eprime}')])
        result = {'quantity':'critical_stress','value':sigma,'unit':'Pa',
                  'critical_energy_release_rate':{'value':release,'unit':'J/m^2'}}
        if 'area' in p.raw:
            area = p.get('area','m^2',positive=True)
            result['nominal_force'] = {'value':sigma*area,'unit':'N'}
            steps.append(_step('nominal_force','F = sigma_c A',sigma*area,'N',f'{sigma} * {area}'))
        assumptions.append('Mode-I opening, applicable crack definition and geometry factor; explicit isotropic linear-elastic approximation.')
        limitations.extend(['No total fracture work is inferred from G_c alone; crack path, evolving geometry, dissipative mechanisms and new crack area must be modeled.',
                            'Use plane-strain K_Ic only when its validity conditions match; plane-stress fracture requires an applicable K_c rather than reusing an unmatched material value.',
                            'Wood is orthotropic. Its toughness, modulus, crack path, grain orientation and moisture must be established; this isotropic approximation may be unsuitable.'])
        sources.extend([SOURCES['fracture'],SOURCES['fracture_energy'],SOURCES['wood']])

    elif model == 'thermal':
        m = p.get('mass','kg',positive=True)
        c = p.get('specific_heat','J/(kg K)',minimum=0)
        dt = p.get('delta_temperature','K',minimum=0)
        latent = p.get('latent_heat','J/kg',default=0,minimum=0)
        fraction = p.get('phase_fraction','1',default=1,minimum=0,maximum=1)
        sensible = m*c*dt
        phase = m*latent*fraction
        energy = sensible+phase
        steps.extend([_step('sensible_heat','Q_s = m c delta_T',sensible,'J',f'{m}*{c}*{dt}'),
                      _step('latent_heat','Q_l = m L f',phase,'J',f'{m}*{latent}*{fraction}'),
                      _step('thermal_energy','Q = Q_s + Q_l',energy,'J',f'{sensible}+{phase}')])
        result = {'quantity':'thermal_energy','value':energy,'unit':'J'}
        assumptions.append('Specified heated mass, mean applicable heat capacity, temperature interval and phase fraction; account for each phase separately when needed.')
        limitations.append('Heating/phase-change energy only. Visible disappearance does not establish vaporization; heat losses, chemistry, radiation and shock require separate treatment.')
        sources.append(SOURCES['thermal'])

    elif model == 'gravitational_binding':
        m = p.get('mass','kg',positive=True)
        r = p.get('radius','m',positive=True)
        compactness = 2*G*m/(r*C*C)
        if compactness>=.1:
            raise ValueError('Compactness >= 0.1: Newtonian uniform-sphere model is inapplicable; use a reviewed relativistic model')
        energy = 3*G*m*m/(5*r)
        steps.extend([_step('compactness','2 G M / (R c^2)',compactness,'1',f'2*{G}*{m}/({r}*{C}^2)'),
                      _step('binding_energy','|U| = 3 G M^2 / (5 R)',energy,'J',f'3*{G}*{m}^2/(5*{r})')])
        result = {'quantity':'uniform_sphere_binding_energy','value':energy,'unit':'J'}
        assumptions.append('Newtonian gravity; isolated uniform-density sphere dispersed to infinity with zero final kinetic energy.')
        limitations.append('A uniform-density approximation, not the exact binding energy of a differentiated planet/star. Cracking, surface devastation, fragmentation and complete dispersal are distinct events.')
        if compactness>=.01:
            limitations.append('Compactness >= 0.01: relativistic corrections may be material; this is only a coarse Newtonian reference.')
        sources.extend([SOURCES['gravity'],SOURCES['constants']])

    elif model == 'explosion_scaled_distance':
        a = _required_flags(request,['same_overpressure','similar_charge_geometry','same_environment'])
        if not isinstance(a.get('calibration_source'),str) or not a['calibration_source'].strip():
            raise ValueError('applicability.calibration_source is required')
        m1 = p.get('reference_mass','kg TNT',positive=True)
        r1 = p.get('reference_distance','m',positive=True)
        r2 = p.get('target_distance','m',positive=True)
        z = r1/(m1**(1/3))
        m2 = m1*(r2/r1)**3
        steps.extend([_step('scaled_distance','Z = R_ref / W_ref^(1/3)',z,'m/(kg TNT)^(1/3)',f'{r1}/{m1}^(1/3)'),
                      _step('equivalent_charge_mass','W_target = W_ref (R_target/R_ref)^3',m2,'kg TNT',f'{m1}*({r2}/{r1})^3')])
        result = {'quantity':'calibration_equivalent_charge_mass','value':m2,'unit':'kg TNT'}
        assumptions.append('Hopkinson-Cranz similarity at the same calibrated blast effect/overpressure, charge type, geometry and environment.')
        limitations.extend(['Conditional scaling from the supplied calibration, not a universal yield-from-fireball-radius or nuclear-explosion formula.',
                            'Unknown blast mechanism, scaled regime, confinement, altitude, medium, duration or damage endpoint can invalidate this comparison.'])
        sources.extend([SOURCES['blast'],a['calibration_source']])
    else:
        raise ValueError(f'Unsupported model: {model}')

    p.finish()
    if p.unsourced:
        limitations.append('Parameter sources not supplied: '+', '.join(p.unsourced)+'. Add evidence before using this as a researched feat.')
    if result['unit']=='J' and result['value']>=0:
        sources.append(SOURCES['tnt'])
        result['tnt_equivalent'] = {'value':result['value']/TNT_J_PER_TONNE,'unit':'t TNT',
            'meaning':'Energy bookkeeping at 4.184e9 J per tonne TNT; does not establish blast, destructive radius, attack potency or tier.'}
    output = {'model':model,'inputs':p.record,'steps':steps,'result':result,
              'assumptions':assumptions+p.assumptions,'limitations':limitations,
              'sources':list(dict.fromkeys(sources))}
    if request.get('geometry'):
        output['geometry'] = copy.deepcopy(request['geometry'])
    if request.get('applicability'):
        output['applicability'] = copy.deepcopy(request['applicability'])
    _all_finite(output)
    return output


def calculate(request: dict) -> dict:
    """Calculate one supported model, optionally enumerate input interval corners.

    intervals is {input_name: [lower_SI, upper_SI]}. Results are sampled extrema,
    not a claim about probability or unproven interior maxima. At most 8 varied
    scalar parameters (256 cases); correlated intervals need explicit scenarios.
    """
    try:
        output = _single(request)
        intervals = request.get('intervals')
        if intervals is None:
            return output
        if not isinstance(intervals,dict) or not intervals or len(intervals)>8:
            raise ValueError('intervals must contain 1 to 8 scalar input ranges')
        names = list(intervals)
        ranges = []
        for name in names:
            if name not in output['inputs'] or name=='samples':
                raise ValueError(f'Cannot vary unknown/non-scalar input {name}')
            span = intervals[name]
            if not isinstance(span,list) or len(span)!=2:
                raise ValueError(f'intervals.{name} must be [lower, upper] in SI')
            lo,hi = [_number(v,f'intervals.{name}') for v in span]
            if not lo<=output['inputs'][name]['value']<=hi:
                raise ValueError(f'{name}: base value must lie inside its ordered interval')
            ranges.append([lo,hi] if lo!=hi else [lo])
        cases = []
        for combination in itertools.product(*ranges):
            case = copy.deepcopy(request)
            case.pop('intervals',None)
            selection = dict(zip(names,combination))
            for name,value in selection.items():
                original = case['inputs'].get(name)
                if isinstance(original,dict):
                    original['value'] = value
                else:
                    case['inputs'][name] = value
            r = _single(case)
            cases.append({'inputs':selection,'value':r['result']['value'],'unit':r['result']['unit']})
        output['sensitivity'] = {'method':'Cartesian endpoint enumeration; sampled bounds only unless model monotonicity is separately justified.',
            'meaning':'A parameter-scenario range, not a probability interval or the three debate modes. Correlations and model uncertainty are not included.',
            'sampled_min':min(c['value'] for c in cases),'sampled_max':max(c['value'] for c in cases),
            'unit':output['result']['unit'],'cases':cases,'source':SOURCES['uncertainty']}
        return output
    except (OverflowError,ZeroDivisionError) as exc:
        raise ValueError(f'Numerical overflow or singular parameter combination: {exc}') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,help='JSON request path, or - for stdin')
    parser.add_argument('--output',help='Write result JSON; default stdout')
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input=='-' else Path(args.input).read_text(encoding='utf-8-sig')
        request = json.loads(raw,parse_constant=lambda s: (_ for _ in ()).throw(ValueError(f'Invalid JSON constant: {s}')))
        result = calculate(request)
        rendered = json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        if args.output:
            destination = Path(args.output).resolve()
            if args.input!='-' and destination==Path(args.input).resolve():
                raise ValueError('Result JSON must not overwrite the request JSON')
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(rendered,encoding='utf-8')
        else:
            print(rendered,end='')
        return 0
    except (ValueError,OSError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
