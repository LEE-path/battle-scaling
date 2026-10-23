"""Typed VSB quantity mappings for evidence reports; no cross-attribute scaling."""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation

from vsb_rules import ENERGY_UNITS, SPEED_TYPES, run

RULESET_ID = "vsb-current-2026-10-21"
ENERGY_ATTRIBUTES = {
    "attack_potency": "attack_potency", "attack_energy": "attack_potency", "ap": "attack_potency",
    "output": "attack_potency", "输出": "attack_potency",
    "striking_strength": "striking_strength", "striking_energy": "striking_strength",
    "durability": "durability", "body_durability": "durability", "体防": "durability",
    "destructive_capacity": "destructive_capacity", "destruction_energy": "destructive_capacity",
    "destruction": "destructive_capacity", "dc": "destructive_capacity", "破坏": "destructive_capacity",
}
SPEED_UNITS = {"m/s", "km/s", "km/h", "mph", "Mach", "c", "%c"}


def _quantity_points(quantity):
    if "value" in quantity:
        if "best" in quantity:
            raise ValueError("quantity uses either value or best as its central value")
        value = quantity["value"]
        points = {"min": quantity.get("min",value), "best": value, "max": quantity.get("max",value)}
    elif "best" in quantity:
        points = {"min": quantity.get("min", quantity["best"]), "best": quantity["best"],
                  "max": quantity.get("max", quantity["best"])}
    else:
        raise ValueError("quantity requires value or best; no most-likely value is inferred")
    checked = {}
    for key, value in points.items():
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValueError("quantity endpoints must be finite nonnegative decimals")
        if isinstance(value, str) and len(value) > 10000:
            raise ValueError("quantity endpoint is too long")
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("quantity endpoints must be finite decimals") from exc
        if not number.is_finite() or number < 0 or abs(number.adjusted()) > 100000:
            raise ValueError("quantity endpoints must be finite nonnegative decimals in the supported range")
        checked[key] = number
    if not checked["min"] <= checked["best"] <= checked["max"]:
        raise ValueError("quantity must satisfy min <= best <= max")
    # Retain the caller's exact strings, not float-normalized values.
    return points


def _unmapped(attribute, reason, status="not_applicable"):
    return {"ruleset_id": RULESET_ID, "standard": "vsb", "attribute": attribute,
            "status": status, "best_reference": None, "vsb_assessment": None,
            "reason": reason,
            "qualifier": "No VSB numerical category was assigned; a different physical attribute is never substituted."}


def _label(classification):
    if classification.get("tier"):
        return classification["tier"] + " (" + classification["label"] + ")"
    return classification["label"]


def map_quantity(attribute, quantity, context=None):
    """Map only a correctly typed finite quantity into the selected VSB table.

    Recognized: AP/striking/durability/DC energy, the five *_speed attributes,
    generic speed with context.speed_type, and lifting_strength in kg/t. A body
    mass, intelligence value, range or unsupported unit is not recast as one of
    those attributes. This is a numerical reference, not feat approval.
    """
    if not isinstance(attribute, str) or not attribute.strip():
        raise ValueError("attribute must be a nonempty string")
    if not isinstance(quantity, dict):
        raise ValueError("quantity must be an object")
    if context is None:
        context = {}
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    name = attribute.strip().lower()
    if quantity.get("kind") == "tier":
        return _unmapped(attribute, "A typed symbolic tier is not a finite physical measurement.")
    unit = quantity.get("unit")
    if not isinstance(unit, str):
        return _unmapped(attribute, "No supported physical unit was supplied.")
    unit = unit.replace(" TNT", "_TNT")
    request = None
    mapped_attribute = None

    if name in ENERGY_ATTRIBUTES:
        if unit not in ENERGY_UNITS:
            return _unmapped(attribute, "This energy attribute requires a supported energy unit; N, W, kg and velocity do not qualify.")
        mapped_attribute = ENERGY_ATTRIBUTES[name]
        request = {"operation": "energy", "attribute": mapped_attribute}
    elif name == "speed" or name in {kind + "_speed" for kind in SPEED_TYPES}:
        if unit not in SPEED_UNITS:
            return _unmapped(attribute, "This speed table requires a supported distance/time unit; reaction/perception seconds alone are insufficient.")
        kind = None if name == "speed" else name.removesuffix("_speed")
        declared = context.get("speed_type")
        if isinstance(declared, str):
            declared = declared.removesuffix("_speed")
        if kind is None:
            if not isinstance(declared, str) or declared not in SPEED_TYPES:
                result = _unmapped(attribute, "Generic speed requires context.speed_type=attack/combat/reaction/travel/flight.", "requires_review")
                result["best_reference"] = "未定（缺少有效 speed_type）"
                result["qualifier"] = result["reason"] + " No default combat/flight/reaction type is assumed."
                return result
            kind = declared
        elif declared is not None and declared != kind:
            result = _unmapped(attribute, "context.speed_type conflicts with the explicit attribute; resolve the ownership before mapping.", "requires_review")
            result["best_reference"] = "未定（速度属性冲突）"
            result["qualifier"] = result["reason"]
            return result
        mapped_attribute = kind + "_speed"
        request = {"operation": "speed", "speed_type": kind}
        if "boundary_basis" in context:
            request["boundary_basis"] = context["boundary_basis"]
    elif name == "lifting_strength":
        if unit not in {"kg", "t"}:
            return _unmapped(attribute, "lifting_strength requires established Earth-equivalent lifted mass in kg/t; raw N needs a justified conversion model.")
        mapped_attribute = "lifting_strength"
        request = {"operation": "lifting", "mechanism": context.get("mechanism", "physical")}
    else:
        return _unmapped(attribute, "This attribute has no supported finite AP/speed/lifting mapping; body mass is not lifting strength.")

    points = _quantity_points(quantity)
    if request["operation"] == "energy":
        assessment = run({**request, "quantity": {**points, "unit": unit}})
    else:
        branches = {}
        best = None
        for key, value in points.items():
            branch = run({**request, "value": value, "unit": unit})
            branches[key] = {"normalized": branch["normalized"], "classification": branch["classification"]}
            if key == "best":
                best = branch
        assessment = best
        assessment["interval"] = branches
        assessment["input_quantity"] = copy.deepcopy(quantity)
    intervals = assessment["interval"]
    return {"ruleset_id": assessment["ruleset_id"], "standard": "vsb",
            "ruleset_sha256": assessment["ruleset_sha256"],
            "status": "vsb_numerical_mapping", "attribute": attribute, "mapped_attribute": mapped_attribute,
            "min_reference": _label(intervals["min"]["classification"]),
            "best_reference": _label(assessment["classification"]),
            "max_reference": _label(intervals["max"]["classification"]),
            "qualifier": "VSB typed numerical reference only; establish the original feat, applicable mechanics and this attribute's ownership separately. No cross-attribute propagation.",
            "vsb_assessment": assessment}
