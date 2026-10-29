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
        action = ("R1" if content.startswith("Generate concise, targeted search terms") else
                  "R3" if "RETRIEVED RESEARCH\n" in content else
                  "R4" if "PREVIOUS SEARCHES\n" in content else
                  "R5" if "ACCUMULATED RESEARCH\n" in content else
                  "S1" if "Eligible memory catalogue:\n" in content else "S2")
        # Fixture-only inspection of explicitly labelled JSON values, not a
        # production prompt parser or substitute for real model evaluation.
        decoder = json.JSONDecoder()
        if action == "R1": value = {"keywords": ["fictional", "heat", "barrier"]}
        elif action == "R3":
            supplied = decoder.raw_decode(content.split("RETRIEVED RESEARCH\n", 1)[1])[0]
            source_id = supplied["results"][0]["id"]
            value = {"summary": "Scoped summary of all extracted results and their limitations.", "results": [finding("A transfers 4 units", source_id), finding("B transfers 8 units", source_id)]}
        elif action == "R4":
            value = {"decision": "retry", "reason": "Scripted second research batch; the question remains relevant."}
        elif action == "R5":
            question = decoder.raw_decode(content.split("SELECTED QUESTION\n", 1)[1])[0]
            children = {"What can the fictional heat-barrier fixture tell us?":
                        ["How do fixture conditions matter?", "What uncertainties remain?"],
                        "How do fixture conditions matter?": ["What measurement assumptions apply?"]}.get(question, [])
            value = {"questions": children}
        elif action == "S1":
            catalogue = decoder.raw_decode(content.split("Eligible memory catalogue:\n", 1)[1])[0]
            groups = [[m for m in catalogue if m["node_id"] == identity]
                      for identity in dict.fromkeys(m["node_id"] for m in catalogue)]
            chosen = next((g for g in groups if len(g) >= 2), catalogue)
            value = {"disposition": "select", "memory_ids": [m["id"] for m in chosen],
                     "objective": "Compare the fictional barrier measurements and their uncertainty.",
                     "scores": {"R": 5, "C": 4, "X": 0, "N": 3, "E": 3},
                     "reason": "Prewritten comparison of related fixture evidence."}
        else:
            # Stable fixtures reference exactly the selected inputs; text is prewritten.
            value = {"disposition": "synthesis", "title": "Fixture synthesis", "summary": "Synthetic comparison with uncertainty.",
                "findings": [{"label": "Comparison", "proposition": "The fictional values differ, with no claim of real-world validity.",
                    "explanation": "This scripted synthesis tests traceability rather than research quality.",
                    "provenance": "Prewritten demonstration; see every input finding.",
                    "source_findings": [m["id"] + "#f1" for m in decoder.raw_decode(content.split("Input memories:\n", 1)[1])[0]]}]}
        return dumps({"model": self.model, "choices": [{"finish_reason": "stop", "message": {"content": dumps(value)}}], "usage": None})


def demonstrate(root, *, max_cycles=50):
    llm = DemoLLM()
    r = Research(root, llm, {"fixture": FixtureSearch([evidence("fixture-" + str(i)) for i in range(1,9)])})
    # Explicit fixture budget fits complete research prompts and forces synthesis
    # descent through all three levels. The runtime default remains configurable.
    r.initialize("What can the fictional heat-barrier fixture tell us?", ["fixture"], synthesis_interval=100,
                 context_budget=24000, output_reserve=2048, research_capacity_tokens=6000)
    outcome = r.run(max_cycles)
    return {"status": outcome["status"], "metrics": r.inspect(), "model_calls": len(llm.requests),
            "knowledge": r.knowledge.validate(), "root": str(r.store.root)}
