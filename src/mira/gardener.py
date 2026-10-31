"""Collection synthesis with lossless structured summaries and atomic lineage."""
from dataclasses import asdict
from collections import Counter
from functools import lru_cache

from . import research_tree as tree, decisions, questions
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


def context(state, memories, equations, identity, inputs, *, summarized=False, objective=""):
    n = state["nodes"][identity]
    equation_ids = {u.fields["Equation"] for m in inputs for u in m.units if u.kind == "equation"}
    return {"root_question": state["nodes"][state["root_id"]]["question"],
            **questions.context(state, "S2", identity),
            "node": {**{k: n[k] for k in ("id", "question", "status")},
                     "input_memory_ids": [m.id for m in inputs], "input_memory_count": len(inputs)}, "question": n["question"],
            "ancestor_questions": [state["nodes"][i]["question"] for i in tree.ancestors(state, identity)],
            "input_memories": [{**loads(_summary(render(m))), "question": state["nodes"][m.metadata["node_id"]]["question"]}
                if summarized else {"id": m.id, "markdown": render(m), "representation": "complete_memory",
                                    "memory_sha256": digest(render(m))} for m in inputs],
            "equations": [asdict(e) for e in equations if e.id in equation_ids], "objective": objective}


def owner(state, inputs):
    """Assign cross-branch synthesis to the deepest common ancestor."""
    paths = [tree.ancestors(state, m.metadata["node_id"]) for m in inputs]
    common = [i for i in paths[0] if all(i in path for path in paths)]
    return common[-1]


def selection_context(state, memories, equations, model, settings, counter=None):
    inputs = tree.frontier(state, memories, state["root_id"])
    reserve = state.get("synthesis_output_reserve", state["output_reserve"])
    catalogue = []
    for m in inputs:
        costs = {}
        for summarized in (False, True):
            supplied = context(state, memories, equations, m.metadata["node_id"], [m], summarized=summarized)
            usage = measure(decisions.request(model, settings, "S2", supplied), reserve, state["context_budget"], counter)
            costs["structured_summary" if summarized else "complete_memory"] = usage["estimated_tokens"]
        catalogue.append({"id": m.id, "kind": m.metadata["kind"], "content_hash": digest(render(m)), "node_id": m.metadata["node_id"],
            "question": state["nodes"][m.metadata["node_id"]]["question"],
            "ancestor_questions": [state["nodes"][i]["question"] for i in tree.ancestors(state, m.metadata["node_id"])],
            "summary": m.summary, "title": m.title,
            "knowledge_unit_types": dict(Counter(u.fields.get("Kind", u.kind) for u in m.units)),
            "provenance": {"sources": [m.metadata["source"]] if "source" in m.metadata else m.metadata.get("sources", []),
                           "relationships": [r.payload() for r in m.relationships]},
            "lineage": m.metadata.get("source_memories", []), "estimated_s2_tokens": costs})
    return {"root_question": state["nodes"][state["root_id"]]["question"],
        **questions.context(state, "S1"),
        "question": state["nodes"][state["root_id"]]["question"],
        "research_tree": [{k: n[k] for k in ("id", "question", "parent_id", "status")}
                          for i, n in state["nodes"].items() if i in tree.eligible_subtree(state, state["root_id"])],
        "memory_catalogue": catalogue,
        "synthesis_budget": {"context_budget": state["context_budget"], "output_reserve": reserve,
                      "costs_include_request_overhead": True, "objective_cost_is_additional": True},
        "previous_attempt_exclusions": [a["memory_versions"] for a in state["synthesis_attempts"] if a["status"] == "completed"]}


def validate_selection(value, state, memories):
    require(isinstance(value, dict), "S1 object required")
    if value.get("disposition") == "no_candidate":
        decisions.fields(value, ["disposition", "reason"]); decisions.text(value["reason"])
        return []
    decisions.fields(value, ["disposition", "memory_ids", "objective", "scores", "reason"])
    require(value["disposition"] == "select", "invalid S1 disposition")
    decisions.text(value["objective"]); decisions.text(value["reason"])
    ids = value["memory_ids"]
    eligible = {m.id: m for m in tree.frontier(state, memories, state["root_id"])}
    require(isinstance(ids, list) and len(ids) >= 2 and all(isinstance(i, str) and i in eligible for i in ids)
            and len(ids) == len(set(ids)), "S1 requires at least two distinct eligible memory IDs")
    scores = value["scores"]
    require(isinstance(scores, dict) and set(scores) == set("RCXNE") and
            all(type(v) is int and 0 <= v <= 5 for v in scores.values()), "invalid S1 scores (integers 0-5 required)")
    inputs = [eligible[i] for i in ids]
    require(tree.permitted(state, inputs), "S1 combination or subset was previously attempted")
    return inputs


