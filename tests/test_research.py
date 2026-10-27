from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

from mira import ValidationError
from mira.decisions import ScriptedLLM
from mira.format import dumps, loads
from mira.interactions import read_records, transcript
from mira.research import Research
from mira.search import FixtureSearch
from mira import research_tree as tree


def evidence():
    return {"status": "ok", "results": [{"id": "fixture-1", "url": "https://example.org/fixture", "title": "Synthetic measurements",
        "content": "Under the same conditions A transfers less heat than B. This is fictional test evidence.", "content_kind": "fixture", "truncated": False}]}


def draft(label="A"):
    return {"type": "claim", "text": "The fixture describes " + label,
            "qualification": "Controlled synthetic fixture; no real experiment.",
            "source_ids": ["fixture-1"], "related_to": None}


def decision(kind="answered"):
    return {"decision": kind, "reason": "Scripted research disposition."}


def interrupted_model(root):
    class ExitModel(ScriptedLLM):
        def complete(self, request): os._exit(71)
    Research(root, ExitModel([]), {}).step()


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, responses, searches=(), **config):
        self.llm = ScriptedLLM(responses); self.adapter = FixtureSearch(searches)
        self.r = Research(self.root, self.llm, {"fixture": self.adapter})
        config = {"context_budget": 12000, **config}
        self.r.initialize("How does the fictional barrier affect heat?", ["fixture"], **config)
        return self.r

    def state(self):
        return loads((self.root / "research/state.json").read_text())

    def test_deterministic_r1_r2_r3_r4_restart_and_transcript(self):
        r = self.make([{"keywords": ["barrier", "heat"]}, {"results": [draft()]}, decision()], [evidence()])
        self.assertEqual(r.step()["action"], "R1")
        self.assertEqual(r.step()["action"], "R2")
        pending = self.state()["nodes"]["q1"]["pending_results"]
        self.assertIsNotNone(pending)
        r = Research(self.root, self.llm, {"fixture": self.adapter})
        self.assertEqual(r.step()["action"], "R3")
        self.assertEqual(r.step()["action"], "R4")
        state = self.state(); self.assertEqual(state["nodes"]["q1"]["status"], "answered")
        self.assertEqual(state["research_cycles"], 4); self.assertEqual(len(self.llm.requests), 3)
        self.assertEqual(r.step()["status"], "finished")
        self.assertEqual(self.adapter.queries, ["barrier heat"])
        records = read_records(self.root); self.assertEqual(len(records), 3)
        for record in records:
            self.assertEqual(record["request"]["serialized_request"], self.llm.requests[record["request"]["sequence"] - 1])
            self.assertTrue(record["validation"]["accepted"])
            self.assertEqual(record["outcome"]["status"], "committed")
        full = transcript(self.root, full=True)
        for term in ("R1", "R2", "R3", "R4", "Synthetic measurements", "serialized_request", "research_terminal", "scripted-fixture-v1"):
            self.assertIn(term, full)
        self.assertLess(len(transcript(self.root)), len(full))
        # Independent of controller state and SQLite.
        (self.root / "research/state.json").unlink()
        self.assertIn("serialized_request", transcript(self.root, full=True))

    def test_failed_and_empty_searches_both_advance_and_record_distinct_outcomes(self):
        self.llm = ScriptedLLM([{"keywords": ["heat"]}, decision()])
        r = Research(self.root, self.llm, {"offline":FixtureSearch([{"status":"failed","results":[],"error":"network"}]),
             "empty":FixtureSearch([{"status":"empty","results":[]}])})
        r.initialize("Question?", ["offline","empty"])
        r.step()
        failed = r.step(); self.assertEqual(failed["status"], "committed")
        self.assertEqual(failed["search_status"], "failed")
        self.assertEqual(self.state()["nodes"]["q1"]["next_database_index"], 1)
        self.assertEqual(r.step()["search_status"], "empty")
        self.assertEqual(self.state()["nodes"]["q1"]["next_database_index"], 2)
        self.assertEqual(r.step()["action"], "R4")
        self.assertEqual(len(self.llm.requests), 2)

    def test_prompts_supply_search_history_evidence_and_provider_by_named_slots(self):
        self.llm = ScriptedLLM([{"keywords": ["heat"]}, {"results": [draft()]}, decision()])
        r = Research(self.root, self.llm, {"offline":FixtureSearch([{"status":"failed","results":[],"error":"offline"}]),
            "fixture":FixtureSearch([{**evidence(), "raw_api_response":"Raw provider feed is retained outside prompts."}])})
        r.initialize("How does the fictional barrier affect heat?", ["offline","fixture"], context_budget=12000)
        self.assertEqual(r.step()["status"], "committed")
        self.assertEqual(r.step()["status"], "committed")
        for _ in range(3): self.assertEqual(r.step()["status"], "committed")
        from mira.interactions import read_records
        prompts = {record["request"]["action"]: {"context": record["request"]["context"]}
                   for record in read_records(self.root)}
        r1 = prompts["R1"]["context"]
        self.assertEqual(set(r1), {"question", "question_context", "previous_search_terms", "control_terms", "memory_context"})
        self.assertEqual(r1["question"], self.state()["nodes"]["q1"]["question"])
        self.assertEqual(r1["question_context"], [])
        self.assertEqual(r1["previous_search_terms"], [])
        from mira.r1 import CONTROL_TERMS
        self.assertEqual(r1["control_terms"], CONTROL_TERMS)
        r3 = prompts["R3"]["context"]
        self.assertEqual(r3["research"]["results"], evidence()["results"])
        r4 = prompts["R4"]["context"]
        self.assertEqual([s["status"] for s in r4["search_history"]], ["failed", "ok"])
        self.assertEqual([s["query"] for s in r4["search_history"]], ["heat", "heat"])
        self.assertEqual(r4["search_history"][0]["error"], "offline")
        self.assertIn("r1", [m["id"] for m in r4["research_results"]["memories"]])
        self.assertNotIn("raw_api_response", dumps(prompts))
        files = r.store._files()
        self.assertFalse(any("Raw provider feed" in raw for raw in files.values()))
        self.assertTrue(list((self.root / "retrieved").glob("*.json")))

    def test_all_dispositions_retry_to_r1_and_sustained_priority(self):
        for kind in ("kill", "answered", "retry"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                llm = ScriptedLLM([{"keywords": ["heat"]}, decision(kind), {"keywords": ["thermal transfer"]}])
                r = Research(directory, llm, {"fixture": FixtureSearch([{"status": "empty", "results": []}])})
                r.initialize("Question?", ["fixture"])
                for _ in range(3): self.assertEqual(r.step()["status"], "committed")
                state = loads((Path(directory) / "research/state.json").read_text()); root = state["nodes"]["q1"]
                self.assertEqual(root["child_ids"], [])
                if kind == "retry":
                    self.assertEqual(root["next_database_index"], 0)
                    self.assertEqual(root["priority"], 7)
                    self.assertEqual(state["active_node_id"], "q1")
                    self.assertIsNone(root["keywords"])
                    self.assertEqual(root["previous_search_terms"], ["heat"])
                    self.assertEqual(root["status"], "living")
                    self.assertEqual(r.step()["action"], "R1")
                    self.assertEqual(read_records(directory)[-1]["request"]["context"]["previous_search_terms"], ["heat"])
                else:
                    self.assertEqual(root["status"], "killed" if kind == "kill" else "answered")

    def test_priority_cap_oldest_tie_and_no_preemption(self):
        state = tree.initial("Root", ["fixture"])
        state["nodes"].update(q2=tree.node("q2", "A", "q1"), q3=tree.node("q3", "B", "q1"))
        state["next_node"] = 4; state["nodes"]["q1"]["child_ids"] = ["q2", "q3"]
        state["nodes"]["q1"]["priority"] = 1
        state["nodes"]["q2"]["priority"] = 10; state["nodes"]["q3"]["priority"] = 10
        tree.refresh(state, [])
        self.assertEqual(state["active_node_id"], "q1")
        state["nodes"]["q1"]["priority"] = 0; tree.refresh(state, [])
        self.assertEqual(state["active_node_id"], "q2")
        self.assertEqual(tree.metrics(state)["max_depth"], 1)

    def test_rejected_raw_response_and_pending_evidence_preserved(self):
        r = self.make([{"keywords": ["heat"]}, "{not JSON"], [evidence()])
        r.step(); r.step(); before = self.state()
        event = r.step(); self.assertEqual(event["status"], "rejected")
        self.assertEqual(before, self.state())
        records = read_records(self.root)
        self.assertEqual(records[-1]["response"]["raw"], "{not JSON")
        self.assertFalse(records[-1]["validation"]["accepted"])
        self.assertIsNone(records[-1]["outcome"]["action_committed"])
        self.assertIn("{not JSON", transcript(self.root, full=True))

    def test_unsupported_evidence_no_second_llm_pass(self):
        bad = draft(); bad["source_ids"] = ["invented"]
        r = self.make([{"keywords": ["heat"]}, {"results": [bad]}], [evidence()])
        r.step(); r.step(); self.assertEqual(r.step()["status"], "rejected")
        self.assertEqual(len(self.llm.requests), 2)
        self.assertEqual(r.knowledge.validate()["documents"], 0)
        # Old memory proposals are rejected, not silently migrated or admitted.
        r.llm = ScriptedLLM([{"memories": [], "no_finding_reason": "Old contract"}])
        event = r.step()
        self.assertEqual(event["status"], "rejected")
        self.assertNotIn("memory_ids", event)
        self.assertEqual(read_records(self.root)[-1]["outcome"]["memory_ids"], [])
        self.assertEqual(r.knowledge.validate()["documents"], 0)

    def test_interrupted_call_needs_explicit_acknowledgment(self):
        r = self.make([{"keywords": ["heat"]}])
        p = multiprocessing.get_context("fork").Process(target=interrupted_model, args=(str(self.root),)); p.start(); p.join(10)
        self.assertEqual(p.exitcode, 71)
        self.assertRaisesRegex(ValidationError, "interrupted/unknown", r.step)
        self.assertIn("interrupted_or_unknown", transcript(self.root, full=True))
        self.assertEqual(len(r.acknowledge_interrupted()), 1)
        self.assertEqual(r.step()["action"], "R1")

    def test_context_block_and_no_finding_interpretation(self):
        r = self.make([{"keywords": ["heat"]}], context_budget=100, output_reserve=50)
        self.assertEqual(r.step()["status"], "rejected"); self.assertFalse(self.llm.requests)
        with tempfile.TemporaryDirectory() as directory:
            llm = ScriptedLLM([{"keywords": ["heat"]}, {"results": []}])
            r = Research(directory, llm, {"fixture": FixtureSearch([evidence()])}); r.initialize("Q?", ["fixture"], context_budget=12000)
            for _ in range(3): self.assertEqual(r.step()["status"], "committed")
            self.assertEqual(r.knowledge.validate()["documents"], 0)

    def test_transport_errors_and_secret_redaction(self):
        class SecretModel(ScriptedLLM): secrets = ("test-secret-token",)
        llm = SecretModel([RuntimeError("failed test-secret-token")])
        r = Research(self.root, llm, {}); r.initialize("Q?", ["fixture"], context_budget=12000)
        self.assertEqual(r.step()["status"], "rejected")
        for path in self.root.rglob("*"):
            if path.is_file(): self.assertNotIn("test-secret-token", path.read_text())
        self.assertIn("call_failed", transcript(self.root, full=True))

    def test_corrupt_tree_and_reference_validation(self):
        r = self.make([])
        with r.store.lock():
            token, memories, equations, ledger = r.store.read()
            state = self.state(); state["nodes"]["q1"]["child_ids"] = ["q99"]
            self.assertRaises((ValidationError, KeyError), r.store.publish, memories, equations, ledger, token,
                              files={"research/state.json": dumps(state)})
        self.assertEqual(self.state()["nodes"]["q1"]["child_ids"], [])
