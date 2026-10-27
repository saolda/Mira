"""Read-only projections of recorded decisions. Never rebuild model inputs from live state."""
from copy import deepcopy
import json
from pathlib import Path
import re

from .experiments import Experiments, confined, NAME
from .format import digest, dumps, loads, require
from .prompts import PLACEHOLDER


def read_text(root, relative):
    root = Path(root)
    confined(root)
    path = root / relative
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "unsafe artifact path")
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "symlink research artifact")
        if parent == root: break
    return path.read_text(encoding="utf-8") if path.is_file() else None


def read_json(root, relative, warnings):
    try:
        text = read_text(root, relative)
        if text is None: return None
        value = loads(text)
        require(isinstance(value, dict), "record must be a JSON object")
        return value
    except (ValueError, OSError) as exc:
        warnings.append(f"{relative}: {exc}")
        return {"record_error": str(exc), "raw": read_text(root, relative)}


def response_body(record):
    response = record.get("response") or {}
    raw = response.get("raw")
    try:
        body = loads(raw)
        return body if isinstance(body, dict) else {}
    except (ValueError, TypeError): return {}


class Inspector:
    def __init__(self, home=None): self.catalog = Experiments(home)

    def experiments(self):
        result = []
        for name in self.catalog.names():
            warnings = []
            root = self.catalog.path(name)
            state = read_json(root, "research/state.json", warnings) or {}
            nodes = state.get("nodes", {})
            root_node = nodes.get(state.get("root_id"), {}) if isinstance(nodes, dict) else {}
            result.append({"name": name, "question": root_node.get("question"), "run_id": state.get("run_id"),
                "research_cycles": state.get("research_cycles"), "synthesis_cycles": state.get("synthesis_cycles"),
                "warnings": warnings, "initialized": bool(state.get("run_id"))})
        return result

    def _load(self, name):
        root = self.catalog.select(name)
        warnings, records, events, journals = [], [], [], []
        directory = root / "interactions"
        confined(root, "interactions")
        if directory.exists():
            for path in sorted(directory.iterdir()):
                require(not path.is_symlink(), "symlink interaction")
                if not path.is_dir() or not NAME.fullmatch(path.name):
                    warnings.append("Unrecognized interaction artifact: " + path.name); continue
                record = {"id": path.name}
                for phase in ("request", "response", "validation", "outcome"):
                    value = read_json(root, f"interactions/{path.name}/{phase}.json", warnings)
                    if value is not None: record[phase] = value
                records.append(record)
        confined(root, "journal")
        for path in sorted((root / "journal").glob("*.json")):
            m = read_json(root, "journal/" + path.name, warnings)
            if m and isinstance(m.get("files"), list): journals.append(m)
        journals.sort(key=lambda m: m.get("sequence", 0))
        committed_events = {}
        for m in journals:
            if m.get("status") == "committed":
                for entry in m["files"]:
                    if isinstance(entry, dict) and str(entry.get("path", "")).startswith("events/"):
                        committed_events[entry["path"]] = (entry.get("after"), m.get("sequence"))
            else: warnings.append(f"Journal {m.get('id')} is {m.get('status')}; do not treat partial files as committed.")
        confined(root, "events")
        for path in sorted((root / "events").glob("*.json")):
            relative = "events/" + path.name
            event = read_json(root, relative, warnings)
            if event is None: continue
            expected, sequence = committed_events.get(relative, (None, None))
            verified = expected is not None and digest(read_text(root, relative)) == expected
            if not verified:
                warnings.append(relative + ": not verified by a committed journal entry; not shown as a committed action.")
            event = {**event, "id": path.stem, "journal_sequence": sequence,
                "verified_committed": verified}
            events.append(event)
        state = read_json(root, "research/state.json", warnings)
        return root, records, events, journals, state, warnings

    @staticmethod
    def _status(record, event):
        response = record.get("response", {})
        outcome = record.get("outcome") or event or {}
        if response.get("status") == "call_failed": return "failed"
        if outcome.get("status") == "rejected": return "rejected"
        if outcome.get("status") == "interrupted_acknowledged": return "interrupted"
        if outcome.get("status") == "committed" and ("outcome" in record or event): return "completed"
        return "interrupted"

    def run(self, name):
        root, records, events, journals, state, warnings = self._load(name)
        linked = {e.get("interaction_id"): e for e in events if e.get("interaction_id") and e["verified_committed"]}
        timeline = []
        for record in records:
            req = record.get("request", {})
            timeline.append({"id": record["id"], "kind": "decision", "timestamp": req.get("timestamp", ""),
                "sequence": req.get("sequence"), "cycle": req.get("cycle"), "node_id": req.get("node_id"),
                "action": req.get("action", "unknown"), "question": req.get("question"),
                "status": self._status(record, linked.get(record["id"]))})
        for event in events:
            if event.get("interaction_id") in {r["id"] for r in records}: continue
            status = "completed" if event.get("verified_committed") and event.get("status", "committed") == "committed" else "failed"
            timeline.append({**{k: event.get(k) for k in ("timestamp", "cycle", "node_id", "action", "question")},
                "id": event["id"], "kind": "action", "status": status})
        timeline.sort(key=lambda item: (item.get("timestamp") or "", item["id"]))
        corpus = []
        confined(root, "memories")
        for path in sorted((root / "memories").glob("*.md")):
            corpus.append({"id": path.stem, "markdown": read_text(root, "memories/" + path.name)})
        return {"name": name, "current_state": state, "current_corpus": corpus, "timeline": timeline,
                "warnings": warnings, "notice": "Current corpus/state are separate from historical model inputs. All decision inputs come from recorded requests."}

    @staticmethod
    def _historical(root, journals, before_sequence, warnings):
        """Replay retained after-images for historical availability, never for prompts."""
        corpus, state = {}, None
        if before_sequence is None: return None, None
        for m in journals:
            if m.get("status") != "committed" or m.get("sequence", 0) >= before_sequence: continue
            for entry in m["files"]:
                path = entry.get("path", "")
                if not (path.startswith("memories/") or path == "research/state.json"): continue
                text = read_text(root, entry.get("payload", ""))
                if text is None or digest(text) != entry.get("after"):
                    warnings.append("Historical after-image unavailable: " + path)
                    if path == "research/state.json": state = None
                    else: corpus[path] = None
                    continue
                if path == "research/state.json": state = loads(text)
                else: corpus[path] = text
        return [{"id": Path(path).stem, "markdown": text, "available": text is not None} for path, text in sorted(corpus.items())], state

    def decision(self, name, identity):
        require(NAME.fullmatch(identity), "invalid decision identifier")
        root, records, events, journals, current_state, warnings = self._load(name)
        record = next((r for r in records if r["id"] == identity), None)
        require(record is not None, "unknown decision")
        req = record.get("request", {})
        event = next((e for e in events if e.get("interaction_id") == identity and e["verified_committed"]), None)
        serialized = req.get("serialized_request")
        payload, source = None, "Not recorded"
        if isinstance(serialized, str):
            try:
                payload = loads(serialized)
                require(isinstance(payload, dict), "request body is not an object")
                source = "Exact recorded serialized_request"
            except ValueError: warnings.append("Serialized request is malformed; raw body remains available.")
        elif isinstance(req.get("request"), dict):
            payload = req["request"]; source = "Recorded request object; exact serialized body absent"
        messages = payload.get("messages", []) if payload else []
        require(isinstance(messages, list), "recorded messages must be a list")
        template = req.get("prompt_template")
        template_check = {"recorded": isinstance(template, dict), "matches_recorded_request": None,
                          "notice": "Template version was not recorded for this call. Filled text below comes only from the saved request."}
        if isinstance(template, dict):
            matches = (isinstance(serialized, str) and template.get("serialized_request_sha256") == digest(serialized)
                       and template.get("filled_messages") == messages)
            if template.get("version") == 2:
                files = template.get("files", [])
                bindings = template.get("bindings", {}).get("context")
                try:
                    raw = files[0]["source"]
                    reproduced = PLACEHOLDER.sub(lambda m: dumps(bindings[m[1]]).rstrip("\n"), raw)
                    matches = (matches and len(files) == 1 and digest(raw) == files[0]["sha256"]
                               and bindings == req.get("context")
                               and messages == [{"role": "user", "content": reproduced}])
                except (KeyError, IndexError, TypeError):
                    matches = False
            template_check.update(matches_recorded_request=matches,
                                  notice="Filled templates match the recorded request." if matches else "Template snapshot does not match the saved request; use the saved request as authority.")
            if not matches: warnings.append(template_check["notice"])
        user_payloads = []
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "user":
                try:
                    value = loads(message.get("content"))
                    if isinstance(value, dict): user_payloads.append(value)
                except (ValueError, TypeError): pass
        structured = next((v for v in user_payloads if "context" in v), {})
        context = structured.get("context") if isinstance(structured.get("context"), dict) else {}
        plain_text_prompt = None
        context_recorded = "context" in structured
        if isinstance(template, dict) and template.get("version") == 2:
            if template_check["matches_recorded_request"]:
                context = template["bindings"]["context"]
                context_recorded = True
            plain_text_prompt = next((m.get("content") for m in messages if isinstance(m, dict) and m.get("role") == "user"), None)
        corpus, historic_state = self._historical(root, journals, event.get("journal_sequence") if event else None, warnings)
        before = historic_state.get("nodes") if historic_state else None
        supplied = list(context.get("linked_memories") or []) + list(context.get("input_memories") or []) + list((context.get("research_results") or {}).get("memories", []))
        supplied_ids = {m.get("id") for m in supplied if isinstance(m, dict)}
        if corpus is not None:
            for m in corpus: m["included_in_request"] = m["id"] in supplied_ids
        # Evidence previously retrieved is displayed separately, not inserted into context.
        retrieved = []
        if event and event.get("journal_sequence") is not None:
            for past in sorted(events, key=lambda e: e.get("journal_sequence") or 0):
                if past["verified_committed"] and past.get("evidence_ref") and past.get("journal_sequence", 0) < event["journal_sequence"]:
                    ref = past["evidence_ref"]
                    if not any(item["reference"] == ref for item in retrieved):
                        retrieved.append({"reference": ref, "evidence": read_json(root, ref, warnings)})
        body = response_body(record)
        usage = body.get("usage")
        config = historic_state or {}
        selection = req.get("selection") or {}
        limit = selection.get("context_budget", config.get("context_budget"))
        reserve = selection.get("output_reserve", config.get("output_reserve"))
        estimated = len(serialized.encode("utf-8")) if isinstance(serialized, str) else None
        estimate_total = estimated + reserve if estimated is not None and isinstance(reserve, int) else None
        recorded_usage = req.get("context_usage")
        if isinstance(recorded_usage, dict):
            reserve = recorded_usage["output_reserve"]
            limit = recorded_usage["context_budget"]
            estimate_total = recorded_usage["estimated_tokens"]
        inputs = {"root_question": context.get("root_question", (context.get("question_context") or [context.get("question")])[0]), "question": context.get("question"),
            "question_context": context.get("question_context"), "node": context.get("node"),
            "ancestor_questions": context.get("ancestor_questions"), "existing_memories": supplied or None,
            "search_evidence": context.get("research", context.get("search_evidence")), "children": context.get("children"),
            "equations": context.get("equations"), "output_contract": structured.get("output_contract"),
            "system_messages": [m for m in messages if isinstance(m, dict) and m.get("role") == "system"] or None,
            "developer_messages": [m for m in messages if isinstance(m, dict) and m.get("role") == "developer"] or None,
            "user_messages": [m for m in messages if isinstance(m, dict) and m.get("role") == "user"] or None}
        return {"id": identity, "experiment": name, "status": self._status(record, event), "record": record,
            "input_source": source, "serialized_request": serialized, "inputs": inputs,
            "prompt_template": template, "template_verification": template_check,
            "filled_prompt_messages": messages, "plain_text_prompt": plain_text_prompt,
            "task_instructions": {key: structured.get(key) for key in
                ("task", "instructions", "information_rules", "output_requirements")},
            "prompt_slots": [{"name": key, "value": value,
                "status": "Explicit null" if value is None else
                          "Empty collection" if value == [] or value == {} else
                          "Empty string" if value == "" else "Supplied"}
                for key, value in context.items()] if context_recorded else None,
            "structured_context": context if context_recorded else None,
            "model": payload.get("model") if payload else None,
            "generation_settings": {k: v for k, v in payload.items() if k not in {"model", "messages"}} if payload else None,
            "reported_model": body.get("model"), "usage": usage, "raw_response": (record.get("response") or {}).get("raw"),
            "completion_messages": [c.get("message") for c in body.get("choices", []) if isinstance(c, dict)],
            "validation": record.get("validation"), "outcome": record.get("outcome"), "committed_event": event,
            "tree_before": before, "tree_after": event.get("tree") if event else None,
            "historical_corpus": corpus, "retrieved_before_decision": retrieved if event else None,
            "generated_memories": event.get("generated_memories") if event else None,
            "context_estimate": {**(recorded_usage or {}), "request_bytes": estimated, "output_reserve": reserve, "budget": limit,
                "estimated_total": estimate_total, "fraction": estimate_total / limit if estimate_total is not None and limit else None,
                "basis": recorded_usage["estimator"] if recorded_usage else "Conservative UTF-8 request bytes plus reserve; budget from recorded selection or historical journal state, never current state."},
            "warnings": warnings}

    def action(self, name, identity):
        require(NAME.fullmatch(identity), "invalid action ID")
        root, records, events, journals, state, warnings = self._load(name)
        event = next((e for e in events if e["id"] == identity), None)
        require(event is not None, "unknown action")
        evidence = read_json(root, event["evidence_ref"], warnings) if event.get("evidence_ref") else None
        return {"event": event, "retrieved_evidence": evidence, "warnings": warnings,
                "notice": "This is an audit action. Retrieved evidence was not necessarily supplied to an LLM; inspect each recorded request."}
