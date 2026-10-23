"""Linux snapshot publication: one durable pointer commits a complete corpus.

Only cooperative writers are serialized. External edits are detected by manifests;
readers never silently ingest changed snapshots. Old generations are retained.
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


class ConflictError(RuntimeError):
    pass


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_write(path, text):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


class SnapshotStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "generations").mkdir(exist_ok=True)

    @contextmanager
    def lock(self):
        with (self.root / ".writer.lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def current(self):
        path = self.root / "CURRENT"
        if not path.exists():
            return None
        value = path.read_text().strip()
        require(re.fullmatch(r"[0-9a-f]{32}", value), "invalid snapshot pointer")
        return value

    def read(self):
        generation = self.current()
        if generation is None:
            return None, [], [], {"r": 1, "s": 1}
        directory = self.root / "generations" / generation
        require(directory.is_dir() and not directory.is_symlink(), "missing/unsafe generation")
        manifest = loads((directory / "manifest.json").read_text())
        require(isinstance(manifest, dict) and set(manifest) == {"parent", "files"}, "invalid manifest")
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        require(actual == set(manifest["files"]) | {"manifest.json"}, "snapshot file inventory changed")
        documents, equations, ledger = [], [], None
        for relative, expected in manifest["files"].items():
            require(re.fullmatch(r"(?:documents/[rs][1-9a-z][0-9a-z]*\.md|equations/e_[rs][1-9a-z][0-9a-z]*_[1-9][0-9]*\.json|identity.json)", relative), "unsafe manifest path")
            path = directory / relative
            require(not path.is_symlink() and not path.parent.is_symlink(), "symlink in canonical snapshot")
            text = path.read_text(encoding="utf-8")
            require(digest(text) == expected, "canonical snapshot changed externally: " + relative)
            if relative.startswith("documents/"):
                memory = parse(text)
                require(path.stem == memory.id, "document filename/ID mismatch")
                documents.append(memory)
            elif relative.startswith("equations/"):
                try:
                    equation = Equation(**loads(text))
                except TypeError as exc:
                    raise ValueError("invalid equation fields") from exc
                require(path.stem == equation.id, "equation filename/ID mismatch")
                equations.append(equation)
            else:
                ledger = loads(text)
        require(isinstance(ledger, dict) and set(ledger) == {"r", "s"}
                and all(type(v) is int and v > 0 for v in ledger.values()), "identity ledger required")
        for memory in documents:
            require(int(memory.id[1:], 36) < ledger[memory.id[0]], "document allocator would reuse ID")
        validate_corpus(documents, equations)
        return generation, documents, equations, ledger

    def publish(self, documents, equations, ledger, expected, fault=None):
        """Caller holds lock. fault is an injection hook for interruption tests."""
        if self.current() != expected:
            raise ConflictError("snapshot changed before commit")
        validate_corpus(documents, equations)
        # The previous snapshot is the identity ledger of committed objects.
        previous, old_docs, old_eqs, old_ledger = self.read()
        require(previous == expected, "snapshot changed")
        new_docs = {d.id: d for d in documents}
        for old in old_docs:
            require(old.id in new_docs, "document removal/retirement unsupported")
            new = new_docs[old.id]
            require(all(new.next_ids[k] >= old.next_ids[k] for k in old.next_ids), "anchor allocator regressed")
            new_units = {u.anchor: u for u in new.units}
            require(all(new_units.get(u.anchor) == u for u in old.units), "existing unit edits/removal unsupported in Phase 1")
            for unit in new.units:
                if unit.anchor not in {u.anchor for u in old.units}:
                    require(int(unit.anchor[1:], 36) >= old.next_ids[unit.anchor[0]], "anchor ID reuse")
        eqs = {eq.id: eq for eq in equations}
        require(all(eqs.get(eq.id) == eq for eq in old_eqs), "equation edits/removal unsupported")
        require(set(ledger) == {"r", "s"} and all(type(v) is int and v >= old_ledger[k] for k, v in ledger.items()), "document allocator regressed")
        old_ids = {d.id for d in old_docs}
        for memory in documents:
            require(int(memory.id[1:], 36) < ledger[memory.id[0]], "document high-water mark")
            if memory.id not in old_ids:
                require(int(memory.id[1:], 36) >= old_ledger[memory.id[0]], "document ID reuse")
        generation = uuid.uuid4().hex
        directory = self.root / "generations" / generation
        directory.mkdir()
        (directory / "documents").mkdir()
        (directory / "equations").mkdir()
        files = {"identity.json": dumps(ledger)}
        files.update({"documents/" + d.id + ".md": render(d) for d in documents})
        files.update({"equations/" + eq.id + ".json": dumps(asdict(eq)) for eq in equations})
        for relative, text in sorted(files.items()):
            durable_write(directory / relative, text)
        durable_write(directory / "manifest.json", dumps({"parent": expected, "files": {p: digest(t) for p, t in sorted(files.items())}}))
        for child in (directory / "documents", directory / "equations", directory, directory.parent):
            sync_dir(child)
        if fault:
            fault("staged")
        # Recheck the previous immutable snapshot immediately before publication.
        self.read()
        if self.current() != expected:
            raise ConflictError("snapshot changed during staging")
        pointer = self.root / (".CURRENT-" + generation)
        durable_write(pointer, generation + "\n")
        os.replace(pointer, self.root / "CURRENT")
        sync_dir(self.root)
        if fault:
            fault("published")
        return generation

    def recovery_status(self):
        """Staged/orphan snapshots are never guessed to be committed."""
        current = self.current()
        committed = set()
        cursor = current
        while cursor:
            require(cursor not in committed and re.fullmatch(r"[0-9a-f]{32}", cursor), "invalid snapshot lineage")
            committed.add(cursor)
            cursor = loads((self.root / "generations" / cursor / "manifest.json").read_text())["parent"]
        return {"current": current, "retained_committed": sorted(committed),
                "unpublished": sorted(p.name for p in (self.root / "generations").iterdir() if p.name not in committed)}
