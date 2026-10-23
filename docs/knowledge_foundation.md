# Knowledge foundation, Phase 1

This implementation follows `ProjectOverview.md` and `architecture.md` Draft 0.2.
The assignment authorizes implementation although the draft leaves exact schemas,
status vocabularies and endpoint rules open. The bounded contracts below are
**provisional version 1 choices for review**, not silent changes to the approved
architecture. No autonomous execution, LLM generation or old corpus is included.

## Running it

Python 3.11+ on Linux, SQLite with FTS5, and `markdown-it-py>=3,<5` are required.
Python 3.14.4 and markdown-it-py 3.0.0 were used here.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/mira --root /tmp/mira-fresh-demo --test-embedding demo
```

The source tree also runs without installation when the parser is installed:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m mira --root /tmp/mira-fresh-demo --test-embedding demo
PYTHONPATH=src python3 -m mira --root /tmp/mira-fresh-demo validate
PYTHONPATH=src python3 -m mira --root /tmp/mira-fresh-demo rebuild
PYTHONPATH=src python3 -m mira --root /tmp/mira-fresh-demo get 'r1#f1'
PYTHONPATH=src python3 -m mira --root /tmp/mira-fresh-demo search 'thermal energy'
PYTHONPATH=src python3 -m mira --root /tmp/mira-fresh-demo relationships 'r1#f1' --direction incoming
PYTHONPATH=src python3 -m mira --root /tmp/mira-fresh-demo recovery
```

Use an empty directory for each demo. No corpus is created in this repository by
default; the CLI only creates `knowledge/` when invoked without `--root`.
`--test-embedding` is a token-hash **test double, not a semantic model**.
With no backend, exact, lexical and relationship retrieval still work; vector
search requires explicit configuration. Changing backends rebuilds the index.

## Layout and API

`src/mira/format.py` owns data contracts, Markdown parsing/rendering and corpus
validation; `store.py` owns snapshots and writer serialization; `index.py` owns
SQLite and retrieval; `embeddings.py` owns the embedding protocol and clients;
`api.py` exposes the knowledge operations; `cli.py` exposes inspection/demo
commands. `demo.py` creates the synthetic fixtures. No empty future-agent modules.

```python
from mira import Knowledge

k = Knowledge('/tmp/my-mira')
doc = k.create_memory('Trial', 'A small trial of thermal resistance.')
finding = k.add_finding(doc.id, 'Thermal barrier',
    'Insulation slows heat transfer.',
    'Under otherwise comparable conditions.',
    'Manually authored hypothesis.', kind='hypothesis')
question = k.add_question(doc.id, 'Measurement', 'How large is the effect?')
k.add_relationship(doc.id, 'f1', 'CITES',
    'https://example.org/synthetic-reference', status='unverified')
unit = k.retrieve(finding)
complete_document = k.containing_document(finding)
incoming = k.relationships(finding, direction='incoming')
summaries = k.summaries()
k.validate()
k.rebuild()
```

Also available: `add_equation`, `reference_equation`, `save_memory`, `search`,
`directory.exact`, `directory.integrity`. `retrieve` returns complete canonical
fields; equation aliases include the complete equation definition. Directory
records expose revision digests, parent documents and searchable content.
`validate(text)` can validate a candidate Markdown document against current targets.
`save_memory` requires `expected_revision`; add operations optionally accept it.
Without it, an add runs against the latest snapshot under the lock, so concurrent
append operations serialize without overwriting one another.

## Canonical format

A canonical memory uses an H1 title, one JSON metadata fence, `## Memory`, then
zero or more units and one terminal `## Relationships` JSON fence. An empty newly
created document is valid. The header's ID, not its title, is identity authority;
the managed filename must match it. Example:

````markdown
# Cooling experiment

```json
{
  "version": 1,
  "id": "r1",
  "revision": 2,
  "summary": "An authored cooling fixture.",
  "metadata": {},
  "next": {"f": 2, "q": 1, "e": 1}
}
```

## Memory

