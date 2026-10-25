"""Deterministic fictional evidence and prewritten decisions; no network or inference."""
import json

from .decisions import ScriptedLLM
from .format import dumps, loads
from .research import Research
from .search import FixtureSearch


def evidence():
    return {"status": "ok", "results": [{"id": "fixture-1", "url": "https://example.org/mira-heat-fixture",
        "title": "Fictional barrier measurements", "content_kind": "fixture", "truncated": False,
        "content": "Fictional data: sample A transferred 4 heat units; sample B transferred 8 under equal imposed conditions. No real experiment occurred."}]}


def finding(label):
    return {"type": "claim", "text": "The fictional fixture reports " + label + ".",
            "qualification": "No real-world conclusion follows from this artificial fixture.",
            "source_ids": ["fixture-1"], "related_to": None}


class DemoLLM(ScriptedLLM):
    def __init__(self): super().__init__([])

    def complete(self, serialized_request):
        self.requests.append(serialized_request)
        content = loads(serialized_request)["messages"][-1]["content"]
        action = "R1" if content.startswith("Generate concise, targeted search terms") else "R3" if content.startswith("Review the retrieved research") else content.split(":", 1)[0]
        # Fixture-only inspection of explicitly labelled JSON values, not a
        # production prompt parser or substitute for real model evaluation.
        decoder = json.JSONDecoder()
        identity = decoder.raw_decode(content.split("Selected node:\n", 1)[1])[0]["id"] if action not in {"R1", "R3"} else None
        if action == "R1": value = {"keywords": ["fictional", "heat", "barrier"]}
        elif action == "R3": value = {"results": [finding("A transfers 4 units"), finding("B transfers 8 units")]}
        elif action == "R4":
            supplied_node = decoder.raw_decode(content.split("Selected node:\n", 1)[1])[0]
            if len(supplied_node["memory_ids"]) < 2:
                return dumps({"model": self.model, "choices": [{"finish_reason": "stop", "message": {"content": dumps({
                    "decision": "retry", "keywords": ["fictional", "second", "measurement"], "children": [],
                    "rationale": "Scripted second batch to exercise one-memory-per-R3 synthesis inputs."})}}], "usage": None})
            children = {"q1": ["How do fixture conditions matter?", "What uncertainties remain?"],
                        "q2": ["What measurement assumptions apply?"]}.get(identity, [])
            value = {"decision": "exhaust_split" if children else "exhaust", "children": children,
                     "keywords": None, "rationale": "Prewritten demonstration branch; no model judgment occurred."}
        else:
            # Stable fixtures reference exactly the selected inputs; text is prewritten.
            value = {"title": "Fixture synthesis", "summary": "Synthetic comparison with uncertainty.",
                "findings": [{"label": "Comparison", "proposition": "The fictional values differ, with no claim of real-world validity.",
                    "explanation": "This scripted synthesis tests traceability rather than research quality.",
                    "provenance": "Prewritten demonstration; see every input finding.",
                    "source_findings": [m["id"] + "#f1" for m in decoder.raw_decode(content.split("Input memories:\n", 1)[1])[0]]}]}
        return dumps({"model": self.model, "choices": [{"finish_reason": "stop", "message": {"content": dumps(value)}}], "usage": None})


def demonstrate(root, *, max_cycles=50):
    llm = DemoLLM()
    r = Research(root, llm, {"fixture": FixtureSearch([evidence() for _ in range(8)])})
    # Explicit fixture budget fits complete research prompts and forces synthesis
    # descent through all three levels. The runtime default remains configurable.
    r.initialize("What can the fictional heat-barrier fixture tell us?", ["fixture"], synthesis_interval=100,
                 context_budget=12000, output_reserve=2048)
    outcome = r.run(max_cycles)
    return {"status": outcome["status"], "metrics": r.inspect(), "model_calls": len(llm.requests),
            "knowledge": r.knowledge.validate(), "root": str(r.store.root)}
