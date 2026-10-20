"""Source-specific 2026 handbook mappings, with explicit evidence and definition gaps.

Public APIs: enrich(request, out, rule) after typed core arithmetic; analyze(request,
rule) for li, dao, handbook_constructive, handbook_standard and handbook_case.
No global tier ordering, N/phi conversion, hidden text length scoring or network.
"""
from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
BASE_ID = "high-wangba-handbook-2026-07-30"
KINDS = {"li", "dao", "handbook_constructive", "handbook_standard", "handbook_case", "standard"}
MODE_ALIASES = {"常态": "normal", "最高": "highest", "扒下限": "lowball"}


def _blank(request, rule):
    mode = MODE_ALIASES.get(request.get("mode", "normal"), request.get("mode", "normal"))
    if mode not in {"normal", "highest", "lowball"}:
        raise ValueError("invalid mode")
    assumptions = request.get("assumptions", [])
    if not isinstance(assumptions, list):
        raise ValueError("assumptions must be a list")
    provenance = list(rule.get("sources", []))
    for field in ("source", "sources"):
        supplied = request.get(field)
        if supplied is None:
            continue
        supplied = [supplied] if isinstance(supplied, dict) else supplied
        if not isinstance(supplied, list):
            raise ValueError(field + " must contain source objects")
        for item in supplied:
            if (not isinstance(item, dict) or not (item.get("path") or item.get("url"))
                    or not item.get("locator")):
                raise ValueError("each supplied source needs path/url and locator")
            if item not in provenance:
                provenance.append(item)
    return {"schema_version": "1.0", "engine": "battle-scaling.handbook_high",
            "status": "underdetermined", "mode": mode, "result": {}, "steps": [],
            "assumptions": list(assumptions), "mappings": [], "provenance": provenance,
            "warnings": [], "limits": [rule.get("unit_warning", "Source-specific community convention."),
                "Source IDs and supplied facts are checked structurally, not authenticated by this offline engine."],
            "axioms": request.get("axioms", []),
            "ruleset": {k: rule.get(k) for k in ("id", "title", "status", "source", "read_date")}}


def _ids(value):
    return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)


def _source_present(obj):
    value = obj.get("source") or obj.get("sources")
    if isinstance(value, dict):
        return bool((value.get("path") or value.get("url")) and value.get("locator"))
    return isinstance(value, list) and bool(value) and all(
        isinstance(s, dict) and (s.get("path") or s.get("url")) and s.get("locator") for s in value)


def _gap(out, code, message, **details):
    gap = {"code": code, "message": message, **details}
    gaps = out.setdefault("structured_gaps", [])
    if gap not in gaps:
        gaps.append(gap)
    return gap


def _map(out, rule, label, clause_id, basis, *, status="conditional_on_handbook_and_supplied_evidence", source=None, **extra):
    if source is None:
        source = next((s for s in rule.get("sources", []) if s.get("clause_id") == clause_id), None)
    source = dict(source or rule.get("source", {}))
    if source.get("clause_id") not in {None, clause_id}:
        # A general ruleset locator is still useful, but is not the cited clause.
        source.pop("clause_id", None)
        source["source_scope"] = "ruleset_overview_not_exact_clause"
    item = {"label": label, "status": status, "basis": basis,
            "ruleset": rule["id"], "standard": rule.get("standard"), "clause_id": clause_id,
            "source": source, "scope": "typed/world structure only; no automatic character AP/durability transfer", **extra}
    if item not in out["mappings"]:
        out["mappings"].append(item)


def _aleph1_bound(result):
    if result.get("countability") != "uncountable":
        return False
    index = result.get("aleph_index")
    if isinstance(index, int) and not isinstance(index, bool) and index >= 1:
        return True
    if result.get("domain") == "ordinal" and result.get("canonical") == "omega1":
        return True
    return bool(re.fullmatch(r"aleph[1-9][0-9]*", str(result.get("lower_bound", ""))))


def _parse(text):
    # Late import keeps high_tier -> handbook_high delegation acyclic.
    import high_tier
    return high_tier.parse(text)


