"""VSB acceptance gates around the unchanged general-purpose physics models.

The caller supplies CASE sources as the separate ``sources`` argument. This
module does not browse or verify semantic entailment of source statements.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

import physics as base_physics

POLICY_ID = "vsb_physics_20261021"
READABLE = {"verified", "provided", "read", "verified_via_host_browser"}
RULE_SOURCES = {
    "kinetic": "https://vsbattles.fandom.com/wiki/Kinetic_Energy_Feats?oldid=9342768",
    "mass_energy": "https://vsbattles.fandom.com/wiki/Mass-energy_conversion_feats?oldid=9448480",
}
SCOPE = (
    "Checks selected VSB mathematical admissibility rules and caller-declared readable primary-source metadata; "
    "does not read original works, authenticate sources, establish statement entailment, approve material/visual "
    "measurements or certify that a calculation has been accepted by VSB staff."
)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _source_map(sources):
    if sources is None:
        return {}, []
    if isinstance(sources, dict):
        converted = []
        for sid, item in sources.items():
            if not _text(sid) or not isinstance(item, dict) or item.get("id", sid) != sid:
                raise ValueError("sources map requires matching nonempty IDs and objects")
            converted.append({**item, "id": sid})
        sources = converted
    if not isinstance(sources, list) or any(not isinstance(item, dict) or not _text(item.get("id")) for item in sources):
        raise ValueError("sources must be a list or keyed map of source objects")
    mapping, duplicates = {}, set()
    for item in sources:
        sid = item["id"]
        if sid in mapping:
            duplicates.add(sid)
        mapping[sid] = item
    for sid in duplicates:
        del mapping[sid]
    return mapping, sorted(duplicates)


def _evidence(node, sources, required_flag):
    reasons, used = [], []
    if not isinstance(node, dict):
        return False, ["Supply an explicit statement and bound readable primary-source IDs."], used
    if node.get(required_flag) is not True:
        reasons.append(required_flag + " must be explicitly declared true and semantically checked by the host.")
    if not _text(node.get("statement")):
        reasons.append("Provide the actual relevant statement with its mechanism/energy meaning.")
    ids = node.get("source_ids")
    if not isinstance(ids, list) or not ids or any(not _text(sid) for sid in ids):
        reasons.append("Provide nonempty source_ids bound to this exact statement.")
        ids = []
    for sid in dict.fromkeys(ids):
        source = sources.get(sid)
        if source is None:
            reasons.append("Missing or duplicate/ambiguous source: " + sid)
        elif not isinstance(source.get("access"), str) or source.get("access") not in READABLE:
            reasons.append("Unreadable or index-only source: " + sid)
        elif source.get("origin") != "primary":
            reasons.append("An original-work primary source is required: " + sid)
        elif not _text(source.get("title")) or not _text(source.get("locator")):
            reasons.append("Primary source needs title and an exact locator: " + sid)
        else:
            used.append(sid)
    return not reasons, reasons, used


def _review(status="ok", reasons=None, source_ids=None):
    return {"policy_id": POLICY_ID, "status": status, "reasons": reasons or [],
            "source_ids": source_ids or [], "validation_scope": SCOPE,
            "original_source_verified": False,
            "rule_sources": list(RULE_SOURCES.values())}


def _withheld(request, status, reasons, reference=None, source_ids=None):
    output = {"model": request.get("model"), "standard": "vsb", "status": status,
              "eligible_for_attachment": False,
              "policy_review": _review(status, reasons, source_ids)}
    if reference is not None:
        output["mathematical_reference"] = reference
        output["policy_review"]["reference_scope"] = "Counterfactual/raw mathematics only; every nested value is ineligible for rating attachment."
    return output


def _cap_value(raw_value, mass, speed, exception):
    classical = 0.5 * mass * speed * speed
    cap = 4 * classical
    if not math.isfinite(classical) or not math.isfinite(cap):
        raise ValueError("VSB kinetic reference overflow; use a reviewed higher precision model")
    accepted = raw_value if exception else min(raw_value, cap)
    return accepted, {"newtonian_energy_j": classical, "four_times_newtonian_j": cap,
                      "uncapped_relativistic_energy_j": raw_value,
                      "accepted_energy_j": accepted, "cap_applied": accepted < raw_value,
                      "explicit_statement_exception": exception}


def _relativistic(output, request, exception):
    output = copy.deepcopy(output)
    raw = copy.deepcopy(output)
    m, v = output["inputs"]["mass"]["value"], output["inputs"]["speed"]["value"]
    accepted, cap = _cap_value(output["result"]["value"], m, v, exception)
    output["raw_calculation"] = raw
    output["result"]["value"] = accepted
    output["result"]["tnt_equivalent"]["value"] = accepted / base_physics.TNT_J_PER_TONNE
    output["steps"].append({"quantity": "vsb_accepted_kinetic_energy", "unit": "J", "value": accepted,
                            "formula": "K_rel (sourced explicit-energy exception)" if exception else "min(K_rel, 4 * K_Newtonian)",
                            "substitution": f"K_rel={cap['uncapped_relativistic_energy_j']}; K_Newtonian={cap['newtonian_energy_j']}"})
    output["policy_review"]["kinetic_cap"] = cap
    if "sensitivity" in output:
        # Apply the same policy to every corner, not only the base/best point.
        for case in output["sensitivity"]["cases"]:
            cm = case["inputs"].get("mass", m)
            cv = case["inputs"].get("speed", v)
            original = case["value"]
            case["value"], detail = _cap_value(original, cm, cv, exception)
            case["policy_review"] = detail
        values = [case["value"] for case in output["sensitivity"]["cases"]]
        output["sensitivity"]["sampled_min"] = min(values)
        output["sensitivity"]["sampled_max"] = max(values)
        output["sensitivity"]["policy_applied_to_all_corners"] = True
    return output


def calculate(request, sources=None):
    """Calculate with VSB policy; raw physics request fields stay compatible.

    Optional request.vsb_policy:
      relativistic_exception: {explicit_energy_statement: true,
                              statement: '...', source_ids: ['original']}
      mass_energy_conversion: {explicit_conversion_mechanism: true,
                               statement: '...', source_ids: ['original']}

    ``sources`` must be injected from the surrounding CASE. A nested request
    cannot replace that catalog. Blocked/undetermined outputs have no top-level
    result; their mathematical_reference must never be attached as a tier anchor.
    """
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    if "sources" in request:
        raise ValueError("Inject CASE sources through calculate(..., sources=...); nested source catalogs are not accepted")
    policy = request.get("vsb_policy", {})
    if not isinstance(policy, dict) or set(policy) - {"relativistic_exception", "mass_energy_conversion"}:
        raise ValueError("vsb_policy supports only relativistic_exception and mass_energy_conversion")
    raw_request = {key: copy.deepcopy(value) for key, value in request.items() if key != "vsb_policy"}
    model = raw_request.get("model")
    if not isinstance(model, str):
        raise ValueError("model must be a supported model name")
    if "relativistic_exception" in policy and model != "relativistic_kinetic":
        raise ValueError("relativistic_exception applies only to relativistic_kinetic")
    if "mass_energy_conversion" in policy and model != "mass_energy":
        raise ValueError("mass_energy_conversion applies only to mass_energy")
    catalog, duplicates = _source_map(sources)

    if model == "mass_energy":
        gate = policy.get("mass_energy_conversion")
        valid, reasons, used = _evidence(gate, catalog, "explicit_conversion_mechanism")
        original_app = raw_request.get("applicability", {})
        if not isinstance(original_app, dict):
            raise ValueError("applicability must be an object")
        known_failure = original_app.get("physical_mass_conversion_established") is False
        if known_failure:
            valid = False
            reasons.append("The supplied applicability explicitly denies physical mass-energy conversion.")
        mathematical = copy.deepcopy(raw_request)
        if valid:
            mathematical["applicability"] = {**original_app, "physical_mass_conversion_established": True,
                                             "conversion_evidence": gate["statement"]}
        elif original_app.get("physical_mass_conversion_established") is not True or not _text(original_app.get("conversion_evidence")):
            # This construction is explicitly counterfactual, stored only below
            # mathematical_reference, and cannot be routed into an attachment.
            mathematical["applicability"] = {**original_app, "physical_mass_conversion_established": True,
                "conversion_evidence": "COUNTERFACTUAL arithmetic benchmark only: if the stated mass fraction converted; actual mechanism is NOT established."}
        raw = base_physics.calculate(mathematical)
        if not valid:
            return _withheld(raw_request, "blocked" if known_failure else "undetermined", reasons, raw, used)
        output = raw
        output["policy_review"] = _review(source_ids=used)
        output["policy_review"]["mass_energy_conversion"] = {"statement": gate["statement"], "source_ids": used,
                                                              "input_declares_explicit_mechanism": True}
    else:
        try:
            output = base_physics.calculate(raw_request)
        except ValueError as exc:
            if model in {"kinetic", "relativistic_kinetic"} and "speed must be < c" in str(exc):
                return _withheld(raw_request, "blocked", ["VSB prohibits massive-body kinetic-energy calculations at or above c, including interval endpoints; an exception cannot override this."])
            raise
        output["policy_review"] = _review()
        if model == "relativistic_kinetic":
            exception = False
            if "relativistic_exception" in policy:
                exception, reasons, used = _evidence(policy["relativistic_exception"], catalog, "explicit_energy_statement")
                if not exception:
                    return _withheld(raw_request, "undetermined", reasons, output, used)
                output["policy_review"]["source_ids"] = used
                output["policy_review"]["relativistic_exception"] = copy.deepcopy(policy["relativistic_exception"])
            output = _relativistic(output, raw_request, exception)
    output.update({"standard": "vsb", "status": "ok", "eligible_for_attachment": True})
    output["policy_review"]["request_sha256"] = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    output["policy_review"]["source_catalog_duplicates"] = duplicates
    output["limitations"].append("VSB numerical policy eligibility is not proof of scene applicability, transfer to AP, or VSB staff acceptance; host evidence review remains required.")
    return output