def prepare(state, memories, equations, inputs, objective, model, settings, counter=None):
    """Preserve the exact selected collection; never pack or drop inputs."""
    identity = owner(state, inputs)
    info = {"selected_node": identity, "input_ids": [m.id for m in inputs],
            "context_budget": state["context_budget"],
            "output_reserve": state.get("synthesis_output_reserve", state["output_reserve"])}
    for summarized in (False, True):
        supplied = context(state, memories, equations, identity, inputs, summarized=summarized, objective=objective)
        usage = measure(decisions.request(model, settings, "S2", supplied), info["output_reserve"], state["context_budget"], counter)
        info.update(representation="structured_summary" if summarized else "complete_memory", usage=usage,
                    estimated_total=usage["estimated_tokens"])
        if not usage["over_context_budget"]: return identity, supplied, info
    return identity, None, info


def validate(value, inputs, supplied=None):
    require(isinstance(value, dict), "S2 object required")
    if value.get("disposition") == "no_synthesis":
        decisions.fields(value, ["disposition", "reason"]); decisions.text(value["reason"])
        return []
    decisions.fields(value, ["disposition", "title", "summary", "findings"])
    require(value["disposition"] == "synthesis", "invalid S2 disposition")
    decisions.text(value["title"]); decisions.text(value["summary"])
    require(isinstance(value["findings"], list) and value["findings"], "synthesis findings required")
    targets = {m.id + "#" + u.anchor for m in inputs for u in m.units if u.kind in {"finding", "question", "equation", "image"}}
    if supplied is not None:
        shown = {u["id"] for m in supplied if m.get("representation") == "structured_summary" for u in m["units"]}
        shown.update(m.id + "#" + u.anchor for m in inputs for u in m.units
                     if any(s["id"] == m.id and s.get("representation") == "complete_memory" for s in supplied))
        targets &= shown
    covered, integrated = set(), False
    for finding in value["findings"]:
        decisions.fields(finding, SYNTHESIS_FINDING)
        for key in ("label", "proposition", "explanation", "provenance"): decisions.text(finding[key])
        refs = finding["source_findings"]
        require(isinstance(refs, list) and refs and all(isinstance(r, str) and r in targets for r in refs), "invalid synthesis finding reference")
        require(len(refs) == len(set(refs)), "duplicate synthesis reference")
        contributors = {r.split("#")[0] for r in refs}
        integrated |= len(contributors) >= 2
        covered.update(contributors)
    require(integrated, "at least one integrated finding must reference two distinct input memories")
    return [m.id for m in inputs if m.id in covered]


def apply(state, memories, ledger, identity, inputs, value, supplied=None):
    require(len(inputs) >= 2 and len({m.id for m in inputs}) == len(inputs) and
            all(m.metadata["synthesized_by"] is None for m in inputs), "invalid synthesis frontier")
    contributing = {r.split("#")[0] for f in value["findings"] for r in f["source_findings"]}
    # Existing callers constructing historical fixture lineage may omit the new
    # disposition. The live S2 path always validates the current response first.
    consumed = [m for m in inputs if m.id in contributing] if "disposition" in value else inputs
    output_id = "s" + base36(ledger["s"]); ledger["s"] += 1
    output = Memory(output_id, value["title"], value["summary"], metadata={"node_id": identity,
        "kind": "synthesis", "source_memories": [m.id for m in consumed], "synthesized_by": None,
        "created_order": len(memories) + 1, "markdown_format": 2})
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
    for memory in consumed:
        memory.metadata["synthesized_by"] = output_id; memory.revision += 1
    memories.append(output); state["nodes"][identity]["memory_ids"].append(output_id)
    return output
