"""Project-local experiment directories around the existing live store, not a new store."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
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
def existing_reader(root):
    """Open an existing corpus without creating files or invoking store initialization."""
    root = Path(root).absolute()
    confined(root)
    require(root.is_dir() and not (root / ".writer.lock").is_symlink(), "invalid existing corpus")
    with (root / ".writer.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
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
        return sorted(p.name for p in base.iterdir() if NAME.fullmatch(p.name) and p.is_dir() and not p.is_symlink())

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

    def create(self, name=None):
        name = name or datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        with self.catalog_lock():
            path = self.path(name)
            require(not path.exists(), "experiment already exists: " + name)
            path.mkdir(mode=0o700); sync_dir(path.parent)
        return path

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
