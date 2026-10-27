"""Mechanical benchmark invariants only: never a semantic scoring oracle."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import semantic_benchmark as sb


class SemanticPacketTests(unittest.TestCase):
    def setUp(self):
        self.prompts = sb.read_json(sb.DATA / "prompts.json")
        self.answers = sb.read_json(sb.DATA / "answers.json")
        self.packet = sb.create_packet(self.prompts, ["SB-01"])

    def response(self, **extra):
        return {"packet_sha256": self.packet["packet_sha256"], "responses": [
            {"case_id": "SB-01", "analysis": "This deliberately arbitrary prose is not graded by the recorder.",
             **{k: [] for k in sb.RESPONSE_FIELDS}, **extra}
        ]}

    def test_corpus_links_and_versions_are_consistent(self):
        result = sb.audit(self.prompts, self.answers)
        self.assertEqual(result["case_count"], 6)
        self.assertFalse(result["semantic_certification"])
        self.assertIn("entailment of prose", result["not_checked"])

    def test_packet_selects_only_required_sources_without_answer_fields(self):
        self.assertEqual([c["case_id"] for c in self.packet["cases"]], ["SB-01"])
        self.assertEqual([s["id"] for s in self.packet["sources"]], ["disney-stormbreaker"])
        for key in ("required_boundaries", "clear_failures", "acceptable_interpretations", "variant_check"):
            self.assertNotIn(key, json.dumps(self.packet))

    def test_cli_packet_does_not_need_or_open_answer_resource(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "prompts.json").write_text(json.dumps(self.prompts), encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT / "scripts/semantic_benchmark.py"),
                                  "packet", "--data", str(folder), "--ids", "SB-03"],
                                 capture_output=True, encoding="utf-8")
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["cases"][0]["case_id"], "SB-03")

    def test_unknown_duplicate_or_empty_selection_is_refused(self):
        for selection in (["unknown"], ["SB-01", "SB-01"], []):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                sb.create_packet(self.prompts, selection)

    def test_rubric_key_in_prompts_is_refused(self):
        self.prompts["cases"][0]["acceptable_interpretations"] = ["leaked reference"]
        with self.assertRaisesRegex(ValueError, "rubric fields"):
            sb.create_packet(self.prompts)

    def test_modified_packet_is_not_silently_recorded(self):
        self.packet["cases"][0]["fixed_context"] = "changed evidence"
        with self.assertRaisesRegex(ValueError, "changed"):
            sb.record_response(self.packet, self.response(), respondent="test worker")

    def test_response_must_bind_packet_and_cover_exact_selection(self):
        for mutation in ("hash", "case", "missing"):
            response = self.response()
            if mutation == "hash":
                response["packet_sha256"] = "incorrect"
            elif mutation == "case":
                response["responses"][0]["case_id"] = "SB-02"
            else:
                response["responses"] = []
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                sb.record_response(self.packet, response, respondent="test worker")

    def test_recording_prose_never_produces_automatic_semantic_pass(self):
        result = sb.record_response(self.packet, self.response(assessment="acceptable", tier="arbitrary"), respondent="test worker")
        self.assertEqual(result["status"], "recorded_unreviewed")
        self.assertFalse(result["semantic_certification"])
        self.assertNotIn("score", result)
        self.assertNotIn("assessment", result)

    def test_review_is_attributed_requires_reasons_and_binds_response(self):
        record = sb.record_response(self.packet, self.response(), respondent="test worker")
        judgments = {"reviewer": "host-test", "response_sha256": record["response_sha256"], "judgments": [
            {"case_id": "SB-01", "assessment": "unresolved", "rationale": "Needs actual human comparison.",
             "evidence_comparison": "The test has deliberately not interpreted the source."}
        ]}
        result = sb.record_review(record, judgments, self.answers)
        self.assertEqual(result["status"], "host_review_recorded")
        self.assertEqual(result["review"]["reviewer"], "host-test")
        self.assertFalse(result["semantic_certification"])
        judgments["judgments"][0]["evidence_comparison"] = ""
        with self.assertRaises(ValueError):
            sb.record_review(record, judgments, self.answers)

    def test_changed_response_or_wrong_rubric_revision_is_refused(self):
        record = sb.record_response(self.packet, self.response(), respondent="test worker")
        altered = copy.deepcopy(record)
        altered["response"]["responses"][0]["analysis"] = "changed"
        with self.assertRaisesRegex(ValueError, "binding changed"):
            sb.record_review(altered, {}, self.answers)
        self.answers["corpus_version"] = "different-revision"
        with self.assertRaisesRegex(ValueError, "corpus"):
            sb.record_review(record, {}, self.answers)


if __name__ == "__main__":
    unittest.main()
