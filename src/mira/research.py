"""State-driven controller: one selected action, at most one model call per step."""
from copy import deepcopy
from collections import Counter
import uuid

from .api import Knowledge
from .format import Memory, Unit, Relationship, base36, dumps, loads, render, require
from .live import LiveStore
from .interactions import Interactions, now, read_records
from . import decisions, research_tree as tree
from .search import validate_search


class Research:
    def __init__(self, root, llm, adapters):
        self.knowledge = Knowledge(store=LiveStore(root))
        self.store = self.knowledge.store
        self.llm, self.adapters = llm, adapters
        self.trace = Interactions(self.store, getattr(llm, "secrets", ()))

    def initialize(self, question, databases, **config):
        with self.store.lock():
            token, memories, equations, ledger = self.store.read()
            require(not self.store._files(), "research initialization requires an empty isolated corpus")
            state = tree.initial(question, databases, **config)
            event = {"run_id": state["run_id"], "timestamp": now(), "cycle": 0, "action": "initialize",
                     "node_id": "q1", "question": question, "databases": databases, "config": config}
            self.store.publish(memories, equations, ledger, token, files={
                "research/state.json": dumps(state), "events/initialize.json": dumps(event)}, operation_type="initialize")
            return state

    def inspect(self):
        with self.store.lock():
            self.store.read()
            state = loads(self.store._files()["research/state.json"])
            return tree.metrics(state)

    def _context(self, state, memories, node_id):
        n = state["nodes"][node_id]
        return {"root_question": state["nodes"][state["root_id"]]["question"], "node": deepcopy(n),
                "ancestor_questions": [state["nodes"][i]["question"] for i in tree.ancestors(state, node_id)],
                "linked_memories": [{"id": m.id, "markdown": render(m)} for m in memories if m.id in n["memory_ids"]],
                "children": [deepcopy(state["nodes"][i]) for i in n["child_ids"]]}

    def _unresolved(self, files):
        committed = {loads(t).get("interaction_id") for p, t in files.items() if p.startswith("events/")}
        return [r for r in read_records(self.store.root) if "outcome" not in r and r["id"] not in committed]

    def acknowledge_interrupted(self):
        """Explicitly acknowledge unknown calls after inspecting their independent records."""
        with self.store.lock():
            self.store.read()
            records = self._unresolved(self.store._files())
            for record in records:
                self.trace.write(record["id"], "outcome", {"timestamp": now(), "status": "interrupted_acknowledged",
                    "action_committed": None, "warning": "Model may have executed; operator authorized another attempt."})
            return [r["id"] for r in records]

    def _model(self, event, action, context, state):
        require(0 < self.llm.settings["max_tokens"] <= state["output_reserve"], "generation limit exceeds output reserve")
        serialized = self.trace.clean(decisions.request(self.llm.model, self.llm.settings, action, context))
        # Byte count is a deliberately conservative token estimate, including JSON overhead.
        require(len(serialized.encode("utf-8")) + state["output_reserve"] <= state["context_budget"],
                "blocked_context_budget: full decision context does not fit")
        identity = self.trace.start(event, serialized, context)
        event["interaction_id"] = identity
        try:
            raw = self.llm.complete(serialized)
        except Exception as exc:
            self.trace.write(identity, "response", {"timestamp": now(), "error": self.trace.clean(str(exc)),
                "error_type": type(exc).__name__, "raw": getattr(exc, "raw", None), "status": "call_failed"})
            raise
        raw = self.trace.clean(raw)
        self.trace.write(identity, "response", {"timestamp": now(), "raw": raw, "status": "received"})
        value, info = decisions.proposal(raw)
        event["model"] = info
        return value

    def _add_memory(self, state, memories, ledger, node_id, draft, evidence):
        identity = "r" + base36(ledger["r"]); ledger["r"] += 1
        memory = Memory(identity, draft["title"], draft["summary"], metadata={"node_id": node_id,
            "kind": "research", "source_memories": [], "synthesized_by": None,
            "created_order": len(memories) + 1, "evidence_ref": evidence["reference"]})
        rows = {r["id"]: r for r in evidence["results"]}
        for finding in draft["findings"]:
            anchor = memory.allocate("f")
            memory.units.append(Unit(anchor, finding["label"], {"Kind": finding["kind"],
                "Evidence status": "unverified", "Proposition": finding["proposition"],
                "Explanation": finding["explanation"], "Provenance": finding["provenance"]}))
            for url in dict.fromkeys(rows[i]["url"] for i in finding["evidence_ids"]):
                memory.relationships.append(Relationship(anchor, "CITES", url, "unverified"))
        memories.append(memory); state["nodes"][node_id]["memory_ids"].append(identity)
        return identity

    def _research(self, state, memories, ledger, files, event):
        identity = state["active_node_id"]; n = state["nodes"][identity]
        before_nodes = set(state["nodes"])
        databases = state["strategies"][state["strategy_index"]]["databases"]
        action = ("R3" if n["pending_results"] else "R1" if n["keywords"] is None else
                  "R2" if n["next_database_index"] < len(databases) else "R4")
        event.update(action=action, node_id=identity, question=n["question"])
        extras = {}
        if action == "R2":
            provider = databases[n["next_database_index"]]
            query = " ".join(n["keywords"])
            evidence_ref = "research/results/" + uuid.uuid4().hex + ".json"
            event.update(provider=provider, query=query, evidence_ref=evidence_ref)
            try:
                result = validate_search(self.adapters[provider].search(query))
            except Exception as exc:
                result = {"status": "failed", "results": [], "error": self.trace.clean(str(exc)), "error_type": type(exc).__name__}
            evidence = {**result, "provider": provider, "query": query, "timestamp": now(), "node_id": identity, "reference": evidence_ref}
            # Sanitize known transport credentials even if an adapter echoes them.
            evidence = loads(self.trace.clean(dumps(evidence)))
            extras[evidence_ref] = dumps(evidence)
            event["search_status"] = evidence["status"]
            if evidence["status"] in {"failed", "rate_limited"}:
                event["status"] = "search_failed"
                return extras, False
            n["next_database_index"] += 1
            if evidence["status"] == "ok": n["pending_results"] = evidence_ref
        else:
            context = self._context(state, memories, identity)
            evidence = None
            if action == "R3":
                evidence = loads(files[n["pending_results"]])
                context["search_evidence"] = {key: value for key, value in evidence.items() if key != "raw_api_response"}
                event["evidence_ref"] = n["pending_results"]
            value = self._model(event, action, context, state)
            decisions.validate(action, value, evidence)
            if action == "R1": n["keywords"] = value["keywords"]
            elif action == "R3":
                event["memory_ids"] = [self._add_memory(state, memories, ledger, identity, d, evidence) for d in value["memories"]]
                event["generated_memories"] = [render(m) for m in memories if m.id in event["memory_ids"]]
                n["pending_results"] = None
            else:
                decision = value["decision"]
                if decision in {"kill", "exhaust", "exhaust_split"}:
                    n["status"] = "killed" if decision == "kill" else "exhausted"
                if decision.startswith("retry"):
                    n["keywords"] = value["keywords"]; n["next_database_index"] = 0
                for question in value["children"]:
                    child_id = "q" + str(state["next_node"]); state["next_node"] += 1
                    child = tree.node(child_id, question, identity)
                    state["nodes"][child_id] = child; n["child_ids"].append(child_id)
                event["decision"] = value
        for i in before_nodes:
            other = state["nodes"][i]
            if i == identity: other["priority"] = max(0, other["priority"] - 1)
            elif other["status"] == "living": other["priority"] = min(10, other["priority"] + 1)
        state["research_cycles"] += 1; state["research_cycles_since_synthesis"] += 1
        return extras, True

    def _synthesis(self, state, memories, equations, ledger, event):
        from . import gardener
        identity, inputs, context, selection = gardener.select(state, memories, equations, self.llm.model, self.llm.settings)
        event["selection"] = selection
        if identity is None:
            event.update(action="S1", reason="no_candidate")
        elif len(inputs) < 2:
            event.update(action="S1", node_id=identity, status="blocked_synthesis", reason="no_fitting_pair")
        else:
            event.update(action="S2", node_id=identity, question=state["nodes"][identity]["question"], input_ids=[m.id for m in inputs])
            value = self._model(event, "S2", context, state)
            gardener.validate(value, inputs)
            output = gardener.apply(state, memories, ledger, identity, inputs, value)
            event.update(memory_ids=[output.id], generated_memories=[render(output)])
        state["synthesis_cycles"] += 1; state["research_cycles_since_synthesis"] = 0
        return True

    def step(self, *, fault=None):
        with self.store.lock():
            token, memories, equations, ledger = self.store.read()
            files = self.store._files()
            require("research/state.json" in files, "initialize research first")
            state = loads(files["research/state.json"])
            tree.validate(state, memories, files)
            require(not self._unresolved(files), "interrupted/unknown model call: inspect transcript and explicitly acknowledge before retry")
            original = deepcopy((state, memories, ledger))
            event_id = uuid.uuid4().hex
            event = {"run_id": state["run_id"], "timestamp": now(),
                     "cycle": state["research_cycles"] + state["synthesis_cycles"] + 1,
                     "research_cycle": state["research_cycles"] + 1,
                     "node_id": state["active_node_id"], "action": "select", "status": "committed"}
            extras = {}
            try:
                if state["active_node_id"] is None:
                    if not state["synthesis_candidate_order"]:
                        return {"status": "finished", "research_cycles": state["research_cycles"], "synthesis_cycles": state["synthesis_cycles"]}
                    success = self._synthesis(state, memories, equations, ledger, event)
                elif state["research_cycles_since_synthesis"] >= state["synthesis_interval"]:
                    success = self._synthesis(state, memories, equations, ledger, event)
                else:
                    extras, success = self._research(state, memories, ledger, files, event)
                tree.refresh(state, memories)
                event["tree"] = deepcopy(state["nodes"])
                if state["active_node_id"] is None and state["terminal_event"] is None:
                    terminal_id = "terminal_" + event_id
                    state["terminal_event"] = terminal_id
                    terminal = {"run_id": state["run_id"], "timestamp": now(), "cycle": event["cycle"],
                        "action": "research_terminal", "node_id": None,
                        "root_question": state["nodes"][state["root_id"]]["question"],
                        "status_totals": dict(Counter(n["status"] for n in state["nodes"].values())),
                        "unsynthesized_counts": {i: n["unsynthesized_memory_count"] for i, n in state["nodes"].items()},
                        "pending_results": {i: n["pending_results"] for i, n in state["nodes"].items() if n["pending_results"]},
                        "pending_synthesis": state["synthesis_candidate_order"]}
                    extras["events/" + terminal_id + ".json"] = dumps(terminal)
                if success: state["revision"] += 1
                combined = {**files, **extras, "research/state.json": dumps(state)}
                tree.validate(state, memories, combined)
                # Admission includes canonical Markdown/lineage checks before marking valid.
                from .live import decode
                candidate = {**combined, "identity.json": dumps(ledger), **{"memories/" + m.id + ".md": render(m) for m in memories}}
                decode(candidate)
            except Exception as exc:
                state, memories, ledger = original
                if "memory_ids" in event:
                    event["proposed_memory_ids"] = event.pop("memory_ids")
                if "generated_memories" in event:
                    event["rejected_generated_memories"] = event.pop("generated_memories")
                if "tree" in event:
                    event["proposed_tree"] = event.pop("tree")
                event["tree"] = deepcopy(state["nodes"])
                event.update(status="rejected", error=self.trace.clean(str(exc)), error_type=type(exc).__name__)
                success = False; extras = {}
            interaction = event.get("interaction_id")
            if interaction:
                self.trace.write(interaction, "validation", {"timestamp": now(), "accepted": success,
                    "error": event.get("error"), "action": event["action"], "model": event.get("model")})
            event["action_committed"] = event["action"] if success else None
            extras["research/state.json"] = dumps(state)
            extras["events/" + event_id + ".json"] = dumps(event)
            self.store.publish(memories, equations, ledger, token, files=extras,
                operation_type="research_cycle", context={"cycle_id": event_id, "node_id": event["node_id"],
                    "interaction_id": interaction}, fault=fault)
            if interaction:
                self.trace.write(interaction, "outcome", {"timestamp": now(), "status": event["status"],
                    "action_committed": event["action_committed"], "event_ref": "events/" + event_id + ".json",
                    "memory_ids": event.get("memory_ids", []), "tree_changes": event.get("decision"), "error": event.get("error")})
            return event

    def run(self, max_cycles):
        require(type(max_cycles) is int and max_cycles > 0, "positive cycle limit required")
        events = []
        for _ in range(max_cycles):
            event = self.step(); events.append(event)
            if event["status"] != "committed": break
        return {"status": events[-1]["status"] if events[-1]["status"] != "committed" else "cycle_limit", "actions": events}
