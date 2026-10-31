"""Live canonical files with inspectable, explicitly repaired operations.

All public read/publish calls require lock(). Recovery entry points lock themselves.
Only cooperating local Linux processes are covered; raw file reads are not atomic.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import re
import uuid

from .format import Equation, digest, dumps, loads, parse, render, require, validate_corpus
from .store import ConflictError, durable_write, sync_dir, validate_transition
from .glossary import TERM_PATH, validate_record, validate_transaction as validate_glossary_transaction


class RecoveryRequired(RuntimeError):
    pass


ID = re.compile(r"[0-9a-f]{32}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
CANONICAL = re.compile(
    r"(?:memories/[rs][1-9a-z][0-9a-z]*\.md|"
    r"equations/e_[rs][1-9a-z][0-9a-z]*_[1-9][0-9]*\.json|"
    r"identity\.json|research/state\.json|research/question\.md|glossary/g[1-9][0-9]*\.json|"
    r"research/results/[A-Za-z0-9_-]+\.json|events/[A-Za-z0-9_-]+\.json)\Z")


def revision(files):
    # Sparse glossary after-images are committed by the hash chain in state.
    return digest(dumps({p: digest(t) for p, t in sorted(files.items()) if not TERM_PATH.fullmatch(p)}))


def hash_revision(hashes):
    return digest(dumps({p: h for p, h in sorted(hashes.items()) if not TERM_PATH.fullmatch(p)}))


def decode(files):
    """Validate a complete prospective canonical view without writing it."""
    documents, equations = [], []
    for name, text in sorted(files.items()):
        require(CANONICAL.fullmatch(name), "unsafe canonical path")
        if name == "research/question.md":
            require("research/state.json" in files, "question Markdown requires research state")
            from .questions import parse as parse_question
            parse_question(text)
            continue
        if TERM_PATH.fullmatch(name):
            record = loads(text)
            validate_record(record)
            require(name == "glossary/" + record["id"] + ".json", "glossary filename mismatch")
            continue
        if name.startswith("memories/"):
            memory = parse(text)
            require(memory.id == Path(name).stem, "document filename/ID mismatch")
            documents.append(memory)
        elif name.startswith("equations/"):
            equation = Equation(**loads(text))
            require(equation.id == Path(name).stem, "equation filename/ID mismatch")
            equations.append(equation)
        else:
            require(isinstance(loads(text), dict), "canonical JSON object required")
    ledger = loads(files["identity.json"]) if files else {"r": 1, "s": 1}
    require(set(ledger) == {"r", "s"} and
            all(type(v) is int and v > 0 for v in ledger.values()), "invalid identity ledger")
    for doc in documents:
        require(int(doc.id[1:], 36) < ledger[doc.id[0]], "document allocator would reuse ID")
    validate_corpus(documents, equations)
    validate_lineage(documents)
    if "research/state.json" in files:
        state = loads(files["research/state.json"])
        if "mira_research" in state:
            from .research_tree import validate
            validate(state, documents, files)
    return documents, equations, ledger


def validate_lineage(documents):
    """Opt-in metadata contract; ordinary foundation memories remain valid."""
    docs = {m.id: m for m in documents}
    managed = {m.id: m for m in documents if "node_id" in m.metadata}
    for m in managed.values():
        meta = m.metadata
        require(isinstance(meta["node_id"], str) and bool(re.fullmatch(r"q[1-9][0-9]*", meta["node_id"])),
                "invalid originating node ID")
        require(meta.get("kind") == ("research" if m.id.startswith("r") else "synthesis"), "memory kind mismatch")
        require("synthesized_by" in meta and "source_memories" in meta, "lineage fields required")
        sources = meta["source_memories"]
        require(isinstance(sources, list) and all(isinstance(s, str) for s in sources), "invalid source list")
        require(len(sources) == len(set(sources)) and m.id not in sources, "duplicate/self synthesis input")
        require(not sources if meta["kind"] == "research" else len(sources) >= 2,
                "synthesis requires at least two sources")
        consumer = meta["synthesized_by"]
        require(consumer is None or isinstance(consumer, str), "invalid consumer")
        if consumer is not None:
            require(consumer in managed and m.id in managed[consumer].metadata["source_memories"],
                    "missing reciprocal synthesis lineage")
        for source in sources:
            require(source in docs and source in managed and
                    docs[source].metadata["synthesized_by"] == m.id, "missing source/consumption mark")
    # Iterative walk also rejects cycles without imposing a depth limit.
    for identity in managed:
        seen = set()
        while identity is not None:
            require(identity not in seen, "cyclic synthesis lineage")
            seen.add(identity)
            identity = managed[identity].metadata["synthesized_by"]


class LiveStore:
    live = True

    def __init__(self, root):
        self.root = Path(root).absolute()
        require(not any(p.is_symlink() for p in (self.root, *self.root.parents)), "symlink store root/ancestor")
        self.root.mkdir(parents=True, exist_ok=True)
        sync_dir(self.root.parent)
        require(not (self.root / "CURRENT").exists() and not (self.root / "generations").exists(),
                "cannot open snapshot corpus as live storage")
        for relative in ("memories", "equations", "research", "research/results", "events", "journal", "glossary"):
            path = self.path(relative)
            path.mkdir(exist_ok=True)
            sync_dir(path.parent)

    def path(self, relative):
        p = Path(relative)
        require(not p.is_absolute() and p.parts and all(s not in {".", ".."} for s in p.parts), "unsafe relative path")
        target = self.root
        # Include root ancestors, not just the final path, in symlink checks.
        require(not any(parent.is_symlink() for parent in (self.root, *self.root.parents)), "symlink root ancestor")
        for part in p.parts:
            target /= part
            require(not target.is_symlink(), "symlink path: " + relative)
        return target

    @contextmanager
    def lock(self):
        with self.path(".writer.lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def _replace(self, relative, text):
        path = self.path(relative)
        temporary = self.path(str(path.relative_to(self.root)) + ".tmp-" + uuid.uuid4().hex)
        durable_write(temporary, text)
        os.replace(temporary, path)
        sync_dir(path.parent)

    def _files(self):
        result = {}
        for base in ("memories", "equations", "research", "events"):
            for p in self.path(base).rglob("*"):
                # Protected legacy corpora can coexist during an explicit storage
                # transition. They are independent stores, never active after-images.
                relative_parts = p.relative_to(self.root).parts
                if base == 'research' and len(relative_parts) > 2:
                    legacy = self.root / 'research' / relative_parts[1]
                    if (legacy / '.writer.lock').is_file() and (legacy / 'research').is_dir(): continue
                self.path(p.relative_to(self.root).as_posix())
                if p.is_file():
                    relative = p.relative_to(self.root).as_posix()
                    # Atomic-write leftovers are not canonical, and remain inspectable.
                    if re.search(r"\.tmp-[0-9a-f]{32}\Z", p.name):
                        continue
                    if relative in {"research/glossary.md", "research/glossary.html"}:
                        continue  # Explicitly regenerated, disposable export.
                    require(CANONICAL.fullmatch(relative), "unexpected canonical file: " + relative)
                    result[relative] = p.read_bytes().decode("utf-8")
        ledger = self.path("identity.json")
        if ledger.exists():
            result["identity.json"] = ledger.read_text(encoding="utf-8")
        return result

    def _journals(self):
        manifests = []
        for p in self.path("journal").iterdir():
            self.path(p.relative_to(self.root).as_posix())
            if p.suffix != ".json":
                continue
            manifest = loads(p.read_text(encoding="utf-8"))
            self._validate_manifest(manifest, p.stem)
            manifests.append(manifest)
        manifests.sort(key=lambda m: m["sequence"])
        previous = revision({})
        for number, m in enumerate(manifests, 1):
            require(m["sequence"] == number and m["before_revision"] == previous,
                    "conflicting or missing journal operation")
            require(number == len(manifests) or m["status"] == "committed", "multiple incomplete operations")
            previous = m["after_revision"]
        return manifests

    def _validate_manifest(self, m, identity):
        require(isinstance(m, dict) and set(m) == {"version", "id", "sequence", "type", "context", "status",
                "before_revision", "after_revision", "files"}, "invalid journal fields")
        require(type(m["version"]) is int and m["version"] == 1 and ID.fullmatch(identity) and m["id"] == identity, "invalid operation ID/version")
        require(type(m["sequence"]) is int and m["sequence"] > 0, "invalid operation sequence")
        require(isinstance(m["type"], str) and bool(m["type"]) and isinstance(m["context"], dict), "invalid operation context")
        require(m["status"] in {"prepared", "applying", "committed"}, "invalid journal status")
        require(all(isinstance(m[k], str) and HASH.fullmatch(m[k]) for k in ("before_revision", "after_revision")), "invalid revision hash")
        require(isinstance(m["files"], list) and m["files"], "empty journal operation")
        paths = set()
        for index, entry in enumerate(m["files"]):
            require(isinstance(entry, dict) and set(entry) == {"path", "before", "after", "payload", "completed"}, "invalid file entry")
            name = entry["path"]
            require(isinstance(name, str) and CANONICAL.fullmatch(name) and name not in paths, "unsafe/duplicate journal path")
            paths.add(name)
            require(entry["payload"] == f"journal/{identity}/{index}.txt", "unsafe staged payload path")
            require(type(entry["completed"]) is bool, "invalid progress")
            require(entry["before"] is None or isinstance(entry["before"], str) and HASH.fullmatch(entry["before"]), "invalid precondition")
            require(isinstance(entry["after"], str) and HASH.fullmatch(entry["after"]), "invalid after hash")
            self.path(name)
            self.path(entry["payload"])

    def read(self):
        if not getattr(self, '_storage_transition', False) and any(
                (self.root / name).exists() for name in ('.transition.json', '.reset.json')):
            raise RecoveryRequired('incomplete storage transition; explicitly resume migration/reset')
        manifests = self._journals()
        orphans = self._orphans(manifests)
        if orphans or manifests and manifests[-1]["status"] != "committed":
            raise RecoveryRequired("incomplete/unpublished operation; run recovery inspect")
        files = self._files()
        token = revision(files)
        require(token == (manifests[-1]["after_revision"] if manifests else revision({})),
                "canonical files differ from committed operation")
        return (token, *decode(files))

    def _orphans(self, manifests):
        known = {m["id"] for m in manifests}
        return sorted(p.name for p in self.path("journal").iterdir() if p.is_dir() and p.name not in known)

    def publish(self, documents, equations, ledger, expected, fault=None, *, files=None,
                operation_type="knowledge", context=None):
        old_token, old_docs, old_eqs, old_ledger = self.read()
        if old_token != expected:
            raise ConflictError("live corpus changed before commit")
        require(isinstance(operation_type, str) and bool(operation_type), "operation type required")
        require(context is None or isinstance(context, dict), "operation context must be an object")
        loads(dumps(context))  # Reject invalid context before creating staged artifacts.
        validate_corpus(documents, equations)
        validate_transition(documents, equations, ledger, old_docs, old_eqs, old_ledger)
        old = self._files()
        # Read only touched glossary records. All other terms stay on disk.
        for name in files or {}:
            if isinstance(name, str) and TERM_PATH.fullmatch(name):
                path = self.path(name)
                if path.exists(): old[name] = path.read_text(encoding="utf-8")
        proposed = dict(old)
        extras = dict(files or {})
        for name, text in extras.items():
            require(isinstance(name, str) and CANONICAL.fullmatch(name) and
                    (name.startswith("research/") or name.startswith("events/") or TERM_PATH.fullmatch(name)), "invalid auxiliary path")
            require(isinstance(text, str), "auxiliary text required")
            if name != "research/question.md":
                require(isinstance(loads(text), dict), "auxiliary JSON required")
            if name != "research/state.json" and not TERM_PATH.fullmatch(name):
                require(name not in old or old[name] == text, "evidence/events are immutable")
        proposed.update(extras)
        proposed.update({"memories/" + d.id + ".md": render(d) for d in documents})
        proposed.update({"equations/" + e.id + ".json": dumps(asdict(e)) for e in equations})
        proposed["identity.json"] = dumps(ledger)
        validate_glossary_transaction(old, proposed)
        decode(proposed)
        if "research/state.json" in old and "mira_research" in loads(old["research/state.json"]):
            from .research_tree import validate_transition as validate_tree_transition
            validate_tree_transition(loads(old["research/state.json"]), loads(proposed["research/state.json"]))
        for old_doc in old_docs:
            new_doc = next(d for d in documents if d.id == old_doc.id)
            if new_doc != old_doc:
                require(new_doc.revision > old_doc.revision, "changed document requires newer revision")
            if "node_id" in old_doc.metadata:
                for key in ("node_id", "kind", "source_memories"):
                    require(new_doc.metadata.get(key) == old_doc.metadata[key], "immutable lineage changed")
                if old_doc.metadata["synthesized_by"] is not None:
                    require(new_doc.metadata.get("synthesized_by") == old_doc.metadata["synthesized_by"], "memory already consumed")
        changed = [p for p in proposed if old.get(p) != proposed[p]]
        if not changed:
            return expected
        # New documents first, then edits, auxiliary evidence, ledger and state last.
        def order(p):
            return (3 if p == "research/state.json" else 2 if p == "identity.json" else
                    0 if p.startswith("memories/") and p not in old else 1, p)
        changed.sort(key=order)
        identity = uuid.uuid4().hex
        payload_dir = self.path("journal/" + identity)
        payload_dir.mkdir()
        sync_dir(payload_dir.parent)
        entries = []
        for index, name in enumerate(changed):
            payload = f"journal/{identity}/{index}.txt"
            durable_write(self.path(payload), proposed[name])
            entries.append({"path": name, "before": digest(old[name]) if name in old else None,
                            "after": digest(proposed[name]), "payload": payload, "completed": False})
        sync_dir(payload_dir)
        details = dict(context or {})
        details.update({"affected_ids": [Path(p).stem for p in changed if p.startswith("memories/")],
                        "allocated_ids": [d.id for d in documents if d.id not in {o.id for o in old_docs}],
                        "source_memories": {d.id: d.metadata["source_memories"] for d in documents
                                            if d.id not in {o.id for o in old_docs} and d.metadata.get("kind") == "synthesis"},
                        "expected_state_revision": digest(old["research/state.json"]) if "research/state.json" in old else None})
        if any(TERM_PATH.fullmatch(p) for p in changed):
            from .glossary import metadata
            details["glossary_before"] = metadata(loads(old.get("research/state.json", "{}")))
        m = {"version": 1, "id": identity, "sequence": len(self._journals()) + 1,
             "type": operation_type, "context": details, "status": "prepared",
             "before_revision": expected, "after_revision": revision(proposed), "files": entries}
        self._validate_manifest(m, identity)
        if fault:
            fault("staged")
        self._save_manifest(m)
        if fault:
            fault("prepared")
        # Catch external changes made while staging, before touching canonical bytes.
        require(revision(self._files()) == expected, "canonical precondition changed")
        self._apply(m, fault)
        return m["after_revision"]

    def _save_manifest(self, m):
        self._replace("journal/" + m["id"] + ".json", dumps(m))

    def _assessment(self, m):
        actual = self._files()
        for entry in m["files"]:
            if TERM_PATH.fullmatch(entry["path"]):
                path = self.path(entry["path"])
                if path.exists(): actual[entry["path"]] = path.read_text(encoding="utf-8")
        prospective = dict(actual)
        before_hashes = {p: digest(t) for p, t in actual.items()}
        completed, remaining, problems = [], [], []
        for entry in m["files"]:
            name = entry["path"]
            current = digest(actual[name]) if name in actual else None
            if current == entry["after"]:
                completed.append(name)
            elif current == entry["before"]:
                remaining.append(name)
            else:
                problems.append("unexpected bytes: " + name)
            if entry["before"] is None:
                before_hashes.pop(name, None)
            else:
                before_hashes[name] = entry["before"]
            # Completed files need no payload to finalize; pending files always do.
            if current != entry["after"]:
                payload = self.path(entry["payload"])
                if not payload.is_file():
                    problems.append("missing payload: " + name)
                else:
                    text = payload.read_bytes().decode("utf-8")
                    if digest(text) != entry["after"]:
                        problems.append("damaged payload: " + name)
                    else:
                        prospective[name] = text
        if hash_revision(before_hashes) != m["before_revision"]:
            problems.append("unrelated canonical changes")
        try:
            require(revision(prospective) == m["after_revision"], "prospective revision mismatch")
            decode(prospective)
            touched = {entry["path"]: prospective[entry["path"]] for entry in m["files"] if TERM_PATH.fullmatch(entry["path"])}
            if touched:
                from .glossary import commitment, metadata
                before = m["context"].get("glossary_before")
                require(isinstance(before, dict), "glossary recovery lacks prior commitment")
                after = metadata(loads(prospective["research/state.json"]))
                require(after["revision"] == before["revision"] + 1 and
                        after["commitment"] == commitment(before["commitment"], touched), "glossary recovery commitment mismatch")
        except (ValueError, TypeError, KeyError) as exc:
            problems.append(str(exc))
        return {"id": m["id"], "type": m["type"], "context": m["context"], "status": m["status"],
                "assessment": "ambiguous" if problems else "complete" if not remaining else "safely_finishable",
                "safely_cancellable": not problems and not completed,
                "completed": completed, "remaining": remaining, "problems": problems,
                "files": m["files"]}

    def _apply(self, m, fault=None):
        assessment = self._assessment(m)
        require(assessment["assessment"] != "ambiguous", "unsafe recovery: " + str(assessment["problems"]))
        m["status"] = "applying"
        self._save_manifest(m)
        for entry in m["files"]:
            path = self.path(entry["path"])
            current = digest(path.read_bytes().decode("utf-8")) if path.exists() else None
            if current != entry["after"]:
                require(current == entry["before"], "file changed during apply")
                text = self.path(entry["payload"]).read_bytes().decode("utf-8")
                require(digest(text) == entry["after"], "payload changed during apply")
                self._replace(entry["path"], text)
            if fault:
                fault("replaced:" + entry["path"])
            entry["completed"] = True
            self._save_manifest(m)
            if fault:
                fault("progress:" + entry["path"])
        require(revision(self._files()) == m["after_revision"], "commit revision mismatch")
        decode(self._files())
        for entry in m["files"]:
            if TERM_PATH.fullmatch(entry["path"]):
                require(digest(self.path(entry["path"]).read_text(encoding="utf-8")) == entry["after"], "glossary commit hash mismatch")
        if fault:
            fault("before_commit")
        m["status"] = "committed"
        self._save_manifest(m)
        if fault:
            fault("committed")

    def recovery_status(self):
        """Read-only assessment; malformed journals are reported, never ignored."""
        with self.lock():
            try:
                manifests = self._journals()
                orphans = self._orphans(manifests)
                pending = [self._assessment(m) for m in manifests if m["status"] != "committed"]
                problems = []
                if not pending:
                    files = self._files()
                    require(revision(files) == (manifests[-1]["after_revision"] if manifests else revision({})), "canonical revision mismatch")
                    decode(files)
                    if "research/state.json" in files:
                        from .glossary import verify
                        verify(self, loads(files["research/state.json"]), manifests)
                return {"operations": pending, "committed": [m["id"] for m in manifests if m["status"] == "committed"],
                        "unpublished": orphans, "blocked": bool(pending or orphans), "problems": problems}
            except (ValueError, TypeError, KeyError, OSError) as exc:
                return {"blocked": True, "assessment": "ambiguous", "problems": [str(exc)]}

    def repair(self, operation_id, *, apply=False, fault=None):
        """Dry run by default. Explicit forward repair never regenerates research."""
        require(isinstance(operation_id, str) and ID.fullmatch(operation_id), "invalid operation ID")
        with self.lock():
            manifests = self._journals()
            require(not self._orphans(manifests), "unpublished staging requires human judgment")
            m = next((m for m in manifests if m["id"] == operation_id), None)
            require(m is not None, "unknown operation")
            if m["status"] == "committed":
                self.read()
                return {"id": operation_id, "assessment": "committed", "applied": False}
            result = self._assessment(m)
            result["applied"] = False
            if apply:
                require(result["assessment"] != "ambiguous", "ambiguous operation requires human judgment")
                self._apply(m, fault)
                result["applied"] = True
            return result
