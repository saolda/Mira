"""Question documents: parsing, immutable recovery, prompt projections and budgets."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mira import branching, gardener, questions, research_tree as tree
from mira.decisions import ScriptedLLM, request
from mira.format import digest, dumps, loads
from mira.interactions import read_records
from mira.live import decode
from mira.research import Research
from mira.search import FixtureSearch
from test_gardener import seed
from test_research import evidence, draft, decision
from test_synthesis import selection, synthesis


MARKDOWN = """# Research question

How  does the fictional barrier affect heat?

## Context

Controlled fixture background; this is not real evidence.

## Research objectives

- Compare attributed heat measurements.
- Retain uncertainty and limitations.
"""


class QuestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "experiment"
        self.input = self.base / "question.md"
        self.input.write_bytes(MARKDOWN.encode())

    def make(self, responses=(), *, markdown=None, **config):
        if markdown is not None: self.input.write_bytes(markdown.encode())
        self.llm = ScriptedLLM(responses)
        self.r = Research(self.root, self.llm, {"fixture": FixtureSearch([evidence()])})
        self.r.initialize(question_file=self.input, databases=["fixture"], context_budget=60000, **config)
        return self.r

    def state(self): return loads((self.root / "research/state.json").read_text())

    def test_short_file_and_exact_question_whitespace_unicode_and_hash(self):
        raw = "# Research question\r\n\r\nExact  question 温度?  \r\n"
        r = self.make(markdown=raw)
        document = self.state()["question_document"]
        self.assertEqual(document, {"path": "research/question.md", "sha256": digest(raw),
            "question": "Exact  question 温度?  ", "context": "", "objectives": []})
        self.assertEqual(self.state()["nodes"]["q1"]["question"], document["question"])
        self.assertEqual((self.root / questions.PATH).read_bytes(), raw.encode())
        self.assertEqual(r.inspect()["question_document"], document)
        self.assertEqual(r.knowledge.validate()["documents"], 0)

    def test_optional_sections_ordered_nested_and_multiline_objectives(self):
        raw = "# Research question\n\nQuestion?\n\n## Research objectives\n\n1. First goal.\n   Further scope.\n   - Nested constraint.\n2. Second goal.\n\n## Context\n\nBackground.\n"
        parsed = questions.parse(raw)
        self.assertEqual(parsed["context"], "Background.")
        self.assertEqual(parsed["objectives"], ["1. First goal.\n   Further scope.\n   - Nested constraint.", "2. Second goal."])
        for name, body in (("Context", "Background."), ("Research objectives", "- An objective.")):
            self.assertEqual(questions.parse("# Research question\n\nQ?\n\n## " + name + "\n\n" + body)["question"], "Q?")

    def test_invalid_markdown_structure_and_empty_inputs(self):
        invalid = ["", "  ", "Question?", "# Wrong\n\nQuestion?", "Preface\n\n# Research question\n\nQ?",
            "# Research question", "# Research question\n\n```\nQ?\n```", "# Research question\n\n- Q?",
            "# Research question\n\nQ?\n\n# Context\n\nBackground.",
            "# Research question\n\nQ?\n\n### Context\n\nBackground.",
            "# Research question\n\nQ?\n\n## Unknown\n\nText.",
            "# Research question\n\nQ?\n\n## Context\n\nA.\n\n## Context\n\nB.",
            "# Research question\n\nQ?\n\n## Context", "# Research question\n\nQ?\n\n## Research objectives\n\nJust prose.",
            "# Research question\n\nQ?\n\n## Research objectives\n\n- Goal\n\nUnlisted goal.",
            "# Research question\n\nQ?\n\n## Research objectives\n\n-\n- Valid goal.",
            "# Research question\n\nQ?\x00"]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError): questions.parse(raw)
        self.input.write_bytes(b"\xff")
        with self.assertRaises(UnicodeError): questions.read(self.input)

    def test_cli_positional_and_question_file_and_rejects_both_or_neither(self):
        script = self.base / "script.json"; script.write_text(dumps({"responses": []}))
        for name, inputs in (("old", ["Exact question?"]), ("new", ["--question-file", str(self.input)])):
            root = self.base / name
            result = subprocess.run([sys.executable, "-m", "mira", "--root", str(root), "research-init", *inputs,
                "--strategy", "medical", "--script", str(script)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = loads(result.stdout)
            self.assertEqual(state["strategy_selection"]["method"], "explicit")
            self.assertEqual("question_document" in state, name == "new")
            self.assertEqual((root / questions.PATH).exists(), name == "new")
        for inputs in ([], ["Q?", "--question-file", str(self.input)]):
            root = self.base / "invalid"
            result = subprocess.run([sys.executable, "-m", "mira", "--root", str(root), "research-init", *inputs,
                "--strategy", "medical", "--script", str(script)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("provide a question or --question-file", result.stderr)
            self.assertFalse(root.exists())
        self.input.write_text("Malformed")
        result = subprocess.run([sys.executable, "-m", "mira", "--root", str(self.root), "research-init",
            "--question-file", str(self.input), "--strategy", "medical", "--script", str(script)], capture_output=True)
        self.assertNotEqual(result.returncode, 0); self.assertFalse(self.root.exists())

    def test_api_alternatives_and_legacy_restart(self):
        r = Research(self.root, ScriptedLLM([{"new_concepts": [], "reason": "Fixture search plan.", "search_concepts": ["heat", "transfer"]}]), {})
        for args, kwargs in (((), {}), (("Q?",), {"question_file": self.input})):
            with self.assertRaisesRegex(ValueError, "provide a question"):
                r.initialize(*args, databases=["fixture"], **kwargs)
        state = r.initialize("Exact old  question?", ["fixture"])
        self.assertNotIn("question_document", state)
        self.assertEqual(Research(self.root, r.llm, {}).step()["status"], "committed")
        self.assertFalse((self.root / questions.PATH).exists())
        self.assertIsNone(read_records(self.root)[0]["request"]["context"]["question_scope"]["research_brief"])

    def test_r0_receives_context_and_complete_objectives(self):
        llm = ScriptedLLM([{"strategy": "medical", "reason": "Explicit fixture domain."}])
        r = Research(self.root, llm, {})
        r.initialize(question_file=self.input, context_budget=60000)
        record = read_records(self.root)[0]["request"]
        self.assertEqual(record["action"], "R0")
        self.assertEqual(record["context"]["question"], questions.parse(MARKDOWN)["question"])
        self.assertEqual(record["context"]["research_brief"]["objectives"], questions.parse(MARKDOWN)["objectives"])
        self.assertIn("Controlled fixture", record["serialized_request"])

    def test_research_prompts_and_restart_do_not_reread_input(self):
        r = self.make([{"new_concepts": [], "reason": "Fixture search plan.", "search_concepts": ["heat", "transfer"]}, {"summary": "Fixture evidence.", "results": [draft()]}, decision()])
        self.input.write_text("External file changed after initialization.")
        self.assertEqual(r.step()["action"], "R1")
        self.assertEqual(r.step()["action"], "R2")
        r = Research(self.root, self.llm, r.adapters)
        self.input.unlink()
        self.assertEqual(r.step()["action"], "R3")
        self.assertEqual(r.step()["action"], "R4")
        self.assertEqual((self.root / questions.PATH).read_bytes(), MARKDOWN.encode())
        for record in read_records(self.root):
            supplied = record["request"]["context"]
            self.assertEqual(supplied["question"], questions.parse(MARKDOWN)["question"])
            brief = (supplied["question_scope"] if record["request"]["action"] == "R1" else supplied)["research_brief"]
            self.assertEqual(brief["context"], questions.parse(MARKDOWN)["context"])
            self.assertEqual(brief["objectives"], questions.parse(MARKDOWN)["objectives"])
            self.assertNotIn("question", brief)
        self.assertEqual(r.knowledge.validate()["documents"], 1)

    def test_parsed_fields_root_and_original_are_immutable(self):
        r = self.make()
        before = self.state()
        for change in (lambda s: s["question_document"].update(context="Changed"),
                       lambda s: s.pop("question_document"),
                       lambda s: s["nodes"]["q1"].update(question="Changed?")):
            with self.subTest(change=change), r.store.lock():
                token, docs, eqs, ledger = r.store.read(); state = deepcopy(before); change(state)
                with self.assertRaises(ValueError):
                    r.store.publish(docs, eqs, ledger, token, files={"research/state.json": dumps(state)})
        with r.store.lock():
            token, docs, eqs, ledger = r.store.read()
            changed = MARKDOWN.replace("barrier", "wall")
            state = deepcopy(before); state["question_document"] = questions.parse(changed)
            state["nodes"]["q1"]["question"] = state["question_document"]["question"]
            with self.assertRaisesRegex(ValueError, "immutable"):
                r.store.publish(docs, eqs, ledger, token, files={questions.PATH: changed, "research/state.json": dumps(state)})
            files = r.store._files(); files[questions.PATH] += "\n"
            with self.assertRaisesRegex(ValueError, "hash or parsed fields mismatch"): decode(files)
        self.assertEqual(self.state(), before)

    def test_initialization_journal_recovery_preserves_exact_crlf_snapshot(self):
        raw = MARKDOWN.replace("\n", "\r\n"); self.input.write_bytes(raw.encode())
        for stage in ("prepared", "replaced:research/question.md", "replaced:research/state.json", "before_commit"):
            with self.subTest(stage=stage):
                r = Research(self.base / stage.replace(":", "_"), ScriptedLLM([]), {})
                def fault(point):
                    if point == stage: raise RuntimeError("simulated interruption")
                with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                    r.initialize(question_file=self.input, strategy="medical", fault=fault)
                report = r.store.recovery_status()
                operation = report["operations"][-1]
                self.assertIn(operation["assessment"], {"safely_finishable", "complete"})
                r.store.repair(operation["id"], apply=True)
                self.assertEqual((r.store.root / questions.PATH).read_bytes(), raw.encode())
                self.assertEqual(r.inspect()["question_document"], questions.parse(raw))
                self.assertEqual(r.knowledge.validate()["documents"], 0)

    def test_long_background_is_relevant_and_bounded_with_every_objective_intact(self):
        raw = MARKDOWN.replace("Controlled fixture background; this is not real evidence.",
            ("Unrelated background. " * 2000) + "\n\nHeat barrier scope at the end.")
        r = self.make(markdown=raw)
        state = self.state(); state["nodes"]["q2"] = tree.node("q2", "Heat barrier uncertainty?", "q1")
        for action, limit in questions.CONTEXT_BYTES.items():
            brief = questions.context(state, action, "q2")["research_brief"]
            self.assertLessEqual(len(brief["context"].encode()), limit)
            self.assertIn("Heat barrier scope at the end.", brief["context"])
            self.assertTrue(brief["context_excerpted"])
            self.assertEqual(brief["objectives"], questions.parse(raw)["objectives"])
        self.assertEqual(r.inspect()["question_document"]["context"], questions.parse(raw)["context"])

    def test_r5_budget_measures_the_complete_projection(self):
        r = self.make()
        with r.store.lock():
            _, docs, eqs, _ = r.store.read()
        state = self.state()
        supplied = branching.context(state, docs, eqs, "q1")
        wire = request(self.llm.model, self.llm.settings, "R5", supplied)
        self.assertEqual(state["nodes"]["q1"]["research_capacity"]["request_sha256"], digest(wire))
        self.assertEqual(state["nodes"]["q1"]["research_capacity"]["estimated_tokens"], len(wire.encode()) + 2048)
        self.assertEqual(supplied["research_brief"]["objectives"], questions.parse(MARKDOWN)["objectives"])

    def test_s1_and_s2_prompt_context_persists_across_restart(self):
        r = self.make([selection(), synthesis()])
        seed(r, own=2, child=0, leaf=0)
        self.assertEqual(r.step()["action"], "S1")
        pending = self.state()["pending_synthesis"]["context"]
        self.assertEqual(pending["research_brief"]["objectives"], questions.parse(MARKDOWN)["objectives"])
        self.input.unlink()
        r = Research(self.root, self.llm, {})
        self.assertEqual(r.step()["action"], "S2")
        for record in read_records(self.root):
            self.assertEqual(record["request"]["context"]["research_brief"], pending["research_brief"])
        self.assertEqual(self.state()["synthesis_attempts"][0]["status"], "completed")
        self.assertEqual(r.knowledge.document("s1").metadata["source_memories"], ["r1", "r2"])
        self.assertEqual(r.knowledge.validate()["documents"], 3)

    def test_oversized_question_or_objectives_block_without_loss_or_model_call(self):
        for section in ("question", "objectives"):
            with self.subTest(section=section):
                self.root = self.base / section
                raw = ("# Research question\n\n" + "Essential question " * 4000) if section == "question" else \
                    MARKDOWN + "- " + "Essential objective " * 4000 + "\n"
                r = self.make(markdown=raw)
                with r.execution(self.base / "logs") as log:
                    event = r.step()
                self.assertEqual(event["status"], "rejected")
                self.assertIn("blocked_context_budget", event["error"])
                self.assertFalse(self.llm.requests)
                records = [loads(line) for line in log.path.read_text().splitlines()]
                supplied = next(row["data"]["context"] for row in records if row["kind"] == "model_request_blocked")
                self.assertEqual(read_records(self.root), [])
                parsed = questions.parse(raw)
                self.assertEqual(supplied["question"], parsed["question"])
                self.assertEqual(supplied["question_scope"]["research_brief"]["objectives"], parsed["objectives"])
                self.assertEqual(self.state()["question_document"], parsed)

    def test_s2_budget_never_drops_essential_objectives(self):
        r = self.make()
        seed(r, own=2, child=0, leaf=0)
        with r.store.lock(): _, docs, eqs, _ = r.store.read()
        state = self.state(); state["question_document"]["objectives"] = ["- " + "Essential " * 8000]
        _, prepared, info = gardener.prepare(state, docs, eqs, docs, "Compare", self.llm.model, self.llm.settings)
        self.assertIsNone(prepared)
        supplied = gardener.context(state, docs, eqs, "q1", docs, objective="Compare", summarized=True)
        self.assertEqual(supplied["research_brief"]["objectives"], state["question_document"]["objectives"])
        self.assertTrue(info["usage"]["over_context_budget"])
