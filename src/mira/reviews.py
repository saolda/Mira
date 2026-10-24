"""Local human reviews. These files are never read by the research controller."""
import fcntl
from datetime import datetime, timezone

from .experiments import confined, atomic_text
from .format import dumps, loads, require
from .store import ConflictError, sync_dir

STATUSES = {"approved", "questionable", "incorrect", "needs_investigation"}


class Reviews:
    def __init__(self, catalog): self.catalog = catalog

    def path(self, experiment, decision):
        return confined(self.catalog.home, "reviews", experiment, decision).with_suffix(".json")

    def read(self, experiment, decision):
        path = self.path(experiment, decision)
        require(not path.is_symlink(), "symlink review")
        return loads(path.read_text()) if path.exists() else None

    def save(self, experiment, decision, status, comments, *, expected_revision):
        require(status in STATUSES, "invalid review status")
        require(isinstance(comments, str) and len(comments) <= 20000, "comments must be at most 20000 characters")
        require(type(expected_revision) is int and expected_revision >= 0, "review revision required")
        require(self.catalog.path(experiment).is_dir(), "unknown experiment")
        base = confined(self.catalog.home, "reviews"); base.mkdir(exist_ok=True, mode=0o700)
        directory = confined(base, experiment); directory.mkdir(exist_ok=True, mode=0o700)
        lock_path = directory / ".reviews.lock"
        require(not lock_path.is_symlink(), "symlink review lock")
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            current = self.read(experiment, decision)
            revision = current["revision"] if current else 0
            if expected_revision != revision: raise ConflictError("review changed; reload before saving")
            entry = {"revision": revision + 1, "status": status, "comments": comments,
                     "timestamp": datetime.now(timezone.utc).isoformat()}
            result = {"version": 1, "experiment": experiment, "decision_id": decision, **entry,
                      "history": (current["history"] if current else []) + [entry]}
            atomic_text(self.path(experiment, decision), dumps(result)); sync_dir(directory.parent)
            return result
