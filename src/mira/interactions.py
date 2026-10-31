"""Durable independent decision records; actual request text precedes every call."""
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
import fcntl
import json
import os
import traceback
import uuid

from .format import dumps, loads, require
from .store import durable_write, sync_dir


def now():
    return datetime.now(timezone.utc).isoformat()


def configured_secrets(extra=()):
    """Values only; environment names and unrelated environment data aren't logged."""
    return tuple(dict.fromkeys([*extra, *(value for key, value in os.environ.items()
        if set(key.upper().split("_")) & {"KEY", "TOKEN", "PASSWORD", "SECRET", "CREDENTIAL", "CREDENTIALS"} and value)]))


def scrub(value, secrets):
    def clean(text):
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
                text = text.replace(dumps(secret).strip()[1:-1], "[REDACTED]")
        return text
    if isinstance(value, str): return clean(value)
    if isinstance(value, dict): return {clean(k): scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [scrub(v, secrets) for v in value]
    return value


class ExecutionLog:
    """An incremental export of existing interaction phases and action events."""
    def __init__(self, directory, root, *, command, model=None, settings=None, secrets=()):
        from .experiments import confined
        self.root = Path(root).absolute()
        self.directory = Path(directory).absolute()
        confined(self.directory)
        require(not self.directory.is_relative_to(self.root), "run logs must be outside the experiment")
        if self.root.parent.name == "research":
            require(not self.directory.is_relative_to(self.root.parent), "run logs must be outside the experiment catalog")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        sync_dir(self.directory.parent)
        self.identity = uuid.uuid4().hex
        policy = self.root / 'experiment.json'
        self.experiment = loads(policy.read_text()).get('name', self.root.name) if policy.exists() else self.root.name
        self.secrets = tuple(secrets)
        self.model, self.settings = model, settings
        # The random suffix prevents collisions and never reopens an old run.
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        label = "".join(c if c.isalnum() or c in "_-" else "_" for c in self.experiment)[:96]
        self.path = self.directory / f"{stamp}_{label}_{self.identity[:12]}.jsonl"
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.stream = os.fdopen(fd, "w", encoding="utf-8")
        self.sequence, self.seen = 0, set()
        self.reason = "completed"
        self.append("execution_start", {"command": command, "root": str(self.root),
                    "pid": os.getpid(), "model": model, "generation_parameters": settings})
        sync_dir(self.directory)

    def append(self, kind, data, *, key=None, **context):
        if key is not None and key in self.seen: return
        record = scrub({"version": 1, "execution_id": self.identity,
            "sequence": self.sequence + 1, "timestamp": now(), "experiment_id": self.experiment,
            "kind": kind, "model": self.model, "generation_parameters": self.settings,
            **context, "data": data}, self.secrets)
        # dumps() intentionally pretty-prints canonical JSON. JSONL needs one
        # complete compact JSON object per physical line, including embedded LF.
        self.stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
        self.stream.flush(); os.fsync(self.stream.fileno())
        self.sequence += 1
        if key is not None: self.seen.add(key)

    def configure(self, model, settings):
        self.model, self.settings = model, settings
        self.append("model_configuration", {"model": model, "generation_parameters": settings})

    def close(self, exception=None):
        try:
            self.append("execution_end", {"reason": self.reason if exception is None else
                "interrupted" if isinstance(exception, (KeyboardInterrupt, SystemExit)) else "exception",
                **({"error": str(exception), "error_type": type(exception).__name__,
                    "traceback": "".join(traceback.format_exception(exception))} if exception is not None else {})})
        finally:
            self.stream.close()


class Interactions:
    def __init__(self, store, secrets=()):
        self.store = store
        self.secrets = configured_secrets(s for s in secrets if s)
        self.log = None
        self.proposals, self.normalized, self.requests = {}, {}, {}
        path = store.path("interactions")
        path.mkdir(exist_ok=True); sync_dir(path.parent)

    def clean(self, text):
        return scrub(text, self.secrets)

    @contextmanager
    def execution(self, directory=None, *, command="research-run", model=None, settings=None):
        if self.log is not None:
            yield self.log
            return
        root = self.store.root
        directory = directory or ((root.parent.parent.parent if root.parent.name == "research" else root.parent) / "log")
        self.log = ExecutionLog(directory, root, command=command, model=model, settings=settings, secrets=self.secrets)
        exception, lease = None, None
        try:
            # A lease protects the entire run, including gaps between writer locks.
            # Create the export first so even a rejected concurrent invocation is
            # diagnosed in its own file rather than disappearing without a log.
            lease = self.store.path(".runner.lock").open("a")
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for cache in (self.requests, self.proposals, self.normalized): cache.clear()
            yield self.log
        except BaseException as exc:
            exception = exc
            raise
        finally:
            try: self.log.close(exception)
            finally:
                self.log = None
                for cache in (self.requests, self.proposals, self.normalized): cache.clear()
                if lease:
                    fcntl.flock(lease, fcntl.LOCK_UN)
                    lease.close()

    def record(self, kind, data, event=None, *, key=None):
        if self.log is not None:
            event = event or {}
            self.log.append(kind, data, key=key,
                **{k: event.get(k) for k in ("action", "node_id", "cycle", "interaction_id", "run_id")})

    def write(self, identity, phase, data):
        path = self.store.path(f"interactions/{identity}/{phase}.json")
        if phase == "request":
            self.requests[identity] = {k: data.get(k) for k in ("action", "node_id", "cycle", "run_id")}
            if self.log is not None:
                wire = data["request"]
                settings = {k: v for k, v in wire.items() if k not in {"model", "messages"}}
                if self.log.model != wire.get("model") or self.log.settings != settings:
                    self.log.configure(wire.get("model"), settings)
        if phase == "validation":
            data = {**data, "proposed_response": self.proposals.get(identity),
                    "normalized_response": self.normalized.get(identity, self.proposals.get(identity))
                    if data.get("accepted") else self.normalized.get(identity)
                    if data.get('rejected_components') is not None else None}
        # Immutable phase files remain the recovery authority. The JSONL contains
        # their complete redacted contents, not references to removable files.
        cleaned = scrub(data, self.secrets)
        durable_write(path, dumps(cleaned))
        sync_dir(path.parent)
        request = self.requests.get(identity)
        if request is None:
            file = self.store.path(f"interactions/{identity}/request.json")
            request = loads(file.read_text()) if file.exists() else {}
            saved = {"id": identity, "request": request}
            for name in ("response", "validation"):
                file = self.store.path(f"interactions/{identity}/{name}.json")
                if file.exists(): saved[name] = loads(file.read_text())
            self.record("recovered_interaction_context", saved, {**request, "interaction_id": identity}, key=(identity, "context"))
        self.record("interaction_" + phase, cleaned, {**request, "interaction_id": identity}, key=(identity, phase))
        if phase == "outcome":
            for cache in (self.requests, self.proposals, self.normalized): cache.pop(identity, None)

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
