"""Collection synthesis with lossless structured summaries and atomic lineage."""
from dataclasses import asdict
from functools import lru_cache

from . import research_tree as tree, decisions
from .format import Memory, Unit, Relationship, base36, digest, dumps, loads, parse, render, require
from .budget import measure

SYNTHESIS_FINDING = {"label": "nonempty string", "proposition": "nonempty string", "explanation": "nonempty string",
                     "provenance": "nonempty string", "source_findings": ["complete input finding IDs, e.g. r1#f1"]}


@lru_cache(maxsize=256)
def _summary(markdown):
    """Extract every unit verbatim; omit allocators, repeated headings and bookkeeping.

    Cached by complete canonical content, so edits invalidate without migrations.
    No model call, semantic rewriting, excerpting or loss of qualifications occurs.
    """
    memory = parse(markdown)
    return dumps({"id": memory.id, "title": memory.title, "summary": memory.summary,
        "representation": "structured_summary", "memory_sha256": digest(markdown),
        "node_id": memory.metadata.get("node_id"),
        "units": [{"id": memory.id + "#" + u.anchor,
                   "text": "\n".join(key + ": " + value for key, value in u.fields.items())} for u in memory.units],
        "sources": [memory.metadata["source"]] if "source" in memory.metadata else memory.metadata.get("sources", []),
        "source_memories": memory.metadata.get("source_memories", []),
        "relationships": [r.payload() for r in memory.relationships]})


def context(state, memories, equations, identity, inputs, *, summarized=False):
    n = state["nodes"][identity]
    equation_ids = {u.fields["Equation"] for m in inputs for u in m.units if u.kind == "equation"}
    return {"root_question": state["nodes"][state["root_id"]]["question"],
            "node": {**{k: n[k] for k in ("id", "question", "status")},
                     "input_memory_ids": [m.id for m in inputs], "input_memory_count": len(inputs)}, "question": n["question"],
            "ancestor_questions": [state["nodes"][i]["question"] for i in tree.ancestors(state, identity)],
            "input_memories": [{**loads(_summary(render(m))), "question": state["nodes"][m.metadata["node_id"]]["question"]}
                if summarized else {"id": m.id, "markdown": render(m), "representation": "complete_memory",
                                    "memory_sha256": digest(render(m))} for m in inputs],
            "equations": [asdict(e) for e in equations if e.id in equation_ids]}


def select(state, memories, equations, model, settings, counter=None):
    candidates = state["synthesis_candidate_order"]
    info = {"candidates": [{"id": i, "score": state["nodes"][i]["synthesis_score"],
            "count": state["nodes"][i]["unsynthesized_memory_count"]} for i in candidates],
            "context_budget": state["context_budget"],
            "output_reserve": state.get("synthesis_output_reserve", state["output_reserve"]), "attempts": []}
    if not candidates: return None, [], None, info
    def usage(identity, inputs, summarized):
        supplied = context(state, memories, equations, identity, inputs, summarized=summarized)
        wire = decisions.request(model, settings, "S2", supplied)
        return measure(wire, info["output_reserve"], state["context_budget"], counter)
    # Try broadest eligible collections in existing priority order. Only condense
    # when the full collection does not fit; consider other candidates if needed.
    for identity in candidates:
        inputs = tree.frontier(state, memories, identity)
        measured = usage(identity, inputs, False)
        complete_total = measured["estimated_tokens"]
        summarized = measured["over_context_budget"]
        if summarized: measured = usage(identity, inputs, True)
        summary_total = measured["estimated_tokens"] if summarized else None
        chosen = list(inputs)
        if measured["over_context_budget"]:
            # Small summaries first maximize collection coverage, with stable ties.
            costs = {m.id: usage(identity, [m], True)["estimated_tokens"] for m in inputs}
            chosen = []
            for memory in sorted(inputs, key=lambda m: (costs[m.id], m.metadata["created_order"])):
                trial = usage(identity, chosen + [memory], True)
                if not trial["over_context_budget"]: chosen.append(memory)
            chosen.sort(key=lambda m: m.metadata["created_order"])
            measured = usage(identity, chosen, True)
            while chosen and measured["over_context_budget"]:
                chosen.pop()
                measured = usage(identity, chosen, True)
        attempt = {"selected_node": identity, "available_inputs": [m.id for m in inputs],
            "input_ids": [m.id for m in chosen], "representation": "structured_summary" if summarized else "complete_memory",
            "estimated_total": measured["estimated_tokens"], "usage": measured,
            "complete_collection_tokens": complete_total, "summary_collection_tokens": summary_total,
            "blocked_input_ids": [m.id for m in inputs if m not in chosen]}
        info["attempts"].append(attempt)
        if len(chosen) >= 2:
            info.update(attempt)
            return identity, chosen, context(state, memories, equations, identity, chosen, summarized=summarized), info
    info.update(info["attempts"][0])
    return candidates[0], [], None, info


def validate(value, inputs, supplied=None):
    decisions.fields(value, ["title", "summary", "findings"])
    decisions.text(value["title"]); decisions.text(value["summary"])
    require(isinstance(value["findings"], list) and value["findings"], "synthesis findings required")
    targets = {m.id + "#" + u.anchor for m in inputs for u in m.units if u.kind in {"finding", "question", "equation", "image"}}
    if supplied is not None:
        shown = {u["id"] for m in supplied if m.get("representation") == "structured_summary" for u in m["units"]}
        shown.update(m.id + "#" + u.anchor for m in inputs for u in m.units
                     if any(s["id"] == m.id and s.get("representation") == "complete_memory" for s in supplied))
        targets &= shown
    covered = set()
    for finding in value["findings"]:
        decisions.fields(finding, SYNTHESIS_FINDING)
        for key in ("label", "proposition", "explanation", "provenance"): decisions.text(finding[key])
        refs = finding["source_findings"]
        require(isinstance(refs, list) and refs and all(isinstance(r, str) and r in targets for r in refs), "invalid synthesis finding reference")
        require(len(refs) == len(set(refs)), "duplicate synthesis reference")
        covered.update(r.split("#")[0] for r in refs)
    require(covered == {m.id for m in inputs}, "every consumed input must contribute a referenced finding")


def apply(state, memories, ledger, identity, inputs, value, supplied=None):
    require(len(inputs) >= 2 and len({m.id for m in inputs}) == len(inputs) and
            all(m.metadata["synthesized_by"] is None for m in inputs), "invalid synthesis frontier")
    output_id = "s" + base36(ledger["s"]); ledger["s"] += 1
    output = Memory(output_id, value["title"], value["summary"], metadata={"node_id": identity,
        "kind": "synthesis", "source_memories": [m.id for m in inputs], "synthesized_by": None,
        "created_order": len(memories) + 1})
    if supplied is not None:
        output.metadata["synthesis_inputs"] = [{"memory_id": s["id"], "memory_sha256": s["memory_sha256"],
            "representation": s["representation"],
            "supplied_units": [m.id + "#" + u.anchor for m in inputs if m.id == s["id"] for u in m.units]}
            for s in supplied]
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
