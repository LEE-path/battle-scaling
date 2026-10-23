"""Evidence-packet review for the pinned VSB high-tier rules.

This does not read canon, validate source truth, or grant wiki approval. A source-
bound host claim is necessary; no dimensional number or tier label is sufficient.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re

RULESET_ID = "vsb-high-current-2026-10-21"
PROFILE_ID = "vsb-current-2026-10-21"
VALIDATION_SCOPE = (
    "Evidence-packet completeness and supplied-claim consistency only; the host must "
    "read and interpret canon, verify provenance and scope, and review counterevidence. "
    "Not semantic verification, an automatic cosmology inference, or VSB Wiki approval."
)
RULE_SOURCES = [
    {"id": "vsb-tiering", "title": "Tiering System", "revision_id": 9401765,
     "url": "https://vsbattles.fandom.com/wiki/Tiering_System", "access": "readable"},
    {"id": "vsb-tiering-faq", "title": "Tiering System FAQ", "revision_id": 9689808,
     "url": "https://vsbattles.fandom.com/wiki/Tiering_System_FAQ", "access": "readable"},
    {"id": "vsb-rf", "title": "Reality-Fiction Transcendence", "revision_id": 9706463,
     "url": "https://vsbattles.fandom.com/wiki/Reality-Fiction_Transcendence", "access": "readable"},
    {"id": "vsb-omnipotence", "title": "Omnipotence", "revision_id": 9411237,
     "url": "https://vsbattles.fandom.com/wiki/Omnipotence", "access": "readable"},
]
COMMON = {
    "structure_is_real": "The stated structure exists in the canon; not merely a mathematical idea, metaphor, or label.",
    "full_scope_effect": "The selected character/state significantly affects, creates, destroys, or suitably embodies the entire qualifying structure.",
    "version_state_match": "The cited structure, ability, feats and scaling bridge apply to the selected continuity and compatible state/configuration.",
    "contradictions_reviewed": "Relevant failures, contextual restrictions, alternative readings and contradictions have actually been reviewed and resolved or explicitly bounded.",
}
DESCRIPTIONS = {
    **COMMON,
    "finite_universal_3d_scope": "The effect covers a finite 3-D universe at least as large as the observable universe under the 3-A standard.",
    "actual_infinite_3d_magnitude": "An actual infinite 3-D magnitude/energy/mass or full infinite 3-D extent is affected; not merely endless stamina or growth potential.",
    "full_universal_spacetime": "An entire universal-scale 4-D spacetime, or equivalent significant 4-D structure, is affected rather than one spatial snapshot.",
    "direct_spacetime_effect": "The whole spacetime effect is direct, not only later disappearance through a causal paradox.",
    "independent_spacetimes": "The counted universes have separate qualifying spacetimes; ordinary 3-D travel or temporary labels do not establish independence.",
    "complete_spacetimes": "Every counted object meets the full, significant spacetime scope, including the FAQ's branching/merging restrictions.",
    "direct_multi_spacetime_effect": "The selected feat/ability directly covers the full counted collection, not hypothetical storage capacity or a single shared causal origin.",
    "countably_infinite_spacetimes": "The qualifying collection contains actually countably infinitely many independent complete spacetimes, not an arbitrarily large finite count.",
    "significant_dimensional_superiority": "The additional axes/structural gaps are real and significant under VSB standards; merely being called n-D or being in a higher place is insufficient.",
    "appropriate_dimensional_scope": "The affected full structure has the requested ordinary real-coordinate dimensional scope or an explicitly justified equivalent, rather than negligible extra axes.",
    "continuum_many_spacetimes": "Actually real-number-cardinality many independent complete universes/spacetimes are affected, created, destroyed, or embodied.",
    "infinite_dimensional_structure": "The fully affected structure has actually infinitely many significant dimensions, or a qualifying union covering all finite dimensional spaces.",
    "uncountable_dimensional_or_higher_cardinal_scope": "The full structure has uncountably many or more dimensions, or the higher-cardinality quantitative scope permitted by the FAQ; the counted objects and actual existence are specified.",
    "higher_cardinal_quantitative_scope": "The actually existing full quantitative structure meets the FAQ's higher-cardinality threshold beyond the real continuum (such as the power set of the power set of aleph-0), with the counted objects specified; a mere continuum of points or mathematical discussion does not suffice.",
    "all_possible_dimensional_spaces": "The structure encompasses all possible dimensional spaces, corresponding to the Von Neumann universe or a qualifying encompassing structure.",
    "genuine_superiority_over_dimensionality": "Generic above-dimensions wording has been contextually established as actual superiority over dimensionality, not lack of dimensions, travel, age, or a local realm.",
    "above_dimensions_context_verified": "The specific VSB Low 1-A default for genuinely superior above-dimensional wording is applicable after contextual and contradiction review.",
    "ontological_qualitative_superiority": "The higher existence's very ontological nature is qualitatively superior, not merely more numerous, larger, nonphysical, or stronger.",
    "no_lower_composition_access": "No union, addition, permutation or quantitative extension within the lower nature can reach or compose the higher nature; alleged illicit interactions are reviewed.",
    "infinite_qualitative_hierarchy": "Actually infinitely many qualifying ontological/qualitative layers are established, not infinitely many equal-tier items or dimensions.",
    "meta_qualitative_framework_transcendence": "The entire framework/algorithm generating a 1-A qualitative hierarchy is surpassed, not just one more layer of that same algorithm.",
    "all_conceivable_meta_extensions": "Meta-qualities, meta-meta-qualities and all conceivable extensions of that process are covered, not one finite or repeatable stack.",
    "logical_possibility_scope": "The relevant scope is logical possibility at least as broad as the VSB default classical logical space; physical branching or a more restrictive logic is not enough.",
    "arbitrarily_large_logically_possible_worlds": "The character can actualize arbitrarily large logically possible worlds under the qualifying logical scope, with a demonstrated ability/structure bridge.",
    "embodies_all_logical_possibilities": "The character actually embodies the whole framework of all logically possible worlds, not a very large subset or an isolated possible world.",
    "no_independent_maximal_logical_spaces": "For the maximal framework-embodiment route, purported independent peer all-logical spaces and further same-framework power gaps have been excluded or resolved.",
    "trans_hierarchical_supremacy": "All forms of hierarchical extension, including High 1-A+ qualities, are utterly exceeded; no merely longer hierarchy is substituted.",
    "transcends_ontological_distinctions": "The being surpasses ontological distinctions, object divisions and qualitative multiplicity themselves; vague all-in-one or omnipotent titles are insufficient.",
    "primacy": "Nothing above, more fundamental than, prior to, or externally conditioning the Absolute is present.",
    "unity": "No mutually exclusive coordinate Absolute peers exist; multiple names/incarnations, if any, are demonstrably the same indivisible Absolute.",
    "immutability": "No intrinsic becoming, new apotheosis, retrospective creation, growth, sequential reaction or change contradicts the Absolute; external perspectives are distinguished.",
    "indivisibility": "No literal pieces, fractional power, parts, or fusion of lesser powers constitute the Absolute; avatars and blessings are distinguished from its nature.",
    "zero_counterexamples_resolved": "Actual limitations, derivation, divided peers, defeat, change and other Omnipotence disqualifiers have been specifically reviewed; stock labels do not waive them.",
}


def _rule(label, required, *, routes=None, numeric=None, qualifier=""):
    return {"label": label, "required": list(required), "routes": routes or {},
            "numeric": numeric or {}, "qualifier": qualifier}


_QUAL = ["ontological_qualitative_superiority", "no_lower_composition_access"]
_DIM = ["significant_dimensional_superiority", "appropriate_dimensional_scope"]
_MULTI = ["independent_spacetimes", "complete_spacetimes", "direct_multi_spacetime_effect"]
RULES = {
    "3-A": _rule("Universe level", ["finite_universal_3d_scope"]),
    "High 3-A": _rule("High Universe level", ["actual_infinite_3d_magnitude"]),
    "Low 2-C": _rule("Universe level+", ["full_universal_spacetime", "direct_spacetime_effect"]),
    "2-C": _rule("Low Multiverse level", _MULTI, numeric={"count": [2, 1000]}),
    "2-B": _rule("Multiverse level", _MULTI, numeric={"count": [1001, None]}),
    "2-A": _rule("Multiverse level+", _MULTI + ["countably_infinite_spacetimes"]),
    "Low 1-C": _rule("Low Complex Multiverse level", [], routes={
        "dimensional": {"required": _DIM, "numeric": {"dimensions": [5, 5]}},
        "continuum_spacetimes": {"required": _MULTI + ["continuum_many_spacetimes"], "numeric": {}},
    }),
    "1-C": _rule("Complex Multiverse level", _DIM, numeric={"dimensions": [6, 9]}),
    "High 1-C": _rule("High Complex Multiverse level", _DIM, numeric={"dimensions": [10, 11]}),
    "1-B": _rule("Hyperverse level", _DIM, numeric={"dimensions": [12, None]}),
    "High 1-B": _rule("High Hyperverse level", ["significant_dimensional_superiority", "infinite_dimensional_structure"]),
    "High 1-B+": _rule("High Hyperverse level+", [], routes={
        "dimensional": {"required": ["significant_dimensional_superiority", "uncountable_dimensional_or_higher_cardinal_scope"], "numeric": {}},
        "higher_cardinal_structure": {"required": ["higher_cardinal_quantitative_scope"], "numeric": {}},
    }, qualifier="AP plus modifier, not a separate base tier"),
    "Low 1-A": _rule("Low Outerverse level", [], routes={
        "all_dimensional_spaces": {"required": ["all_possible_dimensional_spaces"], "numeric": {}},
        "valid_above_dimensions": {"required": ["genuine_superiority_over_dimensionality", "above_dimensions_context_verified"], "numeric": {}},
    }),
    "1-A": _rule("Outerverse level", _QUAL),
    "1-A+": _rule("Outerverse level+", _QUAL + ["infinite_qualitative_hierarchy"], qualifier="AP plus modifier, not a separate base tier"),
    "High 1-A": _rule("High Outerverse level", _QUAL + ["meta_qualitative_framework_transcendence"]),
    "High 1-A+": _rule("High Outerverse level+", _QUAL + ["meta_qualitative_framework_transcendence", "all_conceivable_meta_extensions", "logical_possibility_scope"], routes={
        "actualize_possible_worlds": {"required": ["arbitrarily_large_logically_possible_worlds"], "numeric": {}},
        "embody_logical_space": {"required": ["embodies_all_logical_possibilities", "no_independent_maximal_logical_spaces"], "numeric": {}},
    }, qualifier="AP plus modifier; actualization and maximal-framework embodiment are distinct routes"),
    "0": _rule("Boundless", ["trans_hierarchical_supremacy", "transcends_ontological_distinctions", "primacy", "unity", "immutability", "indivisibility", "zero_counterexamples_resolved"], qualifier="Absolute itself; ordinary Tier 0 versus Tier 0 combat is inapplicable"),
}
READABLE = {"readable", "verified", "provided"}
FORBIDDEN_REQUEST_FIELDS = {"classification", "result", "review_result", "validated", "approved", "status", "wangba_tier", "auto_tier"}


def _tier(value):
    if not isinstance(value, str):
        raise ValueError("requested_tier must be a VSB tier code")
    normalized = re.sub(r"\s+", " ", value.strip())
    normalized = re.sub(r"^(Low|High)\s*(?=\d)", r"\1 ", normalized)
    normalized = normalized.replace(" +", "+")
    if normalized not in RULES:
        raise ValueError("unsupported VSB high-tier code; labels and other standards are not tier codes")
    return normalized


def _base(operation):
    encoded = json.dumps({"common": COMMON, "descriptions": DESCRIPTIONS, "rules": RULES,
                          "sources": RULE_SOURCES}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {"operation": operation, "standard": "vsb", "ruleset_id": RULESET_ID,
            "profile_id": PROFILE_ID, "ruleset_sha256": hashlib.sha256(encoded).hexdigest(),
            "rule_sources": copy.deepcopy(RULE_SOURCES), "validation_scope": VALIDATION_SCOPE,
            "not_an_automatic_tier_conversion": True}


def _selected(tier, route=None):
    rule = RULES[tier]
    choices = rule["routes"]
    if choices:
        route = route or next(iter(choices))
        if route not in choices:
            raise ValueError("unsupported route for requested_tier")
        chosen = choices[route]
    else:
        if route is not None:
            raise ValueError("this tier has no alternative route")
        chosen = {"required": [], "numeric": {}}
    keys = list(COMMON) + rule["required"] + chosen["required"]
    numeric = {**rule["numeric"], **chosen["numeric"]}
    return rule, route, keys, numeric


def _sources(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        rows = []
        for sid, row in value.items():
            if not isinstance(sid, str) or not sid or not isinstance(row, dict):
                raise ValueError("sources mapping requires nonempty ids and source objects")
            if row.get("id", sid) != sid:
                raise ValueError("source id conflicts with its mapping key")
            rows.append({**row, "id": sid})
    elif isinstance(value, list):
        rows = value
    else:
        raise ValueError("sources must be a list or id-to-source mapping")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("every source requires a nonempty id")
        sid = row["id"]
        if sid in result:
            raise ValueError("duplicate source id")
        result[sid] = dict(row)
    return result


def _citation_check(ids, sources):
    if not isinstance(ids, list) or any(not isinstance(sid, str) or not sid for sid in ids):
        raise ValueError("source_ids must be a list of nonempty source ids")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate citation id")
    issues, assumed = [], False
    if not ids:
        issues.append("no_cited_source")
    for sid in ids:
        source = sources.get(sid)
        if source is None:
            issues.append(f"unknown_source:{sid}")
            continue
        if source.get("access") not in READABLE:
            issues.append(f"source_not_readable:{sid}")
        if any(not isinstance(source.get(k), str) or not source[k].strip() for k in ("title", "origin", "locator")):
            issues.append(f"source_provenance_incomplete:{sid}")
        if source.get("origin") in {"assumption", "synthetic"}:
            assumed = True
    return issues, assumed


def _reason(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires a nonempty reasoning statement")
    value = value.strip()
    labels = set(RULES) | {r["label"] for r in RULES.values()} | {"true", "false", "verified", "approved", "supported"}
    if value in labels:
        raise ValueError(f"{name} cannot be a tier label or a supplied review result")
    return value


def _assumption(value):
    if value is None:
        return None
    if isinstance(value, str):
        return _reason(value, "assumption")
    if not isinstance(value, dict):
        raise ValueError("assumption must be an explicit local explanation or object")
    if value.get("status", True) is not True:
        raise ValueError("assumption.status must be true when supplied")
    if set(value) - {"reason", "status", "source_ids"}:
        raise ValueError("unsupported assumption field")
    if "source_ids" in value and (not isinstance(value["source_ids"], list) or any(not isinstance(s, str) or not s for s in value["source_ids"])):
        raise ValueError("assumption source_ids must be a list")
    return _reason(value.get("reason"), "assumption")


def _claim(key, value, sources):
    if value is None:
        return {"criterion": key, "outcome": "unknown", "issues": ["missing_required_claim"]}
    if not isinstance(value, dict):
        raise ValueError(f"criterion {key} must be a claim object, not a label or boolean")
    if set(value) - {"status", "reason", "source_ids", "assumption"}:
        raise ValueError(f"unsupported field in criterion {key}")
    if "status" not in value or (value["status"] is not None and type(value["status"]) is not bool):
        raise ValueError(f"criterion {key} status must be true, false or null")
    reason = _reason(value.get("reason"), key)
    ids = value.get("source_ids", [])
    issues, assumed_source = _citation_check(ids, sources)
    assumption = _assumption(value.get("assumption"))
    row = {"criterion": key, "claimed_status": value["status"], "reason": reason,
           "source_ids": ids, "issues": issues}
    if value["status"] is False:
        row["outcome"] = "contradicted"
        if assumption:
            row["issues"].append("assumption_cannot_override_false")
    elif value["status"] is True and not issues and not assumed_source and not assumption:
        row["outcome"] = "supported_claim"
    elif assumption or (value["status"] is True and not issues and assumed_source):
        row["outcome"] = "assumed"
        row["assumption"] = assumption or "Only assumption/synthetic provenance supports this supplied claim."
    else:
        row["outcome"] = "unknown"
    return row


def _number(key, value, bounds, sources):
    if value is None:
        return {"parameter": key, "outcome": "unknown", "issues": ["missing_sourced_integer"]}
    if not isinstance(value, dict):
        raise ValueError(f"{key} requires an object with an integer value, reason and source_ids")
    if set(value) - {"value", "reason", "source_ids", "assumption"}:
        raise ValueError(f"unsupported field in parameter {key}")
    number = value.get("value")
    if type(number) is not int or number < 0:
        raise ValueError(f"{key}.value must be a nonnegative integer; no floats, infinities or boolean values")
    reason = _reason(value.get("reason"), key)
    ids = value.get("source_ids", [])
    issues, assumed_source = _citation_check(ids, sources)
    assumption = _assumption(value.get("assumption"))
    row = {"parameter": key, "value": number, "range": {"min": bounds[0], "max": bounds[1]},
           "reason": reason, "source_ids": ids, "issues": issues}
    if number < bounds[0] or (bounds[1] is not None and number > bounds[1]):
        row["outcome"] = "contradicted"
        row["issues"].append("integer_outside_requested_tier_range")
    elif issues:
        row["outcome"] = "unknown"  # Unsupported numbers cannot establish even a conditional numerical threshold.
    elif assumed_source or assumption:
        row["outcome"] = "assumed"
        row["assumption"] = assumption or "Assumption/synthetic provenance; not an established integer parameter."
    else:
        row["outcome"] = "supported_claim"
    return row


def run(request):
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    if FORBIDDEN_REQUEST_FIELDS.intersection(request):
        raise ValueError("supplied classifications or review results are not accepted as evidence")
    if request.get("standard", "vsb") != "vsb":
        raise ValueError("VSB high review cannot use another standard")
    for key in ("profile", "ruleset", "ruleset_id"):
        if key in request and request[key] not in {PROFILE_ID, RULESET_ID}:
            raise ValueError("requested ruleset/profile is not the pinned VSB high standard")
    operation = request.get("operation", request.get("op", "criteria"))
    if "op" in request and "operation" in request and request["op"] != request["operation"]:
        raise ValueError("conflicting operation fields")
    if operation not in {"criteria", "review"}:
        raise ValueError("operation must be criteria or review")
    result = _base(operation)
    if operation == "criteria":
        result["status"] = "reference_only"
        result["common_criteria"] = copy.deepcopy(COMMON)
        value = request.get("tier", request.get("requested_tier"))
        tiers = [_tier(value)] if value is not None else list(RULES)
        result["tiers"] = {tier: {**copy.deepcopy(RULES[tier]),
                                "criteria_descriptions": {k: DESCRIPTIONS[k] for k in sorted(
                                    set(COMMON) | set(RULES[tier]["required"]) |
                                    {k for route in RULES[tier]["routes"].values() for k in route["required"]})}}
                           for tier in tiers}
        return result
    if "tier" in request:
        raise ValueError("review uses requested_tier, not an already assigned tier")
    tier = _tier(request.get("requested_tier"))
    rule, route, keys, numeric = _selected(tier, request.get("route"))
    sources = _sources(request.get("sources"))
    claims = request.get("criteria", {})
    if not isinstance(claims, dict):
        raise ValueError("criteria must be a mapping of criterion keys to claim objects")
    if set(claims) - set(keys):
        raise ValueError("unknown or irrelevant criterion; choose and inspect the appropriate route")
    if {"count", "dimensions"}.intersection(request) - set(numeric):
        raise ValueError("a finite count/dimension number cannot substitute for this tier's required structural criteria")
    rows = [_claim(key, claims.get(key), sources) for key in keys]
    parameters = [_number(key, request.get(key), bounds, sources) for key, bounds in numeric.items()]
    outcomes = {row["outcome"] for row in rows + parameters}
    if "contradicted" in outcomes:
        status = "blocked"
    elif "unknown" in outcomes:
        status = "undetermined"
    elif "assumed" in outcomes:
        status = "conditional"
    else:
        status = "supported_by_packet"
    result.update({"status": status, "requested_tier": tier, "route": route,
                   "classification": None, "criteria_review": rows, "parameter_review": parameters,
                   "required_criteria": keys, "adopted_source_ids": sorted({sid for row in rows + parameters
                       if row["outcome"] == "supported_claim" for sid in row.get("source_ids", [])}),
                   "automatic_propagation": "none; no multiplication, label conversion or dimensionality-to-stat propagation"})
    if status in {"supported_by_packet", "conditional"}:
        qualifier = "conditional on explicit local assumptions" if status == "conditional" else "supported by supplied evidence packet; not semantically certified"
        if rule["qualifier"]:
            qualifier += "; " + rule["qualifier"]
        result["classification"] = {"tier": tier, "label": rule["label"], "qualifier": qualifier}
    return result
