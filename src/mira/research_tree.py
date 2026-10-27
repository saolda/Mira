"""Research-tree contracts, deterministic priorities and frontier accounting."""
from copy import deepcopy
from collections import Counter
import re
import uuid

from .format import loads, require


def node(identity, question, parent=None):
    return {"id": identity, "created_order": int(identity[1:]), "parent_id": parent,
            "child_ids": [], "question": question, "status": "living", "priority": 0,
            "keywords": None, "next_database_index": 0, "pending_results": None,
            "previous_search_terms": [], "split_attempt": None, "research_capacity": None,
            "memory_ids": [], "unsynthesized_memory_count": 0,
            "living_descendant_count": 0, "synthesis_score": 0}


def initial(question, databases, *, synthesis_interval=5, context_budget=8192, output_reserve=2048,
            research_capacity_tokens=None, branching_interval=5, max_children=3):
    require(isinstance(question, str) and question.strip(), "research question required")
    require(databases and len(set(databases)) == len(databases) and
            all(isinstance(d, str) and d.strip() for d in databases), "ordered database IDs required")
    require(type(synthesis_interval) is int and synthesis_interval > 0, "positive synthesis interval required")
    require(type(context_budget) is int and type(output_reserve) is int and 0 < output_reserve < context_budget,
            "invalid context/output budget")
    research_capacity_tokens = research_capacity_tokens if research_capacity_tokens is not None else context_budget * 3 // 4
    require(type(research_capacity_tokens) is int and 0 < research_capacity_tokens <= context_budget,
            "research capacity must be positive and no larger than context budget")
    require(type(branching_interval) is int and branching_interval > 0, "positive branching interval required")
    require(type(max_children) is int and max_children > 0, "positive child limit required")
    root = node("q1", question); root["priority"] = 10
    state = {"mira_research": 2, "run_id": uuid.uuid4().hex, "root_id": "q1", "strategy_index": 0,
            "strategies": [{"id": "selected", "databases": list(databases)}], "active_node_id": "q1",
            "next_node": 2, "research_cycles": 0, "synthesis_cycles": 0, "revision": 1,
            "research_cycles_since_synthesis": 0, "synthesis_interval": synthesis_interval,
            "priority_max": 10, "terminal_synthesis_bonus": 1000, "context_budget": context_budget,
            "output_reserve": output_reserve, "nodes": {"q1": root}, "living_priority_order": ["q1"],
            "synthesis_candidate_order": [], "terminal_event": None,
            "research_capacity_tokens": research_capacity_tokens, "branching_interval": branching_interval,
            "max_children": max_children, "branching_cycles": 0, "research_cycles_since_branching": 0,
            "ripeness_weights": {"findings": 1, "hypotheses": 2, "questions": 2, "depth": -1},
            "ripeness_order": [], "recent_activity": []}

    refresh(state, [])
    return state


def descendants(state, identity):
    result, stack = [], [identity]
    while stack:
        current = stack.pop()
        require(current not in result, "cycle or repeated child in research tree")
        result.append(current)
        stack.extend(reversed(state["nodes"][current]["child_ids"]))
    return result


def ancestors(state, identity):
    result = []
    while identity is not None:
        require(identity not in result, "cyclic parent chain")
        result.append(identity)
        identity = state["nodes"][identity]["parent_id"]
    return list(reversed(result))


def frontier(state, memories, identity):
    scope = set(eligible_subtree(state, identity))
    documents = {m.id: m for m in memories}
    def relevant(memory):
        owner = memory.metadata.get("node_id")
        if owner is None: return False
        if any(state["nodes"][i]["status"] == "killed" for i in ancestors(state, owner)): return False
        return all(relevant(documents[i]) for i in memory.metadata.get("source_memories", []))
    return sorted((m for m in memories if m.metadata.get("node_id") in scope and
                   m.metadata["synthesized_by"] is None and relevant(m)), key=lambda m: m.metadata["created_order"])


def eligible_subtree(state, identity):
    """Killed branches retain their corpus but never enter normal synthesis."""
    if any(state["nodes"][i]["status"] == "killed" for i in ancestors(state, identity)):
        return []
    return [i for i in descendants(state, identity)
            if not any(state["nodes"][a]["status"] == "killed" for a in ancestors(state, i))]