def _mathematical_map(request, out, rule, result, *, node=None):
    standard = rule.get("standard")
    if standard not in {"handbook_ordinal", "constructive_new"}:
        return
    is_strong = result.get("classification") == "strongly_inaccessible"
    bounded = _aleph1_bound(result) or is_strong
    if standard == "handbook_ordinal":
        if request.get("kind") == "ordinal" and node is None:
            expression = request.get("expression")
            ast = _parse(expression)
            for p in rule.get("ordinal_patterns", []):
                if ast == _parse(p["expression"]) or (p.get("canonical") and result.get("canonical") == p["canonical"]):
                    _map(out, rule, p["label"], p["clause_id"], "typed_ordinal_pattern",
                         interpretation="Source infinite is interpreted as omega for this explicit ordinal request; this is not N=omega.")
                    if p.get("extra_assumption"):
                        out["assumptions"].append({"text": p["extra_assumption"], "type": "handbook_ordinal_interpretation"})
                    break
        if bounded:
            _map(out, rule, rule["outer_label"], rule["outer_clause_id"], "proved_typed_aleph1_lower_bound", node=node)
            if is_strong:
                supplement = rule["strong_inaccessible_supplement"]
                _map(out, {**rule, "id": supplement["ruleset"], "standard": "constructive_new"},
                     supplement["label"], supplement["clause_id"], "strong_inaccessible_criteria",
                     source=supplement["source"], node=node)
            elif result.get("aleph_index") is not None:
                _map(out, {**rule, "id": BASE_ID + "-new", "standard": "constructive_new"},
                     rule["supplementary_new_aleph_label"], "HR-NEW-01", "aleph_object_lower_bound_only", node=node,
                     source={**rule["strong_inaccessible_supplement"]["source"], "clause_id": "HR-NEW-01", "short_excerpt": "论外三线（论外守门员）：阿列夫数"})
                _gap(out, "finer_new_property_not_established", "An aleph name/lower bound does not establish huge/inaccessible/model/framework properties; use -new with typed properties for finer placement.", node=node)
            else:
                _gap(out, "outer_finer_standard_required", "The typed lower bound reaches the p250 gate; no finer named property is established. Select the explicit -new standard and supply its construction criteria.", node=node)
        elif result.get("countability") in {"countable", "finite"}:
            _gap(out, "countable_not_outer", "Finite/countable ordinal progress is not a proved corresponding cardinal >=aleph1.", node=node)
    elif standard == "constructive_new":
        if is_strong:
            row = next(x for x in rule["rules"] if x["id"] == "HR-NEW-02")
            _map(out, rule, row["label"], row["id"], "strong_inaccessible_criteria", source=row["source"], node=node)
        elif result.get("classification") == "weakly_inaccessible":
            _gap(out, "inaccessible_terminology_ambiguous", "The handbook says inaccessible without fixing weak/strong terminology; weak properties alone are not silently upgraded to strong.", clause_id="HR-NEW-02", node=node)
        elif bounded:
            row = rule["rules"][0]
            _map(out, rule, row["label"] + "及以上（条件下界）", row["id"], "proved_typed_aleph1_lower_bound", source=row["source"], node=node)
            _gap(out, "finer_new_property_not_established", "No inaccessible/huge/theory/framework property follows merely from this cardinal lower bound.", node=node)
        elif result.get("countability") in {"countable", "finite"}:
            _gap(out, "aleph_index_and_gate_gap", "Appendix p285 says aleph numbers without an index, while p250 uses aleph1 as the outer gate; countable objects are not automatically outer.", node=node)


