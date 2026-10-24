# Live persistence: Increment 2a

Implemented against the approved `autonomous_research_plan.md`. This increment
adds persistence only. No research controller, scheduler, synthesis gardener,
provider calls or model service changes are included. The historical project and
its data remain untouched.

The owner's clarifications are retained for later increments: killed nodes may
supply existing memories, but only exhausted nodes receive the terminal bonus;
8192 context tokens and 2048 output tokens are configurable starting defaults.
No context-budget policy is implemented in this persistence increment.

## Using the existing Knowledge API with live files

```python
from mira import Knowledge, LiveStore

k = Knowledge(store=LiveStore('/tmp/mira-live'))
m = k.create_memory('A trial', 'A manually authored trial.')
k.add_finding(m.id, 'Observation', 'A measured result.',
              'The applicable conditions.', 'The actual source.')
k.validate()
k.rebuild()
```

Existing `Knowledge(root)` and Phase 1 CLI commands retain snapshot behavior.
Neither store opens the other store's layout; there is no implicit migration.
The CLI selects live persistence explicitly:

```bash
PYTHONPATH=src python3 -m mira --live --root /tmp/mira-live create 'A trial' 'A manually authored trial.'
PYTHONPATH=src python3 -m mira --live --root /tmp/mira-live validate
PYTHONPATH=src python3 -m mira --live --root /tmp/mira-live integrity
PYTHONPATH=src python3 -m mira --live --root /tmp/mira-live recovery inspect
PYTHONPATH=src python3 -m mira --live --root /tmp/mira-live recovery validate
PYTHONPATH=src python3 -m mira --live --root /tmp/mira-live recovery repair OPERATION_ID
PYTHONPATH=src python3 -m mira --live --root /tmp/mira-live recovery repair OPERATION_ID --apply
```

`inspect` and `validate` both assess journal integrity, actual file hashes and the
complete prospective corpus. Neither changes canonical files or marks operations
committed. `repair` defaults to the same read-only assessment for one operation.
`--apply` explicitly authorizes forward completion after rechecking under lock.
Assessment does not imply permission to repair. Malformed journals, unexpected
bytes, conflicting operations, missing required payloads or invalid references
block repair and remain preserved. The CLI emits a JSON report, including blocked
status; callers should examine that status rather than interpreting exit success
as a clean corpus. Constructor-created directories and lock files may be created
when opening a root, including for inspection; no corpus or journal is adopted.

## Transaction boundary and layout

`Knowledge.transaction(callback, files=..., operation_type=..., context=...,
expected_revision=...)` is a live-only batch entrypoint. The callback receives
and mutates the existing memory list, equation list and identity ledger; it does
not introduce another memory model. The callback runs under the writer lock and
must not call Knowledge recursively. Its result is returned after durable commit.
For state prepared from an earlier read, supply `expected_revision` obtained from
`store.read()[0]` under `store.lock()`; a stale whole-corpus revision fails before
the callback runs. The ordinary single-document API retains revision checks.

The optional `files` mapping supplies JSON text for `research/state.json`,
`research/results/<id>.json` and `events/<id>.json`. Only state may be replaced;
results and events are immutable once written. Documents and equations must go
through the existing validated objects. Callers supply cycle/node context when
available; persistence automatically records affected/new document IDs, new
synthesis input lists and the expected state-file digest. Increment 2b will
validate the tree schema, ownership and aggregate counts. At this boundary state,
results and events must be JSON objects, without speculative controller schemas.

```text
memories/*.md                  canonical existing Markdown format
equations/*.json               canonical existing equation format
identity.json                  canonical monotonic allocator
research/state.json            optional canonical controller state
research/results/*.json        immutable search evidence, when supplied
events/*.json                  immutable audit/terminal events, when supplied
journal/<operation-id>.json    versioned operation manifest
journal/<operation-id>/*.txt   after-images of changed files only
.writer.lock                   cooperating readers/writers
index.sqlite3                  disposable derived retrieval index
```

Live reads return an opaque content digest in the existing store tuple's revision
slot. SQLite's legacy `generation` metadata key stores that token without requiring
snapshot directories. Every query checks canonical integrity and repairs index
staleness by rebuilding; a failed rebuild fails the query. Vector query embedding
also waits until the recovery gate succeeds.

Identity allocation and immutable finding/equation checks are shared with Phase 1.
Existing canonical Markdown is unchanged. Documents that opt into autonomous
metadata with `node_id` must also have valid `kind`, `source_memories` and
`synthesized_by`. Lineage is reciprocal, acyclic and requires at least two distinct
sources for a synthesis. Existing source lists, owners and kinds are immutable;
a consumed memory cannot be consumed again. New finding-level SYNTHESIZES edges
still pass the existing endpoint validator. These are structural guarantees, not
validation of the scientific reasoning.

