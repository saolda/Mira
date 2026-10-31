"""Source-grounded term records and a disposable, bounded SQLite directory.

Call directory methods under the live-store lock. Only rebuild/export enumerate
all terms; ordinary lookups deserialize at most the selected/touched records.
"""
from contextlib import closing
from copy import deepcopy
import re
import sqlite3
import unicodedata

from .format import digest, dumps, loads, require
from . import r1

TERM_PATH = re.compile(r"glossary/g[1-9][0-9]*\.json\Z")
TERM_ID = re.compile(r"g[1-9][0-9]*\Z")
RELATIONS = {"SYNONYM_OF", "BROADER_THAN", "NARROWER_THAN", "RELATED_TO"}
EMPTY = digest("")


def normalize(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[-‐‑–—]", " ", value).split())


def metadata(state):
    return state.get("glossary", {"next_id": 1, "revision": 0, "commitment": EMPTY,
                                  "token_budget": 3200, "limit": 12})


def validate_metadata(value):
    require(isinstance(value, dict) and set(value) == {"next_id", "revision", "commitment", "token_budget", "limit"}, "invalid glossary metadata")
    require(all(type(value[k]) is int and value[k] >= (0 if k == "revision" else 1)
                for k in ("next_id", "revision", "token_budget", "limit")), "invalid glossary allocator/budget")
    require(value["limit"] <= 15 and re.fullmatch(r"[0-9a-f]{64}", value["commitment"]), "invalid glossary commitment/limit")
    require(value["token_budget"] >= 128, "glossary budget must be at least 128")


def commitment(previous, files):
    return digest(dumps({"previous": previous, "terms": {p: digest(t) for p, t in sorted(files.items())}}))


def validate_transaction(old, proposed):
    """Bind sparse term after-images into the ordinary canonical revision."""
    changed = {p: t for p, t in proposed.items() if TERM_PATH.fullmatch(p) and old.get(p) != t}
    before = metadata(loads(old.get("research/state.json", "{}")))
    after = metadata(loads(proposed.get("research/state.json", "{}")))
    validate_metadata(after)
    if changed:
        require(after["revision"] == before["revision"] + 1 and
                after["commitment"] == commitment(before["commitment"], changed), "glossary update lacks state commitment")
        new_ids = []
        for path, raw in changed.items():
            record = loads(raw); validate_record(record)
            require(path == "glossary/" + record["id"] + ".json" and int(record["id"][1:]) < after["next_id"], "invalid glossary ID allocation")
            if path in old:
                previous = loads(old[path])
                require(record["id"] == previous["id"] and record["key"] == previous["key"] and
                        record["term"] == previous["term"], "glossary identity changed")
                for key in ("definitions", "evidence", "aliases", "relationships", "node_ids"):
                    require(all(row in record[key] for row in previous[key]), "glossary evidence cannot be removed")
                require(all(row in record.get('terminology', []) for row in previous.get('terminology', [])),
                        'terminology lookup history cannot be removed')
            else:
                new_ids.append(int(record["id"][1:]))
        require(sorted(new_ids) == list(range(before["next_id"], after["next_id"])), "glossary allocator would reuse or skip an ID")
    else:
        require(after["revision"] == before["revision"] and after["commitment"] == before["commitment"] and
                after["next_id"] == before["next_id"], "glossary changed without term after-images")


def string(value, limit=1000):
    require(isinstance(value, str) and value.strip() and len(value) <= limit and
            not any(ord(c) < 32 and c not in "\n\r\t" for c in value), "invalid glossary text")


def validate_record(record):
    fields = {"id", "key", "term", "aliases", "definitions", "evidence", "relationships", "node_ids", "status"}
    require(isinstance(record, dict) and fields <= set(record) <= fields | {'terminology'}, "invalid glossary record")
    require(isinstance(record["id"], str) and TERM_ID.fullmatch(record["id"]), "invalid glossary ID")
    string(record["term"], 160); string(record["key"], 1200)
    for key in ("aliases", "definitions", "evidence", "relationships", "node_ids"):
        require(isinstance(record[key], list), "invalid glossary record list")
    require(record["evidence"] and record["node_ids"], "glossary evidence/nodes required")
    for alias in record["aliases"]: string(alias, 160)
    for row in record["evidence"]:
        require(isinstance(row, dict) and set(row) == {"source_id", "passage", "evidence_ref", "node_id", "qualification"}, "invalid term evidence")
        for key, value in row.items():
            if key == "qualification": require(isinstance(value, str), "invalid evidence qualification")
            else: string(value)
    for row in record["definitions"]:
        if isinstance(row, dict) and 'authority' in row:
            from .terminology import validate_concept, normalize as authority_name
            require(set(row) == {'text', 'qualification', 'type', 'scope', 'authority'}, 'invalid authority definition')
            authority = validate_concept(row['authority'])
            require(authority_name(record['term']) == authority_name(authority['matched_name']),
                    'authority definition belongs to a different term')
            require({k: row[k] for k in ('text', 'qualification', 'type', 'scope')} in authority['descriptions'],
                    'authority description differs from retrieved text')
            continue
        require(isinstance(row, dict) and set(row) == {"text", "qualification", "evidence"} and row["evidence"] in record["evidence"], "invalid definition evidence")
        string(row["text"]); require(isinstance(row["qualification"], str), "invalid definition qualification")
        require(row["text"] in row["evidence"]["passage"], "definition must be extractive")
    for row in record["relationships"]:
        require(isinstance(row, dict) and set(row) == {"target", "type", "evidence"} and
                TERM_ID.fullmatch(row["target"]) and row["target"] != record["id"] and
                row["type"] in RELATIONS, "invalid glossary relationship")
        require(row["evidence"] in record["evidence"], "relationship evidence missing")
    expected = "candidate" if not record["definitions"] else "source_defined" if len({normalize(d["text"]) for d in record["definitions"]}) == 1 else "multiple_definitions"
    require(record["status"] == expected, "incorrect definition status")
    from .terminology import validate_result
    require(isinstance(record.get('terminology', []), list), 'invalid terminology lookup history')
    for lookup in record.get('terminology', []): validate_result(lookup, record['term'])


def present(term, passage):
    return bool(re.search(r"(?<!\w)" + re.escape(normalize(term)) + r"(?!\w)", normalize(passage)))


def alias_supported(term, alias, passage):
    a, b, p = map(normalize, (term, alias, passage))
    # Mere co-occurrence is not synonym evidence. Parenthetical expansions and
    # explicit naming statements are accepted, with the original quote retained.
    return any(re.search(re.escape(x) + r"\s*\(\s*" + re.escape(y) + r"\s*\)", p)
               or re.search(re.escape(x) + r"\s*(?:,\s*)?(?:also (?:known|referred to) as|also called|or)\s+" + re.escape(y) + r"(?!\w)", p)
               for x, y in ((a, b), (b, a)))


def relationship_supported(term, target, kind, passage):
    a, b, p = map(normalize, (term, target, passage))
    if kind == "SYNONYM_OF": return alias_supported(term, target, passage)
    if kind == "BROADER_THAN": a, b = b, a
    cue = r"(?:is |are )?(?:a |an )?(?:type|form|subtype|kind) of" if kind != "RELATED_TO" else r"(?:is |are )?(?:associated with|related to|linked to)"
    return bool(re.search(re.escape(a) + r"\s+" + cue + r"\s+" + re.escape(b) + r"(?!\w)", p))


def validate_proposal(value, evidence):
    require(isinstance(value, dict) and set(value) == {"term", "definition", "aliases", "relationships", "source_id", "passage", "qualification"}, "invalid term proposal fields")
    string(value["term"], 160); string(value["passage"], 1000)
    sources = {row["id"]: row for row in evidence["results"]}
    require(isinstance(value["source_id"], str) and value["source_id"] in sources, "invalid glossary source reference")
    source = sources[value["source_id"]]
    require(value["passage"] in source.get("content", ""), "term passage absent from supplied source text")
    require(present(value["term"], value["passage"]), "term absent from supporting passage")
    require(isinstance(value["qualification"], str) and len(value["qualification"]) <= 500, "invalid term qualification")
    require(isinstance(value["aliases"], list) and len(value["aliases"]) <= 8, "invalid term aliases")
    # Models commonly include a supplied abbreviation in the canonical label.
    # Remove that redundant suffix only when the quoted naming statement proves
    # the expansion; this is formatting normalization, not fuzzy equivalence.
    for alias in value["aliases"]:
        if not isinstance(alias, str): continue
        expanded = re.sub(r"\s*\(\s*" + re.escape(alias) + r"\s*\)\s*$", "", value["term"], flags=re.I).strip()
        if expanded and expanded != value["term"] and alias_supported(expanded, alias, value["passage"]):
            value = {**value, "term": expanded}
            break
    for alias in value["aliases"]:
        string(alias, 160)
        require(alias_supported(value["term"], alias, value["passage"]), "alias lacks explicit naming evidence")
    if value["definition"] is not None:
        string(value["definition"])
        require(value["definition"] in value["passage"] and present(value["term"], value["definition"]), "definition must quote a source statement about the term")
        # Definition assertions require a definitional cue, not simply a mention.
        require(re.search(r"\b(is|are|means|defined as|refers to|denotes)\b", value["definition"], re.I), "unsupported definition; use null for a candidate")
    require(isinstance(value["relationships"], list) and len(value["relationships"]) <= 8, "invalid term relationships")
    for row in value["relationships"]:
        require(isinstance(row, dict) and set(row) == {"term", "type"}, "invalid relationship proposal fields")
        string(row["term"], 160)
        require(isinstance(row["type"], str) and row["type"] in RELATIONS and relationship_supported(value["term"], row["term"], row["type"], value["passage"]), "relationship lacks explicit source support")
    return value


def key_for(proposal):
    key = normalize(proposal["term"])
    # A bare acronym is not a globally unique concept. Expanded canonical names
    # merge normally; isolated acronyms retain their definition/source scope.
    mentions = re.findall(r"(?<!\w)" + re.escape(proposal["term"].strip()) + r"(?!\w)", proposal["passage"], re.I)
    acronym = re.fullmatch(r"[A-Z][A-Z0-9-]{1,11}", proposal["term"])
    if acronym and not any(word != word.upper() for word in mentions):
        key += "|" + normalize(proposal["definition"] or proposal["source_id"])
    return key


def verify(store, state, manifests=None):
    """Explicit full integrity audit. Never used by ordinary R1 retrieval."""
    hashes = {}
    for manifest in manifests if manifests is not None else store._journals():
        for entry in manifest["files"]:
            if TERM_PATH.fullmatch(entry["path"]): hashes[entry["path"]] = entry["after"]
    directory = store.path("glossary")
    present = set()
    if directory.exists():
        for path in directory.iterdir():
            relative = path.relative_to(store.root).as_posix(); store.path(relative)
            if re.search(r"\.tmp-[0-9a-f]{32}\Z", path.name): continue
            require(path.is_file() and TERM_PATH.fullmatch(relative), "unexpected glossary file")
            present.add(relative)
    require(present == set(hashes), "missing or unregistered glossary records")
    for path, expected in hashes.items():
        raw = store.path(path).read_text(encoding="utf-8")
        require(digest(raw) == expected, "glossary record differs from committed hash: " + path)
        record = loads(raw); validate_record(record)
        require(path == "glossary/" + record["id"] + ".json", "glossary filename mismatch")
        for link in record["relationships"]:
            require("glossary/" + link["target"] + ".json" in hashes, "missing glossary relationship target")
    require(len(hashes) == metadata(state)["next_id"] - 1, "glossary allocator/count mismatch")
    return len(hashes)


class Directory:
    def __init__(self, store):
        self.store = store
        self.path = store.path("glossary.sqlite3")
        self.records_read = 0

    def _db(self):
        self.store.path(self.path.relative_to(self.store.root).as_posix())
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def _read(self, identity, expected):
        raw = self.store.path("glossary/" + identity + ".json").read_text(encoding="utf-8")
        require(digest(raw) == expected, "glossary record differs from committed hash: " + identity)
        self.records_read += 1
        record = loads(raw); validate_record(record)
        require(record["id"] == identity, "glossary filename mismatch")
        return record

    def _update(self, db, record, sha):
        identity = record["id"]
        for table in ("terms", "names", "links", "terms_fts", "lookups"):
            db.execute("DELETE FROM " + table + " WHERE id=?", (identity,))
        definition = " | ".join(d["text"] for d in record["definitions"][:2])[:480]
        db.execute("INSERT INTO terms VALUES (?,?,?,?,?,?,?)", (identity, record["key"], record["term"], definition,
                   dumps(record["aliases"][:8]), record["status"], sha))
        db.executemany("INSERT OR IGNORE INTO names VALUES (?,?)", [(identity, normalize(n)) for n in [record["term"], *record["aliases"]]])
        db.executemany("INSERT OR IGNORE INTO links VALUES (?,?)", [(identity, r["target"]) for r in record["relationships"]])
        db.execute("INSERT INTO terms_fts VALUES (?,?,?,?)", (identity, record["term"], " ".join(record["aliases"]), definition))
        if record.get('terminology'):
            from datetime import datetime
            last = record['terminology'][-1]
            db.execute('INSERT INTO lookups VALUES (?,?,?)',
                       (identity, last['status'], datetime.fromisoformat(last['retrieved_at']).timestamp()))

    def ensure(self, state, *, rebuild=False):
        meta = metadata(state)
        fresh = None
        try:
            with closing(self._db()) as db:
                fresh = dict(db.execute("SELECT key,value FROM metadata"))
        except sqlite3.DatabaseError:
            pass
        if fresh and fresh.get('schema') != '2': rebuild = True
        if not rebuild and fresh and fresh.get("commitment") == meta["commitment"]:
            return
        # Journal hashes, rather than the cache or unverified directory contents,
        # are the authority for rebuilding and validating touched records.
        manifests = self.store._journals()
        hashes = {}
        start = int(fresh.get("sequence", 0)) if fresh and not rebuild else 0
        for manifest in manifests[start:]:
            require(manifest["status"] == "committed", "recover before indexing glossary")
            for entry in manifest["files"]:
                if TERM_PATH.fullmatch(entry["path"]): hashes[entry["path"].split("/")[1][:-5]] = entry["after"]
        if not fresh or rebuild:
            verify(self.store, state, manifests)
            # Never discard a broken cache in place: build a replacement and
            # atomically install it using the existing live-store writer.
            import os
            import uuid
            from .store import sync_dir
            original = self.path
            self.path = self.path.with_name(".glossary-" + uuid.uuid4().hex + ".sqlite3")
            try:
                self._build(state, hashes, len(manifests))
                with self.path.open("rb") as stream: os.fsync(stream.fileno())
                os.replace(self.path, original); sync_dir(original.parent)
            finally:
                self.path.unlink(missing_ok=True)
                self.path = original
        else:
            with closing(self._db()) as db, db:
                for identity, sha in hashes.items(): self._update(db, self._read(identity, sha), sha)
                db.execute("UPDATE metadata SET value=? WHERE key='commitment'", (meta["commitment"],))
                db.execute("UPDATE metadata SET value=? WHERE key='sequence'", (str(len(manifests)),))

    def _build(self, state, hashes, sequence):
        with closing(self._db()) as db, db:
            db.executescript('''
                CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE terms(id TEXT PRIMARY KEY,key TEXT UNIQUE,term TEXT,definition TEXT,aliases TEXT,status TEXT,sha TEXT);
                CREATE TABLE names(id TEXT,name TEXT,PRIMARY KEY(id,name));
                CREATE INDEX names_lookup ON names(name);
                CREATE TABLE links(id TEXT,target TEXT,PRIMARY KEY(id,target));
                CREATE INDEX links_incoming ON links(target);
                CREATE TABLE lookups(id TEXT PRIMARY KEY,status TEXT,checked REAL);
                CREATE INDEX lookups_pending ON lookups(status,checked);
                CREATE VIRTUAL TABLE terms_fts USING fts5(id UNINDEXED,term,aliases,definition);
            ''')
            for identity, sha in hashes.items(): self._update(db, self._read(identity, sha), sha)
            db.executemany("INSERT INTO metadata VALUES (?,?)", [("commitment", metadata(state)["commitment"]), ("sequence", str(sequence)), ('schema', '2')])
            require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "glossary index integrity failure")

    def exact(self, key):
        with closing(self._db()) as db:
            row = db.execute("SELECT id,sha FROM terms WHERE key=?", (key,)).fetchone()
        return self._read(row["id"], row["sha"]) if row else None

    def known(self, terms, state):
        """Bounded indexed membership check for R1 discoveries, including aliases."""
        self.ensure(state)
        known = []
        with closing(self._db()) as db:
            for term in terms:
                row = db.execute('SELECT t.id,t.sha FROM names n JOIN terms t ON n.id=t.id WHERE n.name=? LIMIT 1',
                    (normalize(term),)).fetchone()
                if row:
                    self._read(row['id'], row['sha'])
                    known.append(term)
        return known

    def proposals(self, state, values, evidence, node_id, *, enricher=None):
        self.ensure(state)
        accepted, rejected = [], []
        if not isinstance(values, list): return {}, {"accepted": 0, "rejected": ["terms must be an array"], "merged": 0}
        for value in values[:5]:
            try: accepted.append(validate_proposal(value, evidence))
            except (ValueError, TypeError, KeyError) as exc: rejected.append(str(exc))
        if len(values) > 5: rejected.append("ignored terms beyond per-source limit of five")
        records, by_key, merged = {}, {}, 0
        meta = deepcopy(metadata(state))
        for value in accepted:
            key = key_for(value)
            record = by_key.get(key) or self.exact(key)
            if record is None and '|' not in key and not re.fullmatch(r'[A-Z][A-Z0-9-]{1,11}', value['term']):
                with closing(self._db()) as db:
                    matches = list(db.execute('SELECT t.id,t.sha FROM names n JOIN terms t ON t.id=n.id WHERE n.name=? LIMIT 2', (normalize(value['term']),)))
                if len(matches) == 1:
                    candidate = records.get(matches[0]['id']) or self._read(matches[0]['id'], matches[0]['sha'])
                    # A unique name in this corpus is not global concept proof.
                    # Alias admission requires an explicit authority synonym link.
                    if any(normalize(value['term']) in {normalize(n) for n in
                           [d['authority']['preferred_name'], *d['authority']['aliases']]}
                           for d in candidate['definitions'] if 'authority' in d): record = candidate
            if record is None:
                identity = "g" + str(meta["next_id"]); meta["next_id"] += 1
                record = {"id": identity, "key": key, "term": value["term"], "aliases": [], "definitions": [],
                          "evidence": [], "relationships": [], "node_ids": [], "status": "candidate"}
            else: merged += 1
            by_key[key] = record; records[record["id"]] = record
            support = {"source_id": value["source_id"], "passage": value["passage"], "evidence_ref": evidence["reference"], "node_id": node_id, "qualification": value["qualification"]}
            for field, additions in (("aliases", value["aliases"]), ("evidence", [support]), ("node_ids", [node_id])):
                for addition in additions:
                    exists = any(normalize(addition) == normalize(old) for old in record[field]) if field == "aliases" else addition in record[field]
                    if not exists: record[field].append(addition)
            if value["definition"]:
                definition = {"text": value["definition"], "qualification": value["qualification"], "evidence": support}
                if definition not in record["definitions"]: record["definitions"].append(definition)
            record["status"] = "candidate" if not record["definitions"] else "source_defined" if len({normalize(d["text"]) for d in record["definitions"]}) == 1 else "multiple_definitions"
        for value in accepted:
            record = by_key[key_for(value)]
            for relation in value["relationships"]:
                target = by_key.get(normalize(relation["term"])) or self.exact(normalize(relation["term"]))
                if not target or target["id"] == record["id"]:
                    rejected.append("relationship target unavailable or ambiguous: " + relation["term"]); continue
                support = next(e for e in record["evidence"] if e["source_id"] == value["source_id"] and e["passage"] == value["passage"])
                link = {"target": target["id"], "type": relation["type"], "evidence": support}
                if link not in record["relationships"]: record["relationships"].append(link)
        enrichment = None
        if enricher is not None:
            from .terminology import FAILURE_COOLDOWN, RESULT_TTL, lookup_due, timestamp, failure_reason
            # Newly admitted records and touched undefined candidates first; a
            # bounded indexed backlog lets later R3 actions enrich older candidates.
            now = enricher.clock()
            targets = [r for r in records.values() if (not r['definitions'] or
                       int(r['id'][1:]) >= metadata(state)['next_id'] or
                       (r.get('terminology') and r['terminology'][-1]['status'] in
                        {'not_attempted', 'unavailable', 'error'}))
                       and lookup_due(r, now)]
            with closing(self._db()) as db:
                suppressed = db.execute("""SELECT COUNT(*) FROM terms t JOIN lookups l ON l.id=t.id
                    WHERE l.status IN ('unavailable','error') AND l.checked>?""",
                    (now-FAILURE_COOLDOWN,)).fetchone()[0]
            if len(targets) < enricher.max_terms:
                with closing(self._db()) as db:
                    backlog = list(db.execute("""SELECT t.id,t.sha FROM terms t LEFT JOIN lookups l ON l.id=t.id
                        WHERE (t.status='candidate' OR l.status IN ('not_attempted','unavailable','error'))
                            AND (l.status IS NULL OR l.status='not_attempted'
                            OR (l.status IN ('unavailable','error') AND l.checked<=?)
                            OR (l.status IN ('matched','not_found','ambiguous') AND l.checked<=?))
                        ORDER BY CASE WHEN l.status IS NULL OR l.status='not_attempted' THEN 0 ELSE 1 END,
                            l.checked,CAST(substr(t.id,2) AS INTEGER) LIMIT ?""",
                        (now-FAILURE_COOLDOWN, now-RESULT_TTL, enricher.max_terms + len(records))))
                for row in backlog:
                    if row['id'] not in records:
                        record = self._read(row['id'], row['sha'])
                        if not lookup_due(record, now): continue
                        records[record['id']] = record; targets.append(record)
                        if len(targets) >= enricher.max_terms: break
            # The optional boundary cannot invalidate already validated science.
            try:
                outcomes, enrichment = enricher.enrich(targets)
                require(isinstance(outcomes, dict) and isinstance(enrichment, dict), 'invalid enrichment result')
            except Exception as exc:
                outcomes = {r['id']: {'provider': 'mesh', 'term': r['term'], 'status': 'error',
                    'reason': failure_reason(exc), 'retrieved_at': timestamp(enricher.clock()), 'concepts': []} for r in targets}
                enrichment = {'api_calls': 0, 'outcomes': list(outcomes.values()), 'error': failure_reason(exc)}
            # Count entries suppressed in this action, not API requests.
            enrichment['cooldown_suppressions'] = suppressed
            for record in targets:
                result = outcomes.get(record['id'])
                if result is None: continue
                try:
                    from .terminology import validate_result
                    validate_result(result, record['term'])
                except (ValueError, TypeError, KeyError) as exc:
                    enrichment.setdefault('rejected', []).append({'id': record['id'], 'error': str(exc)})
                    record.setdefault('terminology', []).append({'provider': 'mesh', 'term': record['term'],
                        'status': 'error', 'reason': failure_reason(exc), 'retrieved_at': timestamp(enricher.clock()), 'concepts': []})
                    continue
                history = record.setdefault('terminology', [])
                if result not in history: history.append(result)
                if result['status'] == 'matched':
                    authority = result['concepts'][0]
                    for alias in [authority['preferred_name'], *authority['aliases']]:
                        if len(alias) <= 160 and not any(normalize(alias) == normalize(old)
                                for old in [record['term'], *record['aliases']]): record['aliases'].append(alias)
                    for description in authority['descriptions']:
                        definition = {**description, 'authority': authority}
                        if not any(d.get('authority', {}).get('provider') == authority['provider'] and
                            d.get('authority', {}).get('concept_id') == authority['concept_id'] and
                            d.get('type') == description['type'] and d['text'] == description['text']
                            for d in record['definitions']): record['definitions'].append(definition)
                    record['status'] = 'candidate' if not record['definitions'] else 'source_defined' if len({normalize(d['text']) for d in record['definitions']}) == 1 else 'multiple_definitions'
        files = {}
        for record in records.values():
            validate_record(record)
            path = "glossary/" + record["id"] + ".json"; raw = dumps(record)
            existing = self.store.path(path)
            if not existing.exists() or existing.read_text(encoding="utf-8") != raw: files[path] = raw
        if files:
            meta["revision"] += 1; meta["commitment"] = commitment(meta["commitment"], files)
            state["glossary"] = meta
        return files, {"accepted": len(accepted), "rejected": rejected, "merged": merged, "changed_ids": list(records),
                       **({'enrichment': enrichment} if enrichment is not None else {})}

    def used(self, query, state):
        self.ensure(state)
        if query.startswith('all:"'):
            query = " ".join(re.findall(r'all:"([^"]+)"', query))
        words = re.findall(r"\w+", normalize(query))[:80]
        phrases = {" ".join(words[i:j]) for i in range(len(words)) for j in range(i + 1, len(words) + 1)}
        if not phrases: return []
        with closing(self._db()) as db:
            rows = db.execute("SELECT name,group_concat(id),count(*) FROM names WHERE name IN (" + ",".join("?" for _ in phrases) + ") GROUP BY name", sorted(phrases))
            # Ambiguous abbreviations alone never count as actual concept use.
            return sorted({row[1] for row in rows if row[2] == 1}, key=lambda i: int(i[1:]))

    def retrieve(self, state, context, node_id):
        self.ensure(state)
        meta = metadata(state)
        question = " ".join([context["question"], *context["question_context"]])
        memory = dumps(context["memory_context"])
        words = sorted(r1.tokens(question + " " + memory))[:100]
        expression = " OR ".join('"' + word.replace('"', '""') + '"' for word in words)
        used = set(state["nodes"][node_id].get("used_glossary_term_ids", []))
        with closing(self._db()) as db:
            rows = list(db.execute("SELECT t.*,bm25(terms_fts,0,5,4,1) AS rank FROM terms_fts JOIN terms t ON t.id=terms_fts.id WHERE terms_fts MATCH ? ORDER BY rank,t.id LIMIT 96", (expression,))) if words else []
            # Explicit neighbours receive a small relevance discount; novelty is
            # only a tie-breaker and cannot promote unrelated catalogue entries.
            neighbours = {}
            for row in rows[:12]:
                for other in db.execute("SELECT t.* FROM links l JOIN terms t ON t.id=l.target WHERE l.id=? UNION SELECT t.* FROM links l JOIN terms t ON t.id=l.id WHERE l.target=? LIMIT 8", (row["id"], row["id"])):
                    neighbours[other["id"]] = dict(other)
        candidates = {row["id"]: dict(row) for row in rows}
        candidates.update({i: row for i, row in neighbours.items() if i not in candidates})
        relevant = r1.tokens(question); findings = r1.tokens(memory)
        def score(row):
            names = r1.tokens(row["term"] + " " + row["aliases"])
            return (4 * len(names & relevant) + len(names & findings) +
                    .2 * (row['status'] != 'candidate') + .1 * (row["id"] not in used), -int(row["id"][1:]))
        entries = []
        result = {"entries": entries, "untrusted_glossary_data": True,
                  "omitted_count": meta['next_id'] - 1, "selection_policy": "indexed relevance then per-node novelty"}
        for row in sorted(candidates.values(), key=score, reverse=True):
            term, _ = r1.clean_text(row["term"], 160)
            if not term: continue
            definition, _ = r1.clean_text(row["definition"], 240)
            aliases = [clean for alias in loads(row["aliases"]) if (clean := r1.clean_text(alias, 100)[0])]
            entry = {"id": row["id"], "term": term, "definition": definition or None,
                     "aliases": aliases, "status": row["status"], "used_in_submitted_search": row["id"] in used}
            entries.append(entry)
            # UTF-8 byte count is a conservative token upper bound; the complete
            # request is still checked by the configured model tokenizer.
            if len(dumps(result).encode("utf-8")) > meta["token_budget"]:
                entries.pop(); continue
            if len(entries) >= meta["limit"]: break
        # Validate only selected records. Render from canonical bytes, so the
        # disposable cache can never replace their content in a prompt.
        for entry in entries:
            record = self._read(entry["id"], candidates[entry["id"]]["sha"])
            entry["term"] = r1.clean_text(record["term"], 160)[0]
            definitions = sorted(record['definitions'], key=lambda d: 'authority' not in d)[:2]
            definition, omitted = r1.clean_text(" | ".join(d["text"] for d in definitions), 240)
            entry["definition"] = definition or None
            entry["aliases"] = [clean for alias in record["aliases"][:8] if (clean := r1.clean_text(alias, 100)[0])]
            entry["status"] = record["status"]
            if any('authority' in d for d in record['definitions']):
                entry['definition_sources'] = [{'provider': d['authority']['provider'],
                    'concept_id': d['authority']['concept_id'], 'type': d['type'],
                    'preferred_name': r1.clean_text(d['authority']['preferred_name'], 160)[0]}
                    if 'authority' in d else {'source_id': d['evidence']['source_id'], 'type': 'research_source'}
                    for d in definitions]
                entry['terminology_only'] = True
                entry['definition_omitted_or_truncated'] = omitted
            if record["relationships"]:
                entry["relationships"] = [{"target": link["target"], "type": link["type"]} for link in record["relationships"][:3]]
        while entries and len(dumps(result).encode("utf-8")) > meta["token_budget"]:
            entries.pop()
        result['omitted_count'] = meta['next_id'] - 1 - len(entries)
        return result

    def export(self, state):
        """Export both views under the caller's live-store writer lock."""
        from . import glossary_view
        self.store.read()  # Recovery/canonical gate also applies to direct API callers.
        self.ensure(state)
        # Export is an explicit full audit. Neither a stale index nor forged cache
        # hashes may hide missing/unregistered or externally changed canonical data.
        manifests = self.store._journals()
        verify(self.store, state, manifests)
        hashes = {entry['path'].split('/')[1][:-5]: entry['after'] for manifest in manifests
                  for entry in manifest['files'] if TERM_PATH.fullmatch(entry['path'])}
        for attempt in range(2):
            try:
                with closing(self._db()) as db:
                    # Python's Unicode casefold preserves the existing Markdown
                    # order; SQLite performs enumeration and sorting, not FTS.
                    db.create_collation('GLOSSARY_ALPHABETICAL', lambda a, b:
                        (a.casefold() > b.casefold()) - (a.casefold() < b.casefold()))
                    rows = list(db.execute('SELECT id,term,sha FROM terms ORDER BY term COLLATE GLOSSARY_ALPHABETICAL,id'))
                valid = len(rows) == len(hashes) and {row['id']: row['sha'] for row in rows} == hashes
            except sqlite3.DatabaseError:
                valid = False
            if valid:
                records = [self._read(row['id'], hashes[row['id']]) for row in rows]
                valid = all(record['term'] == row['term'] for record, row in zip(records, rows))
            if valid: break
            require(attempt == 0, 'glossary index differs from committed records')
            self.ensure(state, rebuild=True)
        outputs = {'research/glossary.md': glossary_view.markdown(records),
                   'research/glossary.html': glossary_view.html(records)}
        glossary_view.publish(self.store, outputs)
        return {'path': str(self.store.path('research/glossary.md')),
                'html_path': str(self.store.path('research/glossary.html')), 'entries': len(records)}


def r3_prose(text):
    from .r3 import prose
    return prose(text)
