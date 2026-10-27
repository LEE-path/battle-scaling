"""Blind semantic-boundary packets and attributable host reviews.

This tool selects questions, binds bytes and records reasoning. It has no model,
does not search the work, and never grades prose or infers semantic correctness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


DATA = Path(__file__).resolve().parents[1] / "benchmarks" / "semantic-boundaries"
RESPONSE_FIELDS = ("supported_conclusions", "rejected_inferences", "missing_bridges", "conditional_alternatives")


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + " must be nonempty text")
    return value


def _index(rows, key):
    if not isinstance(rows, list):
        raise ValueError(key + " rows must be a list")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(key + " row must be an object")
        ident = _text(row.get(key), key)
        if ident in result:
            raise ValueError("duplicate " + key + ": " + ident)
        result[ident] = row
    return result


def _no_rubric(value):
    # This guards the *packet schema*, not answer leakage through natural prose.
    if isinstance(value, dict):
        if set(value).intersection({"answers", "required_boundaries", "acceptable_interpretations", "decisive_missing_bridges", "clear_failures", "variant_check", "review_policy"}):
            raise ValueError("answer/rubric fields are forbidden in blind packets")
        for child in value.values():
            _no_rubric(child)
    elif isinstance(value, list):
        for child in value:
            _no_rubric(child)


def create_packet(prompts, selected=None):
    """Use prompts only. The answer resource is neither accepted nor opened."""
    _no_rubric(prompts)
    cases = _index(prompts.get("cases"), "case_id")
    sources = _index(prompts.get("sources"), "id")
    selected = list(cases) if selected is None else list(selected)
    if not selected or len(set(selected)) != len(selected) or any(x not in cases for x in selected):
        raise ValueError("select nonempty, unique, known case IDs")
    needed = []
    for ident in selected:
        row = cases[ident]
        for key in ("topic", "fixed_context", "candidate_reasoning", "task", "variant"):
            _text(row.get(key), ident + "." + key)
        if not isinstance(row.get("source_ids"), list) or not row["source_ids"]:
            raise ValueError("case source_ids must be a nonempty list")
        for sid in row["source_ids"]:
            if sid not in sources:
                raise ValueError("unknown source: " + str(sid))
            if sid not in needed:
                needed.append(sid)
    for sid in needed:
        for key in ("url", "locator", "excerpt", "work_version", "source_kind"):
            _text(sources[sid].get(key), sid + "." + key)
    payload = {
        "schema_version": "1.0", "kind": "semantic_boundary_blind_packet",
        "corpus_version": prompts["corpus_version"], "prompts_sha256": digest(prompts),
        "instructions": prompts["instructions"], "cases": [cases[x] for x in selected],
        "sources": [sources[x] for x in needed],
        "response_format": {"packet_sha256": "copy the packet_sha256 below", "responses": [
            {"case_id": "selected case ID", "analysis": "your reasoning and source comparison",
             **{key: [] for key in RESPONSE_FIELDS}}
        ]},
        "limits": ["This packet contains no reference answers.",
                   "The tool has not certified source truth or semantic correctness.",
                   "A reasoned answer may preserve several interpretations; no unique tier is required."]
    }
    return {**payload, "packet_sha256": digest(payload)}


def _check_packet(packet):
    if packet.get("kind") != "semantic_boundary_blind_packet":
        raise ValueError("expected a blind packet")
    _no_rubric(packet)
    payload = {k: v for k, v in packet.items() if k != "packet_sha256"}
    if packet.get("packet_sha256") != digest(payload):
        raise ValueError("packet bytes/contents changed after creation")
    return _index(packet.get("cases"), "case_id")


def record_response(packet, response, *, respondent):
    cases = _check_packet(packet)
    _text(respondent, "respondent")
    if response.get("packet_sha256") != packet["packet_sha256"]:
        raise ValueError("response must name the exact packet_sha256 it answered")
    rows = _index(response.get("responses"), "case_id")
    if set(rows) != set(cases):
        raise ValueError("responses must cover exactly the selected cases")
    for ident, row in rows.items():
        _text(row.get("analysis"), ident + ".analysis")
        for key in RESPONSE_FIELDS:
            values = row.get(key)
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(ident + "." + key + " must contain text items (an empty list is allowed)")
    return {"schema_version": "1.0", "kind": "semantic_boundary_response_record",
            "status": "recorded_unreviewed", "respondent": respondent,
            "packet_sha256": packet["packet_sha256"], "packet": packet,
            "response": response, "response_sha256": digest(response),
            "semantic_certification": False,
            "limits": ["Content recorded without a semantic grade. A host or independent reviewer must compare the actual reasoning and sources."]}


def record_review(record, judgments, answers):
    if record.get("kind") != "semantic_boundary_response_record":
        raise ValueError("expected an unreviewed response record")
    cases = _check_packet(record["packet"])
    if (record.get("packet_sha256") != record["packet"]["packet_sha256"]
            or record.get("response_sha256") != digest(record.get("response"))):
        raise ValueError("record packet/response binding changed")
    record_response(record["packet"], record["response"], respondent=record.get("respondent"))
    rubric = _index(answers.get("answers"), "case_id")
    if answers.get("corpus_version") != record["packet"]["corpus_version"] or not set(cases).issubset(rubric):
        raise ValueError("reference rubric does not match the packet corpus")
    _text(judgments.get("reviewer"), "reviewer")
    if judgments.get("response_sha256") != record["response_sha256"]:
        raise ValueError("review must bind the exact response_sha256")
    rows = _index(judgments.get("judgments"), "case_id")
    if set(rows) != set(cases):
        raise ValueError("judgments must cover exactly the selected cases")
    for ident, row in rows.items():
        if row.get("assessment") not in {"acceptable", "needs_revision", "unresolved"}:
            raise ValueError("unknown host assessment for " + ident)
        _text(row.get("rationale"), ident + ".rationale")
        _text(row.get("evidence_comparison"), ident + ".evidence_comparison")
    return {"schema_version": "1.0", "kind": "semantic_boundary_host_review",
            "status": "host_review_recorded", "response_record": record,
            "review": judgments, "rubric_sha256": digest(answers),
            "semantic_certification": False,
            "limits": ["Assessments above are supplied by the named host/reviewer, not inferred or certified by this program.",
                       "Corpus integrity and complete records do not prove the interpretation is correct."]}


def audit(prompts, answers):
    packet = create_packet(prompts)
    cases = _index(packet["cases"], "case_id")
    rubric = _index(answers.get("answers"), "case_id")
    if set(cases) != set(rubric) or prompts["corpus_version"] != answers.get("corpus_version"):
        raise ValueError("question/answer corpus IDs or versions differ")
    for ident, row in rubric.items():
        for key in ("required_boundaries", "acceptable_interpretations", "decisive_missing_bridges", "clear_failures"):
            if not isinstance(row.get(key), list) or not row[key] or any(not isinstance(x, str) or not x.strip() for x in row[key]):
                raise ValueError(ident + "." + key + " must contain reference reasoning")
        _text(row.get("variant_check"), ident + ".variant_check")
    return {"status": "structural_checks_passed", "case_count": len(cases),
            "prompts_sha256": digest(prompts), "rubric_sha256": digest(answers),
            "semantic_certification": False,
            "checked": ["unique IDs and corpus version", "source locator fields", "blind schema without rubric fields", "reference reasoning fields"],
            "not_checked": ["source authenticity or full-work coverage", "entailment of prose", "a character tier or winner"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "packet", "rubric", "record", "review", "audit"))
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--ids", help="comma-separated selected case IDs; default all")
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--response", type=Path)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--judgments", type=Path)
    parser.add_argument("--respondent")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in {"packet", "list", "audit"}:
            prompts = read_json(args.data / "prompts.json")
        if args.command == "list":
            value = [{"case_id": r["case_id"], "topic": r["topic"]} for r in prompts["cases"]]
        elif args.command == "packet":
            value = create_packet(prompts, args.ids.split(",") if args.ids else None)
        elif args.command == "rubric":
            value = read_json(args.data / "answers.json")
        elif args.command == "audit":
            value = audit(prompts, read_json(args.data / "answers.json"))
        elif args.command == "record":
            if not args.packet or not args.response or not args.respondent:
                raise ValueError("record requires --packet, --response and --respondent")
            value = record_response(read_json(args.packet), read_json(args.response), respondent=args.respondent)
        else:
            if not args.record or not args.judgments:
                raise ValueError("review requires --record and --judgments")
            value = record_review(read_json(args.record), read_json(args.judgments), read_json(args.data / "answers.json"))
        rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(rendered, end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc), "semantic_certification": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
