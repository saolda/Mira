from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

from mira.decisions import ScriptedLLM
from mira.experiments import Experiments, file_hashes
from mira.format import digest, dumps, loads
from mira.inspection import Inspector
from mira.prompts import ACTIONS, SLOTS, PromptTemplates
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

    def test_historical_fixture_prompts_are_displayed_without_new_instructions(self):
        path = Path(__file__).parent / "fixtures/full_research_transcript.txt"
        records = [loads(m[1]) for m in re.finditer(r"Actual request record:\n```json\n(.*?)\n```", path.read_text(), re.S)]
        self.assertGreater(len(records), 10)
        root = self.catalog.create("historical")
        seen = set()
        for i, record in enumerate(records):
            original = record["serialized_request"]; payload = loads(original)
            identity = f"{i:08d}-historical"
            path = root / "interactions" / identity; path.mkdir(parents=True)
            (path / "request.json").write_text(dumps(record))
            before = file_hashes(root)
            data = Inspector(self.catalog.home).decision("historical", identity)
            self.assertEqual(data["serialized_request"], original)
            self.assertEqual(data["filled_prompt_messages"], payload["messages"])
            self.assertIsNone(data["task_instructions"]["task"])
            if record["action"] == "R4": self.assertIsNone(data["inputs"]["search_evidence"])
            self.assertEqual(file_hashes(root), before)
            seen.add(record["action"])
        self.assertEqual(seen, set(ACTIONS) - {"R0", "R5"})

    def test_source_hashes_and_literal_context_not_recursively_templated(self):
        for action in ACTIONS:
            context = dict.fromkeys(SLOTS[action], None)
            context["question"] = 'Literal {{ unknown }} ${name} "quoted" \n Unicode 温度'
            messages, metadata = PromptTemplates().render(action, context)
            self.assertEqual([m["role"] for m in messages], ["user"])
            self.assertIn(dumps(context["question"]).rstrip("\n"), messages[0]["content"])
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

    def test_every_action_has_an_independent_plain_text_prompt(self):
        for action in ACTIONS:
            context = {key: {"marker": key} for key in SLOTS[action]}
            messages, snapshot = PromptTemplates().render(action, context)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["role"], "user")
            self.assertTrue(messages[0]["content"].startswith("Generate concise, targeted search terms" if action == "R1" else "Extract only substantive information" if action == "R3" else action + ":"))
            self.assertIn("Return JSON only", messages[0]["content"])
            self.assertNotIn('"$schema"', messages[0]["content"])
            self.assertEqual(snapshot["bindings"]["context"], context)
            self.assertEqual(len(snapshot["files"]), 1)
            self.assertEqual(snapshot["files"][0]["path"], "prompt_templates/" + action + ".txt")
            for key in SLOTS[action]:
                self.assertIn("{{" + key + "}}", snapshot["files"][0]["source"])
                self.assertIn(dumps(context[key]).rstrip("\n"), messages[0]["content"])
        r4 = PromptTemplates().sources("R4")[0]["source"]
        for decision in ("kill", "answered", "retry"):
            self.assertIn("- " + decision + ":", r4)

    def test_surrounding_text_crlf_and_empty_values_preserved_exactly(self):
        source = "Prefix 温度\r\n" + " / ".join("{{" + key + "}}" for key in SLOTS["R1"]) + "\r\nSuffix\r\n"
        (self.templates / "R1.txt").write_bytes(source.encode())
        context = dict.fromkeys(SLOTS["R1"], None)
        context.update(question="", question_context=[], previous_search_terms=[], control_terms=[], memory_context={"note": "first\nsecond {{question}}"})
        messages, metadata = PromptTemplates().render("R1", context)
        expected = "Prefix 温度\r\n" + " / ".join(dumps(context[key]).rstrip("\n") for key in SLOTS["R1"]) + "\r\nSuffix\r\n"
        self.assertEqual(messages[0]["content"], expected)
        self.assertEqual(metadata["files"][0]["source"], source)
        self.assertIn('""', expected)
        with self.assertRaisesRegex(ValueError, "missing prompt values"):
            PromptTemplates().render("R1", {k: v for k, v in context.items() if k != "question"})

    def test_unknown_context_fields_cannot_be_silently_omitted(self):
        self.assertRaisesRegex(ValueError, "no declared prompt slot", PromptTemplates().render, "R4", {"unbound_evidence": "important"})

    def test_template_edit_changes_only_new_calls_and_preserves_old_provenance(self):
        root, wire, file, original = self.call("before")
        before = file_hashes(root)
        system = self.templates / "R1.txt"
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
        user = self.templates / "R1.txt"
        original = user.read_text()
        context = dict.fromkeys(SLOTS["R1"], None)
        for wrong in ("typo_context", "question_json"):
            user.write_text(original.replace("{{question}}", "{{" + wrong + "}}"))
            self.assertRaisesRegex(ValueError, "unknown prompt placeholder", PromptTemplates().render, "R1", context)
        for wrong in ("{{Question}}", "{{question.name}}", "{{question", "question}}"):
            user.write_text(original.replace("{{question}}", wrong))
            self.assertRaisesRegex(ValueError, "malformed prompt placeholder", PromptTemplates().render, "R1", context)
        user.write_text("R1: No slots")
        self.assertRaisesRegex(ValueError, "missing slot", PromptTemplates().render, "R1", context)
        user.unlink()
        self.assertRaises(FileNotFoundError, PromptTemplates().render, "R1", context)
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

    def test_historical_json_template_snapshot_still_displays_exactly(self):
        root, _, file, record = self.call("old-json-snapshot")
        old_user = {"context": {"question": "Historical question", "children": []},
                    "task": "Original task", "instructions": ["Original instruction"],
                    "output_contract": {"keywords": ["terms"]}}
        messages = [{"role": "system", "content": "Original instruction\r\n"},
                    {"role": "user", "content": dumps(old_user)}]
        wire = dumps({"model": "historical", "messages": messages})
        record.update(serialized_request=wire, request=loads(wire), prompt_template={
            "version": 1, "filled_messages": messages, "serialized_request_sha256": digest(wire),
            "files": [{"path": "prompt_templates/R1.user.json", "source": "Original JSON template", "sha256": digest("Original JSON template")}],
            "bindings": {"context": old_user["context"]}})
        file.write_text(dumps(record))
        before = file_hashes(root)
        data = Inspector(self.catalog.home).decision("old-json-snapshot", file.parent.name)
        self.assertEqual(data["serialized_request"], wire)
        self.assertEqual(data["filled_prompt_messages"], messages)
        self.assertEqual(data["task_instructions"]["task"], "Original task")
        self.assertTrue(data["template_verification"]["matches_recorded_request"])
        self.assertEqual(file_hashes(root), before)

    def test_tampered_plain_text_bindings_do_not_become_actual_input(self):
        root, wire, file, record = self.call("changed-bindings")
        record["prompt_template"]["bindings"]["context"]["question"] = "Wrong question"
        file.write_text(dumps(record))
        data = Inspector(self.catalog.home).decision("changed-bindings", file.parent.name)
        self.assertFalse(data["template_verification"]["matches_recorded_request"])
        self.assertIsNone(data["structured_context"])
        self.assertEqual(data["filled_prompt_messages"], loads(wire)["messages"])
