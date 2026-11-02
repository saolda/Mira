"""Deterministic fictional evidence and prewritten decisions; no network or inference."""
import json

from .decisions import ScriptedLLM
from .format import dumps, loads
from .research import Research
from .search import FixtureSearch


def evidence(source_id="fixture-1"):
    return {"status": "ok", "results": [{"id": source_id, "url": "https://example.org/mira-heat-" + source_id,
        "title": "Fictional barrier measurements", "content_kind": "fixture", "truncated": False,
        "content": "Fictional data: sample A transferred 4 heat units; sample B transferred 8 under equal imposed conditions. No real experiment occurred."}]}


def finding(label, source_id="fixture-1"):
    return {"type": "claim", "text": "The fictional fixture reports " + label + ".",
            "qualification": "No real-world conclusion follows from this artificial fixture.",
            "source_ids": [source_id], "related_to": None}


class DemoLLM(ScriptedLLM):
    def __init__(self): super().__init__([])

    def complete(self, serialized_request):
        self.requests.append(serialized_request)
        content = loads(serialized_request)["messages"][-1]["content"]
        action = ("R1" if "AVAILABLE CONCEPTS\n" in content else
                  "R3" if "RETRIEVED RESEARCH\n" in content else
                  "R4" if "SCIENTIFIC EVIDENCE\n" in content else
                  "R5" if "ACCUMULATED RESEARCH\n" in content else
                  "S2" if "Identify scientific synthesis opportunities" in content else "S3")
        # Fixture-only inspection of explicitly labelled JSON values, not a
        # production prompt parser or substitute for real model evaluation.
        decoder = json.JSONDecoder()
        if action == "R1":
            plans = [["fictional heat barrier", "measurement uncertainty"], ["thermal resistance", "heat flux"],
                     ["thermal conductivity", "heat transfer"], ["boundary conditions", "thermal gradient"],
                     ["measurement precision", "temperature dependence"], ["thermal diffusivity", "heat capacity"]]
            count = getattr(self, '_plans', 0)
            value = {"new_concepts": [], "search_concepts": plans[count % len(plans)], "reason": "Prewritten fixture plan."}
            self._plans = count + 1
        elif action == "R3":
            supplied = decoder.raw_decode(content.split("RETRIEVED RESEARCH\n", 1)[1])[0]
            source_id = supplied["results"][0]["id"]
            value = {"summary": "Scoped summary of all extracted results and their limitations.", "results": [finding("A transfers 4 units", source_id), finding("B transfers 8 units", source_id)]}
        elif action == "R4":
            value = {"decision": "unresolved", "reason": "Scripted second research batch; the question remains relevant."}
        elif action == "R5":
            question = decoder.raw_decode(content.split("SELECTED QUESTION\n", 1)[1])[0]
            children = {"What can the fictional heat-barrier fixture tell us?":
                        ["How do fixture conditions matter?", "What uncertainties remain?"],
                        "How do fixture conditions matter?": ["What measurement assumptions apply?"]}.get(question, [])
            value = {"questions": children}
        elif action == "S2":
            units = decoder.raw_decode(content.split("SELECTED KNOWLEDGE UNITS\n",1)[1])[0]
            if getattr(self,'_planned',False):
                value={"disposition":"no_candidate","ideas":[],"reason":"No additional defensible fixture integration."}
            else:
                self._planned=True
                value={"disposition":"ideas","ideas":[{"category":"comparison",
                    "objective":"Compare the fictional measurements while retaining their uncertainty.",
                    "unit_ids":[u['id'] for u in units],"potential_new_understanding":"A scoped fixture comparison.",
                    "limitations":["Fictional data; no real-world inference."],"novelty":"Compare the measurements rather than repeat a single source."}],
                    "reason":"Prewritten fixture opportunity."}
        else:
            value={"disposition":"no_synthesis","reason":"The fictional repeated statements establish no defensible new scientific conclusion."}
        return dumps({"model": self.model, "choices": [{"finish_reason": "stop", "message": {"content": dumps(value)}}], "usage": None})


def demonstrate(root, *, max_cycles=50, trace=None, log_directory=None):
    llm = DemoLLM()
    r = Research(root, llm, {"fixture": FixtureSearch([evidence("fixture-" + str(i)) for i in range(1,9)])})
    if trace is not None:
        r.trace = trace
        trace.log.configure(llm.model, llm.settings)
    # Explicit fixture budget fits complete research prompts and forces synthesis
    # descent through all three levels. The runtime default remains configurable.
    r.initialize("What can the fictional heat-barrier fixture tell us?", ["fixture"], synthesis_interval=100,
                 context_budget=24000, output_reserve=2048, research_capacity_tokens=6000)
    outcome = r.run(max_cycles, log_directory=log_directory)
    return {"status": outcome["status"], "metrics": r.inspect(), "model_calls": len(llm.requests),
            "knowledge": r.knowledge.validate(), "root": str(r.store.root)}
