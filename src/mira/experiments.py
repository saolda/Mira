"""Single active corpus, explicit restricted resets and legacy storage transitions."""
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


class LegacyReader:
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
    def _idle(self, path, *, apply=False):
        """Lease and writer locks stay held through validation/deletion."""
        lease = path / ".runner.lock"
        require(not lease.is_symlink(), "symlink runner lease")
        stream = lease.open("a" if apply else "r") if apply or lease.exists() else None
        try:
            if stream: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with existing_reader(path, blocking=False, exclusive=apply) as store:
                yield store
        finally:
            if stream: stream.close()


    def select(self, name=None):
        if name is None:
            names = self.names()
            require(len(names) == 1, "select --experiment NAME; available experiments: " + ", ".join(names))
            name = names[0]
        path = self.path(name)
        require(path.is_dir(), "unknown experiment: " + name)
        return path


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


class Experiments(LegacyReader):
    """One active corpus in memory/. Legacy paths are read/cleanup compatibility."""
    @property
    def log_home(self):
        return confined(self.home.parent, 'log')

    def active_name(self):
        policy = self.home / 'experiment.json'
        require(not policy.is_symlink(), 'symlink experiment metadata')
        if not policy.exists(): return None
        data = loads(policy.read_text())
        name = data.get('name')
        if name is None and data.get('version') == 1 and data.get('retention') in {'retain', 'disposable'}:
            name = self.home.name  # Legacy explicit --root metadata.
        require(isinstance(name, str) and NAME.fullmatch(name), 'invalid active experiment name')
        return name

    def path(self, name):
        require(isinstance(name, str) and NAME.fullmatch(name), 'invalid experiment name')
        if name == self.active_name(): return self.home
        return confined(self.home, 'research', name)

    def names(self):
        old = super().names()
        # results/ is part of the active corpus, never an experiment.
        old = [n for n in old if (confined(self.home, 'research', n) / 'research/state.json').is_file()]
        active = self.active_name()
        return sorted(set(old + ([active] if active else [])))

    @contextmanager
    def catalog_lock(self):
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = confined(self.home) / '.catalog.lock'
        require(not path.is_symlink(), 'symlink catalog lock')
        with path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(lock, fcntl.LOCK_UN)

    def create(self, name=None, *, disposable=False, reset=False):
        name = name or datetime.now(timezone.utc).strftime('run-%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]
        require(NAME.fullmatch(name), 'invalid experiment name')
        with self.catalog_lock():
            require(not (self.home / '.transition.json').exists(), 'finish pending legacy transition first')
            present = self.active_name() is not None or (self.home / 'research/state.json').exists()
            require(not present or reset, 'active corpus exists; use explicit --new-experiment to replace it')
            require(reset or not (self.home / '.reset.json').exists(), 'interrupted reset; use --new-experiment to finish')
            if present or (self.home / '.reset.json').exists():
                self._reset_active()
            atomic_text(self.home / 'experiment.json', dumps({'version': 2, 'name': name,
                'created_at': datetime.now(timezone.utc).isoformat(), 'layout': 'single-active-corpus'}))
        return self.home

    def _verified(self, store):
        """No deletion until canonical recovery, all terms and submissions are known."""
        from types import SimpleNamespace
        from .interactions import read_records
        from . import glossary, retrieval
        store.read()
        files = store._files()
        committed = {loads(raw).get('interaction_id') for p, raw in files.items() if p.startswith('events/')}
        for record in read_records(store.root):
            require(not any(record.get(phase, {}).get('error') == 'interrupted or corrupt phase file'
                for phase in ('request', 'response', 'validation', 'outcome')), 'corrupt interaction record')
            require('outcome' in record or record['id'] in committed, 'unresolved model interaction')
        require(not retrieval.unresolved(SimpleNamespace(store=store), files), 'uncertain provider submission')
        if 'research/state.json' in files:
            glossary.verify(store, loads(files['research/state.json']))

    def _generated_files(self, root):
        """Explicit owned paths; arbitrary siblings and private inputs are preserved."""
        result = []
        patterns = {'memories': r'[rs][1-9a-z][0-9a-z]*\.md',
            'equations': r'e_[rs][1-9a-z][0-9a-z]*_[1-9][0-9]*\.json',
            'glossary': r'g[1-9][0-9]*\.json', 'events': r'[A-Za-z0-9_-]+\.json'}
        for directory, pattern in patterns.items():
            path = root / directory
            require(not path.is_symlink(), 'symlink generated directory')
            if not path.exists(): continue
            for child in path.iterdir():
                require(not child.is_symlink(), 'symlink generated file')
                if re.fullmatch(pattern, child.name) and child.is_file(): result.append(child)
                # Unrelated files are not generated and remain untouched.
        for relative in ('research/state.json', 'research/question.md', 'research/glossary.md', 'research/glossary.html',
                         'identity.json', 'glossary.sqlite3', 'glossary.sqlite3-wal', 'glossary.sqlite3-shm',
                         'index.sqlite3', 'index.sqlite3-wal', 'index.sqlite3-shm'):
            path = root / relative
            confined(path.parent)
            require(not path.is_symlink(), 'symlink generated file')
            if path.exists():
                require(path.is_file(), 'nonregular generated file'); result.append(path)
        for relative in ('research/results', 'journal', 'interactions', 'retrieval_calls', 'retrieved'):
            path = root / relative
            if path.exists(): result.extend(safe_files(path))
        return sorted(set(result))

    def _reset_active(self):
        # Keep lock inodes throughout reset and reuse them for the next corpus.
        root = self.home
        lease_path, writer_path = root / '.runner.lock', root / '.writer.lock'
        require(not lease_path.is_symlink() and not writer_path.is_symlink(), 'symlink lock')
        with lease_path.open('a') as lease, writer_path.open('a') as writer:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            marker = root / '.reset.json'
            require(not marker.is_symlink(), 'symlink reset marker')
            if marker.exists():
                plan = loads(marker.read_text())
                require(plan.get('version') == 1 and isinstance(plan.get('files'), dict), 'invalid reset receipt')
            else:
                store = LiveStore.__new__(LiveStore); store.root = root
                # An unsuccessful initialization may have no canonical files yet.
                if (root / 'research').is_dir(): self._verified(store)
                generated = self._generated_files(root)
                plan = {'version': 1, 'files': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in generated}}
                atomic_text(marker, dumps(plan))
            owned = {p.relative_to(root).as_posix() for p in self._generated_files(root)}
            for relative, expected in plan['files'].items():
                require(relative in owned or not (root / relative).exists(), 'unsafe reset path')
                require(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'unsafe reset path')
                path = root / relative
                confined(path.parent)
                require(not path.is_symlink(), 'symlink reset path')
                if path.exists():
                    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'reset file changed')
                    path.unlink(); sync_dir(path.parent)
            # Empty journal/receipt directories are harmless; remove only empties.
            for relative in ('journal', 'interactions', 'retrieval_calls', 'retrieved', 'research/results'):
                path = root / relative
                if path.exists():
                    for child in sorted((p for p in path.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                        if not any(child.iterdir()): child.rmdir()
            policy = root / 'experiment.json'
            if policy.exists(): policy.unlink()
            marker.unlink(); sync_dir(root)

    def select(self, name=None):
        require(not (self.home / '.reset.json').exists(), 'interrupted reset; finish explicit new-experiment reset first')
        require(not (self.home / '.transition.json').exists(), 'interrupted migration; resume explicit legacy activation first')
        if name is None and self.active_name() is not None: return self.home
        return super().select(name)

    def cleanup(self, names=(), *, apply=False, older_than_days=None, retention=None):
        """Explicit legacy removal only. Never delete the single active corpus."""
        names = list(dict.fromkeys(names))
        require(not apply or names, '--apply requires explicit --experiment IDs')
        require(retention is None, 'retention catalog superseded; explicitly select legacy runs for cleanup')
        require(older_than_days is None or type(older_than_days) in {int, float} and
            0 <= older_than_days < float('inf'), 'invalid age threshold')
        with self.catalog_lock():
            available = self.names()
            require(all(n in available for n in names), 'unknown or unsafe selected experiment')
            rows, deleted = [], []
            for name in available:
                root = self.path(name)
                row = {'name': name, 'path': str(root), 'selected': name in names, 'eligible': False, 'reasons': []}
                if root == self.home:
                    row.update(status='active_corpus', reasons=['use explicit new-experiment reset']); rows.append(row); continue
                try:
                    safe_files(root)
                    with self._idle(root, apply=apply and name in names) as store:
                        self._verified(store)
                        modified = max(p.stat().st_mtime for p in safe_files(root))
                        row['age_days'] = (time.time() - modified) / 86400
                        require(older_than_days is None or row['age_days'] >= older_than_days, 'younger than age threshold')
                        row.update(eligible=True, status='idle_verified')
                        if apply and name in names:
                            require(shutil.rmtree.avoids_symlink_attacks, 'safe directory deletion unavailable')
                            self._move_diagnostics(root, name)
                            shutil.rmtree(root); sync_dir(root.parent); deleted.append(name)
                except BlockingIOError:
                    row.update(status='active', reasons=['runner or writer lock is held'])
                except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                    row.update(status='recovery_blocked', reasons=[str(exc)])
                row['would_delete'] = row['selected'] and row['eligible']
                rows.append(row)
            return {'applied': apply, 'experiments': rows, 'deleted': deleted, 'run_logs': str(self.log_home)}

    def _move_diagnostics(self, root, name):
        generated = set(self._generated_files(root))
        rows = []
        for path in safe_files(root):
            if path in generated or path.name in {'.writer.lock', '.runner.lock'}: continue
            target = self.log_home / 'legacy' / name / path.relative_to(root)
            confined(target.parent)
            require(not target.exists() and not target.is_symlink(), 'diagnostic destination exists')
            rows.append((path, target, hashlib.sha256(path.read_bytes()).hexdigest()))
        for source, target, expected in rows:
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.rename(source, target)
            require(hashlib.sha256(target.read_bytes()).hexdigest() == expected, 'diagnostic hash changed')
            sync_dir(source.parent); sync_dir(target.parent)

    def export_transcript(self, name, text, *, full):
        require(NAME.fullmatch(name), 'invalid experiment name')
        directory = confined(self.log_home, 'transcripts', name)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / ('full.md' if full else 'concise.md')
        atomic_text(path, text)
        return path

    def import_run(self, source, name, *, transcript=None):
        raise ValueError('per-experiment imports are superseded; select legacy runs for compatible reads')

    def move_run_logs(self):
        """Move historical log files byte-for-byte; never replace a destination."""
        moved = []
        with self.catalog_lock():
            source = confined(self.home, 'run-logs')
            if not source.exists(): return moved
            files = safe_files(source)
            self.log_home.mkdir(parents=True, exist_ok=True, mode=0o700)
            for path in files:
                target = self.log_home / path.relative_to(source)
                confined(target.parent)
                require(not target.exists() and not target.is_symlink(), 'existing log destination')
            for path in files:
                target = self.log_home / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                before = hashlib.sha256(path.read_bytes()).hexdigest()
                os.rename(path, target)
                require(hashlib.sha256(target.read_bytes()).hexdigest() == before, 'log hash changed')
                sync_dir(target.parent); sync_dir(path.parent); moved.append(str(target))
            for path in sorted((p for p in source.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True): path.rmdir()
            source.rmdir(); sync_dir(source.parent)
        return moved

    def activate_legacy(self, name):
        """Explicit, resumable relocation into memory/, preserving exact corpus bytes."""
        require(NAME.fullmatch(name), 'invalid experiment name')
        marker = self.home / '.transition.json'
        with self.catalog_lock():
            require(self.active_name() is None, 'active corpus already exists')
            root = confined(self.home, 'research', name)
            require(root.is_dir(), 'missing legacy corpus')
            require(not marker.is_symlink(), 'symlink transition receipt')
            # Destination locks protect continuation while source locks protect
            # legacy runners throughout the move. Locks themselves are not moved.
            for lock_name in ('.runner.lock', '.writer.lock'):
                require(not (self.home / lock_name).is_symlink(), 'symlink destination lock')
            with (self.home / '.runner.lock').open('a') as lease, (self.home / '.writer.lock').open('a') as writer:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self._idle(root, apply=True) as store:
                    if marker.exists():
                        plan = loads(marker.read_text())
                        require(plan.get('name') == name, 'different transition pending')
                    else:
                        safe_files(root); self._verified(store)
                        generated = set(self._generated_files(root))
                        rows = []
                        for path in safe_files(root):
                            if path.name in {'.writer.lock', '.runner.lock'}: continue
                            relative = path.relative_to(root).as_posix()
                            scientific = path in generated
                            target = (self.home if scientific else self.log_home / 'legacy' / name) / relative
                            confined(target.parent)
                            require(not target.exists() and not target.is_symlink(), 'transition destination exists')
                            rows.append({'relative': relative, 'scientific': scientific,
                                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
                        plan = {'version': 1, 'name': name, 'files': rows}
                        atomic_text(marker, dumps(plan))
                    for row in plan['files']:
                        relative = row['relative']
                        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'unsafe transition path')
                        source = root / relative
                        target = (self.home if row['scientific'] else self.log_home / 'legacy' / name) / relative
                        confined(source.parent); confined(target.parent)
                        require(not source.is_symlink() and not target.is_symlink(), 'symlink transition file')
                        if source.exists():
                            require(not target.exists(), 'ambiguous transition file')
                            require(hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256'], 'source changed during transition')
                            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                            os.rename(source, target); sync_dir(source.parent); sync_dir(target.parent)
                        require(target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == row['sha256'], 'transition hash mismatch')
                    # Validate all relocated canonical/journal records before the
                    # pointer is published; the transition gate remains closed.
                    active = LiveStore.__new__(LiveStore); active.root = self.home; active._storage_transition = True
                    self._verified(active)
                    atomic_text(self.home / 'experiment.json', dumps({'version': 2, 'name': name,
                        'created_at': datetime.now(timezone.utc).isoformat(), 'layout': 'single-active-corpus'}))
                    marker.unlink(); sync_dir(self.home)
                    require(shutil.rmtree.avoids_symlink_attacks, 'safe directory deletion unavailable')
                    shutil.rmtree(root); sync_dir(root.parent)
        return self.home
