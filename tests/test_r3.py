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


class R3Tests(unittest.TestCase):
    def make(self, results):
        state=tree.initial("What does this fixture establish?", ["fixture"])
        memories, equations, ledger=[], [], {"r": 1, "s": 1}
        memory=r3.create_memory(state, memories, equations, ledger, "q1", results, research())
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
        self.assertIsNone(r3.create_memory(state,[],[],ledger,"q1",[],research()))
        self.assertEqual(ledger,{"r":1,"s":1})
        validate("R3",{"results":[]},research())

    def test_all_text_types_and_no_model_memory_fields(self):
        results=[result(t) for t in ("finding","observation","claim","inference","hypothesis")]
        memory, equations, _, _=self.make(results)
        self.assertEqual([u.fields["Kind"] for u in memory.units],[r["type"] for r in results])
        self.assertEqual([u.fields["Evidence status"] for u in memory.units],["unverified"]*5)
        with self.assertRaises(ValueError): validate("R3",{"memories":[],"no_finding_reason":"old"},research())
        bad=result();bad["memory_id"]="r99"
        with self.assertRaises(ValueError): validate("R3",{"results":[bad]},research())

    def test_mixed_order_stable_refs_and_deterministic_markdown(self):
        results=[result(),equation(),image(),result("hypothesis",0)]
        memory, equations, docs, _=self.make(results)
        self.assertEqual([u.anchor for u in memory.units],["f1","e1","i1","f2"])
        text=render(memory)
        self.assertEqual(text,render(memory))
        self.assertEqual(parse(text),memory)
        self.assertLess(text.index("[#f1]"),text.index("[#e1]"))
        self.assertLess(text.index("[#e1]"),text.index("[#i1]"))
        self.assertLess(text.index("[#i1]"),text.index("[#f2]"))
        self.assertIn("$$\nE = mc^2\n$$",text)
        self.assertIn("units: not supplied",text)
        self.assertIn("![Synthetic caption](<https://example.org/fig2.png>)",text)
        self.assertEqual([e.target for e in memory.relationships if e.type=="RELATED_TO"],["r1#f1"]*3)
        validate_corpus(docs,equations)
        self.assertEqual(self.make(results)[0],memory)

    def test_equation_json_roundtrip_units_and_optional_origin(self):
        eq=equation(None);eq["latex"]=r"E = \frac{mc^2}{1}"
        del eq["origin"]
        wire=dumps({"results":[eq]});self.assertIn(r"\\frac",wire)
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
            with self.assertRaises(ValueError):r3.validate({"results":[bad]},research())

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
            with self.subTest(bad=bad),self.assertRaises(ValueError):r3.validate({"results":[bad]},research())

    def test_reference_ranges_self_and_cycles(self):
        for ref in (-1,3,True,"0",0):
            with self.subTest(ref=ref),self.assertRaises(ValueError):r3.validate({"results":[result(related=ref)]},research())
        with self.assertRaises(ValueError):r3.validate({"results":[result(related=1),result(related=0)]},research())
        r3.validate({"results":[result(related=1),result()]},research())
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
            llm=ScriptedLLM([{"keywords":["physics"]},{"results":[result(),equation(),image()]}])
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

    def test_rejected_equation_batch_rolls_back_equations_and_ids(self):
        with tempfile.TemporaryDirectory() as root:
            bad=equation(None);bad["latex"]="x=y\n## Relationships"
            llm=ScriptedLLM([{"keywords":["physics"]},{"results":[bad]}])
            r=Research(root,llm,{"fixture":FixtureSearch([research()])})
            r.initialize("Physics?",["fixture"],context_budget=20000)
            r.step();r.step()
            before=Path(root,"research/state.json").read_text()
            event=r.step()
            self.assertEqual(event["status"],"rejected")
            self.assertEqual(Path(root,"research/state.json").read_text(),before)
            self.assertEqual(r.knowledge.validate()["documents"],0)
            self.assertEqual(r.knowledge.validate()["equations"],0)
            self.assertEqual(list(Path(root,"equations").glob("*.json")),[])

    def test_synthesis_can_reference_media_only_inputs(self):
        memory,eq,docs,state=self.make([equation(None),image(None,None)])
        second=deepcopy(memory);second.id="r2";second.units=[Unit("i1","Figure",{"Image":"Caption","Figure reference":"Fig 2","Provenance":"Fixture"})]
        second.relationships=[]
        value={"title":"Combined","summary":"Scoped integration","findings":[{"label":"Combined","proposition":"A scoped integration.","explanation":"No verification implied.","provenance":"Supplied media only.","source_findings":["r1#e1","r2#i1"]}]}
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
