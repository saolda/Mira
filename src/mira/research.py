"""State-driven controller: one selected action, at most one model call per step."""
from copy import deepcopy
from dataclasses import asdict
from collections import Counter
import uuid

from .api import Knowledge
from .format import digest, dumps, loads, render, require
from .live import LiveStore
from .interactions import Interactions, now, read_records
from . import decisions, research_tree as tree, r1, r3, branching
from .search import validate_search, ArxivSearch
from . import strategies, sources
import time
from email.utils import parsedate_to_datetime


class Research:
    def __init__(self, root, llm, adapters, *, control_terms=()):
        self.knowledge = Knowledge(store=LiveStore(root))
        self.store = self.knowledge.store
        self.llm, self.adapters = llm, adapters
        self.control_terms = r1.controls(control_terms)
        self.trace = Interactions(self.store, tuple(getattr(llm, "secrets", ())) +
            tuple(secret for adapter in adapters.values() for secret in getattr(adapter, "secrets", ())))

    def initialize(self, question, databases=None, *, strategy=None, registry=None, fault=None, **config):
        with self.store.lock():
            token, memories, equations, ledger = self.store.read()
            require(not self.store._files() and not read_records(self.store.root), "research initialization requires an empty isolated corpus")
            require(not (databases is not None and strategy is not None), "choose a strategy or explicit databases")
            values = strategies.registry(registry) if databases is None else None
            chosen = strategies.select(values, strategy) if strategy is not None else None
            state = tree.initial(question, databases or (chosen["databases"] if chosen else ["selection_pending"]), **config)
            state.update(source_index={}, provider_cooldowns={}, retrieval_storage="temporary")
            event = {"run_id": state["run_id"], "timestamp": now(), "cycle": 0, "action": "initialize",
                     "node_id": "q1", "question": question, "config": config}
            extras = {}
            if chosen is None and databases is None:
                event.update(action="R0", status="committed")
                try:
                    value = self._model(event, "R0", {"question": question, "strategies": values}, state)
                    decisions.validate("R0", value, values)
                    chosen = strategies.select(values, value["strategy"])
                    event.update(decision=value, action_committed="R0")
                    state["strategy_selection"] = {"method":"r0", **value, "interaction_id":event["interaction_id"]}
                except Exception as exc:
                    identity = event.get("interaction_id")
                    if identity:
                        self.trace.write(identity, "validation", {"timestamp":now(), "accepted":False, "action":"R0", "error":str(exc)})
                        self.trace.write(identity, "outcome", {"timestamp":now(), "status":"rejected", "action_committed":None, "error":str(exc)})
                    raise
            elif chosen is not None:
                state["strategy_selection"] = {"method":"explicit", "strategy":chosen["id"], "reason":"Operator-selected strategy."}
            else:
                chosen = {"id":"custom", "name":"Custom", "description":"Operator-supplied database sequence.", "databases":list(databases)}
                state["strategy_selection"] = {"method":"databases", "strategy":"custom", "reason":"Explicit database compatibility path."}
            state["strategies"] = [deepcopy(chosen)]
            event.update(databases=chosen["databases"], strategy=chosen)
            branching.assess(state, memories, equations, self.llm.model, self.llm.settings)
            tree.validate(state, memories, {})
            identity = event.get("interaction_id")
            if identity:
                self.trace.write(identity, "validation", {"timestamp":now(), "accepted":True, "action":"R0"})
            extras.update({"research/state.json":dumps(state), "events/initialize.json":dumps(event)})
            self.store.publish(memories, equations, ledger, token, files=extras, operation_type="initialize", fault=fault)
            if identity:
                self.trace.write(identity, "outcome", {"timestamp":now(), "status":"committed", "action_committed":"R0", "event_ref":"events/initialize.json"})
            return state

    def prune_retrievals(self, *, apply=False):
        return sources.prune(self.store, apply=apply)

    def inspect(self):
        with self.store.lock():
            self.store.read()
            state = loads(self.store._files()["research/state.json"])
            return tree.metrics(state)

    def _context(self, state, memories, equations, files, node_id):
        n = state["nodes"][node_id]
        linked = [m for m in memories if m.id in n["memory_ids"]]
        equation_ids = {u.fields["Equation"] for m in linked for u in m.units if u.kind == "equation"}
        strategy = deepcopy(state["strategies"][state["strategy_index"]])
        searches = []
        for path, raw in files.items():
            if path.startswith("research/results/"):
                result = loads(raw)
                if result.get("node_id") == node_id:
                    searches.append({key: value for key, value in result.items() if key != "raw_api_response"})
        searches.sort(key=lambda item: (item.get("timestamp", ""), item.get("reference", "")))
        history = [{key: value for key, value in result.items() if key not in {"results", "duplicates", "payload_ref", "payload_sha256"}} for result in searches]
        return {"root_question": state["nodes"][state["root_id"]]["question"], "question": n["question"],
                "node": deepcopy(n),
                "ancestor_questions": [state["nodes"][i]["question"] for i in tree.ancestors(state, node_id)],
                "linked_memories": [{"id": m.id, "markdown": render(m)} for m in linked],
                "children": [deepcopy(state["nodes"][i]) for i in n["child_ids"]],
                "strategy": strategy,
                "next_database": strategy["databases"][n["next_database_index"]] if n["next_database_index"] < len(strategy["databases"]) else None,
                "search_history": history,
                "equations": [asdict(e) for e in equations if e.id in equation_ids]}, searches

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
        unredacted, template = decisions.prepared_request(self.llm.model, self.llm.settings, action, context)
        serialized = self.trace.clean(unredacted)
        template["redaction_applied"] = serialized != unredacted
        template["filled_messages"] = loads(serialized)["messages"]
        template["serialized_request_sha256"] = digest(serialized)
        # Byte count is a deliberately conservative token estimate, including JSON overhead.
        require(len(serialized.encode("utf-8")) + state["output_reserve"] <= state["context_budget"],
                "blocked_context_budget: full decision context does not fit")
        identity = self.trace.start(event, serialized, context, template=template)
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

    def _research(self, state, memories, equations, ledger, files, event):
        identity = state["active_node_id"]; n = state["nodes"][identity]
        before_nodes = set(state["nodes"])
        databases = state["strategies"][state["strategy_index"]]["databases"]
        action = ("R3" if n["pending_results"] else "R1" if n["keywords"] is None else
                  "R2" if n["next_database_index"] < len(databases) else "R4")
        event.update(action=action, node_id=identity, question=n["question"])
        extras = {}
        if action == "R2":
            provider = databases[n["next_database_index"]]
            query = ArxivSearch.query(n["keywords"]) if provider == "arxiv" else " ".join(n["keywords"])
            evidence_ref = "research/results/" + uuid.uuid4().hex + ".json"
            event.update(provider=provider, query=query, evidence_ref=evidence_ref)
            cooldowns = state.setdefault("provider_cooldowns", {})
            if cooldowns.get(provider, 0) > time.time():
                result = {"status":"rate_limited", "results":[], "skipped":"provider_cooldown", "retry_at":cooldowns[provider]}
            else:
                try:
                    result = validate_search(self.adapters[provider].search(query))
                except Exception as exc:
                    result = {"status":"failed", "results":[], "error":self.trace.clean(str(exc)), "error_type":type(exc).__name__}
            result = loads(self.trace.clean(dumps(result)))
            unique, duplicates = sources.unique(result["results"], state.setdefault("source_index", {}))
            sources.reconcile(state["source_index"], duplicates)
            evidence = {**{k:v for k,v in result.items() if k not in {"results","raw_api_response"}},
                "provider":provider, "query":query, "timestamp":now(), "node_id":identity,
                "round":n.get("search_round",0), "reference":evidence_ref,
                "results":unique, "duplicates":duplicates}
            if state.get("retrieval_storage") == "temporary":
                evidence["results"] = [sources.descriptor(row) for row in unique]
                if unique:
                    evidence.update(sources.save_payload(self.store, evidence_ref.split('/')[-1][:-5], unique))
            elif "raw_api_response" in result:
                evidence["raw_api_response"] = result["raw_api_response"]  # Preserve old experiment policy.
            extras[evidence_ref] = dumps(evidence)
            event.update(search_status=result["status"], duplicate_count=len(duplicates), unique_source_count=len(unique))
            n["next_database_index"] += 1
            outcomes = n.setdefault("round_outcomes", [])
            outcomes.append(result["status"])
            if result["status"] in {"failed","rate_limited"} and not result.get("skipped"):
                delay = 60
                retry = result.get("retry_after")
                if retry:
                    try: delay = max(1, int(retry))
                    except (TypeError,ValueError):
                        try: delay = max(1, parsedate_to_datetime(retry).timestamp() - time.time())
                        except (TypeError,ValueError,OverflowError): pass
                cooldowns[provider] = max(cooldowns.get(provider, 0), time.time() + delay)
                event["retry_at"] = cooldowns[provider]
            if result["status"] in {"ok","empty"}: cooldowns.pop(provider, None)
            if unique: n["pending_results"] = evidence_ref
            if n["next_database_index"] == len(databases) and outcomes and all(o in {"failed","rate_limited"} for o in outcomes):
                event.update(status="providers_unavailable", reason="All databases were unavailable this round; progress saved for explicit resumption.")
        else:
            if action == "R1":
                context = r1.context(state, memories, files, identity, self.control_terms)
            elif action == "R3":
                evidence = sources.hydrate(self.store, loads(files[n["pending_results"]]))
                evidence["results"], duplicates = sources.unique(evidence["results"], state.setdefault("source_index", {}))
                event["duplicate_count"] = len(duplicates)
                context = r3.context(state, identity, evidence)
            else:
                old_context, searches = self._context(state, memories, equations, files, identity)
                context = {k: v for k, v in branching.context(state, memories, equations, identity).items() if k != "max_children"}
                context = {**context,
                           "search_history": old_context["search_history"]}
            if action == "R3":
                event["evidence_ref"] = n["pending_results"]
            if action == "R3" and not evidence["results"]:
                value = {"results": []}
                event["reason"] = "All pending sources were processed by another node."
            else:
                value = self._model(event, action, context, state)
            decisions.validate(action, value, evidence if action == "R3" else None)
            if action == "R1":
                accepted = r1.filter_terms(value["keywords"], self.control_terms)
                event["keyword_filter"] = {"original": value["keywords"], "accepted": accepted}
                n["keywords"] = accepted
                n["search_round"] = n.get("search_round",0) + 1
                n["round_outcomes"] = []
            elif action == "R3":
                output = r3.create_memory(state, memories, equations, ledger, identity, value["results"], evidence)
                sources.processed(state.setdefault("source_index", {}), evidence["results"], evidence["reference"])
                sources.reconcile(state["source_index"], evidence.get("duplicates", []))
                if output is not None:
                    cited = {source for result in value["results"] for source in result["source_ids"]}
                    output.metadata["sources"] = [sources.descriptor(row) for row in evidence["results"] if row["id"] in cited]
                event["memory_ids"] = [output.id] if output is not None else []
                event["generated_memories"] = [render(m) for m in memories if m.id in event["memory_ids"]]
                n["pending_results"] = None
            else:
                decision = value["decision"]
                if decision in {"kill", "answered"}:
                    n["status"] = "killed" if decision == "kill" else "answered"
                if decision == "retry":
                    n["previous_search_terms"] = r1.unique(n["previous_search_terms"] + n["keywords"])
                    n["keywords"] = None
                    n["next_database_index"] = 0
                    n["round_outcomes"] = []
                event["decision"] = value
        for i in before_nodes:
            other = state["nodes"][i]
            if i == identity: other["priority"] = max(0, other["priority"] - 1)
            elif other["status"] == "living": other["priority"] = min(10, other["priority"] + 1)
        state["research_cycles"] += 1; state["research_cycles_since_synthesis"] += 1
        state["research_cycles_since_branching"] += 1
        return extras, True

    def _branching(self, state, memories, equations, event, event_id):
        identity = state["ripeness_order"][0]
        n = state["nodes"][identity]
        require(n["status"] == "exhausted" and n["split_attempt"] is None, "R5 requires exhausted node")
        event.update(action="R5", node_id=identity, question=n["question"],
            selection={"ripeness_order": list(state["ripeness_order"]), "ripeness": n["ripeness"],
                       "counts": deepcopy(n["ripeness_counts"]), "capacity": deepcopy(n["research_capacity"]),
                       "branching_interval": state["branching_interval"]})
        value = self._model(event, "R5", branching.context(state, memories, equations, identity), state)
        decisions.validate("R5", value)
        event["branching"] = branching.apply(state, identity, value, event_id)
        # Branching also uses a work slot in the synthesis cadence.
        state["research_cycles_since_synthesis"] += 1
        return True

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
            original = deepcopy((state, memories, equations, ledger))
            state = tree.upgrade(state, memories)
            if "source_index" not in state:
                state["source_index"] = {}
                for path, raw in files.items():
                    if not path.startswith("events/"): continue
                    past = loads(raw)
                    ref = past.get("evidence_ref")
                    if past.get("action_committed") == "R3" and ref in files:
                        old_evidence = loads(files[ref])
                        sources.processed(state["source_index"], old_evidence["results"], ref)
            event_id = uuid.uuid4().hex
            event = {"run_id": state["run_id"], "timestamp": now(),
                     "cycle": state["research_cycles"] + state["synthesis_cycles"] + state["branching_cycles"] + 1,
                     "research_cycle": state["research_cycles"] + 1,
                     "node_id": state["active_node_id"], "action": "select", "status": "committed"}
            extras = {}
            try:
                event["exhaustion"] = branching.assess(state, memories, equations, self.llm.model, self.llm.settings)
                if original[0]["mira_research"] == 1: event["state_upgrade"] = {"from": 1, "to": 2}
                if state["research_cycles_since_synthesis"] >= state["synthesis_interval"]:
                    success = self._synthesis(state, memories, equations, ledger, event)
                elif branching.due(state):
                    success = self._branching(state, memories, equations, event, event_id)
                elif state["active_node_id"] is None:
                    if not state["synthesis_candidate_order"]:
                        return {"status": "finished", "research_cycles": state["research_cycles"], "synthesis_cycles": state["synthesis_cycles"]}
                    success = self._synthesis(state, memories, equations, ledger, event)
                else:
                    extras, success = self._research(state, memories, equations, ledger, files, event)
                event["exhaustion"].extend(branching.assess(state, memories, equations, self.llm.model, self.llm.settings))
                tree.refresh(state, memories)
                if success:
                    state["recent_activity"] = (state["recent_activity"] + [{"cycle": event["cycle"],
                        "action": event["action"], "node_id": event["node_id"], "timestamp": event["timestamp"]}])[-20:]
                event["tree"] = deepcopy(state["nodes"])
                if state["active_node_id"] is None and not state["ripeness_order"] and state["terminal_event"] is None:
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
                candidate = {**combined, "identity.json": dumps(ledger), **{"memories/" + m.id + ".md": render(m) for m in memories},
                             **{"equations/" + e.id + ".json": dumps(asdict(e)) for e in equations}}
                decode(candidate)
            except Exception as exc:
                state, memories, equations, ledger = original
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
                    "memory_ids": event.get("memory_ids", []), "tree_changes": event.get("branching", event.get("decision")), "error": event.get("error")})
            return event

    def run(self, max_cycles):
        require(type(max_cycles) is int and max_cycles > 0, "positive cycle limit required")
        events = []
        for _ in range(max_cycles):
            event = self.step(); events.append(event)
            if event["status"] != "committed": break
        return {"status": events[-1]["status"] if events[-1]["status"] != "committed" else "cycle_limit", "actions": events}