[#f1] Cooling direction

**Kind:** claim

**Evidence status:** unverified

**Proposition:** Heat flows toward cooler surroundings.

**Explanation:** Under comparable conditions.

**Provenance:** Authored synthetic fixture.

## Relationships

```json
{
  "version": 1,
  "relationships": [
    {"from": "f1", "type": "CITES", "to": "https://example.org/synthetic", "status": "unverified"}
  ]
}
```
````

Fields may contain multiple paragraphs, fenced code, quotes and lists. Top-level
headings inside units are deliberately unsupported in v1 to avoid ambiguous
section boundaries. Reserved unescaped `[#` syntax in normal prose must be a valid
whole-line marker; code/quote/list examples do not allocate identities. Unknown
fields, malformed JSON, duplicate JSON keys, duplicate anchors, extra terminal
content and lossy rendering are rejected. Prose is not interpreted as canonical
relationships. No source-unit anchors are supported.

Finding kinds: `observation`, `claim`, `inference`, `hypothesis`, `synthesis`.
Evidence statuses: `unverified`, `supported`, `disputed`, `inconclusive`.
Question fields are `Question` and `State`, with states `open`, `partially_answered`,
`answered`, `superseded`. These vocabularies are provisional. They do not imply
machine verification. Existing unit-field changes are currently rejected, including
question-state changes; lifecycle update admission needs a reviewed revision policy.

Equation anchors contain `**Equation:** e_r1_1`. JSON definitions contain exactly
the `Equation` dataclass fields: `id`, `origin`, `label`, `expression`, `variables`,
`assumptions`, `provenance`, `revision`, and `units`. Variable meanings are required;
units are optional by variable. Origin is stable; additional documents allocate
local aliases without changing the global ID. No symbolic equivalence or expression
execution is attempted. Equation canonical citations can originate from the local
alias in its document's relationship block; prose provenance is not a duplicate
machine-readable citation list. Missing and orphan definitions are rejected.

## Identity and revision policy

Document IDs use independent positive base-36 research/synthesis sequences; finding,
question and equation-anchor counters are per document and type. A canonical
`identity.json` ledger and document high-water counters are committed together.
Equation global IDs use a decimal origin-local ordinal, e.g. `e_r1_10`; local anchors
use base-36. Committed IDs cannot be reused. Failed unpublished work allocates no
public identity; callers receive IDs only after publication succeeds. Old snapshots
remain available for audit; no deletion, reset, compaction or ID-reuse operation exists.

Titles, summaries, optional metadata and relationship lists can be edited through
`save_memory`; document revisions increase. Existing units and equation definitions
are immutable in this milestone, so even a harmless wording change is rejected.
Splits, merges, retirement, relocation and material finding revision are deliberately
unsupported pending identity/semantic-continuity policy. New units may be appended.
Stable equation reuse is supported. Changing a title preserves all references.
Relationship status edits are explicit; nothing promotes status automatically.

## Relationships and endpoint meanings

Each record has exactly `from`, `type`, `to`, `status`. `from` is a local unit anchor;
`to` is a global unit ID, document ID, equation ID, HTTP(S) URL or `doi:10.../...`.
Only `CITES` may target external sources or whole documents. Status vocabulary:
`unverified`, `proposed`, `reviewed`, `rejected`. The default query includes reviewed
and unverified assertions and returns their statuses. Proposals/rejections require
explicit status filters; unverified edges must not be interpreted as established facts.

| Type | Source TYPE target means | Deterministic endpoint restriction |
| --- | --- | --- |
| CITES | Source explicitly references target; no warrant implied. | Any local unit to internal target or external source. |
| SUPPORTS | Source provides evidential warrant for target under matching scope. | Finding to finding. |
| CONTRADICTS | Source conflicts with target under matching scope. | Finding to finding. |
| QUALIFIES | Source limits target's scope or assumptions. | Finding to finding. |
| DEPENDS_ON | Source requires target construction/principle. | Local unit to internal unit or equation definition. |
| BUILDS_ON | Source extends target contribution. | Finding to finding. |
| SYNTHESIZES | Source integrates target as an input. | Synthesis-kind finding to finding. |
| RELATED_TO | Substantive association; not vector similarity. | Local unit to internal unit or equation definition. |
| INFLUENCED_BY | Source historically influenced by target, requiring attribution. | Finding to finding. |

Edges are stored once, only in the originating Markdown. A type/source/target
assertion cannot be duplicated with a different status. Reversed `RELATED_TO`
assertions count as duplicates. Other inverse conceptual edges are not auto-created.
Self-edges are rejected. The validator checks endpoints, vocabulary and synthesis
actor kind, **not entailment, historical truth, scope matching or evidence quality**.
All semantic admissions remain the caller/reviewer's responsibility; status labels
are not a permission system. The restricted v1 fields omit passage-level evidence
pins and source canonicalization; those need review before research automation.

## Derived database and retrieval

`index.sqlite3` contains `documents` (identity/title/summary/revision/metadata),
`units` (identity/parent/type/label/content/revision/vector), FTS5 `units_fts`,
`edges` (source/target/type/status/owner), and `metadata` (schema, generation,
embedding identity and dimensions). Incoming/outgoing indexes support filtering
before limits. Unit records contain actual finding fields, questions, equation
aliases and definitions. Document-summary records use the document ID and resolve
to the whole Markdown document. Exact lookup is separate from FTS phrase search.
The current full-text query treats input as a literal phrase, without FTS operators.
Vector ranking uses cosine similarity, deterministic ID tie-breaking and optional
type filtering. It loads all vectors; appropriate for this bounded corpus, not a
large production index. Complete content is fetched through the canonical API.

Rebuild scans the selected snapshot, validates the entire corpus, embeds records,
constructs a temporary SQLite file and atomically replaces the old database.
No model is needed for basic operations. Persisted model identity includes model
artifact digest in the real demonstration; changing identity regenerates vectors.
The backend must return finite numeric vectors with matching cardinality/dimensions.
`integrity` compares canonical records and edges with SQLite, validates SQLite/FTS
integrity, and checks foreign keys. Database deletion loses no canonical information.

## Persistence and recovery contract

```text
knowledge/
  CURRENT                         # atomic generation selector
  .writer.lock                    # Linux advisory writer/query lock
  generations/<generation>/
    documents/*.md                # canonical, readable memories
    equations/*.json              # canonical equation definitions
    identity.json                 # document allocation high-water marks
    manifest.json                 # file hashes + parent generation
  index.sqlite3                   # entirely disposable
```

One mutation holds `flock`, reads the selected snapshot, checks a supplied document
revision, validates the complete proposed corpus and rejects identity-changing
edits. It stages **all** canonical files in a new generation, flushes files and
directories, rechecks current content, writes/fsyncs a temporary pointer and uses
`os.replace` plus directory fsync to publish it. Readers also hold the lock and use
only CURRENT. A complete snapshot makes a multi-file equation/document addition
visible together. Old generations remain audit history; orphan staging directories
are reported by `recovery`, never automatically adopted. No destructive cleanup.

The derived index may lag immediately after a commit. Every query checks current
canonical integrity and index generation/model, rebuilding under the lock if needed.
A crash between pointer publication and indexing never returns an old generation
as current knowledge. A rebuild failure fails the query; it does not roll back or
misreport the canonical commit. If a process exits after pointer publication but
before receiving its result, callers must inspect canonical state before retrying
(the usual ambiguous-acknowledgment case).

This is a bounded Linux local-filesystem snapshot protocol, tested with process
exit before and after publication, **not a power-loss/filesystem-failure proof**.
It relies on filesystem rename/fsync semantics and cooperating processes. External
edits to immutable generations fail hash checks; edit detached drafts through the
API instead. Malicious edits racing outside the advisory lock are outside the
contract. Snapshot copying and retained history cost O(corpus size) per write;
no incremental storage, garbage collection, cross-platform locking or backup
manager is implemented. Back up CURRENT and the complete referenced generation,
including identity ledger and manifest, independently of SQLite.

## Real semantic demonstration

`examples/semantic_demo.py` uses the existing local Nomic GGUF over an independently
managed localhost endpoint. It never starts or controls the reference service.
To reproduce, start a separate CPU-only server, then run the script:

```bash
/home/eric/Dev/llama.cpp/build/bin/llama-server \
  --host 127.0.0.1 --port 18091 \
  --model /home/eric/models/nomic-embed-text-v1.5.Q5_K_M.gguf \
  --embedding --pooling mean --ctx-size 2048 --parallel 1 \
  --n-gpu-layers 0 --device none --threads 4 --no-op-offload
```

In another terminal:

```bash
PYTHONPATH=src python3 examples/semantic_demo.py \
  --model /home/eric/models/nomic-embed-text-v1.5.Q5_K_M.gguf
```

Stop that separate server after the run. The client prefixes documents with
`search_document:` and queries with `search_query:`. It has no model download,
restart or truncation mechanism; oversized inputs fail at the endpoint rather than
being silently shortened. A future context/window policy needs review.
