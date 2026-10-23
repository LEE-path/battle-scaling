"""Pinned VSB quantitative reference tables; never a feat-acceptance engine.

Decimal strings preserve exact table boundaries. Numerical energy cannot establish
higher-dimensional tiers, and finite velocities never establish Infinite speed.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE_PATH = ROOT / "rulesets" / "vsb-current-2026-10-21.json"
SPEED_TYPES = {"attack", "combat", "reaction", "travel", "flight"}
ENERGY_UNITS = {
    "J": "1", "kJ": "1000", "MJ": "1e6", "GJ": "1e9",
    "TJ": "1e12", "PJ": "1e15", "EJ": "1e18",
    "g_TNT": "4184", "kg_TNT": "4184000", "t_TNT": "4184000000",
    "kt_TNT": "4184000000000", "Mt_TNT": "4184000000000000",
    "Gt_TNT": "4184000000000000000", "foe": "1e44",
}


def _decimal(value, name):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{name} must be a finite decimal string or number")
    if isinstance(value, str) and len(value) > 10000:
        raise ValueError(f"{name} is too long")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    if abs(result.adjusted()) > 100000:
        raise ValueError(f"{name} exponent exceeds the supported finite range")
    return result


def _precision(*values):
    # Retain values arbitrarily close to a boundary rather than rounding upward.
    return max(128, sum(len(v.as_tuple().digits) for v in values) + 32)


def _multiply(value, factor):
    with localcontext() as ctx:
        ctx.prec = _precision(value, factor)
        return value * factor


def _display(value):
    return str(value)


def _data():
    raw = RULE_PATH.read_bytes()
    data = json.loads(raw)
    return data, hashlib.sha256(raw).hexdigest()


def _row(value, rows):
    for row in reversed(rows):
        low = Decimal(row["lower"])
        upper = None if row["upper"] is None else Decimal(row["upper"])
        if value >= low and (upper is None or value < upper):
            return row
    raise ValueError("quantity is outside the finite table")


def _base(data, digest, operation):
    topic = {"energy": "attack_potency", "speed": "speed", "lifting": "lifting_strength"}.get(operation)
    return {
        "status": "ok", "operation": operation,
        "ruleset": data["id"], "ruleset_id": data["id"], "standard": "vsb", "ruleset_sha256": digest,
        "sources": data["sources"] if topic is None else [data["sources"][topic]],
        "classification_scope": "numerical_reference_only; host must establish applicable feat and accepted scaling",
        "limitations": data["limitations"] + ([] if topic is None else data[topic]["limitations"]),
    }


def _quantity(request, direct_key, default_unit):
    if direct_key in request:
        if "value" in request or "unit" in request:
            raise ValueError(f"use either {direct_key} or value/unit, not both")
        return _decimal(request[direct_key], direct_key), default_unit
    if "value" not in request:
        raise ValueError(f"provide {direct_key} or value/unit")
    return _decimal(request["value"], "value"), request.get("unit", default_unit)


def _energy(request, data, result):
    if "quantity" in request:
        if any(k in request for k in ("value", "unit", "energy_j")):
            raise ValueError("quantity cannot be combined with value/unit or energy_j")
        quantity = request["quantity"]
        if not isinstance(quantity, dict):
            raise ValueError("quantity must be an object")
        if "value" in quantity:
            if any(k in quantity for k in ("min", "best", "max")):
                raise ValueError("quantity uses either value or min/best/max")
            return _energy({**{k: v for k, v in request.items() if k != "quantity"},
                            "value": quantity["value"], "unit": quantity.get("unit", "J")}, data, result)
        if "best" not in quantity:
            raise ValueError("an interval quantity requires best; min and max are optional")
        points = {key: _decimal(quantity[key], key) for key in ("min", "best", "max") if key in quantity}
        if ("min" in points and points["min"] > points["best"]) or ("max" in points and points["best"] > points["max"]):
            raise ValueError("quantity must satisfy min <= best <= max")
        branches = {}
        common = {k: v for k, v in request.items() if k != "quantity"}
        for key, value in points.items():
            branch = _energy({**common, "value": str(value), "unit": quantity.get("unit", "J")}, data, dict(result))
            branches[key] = {"normalized": branch["normalized"], "classification": branch["classification"]}
        best = _energy({**common, "value": quantity["best"], "unit": quantity.get("unit", "J")}, data, result)
        best["interval"] = branches
        best["input_quantity"] = quantity.copy()
        return best
    value, unit = _quantity(request, "energy_j", "J")
    if unit not in ENERGY_UNITS:
        raise ValueError("unsupported energy unit; force, power and bare mass are not energy")
    energy = _multiply(value, Decimal(ENERGY_UNITS[unit]))
    row = _row(energy, data["attack_potency"]["finite_tiers"])
    classification = {"tier": row["tier"], "label": row["label"] + " level",
                      "lower_j": row["lower"], "upper_j_exclusive": row["upper"]}
    # '+' uses the AP page's strict 'greater than arithmetic mean' prose.
    # At exact midpoint the example's overlapping endpoints are disclosed.
    if row["upper"] is not None:
        low, high = Decimal(row["lower"]), Decimal(row["upper"])
        with localcontext() as ctx:
            ctx.prec = _precision(low, high, energy)
            midpoint = (low + high) / 2
        classification["arithmetic_midpoint_j"] = _display(midpoint)
        classification["plus"] = energy > midpoint
        classification["midpoint_equality_requires_editorial_review"] = energy == midpoint
        if energy > midpoint:
            classification["label"] += "+"
    else:
        classification["plus"] = False
    attribute = request.get("attribute", "attack_potency")
    if attribute not in {"attack_potency", "striking_strength", "durability", "destructive_capacity"}:
        raise ValueError("energy attribute must identify attack_potency, striking_strength, durability or destructive_capacity")
    result.update({"attribute": attribute, "normalized": {"energy_j": _display(energy)},
                   "classification": classification,
                   "attribute_propagation": "none; an energy result does not automatically transfer between attributes"})
    return result


def _speed(request, data, result):
    speed_type = request.get("speed_type")
    if isinstance(speed_type, str):
        speed_type = speed_type.removesuffix("_speed")
    if speed_type not in SPEED_TYPES:
        raise ValueError("speed_type is required: attack, combat, reaction, travel or flight")
    value, unit = _quantity(request, "speed_m_s", "m/s")
    c = Decimal(data["speed"]["constants"]["c_m_s"])
    factors = {"m/s": Decimal(1), "km/s": Decimal(1000), "Mach": Decimal(343), "c": c,
               "%c": c / 100, "mph": Decimal("0.44704")}
    if unit == "km/h":
        with localcontext() as ctx:
            ctx.prec = _precision(value) + 32
            speed = value / Decimal("3.6")
    elif unit in factors:
        speed = _multiply(value, factors[unit])
    else:
        raise ValueError("unsupported speed unit; reaction/perception time needs a separately justified distance model")
    basis = request.get("boundary_basis", "canonical")
    if basis not in {"canonical", "printed_m_s"}:
        raise ValueError("boundary_basis must be canonical or printed_m_s")
    # Exact zero and exact c are singleton categories in the source chart.
    if speed == 0:
        label, row = "Immobile", None
    elif speed == c:
        label, row = "Speed of Light", None
    else:
        rows = data["speed"]["finite_tiers"]
        if basis == "printed_m_s":
            rows = [{**r, "lower": r["printed_lower_m_s"], "upper": r["printed_upper_m_s"]} for r in rows]
        row = _row(speed, rows)
        label = row["label"]
    classification = {"label": label, "speed_type": speed_type, "boundary_basis": basis}
    if row:
        classification.update({"lower_m_s": row["lower"], "upper_m_s_exclusive": row["upper"]})
    result.update({"speed_type": speed_type, "normalized": {"speed_m_s": _display(speed)},
                   "classification": classification,
                   "attribute_propagation": "none; attack/combat/reaction/travel/flight remain separate"})
    return result


def _lifting(request, data, result):
    mass, unit = _quantity(request, "mass_kg", "kg")
    factors = {"kg": "1", "t": "1000", "metric_ton": "1000", "g": "0.001"}
    if unit not in factors:
        raise ValueError("lifting accepts Earth-equivalent lifted mass; force needs an explicit force/gravity model outside this classifier")
    mass = _multiply(mass, Decimal(factors[unit]))
    row = _row(mass, data["lifting_strength"]["finite_tiers"])
    mechanism = request.get("mechanism", "physical")
    if mechanism not in {"physical", "telekinesis", "other"}:
        raise ValueError("mechanism must be physical, telekinesis or other")
    result.update({"normalized": {"mass_kg": _display(mass)},
                   "classification": {"label": row["label"], "lower_kg": row["lower"], "upper_kg_exclusive": row["upper"]},
                   "mechanism": mechanism,
                   "attribute_propagation": "none; lifting and striking/AP are independent, and telekinesis is not physical strength"})
    return result


def run(request):
    """Return an auditable finite-table reference, not semantic acceptance.

    energy: {operation: energy, energy_j: '1.046e9'}
    speed: {operation: speed, value: '10', unit: Mach, speed_type: combat}
    lifting: {operation: lifting, mass_kg: '1000', mechanism: physical}
    info returns source coverage and supported boundaries without live retrieval.
    """
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    operation = request.get("operation", request.get("op", "info"))
    if operation not in {"info", "energy", "speed", "lifting"}:
        raise ValueError("operation must be info, energy, speed or lifting")
    data, digest = _data()
    result = _base(data, digest, operation)
    if operation == "info":
        return {**result, "coverage": data["coverage"], "operations": ["info", "energy", "speed", "lifting"],
                "energy_units": list(ENERGY_UNITS), "speed_types": sorted(SPEED_TYPES),
                "boundary_policy": data["boundary_policy"],
                "qualitative_categories_require_host_review": {
                    "speed": data["speed"]["qualitative_categories"],
                    "lifting": data["lifting_strength"]["qualitative_categories"]}}
    if operation == "energy":
        return _energy(request, data, result)
    if operation == "speed":
        return _speed(request, data, result)
    return _lifting(request, data, result)
