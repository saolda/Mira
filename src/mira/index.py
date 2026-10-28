"""Disposable SQLite unit, FTS5, relationship and vector index."""
from __future__ import annotations
from contextlib import closing
from dataclasses import asdict
import json
import os
import sqlite3
import uuid

from .embeddings import cosine, validate_vectors
from .format import digest, dumps, require, validate_corpus
from .store import sync_dir


def records(documents, equations):
    result = []
    for memory in sorted(documents, key=lambda d: d.id):
        result.append({"id": memory.id, "document": memory.id, "type": "document",
                       "label": memory.title, "content": memory.summary,
                       "revision": digest(dumps(asdict(memory)))})
        for unit in memory.units:
            result.append({"id": memory.id + "#" + unit.anchor, "document": memory.id,
                           "type": unit.kind, "label": unit.label,
                           "content": "\n".join(unit.fields.values()), "revision": unit.revision})
    for eq in sorted(equations, key=lambda e: e.id):
        result.append({"id": eq.id, "document": eq.origin, "type": "equation_definition",
                       "label": eq.label, "content": dumps(asdict(eq)), "revision": digest(dumps(asdict(eq)))})
    return sorted(result, key=lambda row: row["id"])


class SemanticDirectory:
    def __init__(self, store, backend=None):
        self.store, self.backend = store, backend
        self.path = store.root / "index.sqlite3"

    @property
    def model(self):
        return self.backend.identity if self.backend else "none"

    def rebuild_locked(self, snapshot=None):
        # The first tuple member is an opaque canonical revision: a Phase 1
        # generation ID or a live content digest. Keep the legacy SQLite key.
        generation, documents, equations, _ = snapshot or self.store.read()
        docs, _, _, edges = validate_corpus(documents, equations)
        rows = records(documents, equations)
        vectors = self.backend.embed([r["label"] + "\n" + r["content"] for r in rows]) if self.backend and rows else []
        dimensions = validate_vectors(vectors, len(rows)) if self.backend else 0
        temporary = self.path.with_name(".index-" + uuid.uuid4().hex + ".sqlite3")
        try:
            with closing(sqlite3.connect(temporary)) as db, db:
                db.executescript('''
                    CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE documents(id TEXT PRIMARY KEY,title TEXT,summary TEXT,revision INTEGER,metadata TEXT);
                    CREATE TABLE units(id TEXT PRIMARY KEY,document TEXT REFERENCES documents(id),type TEXT,label TEXT,content TEXT,revision TEXT,vector TEXT);
                    CREATE VIRTUAL TABLE units_fts USING fts5(id UNINDEXED,label,content);
                    CREATE TABLE edges(source TEXT,target TEXT,type TEXT,status TEXT,owner TEXT REFERENCES documents(id),PRIMARY KEY(source,target,type));
                    CREATE INDEX edges_incoming ON edges(target,status,type);
                    CREATE INDEX edges_outgoing ON edges(source,status,type);
                ''')
                db.executemany("INSERT INTO metadata VALUES (?,?)", [("generation", generation or "empty"), ("model", self.model), ("dimensions", str(dimensions)), ("schema", "2")])
                db.executemany("INSERT INTO documents VALUES (?,?,?,?,?)", [(m.id, m.title, m.summary, m.revision, dumps(m.metadata)) for m in docs.values()])
                for i, row in enumerate(rows):
                    db.execute("INSERT INTO units VALUES (?,?,?,?,?,?,?)", (*[row[k] for k in ("id", "document", "type", "label", "content", "revision")], json.dumps(vectors[i]) if vectors else None))
                    db.execute("INSERT INTO units_fts VALUES (?,?,?)", (row["id"], row["label"], row["content"]))
                db.executemany("INSERT INTO edges VALUES (?,?,?,?,?)", [(e["from"], e["to"], e["type"], e["status"], e["owner"]) for e in edges])
                require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity failure")
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            sync_dir(self.path.parent)
        finally:
            temporary.unlink(missing_ok=True)
        return {"documents": len(documents), "records": len(rows), "relationships": len(edges), "model": self.model, "dimensions": dimensions}

    def rebuild(self):
        with self.store.lock():
            return self.rebuild_locked()

    def _ensure_locked(self):
        snapshot = self.store.read()  # Includes canonical integrity checks on every query.
        fresh = False
        if self.path.exists():
            try:
                with closing(sqlite3.connect(self.path)) as db:
                    meta = dict(db.execute("SELECT key,value FROM metadata"))
                    fresh = meta.get("generation") == (snapshot[0] or "empty") and meta.get("model") == self.model and meta.get("schema") == "2"
            except sqlite3.DatabaseError:
                pass
        if not fresh:
            self.rebuild_locked(snapshot)

    def _query(self, function):
        with self.store.lock():
            self._ensure_locked()
            with closing(sqlite3.connect(self.path)) as db:
                db.row_factory = sqlite3.Row
                return function(db)

    def exact(self, reference):
        return self._query(lambda db: next((dict(row) for row in db.execute(
            "SELECT id,document,type,label,content,revision FROM units WHERE id=?", (reference,))), None))

    def summaries(self):
        return self._query(lambda db: [dict(row) for row in db.execute("SELECT * FROM documents ORDER BY id")])

    def relationships(self, reference, *, direction="outgoing", type=None, statuses=("reviewed", "unverified"), limit=100):
        require(direction in {"incoming", "outgoing"}, "invalid direction")
        require(isinstance(limit, int) and 1 <= limit <= 1000, "limit must be 1..1000")
        require(statuses and all(isinstance(s, str) for s in statuses), "statuses required")
        column = "source" if direction == "outgoing" else "target"
        sql = f"SELECT source,target,type,status,owner FROM edges WHERE {column}=? AND status IN ({','.join('?' for _ in statuses)})"
        params = [reference, *statuses]
        if type:
            sql += " AND type=?"
            params.append(type)
        sql += " ORDER BY source,target,type LIMIT ?"
        params.append(limit)
        return self._query(lambda db: [dict(row) for row in db.execute(sql, params)])

    def search(self, query, *, mode="fulltext", limit=10, type=None):
        require(isinstance(query, str) and query.strip(), "query required")
        require(isinstance(limit, int) and 1 <= limit <= 1000, "limit must be 1..1000")
        require(mode in {"fulltext", "vector"}, "unknown search mode")
        if mode == "fulltext":
            # Literal phrase query prevents FTS operators/syntax errors from user input.
            phrase = '"' + query.replace('"', '""') + '"'
            sql = "SELECT u.id,u.document,u.type,u.label,u.content,u.revision,bm25(units_fts) AS score FROM units_fts JOIN units u ON u.id=units_fts.id WHERE units_fts MATCH ?"
            params = [phrase]
            if type:
                sql += " AND u.type=?"
                params.append(type)
            sql += " ORDER BY score,u.id LIMIT ?"
            return self._query(lambda db: [dict(row) for row in db.execute(sql, [*params, limit])])
        require(self.backend is not None, "configure an embedding backend for vector search")
        def ranked(db):
            # Validate canonical/recovery state in _query before contacting a model.
            vector = self.backend.embed([query], query=True)
            validate_vectors(vector, 1)
            rows = db.execute("SELECT * FROM units" + (" WHERE type=?" if type else ""), (type,) if type else ())
            results = []
            for row in rows:
                result = dict(row)
                result["score"] = cosine(vector[0], json.loads(result.pop("vector")))
                results.append(result)
            return sorted(results, key=lambda r: (-r["score"], r["id"]))[:limit]
        return self._query(ranked)

    def integrity(self):
        def check(db):
            require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite corruption")
            require(not list(db.execute("PRAGMA foreign_key_check")), "index foreign-key violation")
            snapshot = self.store.read()
            expected = records(snapshot[1], snapshot[2])
            actual = [dict(row) for row in db.execute("SELECT id,document,type,label,content,revision FROM units ORDER BY id")]
            require(actual == expected, "index units differ from canonical snapshot")
            expected_docs = [(m.id, m.title, m.summary, m.revision, dumps(m.metadata)) for m in sorted(snapshot[1], key=lambda m: m.id)]
            require([tuple(r) for r in db.execute("SELECT * FROM documents ORDER BY id")] == expected_docs, "index document metadata differs")
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
            stored_vectors = [json.loads(r[0]) for r in db.execute("SELECT vector FROM units ORDER BY id") if r[0] is not None]
            if self.backend:
                dimensions = validate_vectors(stored_vectors, len(expected))
                require(str(dimensions) == metadata["dimensions"], "stored vector dimension mismatch")
            else:
                require(not stored_vectors, "unexpected vectors in lexical index")
            canonical_edges = validate_corpus(snapshot[1], snapshot[2])[3]
            actual_edges = [tuple(row) for row in db.execute("SELECT source,target,type,status,owner FROM edges ORDER BY source,target,type")]
            require(actual_edges == sorted((e["from"], e["to"], e["type"], e["status"], e["owner"]) for e in canonical_edges), "index edges differ from canonical snapshot")
            db.execute("INSERT INTO units_fts(units_fts) VALUES('integrity-check')")
            require([tuple(r) for r in db.execute("SELECT id,label,content FROM units_fts ORDER BY id")] == [(r["id"],r["label"],r["content"]) for r in expected], "FTS content mismatch")
            return {"integrity": "ok", "records": len(actual), "relationships": len(actual_edges)}
        return self._query(check)
