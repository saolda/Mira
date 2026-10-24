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
            "memory_ids": [], "unsynthesized_memory_count": 0,
            "living_descendant_count": 0, "synthesis_score": 0}


def initial(question, databases, *, synthesis_interval=5, context_budget=8192, output_reserve=2048):
    require(isinstance(question, str) and question.strip(), "research question required")
    require(databases and len(set(databases)) == len(databases) and
            all(isinstance(d, str) and d.strip() for d in databases), "ordered database IDs required")
    require(type(synthesis_interval) is int and synthesis_interval > 0, "positive synthesis interval required")
    require(type(context_budget) is int and type(output_reserve) is int and 0 < output_reserve < context_budget,
            "invalid context/output budget")
    root = node("q1", question); root["priority"] = 10
    return {"mira_research": 1, "run_id": uuid.uuid4().hex, "root_id": "q1", "strategy_index": 0,
            "strategies": [{"id": "selected", "databases": list(databases)}], "active_node_id": "q1",
            "next_node": 2, "research_cycles": 0, "synthesis_cycles": 0, "revision": 1,
            "research_cycles_since_synthesis": 0, "synthesis_interval": synthesis_interval,
            "priority_max": 10, "terminal_synthesis_bonus": 1000, "context_budget": context_budget,
            "output_reserve": output_reserve, "nodes": {"q1": root}, "living_priority_order": ["q1"],
            "synthesis_candidate_order": [], "terminal_event": None}


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
    scope = set(descendants(state, identity))
    return sorted((m for m in memories if m.metadata.get("node_id") in scope and
                   m.metadata["synthesized_by"] is None), key=lambda m: m.metadata["created_order"])


def refresh(state, memories, *, complete=True):
    """Postorder refresh covers input owners as well as output ancestors."""
    nodes = state["nodes"]
    for identity in reversed(descendants(state, state["root_id"])):
        n = nodes[identity]
        n["unsynthesized_memory_count"] = sum(m.metadata.get("node_id") == identity and
            m.metadata.get("synthesized_by") is None for m in memories) + sum(nodes[c]["unsynthesized_memory_count"] for c in n["child_ids"])
        n["living_descendant_count"] = sum(int(nodes[c]["status"] == "living") + nodes[c]["living_descendant_count"] for c in n["child_ids"])
        count = n["unsynthesized_memory_count"]
        if complete and n["status"] == "exhausted" and not n["living_descendant_count"] and count <= 1:
            n["status"] = "complete"
        terminal = n["status"] == "exhausted" and not n["living_descendant_count"] and count >= 2
        n["synthesis_score"] = count + (state["terminal_synthesis_bonus"] if terminal else 0)
    state["living_priority_order"] = sorted((i for i, n in nodes.items() if n["status"] == "living"),
        key=lambda i: (-nodes[i]["priority"], nodes[i]["created_order"]))
    state["synthesis_candidate_order"] = sorted((i for i, n in nodes.items() if n["status"] != "complete" and n["unsynthesized_memory_count"] >= 2),
        key=lambda i: (-nodes[i]["synthesis_score"], nodes[i]["created_order"]))
    active = state["active_node_id"]
    if active is None or nodes[active]["status"] != "living" or nodes[active]["priority"] == 0:
        state["active_node_id"] = next(iter(state["living_priority_order"]), None)


def validate(state, memories, files):
    require(isinstance(state, dict) and state.get("mira_research") == 1, "invalid research state version")
    for key in ("next_node", "revision", "synthesis_interval", "context_budget", "output_reserve"):
        require(type(state[key]) is int and state[key] > 0, "invalid research configuration: " + key)
    for key in ("research_cycles", "synthesis_cycles", "research_cycles_since_synthesis"):
        require(type(state[key]) is int and state[key] >= 0, "invalid cycle count")
    require(state["context_budget"] > state["output_reserve"] and state["priority_max"] == 10 and
            state["terminal_synthesis_bonus"] == 1000, "invalid scheduler/budget configuration")
    nodes = state["nodes"]
    require(isinstance(nodes, dict) and state["root_id"] in nodes, "missing root")
    require(nodes[state["root_id"]]["parent_id"] is None, "root has parent")
    require(type(state["strategy_index"]) is int and 0 <= state["strategy_index"] < len(state["strategies"]), "invalid strategy")
    databases = state["strategies"][state["strategy_index"]]["databases"]
    require(databases and len(databases) == len(set(databases)) and all(isinstance(d, str) and d for d in databases), "invalid databases")
    linked, orders = [], []
    for identity, n in nodes.items():
        require(re.fullmatch(r"q[1-9][0-9]*", identity) and n["id"] == identity and
                n["created_order"] == int(identity[1:]) < state["next_node"], "invalid node allocator/order")
        require(n["status"] in {"living", "exhausted", "killed", "complete"}, "invalid node status")
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
    living = Counter()
    for i in descendants(state, state["root_id"]):
        n = state["nodes"][i]
        if n["parent_id"] is not None:
            depths[i] = depths[n["parent_id"]] + 1
        if n["status"] == "living":
            living[depths[i]] += 1
    return {"active_node": state["active_node_id"], "research_cycles": state["research_cycles"],
            "synthesis_cycles": state["synthesis_cycles"], "max_depth": max(depths.values()),
            "living_by_depth": dict(sorted(living.items())), "nodes": state["nodes"],
            "candidates": state["synthesis_candidate_order"]}
