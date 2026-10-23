"""Typed high-tier arithmetic, fictional construction DAGs and sourced tier mapping.

Standard library only; no eval, network, imported CAS, or hidden scalar conversion.
analyze(request, ruleset=None) always returns a JSON-serializable audit record.
The engine checks supplied evidence *structure*, not the truth of a webpage.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any

from rating_modes import MODES, applies, metadata as mode_metadata
MODE_ALIASES = {"综合": "integrated", "常态": "normal", "最高": "highest", "扒下限": "lowball"}
MATH_SOURCE = {"url": "https://people.math.harvard.edu/~wboney/fall16/settheory.pdf", "locator": "ordinal/cardinal arithmetic, cofinality", "kind": "mathematical_reference"}
MAX_BITS = 32768


class InputError(ValueError):
    pass


@dataclass(frozen=True)
class Expr:
    op: str
    value: str = ""
    args: tuple = ()

    def render(self) -> str:
        if self.op in {"int", "name"}:
            return self.value
        if self.op == "call":
            return self.value + "(" + ",".join(x.render() for x in self.args) + ")"
        return "(" + self.args[0].render() + self.op + self.args[1].render() + ")"

    def as_dict(self) -> dict:
        return {"op": self.op, **({"value": self.value} if self.value else {}), **({"args": [x.as_dict() for x in self.args]} if self.args else {})}


TOKEN = re.compile(r"\s*(\^\^|[+*^(),]|[0-9]+|[A-Za-z_][A-Za-z_0-9]*)")
FORBIDDEN_NAMES = {"eval", "exec", "open", "compile", "globals", "locals", "getattr", "setattr"}


class Parser:
    """Small right-power-associative grammar, not a Python expression evaluator."""
    def __init__(self, text: str):
        if not isinstance(text, str) or not text.strip() or len(text) > 4096:
            raise InputError("expression must contain 1..4096 characters")
        text = text.replace("ω", "omega").replace("ε₀", "epsilon0").replace("ℵ₀", "aleph0").replace("ℵ₁", "aleph1").strip()
        self.tokens = []
        pos = 0
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m:
                raise InputError("unsupported expression character at position " + str(pos))
            s = m.group(1)
            if len(s) > 100 or s.startswith("__") or s in FORBIDDEN_NAMES:
                raise InputError("unsupported or excessive token")
            self.tokens.append(s)
            pos = m.end()
        if len(self.tokens) > 512:
            raise InputError("expression exceeds 512 tokens")
        self.i = 0

    def parse(self) -> Expr:
        out = self.expr(0, 0)
        if self.i != len(self.tokens):
            raise InputError("unexpected token " + self.tokens[self.i])
        return out

    def expr(self, minimum: int, depth: int) -> Expr:
        if depth > 48 or self.i >= len(self.tokens):
            raise InputError("expression nesting excessive or operand missing")
        s = self.tokens[self.i]
        self.i += 1
        if s == "(":
            left = self.expr(0, depth + 1)
            self.take(")")
        elif s.isdigit():
            left = Expr("int", str(int(s)))
        elif re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", s):
            if self.i < len(self.tokens) and self.tokens[self.i] == "(":
                self.i += 1
                args = []
                if self.i < len(self.tokens) and self.tokens[self.i] != ")":
                    args.append(self.expr(0, depth + 1))
                    while self.i < len(self.tokens) and self.tokens[self.i] == ",":
                        self.i += 1
                        args.append(self.expr(0, depth + 1))
                self.take(")")
                left = Expr("call", s, tuple(args))
            else:
                left = Expr("name", s)
        else:
            raise InputError("operand expected, found " + s)
        while self.i < len(self.tokens):
            op = self.tokens[self.i]
            binding = {"+": 10, "*": 20, "^": 30, "^^": 35}.get(op, -1)
            if binding < minimum:
                break
            self.i += 1
            right = self.expr(binding if op in {"^", "^^"} else binding + 1, depth + 1)
            left = Expr(op, args=(left, right))
        return left

    def take(self, token: str):
        if self.i >= len(self.tokens) or self.tokens[self.i] != token:
            raise InputError("expected " + token)
        self.i += 1


def parse(expression: str) -> Expr:
    return Parser(expression).parse()


def _step(out: dict, rule: str, result: Any, **extra):
    out["steps"].append({"id": "s" + str(len(out["steps"]) + 1), "rule": rule, "result": result, **extra})


def _safe_power(a: int, b: int) -> int | None:
    if b < 0 or b > 10000 or (a > 1 and a.bit_length() * b > MAX_BITS):
        return None
    return pow(a, b)


def _poly_add(a: dict[int, int], b: dict[int, int]) -> dict[int, int]:
    if not b:
        return dict(a)
    top = max(b)
    c = {k: v for k, v in a.items() if k >= top}
    for k, v in b.items():
        c[k] = c.get(k, 0) + v
    return {k: v for k, v in c.items() if v}


def _poly_mul(a: dict[int, int], b: dict[int, int]) -> dict[int, int] | None:
    if not a or not b:
        return {}
    out: dict[int, int] = {}
    for d in sorted(b, reverse=True):
        coefficient = b[d]
        if d:
            term = {max(a) + d: coefficient}
        else:
            term = dict(a)
            term[max(a)] *= coefficient
        if max(term) > 10000 or any(v.bit_length() > MAX_BITS for v in term.values()):
            return None
        out = _poly_add(out, term)
    return out


def _render_poly(p: dict[int, int]) -> str:
    if not p:
        return "0"
    parts = []
    for exponent in sorted(p, reverse=True):
        c = p[exponent]
        if exponent == 0:
            parts.append(str(c))
        else:
            term = "omega" if exponent == 1 else "omega^" + str(exponent)
            parts.append(term if c == 1 else term + "*" + str(c))
    return " + ".join(parts)


def _join_countability(a: str, b: str) -> str:
    if "unknown" in {a, b}:
        return "unknown"
    if "uncountable" in {a, b}:
        return "uncountable"
    if "countable" in {a, b}:
        return "countable"
    return "finite"


def _ordinal(expr: Expr, out: dict) -> dict:
    """Exact CNF for finite exponents (<omega^omega); other expressions typed."""
    if expr.op == "int":
        n = int(expr.value)
        return {"poly": {0: n} if n else {}, "canonical": str(n), "countability": "finite", "exact": True}
    if expr.op == "name":
        if expr.value.startswith(("aleph", "beth")) or expr.value == "N":
            raise InputError("cardinal/formal-box symbol in ordinal domain")
        if expr.value == "omega":
            return {"poly": {1: 1}, "canonical": "omega", "countability": "countable", "exact": True}
        if expr.value == "epsilon0":
            return {"poly": None, "canonical": "epsilon0", "countability": "countable", "exact": True}
        if expr.value == "omega1":
            return {"poly": None, "canonical": "omega1", "countability": "uncountable", "exact": True}
        return {"poly": None, "canonical": expr.render(), "countability": "unknown", "exact": False}
    if expr.op == "call" and expr.value == "tower" and len(expr.args) == 2:
        base, height = expr.args
        if base == Expr("name", "omega") and height == Expr("name", "omega"):
            _step(out, "ordinal_tower_supremum", "epsilon0 is the supremum of t0=1, t(n+1)=omega^t(n); each stage and supremum are countable", source=MATH_SOURCE)
            return {"poly": None, "canonical": "epsilon0", "countability": "countable", "exact": True}
        if height.op == "int":
            n = int(height.value)
            if n > 32:
                return {"poly": None, "canonical": expr.render(), "countability": "unknown", "exact": False}
            tower = Expr("int", "1")
            for _ in range(n):
                tower = Expr("^", args=(base, tower))
            return _ordinal(tower, out)
    if expr.op in {"+", "*", "^"}:
        a, b = (_ordinal(x, out) for x in expr.args)
        p, q = a["poly"], b["poly"]
        c = None
        if p is not None and q is not None:
            if expr.op == "+":
                c = _poly_add(p, q)
            elif expr.op == "*":
                c = _poly_mul(p, q)
            elif not q or max(q) == 0:
                n = q.get(0, 0)
                if not p or max(p) == 0:
                    x = _safe_power(p.get(0, 0), n)
                    if x is not None:
                        c = {0: x} if x else {}
                elif n <= 256 and n * max(p) <= 10000:
                    c = {0: 1}
                    for _ in range(n):
                        c = _poly_mul(c, p)
                        if c is None:
                            break
        if c is not None:
            label = _render_poly(c)
            _step(out, "ordinal_CNF_" + expr.op, label, expression=expr.render(), source=MATH_SOURCE)
            return {"poly": c, "canonical": label, "countability": "finite" if not c or max(c) == 0 else "countable", "exact": True}
        count = _join_countability(a["countability"], b["countability"])
        # Countable ordinal arithmetic is closed; uncountable symbolic expressions
        # need zero/exponent details and are conservatively left unknown.
        if count == "uncountable":
            count = "unknown"
        return {"poly": None, "canonical": expr.render(), "countability": count, "exact": False}
    # Unknown functions are retained, never executed or equated to named functions.
    return {"poly": None, "canonical": expr.render(), "countability": "unknown", "exact": False}


def _card(name: str, *, finite: int | None = None, index: int | None = None, exact=True, countability=None, lower=None):
    return {"canonical": name, "finite": finite, "aleph_index": index, "exact": exact, "countability": countability or ("finite" if finite is not None else "countable" if index == 0 else "uncountable" if index is not None else "unknown"), **({"lower_bound": lower} if lower else {})}


def _powerset(a: dict, axioms: set[str], out: dict):
    if a["finite"] is not None:
        n = _safe_power(2, a["finite"])
        return _card(str(n), finite=n) if n is not None else _card("powerset("+a["canonical"]+")", exact=False)
    i = a["aleph_index"]
    if i is not None and ("GCH" in axioms or i == 0 and "CH" in axioms):
        _step(out, "conditional_continuum_successor", "aleph" + str(i + 1), axioms=["GCH" if "GCH" in axioms else "CH"], source=MATH_SOURCE)
        return _card("aleph" + str(i + 1), index=i + 1)
    _step(out, "Cantor_powerset_strict_growth", "power-set cardinal exceeds base; no unconditional successor equality", source=MATH_SOURCE)
    lower = ("aleph" + str(i + 1) if axioms.intersection({"ZFC", "AC"}) else "aleph" + str(i) if i >= 1 else None) if i is not None else None
    if i == 0 and not axioms.intersection({"ZFC", "AC"}):
        out["limits"].append("In ZF, Cantor proves P(omega) uncountable, but an injection aleph1→P(omega) is not inferred without a suitable choice/well-ordering premise.")
    return _card("powerset(" + a["canonical"] + ")", exact=a["exact"], countability="uncountable" if a["countability"] in {"countable", "uncountable"} else "unknown", lower=lower)


def _cardinal(expr: Expr, axioms: set[str], out: dict):
    if expr.op == "int":
        n = int(expr.value)
        return _card(str(n), finite=n)
    if expr.op == "name":
        if expr.value in {"omega", "omega1", "epsilon0", "N"}:
            raise InputError("ordinal/formal-box symbol in cardinal domain; use an explicit type conversion with proof")
        m = re.fullmatch(r"aleph([0-9]+)", expr.value)
        if m:
            index = int(m.group(1))
            if index > 10000:
                return _card(expr.value, exact=False)
            return _card(expr.value, index=index)
        return _card(expr.value, exact=False)
    if expr.op == "call" and expr.value == "powerset" and len(expr.args) == 1:
        return _powerset(_cardinal(expr.args[0], axioms, out), axioms, out)
    if expr.op not in {"+", "*", "^"}:
        return _card(expr.render(), exact=False)
    a, b = (_cardinal(x, axioms, out) for x in expr.args)
    af, bf, ai, bi = a["finite"], b["finite"], a["aleph_index"], b["aleph_index"]
    if af is not None and bf is not None:
        v = af + bf if expr.op == "+" else af * bf if expr.op == "*" else _safe_power(af, bf)
        return _card(str(v), finite=v) if v is not None and v.bit_length() <= MAX_BITS else _card(expr.render(), exact=False)
    if expr.op == "*" and (af == 0 or bf == 0):
        return _card("0", finite=0)
    if expr.op in {"+", "*"} and (ai is not None and bi is not None or ai is not None and bf is not None or af is not None and bi is not None):
        n = max(i for i in (ai, bi) if i is not None)
        _step(out, "well_orderable_infinite_cardinal_max", "aleph"+str(n), operation=expr.op, source=MATH_SOURCE)
        return _card("aleph"+str(n), index=n)
    if expr.op == "^":
        if bf == 0 or af == 1:
            return _card("1", finite=1)
        if af == 0:
            return _card("0", finite=0)
        if ai is not None and bf is not None:
            return a
        if bi is not None and (af is not None and af >= 2 or ai is not None and ai <= bi):
            _step(out, "bounded_base_infinite_power", "base^lambda = 2^lambda when 2 <= base <= lambda and lambda infinite", source=MATH_SOURCE)
            return _powerset(b, axioms, out)
        if ai is not None and bi is not None and ai == bi + 1 and ("GCH" in axioms or bi == 0 and "CH" in axioms):
            _step(out, "successor_power_under_continuum_hypothesis", a["canonical"], axioms=["GCH" if "GCH" in axioms else "CH"], source=MATH_SOURCE)
            return a
    return _card(expr.render(), exact=False)


def _inaccessible(request: dict, out: dict, axioms: set[str]):
    facts = request.get("facts", {})
    if not isinstance(facts, dict) or any(v is not None and not isinstance(v, bool) for v in facts.values()):
        raise InputError("inaccessible facts must be boolean or null")
    if facts.get("strong_limit") is True and facts.get("limit") is False:
        raise InputError("strong_limit with not_limit is inconsistent for an uncountable cardinal")
    if facts.get("uncountable") is True and facts.get("countable") is True:
        raise InputError("countable and uncountable premises conflict")
    uncountable = facts.get("uncountable") is True
    regular = facts.get("regular") is True
    limit = facts.get("limit") is True or facts.get("strong_limit") is True
    strong_limit = facts.get("strong_limit") is True
    weak = uncountable and regular and limit
    if weak and "GCH" in axioms:
        strong_limit = True
        _step(out, "GCH_at_limit", "for every lambda<kappa, 2^lambda=lambda+<kappa; kappa is strong limit", axioms=["GCH"], source=MATH_SOURCE)
    strong = uncountable and regular and strong_limit
    classification = "strongly_inaccessible" if strong else "weakly_inaccessible" if weak else "not_established"
    _step(out, "inaccessible_definition", classification, given=facts, source=MATH_SOURCE)
    out["result"] = {"domain": "cardinal_property", "classification": classification, "weakly_inaccessible": weak or strong, "strongly_inaccessible": strong, "scalar_value": None, "facts_are_supplied_premises": True}
    out["status"] = "conditional"
    out["assumptions"].append({"text": "The stated cardinal properties hold for the same kappa.", "type": "supplied_mathematical_premises"})


def _source_present(obj: dict) -> bool:
    src = obj.get("source") or obj.get("sources")
    if isinstance(src, dict):
        return bool((src.get("url") or src.get("path")) and src.get("locator"))
    return isinstance(src, list) and bool(src) and all(isinstance(x, dict) and (x.get("url") or x.get("path")) and x.get("locator") for x in src)


def _provenance(out: dict, obj: dict):
    src = obj.get("source") or obj.get("sources") or []
    if isinstance(src, dict):
        src = [src]
    if isinstance(src, list):
        for item in src:
            if isinstance(item, dict) and item not in out["provenance"]:
                out["provenance"].append(item)


def _load_rule(request: dict, rule: dict | None):
    if rule is not None:
        if not isinstance(rule, dict):
            raise InputError("ruleset must be a JSON object")
        return rule
    name = request.get("ruleset")
    if name is None:
        return None
    if not isinstance(name, str) or not re.fullmatch(r"high-[a-z0-9-]+(?:\.json)?", name):
        raise InputError("ruleset must name a bundled high-*.json; custom rulesets use --ruleset")
    filename = name if name.endswith(".json") else name + ".json"
    path = Path(__file__).resolve().parents[1] / "rulesets" / filename
    if not path.is_file():
        raise InputError("bundled ruleset not found: " + filename)
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping(out: dict, rule: dict, label: str, status: str, basis: str, **extra):
    out["mappings"].append({"label": label, "status": status, "basis": basis, "ruleset": rule.get("id", "unidentified-custom-rule"), "source": rule.get("source", {}), "source_status": rule.get("status", "unverified_custom_rule"), **extra})


def _aleph1_lower_bound(result: dict, axioms: list[str]) -> bool:
    if result.get("countability") != "uncountable":
        return False
    if result.get("aleph_index") is not None and result["aleph_index"] >= 1:
        return True
    if result.get("domain") == "ordinal" and result.get("canonical") == "omega1":
        return True
    lower = result.get("lower_bound", "")
    if re.fullmatch(r"aleph[1-9][0-9]*", lower):
        return True
    return bool(set(axioms).intersection({"ZFC", "AC"}))


def _map_math(out: dict, rule: dict | None):
    if not rule:
        return
    result = out["result"]
    if result.get("domain") in {"cardinal", "ordinal"} and _aleph1_lower_bound(result, out["axioms"]) and rule.get("old_uncountable_threshold"):
        _mapping(out, rule, rule["old_uncountable_threshold"], "conditional_on_ruleset", "proved_aleph1_lower_bound_of_typed_object", scope="structure only; character properties need a separate bridge")
    if result.get("classification") == "strongly_inaccessible" and rule.get("strong_inaccessible_label"):
        _mapping(out, rule, rule["strong_inaccessible_label"], "conditional_on_ruleset_and_premises", "strong_inaccessible_criteria")


def _formal_box(expr: Expr, out: dict, rule: dict | None):
    def valid(e):
        return (e.op == "name" and e.value == "N") or e.op == "int" or e.op in {"+", "*", "^", "^^"} and all(valid(x) for x in e.args)
    if not valid(expr):
        raise InputError("formal_box permits N, nonnegative integers and + * ^ ^^ only; custom phi belongs to native domain")
    out["result"] = {"domain": "community_formal_structure", "canonical": expr.render(), "ast": expr.as_dict(), "cardinal": None, "ordinal": None, "scalar_value": None}
    out["status"] = "symbolic"
    out["limits"].append("N is the selected community's formal universe unit; no substitution N=aleph0, omega or a unique hyperreal is inferred.")
    if not rule:
        return
    for item in rule.get("formal_mappings", []):
        if parse(item["expression"]) == expr:
            _mapping(out, rule, item["label"], "conditional_on_ruleset", "formal_pattern", original_notation=item.get("original_notation", item["expression"]))
            return
    if expr.op == "^" and expr.args[0] == Expr("name", "N") and expr.args[1].op == "int" and int(expr.args[1].value) > 4 and rule.get("finite_box_label"):
        _mapping(out, rule, rule["finite_box_label"], "conditional_on_ruleset", "finite_exponent_schema")
    elif expr.op == "^^" and expr.args[0] == Expr("name", "N") and expr.args[1].op == "int" and int(expr.args[1].value) >= 4 and rule.get("finite_tower_label"):
        _mapping(out, rule, rule["finite_tower_label"], "conditional_on_ruleset", "finite_tetration_schema")
    else:
        out["warnings"].append("No exact formal pattern in selected ruleset; preserve expression rather than invent a tier.")


def _native(request: dict, out: dict, rule: dict | None):
    nodes = request.get("nodes", [])
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 512:
        raise InputError("native nodes must contain 1..512 entries")
    by_id: dict[str, dict] = {}
    allowed = {"base", "contains", "iteration", "closure", "base_reset", "transcends", "adjective", "narrative", "typed_structure", "anchor"}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"] or node["id"] in by_id:
            raise InputError("node IDs must be nonempty and unique")
        if node.get("operation") not in allowed:
            raise InputError("unsupported native operation: " + str(node.get("operation")))
        deps = node.get("depends_on", [])
        if not isinstance(deps, list) or any(not isinstance(x, str) for x in deps):
            raise InputError("depends_on must contain node IDs")
        if node["operation"] != "base" and not deps:
            out["warnings"].append("node " + node["id"] + " lacks an input; operation scope is not established")
        by_id[node["id"]] = node
    for node in nodes:
        if any(x not in by_id for x in node.get("depends_on", [])):
            raise InputError("unknown native dependency in " + node["id"])
    # Kahn sorting avoids recursion even for long user-supplied graphs.
    done: set[str] = set()
    order = []
    while len(done) < len(nodes):
        ready = [n for n in nodes if n["id"] not in done and all(d in done for d in n.get("depends_on", []))]
        if not ready:
            raise InputError("native DAG contains a cycle; circular escalation has no independent base")
        for node in ready:
            done.add(node["id"])
            order.append(node)
    out["status"] = "conditional"
    out["limits"] += ["Native phi/Φ is not Veblen phi unless the work explicitly supplies that definition.", "DAG checks validate dependency/provenance structure; semantic entailment of prose still requires source reading.", "Fictional transcendence does not independently prove a cardinal, ordinal or consistency-strength value."]
    eligibility: dict[str, bool] = {}
    for node in order:
        _provenance(out, node)
        assumptions = node.get("assumptions", [])
        if not isinstance(assumptions, list):
            raise InputError("node assumptions must be a list")
        out["assumptions"].extend({"node": node["id"], "text": x, "type": "native_interpretation"} for x in assumptions)
        sourced = _source_present(node)
        if not sourced:
            out["warnings"].append("unsourced_node:" + node["id"])
        op = node["operation"]
        aggressive = op == "adjective" or node.get("aggressive") is True
        admitted = (not aggressive or out["mode"] in ("integrated", "highest") and bool(assumptions)) and all(eligibility[d] for d in node.get("depends_on", []))
        eligibility[node["id"]] = admitted
        if aggressive and not admitted:
            out["warnings"].append("unadmitted_aggressive_node:" + node["id"])
        if op == "base_reset" and not node.get("scope"):
            out["warnings"].append("base_reset lacks explicit packed scope:" + node["id"])
        if op in {"closure", "iteration"} and not node.get("definition"):
            out["warnings"].append("operation domain/iteration rule needs definition:" + node["id"])
        _step(out, "native_" + op, node.get("description", node["id"]), node=node["id"], depends_on=node.get("depends_on", []), source_present=sourced, aggressive=aggressive, admitted=admitted, assumptions=assumptions, definition=node.get("definition"), scope=node.get("scope"))
    indexed_anchors = {a["id"]: a for a in (rule or {}).get("anchors", [])}
    claims = request.get("anchor_claims", [])
    if not isinstance(claims, list):
        raise InputError("anchor_claims must be a list")
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("node") not in by_id:
            raise InputError("anchor claim references an unknown node")
        aid = claim.get("anchor_id")
        anchor = indexed_anchors.get(aid)
        if not anchor:
            out["warnings"].append("unknown_anchor:" + str(aid))
            continue
        node = by_id[claim["node"]]
        relation = claim.get("relation", "equal")
        if relation not in {"equal", "at_least", "less_than", "analogous"}:
            raise InputError("unsupported anchor relation")
        identity_ok = bool(anchor.get("identity")) and all(str(node.get("identity", {}).get(k)) == str(v) for k, v in anchor["identity"].items())
        if claim.get("basis") == "identity" and identity_ok and _source_present(node) and eligibility[node["id"]]:
            status = "conditional_on_anchor_identity_and_source"
            basis = "named_anchor_identity"
        else:
            status = "candidate"
            basis = "analyst_comparison_requires_audit"
            out["warnings"].append("candidate_anchor_mapping_requires_scope_and_comparison_audit:" + str(aid))
        label = anchor["label"]
        if relation == "at_least":
            label += "及以上（条件下界）"
        if relation == "less_than":
            label = "低于" + label + "（条件上界）"
        if relation == "analogous":
            label = "与" + label + "锚点类比（候选）"
        if relation in {"less_than", "analogous"}:
            status = "candidate"
        _mapping(out, rule, label, status, basis, node=node["id"], anchor_id=aid, relation=relation, comparison=claim.get("comparison", []), scope="world construction; no automatic transfer to character AP")
        _provenance(out, claim)
        out["assumptions"].extend({"anchor": aid, "text": a, "type": "anchor_comparison"} for a in claim.get("assumptions", []))
    properties: dict[str, list] = {}
    links = request.get("character_relations", [])
    if not isinstance(links, list):
        raise InputError("character_relations must be a list")
    for link in links:
        if not isinstance(link, dict) or link.get("node") not in by_id:
            raise InputError("character relation references an unknown node")
        _provenance(out, link)
        relation = link.get("relation")
        source_ok = _source_present(link) and _source_present(by_id[link["node"]]) and eligibility[link["node"]]
        if relation in {"becomes", "merges"}:
            # Identity/fusion is an ontological state claim, not an action that
            # controls or destroys the whole target. Preserve its time scope.
            props = ["state_identity" if relation == "becomes" else "fusion_state"]
            for field in ("state", "duration"):
                value = link.get(field)
                if value is None or isinstance(value, str) and not value.strip():
                    out["warnings"].append("identity_relation_missing_" + field + ":" + str(link.get("character")) + ":" + relation)
            if any(p in {"attack", "durability", "attack_potency", "destructive_capacity", "AP", "DC"} for p in link.get("properties", [])):
                out["warnings"].append("blocked_identity_to_combat_transfer:" + str(link.get("character")))
            out["limits"].append("Identity/fusion applies only to the supplied state and duration; an unknown duration is not permanent normal-state capability. Combat properties require separate action/resistance evidence.")
        elif relation in {"reaches", "travels", "perceives", "exists_in"}:
            props = ["perception_range" if relation == "perceives" else "range" if relation in {"reaches", "travels"} else "ontological_location"]
            if any(p in {"attack", "durability", "destructive_capacity"} for p in link.get("properties", [])):
                out["warnings"].append("blocked_travel_to_combat_transfer:" + str(link.get("character")))
        elif relation in {"affects", "creates", "destroys", "controls", "withstands"}:
            default = {"affects": "special_effect_scope", "creates": "creation_scope", "destroys": "destructive_capacity", "controls": "control_scope", "withstands": "specific_resistance"}[relation]
            props = [default]
            if link.get("properties"):
                if link.get("mechanism") and link.get("bridge") and source_ok:
                    props = link["properties"]
                    out["assumptions"].append({"text": link["bridge"], "type": "property_transfer", "character": link.get("character")})
                else:
                    out["warnings"].append("property_transfer_requires_mechanism_bridge_and_source")
        else:
            out["warnings"].append("unrecognized_character_relation:" + str(relation))
            continue
        for prop in props:
            properties.setdefault(prop, []).append({"character": link.get("character"), "node": link["node"], "relation": relation, "status": "source_conditioned" if source_ok else "candidate_unsourced", "mechanism": link.get("mechanism"), "source": link.get("source", link.get("sources", [])), **{field: link[field] for field in ("state", "duration", "scope", "conditions", "timeframe", "phase", "start", "end", "version", "continuity", "form") if field in link}})
    # Typed facts are surfaced as supplied claims, not converted into scalar energy.
    typed = [{"node": n["id"], **n["typed_object"]} for n in nodes if isinstance(n.get("typed_object"), dict)]
    checks = []
    for obj in typed:
        if obj.get("kind") not in {"ordinal", "cardinal", "inaccessible", "formal_box", "theory", "proper_class"}:
            out["warnings"].append("unrecognized_typed_object:" + obj["node"])
            continue
        check = analyze({**obj, "mode": out["mode"], "axioms": request.get("axioms") or ["ZF"]})
        checks.append({"node": obj["node"], "mathematical_check": check, "interpretation": obj.get("interpretation")})
        if check["status"] == "invalid":
            out["warnings"].append("invalid_typed_object:" + obj["node"])
        if rule and rule.get("old_uncountable_threshold") and _aleph1_lower_bound(check.get("result", {}), check.get("axioms", [])) and eligibility[obj["node"]] and _source_present(by_id[obj["node"]]):
            _mapping(out, rule, rule["old_uncountable_threshold"], "conditional_on_source_semantics_and_ruleset", "typed_source_interpretation", node=obj["node"], scope="typed structure; character property follows only its separate relation")
    out["result"] = {"domain": "fiction_native", "node_order": [n["id"] for n in order], "nodes": order, "typed_objects": typed, "typed_checks": checks, "cardinal": None, "ordinal": None, "scalar_value": None, "combat_properties": properties}


def analyze(request: dict, ruleset: dict | None = None) -> dict:
    """Analyze an explicitly typed request. Invalid/unsupported are data, not claims.

    kind: ordinal | cardinal | formal_box | inaccessible | native | theory |
    proper_class. modes are normal/highest/lowball (Chinese aliases accepted).
    Exact means the bundled arithmetic covered the expression; conditional
    mappings remain community conventions, not mathematical combat theorems.
    """
    out = {"schema_version": "1.0", "engine": "battle-scaling.high_tier", "status": "invalid", "mode": "integrated", "result": {}, "steps": [], "assumptions": [], "mappings": [], "provenance": [], "warnings": [], "limits": []}
    try:
        if not isinstance(request, dict):
            raise InputError("request must be a JSON object")
        mode = MODE_ALIASES.get(request.get("mode", "integrated"), request.get("mode", "integrated"))
        if mode not in MODES:
            raise InputError("mode must be integrated or explicit legacy normal/highest/lowball or 常态/最高/扒下限")
        out["mode"] = mode
        out.update(mode_metadata(mode))
        assumptions = request.get("assumptions", [])
        if not isinstance(assumptions, list):
            raise InputError("assumptions must be a list")
        out["assumptions"].extend(assumptions)
        _provenance(out, request)
        raw_axioms = request.get("axioms", [])
        if not isinstance(raw_axioms, list) or any(not isinstance(a, str) for a in raw_axioms):
            raise InputError("axioms must contain strings")
        axioms = set(raw_axioms)
        kind = request.get("kind")
        if not axioms and kind in {"cardinal", "inaccessible"}:
            axioms.add("ZFC")
            out["assumptions"].append({"text": "ZFC is the explicitly reported default for this arithmetic fragment; request axioms=[ZF] to evaluate without Choice.", "type": "default_background_axiom"})
        elif not axioms and kind == "ordinal":
            axioms.add("ZF")
        elif "not_AC" in axioms and not axioms.intersection({"ZF", "ZFC"}):
            axioms.add("ZF")
        elif kind in {"ordinal", "cardinal", "inaccessible"} and not axioms.intersection({"ZF", "ZFC"}):
            base = "ZF" if kind == "ordinal" else "ZFC"
            axioms.add(base)
            out["assumptions"].append({"text": base + " is the reported base theory for the requested arithmetic; supply ZF explicitly to withhold Choice.", "type": "default_background_axiom"})
        if "ZFC" in axioms and axioms.intersection({"not_AC", "not_ZFC"}):
            raise InputError("ZFC conflicts with the explicitly negated Choice/ZFC premise")
        if "not_CH" in axioms and axioms.intersection({"CH", "GCH"}):
            raise InputError("inconsistent declared CH/GCH/not_CH premises")
        if "not_GCH" in axioms and "GCH" in axioms:
            raise InputError("inconsistent declared GCH/not_GCH premises")
        out["axioms"] = sorted(axioms)
        rule = _load_rule(request, ruleset)
        if rule:
            _provenance(out, rule)
            out["ruleset"] = {k: rule.get(k) for k in ("id", "title", "status", "source", "read_date")}
            out["limits"].append("The selected table is source-qualified; it is not certified as a unified current 汪吧 official rule.")
        if rule and rule.get('engine')=='handbook_high' and kind not in {'ordinal','cardinal','formal_box','inaccessible','native','theory','proper_class'}:
            from handbook_high import analyze as analyze_handbook
            return analyze_handbook(request,rule)
        if kind in {"ordinal", "cardinal", "formal_box"}:
            expr = parse(request.get("expression"))
            out["input_ast"] = expr.as_dict()
            if kind == "formal_box":
                _formal_box(expr, out, rule)
            else:
                value = _ordinal(expr, out) if kind == "ordinal" else _cardinal(expr, axioms, out)
                value.pop("poly", None)
                out["result"] = {"domain": kind, **value}
                out["status"] = "exact" if value["exact"] else "symbolic"
                if not value["exact"]:
                    out["limits"].append("Exact arithmetic outside the implemented fragment is retained symbolically; this is not a solved value.")
                if value["countability"] == "countable":
                    _step(out, "countability_preserved", "not established to reach aleph1; countable structure", source=MATH_SOURCE)
                _map_math(out, rule)
        elif kind == "inaccessible":
            _inaccessible(request, out, axioms)
            _map_math(out, rule)
        elif kind == "native":
            _native(request, out, rule)
        elif kind in {"theory", "proper_class"}:
            out["status"] = "symbolic"
            out["result"] = {"domain": kind, "name": request.get("name"), "expression": request.get("expression"), "scalar_value": None}
            out["limits"].append("Theory/model/proper-class objects require typed interpretation or a named comparison rule; arithmetic and energy conversion are not defined here.")
        else:
            raise InputError("unsupported kind: " + str(kind))
        if rule and rule.get('engine')=='handbook_high':
            from handbook_high import enrich
            out=enrich(request,out,rule)
        out["limits"].append("Evidence statements are supplied by the caller; this offline checker has not fetched or authenticated cited sources.")
        return out
    except (InputError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        out["status"] = "invalid"
        out["errors"] = [str(exc)]
        out["mappings"] = []
        return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="UTF-8 JSON request file")
    parser.add_argument("--output", help="UTF-8 JSON output file; default stdout")
    parser.add_argument("--ruleset", help="Optional explicit local ruleset JSON file")
    args = parser.parse_args()
    try:
        req = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
        rule = json.loads(Path(args.ruleset).read_text(encoding="utf-8-sig")) if args.ruleset else None
        result = analyze(req, rule)
    except (OSError, json.JSONDecodeError) as exc:
        result = {"status": "invalid", "errors": [str(exc)]}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(rendered)
    return 2 if result["status"] == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