def _named_map(request, out, rule):
    if rule.get("standard") != "constructive_new":
        return
    name = request.get("object_name") or request.get("name")
    aliases = {"Ultimate L": "Ultimate_L", "UltimateL": "Ultimate_L", "终极L": "Ultimate_L", "V-logic": "V_logic", "V-Logic": "V_logic"}
    name = aliases.get(name, name)
    cid = rule.get("mathematical_object_matchers", {}).get(name)
    if not cid:
        return
    row = next(x for x in rule["rules"] if x["id"] == cid)
    facts = request.get("scope_facts", {})
    if not isinstance(facts, dict):
        raise ValueError("scope_facts must be an object")
    qualified = (facts.get("definition_verified") is True and _ids(facts.get("evidence_ids"))
                 and isinstance(request.get("definition"), str) and bool(request["definition"].strip()))
    if not qualified:
        _gap(out, "name_only_not_construction", "A name such as Ultimate L/huge/V-logic does not supply a construction. Provide an explicit definition, definition_verified fact and source evidence IDs.", clause_id=cid)
        return
    _map(out, rule, row["label"], cid, "explicit_sourced_named_object_correspondence", source=row["source"],
         mathematical_truth="caller-supplied construction interpretation, not proved by this engine")
    if row.get("uncertainties"):
        _gap(out, "handbook_named_criterion_underspecified", "The handbook names this framework but does not define a unique matching criterion.", clause_id=cid, original_uncertainties=row["uncertainties"])


def _historical_identity(request, out, rule, identity, evidence_ok, *, node=None):
    if rule.get("standard") not in {"box_aos", "box_404"}:
        return
    if not isinstance(identity, dict):
        return
    if identity.get("work") != "神盒世界" or identity.get("version") not in {"旧版", "旧", "old"}:
        _gap(out, "old_box_identity_not_established", "Historical AOS/404 tables concern named old-version stages; newer/other works are not identified with them.", node=node)
        return
    stage = str(identity.get("stage", ""))
    stage_aliases = {"4": "第四阶段", "5": "第五阶段", "6": "第六阶段", "7": "第七阶段", "8": "第八阶段", "12": "第十二阶段", "infinite": "第无限阶段", "infinity": "第无限阶段"}
    key = stage_aliases.get(stage, stage)
    matches = []
    for row in rule["rules"]:
        definition = row["definition_raw"]
        # Range rows need explicit bounded stage comparisons rather than substring guesses.
        if key and definition == "旧神盒" + key:
            matches.append(row)
        elif key in {"深渊之底", "永恒之核", "原始无极天", "太上超然界"} and definition == "旧神盒" + key:
            matches.append(row)
        elif stage.isdigit():
            n = int(stage)
            if rule["standard"] == "box_aos" and ((6 <= n <= 7 and row["id"] == "HR-BOX-AOS-05") or (8 <= n <= 12 and row["id"] == "HR-BOX-AOS-06")):
                matches.append(row)
            elif rule["standard"] == "box_404" and 5 <= n <= 12 and row["id"] == "HR-BOX-404-10":
                matches.append(row)
    if not evidence_ok:
        _gap(out, "old_box_identity_needs_source", "Provide evidence for this old-version stage identity; the handbook's table is not the original construction.", node=node)
        return
    for row in matches:
        _map(out, rule, row["label"], row["id"], "named_old_box_stage_identity", source=row["source"], node=node)
    if not matches:
        _gap(out, "old_box_stage_unmapped", "No exact stage/range in the selected historical table; cross-work correspondence criteria are not provided.", stage=stage, node=node)


