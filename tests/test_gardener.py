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


def seed(r, *, own=2, child=2, leaf=2, killed=False, living=()):
    with r.store.lock():
        token, memories, equations, ledger = r.store.read()
        state = loads(r.store._files()["research/state.json"])
        state["nodes"].update(q2=tree.node("q2", "Child?", "q1"), q3=tree.node("q3", "Leaf?", "q2"))
        state["nodes"]["q1"]["child_ids"] = ["q2"]; state["nodes"]["q2"]["child_ids"] = ["q3"]; state["next_node"] = 4
        for n in state["nodes"].values(): n["status"] = "answered"
        for identity in living: state["nodes"][identity]["status"] = "living"
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
    def test_zero_and_one_inputs_complete_without_llm(self):
        with tempfile.TemporaryDirectory() as root:
            llm=ScriptedLLM([]);r=Research(root,llm,{})
            r.initialize('Question?', ['fixture']);seed(r,own=1,child=0,leaf=0)
            self.assertEqual(r.step()['status'],'finished');self.assertFalse(llm.requests)
            self.assertEqual(r.inspect()['nodes']['q1']['unsynthesized_memory_count'],1)
    def test_killed_material_retained_and_originals_available(self):
        with tempfile.TemporaryDirectory() as root,tempfile.TemporaryDirectory() as logs:
            r=Research(root,DemoLLM(),{});r.initialize('Question?', ['fixture'],context_budget=200000)
            seed(r,killed=True);out=r.run(100,log_directory=logs)
            self.assertEqual(out['status'],'finished')
            s=r.inspect();self.assertEqual(s['nodes']['q3']['status'],'killed')
            self.assertTrue(s['nodes']['q1']['synthesis_complete'])
            self.assertEqual(s['nodes']['q1']['unsynthesized_memory_count'],4)
            self.assertEqual(r.knowledge.validate()['documents'],6)
            self.assertTrue(all(r.knowledge.document('r'+str(i)).metadata['synthesized_by'] is None for i in range(1,7)))
    def test_demo_records_three_stages_and_at_most_one_call_per_action(self):
        with tempfile.TemporaryDirectory() as root,tempfile.TemporaryDirectory() as logs:
            out=demonstrate(root,max_cycles=250,log_directory=logs)
            self.assertEqual(out['status'],'finished')
            records=read_records(root);self.assertNotIn('S1',{r['request']['action'] for r in records})
            self.assertTrue({'S2','S3'}<={r['request']['action'] for r in records})
            for r in records:
                if r['request']['action'] in {'S2','S3'}:
                    self.assertTrue(r['validation']['accepted']);self.assertGreaterEqual(len(r['request']['context']['knowledge_units']),2)
            self.assertIn('no_synthesis',transcript(root,full=True))
    def test_five_research_actions_then_deterministic_s1_without_aging(self):
        from test_synthesis import FixtureModel
        with tempfile.TemporaryDirectory() as root:
            r=Research(root,FixtureModel(),{});r.initialize('Question?', ['fixture'],context_budget=200000)
            seed(r,own=2,child=0,leaf=0,living=('q3',))
            with r.store.lock():
                token,docs,eqs,ledger=r.store.read();s=loads(r.store._files()['research/state.json']);s['research_cycles_since_synthesis']=5
                r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(s)})
            before=r.inspect()['nodes']['q3']['priority'];self.assertEqual(r.step()['action'],'S1');self.assertFalse(r.llm.requests)
            self.assertEqual(r.step()['action'],'S2');self.assertEqual(r.step()['action'],'S3')
            self.assertEqual(r.inspect()['nodes']['q3']['priority'],before)
    def test_legacy_synthesis_references_and_compact_format_remain_valid(self):
        from test_synthesis import synthesis
        with tempfile.TemporaryDirectory() as root:
            r=Research(root,ScriptedLLM([]),{});r.initialize('Question?', ['fixture'],context_budget=200000)
            seed(r,own=2,child=0,leaf=0)
            with r.store.lock():_,docs,_,_=r.store.read()
            self.assertEqual(gardener.validate(synthesis(),docs),['r1','r2'])
            bad=synthesis(('r1#f1','r99#f1'))
            with self.assertRaises(ValueError):gardener.validate(bad,docs)
