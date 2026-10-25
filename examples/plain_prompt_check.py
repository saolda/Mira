"""Real model calls, recorded in a new experiment without applying proposals.

By default evaluates four actions; --r1-only performs one focused R1 call.

Uses synthetic source material (not external research). No scripted model outputs,
service lifecycle changes or modifications to existing experiments.
"""
import argparse
import json
import uuid
from urllib.request import urlopen

from mira import gardener, research_tree as tree, r1, r3
from mira.clients import HTTPModel
from mira.decisions import validate
from mira.experiments import Experiments
from mira.format import Memory, Unit, base36, dumps, loads
from mira.interactions import now, transcript
from mira.research import Research


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:8090")
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--r1-only", action="store_true")
    parser.add_argument("--control-term", action="append", default=[])
    args = parser.parse_args()
    with urlopen(args.endpoint.rstrip("/") + "/v1/models", timeout=5) as response:
        model = json.load(response)["data"][0]["id"]
    catalog = Experiments()
    root = catalog.create(args.experiment)
    llm = HTTPModel(args.endpoint, model, max_tokens=256 if args.r1_only else 1600, timeout=90, no_thinking=True)
    research = Research(root, llm, {}, control_terms=args.control_term)
    research.initialize("What can these synthetic insulation observations establish, and what remains unknown?", ["fixture"], context_budget=24000, output_reserve=2048)
    evidence = {"status": "ok", "provider": "fixture", "query": "synthetic insulation test", "reference": "evaluation-only", "results": [
        {"id": "fixture-a", "url": "https://example.org/synthetic-a", "title": "Authored synthetic observation A", "content_kind": "fixture", "truncated": False,
         "content": "Synthetic fixture, not a real experiment: under the same imposed conditions, a bare sample transferred 8 heat units and an insulated sample transferred 4. No repeated measurements or uncertainty bounds were supplied."},
        {"id": "fixture-b", "url": "https://example.org/synthetic-b", "title": "Authored synthetic scope note B", "content_kind": "fixture", "truncated": False,
         "content": "Synthetic scope note: no material, geometry or temperature dependence was measured. These fixture values alone do not establish performance in other conditions."}]}
    # Seed two clearly labelled synthetic memories for S2, not model-produced data.
    with research.store.lock():
        token, memories, equations, ledger = research.store.read()
        state = loads(research.store._files()["research/state.json"])
        for title, proposition in [("Synthetic insulation observation", "The synthetic fixture reports transfer of 4 units with insulation versus 8 without."),
                                    ("Synthetic scope limitation", "The fixture supplies no uncertainty bounds or evidence for other conditions.")]:
            identity = "r" + base36(ledger["r"]); ledger["r"] += 1
            memory = Memory(identity, title, proposition, metadata={"kind": "research", "node_id": "q1", "source_memories": [], "synthesized_by": None, "created_order": len(memories)+1})
            memory.units.append(Unit(memory.allocate("f"), title, {"Kind": "claim", "Evidence status": "unverified", "Proposition": proposition,
                "Explanation": "Authored synthetic fixture only; not an empirical measurement.", "Provenance": "Manually authored evaluation input."}))
            memories.append(memory); state["nodes"]["q1"]["memory_ids"].append(identity)
        tree.refresh(state, memories)
        research.store.publish(memories, equations, ledger, token, files={"research/state.json": dumps(state)}, operation_type="evaluation_seed")
    outcomes = []
    for action in (("R1",) if args.r1_only else ("R1", "R3", "R4", "S2")):
        print("Calling " + action + " on " + model, flush=True)
        with research.store.lock():
            token, memories, equations, ledger = research.store.read()
            files = research.store._files()
            state = loads(files["research/state.json"])
            if action == "R1":
                context = r1.context(state, memories, files, "q1", research.control_terms)
            elif action == "R3":
                context = r3.context(state, "q1", evidence)
            elif action == "S2":
                context = gardener.context(state, memories, equations, "q1", memories)
            else:
                context, _ = research._context(state, memories, equations, files, "q1")
                if action == "R3": context["search_evidence"] = evidence
                if action == "R4":
                    context["next_database"] = None
                    context["node"]["keywords"] = ["insulation", "synthetic", "test"]
                    context["node"]["next_database_index"] = 1
                    context["search_history"] = [{"query": "insulation generic", "provider": "fixture", "status": "empty", "results": []}]
                    context["search_evidence"] = [{"status": "empty", "results": [], "query": "insulation generic"}, evidence]
            event = {"timestamp": now(), "run_id": state["run_id"], "action": action, "node_id": "q1", "question": context["question"],
                     "evaluation_only": True, "action_committed": None, "note": "Model proposal evaluated only; no research transition or model-generated memory applied."}
            value = None
            try:
                value = research._model(event, action, context, state)
                if action == "S2": gardener.validate(value, memories)
                else: validate(action, value, evidence if action == "R3" else None)
                if action == "R1": event["filtered_keywords"] = r1.filter_terms(value["keywords"], research.control_terms)
                accepted, error = True, None
            except Exception as exc:
                accepted, error = False, str(exc)
            event.update(status="committed" if accepted else "rejected", proposal=value, error=error)
            identity = event.get("interaction_id")
            if identity:
                research.trace.write(identity, "validation", {"timestamp": now(), "action": action, "accepted": accepted, "error": error})
            event_ref = "events/evaluation-" + uuid.uuid4().hex + ".json"
            research.store.publish(memories, equations, ledger, token, files={event_ref: dumps(event)}, operation_type="prompt_evaluation", context={"interaction_id": identity})
            if identity:
                research.trace.write(identity, "outcome", {"timestamp": now(), "status": event["status"], "action_committed": None,
                    "evaluation_only": True, "event_ref": event_ref, "error": error})
            outcomes.append({"action": action, "accepted": accepted, "interaction_id": identity, "error": error})
            print(dumps(outcomes[-1]), flush=True)
    for full in (False, True):
        catalog.export_transcript(args.experiment, transcript(root, full=full), full=full)
    report = {"experiment": args.experiment, "model": model, "endpoint": args.endpoint, "outcomes": outcomes,
              "limitation": "Bounded calls on authored synthetic evidence; structural validation is not semantic verification. Proposals were not applied."}
    (root / "prompt_evaluation.json").write_text(dumps(report))
    print(dumps(report), flush=True)


if __name__ == "__main__":
    main()
