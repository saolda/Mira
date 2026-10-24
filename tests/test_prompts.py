from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

from mira.decisions import ScriptedLLM, prepared_request
from mira.experiments import Experiments, file_hashes
from mira.format import digest, dumps, loads
from mira.inspection import Inspector
from mira.prompts import ACTIONS, PromptTemplates
from mira.research import Research


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.templates = self.directory / "templates"
        shutil.copytree(Path(__file__).resolve().parents[1] / "prompt_templates", self.templates)
        self.env = patch.dict("os.environ", {"MIRA_PROMPT_TEMPLATES": str(self.templates)})
        self.env.start(); self.addCleanup(self.env.stop)
        self.catalog = Experiments(self.directory / "memory")

    def call(self, name):
        root = self.catalog.create(name)
        llm = ScriptedLLM([{"keywords": ["test"]}])
        r = Research(root, llm, {}); r.initialize("Recorded context?", ["fixture"])
        self.assertEqual(r.step()["status"], "committed")
        file = next((root / "interactions").glob("*/request.json"))
        return root, llm.requests[0], file, loads(file.read_text())

    def test_templates_preserve_every_historical_fixture_request_byte_for_byte(self):
        path = Path(__file__).resolve().parents[1] / "docs/examples/full_research_transcript.md"
        records = [loads(m[1]) for m in re.finditer(r"Actual request record:\n```json\n(.*?)\n```", path.read_text(), re.S)]
        self.assertGreater(len(records), 10)
        seen = set()
        for record in records:
            original = record["serialized_request"]; payload = loads(original)
            settings = {k: v for k, v in payload.items() if k not in {"model", "messages"}}
            rendered, metadata = prepared_request(payload["model"], settings, record["action"], record["context"])
            self.assertEqual(rendered, original)
            self.assertEqual(metadata["filled_messages"], payload["messages"])
            seen.add(record["action"])
        self.assertEqual(seen, set(ACTIONS))

    def test_source_hashes_and_literal_context_not_recursively_templated(self):
        context = {"question": 'Literal {{ unknown }} ${name} "quoted" \n text'}
        for action in ACTIONS:
            messages, metadata = PromptTemplates().render(action, context)
            self.assertEqual(loads(messages[1]["content"])["context"], context)
            self.assertEqual(metadata["bindings"]["context"], context)
            for file in metadata["files"]:
                self.assertEqual(file["sha256"], digest(file["source"]))

    def test_recorded_filled_templates_equal_the_actual_model_request(self):
        root, wire, file, record = self.call("wire")
        snapshot = record["prompt_template"]
        self.assertEqual(snapshot["serialized_request_sha256"], digest(wire))
        self.assertEqual(snapshot["filled_messages"], loads(wire)["messages"])
        before = file_hashes(root)
        data = Inspector(self.catalog.home).decision("wire", file.parent.name)
        self.assertTrue(data["template_verification"]["matches_recorded_request"])
        self.assertEqual(data["filled_prompt_messages"], loads(wire)["messages"])
        self.assertEqual(file_hashes(root), before)

    def test_template_edit_changes_only_new_calls_and_preserves_old_provenance(self):
        root, wire, file, original = self.call("before")
        before = file_hashes(root)
        system = self.templates / "system.txt"
        system.write_bytes(system.read_bytes() + b"\r\nAn explicit new local instruction.\r\n")
        _, next_wire, _, new = self.call("after")
        self.assertNotEqual(next_wire, wire)
        self.assertTrue(loads(next_wire)["messages"][0]["content"].endswith("\r\n"))
        data = Inspector(self.catalog.home).decision("before", file.parent.name)
        self.assertEqual(data["serialized_request"], wire)
        self.assertEqual(data["prompt_template"], original["prompt_template"])
        self.assertTrue(data["template_verification"]["matches_recorded_request"])
        self.assertNotEqual(new["prompt_template"]["files"][0]["sha256"], original["prompt_template"]["files"][0]["sha256"])
        self.assertEqual(file_hashes(root), before)

    def test_unknown_placeholder_missing_context_and_missing_file_fail_closed(self):
        user = self.templates / "R1.user.json"
        original = user.read_text()
        user.write_text(original.replace("context_json", "typo_context"))
        self.assertRaisesRegex(ValueError, "unknown prompt placeholder", PromptTemplates().render, "R1", {})
        user.write_text('{"action":"R1"}')
        self.assertRaisesRegex(ValueError, "preserve action", PromptTemplates().render, "R1", {})
        user.unlink()
        self.assertRaises(FileNotFoundError, PromptTemplates().render, "R1", {})
        self.assertRaises(ValueError, PromptTemplates().render, "R2", {})

    def test_historical_calls_without_snapshot_are_not_backfilled(self):
        root, wire, file, record = self.call("legacy")
        del record["prompt_template"]; file.write_text(dumps(record))
        data = Inspector(self.catalog.home).decision("legacy", file.parent.name)
        self.assertIsNone(data["prompt_template"])
        self.assertFalse(data["template_verification"]["recorded"])
        self.assertIn("not recorded", data["template_verification"]["notice"])
        self.assertEqual(data["filled_prompt_messages"], loads(wire)["messages"])

    def test_mismatched_template_snapshot_does_not_override_original_wire_body(self):
        root, wire, file, record = self.call("mismatch")
        record["prompt_template"]["filled_messages"][0]["content"] = "A wrong reconstructed prompt"
        file.write_text(dumps(record))
        data = Inspector(self.catalog.home).decision("mismatch", file.parent.name)
        self.assertFalse(data["template_verification"]["matches_recorded_request"])
        self.assertTrue(data["warnings"])
        self.assertEqual(data["filled_prompt_messages"], loads(wire)["messages"])