def enrich(request, out, rule):
    """Append handbook mappings/gaps without changing the core mathematical value."""
    if out.get("status") == "invalid":
        return out
    out.setdefault("structured_gaps", [])
    result = out.setdefault("result", {})
    result["handbook_standard"] = rule.get("standard")
    out.setdefault("limits", []).append("Handbook p250 and appendix p285 are distinct source statements; no legacy N/phi/hyperreal convention is imported.")
    standard = rule.get("standard")
    if standard in {"li", "dao"}:
        _gap(out, "wrong_domain_for_text_rubric", "Use kind li/dao with annotated text/counts and rubric evidence; typed arithmetic alone does not qualify.")
        return out
    if request.get("kind") == "formal_box":
        _gap(out, "formal_N_not_handbook_ordinal", "The p250 convention is typed ordinal. Formal N is not silently replaced by omega, aleph0 or a hyperreal.")
    _mathematical_map(request, out, rule, result)
    _named_map(request, out, rule)
    claim = request.get("construction_claim", {})
    if claim and not isinstance(claim, dict):
        raise ValueError("construction_claim must be an object")
    stage = request.get("handbook_stage") or claim.get("stage")
    if stage in rule.get("undefined_stages", []) or stage in {"infinite_layer_infinite_boxes", "infinite_power_infinite_boxes", "infinite_layer_tower"}:
        _gap(out, "handbook_recurrence_undefined", "The p250 list does not define this stage's recurrence; preserve the source expression instead of importing another table.", stage=stage)
    if stage in {"超指数塔", "super_exponential_tower"}:
        if (claim.get("source_definition_verified") is True and _ids(claim.get("evidence_ids"))
                and isinstance(claim.get("definition"), str) and claim["definition"].strip()):
            _map(out, rule, "超指数塔（序数继续进展仍属本档）", "HR-P250-02", "source_defined_native_stage",
                 status="conditional_on_explicit_source_stage_definition")
            _gap(out, "ordinal_to_cardinal_bridge_missing", "This class still needs a separately defined/proved corresponding cardinal >=aleph1 to become outer.")
        else:
            _gap(out, "super_tower_recurrence_missing", "The handbook gives a class name and ordinal closure convention, not a unique recurrence; supply the work's definition and evidence.")
    _historical_identity(request, out, rule, request.get("identity"), _source_present(request) or _ids(request.get("evidence_ids")))
    if result.get("domain") == "fiction_native":
        nodes = {n["id"]: n for n in result.get("nodes", [])}
        admitted = {s.get("node"): s.get("admitted") is True for s in out.get("steps", []) if str(s.get("rule", "")).startswith("native_")}
        for check in result.get("typed_checks", []):
            node_id = check["node"]
            node = nodes[node_id]
            if admitted.get(node_id) and _source_present(node):
                _mathematical_map(request, out, rule, check["mathematical_check"].get("result", {}), node=node_id)
        for node in nodes.values():
            _historical_identity(request, out, rule, node.get("identity"), admitted.get(node["id"]) and _source_present(node), node=node["id"])
        if not out["mappings"]:
            _gap(out, "native_no_mathematical_bridge", "The DAG/phi names alone do not prove ordinal/cardinal values or an applicable named standard criterion.")
    return out


def _nonnegative_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(field + " must be a nonnegative integer")
    return value


def _fact(request, name):
    facts = request.get("scope_facts", {})
    predicates = request.get("predicates", {})
    if not isinstance(facts, dict) or not isinstance(predicates, dict):
        raise ValueError("scope_facts and predicates must be objects")
    aliases = {"beyond_current_mathematics": "transcends_existing_mathematics"}
    value = predicates.get(name, facts.get(name, facts.get(aliases.get(name, ""))))
    if isinstance(value, dict):
        if value.get("value") is not None and not isinstance(value.get("value"), bool):
            raise ValueError("predicate.value must be boolean/null")
        return value.get("value") if _ids(value.get("evidence_ids")) else None
    if value is not None and not isinstance(value, bool):
        raise ValueError("predicate must be boolean/null or evidence object")
    return value if _ids(facts.get("evidence_ids")) else None


