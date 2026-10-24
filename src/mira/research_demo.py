"""Deterministic fictional evidence and prewritten decisions; no network or inference."""
from .decisions import ScriptedLLM
from .format import dumps, loads
from .research import Research
from .search import FixtureSearch


def evidence():
    return {"status": "ok", "results": [{"id": "fixture-1", "url": "https://example.org/mira-heat-fixture",
        "title": "Fictional barrier measurements", "content_kind": "fixture", "truncated": False,
        "content": "Fictional data: sample A transferred 4 heat units; sample B transferred 8 under equal imposed conditions. No real experiment occurred."}]}


def finding(label):
    return {"title": "Fixture " + label, "summary": "Synthetic result " + label,
            "findings": [{"label": label, "kind": "claim", "proposition": "The fictional fixture reports " + label + ".",
                "explanation": "No general physical conclusion follows from this artificial example.",
                "provenance": "Fictional fixture-1; not a real measurement.", "evidence_ids": ["fixture-1"]}]}


class DemoLLM(ScriptedLLM):
    def __init__(self): super().__init__([])

    def complete(self, serialized_request):
        self.requests.append(serialized_request)
        content = loads(loads(serialized_request)["messages"][-1]["content"])
        action, context = content["action"], content["context"]
        identity = context["node"]["id"]
        if action == "R1": value = {"keywords": ["fictional", "heat", "barrier"]}
        elif action == "R3": value = {"memories": [finding("A transfers 4 units"), finding("B transfers 8 units")], "no_finding_reason": None}
        elif action == "R4":
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
                    "source_findings": [m["id"] + "#f1" for m in context["input_memories"]]}]}
        return dumps({"model": self.model, "choices": [{"finish_reason": "stop", "message": {"content": dumps(value)}}], "usage": None})


def demonstrate(root, *, max_cycles=50):
    llm = DemoLLM()
    r = Research(root, llm, {"fixture": FixtureSearch([evidence() for _ in range(4)])})
    # Research finishes first so context descent demonstrates leaf-to-root synthesis.
    r.initialize("What can the fictional heat-barrier fixture tell us?", ["fixture"], synthesis_interval=100,
                 context_budget=8192, output_reserve=2048)
    outcome = r.run(max_cycles)
    return {"status": outcome["status"], "metrics": r.inspect(), "model_calls": len(llm.requests),
            "knowledge": r.knowledge.validate(), "root": str(r.store.root)}