def research_counts(state, memories, identity):
    findings, hypotheses, questions = set(), set(), set()
    for m in memories:
        if m.metadata.get("node_id") != identity or m.metadata.get("kind") != "research":
            continue
        for u in m.units:
            normalized = lambda text: " ".join(text.split()).casefold()
            kind = u.fields.get("Kind")
            if kind == "finding": findings.add(normalized(u.fields["Proposition"]))
            if kind == "hypothesis": hypotheses.add(normalized(u.fields["Proposition"]))
            if u.kind == "question" and u.fields["State"] in {"open", "partially_answered"}:
                questions.add(normalized(u.fields["Question"]))
    return {"findings": len(findings), "hypotheses": len(hypotheses), "questions": len(questions),
            "depth": len(ancestors(state, identity)) - 1}


def refresh(state, memories, *, complete=True):
    # `complete` remains accepted for old callers; research status is never a
    # consequence of synthesis. Completion is a separate, recomputable flag.
    if state.get("mira_research") == 1:
        from .research_tree_v1 import refresh as legacy_refresh
        return legacy_refresh(state, memories, complete=complete)
    nodes = state["nodes"]
    for identity in reversed(descendants(state, state["root_id"])):
        n = nodes[identity]
        n["unsynthesized_memory_count"] = len(frontier(state, memories, identity))
        n["living_descendant_count"] = sum(int(nodes[c]["status"] == "living") + nodes[c]["living_descendant_count"] for c in n["child_ids"])
        pending = any(nodes[i]["status"] in {"living", "exhausted"} for i in eligible_subtree(state, identity))
        count = n["unsynthesized_memory_count"]
        n["synthesis_complete"] = not pending and count <= 1
        terminal = not pending and count >= 2
        n["synthesis_score"] = count + (state["terminal_synthesis_bonus"] if terminal else 0)
        n["ripeness_counts"] = research_counts(state, memories, identity)
        n["ripeness"] = sum(n["ripeness_counts"][k] * w for k, w in state["ripeness_weights"].items())
    state["living_priority_order"] = sorted((i for i, n in nodes.items() if n["status"] == "living"),
        key=lambda i: (-nodes[i]["priority"], nodes[i]["created_order"]))
    state["synthesis_candidate_order"] = sorted((i for i, n in nodes.items() if eligible_subtree(state, i) and n["unsynthesized_memory_count"] >= 2),
        key=lambda i: (-nodes[i]["synthesis_score"], nodes[i]["created_order"]))
    state["ripeness_order"] = sorted((i for i, n in nodes.items() if n["status"] == "exhausted"),
        key=lambda i: (-nodes[i]["ripeness"], nodes[i]["created_order"]))
    active = state["active_node_id"]
    if active is None or nodes[active]["status"] != "living" or nodes[active]["priority"] == 0:
        state["active_node_id"] = next(iter(state["living_priority_order"]), None)


def upgrade(state, memories):
    """Journal the conversion on the next successful action; historical bytes stay intact."""
    if state["mira_research"] == 2: return state
    state = deepcopy(state)
    defaults = initial(state["nodes"][state["root_id"]]["question"], state["strategies"][state["strategy_index"]]["databases"],
                       context_budget=state["context_budget"], output_reserve=state["output_reserve"])
    for k, v in defaults.items(): state.setdefault(k, v)
    state["mira_research"] = 2
    for n in state["nodes"].values():
        old = n["status"]
        n.setdefault("previous_search_terms", [])
        n.setdefault("research_capacity", None)
        n.setdefault("split_attempt", None)
        if old == "complete":
            # Legacy complete meant synthesis bookkeeping, never proof of an answer.
            n["status"] = "split" if n["child_ids"] else "exhausted"
        elif n["child_ids"] and old != "killed": n["status"] = "split"
        if n["child_ids"] and n["status"] == "split":
            if n["pending_results"] is not None:
                n["legacy_pending_results"] = n["pending_results"]
                n["pending_results"] = None
            n["split_attempt"] = {"legacy": True, "questions": [state["nodes"][i]["question"] for i in n["child_ids"]]}
        n["legacy_status"] = old
    refresh(state, memories)
    return state


