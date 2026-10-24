"""Deterministic synthesis candidate descent, complete-input budgeting and commit drafts."""
from dataclasses import asdict
from itertools import combinations

from . import research_tree as tree, decisions
from .format import Memory, Unit, Relationship, base36, render, require

SYNTHESIS_FINDING = {"label": "nonempty string", "proposition": "nonempty string", "explanation": "nonempty string",
                     "provenance": "nonempty string", "source_findings": ["complete input finding IDs, e.g. r1#f1"]}


def context(state, memories, equations, identity, inputs):
    n = state["nodes"][identity]
    equation_ids = {u.fields["Equation"] for m in inputs for u in m.units if u.kind == "equation"}
    return {"root_question": state["nodes"][state["root_id"]]["question"], "node": n, "question": n["question"],
            "ancestor_questions": [state["nodes"][i]["question"] for i in tree.ancestors(state, identity)],
            "input_memories": [{"id": m.id, "markdown": render(m)} for m in inputs],
            "equations": [asdict(e) for e in equations if e.id in equation_ids]}


def select(state, memories, equations, model, settings):
    candidates = state["synthesis_candidate_order"]
    info = {"candidates": [{"id": i, "score": state["nodes"][i]["synthesis_score"],
            "count": state["nodes"][i]["unsynthesized_memory_count"]} for i in candidates],
            "context_budget": state["context_budget"], "output_reserve": state["output_reserve"],
            "estimator": "UTF-8 request bytes (conservative token estimate)"}
    if not candidates: return None, [], None, info
    def estimate(identity, inputs):
        return len(decisions.request(model, settings, "S2", context(state, memories, equations, identity, inputs)).encode("utf-8")) + state["output_reserve"]
    identity = candidates[0]
    path = [identity]
    while True:
        inputs = tree.frontier(state, memories, identity)
        if estimate(identity, inputs) <= state["context_budget"]: break
        eligible = [c for c in state["nodes"][identity]["child_ids"] if c in candidates]
        if not eligible: break
        identity = min(eligible, key=lambda i: (-state["nodes"][i]["synthesis_score"], state["nodes"][i]["created_order"]))
        path.append(identity)
    inputs = tree.frontier(state, memories, identity)
    # Seed with the oldest fitting pair, then add remaining memories in creation
    # order. This avoids falsely blocking when one old large memory crowds out two small ones.
    chosen = []
    for pair in combinations(inputs, 2):
        if estimate(identity, pair) <= state["context_budget"]:
            chosen = list(pair); break
    if chosen:
        for memory in inputs:
            if memory not in chosen and estimate(identity, chosen + [memory]) <= state["context_budget"]:
                chosen.append(memory)
        chosen.sort(key=lambda m: m.metadata["created_order"])
    info.update(descent=path, selected_node=identity, available_inputs=[m.id for m in inputs],
                input_ids=[m.id for m in chosen], estimated_total=estimate(identity, chosen),
                blocked_input_ids=[m.id for m in inputs if m not in chosen])
    return identity, chosen, context(state, memories, equations, identity, chosen), info


def validate(value, inputs):
    decisions.fields(value, ["title", "summary", "findings"])
    decisions.text(value["title"]); decisions.text(value["summary"])
    require(isinstance(value["findings"], list) and value["findings"], "synthesis findings required")
    targets = {m.id + "#" + u.anchor for m in inputs for u in m.units if u.kind == "finding"}
    covered = set()
    for finding in value["findings"]:
        decisions.fields(finding, SYNTHESIS_FINDING)
        for key in ("label", "proposition", "explanation", "provenance"): decisions.text(finding[key])
        refs = finding["source_findings"]
        require(isinstance(refs, list) and refs and all(isinstance(r, str) and r in targets for r in refs), "invalid synthesis finding reference")
        require(len(refs) == len(set(refs)), "duplicate synthesis reference")
        covered.update(r.split("#")[0] for r in refs)
    require(covered == {m.id for m in inputs}, "every consumed input must contribute a referenced finding")


def apply(state, memories, ledger, identity, inputs, value):
    require(len(inputs) >= 2 and len({m.id for m in inputs}) == len(inputs) and
            all(m.metadata["synthesized_by"] is None for m in inputs), "invalid synthesis frontier")
    output_id = "s" + base36(ledger["s"]); ledger["s"] += 1
    output = Memory(output_id, value["title"], value["summary"], metadata={"node_id": identity,
        "kind": "synthesis", "source_memories": [m.id for m in inputs], "synthesized_by": None,
        "created_order": len(memories) + 1})
    for finding in value["findings"]:
        anchor = output.allocate("f")
        output.units.append(Unit(anchor, finding["label"], {"Kind": "synthesis", "Evidence status": "unverified",
            "Proposition": finding["proposition"], "Explanation": finding["explanation"], "Provenance": finding["provenance"]}))
        for target in finding["source_findings"]:
            output.relationships.append(Relationship(anchor, "SYNTHESIZES", target, "unverified"))
    for memory in inputs:
        memory.metadata["synthesized_by"] = output_id; memory.revision += 1
    memories.append(output); state["nodes"][identity]["memory_ids"].append(output_id)
    return output