def _assess_dao(request, out, rule):
    if rule.get("standard") != "dao":
        raise ValueError("kind dao needs the named -dao ruleset")
    manual = None
    if request.get("manual_segments") is not None:
        from li_metrics import manual_dewater
        manual = manual_dewater(request.get("source_text"), request["manual_segments"])
        count, count_ok = manual["effective_characters"], True
    else:
        count = request.get("effective_characters")
        if count is not None:
            count = _nonnegative_int(count, "effective_characters")
        count_ok = (count is not None and request.get("count_unit") == "dewatered_characters"
                    and _fact(request, "dewatered") is True and bool(request.get("count_policy")))
    if not count_ok:
        _gap(out, "dao_dewatered_count_missing", "Supply full annotated manual segments, or a sourced dewatered-character count with count_unit/count_policy; raw text/word tokens are not substituted.")
    cumulative = []
    checks, selected = [], None
    forms = request.get("presentation_forms_count")
    domains = request.get("distinct_domains_count")
    if forms is not None:
        forms = _nonnegative_int(forms, "presentation_forms_count")
    if domains is not None:
        domains = _nonnegative_int(domains, "distinct_domains_count")
    for row in rule["tiers"]:
        for p in row["required_predicates"]:
            if p not in cumulative:
                cumulative.append(p)
        statuses = {}
        for p in cumulative:
            statuses[p] = count_ok if p == "dewatered_character_count_verified" else _fact(request, p)
        minimum = row.get("min_characters")
        statuses["character_threshold"] = count_ok and (minimum is None or count >= minimum)
        extra = row.get("extra", {})
        if extra.get("presentation_forms_min"):
            statuses["presentation_forms_at_least_" + str(extra["presentation_forms_min"])] = (
                forms is not None and forms >= extra["presentation_forms_min"] and _fact(request, "presentation_forms_verified") is True)
        if extra.get("any_of"):
            form_min = next((x["presentation_forms_min"] for x in extra["any_of"] if "presentation_forms_min" in x), None)
            domain_min = next((x["distinct_domains_min"] for x in extra["any_of"] if "distinct_domains_min" in x), None)
            statuses["six_forms_or_two_domains"] = ((forms is not None and forms >= form_min and _fact(request, "presentation_forms_verified") is True)
                or (domains is not None and domains >= domain_min and _fact(request, "distinct_domains_verified") is True))
        # Earlier non-predicate count requirements must remain satisfied at later tiers.
        prior_ok = not checks or checks[-1]["passed"]
        passed = prior_ok and all(v is True for v in statuses.values())
        checks.append({"clause_id": row["id"], "label": row["label"], "passed": passed,
                       "checks": statuses, "missing_or_failed": [k for k,v in statuses.items() if v is not True], "inherited_tier_passed": prior_ok})
        if passed:
            selected = row
    out["result"] = {"domain": "community_text_rubric", "standard": rule["id"], "label": selected["label"] if selected else None,
                     "effective_characters": count, "count_verified_structurally": count_ok, "manual": manual, "tier_checks": checks,
                     "rubric_facts_are_supplied_premises": True, "scalar_value": None}
    out["status"] = "conditional" if selected else "insufficient_evidence"
    if selected:
        _map(out, rule, selected["label"], selected["id"], "all_inherited_count_and_predicate_requirements", source=selected["source"])
    unresolved = next((c for c in checks if not c["passed"]), None)
    if unresolved:
        _gap(out, "dao_next_tier_not_established", "The first unestablished row blocks higher inherited rows.", details=unresolved)
    out["limits"].append(rule["classification_basis"])


def _assess_li(request, out, rule):
    if rule.get("standard") != "li":
        raise ValueError("kind li needs the named -li ruleset")
    if not isinstance(request.get("scope_facts", {}), dict):
        raise ValueError("scope_facts must be an object")
    from li_metrics import assess_li
    assessment = assess_li(request, rule)
    out["result"] = {"domain": "community_text_rubric", **assessment, "scalar_value": None}
    out["status"] = assessment["status"]
    selected = assessment.get("manual") or assessment.get("machine")
    has_manual = assessment.get("manual") is not None
    if selected is None:
        _gap(out, "li_count_not_supplied", "Only a scope baseline can be considered; no word tokens or fully annotated manual character count was supplied.")
    if assessment.get("machine"):
        m = assessment["machine"]
        middle_zero = (rule["small_A_boundary"] < m["metrics"]["A_types"] < rule["large_A_boundary"]
                       and m["metrics"]["E_2A_minus_B"] == 0)
        if m.get("boundary_ambiguity") or m.get("E_boundary_ambiguity") or middle_zero:
            _gap(out, "li_source_endpoint_undefined", "The original A/E branch endpoint is not fully specified; no exact upgraded tier is inferred.", A=m["metrics"]["A_types"], E=m["metrics"]["E_2A_minus_B"])
        if m.get("preliminary_dewatering") not in ("completed", "verified", "annotated"):
            _gap(out, "li_machine_dewatering_not_audited", "Word statistics alone do not certify source-required preliminary dewatering and semantic repetition review.")
    if not assessment.get("qualified_scope_evidence_supplied"):
        _gap(out, "li_scope_evidence_missing", "A text length or positive E does not establish scope beyond mathematics/philosophy; supply typed scope_facts and evidence IDs.")
    if assessment.get("label"):
        used_count_label = selected is not None and selected.get("label") is not None
        status = ("conditional_on_manual_semantic_annotations" if has_manual and used_count_label else
                  "conditional_word_segmentation_estimate" if used_count_label else "conditional_scope_baseline_only")
        if not has_manual and assessment.get("machine") and any(g["code"] in {"li_source_endpoint_undefined", "li_machine_dewatering_not_audited"} for g in out.get("structured_gaps", [])):
            status = "candidate_requires_endpoint_or_dewatering_audit"
        basis = "manual_over_machine" if has_manual and used_count_label else "type_token_E_estimate" if used_count_label else "explicit_scope_baseline"
        _map(out, rule, assessment["label"], "HR-LI-04" if used_count_label else "HR-LI-03", basis, status=status)
    out["limits"].extend([rule["scope_wording_gap"], rule["inter_anchor_policy"]])


