"""Ordered extraction, stable storage, malformed output and exact-input regressions."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from mira import r1, r3, gardener, research_tree as tree
from mira.decisions import ScriptedLLM, validate
from mira.experiments import Experiments
from mira.format import (Memory, Equation, Unit, dumps, loads, render, parse,
                         validate_corpus, equation_fields)
from mira.inspection import Inspector
from mira.interactions import read_records
from mira.research import Research
from mira.search import FixtureSearch
from mira import branching
import multiprocessing
import os


def research():
    return {"status": "ok", "reference": "research/results/batch.json", "provider": "fixture", "raw_api_response": "Raw feed retained separately",
        "results": [{"id": "source-a", "url": "https://example.org/paper", "title": "Authored measurement fixture", "authors": ["Fixture Author"],
          "published": "2020-01-01", "content_kind": "excerpt", "truncated": True,
          "content": "Synthetic fixture: E=mc^2. Figure 2 shows the data. https://example.org/fig2.png", "figures": [{"reference": "Figure 2", "caption": "Synthetic caption", "url": "https://example.org/fig2.png"}]}]}


def result(kind="finding", related=None):
    return {"type": kind, "text": "A scoped " + kind, "qualification": "Synthetic fixture, not empirical evidence.", "source_ids": ["source-a"], "related_to": related}


def equation(related=0, origin="source"):
    return {"type": "equation", "text": "Mass-energy expression", "latex": r"E = mc^2", "variables": [
        {"symbol": "E", "description": "Energy", "units": "joules"}, {"symbol": "m", "description": "Mass", "units": "kilograms"},
        {"symbol": "c", "description": "Speed of light", "units": None}], "source_ids": ["source-a"], "related_to": related, "origin": origin}


def image(related=0, url="https://example.org/fig2.png"):
    return {"type": "image", "text": "Synthetic caption", "url": url, "reference": "Figure 2", "source_ids": ["source-a"], "related_to": related}


def crash_extraction(root, stage, response=None):
    def fault(point):
        if point == stage: os._exit(75)
    response = response if response is not None else {"summary": "Two results with important limitations.",
                                                     "results": [result(), result("claim")]}
    Research(root, ScriptedLLM([response]), {}).step(fault=fault)


class CompactResearchTests(unittest.TestCase):
    def test_summary_contract_rejects_missing_invalid_summaries(self):
        for value in ({"results": [result()]}, {"summary": None, "results": []},
                      {"summary": "", "results": [result()]},
                      {"summary": "Valid", "results": [result()], "extra": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                r3.validate(value, research())
        evidence = research()
        evidence["results"].append({**evidence["results"][0], "id": "source-b"})
        with self.assertRaisesRegex(ValueError, "one source"):
            r3.validate({"summary": "Multiple sources", "results": [result()]}, evidence)

    def test_empty_results_discard_summary_without_changing_raw_proposal(self):
        proposal = {"summary": "The source contains no relevant scientific research.", "results": []}
        normalized = validate("R3", proposal, research())
        self.assertEqual(normalized, {"summary": "", "results": []})
        self.assertEqual(proposal["summary"], "The source contains no relevant scientific research.")
        ledger = {"r": 1, "s": 1}
        self.assertIsNone(r3.create_memory(tree.initial("Q?", ["fixture"]), [], [], ledger,
                                          "q1", [], research(), proposal["summary"]))
        self.assertEqual(ledger, {"r": 1, "s": 1})

    def test_compact_prose_preserves_literal_structure_and_omits_empty_fields(self):
        state = tree.initial("Q?", ["fixture"])
        text = {**result(), "text": "Scope: First line.\nOrigin: literal source prose.", "qualification": ""}
        memory = r3.create_memory(state, [], [], {"r": 1, "s": 1}, "q1", [text], research(),
                                  "A summary with <tags> and # reserved syntax.")
        markdown = render(memory)
        self.assertEqual(parse(markdown), memory)
        self.assertNotIn("Qualification:", markdown)
        self.assertNotIn("Evidence status:", markdown)
        self.assertNotIn("CITES", markdown)
        self.assertEqual(set(memory.units[0].fields), {"Kind", "Proposition"})

    def runner(self, root, responses, rows=None):
        llm = ScriptedLLM([{"keywords": ["physics"]}, *responses])
        evidence = research()
        if rows is not None: evidence["results"] = rows
        runner = Research(root, llm, {"fixture": FixtureSearch([evidence, evidence])})
        runner.initialize("What does physics establish?", ["fixture"], context_budget=24000,
                          synthesis_interval=100)
        for _ in range(2): self.assertEqual(runner.step()["status"], "committed")
        return runner, llm

    def test_summary_is_exact_model_text_covering_all_results_and_contexts(self):
        summary = "Measures energy, but also identifies unresolved calibration limits."
        question = {**result("question", 0), "text": "How reliable is calibration?", "origin": "derived"}
        with tempfile.TemporaryDirectory() as root:
            runner, llm = self.runner(root, [{"summary": summary, "results": [result(), question]}])
            self.assertEqual(runner.step()["status"], "committed")
            memory = runner.knowledge.document("r1")
            self.assertEqual(memory.summary, summary)
            self.assertNotEqual(memory.summary, memory.units[0].fields["Proposition"])
            self.assertEqual(len(llm.requests), 2)
            self.assertIn("summary must represent the extracted results as a whole", llm.requests[-1])
            self.assertIn("Normally use 40–80 words", llm.requests[-1])
            self.assertEqual(parse(render(memory)), memory)
            self.assertIn("Origin: derived", render(memory))
            state = loads(Path(root, "research/state.json").read_text())
            contexts = [branching.context(state, [memory], [], "q1")["research_results"]["memories"][0]["markdown"],
                        gardener.context(state, [memory], [], "q1", [memory])["input_memories"][0]["markdown"]]
            for context in contexts:
                self.assertEqual(context, render(memory))
                self.assertIn("Qualification:", context)
                self.assertNotIn("**Proposition:**", context)
            self.assertEqual(gardener.context(state, [memory], [], "q1", [memory], summarized=True)["input_memories"][0]["sources"],
                             [memory.metadata["source"]])

    def test_multiple_sources_separate_calls_memories_and_dedup_on_restart(self):
        rows = research()["results"]
        rows.append({**rows[0], "id": "source-b", "url": "https://example.org/second"})
        second = {**result("claim"), "source_ids": ["source-b"]}
        with tempfile.TemporaryDirectory() as root:
            runner, llm = self.runner(root, [{"summary": "First source.", "results": [result(), result("claim")]},
                                           {"summary": "Second source.", "results": [second]}], rows)
            self.assertEqual(runner.step()["memory_ids"], ["r1"])
            self.assertIsNotNone(loads(Path(root, "research/state.json").read_text())["nodes"]["q1"]["pending_results"])
            # Resume with the same pending evidence; the processed-source index is its cursor.
            resumed = Research(root, llm, runner.adapters)
            self.assertEqual(resumed.step()["memory_ids"], ["r2"])
            self.assertEqual(resumed.knowledge.validate()["documents"], 2)
            records = read_records(root)[1:]
            self.assertEqual([len(r["request"]["context"]["research"]["results"]) for r in records], [1, 1])
            self.assertEqual([resumed.knowledge.document(i).metadata["source"]["id"] for i in ("r1", "r2")], ["source-a", "source-b"])
            with resumed.store.lock():
                token, memories, equations, ledger = resumed.store.read()
                state = loads(resumed.store._files()["research/state.json"])
                state["nodes"]["q1"]["next_database_index"] = 0
                resumed.store.publish(memories, equations, ledger, token, files={"research/state.json": dumps(state)})
            event = resumed.step()
            self.assertEqual(event["duplicate_count"], 2)
            self.assertEqual(len(llm.requests), 3)
            self.assertEqual(resumed.knowledge.validate()["documents"], 2)

    def test_empty_source_does_not_drop_remaining_source_or_allocate_id(self):
        rows = research()["results"]
        rows.append({**rows[0], "id": "source-b", "url": "https://example.org/second"})
        with tempfile.TemporaryDirectory() as root:
            runner, _ = self.runner(root, [{"summary": "", "results": []},
                                          {"summary": "Useful second source.", "results": [{**result(), "source_ids": ["source-b"]}]}], rows)
            self.assertEqual(runner.step()["memory_ids"], [])
            self.assertEqual(runner.step()["memory_ids"], ["r1"])
            self.assertEqual(runner.knowledge.document("r1").metadata["source"]["id"], "source-b")

    def test_endurance_summary_mismatch_is_normalized_and_run_continues(self):
        rows = research()["results"]
        rows.append({**rows[0], "id": "source-b", "url": "https://example.org/second"})
        raw_summary = "This source defines AI agents but provides no useful scientific research results."
        with tempfile.TemporaryDirectory() as root:
            runner, llm = self.runner(root, [{"summary": raw_summary, "results": []},
                                            {"summary": "Useful second source.", "results": [{**result(), "source_ids": ["source-b"]}]},
                                            {"decision": "answered", "reason": "Fixture completed."}], rows)
            outcome = runner.run(3)
            self.assertEqual([e["action"] for e in outcome["actions"]], ["R3", "R3", "R4"])
            first = outcome["actions"][0]
            self.assertEqual(first["status"], "committed")
            self.assertEqual(first["normalization"], "discarded_summary_for_empty_results")
            self.assertEqual(first["memory_ids"], [])
            self.assertEqual(outcome["actions"][1]["memory_ids"], ["r1"])
            record = read_records(root)[1]
            self.assertIn(raw_summary, record["response"]["raw"])
            self.assertTrue(record["validation"]["accepted"])
            self.assertEqual(len(llm.requests), 4)

    def test_invalid_r3_output_logs_error_and_skips_only_failed_source(self):
        bad_source = {"summary": "Invalid reference.", "results": [{**result(), "source_ids": ["invented"]}]}
        malformed_content = dumps({"choices": [{"finish_reason": "stop", "message": {"content": "{not JSON"}}]})
        for bad in ("{not JSON", malformed_content, dumps({"choices": [None]}),
                    dumps({"choices": [{"finish_reason": "stop", "message": None}]}),
                    bad_source, {"memories": []},
                    {"summary": None, "results": []}):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as root:
                rows = research()["results"]
                rows.append({**rows[0], "id": "source-b", "url": "https://example.org/second"})
                runner, llm = self.runner(root, [bad, {"summary": "Second source.", "results": [{**result(), "source_ids": ["source-b"]}]},
                                                {"decision": "answered", "reason": "Fixture completed."}], rows)
                resumed = Research(root, llm, runner.adapters)
                outcome = resumed.run(3)
                self.assertEqual([e["action"] for e in outcome["actions"]], ["R3", "R3", "R4"])
                skipped = outcome["actions"][0]
                self.assertEqual(skipped["status"], "committed")
                self.assertEqual(skipped["reason"], "invalid_extraction_skipped")
                self.assertEqual(skipped["skipped_source_ids"], ["source-a"])
                self.assertTrue(skipped["error"])
                self.assertFalse(skipped["extraction_accepted"])
                self.assertEqual(skipped["memory_ids"], [])
                self.assertEqual(outcome["actions"][1]["memory_ids"], ["r1"])
                records = read_records(root)
                self.assertFalse(records[1]["validation"]["accepted"])
                self.assertEqual(records[1]["validation"]["error"], skipped["error"])
                self.assertEqual(records[1]["outcome"]["action_committed"], "R3")
                state = loads(Path(root, "research/state.json").read_text())
                self.assertEqual(len(state["source_index"]), 2)
                self.assertIsNone(state["nodes"]["q1"]["pending_results"])
                self.assertEqual(state["research_cycles"], 5)
                self.assertEqual(resumed.knowledge.validate()["documents"], 1)
                self.assertEqual(len(llm.requests), 4)

    def test_skipped_source_advances_to_next_database_without_retry(self):
        with tempfile.TemporaryDirectory() as root:
            llm = ScriptedLLM([{"keywords": ["physics"]}, "{not JSON"])
            runner = Research(root, llm, {"first": FixtureSearch([research()]),
                                          "second": FixtureSearch([{"status": "empty", "results": []}])})
            runner.initialize("Physics?", ["first", "second"], context_budget=24000)
            outcome = runner.run(4)
            self.assertEqual([e["action"] for e in outcome["actions"]], ["R1", "R2", "R3", "R2"])
            self.assertEqual(outcome["actions"][-1]["provider"], "second")
            self.assertEqual(len(llm.requests), 2)

    def test_failed_source_is_not_extracted_again_after_retrieval_and_restart(self):
        with tempfile.TemporaryDirectory() as root:
            runner, llm = self.runner(root, ["{not JSON"])
            self.assertEqual(runner.step()["skipped_source_ids"], ["source-a"])
            with runner.store.lock():
                token, docs, equations, ledger = runner.store.read()
                state = loads(runner.store._files()["research/state.json"])
                state["nodes"]["q1"]["next_database_index"] = 0
                runner.store.publish(docs, equations, ledger, token, files={"research/state.json": dumps(state)})
            event = Research(root, llm, runner.adapters).step()
            self.assertEqual(event["action"], "R2")
            self.assertEqual(event["duplicate_count"], 1)
            self.assertEqual(len(llm.requests), 2)

    def test_r3_context_and_transport_errors_keep_source_pending(self):
        for blocked in (True, False):
            with self.subTest(blocked=blocked), tempfile.TemporaryDirectory() as root:
                runner, llm = self.runner(root, [RuntimeError("temporary transport failure")])
                pending = loads(Path(root, "research/state.json").read_text())["nodes"]["q1"]["pending_results"]
                if blocked:
                    llm.count_tokens = lambda _: {"prompt_tokens": 24000}
                event = runner.step()
                self.assertEqual(event["status"], "rejected")
                state = loads(Path(root, "research/state.json").read_text())
                self.assertEqual(state["nodes"]["q1"]["pending_results"], pending)
                self.assertEqual(state["source_index"], {})
                self.assertNotIn("skipped_source_ids", event)
                self.assertEqual(len(llm.requests), 1 if blocked else 2)

    def test_inherited_provenance_retrieval_graph_synthesis_and_index_rebuild(self):
        question = {**result("question", 0), "origin": "derived"}
        with tempfile.TemporaryDirectory() as root:
            runner, _ = self.runner(root, [{"summary": "Finding and derived objects.", "results": [result(), question, equation(0, "derived")]}])
            self.assertEqual(runner.step()["status"], "committed")
            k = runner.knowledge
            memory = k.document("r1")
            self.assertFalse(any(e.type == "CITES" for e in memory.relationships))
            self.assertNotIn("authors", memory.metadata["source"])
            for ref in ("r1#f1", "r1#q1", "r1#e1"):
                self.assertEqual(k.retrieve(ref)["provenance"][0]["source"], memory.metadata["source"])
                self.assertEqual(k.relationships(ref, type="CITES")[0]["target"], memory.metadata["source"]["url"])
            self.assertEqual(k.provenance("r1#q1")[0]["origin"], "derived")
            self.assertEqual(k.provenance("e_r1_1")[0]["origin"], "derived")
            with runner.store.lock():
                token, docs, equations, ledger = runner.store.read()
                state = loads(runner.store._files()["research/state.json"])
                other = {**research(), "results": [{**research()["results"][0], "id": "source-b", "url": "https://example.org/second"}]}
                second = r3.create_memory(state, docs, equations, ledger, "q1", [{**result(), "source_ids": ["source-b"]}], other, "Second source.")
                value = {"title": "Integration", "summary": "Qualified integration.", "findings": [{
                    "label": "Integration", "proposition": "A scoped integration.", "explanation": "Limitations remain.",
                    "provenance": "Model reasoning.", "source_findings": ["r1#q1", "r2#f1"]}]}
                gardener.apply(state, docs, ledger, "q1", [docs[0], second], value)
                tree.refresh(state, docs)
                runner.store.publish(docs, equations, ledger, token, files={"research/state.json": dumps(state)})
            self.assertIn(k.provenance("r1#q1")[0], k.provenance("s1#f1"))
            k.rebuild()
            k.directory.path.unlink()
            self.assertTrue(k.search("scoped"))
            self.assertEqual(len(k.relationships(memory.metadata["source"]["url"], direction="incoming", type="CITES")), 3)
            self.assertEqual(k.directory.integrity()["integrity"], "ok")

    def test_legacy_memory_citations_are_still_resolvable(self):
        from mira.api import Knowledge
        with tempfile.TemporaryDirectory() as root:
            k = Knowledge(root)
            m = k.create_memory("Legacy", "Legacy memory.")
            k.add_finding(m.id, "Old", "Old claim.", "Scoped.", "Explicit citation.")
            k.add_relationship(m.id, "f1", "CITES", "https://example.org/legacy", status="unverified")
            self.assertEqual(parse(k.retrieve(m.id)), k.document(m.id))
            self.assertEqual(k.provenance("r1#f1")[0]["source"]["url"], "https://example.org/legacy")

    def test_interrupted_source_creation_recovers_memory_summary_and_cursor_together(self):
        for stage in ("prepared", "replaced:memories/r1.md", "replaced:research/state.json", "before_commit"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as root:
                rows = research()["results"]
                rows.append({**rows[0], "id": "source-b", "url": "https://example.org/second"})
                runner, _ = self.runner(root, [], rows)
                process = multiprocessing.get_context("fork").Process(target=crash_extraction, args=(root, stage))
                process.start(); process.join(10)
                self.assertEqual(process.exitcode, 75)
                operation = runner.store.recovery_status()["operations"][0]
                runner.store.repair(operation["id"], apply=True)
                runner.store.repair(operation["id"], apply=True)
                self.assertEqual(runner.knowledge.document("r1").summary, "Two results with important limitations.")
                runner.llm = ScriptedLLM([{"summary": "Second source.", "results": [{**result(), "source_ids": ["source-b"]}]}])
                self.assertEqual(runner.step()["memory_ids"], ["r2"])
                self.assertEqual(len(runner.llm.requests), 1)
                self.assertEqual(runner.knowledge.validate()["documents"], 2)

    def test_recovered_empty_or_skipped_source_is_not_retried(self):
        for response in ({"summary": "No useful results.", "results": []}, "{not JSON"):
            for stage in ("prepared", "replaced:research/state.json"):
                with self.subTest(response=response, stage=stage), tempfile.TemporaryDirectory() as root:
                    rows = research()["results"]
                    rows.append({**rows[0], "id": "source-b", "url": "https://example.org/second"})
                    runner, _ = self.runner(root, [], rows)
                    process = multiprocessing.get_context("fork").Process(target=crash_extraction, args=(root, stage, response))
                    process.start(); process.join(10)
                    self.assertEqual(process.exitcode, 75)
                    operation = runner.store.recovery_status()["operations"][0]
                    runner.store.repair(operation["id"], apply=True)
                    runner.store.repair(operation["id"], apply=True)
                    self.assertEqual(runner.knowledge.validate()["documents"], 0)
                    state = loads(Path(root, "research/state.json").read_text())
                    self.assertEqual(len(state["source_index"]), 1)
                    runner.llm = ScriptedLLM([{"summary": "Second source.", "results": [{**result(), "source_ids": ["source-b"]}]}])
                    self.assertEqual(runner.step()["memory_ids"], ["r1"])
                    self.assertEqual(len(runner.llm.requests), 1)


class R3Tests(unittest.TestCase):
    def make(self, results):
        state=tree.initial("What does this fixture establish?", ["fixture"])
        memories, equations, ledger=[], [], {"r": 1, "s": 1}
        memory=r3.create_memory(state, memories, equations, ledger, "q1", results, research(), summary="Scoped summary of all extracted results and their limitations.")
        return memory, equations, memories, state

    def test_context_exact_three_fields_and_research_metadata(self):
        state=tree.initial(" Root question? ", ["fixture"])
        state["nodes"]["q2"]=tree.node("q2", "Root   question?", "q1")
        state["nodes"]["q3"]=tree.node("q3", "Selected question?", "q2")
        data=r3.context(state,"q3",research())
        self.assertEqual(set(data), {"question","question_context","research"})
        self.assertEqual(data["question_context"],[" Root question? "])
        row=data["research"]["results"][0]
        for key in ("id","title","authors","published","url","content","content_kind","truncated","figures"):
            self.assertEqual(row[key],research()["results"][0][key])
        self.assertEqual(set(data["research"]), {"status", "results"})
        self.assertEqual(r3.context(state,"q1",research())["question_context"],[])

    def test_empty_results_no_memory_or_identity_allocation(self):
        state=tree.initial("Q?",["fixture"]); ledger={"r":1,"s":1}
        self.assertIsNone(r3.create_memory(state,[],[],ledger,"q1",[],research(), summary=""))
        self.assertEqual(ledger,{"r":1,"s":1})
        validate("R3",{"summary": "", "results":[]},research())

    def test_all_text_types_and_no_model_memory_fields(self):
        results=[result(t) for t in ("finding","observation","claim","inference","hypothesis")]
        memory, equations, _, _=self.make(results)
        self.assertEqual([u.fields["Kind"] for u in memory.units],[r["type"] for r in results])
        self.assertTrue(all("Evidence status" not in u.fields for u in memory.units))
        with self.assertRaises(ValueError): validate("R3",{"memories":[],"no_finding_reason":"old"},research())
        bad=result();bad["memory_id"]="r99"
        with self.assertRaises(ValueError): validate("R3",{"summary": "Scoped summary of all extracted results and their limitations.", "results":[bad]},research())

    def test_mixed_order_stable_refs_and_deterministic_markdown(self):
        results=[result(),equation(),image(),result("hypothesis",0)]
        memory, equations, docs, _=self.make(results)
        self.assertEqual([u.anchor for u in memory.units],["f1","e1","i1","f2"])
        text=render(memory)
        self.assertEqual(text,render(memory))
        self.assertEqual(parse(text),memory)
        self.assertLess(text.index("### #f1 |"),text.index("### #e1 |"))
        self.assertLess(text.index("### #e1 |"),text.index("### #i1 |"))
        self.assertLess(text.index("### #i1 |"),text.index("### #f2 |"))
        self.assertIn("$$\nE = mc^2\n$$",text)
        self.assertIn("units: not supplied",text)
        self.assertIn("![Synthetic caption](<https://example.org/fig2.png>)",text)
        self.assertEqual([e.target for e in memory.relationships if e.type=="RELATED_TO"],["r1#f1"]*3)
        validate_corpus(docs,equations)
        self.assertEqual(self.make(results)[0],memory)

    def test_equation_json_roundtrip_units_and_optional_origin(self):
        eq=equation(None);eq["latex"]=r"E = \frac{mc^2}{1}"
        del eq["origin"]
        wire=dumps({"summary": "Scoped summary of all extracted results and their limitations.", "results":[eq]});self.assertIn(r"\\frac",wire)
        memory,equations,docs,_=self.make(loads(wire)["results"])
        stored=Equation(**loads(dumps(asdict(equations[0]))))
        validate_corpus(docs,[stored])
        self.assertEqual(stored.expression,eq["latex"])
        self.assertNotIn("c",stored.units)
        self.assertIn("origin: unspecified",stored.provenance)
        derived=self.make([equation(None,"derived")])[1][0]
        self.assertIn("model-derived, not asserted to appear in source",derived.provenance)
        for change in (lambda e:e["variables"][0].update(description=""),lambda e:e["variables"][0].update(units=4),lambda e:e.update(latex="\f"),lambda e:e.update(variables=[])):
            bad=equation(None);change(bad)
            with self.assertRaises(ValueError):r3.validate({"summary": "Scoped summary of all extracted results and their limitations.", "results":[bad]},research())

    def test_image_without_url_retains_reference_and_description(self):
        memory,_,_,_=self.make([image(None,None)])
        text=render(memory)
        self.assertIn("Figure 2",text);self.assertIn("Synthetic caption",text)
        self.assertNotIn("![",text)

    def test_source_and_url_validation(self):
        cases=[]
        bad=result();bad["source_ids"]=["invented"];cases.append(bad)
        bad=result();bad["source_ids"]=[];cases.append(bad)
        bad=image(None);bad["url"]="https://example.org/fig2.png/invented";cases.append(bad)
        bad=image(None);bad["url"]="https://invented.org/figure";cases.append(bad)
        bad=image(None,None);bad["reference"]=None;cases.append(bad)
        bad=image(None,None);bad["reference"]="Figure 999 invented";cases.append(bad)
        for bad in cases:
            with self.subTest(bad=bad),self.assertRaises(ValueError):r3.validate({"summary": "Scoped summary of all extracted results and their limitations.", "results":[bad]},research())

    def test_reference_ranges_self_and_cycles(self):
        for ref in (-1,3,True,"0",0):
            with self.subTest(ref=ref),self.assertRaises(ValueError):r3.validate({"summary": "Scoped summary of all extracted results and their limitations.", "results":[result(related=ref)]},research())
        with self.assertRaises(ValueError):r3.validate({"summary": "Scoped summary of all extracted results and their limitations.", "results":[result(related=1),result(related=0)]},research())
        r3.validate({"summary": "Scoped summary of all extracted results and their limitations.", "results":[result(related=1),result()]},research())
        memory,_,_,_=self.make([result(related=1),result()])
        self.assertEqual(memory.relationships[-1].target,"r1#f2")

    def test_equation_display_cannot_drift_from_json(self):
        memory,eq,docs,_=self.make([equation(None)])
        memory.units[0].fields["Expression"]="$$\nx=y\n$$"
        with self.assertRaisesRegex(ValueError,"presentation differs"):validate_corpus(docs,eq)

    def test_new_images_can_be_appended_to_existing_allocator(self):
        from mira import Knowledge
        with tempfile.TemporaryDirectory() as directory:
            k=Knowledge(directory);m=k.create_memory("Existing","Old allocator.")
            draft=k.document(m.id)
            draft.units.append(Unit(draft.allocate("i"),"Figure",{"Image":"Description","Figure reference":"Fig 1","Provenance":"Fixture"}))
            k.save_memory(draft,expected_revision=m.revision)
            self.assertEqual(k.retrieve("r1#i1")["anchor"],"i1")

    def test_live_pipeline_exact_prompt_and_atomic_equation_image_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog=Experiments(directory);root=catalog.create("ordered-r3")
            llm=ScriptedLLM([{"keywords":["physics"]},{"summary": "Scoped summary of all extracted results and their limitations.", "results":[result(),equation(),image()]}])
            r=Research(root,llm,{"fixture":FixtureSearch([research()])})
            r.initialize("What does the physics research show?",["fixture"],context_budget=20000)
            for _ in range(3):self.assertEqual(r.step()["status"],"committed")
            self.assertEqual(r.knowledge.validate()["documents"],1)
            self.assertEqual(r.knowledge.validate()["equations"],1)
            self.assertEqual([u.kind for u in r.knowledge.document("r1").units],["finding","equation","image"])
            self.assertEqual(r.knowledge.directory.integrity()["integrity"],"ok")
            viewed=Inspector(directory).decision("ordered-r3",read_records(root)[-1]["id"])
            self.assertEqual({s["name"] for s in viewed["prompt_slots"]},{"question","question_context","research"})
            self.assertTrue(viewed["template_verification"]["matches_recorded_request"])
            self.assertEqual(viewed["plain_text_prompt"],loads(llm.requests[-1])["messages"][0]["content"])
            self.assertEqual(len(viewed["generated_memories"]),1)
            self.assertEqual(viewed["inputs"]["search_evidence"],viewed["structured_context"]["research"])
            self.assertEqual(viewed["inputs"]["question"],"What does the physics research show?")

    def test_skipped_equation_batch_rolls_back_equations_and_ids(self):
        with tempfile.TemporaryDirectory() as root:
            bad=equation(None);bad["latex"]="x=y\n## Relationships"
            llm=ScriptedLLM([{"keywords":["physics"]},{"summary": "Scoped summary of all extracted results and their limitations.", "results":[bad]}])
            r=Research(root,llm,{"fixture":FixtureSearch([research()])})
            r.initialize("Physics?",["fixture"],context_budget=20000)
            r.step();r.step()
            before=Path(root,"identity.json").read_text()
            event=r.step()
            self.assertEqual(event["status"],"committed")
            self.assertEqual(event["skipped_source_ids"],["source-a"])
            self.assertEqual(Path(root,"identity.json").read_text(),before)
            self.assertIsNone(loads(Path(root,"research/state.json").read_text())["nodes"]["q1"]["pending_results"])
            self.assertEqual(r.knowledge.validate()["documents"],0)
            self.assertEqual(r.knowledge.validate()["equations"],0)
            self.assertEqual(list(Path(root,"equations").glob("*.json")),[])

    def test_synthesis_can_reference_media_only_inputs(self):
        memory,eq,docs,state=self.make([equation(None),image(None,None)])
        second=deepcopy(memory);second.id="r2";second.units=[Unit("i1","Figure",{"Image":"Caption","Figure reference":"Fig 2","Provenance":"Fixture"})]
        second.relationships=[];second.metadata.pop("source")
        value={"disposition":"synthesis","title":"Combined","summary":"Scoped integration","findings":[{"label":"Combined","proposition":"A scoped integration.","explanation":"No verification implied.","provenance":"Supplied media only.","source_findings":["r1#e1","r2#i1"]}]}
        gardener.validate(value,[memory,second])
        second.metadata.update(created_order=2)
        state["nodes"]["q1"]["memory_ids"].append("r2")
        ledger={"r":3,"s":1};docs.append(second)
        gardener.apply(state,docs,ledger,"q1",[memory,second],value)
        validate_corpus(docs,eq)

    def test_historical_r3_memory_proposals_remain_inspectable(self):
        old=loads((Path(__file__).parent / 'fixtures/plain_text_prompt_check.json').read_text())
        call=next(c for c in old['calls'] if c['action']=='R3')
        with tempfile.TemporaryDirectory() as directory:
            catalog=Experiments(directory);root=catalog.create('old-r3')
            path=root/'interactions/00000001-old';path.mkdir(parents=True)
            (path/'request.json').write_text(dumps(call['request']))
            (path/'response.json').write_text(dumps(call['response']))
            viewed=Inspector(directory).decision('old-r3',path.name)
            self.assertEqual(viewed['serialized_request'],call['request']['serialized_request'])
            self.assertEqual(viewed['raw_response'],call['response']['raw'])
            self.assertTrue(viewed['template_verification']['matches_recorded_request'])


class R1HeadingControlTests(unittest.TestCase):
    def test_fixed_list_case_whole_word_and_useful_component_cleanup(self):
        self.assertEqual(r1.controls([]),r1.CONTROL_TERMS)
        self.assertEqual(r1.filter_terms(["SUMMARY heat Evidence transfer", "evidential findings", "metadata", "explanations"],r1.controls([])),["heat transfer","evidential","explanations"])
        with self.assertRaises(ValueError):r1.filter_terms(["metadata", "TITLE"],r1.controls([]))
        self.assertEqual(r1.filter_terms(["heat", "transfer"],r1.controls([])),["heat","transfer"])

    def test_pipeline_records_filter_and_uses_clean_query(self):
        with tempfile.TemporaryDirectory() as root:
            llm=ScriptedLLM([{"keywords":["SUMMARY dropout", "evidence", "metadata uncertainty"]}])
            search=FixtureSearch([{"status":"empty","results":[]}])
            runner=Research(root,llm,{"fixture":search})
            runner.initialize("What is dropout uncertainty?",["fixture"])
            event=runner.step()
            self.assertEqual(event['keyword_filter'],{'original':['SUMMARY dropout','evidence','metadata uncertainty'],'accepted':['dropout','uncertainty']})
            self.assertEqual(event['status'],'committed')
            runner.step()
            self.assertEqual(search.queries,['dropout uncertainty'])
            self.assertIn('SUMMARY dropout',read_records(root)[0]['response']['raw'])

    def test_previous_terms_do_not_become_controls(self):
        state=tree.initial("Heat transfer?",["fixture"])
        files={"events/a.json":dumps({"node_id":"q1","question":"Heat transfer?","status":"committed","action_committed":"R1","tree":{"q1":{"keywords":["heat","heat"]}}})}
        ctx=r1.context(state,[],files,"q1")
        self.assertEqual(ctx['previous_search_terms'],['heat'])
        self.assertNotIn('heat',ctx['control_terms'])
