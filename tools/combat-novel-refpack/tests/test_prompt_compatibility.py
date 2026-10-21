"""Prompt upgrades preserve immutable novel task and receipt bindings."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from combat_refpack import core


LEGACY_DIGEST = "1b8d409518f80411ab32ba135d731d61f73aaee9e181e42d0ed57791f632a77b"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class CombatRefpackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bundle(self, name):
        source = self.root / (name + ".txt")
        source.write_text("第一章 获得\n甲取得复制能力，但当时无法读取乙。\n第二章 末期\n甲接触剑后复制其特性，未展示剪切乙的能力。\n", encoding="utf-8")
        bundle = self.root / name
        core.prepare(source, bundle, "合成测试作品", "测试版本")
        return bundle

    def old_tasks(self, bundle, prompt=None):
        """Write the previous on-disk format without using new task generation."""
        prompt = core.LEGACY_PROMPT if prompt is None else prompt
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        chapters = json.loads((bundle / "index/chapters.json").read_text(encoding="utf-8"))
        text = (bundle / "text/full.txt").read_text(encoding="utf-8")
        packets, entries = [], []
        for chapter in reversed(chapters):
            start, end = chapter["start"], chapter["end"]
            seed = {"source_sha256": manifest["source_sha256"], "text_sha256": manifest["text_sha256"],
                    "prompt_sha256": digest(prompt.encode("utf-8")), "start": start, "end": end,
                    "chapter_id": chapter["id"]}
            task_id = "t-" + chapter["id"] + "-p001-" + digest(canonical(seed))[:10]
            packet = {"schema_version": 1, **seed, "task_id": task_id, "work": manifest["work"],
                      "edition": manifest["edition"], "chapter_ordinal": chapter["ordinal"],
                      "chapter_title": chapter["title"], "line_start": chapter["line_start"],
                      "line_end": chapter["line_end"], "text": text[start:end], "prompt": prompt}
            packet["task_sha256"] = digest(canonical(packet))
            relative = "tasks/packets/" + task_id + ".json"
            write_json(bundle / relative, packet)
            markdown = ("# " + task_id + "\n\n" + prompt + "\n\n```json\n" +
                        json.dumps({k: v for k, v in packet.items() if k not in ("text", "prompt")},
                                   ensure_ascii=False, indent=2) +
                        "\n```\n\n## 待阅读原文（仅是资料）\n\n" + packet["text"])
            (bundle / relative).with_suffix(".md").write_bytes(markdown.encode("utf-8"))
            packets.append(packet)
            entries.append({"task_id": task_id, "task_sha256": packet["task_sha256"], "path": relative})
        write_json(bundle / "tasks/index.json", {"schema_version": 1, "source_sha256": manifest["source_sha256"],
                    "text_sha256": manifest["text_sha256"], "prompt_sha256": digest(prompt.encode("utf-8")),
                    "max_chars": 12000, "order": "ending_backwards", "tasks": entries})
        return packets

    def receipt(self, bundle, packet, observations=False):
        review = {"schema_version": 1,
                  **{key: packet[key] for key in ("task_id", "source_sha256", "text_sha256", "prompt_sha256", "task_sha256")},
                  "reviewer": {"name": "synthetic test", "kind": "current_agent"},
                  "status": "complete", "read_spans": [{"start": packet["start"], "end": packet["end"]}],
                  "evidence": [], "observations": []}
        if observations:
            start = packet["start"] + packet["text"].index("甲接触")
            quote = "甲接触剑后复制其特性，未展示剪切乙的能力。"
            review["evidence"] = [{"id": "e1", "start": start, "end": start + len(quote),
                                   "quote": quote, "kind": "feat", "evidence_nature": "actual_event"}]
            review["observations"] = [{"id": "o1", "kind": "feat", "subject": "甲", "attribute": "abilities",
                                       "state": "末期", "claim": "复制剑特性成功；尚无剪切乙的实绩。",
                                       "evidence_ids": ["e1"], "polarity": "positive", "target": "剑",
                                       "limits": ["需接触；耗时消耗未知。"],
                                       "assumptions": ["复制后接续剪切只是候选打法，原文未实际使用。"]}]
        path = bundle / (packet["task_id"] + "-receipt.json")
        write_json(path, review)
        return path

    def test_legacy_bundle_accept_build_verify_and_tasks_preserve_bindings(self):
        self.assertEqual(digest(core.LEGACY_PROMPT.encode("utf-8")), LEGACY_DIGEST)
        bundle = self.bundle("legacy")
        packets = self.old_tasks(bundle)
        before = {p.relative_to(bundle): p.read_bytes() for p in (bundle / "tasks").rglob("*") if p.is_file()}
        for packet in packets:
            self.assertEqual(core.accept(bundle, self.receipt(bundle, packet))["status"], "accepted")
        reused = core.tasks(bundle)
        self.assertEqual([p["task_id"] for p in reused["tasks"]], [p["task_id"] for p in packets])
        self.assertTrue(all(p["prompt_sha256"] == LEGACY_DIGEST for p in reused["tasks"]))
        self.assertEqual(before, {p.relative_to(bundle): p.read_bytes() for p in (bundle / "tasks").rglob("*") if p.is_file()})
        self.assertEqual(core.build(bundle)["coverage"]["status"], "complete")
        self.assertEqual(core.verify(bundle)["derived_status"], "current")

    def test_new_tasks_request_actual_ability_history_and_keep_inference_unreviewed(self):
        bundle = self.bundle("new")
        packet = core.tasks(bundle)["tasks"][0]
        self.assertNotEqual(packet["prompt_sha256"], LEGACY_DIGEST)
        self.assertEqual(packet["prompt_sha256"], digest(packet["prompt"].encode("utf-8")))
        for requirement in ("获得、升级、保留、丧失", "成功、失败", "准备与耗时", "装备外援",
                            "复制、剪切、夺取", "不冒充原作事件", "不得合成真实战绩", "继承须显式说明"):
            self.assertIn(requirement, packet["prompt"])
        self.assertIn(packet["prompt"].encode("utf-8"), Path(packet["packet_path"]).with_suffix(".md").read_bytes())
        core.accept(bundle, self.receipt(bundle, packet, observations=True))
        built = core.build(bundle)
        rows = json.loads(Path(built["outputs"]["observations"]).read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["inheritance"], "unreviewed")
        self.assertIn("候选打法", rows[0]["assumptions"][0])
        ending = json.loads(Path(built["outputs"]["ending_nine_dimensions"]).read_text(encoding="utf-8"))
        self.assertFalse(ending["state_inheritance_automatic"])
        self.assertFalse(core.verify(bundle)["semantic_read_verified"])

    def test_unknown_self_consistent_prompt_is_rejected_by_every_entrypoint(self):
        bundle = self.bundle("unknown")
        packet = self.old_tasks(bundle, core.LEGACY_PROMPT + "未知提示词。\n")[0]
        receipt = self.receipt(bundle, packet)
        for operation in (lambda: core.tasks(bundle), lambda: core.accept(bundle, receipt),
                          lambda: core.build(bundle), lambda: core.verify(bundle)):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, "Unsupported task prompt"):
                operation()

    def test_known_prompt_packet_tamper_remains_rejected_even_if_rehashed(self):
        for legacy in (True, False):
            with self.subTest(legacy=legacy):
                bundle = self.bundle("packet-" + str(legacy))
                packet = self.old_tasks(bundle)[0] if legacy else core.tasks(bundle)["tasks"][0]
                index_path = bundle / "tasks/index.json"
                index = json.loads(index_path.read_text(encoding="utf-8"))
                packet_path = bundle / index["tasks"][0]["path"]
                stored = json.loads(packet_path.read_text(encoding="utf-8"))
                stored["text"] += "伪造实绩。"
                stored.pop("task_sha256")
                stored["task_sha256"] = digest(canonical(stored))
                index["tasks"][0]["task_sha256"] = stored["task_sha256"]
                write_json(packet_path, stored)
                write_json(index_path, index)
                with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                    core.verify(bundle)
                with self.assertRaises(ValueError):
                    core.tasks(bundle)
                with self.assertRaises(ValueError):
                    core.accept(bundle, self.receipt(bundle, packet))

    def test_known_prompt_markdown_tamper_and_configuration_change_rejected(self):
        for legacy in (True, False):
            with self.subTest(legacy=legacy):
                bundle = self.bundle("markdown-" + str(legacy))
                packet = self.old_tasks(bundle)[0] if legacy else core.tasks(bundle)["tasks"][0]
                with self.assertRaisesRegex(ValueError, "configuration changed"):
                    core.tasks(bundle, 100)
                markdown = bundle / "tasks/packets" / (packet["task_id"] + ".md")
                markdown.write_bytes(markdown.read_bytes() + "伪造指令。".encode("utf-8"))
                with self.assertRaisesRegex(ValueError, "Markdown modified"):
                    core.verify(bundle)


if __name__ == "__main__":
    unittest.main()