def analyze(request, rule):
    """Standalone high-engine-shaped result for named handbook standards."""
    out = {"schema_version": "1.0", "engine": "battle-scaling.handbook_high", "status": "invalid", "result": {}, "mappings": [], "steps": [], "assumptions": [], "provenance": [], "warnings": [], "limits": []}
    try:
        if not isinstance(request, dict) or not isinstance(rule, dict):
            raise ValueError("request and rule must be objects")
        if rule.get("engine") != "handbook_high":
            raise ValueError("not a handbook_high ruleset")
        out = _blank(request, rule)
        kind = request.get("kind")
        if kind not in KINDS:
            raise ValueError("unsupported handbook kind: " + str(kind))
        if kind == "li":
            _assess_li(request, out, rule)
        elif kind == "dao":
            _assess_dao(request, out, rule)
        elif kind == "handbook_case":
            out["result"] = {"domain": "handbook_case_coverage", "case": request.get("case"), "construction_status": "derivation_not_provided", "scalar_value": None}
            _gap(out, "case_chapter_no_full_stack", "Appendix pages21–32 give character/work identity and circle history, not complete reproducible Luo/Quan/Divinity Box stack constructions.", source_pages=[291,302])
        elif request.get("mathematical_object") is not None:
            obj = request["mathematical_object"]
            if not isinstance(obj, dict) or obj.get("kind") not in {"ordinal", "cardinal", "inaccessible", "theory", "proper_class"}:
                raise ValueError("mathematical_object needs an explicitly supported core kind")
            import high_tier
            core = high_tier.analyze({**obj, "mode": out["mode"]})
            if core["status"] == "invalid":
                return core
            for key in ("status", "result", "steps", "warnings", "axioms"):
                out[key] = core[key]
            out["assumptions"].extend(x for x in core["assumptions"] if x not in out["assumptions"])
            out["limits"].extend(x for x in core["limits"] if x not in out["limits"])
            out["provenance"].extend(x for x in core["provenance"] if x not in out["provenance"])
            enrich({**request, **obj}, out, rule)
        else:
            out["result"] = {"domain": "named_community_correspondence", "scalar_value": None}
            _named_map(request, out, rule)
            _historical_identity(request, out, rule, request.get("identity"), _source_present(request) or _ids(request.get("evidence_ids")))
            if not out["mappings"] and not out.get("structured_gaps"):
                _gap(out, "named_standard_definition_missing", "Supply a typed mathematical_object, a source-defined object_name, or an explicit old-version stage identity; arbitrary names are not inferred from prose.")
            out["status"] = "conditional" if out["mappings"] else "insufficient_evidence"
        return out
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        out["status"] = "invalid"
        out["errors"] = [str(exc)]
        out["mappings"] = []
        return out
