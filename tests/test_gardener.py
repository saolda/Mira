from pathlib import Path
import multiprocessing
import os
import tempfile
import unittest

from mira import research_tree as tree
from mira.format import dumps, loads, Memory, Unit, render
from mira.decisions import ScriptedLLM
from mira.interactions import read_records, transcript
from mira.research import Research
from mira.research_demo import DemoLLM, demonstrate
from mira import gardener
from test_research import evidence, draft, decision
from mira.search import FixtureSearch


def crash_gardener(root):
    def fault(stage):
        if stage == "replaced:memories/s1.md": os._exit(72)
    Research(root, DemoLLM(), {}).step(fault=fault)


def seed(r, *, own=2, child=2, leaf=2, killed=False):
    with r.store.lock():
        token, memories, equations, ledger = r.store.read()
        state = loads(r.store._files()["research/state.json"])
        state["nodes"].update(q2=tree.node("q2", "Child?", "q1"), q3=tree.node("q3", "Leaf?", "q2"))
        state["nodes"]["q1"]["child_ids"] = ["q2"]; state["nodes"]["q2"]["child_ids"] = ["q3"]; state["next_node"] = 4
        for n in state["nodes"].values(): n["status"] = "exhausted"
        if killed: state["nodes"]["q3"]["status"] = "killed"
        for identity, count in [("q1", own), ("q2", child), ("q3", leaf)]:
            for _ in range(count):
                number = len(memories) + 1
                memory = Memory("r" + str(number), "Synthetic", "Fixture only.", metadata={"node_id": identity,
                    "kind": "research", "source_memories": [], "synthesized_by": None, "created_order": number})
                memory.units.append(Unit(memory.allocate("f"), "Fixture", {"Kind": "claim", "Evidence status": "unverified",
                    "Proposition": "Fictional measurement.", "Explanation": "No real-world interpretation.", "Provenance": "Fixture author."}))
                memories.append(memory); state["nodes"][identity]["memory_ids"].append(memory.id)
        ledger["r"] = len(memories) + 1
        tree.refresh(state, memories)
        r.store.publish(memories, equations, ledger, token, files={"research/state.json": dumps(state)})


class GardenerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.llm = DemoLLM(); self.r = Research(self.root, self.llm, {})
        self.r.initialize("Synthetic research?", ["fixture"])

    def state(self): return loads((self.root / "research/state.json").read_text())

    def test_terminal_bonus_killed_material_and_completed_exclusion(self):
        seed(self.r, killed=True)
        state = self.state()
        self.assertEqual(state["nodes"]["q1"]["synthesis_score"], 1006)
        self.assertEqual(state["nodes"]["q2"]["synthesis_score"], 1004)
        self.assertEqual(state["nodes"]["q3"]["synthesis_score"], 2)
        out = self.r.run(20); self.assertEqual(out["status"], "finished")
        state = self.state(); self.assertEqual(state["nodes"]["q3"]["status"], "killed")
        self.assertEqual(state["nodes"]["q1"]["status"], "complete")
        self.assertEqual(state["nodes"]["q2"]["unsynthesized_memory_count"], 0)
        self.assertEqual(state["synthesis_candidate_order"], [])
        self.assertEqual(self.r.knowledge.document("r5").metadata["synthesized_by"][0], "s")
        calls = len(self.llm.requests); self.assertEqual(self.r.step()["status"], "finished")
        self.assertEqual(calls, len(self.llm.requests))

    def test_zero_and_one_inputs_complete_without_llm(self):
        seed(self.r, own=0, child=0, leaf=1)
        state = self.state()
        self.assertTrue(all(n["status"] == "complete" for n in state["nodes"].values()))
        self.assertEqual(state["nodes"]["q1"]["unsynthesized_memory_count"], 1)
        self.assertEqual(self.r.step()["status"], "finished"); self.assertFalse(self.llm.requests)

    def test_no_fitting_pair_is_explicit_and_does_not_consume(self):
        seed(self.r)
        with self.r.store.lock():
            token, memories, equations, ledger = self.r.store.read()
            state = self.state(); state["context_budget"] = 2100
            self.r.store.publish(memories, equations, ledger, token, files={"research/state.json": dumps(state)})
        event = self.r.step()
        self.assertEqual(event["status"], "blocked_synthesis")
        self.assertEqual(event["reason"], "no_fitting_pair")
        self.assertFalse(self.llm.requests)
        self.assertEqual(self.state()["nodes"]["q1"]["unsynthesized_memory_count"], 6)
        self.assertEqual(self.r.knowledge.validate()["documents"], 6)

    def test_bounded_batches_and_three_level_upward_demo(self):
        with tempfile.TemporaryDirectory() as directory:
            result = demonstrate(directory)
            self.assertEqual(result["status"], "finished")
            state = loads(Path(directory, "research/state.json").read_text())
            self.assertEqual(state["research_cycles"], 16)
            self.assertTrue(all(n["status"] == "complete" for n in state["nodes"].values()))
            records = read_records(directory)
            syntheses = [r for r in records if r["request"]["action"] == "S2"]
            self.assertTrue({"q1", "q2", "q4"} <= {r["request"]["node_id"] for r in syntheses})
            for record in syntheses:
                request = record["request"]["serialized_request"]
                self.assertLessEqual(len(request.encode()) + 2048, 8192)
                self.assertGreaterEqual(len(record["request"]["context"]["input_memories"]), 2)
                self.assertTrue(record["validation"]["accepted"])
            self.assertTrue(any(any(m["id"].startswith("s") for m in r["request"]["context"]["input_memories"]) for r in syntheses))
            text = transcript(directory, full=True)
            for term in ("S2", "source_memories", "source_findings", "Fictional barrier measurements", "selection"):
                self.assertIn(term, text)

    def test_five_research_actions_then_one_synthesis_same_process(self):
        with tempfile.TemporaryDirectory() as directory:
            llm = ScriptedLLM([{"keywords": ["heat"]}, {"memories": [draft(), draft("B")], "no_finding_reason": None},
                decision("retry"), {"memories": [], "no_finding_reason": "No new supported finding."}])
            r = Research(directory, llm, {"fixture": FixtureSearch([evidence(), evidence()])})
            r.initialize("Q?", ["fixture"])
            actions = [r.step()["action"] for _ in range(5)]
            self.assertEqual(actions, ["R1", "R2", "R3", "R4", "R2"])
            r.llm = DemoLLM()
            self.assertEqual(r.step()["action"], "S2")
            state = loads(Path(directory, "research/state.json").read_text())
            self.assertEqual(state["research_cycles"], 5); self.assertEqual(state["synthesis_cycles"], 1)
            self.assertEqual(state["research_cycles_since_synthesis"], 0)
            self.assertEqual(state["nodes"]["q1"]["priority"], 5)

    def test_rejected_synthesis_does_not_consume_or_increment_counters(self):
        seed(self.r)
        self.r.llm = ScriptedLLM([{"title": "Invalid", "summary": "No traceability.", "findings": []}])
        before = self.state()
        event = self.r.step(); self.assertEqual(event["status"], "rejected")
        self.assertEqual(self.state(), before)
        self.assertEqual(self.r.knowledge.document("r1").metadata["synthesized_by"], None)
        self.assertIn('"accepted": false', transcript(self.root, full=True))

    def test_guard_against_partial_source_coverage(self):
        seed(self.r)
        memories = [self.r.knowledge.document("r1"), self.r.knowledge.document("r2")]
        invalid = {"title": "Invalid", "summary": "Drops second source.", "findings": [{"label": "Partial",
            "proposition": "Only one input", "explanation": "Fixture", "provenance": "Fixture", "source_findings": ["r1#f1"]}]}
        self.assertRaisesRegex(ValueError, "every consumed input", gardener.validate, invalid, memories)

    def test_interrupted_gardener_repair_resolves_transcript_without_second_call(self):
        seed(self.r, own=2, child=0, leaf=0)
        p = multiprocessing.get_context("fork").Process(target=crash_gardener, args=(str(self.root),))
        p.start(); p.join(10); self.assertEqual(p.exitcode, 72)
        report = self.r.store.recovery_status()["operations"][0]
        self.assertEqual(report["assessment"], "safely_finishable")
        self.assertIn("interrupted_or_unknown", transcript(self.root, full=True))
        self.r.store.repair(report["id"], apply=True)
        self.assertEqual(self.r.step()["status"], "finished")
        self.assertFalse(self.llm.requests)
        self.assertIn('"action_committed": "S2"', transcript(self.root, full=True))
        self.assertEqual(self.state()["nodes"]["q1"]["unsynthesized_memory_count"], 1)