def validate(state, memories, files):
    if isinstance(state, dict) and state.get("mira_research") == 1:
        from .research_tree_v1 import validate as legacy_validate
        return legacy_validate(state, memories, files)
    require(isinstance(state, dict) and state.get("mira_research") == 2, "invalid research state version")
    for key in ("branching_interval", "max_children", "research_capacity_tokens"):
        require(type(state[key]) is int and state[key] > 0, "invalid branching configuration: " + key)
    require(state["research_capacity_tokens"] <= state["context_budget"], "capacity exceeds context budget")
    require(set(state["ripeness_weights"]) == {"findings", "hypotheses", "questions", "depth"} and
            all(type(v) is int for v in state["ripeness_weights"].values()), "invalid ripeness weights")
    for key in ("next_node", "revision", "synthesis_interval", "context_budget", "output_reserve"):
        require(type(state[key]) is int and state[key] > 0, "invalid research configuration: " + key)
    for key in ("research_cycles", "synthesis_cycles", "research_cycles_since_synthesis", "branching_cycles", "research_cycles_since_branching"):
        require(type(state[key]) is int and state[key] >= 0, "invalid cycle count")
    require(state["context_budget"] > state["output_reserve"] and state["priority_max"] == 10 and
            state["terminal_synthesis_bonus"] == 1000, "invalid scheduler/budget configuration")
    nodes = state["nodes"]
    require(isinstance(nodes, dict) and state["root_id"] in nodes, "missing root")
    require(nodes[state["root_id"]]["parent_id"] is None, "root has parent")
    require(type(state["strategy_index"]) is int and 0 <= state["strategy_index"] < len(state["strategies"]), "invalid strategy")
    databases = state["strategies"][state["strategy_index"]]["databases"]
    require(databases and len(databases) == len(set(databases)) and all(isinstance(d, str) and d for d in databases), "invalid databases")
    if "strategy_selection" in state:
        selection = state["strategy_selection"]
        require(isinstance(selection, dict) and selection.get("method") in {"r0","explicit","databases"}
                and selection.get("strategy") == state["strategies"][state["strategy_index"]]["id"]
                and isinstance(selection.get("reason"),str) and selection["reason"].strip(), "missing/invalid persisted strategy selection")
    require(isinstance(state.get("source_index", {}), dict), "invalid source index")
    for source in state.get("source_index", {}).values():
        require(isinstance(source,dict) and isinstance(source.get("identifiers"),dict) and source["identifiers"]
                and isinstance(source.get("source"),dict) and isinstance(source.get("evidence_ref"),str), "invalid processed source")
    linked, orders = [], []
    for identity, n in nodes.items():
        require(re.fullmatch(r"q[1-9][0-9]*", identity) and n["id"] == identity and
                n["created_order"] == int(identity[1:]) < state["next_node"], "invalid node allocator/order")
        require(n["status"] in {"living", "answered", "exhausted", "killed", "split"}, "invalid node status")
        require(isinstance(n["previous_search_terms"], list) and all(isinstance(t, str) and t.strip() for t in n["previous_search_terms"]), "invalid tried terms")
        require((n["status"] == "split") == (n["split_attempt"] is not None), "inconsistent split attempt")
        if n["split_attempt"] is not None:
            receipt = n["split_attempt"]
            require(isinstance(receipt, dict) and isinstance(receipt.get("questions"), list) and
                    all(isinstance(q, str) and q.strip() for q in receipt["questions"]), "invalid split receipt")
        require(isinstance(n["question"], str) and n["question"].strip(), "empty node question")
        require(type(n["priority"]) is int and 0 <= n["priority"] <= 10, "invalid priority")
        require(n["keywords"] is None or isinstance(n["keywords"], list) and n["keywords"] and
                all(isinstance(k, str) and k.strip() for k in n["keywords"]), "invalid keywords")
        require(type(n["next_database_index"]) is int and 0 <= n["next_database_index"] <= len(databases), "invalid database pointer")
        require(len(n["child_ids"]) == len(set(n["child_ids"])), "duplicate child")
        for child in n["child_ids"]:
            require(child in nodes and nodes[child]["parent_id"] == identity, "nonreciprocal child")
        if identity != state["root_id"]:
            require(n["parent_id"] in nodes and identity in nodes[n["parent_id"]]["child_ids"], "nonreciprocal parent")
        pending = n["pending_results"]
        if pending is not None:
            require(n["status"] == "living" and pending in files and pending.startswith("research/results/"), "missing/invalid pending evidence")
            evidence = loads(files[pending])
            require(evidence["status"] == "ok" and evidence["results"] and evidence["node_id"] == identity, "invalid pending evidence")
        require(n["keywords"] is not None or (pending is None and n["next_database_index"] == 0), "inconsistent research state")
        linked.extend(n["memory_ids"])
    require(set(descendants(state, state["root_id"])) == set(nodes), "disconnected tree")
    require(len(linked) == len(set(linked)) and set(linked) == {m.id for m in memories}, "memory ownership mismatch")
    for m in memories:
        owner = m.metadata["node_id"]
        require(owner in nodes and m.id in nodes[owner]["memory_ids"], "wrong memory owner")
        require(type(m.metadata["created_order"]) is int and m.metadata["created_order"] > 0, "invalid memory creation order")
        orders.append(m.metadata["created_order"])
        for source in m.metadata["source_memories"]:
            source_doc = next(d for d in memories if d.id == source)
            require(source_doc.metadata["node_id"] in descendants(state, owner), "synthesis input outside subtree")
    require(len(orders) == len(set(orders)), "duplicate memory creation order")
    active = state["active_node_id"]
    require(active is None or active in nodes and nodes[active]["status"] == "living", "invalid active node")
    expected = deepcopy(state); refresh(expected, memories)
    require(expected == state, "stale tree counts, lifecycle or ordering")


