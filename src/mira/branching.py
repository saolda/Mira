"""Full direct-research context, deterministic capacity assessment and R5 drafts."""
from copy import deepcopy
from dataclasses import asdict

from . import decisions, research_tree as tree
from .format import digest, render, require
from .r1 import question_context
from .budget import measure


def context(state, memories, equations, identity):
    research = []
    for memory in sorted(memories, key=lambda m: m.metadata["created_order"]):
        if memory.metadata.get("node_id") == identity and memory.metadata.get("kind") == "research":
            # Synthesis consumption must not change the size/content of direct research.
            memory = deepcopy(memory)
            memory.metadata["synthesized_by"] = None
            memory.revision = 1
            research.append(memory)
    equation_ids = {u.fields["Equation"] for m in research for u in m.units if u.kind == "equation"}
    return {"max_children": state["max_children"], "question": state["nodes"][identity]["question"],
            "question_context": question_context(state, identity),
            "research_results": {"memories": [{"id": m.id, "markdown": render(m)} for m in research],
                                 "equations": [asdict(e) for e in equations if e.id in equation_ids]}}


def assess(state, memories, equations, model, settings, counter=None):
    """Assess exactly the rendered R5 payload; preserve overshoots for inspection."""
    changes = []
    for identity, n in state["nodes"].items():
        if n["status"] not in {"living", "exhausted"}: continue
        supplied = context(state, memories, equations, identity)
        serialized, template = decisions.prepared_request(model, settings, "R5", supplied)
        usage = measure(serialized, state["output_reserve"], state["context_budget"], counter)
        assessment = {**usage, "threshold": min(state["research_capacity_tokens"], usage["context_budget"]),
            "memory_ids": [m["id"] for m in supplied["research_results"]["memories"]],
            "request_sha256": digest(serialized), "template_sha256": template["files"][0]["sha256"],
            "model": model}
        n["research_capacity"] = assessment
        if n["status"] == "living" and n["pending_results"] is None and assessment["memory_ids"] and usage["estimated_tokens"] >= assessment["threshold"]:
            n["status"] = "exhausted"
            changes.append({"node_id": identity, "reason": "research_capacity_reached", **assessment})
    tree.refresh(state, memories)
    return changes


def due(state):
    return bool(state["ripeness_order"]) and (not state["living_priority_order"] or
        state["research_cycles_since_branching"] >= state["branching_interval"])


def apply(state, identity, value, event_id):
    n = state["nodes"][identity]
    require(n["status"] == "exhausted" and n["split_attempt"] is None, "R5 requires an unsplit exhausted node")
    seen = {" ".join(other["question"].split()).casefold() for other in state["nodes"].values()}
    accepted, duplicates = [], []
    for question in value["questions"]:
        normalized = " ".join(question.split()).casefold()
        if normalized in seen:
            duplicates.append(question)
            continue
        seen.add(normalized)
        accepted.append(question.strip())
    require(len(accepted) <= state["max_children"], "R5 exceeds configured child limit")
    for question in accepted:
        child_id = "q" + str(state["next_node"])
        state["next_node"] += 1
        state["nodes"][child_id] = tree.node(child_id, question, identity)
        n["child_ids"].append(child_id)
    n["status"] = "split"
    n["split_attempt"] = {"event_id": event_id, "questions": value["questions"],
                          "accepted": accepted, "duplicates": duplicates, "empty": not accepted}
    state["branching_cycles"] += 1
    state["research_cycles_since_branching"] = 0
    return n["split_attempt"]
