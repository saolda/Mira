"""Project-local experiment directories around the existing live store, not a new store."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import time
import uuid

from .format import dumps, loads, require
from .live import LiveStore
from .store import durable_write, sync_dir

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")


def memory_home(value=None):
    return Path(value or os.environ.get("MIRA_MEMORY_DIR") or
                Path(__file__).resolve().parents[2] / "memory").absolute()


def confined(base, *parts):
    base = Path(base).absolute()
    require(not any(p.is_symlink() for p in (base, *base.parents)), "symlink storage root")
    path = base
    for part in parts:
        require(isinstance(part, str) and NAME.fullmatch(part), "invalid local identifier")
        path /= part
        require(not path.is_symlink(), "symlink storage path")
    return path


def atomic_text(path, text):
    require(not path.is_symlink(), "symlink destination")
    temporary = path.with_name("." + path.name + ".tmp-" + uuid.uuid4().hex)
    durable_write(temporary, text)
    os.replace(temporary, path); sync_dir(path.parent)


@contextmanager
def existing_reader(root, *, blocking=True, exclusive=False):
    """Open an existing corpus without creating files or invoking store initialization."""
    root = Path(root).absolute()
    confined(root)
    require(root.is_dir() and not (root / ".writer.lock").is_symlink(), "invalid existing corpus")
    with (root / ".writer.lock").open("rb") as lock:
        fcntl.flock(lock, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | (0 if blocking else fcntl.LOCK_NB))
        try:
            store = LiveStore.__new__(LiveStore); store.root = root
            yield store
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Experiments:
    def __init__(self, home=None):
        self.home = memory_home(home)
        confined(self.home)

    def path(self, name):
        return confined(self.home, "research", name)

    def names(self):
        base = confined(self.home, "research")
        if not base.exists(): return []
        return sorted(p.name for p in base.iterdir() if NAME.fullmatch(p.name) and not p.is_symlink() and p.is_dir())

    @contextmanager
    def catalog_lock(self):
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        confined(self.home, "research").mkdir(exist_ok=True, mode=0o700)
        path = self.home / ".catalog.lock"
        require(not path.is_symlink(), "symlink catalog lock")
        with path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(lock, fcntl.LOCK_UN)

    def create(self, name=None, *, disposable=False):
        name = name or datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        with self.catalog_lock():
            path = self.path(name)
            require(not path.exists(), "experiment already exists: " + name)
            path.mkdir(mode=0o700); sync_dir(path.parent)
            atomic_text(path / "experiment.json", dumps({"version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "retention": "disposable" if disposable else "retain"}))
        return path

    @contextmanager
    def _idle(self, path, *, apply=False):
        """Lease and writer locks stay held through validation/archive/deletion."""
        lease = path / ".runner.lock"
        require(not lease.is_symlink(), "symlink runner lease")
        stream = lease.open("a" if apply else "r") if apply or lease.exists() else None
        try:
            if stream: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with existing_reader(path, blocking=False, exclusive=apply) as store:
                yield store
        finally:
            if stream: stream.close()

    def _inventory(self, name, *, store=None):
        path = self.path(name)
        row = {"name": name, "path": str(path), "bytes": 0, "retention": "unclassified",
               "status": "incomplete", "eligible": False, "reasons": []}
        try:
            files = safe_files(path)
            row["bytes"] = sum(p.stat().st_size for p in files)
            modified = max((p.stat().st_mtime for p in files if p.name not in {".runner.lock", ".writer.lock"}), default=path.stat().st_mtime)
            row.update(modified_at=datetime.fromtimestamp(modified, timezone.utc).isoformat(), age_days=(time.time() - modified) / 86400)
            policy = path / "experiment.json"
            if policy.exists():
                data = loads(policy.read_text())
                require(data.get("version") == 1 and data.get("retention") in {"retain", "disposable"}, "invalid experiment retention metadata")
                row.update(retention=data["retention"], created_at=data["created_at"])
            else: row["created_at"] = row["modified_at"]
            def inspect(current):
                current.read()  # Gates incomplete journals and unregistered edits.
                canonical = current._files()
                state = loads(canonical.get("research/state.json", "{}"))
                require(state.get("mira_research") in {1, 2}, "missing or unknown research state")
                from .interactions import read_records
                committed = {loads(raw).get("interaction_id") for p, raw in canonical.items() if p.startswith("events/")}
                for record in read_records(path):
                    require(not any(record.get(phase, {}).get("error") == "interrupted or corrupt phase file" for phase in ("request", "response", "validation", "outcome")), "corrupt interaction record")
                    require("outcome" in record or record["id"] in committed, "unresolved model interaction")
                from .glossary import verify
                verify(current, state)
                pending = state.get("pending_synthesis") or state.get("synthesis_candidate_order") or any(
                    n.get("pending_results") or n.get("legacy_pending_results") or n.get("status") in {"living", "exhausted"}
                    for n in state.get("nodes", {}).values())
                row["status"] = "completed" if state.get("terminal_event") and not pending else "incomplete"
            if store is not None: inspect(store)
            else:
                with self._idle(path) as current: inspect(current)
        except BlockingIOError:
            row.update(status="active", reasons=["runner or writer lock is held"])
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            row.update(status="recovery_blocked", reasons=[str(exc)])
        if row["retention"] != "disposable": row["reasons"].append("not explicitly designated disposable")
        if row["status"] != "completed": row["reasons"].append("experiment is not safely completed")
        row["eligible"] = not row["reasons"]
        return row

    def cleanup(self, names=(), *, apply=False, older_than_days=None, retention=None):
        require(older_than_days is None or type(older_than_days) in {int, float} and
                older_than_days >= 0 and older_than_days < float("inf"), "invalid age threshold")
        require(retention in {None, "retain", "disposable"}, "invalid retention policy")
        names = list(dict.fromkeys(names))
        require(not apply or names, "--apply requires explicit --experiment IDs")
        require(retention is None or names, "retention changes require explicit --experiment IDs")
        for name in names: require(NAME.fullmatch(name), "invalid experiment name")
        with self.catalog_lock():
            available = self.names()
            require(all(name in available for name in names), "unknown or unsafe selected experiment")
            rows = [self._inventory(name) for name in available]
            for row in rows:
                row["selected"] = row["name"] in names
                if older_than_days is not None and row.get("age_days", 0) < older_than_days:
                    row["eligible"] = False; row["reasons"].append("younger than age threshold")
                row["would_delete"] = row["selected"] and row["eligible"] and retention is None
                if row["selected"] and retention: row["would_set_retention"] = retention
            deleted, updated, archives = [], [], []
            if apply:
                for row in rows:
                    if not row["selected"]: continue
                    path = self.path(row["name"])
                    if retention:
                        # A designation never deletes an experiment. It is a
                        # separate explicit step for legacy/unclassified runs.
                        try:
                            with self._idle(path, apply=True):
                                data = loads((path / "experiment.json").read_text()) if (path / "experiment.json").exists() else {
                                    "version": 1, "created_at": row["created_at"]}
                                atomic_text(path / "experiment.json", dumps({**data, "retention": retention}))
                                updated.append(row["name"])
                        except (BlockingIOError, OSError, ValueError, RuntimeError) as exc:
                            row["reasons"].append(str(exc))
                        continue
                    if not row["would_delete"]: continue
                    try:
                        with self._idle(path, apply=True) as store:
                            current = self._inventory(row["name"], store=store)
                            require(current["eligible"], "experiment eligibility changed")
                            if older_than_days is not None: require(current["age_days"] >= older_than_days, "experiment age changed")
                            archives.append(self._archive(store))
                            # rmtree's fd-based implementation does not follow
                            # replaced directory symlinks. Refuse unsupported OSes.
                            require(shutil.rmtree.avoids_symlink_attacks, "safe directory deletion unavailable")
                            shutil.rmtree(path)
                            sync_dir(path.parent); deleted.append(row["name"])
                    except (OSError, ValueError, RuntimeError) as exc:
                        row["reasons"].append(str(exc))
            return {"applied": apply, "experiments": rows, "deleted": deleted,
                    "updated_retention": updated, "archive_logs": archives,
                    "run_logs": str(confined(self.home, "run-logs"))}

    def _archive(self, store):
        """Preserve inspectable records before removing disposable recovery files."""
        from .interactions import ExecutionLog, read_records, configured_secrets
        log = ExecutionLog(confined(self.home, "run-logs"), store.root, command="research-cleanup archive", secrets=configured_secrets())
        try:
            for record in read_records(store.root):
                log.append("archived_interaction", record, interaction_id=record["id"])
            files = store._files()
            for path in store.path("glossary").glob("g*.json"):
                files[path.relative_to(store.root).as_posix()] = path.read_text()
            for path, content in sorted(files.items()):
                log.append("archived_canonical_file", {"path": path, "content": content})
            log.reason = "disposable_experiment_archived"
        except BaseException as exc:
            log.close(exc); raise
        log.close()
        return str(log.path)

    def select(self, name=None):
        if name is None:
            names = self.names()
            require(len(names) == 1, "select --experiment NAME; available experiments: " + ", ".join(names))
            name = names[0]
        path = self.path(name)
        require(path.is_dir(), "unknown experiment: " + name)
        return path

    def export_transcript(self, name, text, *, full):
        confined(self.home, "transcripts").mkdir(exist_ok=True, mode=0o700)
        directory = confined(self.home, "transcripts", name)
        directory.mkdir(exist_ok=True, mode=0o700)
        path = directory / ("full.md" if full else "concise.md")
        atomic_text(path, text)
        return path

    def import_run(self, source, name, *, transcript=None):
        """Explicit, verified copy. Source stays intact; conflicting targets never merge."""
        source = Path(source).absolute()
        require(not source.is_relative_to(self.path(name)) and not self.path(name).is_relative_to(source),
                "source and destination must be separate")
        transcript_bytes = None
        if transcript is not None:
            transcript_path = Path(transcript).absolute()
            confined(transcript_path.parent)
            require(not transcript_path.is_symlink(), "symlink transcript")
            transcript_bytes = transcript_path.read_bytes()
        with self.catalog_lock(), existing_reader(source) as store:
            store.read()  # Validate the existing journal/corpus without touching the source.
            destination = self.path(name)
            require(not destination.exists(), "experiment already exists: " + name)
            import_record = confined(self.home, "imports", name).with_suffix(".json")
            require(not import_record.exists() and not import_record.is_symlink(), "import record already exists")
            if transcript_bytes is not None:
                old_export = confined(self.home, "transcripts", name) / "imported-original.md"
                require(not old_export.exists() and not old_export.is_symlink(), "imported transcript already exists")
            inventory = file_hashes(source)
            staging = destination.parent / (".import-" + uuid.uuid4().hex)
            # No exception cleanup: an interrupted/failed copy remains inspectable.
            shutil.copytree(source, staging)
            require(file_hashes(staging) == inventory and file_hashes(source) == inventory, "import contents changed while copying")
            with existing_reader(staging) as copy:
                copy.read()
            for path in staging.rglob("*"):
                if path.is_file():
                    with path.open("rb") as stream: os.fsync(stream.fileno())
            for path in sorted((p for p in staging.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                sync_dir(path)
            sync_dir(staging)
            os.rename(staging, destination); sync_dir(destination.parent)
            imports = confined(self.home, "imports"); imports.mkdir(exist_ok=True, mode=0o700)
            atomic_text(imports / (name + ".json"), dumps({"source": str(source), "experiment": name,
                "imported_at": datetime.now(timezone.utc).isoformat(), "file_hashes": inventory,
                "source_preserved": True}))
        if transcript_bytes is not None:
            transcripts = confined(self.home, "transcripts"); transcripts.mkdir(exist_ok=True, mode=0o700)
            directory = confined(transcripts, name); directory.mkdir(exist_ok=True, mode=0o700)
            original = directory / "imported-original.md"
            require(not original.exists(), "imported transcript already exists")
            # Preserve the exported original byte-for-byte, including line endings.
            with original.open("xb") as stream:
                stream.write(transcript_bytes); stream.flush(); os.fsync(stream.fileno())
            sync_dir(directory)
        return destination


def file_hashes(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        require(not path.is_symlink(), "symlink in experiment: " + str(path))
        if path.is_file(): result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        else: require(path.is_dir(), "nonregular experiment artifact")
    return result


def safe_files(root):
    """Inventory regular files without traversing any symlink or special file."""
    require(root.is_dir() and not root.is_symlink(), "unsafe experiment directory")
    files = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        for name in [*names, *filenames]:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), "symlink or special file in experiment")
            if stat.S_ISREG(mode): files.append(path)
    return files
