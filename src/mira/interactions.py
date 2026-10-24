"""Durable independent decision records; actual request text precedes every call."""
from datetime import datetime, timezone
from pathlib import Path
import uuid

from .format import dumps, loads, require
from .store import durable_write, sync_dir


def now():
    return datetime.now(timezone.utc).isoformat()


class Interactions:
    def __init__(self, store, secrets=()):
        self.store = store
        self.secrets = tuple(s for s in secrets if s)
        path = store.path("interactions")
        path.mkdir(exist_ok=True); sync_dir(path.parent)

    def clean(self, text):
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")
            text = text.replace(dumps(secret).strip()[1:-1], "[REDACTED]")
        return text

    def write(self, identity, phase, data):
        path = self.store.path(f"interactions/{identity}/{phase}.json")
        # Immutable phase files: an interrupted write remains visible, never replaced.
        def scrub(value):
            if isinstance(value, str): return self.clean(value)
            if isinstance(value, dict): return {self.clean(k): scrub(v) for k, v in value.items()}
            if isinstance(value, list): return [scrub(v) for v in value]
            return value
        durable_write(path, dumps(scrub(data)))
        sync_dir(path.parent)

    def start(self, event, request, context, *, template=None):
        # Caller holds store lock, giving monotonic order even across restarts.
        sequence = len(list(self.store.path("interactions").iterdir())) + 1
        identity = f"{sequence:08d}-{uuid.uuid4().hex}"
        path = self.store.path("interactions/" + identity)
        path.mkdir(); sync_dir(path.parent)
        self.write(identity, "request", {**event, "timestamp": now(), "sequence": sequence,
            "serialized_request": request, "request": loads(request), "context": context,
            **({"prompt_template": template} if template is not None else {})})
        return identity


def read_records(root):
    """Works without a LiveStore, SQLite, controller state or network."""
    root = Path(root)
    result = []
    directory = root / "interactions"
    require(not directory.is_symlink(), "symlink interaction directory")
    for path in sorted(directory.glob("*")):
        require(path.is_dir() and not path.is_symlink(), "invalid interaction directory")
        phases = {}
        for name in ("request", "response", "validation", "outcome"):
            file = path / (name + ".json")
            require(not file.is_symlink(), "symlink interaction phase")
            if file.exists():
                try:
                    phases[name] = loads(file.read_text())
                except ValueError:
                    phases[name] = {"error": "interrupted or corrupt phase file", "raw": file.read_text()}
        result.append({"id": path.name, **phases})
    return result


def transcript(root, *, full=False):
    """Merge actual interactions with immutable committed event/evidence records."""
    root = Path(root)
    events = []
    for path in (root / "events").glob("*.json"):
        require(not path.is_symlink(), "symlink event")
        events.append(loads(path.read_text()))
    interactions = read_records(root)
    linked = {e.get("interaction_id"): e for e in events if e.get("interaction_id")}
    timeline = [(e.get("timestamp", ""), "event", e) for e in events if not e.get("interaction_id")]
    for record in interactions:
        request = record.get("request", {})
        timeline.append((request.get("timestamp", ""), "llm", record))
    lines = ["# Mira research transcript", ""]
    for timestamp, kind, item in sorted(timeline, key=lambda row: (row[0], row[1])):
        request = item.get("request", {}) if kind == "llm" else item
        lines.extend([f"## {timestamp} | cycle {request.get('cycle', '?')} | {request.get('node_id')} | {request.get('action')}", ""])
        if kind == "llm":
            committed = linked.get(item["id"])
            outcome = item.get("outcome", committed or {"status": "interrupted_or_unknown", "action_committed": None})
            if full:
                lines += ["Actual request record:", "```json", dumps(request).rstrip(), "```",
                          "Complete response, validation and final outcome:", "```json",
                          dumps({**{k: v for k, v in item.items() if k != "request"}, "resolved_outcome": outcome, "committed_event": committed}).rstrip(), "```"]
            else:
                lines += [f"Question: {request.get('question')}", f"Interaction: {item['id']}",
                          f"Outcome: {dumps(outcome).strip()}"]
        else:
            shown = dict(item)
            if full and item.get("evidence_ref"):
                evidence_path = root / item["evidence_ref"]
                require(evidence_path.resolve().is_relative_to(root.resolve()), "unsafe evidence reference")
                shown["evidence"] = loads(evidence_path.read_text()) if evidence_path.exists() else {"error": "missing evidence"}
            if not full:
                shown.pop("tree", None); shown.pop("evidence", None)
            lines += ["```json", dumps(shown).rstrip(), "```"]
        lines.append("")
    return "\n".join(lines)