## Durable protocol

Each operation has a UUID, monotonic sequence, type/context, before/after revision
digests, status and ordered file entries. Each entry contains canonical path,
before digest or absent, after digest, staged-payload path and durable progress.
The sequence and revision chain reject missing/conflicting manifests. A revision
hash covers canonical paths as well as contents, so unrelated changes and missing
files are detected without putting a corpus inventory into every journal entry.

Under one local Linux `flock`:

1. Read and validate the current canonical view and proposed complete change.
   Reject identity reuse, unsupported edits and lineage errors before staging.
2. Write/fsync changed-file after-images and directories. Publish/fsync the prepared
   manifest using a temporary file and atomic replacement before canonical edits.
3. Recheck canonical preconditions. Publish new memories before consumption marks,
   then remaining files, with the allocator and controller state last. Each file
   gets its own file fsync, atomic replacement and parent-directory fsync. Persist
   progress after each replacement. A crash between replacement and progress is
   resolved by actual hashes, not by trusting progress flags.
4. Revalidate all canonical contents and the after digest; durably replace the
   manifest with `committed`. Only then release results and allow normal readers.

All Mira canonical readers/writers use the same lock and recovery gate. Raw reads
of individual files may observe partial application. This is logical multi-file
atomicity through Mira, not filesystem-wide physical atomic visibility.

On restart no automatic repair occurs. Normal reads and writes block on an
incomplete operation or unpublished staging directory. Assessment shows exactly
which files match the intended after-image and which remain outstanding:

- All before, valid payloads: safely finishable and safely cancellable without
  canonical rollback. Cancellation itself is deliberately not automated.
- Mixed before/after, valid pending payloads and prospective corpus: safely
  finishable. Explicit repair writes only remaining files.
- All after and valid: recognizably complete; repair only finalizes progress and
  commit status. Completed files no longer need their staged payloads.
- Unknown hashes, invalid references or missing pending payloads: ambiguous;
  refuse writes and preserve evidence for human judgment.

General rollback is unavailable because before-images are not retained. Committed
operation IDs remain inspectable in the retained journal to resolve an ambiguous
acknowledgment; repeating repair of a committed operation never allocates IDs,
creates documents or reapplies its changes. Callers must inspect after an ambiguous
acknowledgment before retrying a new transaction callback; callback invocations are
not automatically deduplicated. A repeated repair uses the same manifest even if
repair itself was interrupted.

## Verification and limits

Command: `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
All 49 tests pass: 34 retained Phase 1 tests plus 15 live-persistence tests.

The synthetic synthesis changes exactly five canonical files: a new `s1`, two
source consumption marks, allocator and state. Subprocesses terminate with
`os._exit` at these durable boundaries:

| Interruption | Assessment | Explicit repair result |
| --- | --- | --- |
| Payloads staged, before prepared manifest | Unpublished; normal access blocked | Human judgment required; no automatic adoption |
| Prepared manifest | Safely finishable; also safely cancellable | Finishes all five files |
| Output replaced, progress not yet updated | Safely finishable | Recognizes output, finishes remaining files |
| First source mark replaced, progress stale | Safely finishable | Recognizes actual source bytes |
| Both source marks durably recorded | Safely finishable | Finishes allocator and state |
| State replaced, progress stale | Complete | Finalizes journal |
| Before committed marker | Complete | Finalizes journal |
| After committed marker | Already committed | No repair required |
| Repair interrupted after second source replacement | Safely finishable on next assessment | Repeated repair finishes without duplication |

Additional tests cover dry-run byte preservation; unknown bytes; missing pending
payloads; completed files with removed payloads; corrupted references even with
matching payload hashes; unsafe paths and symlinks; conflicting/malformed journals;
immutable events; stale transaction/document revisions; concurrent ID allocation;
changed-files-only staging; equations/reuse; and rebuild of deleted/stale SQLite.

These process-exit tests do not simulate power loss or prove filesystem/hardware
behavior. Durability assumes local Linux rename/fsync semantics and cooperating
processes. External editors are not stopped by an advisory lock; unexpected edits
fail closed. Journal manifests and changed-file payloads are retained indefinitely;
no cleanup, migration, backup manager or rollback is included. Unpublished staging
requires manual investigation. Canonical validation and journal-chain scans are
linear in corpus/history size; this bounded implementation prioritizes inspection
and correctness over large-corpus throughput. Full tree semantics and synthesis
scheduling remain for later reviewed increments. Increment 2b has not begun.