def metrics(state):
    depths = {state["root_id"]: 0}
    living, all_depths = Counter(), Counter()
    for i in descendants(state, state["root_id"]):
        n = state["nodes"][i]
        if n["parent_id"] is not None:
            depths[i] = depths[n["parent_id"]] + 1
        all_depths[depths[i]] += 1
        if n["status"] == "living":
            living[depths[i]] += 1
    return {"active_node": state["active_node_id"], "research_cycles": state["research_cycles"],
            "synthesis_cycles": state["synthesis_cycles"], "max_depth": max(depths.values()),
            "living_by_depth": dict(sorted(living.items())), "nodes": state["nodes"],
            "candidates": state["synthesis_candidate_order"],
            "strategy": state["strategies"][state["strategy_index"]],
            "strategy_selection": state.get("strategy_selection"),
            "processed_source_count": len(state.get("source_index", {})),
            "provider_cooldowns": state.get("provider_cooldowns", {}),
            "retrieval_storage": state.get("retrieval_storage", "legacy_canonical"),
            "status_totals": {s: sum(n["status"] == s for n in state["nodes"].values())
                              for s in ("living", "exhausted", "answered", "killed", "split")},
            "nodes_by_depth": dict(sorted(all_depths.items())),
            "ripeness_queue": state.get("ripeness_order", []),
            "branching_cycles": state.get("branching_cycles", 0),
            "branching_policy": {k: state.get(k) for k in ("branching_interval", "max_children", "research_cycles_since_branching")},
            "research_capacity_tokens": state.get("research_capacity_tokens"),
            "context_budget": state["context_budget"], "output_reserve": state["output_reserve"],
            "ripeness_weights": state.get("ripeness_weights"), "recent_activity": state.get("recent_activity", [])}


def validate_transition(before, after):
    """A durable split receipt cannot be cleared or replayed by any writer."""
    if before.get("mira_research") != 2: return
    require(after.get("mira_research") == 2, "cannot downgrade research state")
    if "strategy_selection" in before:
        require(after.get("strategy_selection") == before["strategy_selection"] and after["strategies"] == before["strategies"]
                and after["strategy_index"] == before["strategy_index"], "experiment strategy is immutable")
    for key, source in before.get("source_index", {}).items():
        require(key in after.get("source_index", {}) and all(after["source_index"][key]["identifiers"].get(k) == v
                for k,v in source["identifiers"].items()), "cannot forget a processed source")
    allowed = {"living": {"living", "answered", "killed", "exhausted"},
               "exhausted": {"exhausted", "split"}, "answered": {"answered"},
               "killed": {"killed"}, "split": {"split"}}
    for identity, old in before["nodes"].items():
        require(identity in after["nodes"], "cannot delete research node")
        new = after["nodes"][identity]
        require(new["status"] in allowed[old["status"]], "invalid research status transition")
        if old["split_attempt"] is not None:
            require(new["split_attempt"] == old["split_attempt"] and new["child_ids"] == old["child_ids"],
                    "branching attempt already committed")
