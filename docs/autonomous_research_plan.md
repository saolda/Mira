# Mira 2: Increment 1 investigation and approval proposal

> Historical milestone report. The current R1–R5 contract, three-way R4,
> question provenance and branching/synthesis policies are documented in
> [architecture](../architecture.md) and [execution](research_execution.md).


Status: approved by the owner on 24 October 2026, with two clarifications:
killed nodes may contribute existing memories but only exhausted nodes qualify
for the 1000-point terminal bonus; 8192 context tokens and 2048 output tokens are
configurable initial defaults. Increment 2a is authorized; Increment 2b awaits
persistence and crash-recovery review. See `live_persistence.md` for the 2a result.

## Verified baseline

Read `ProjectOverview.md`, `architecture.md`, `docs/knowledge_foundation.md`,
the foundation source and tests, and relevant historical source and viewer docs.
GitHub PR #1 is merged; local HEAD is its merge commit
`fdc67433fc083e9cc8610d8f693f2ccadd361adf`. The architecture retrieved from PR
head `ea411515a9d6603d29eb60e5dcfc6832d71cc73f` matches the local document.
The updated PR architecture is the implementation baseline, rather than the
older storage description in `docs/knowledge_foundation.md`.

Baseline verification: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
passes all 34 tests. The working tree was clean before this proposal.
The historical project was inspected read-only; no services were started and
no research data was imported or modified.

## Reuse and incompatibilities

| Component inspected | Recommendation |
| --- | --- |
| `src/mira/format.py` | Reuse Memory, Unit, Equation, Relationship, base-36 IDs, strict JSON, Markdown round trips, endpoint and corpus validation. Keep existing findings immutable and append new findings. |
| `src/mira/api.py` | Keep Knowledge as the sole knowledge API. Extend its transaction boundary to submit complete research/synthesis changes together; repeated public add calls cannot provide one atomic logical synthesis. Allow store injection while retaining the existing constructor behavior for Phase 1 callers. |
| `src/mira/store.py` | Reuse locking, digest/precondition checks, file and directory fsync patterns, identity guards. Keep SnapshotStore for existing functionality; add a live store for explicitly initialized autonomous roots. Do not invoke snapshot publication for autonomous work. |
| `src/mira/index.py` | Reuse finding records, FTS5, exact lookup, vectors and relationship queries. Replace the assumption that freshness means a generation directory with an opaque canonical revision token. Keep readers under the same recovery gate and lock as writers. |
| `src/mira/embeddings.py` | Keep existing embedding protocol and optional HTTP client. Embeddings are separate from the new text-generation interface. |
| `tests/test_foundation.py` | Retain all tests, including snapshot-specific tests. Reuse identity, relationship, concurrency and subprocess-crash testing patterns for live storage. |
| Historical `src/actions.py` | Extract a small adapter, not the module: its config import, automatic provider fallback and query rewriting conflict with explicit strategy order. Retain explicit transport outcomes and bounded responses. |
| Historical `src/brain_viewer.py`, `docs/brain_viewer_health.md` | Reuse read-only tree/selected-node/lineage/health ideas. Avoid legacy goal parsing, stage projections, chat diagnostics and service probes. Start with text/JSON CLI inspection. |
| Historical cycle, synthesis and persistence | Do not port the fixed-stage runtime or exception-rollback persistence. Their lifecycle and path-based memory assumptions differ from this specification. |

There is no concrete incompatibility requiring a canonical Markdown redesign.
Use the existing header's `metadata` dictionary for `kind`, `node_id`,
`synthesized_by`, and `source_memories`. Add deterministic validation of those
keys for autonomous documents. Keep document IDs and equation JSON conventions.
Memory lineage lists document inputs; existing SYNTHESIZES edges connect
synthesis findings to the specific input findings they integrate. Neither claims
independent verification. Existing structural validation cannot establish research
truth or synthesis faithfulness.

No research tree, scheduler, search contract, generation client or synthesis
frontier currently exists. These are additions, not replacements for Phase 1.

## Proposed contracts requiring approval

1. **Scheduling:** use the sustained active turn in section 4: root starts at 10;
   after each committed research action, decrement its priority, increment other
   previously existing living nodes up to 10, and reselect only at zero or on exit
   from living status. Children created in that action remain at 0 until subsequent
   actions. Creation ordinals break research ties, resolving the later stale
   sentence saying tie-breaking is unspecified. A selected zero-priority node can
   perform an action before reselection. Persist counters and creation ordinals.
2. **Search outcomes:** `ok(results)`, `empty`, `failed`, and `rate_limited` are
   distinct. A valid empty response advances the database pointer and logs the
   unsuccessful search without R3; a transport, parse or provider error never
   advances it. Commit nonempty results and pointer advancement together. Preserve
   pending results on R3 validation/model failure. Failed attempts are logged but
   do not spend priority or count toward the five committed research actions.
   Use bounded transport retries/backoff; persistent failure pauses with an
   inspectable reason, rather than silently skipping a database or spinning.
3. **R3/R4 admission:** R3 may explicitly report no supported findings with a
   reason; clear processed results only when that assessment or valid memories
   commit. R4 allows exactly the five architecture decisions, with nonempty
   replacement keywords on retry and contributing child questions on split.
   Reject malformed/unsupported model proposals without another LLM pass in the
   same cycle. Node q IDs and memory q anchors are separate namespaces.
4. **Synthesis ordering:** eligible candidates have at least two frontier memories
   and are not complete. Order by descending score then oldest creation ordinal.
   Use the specified count plus 1000 exhausted-terminal bonus. Proposed killed-node
   policy: retain their material and allow synthesis when they have two inputs;
   never convert killed to complete. This needs approval because the architecture
   only defines automatic completion for exhausted nodes.
5. **Bounded selection:** descend through eligible children by synthesis score,
   ties oldest-first. Select complete unconsumed memories in committed creation
   order, skipping those that do not fit; never truncate canonical source content.
   Reserve configurable space for instructions, ancestor questions and output;
   use a model tokenizer when supplied and a documented conservative UTF-8-byte
   estimate otherwise. Log blocked input IDs and estimates if no pair fits.
   Default proposed total context is 8192 estimated tokens with 2048 reserved
   for output; actual instruction/question costs are also subtracted. Reject an
   infeasible configuration. No automatic splitting of a single memory yet.
6. **Completion and final drain:** propagate exhausted-terminal completion at
   zero or one inputs without a model call, including after R4. When no living
   nodes remain, persist one detailed terminal event containing root question,
   status totals, pending results, frontier counts and outstanding synthesis.
   Switch directly to synthesis-only cycles until no eligible work remains;
   distinguish completed from blocked-by-budget/recovery outcomes. Do not pad
   the interval with artificial research cycles.
7. **Health:** validate tree acyclicity, reciprocal links, node ownership,
   allocators, statuses, priorities, lineage and derived counts. Invalid state
   pauses; no heuristic node repair, reparenting or imbalance intervention.
   Report maximum depth, living counts by depth and child counts from the start.

Important bookkeeping detail: when a synthesis at an ancestor consumes descendant
memories, update each input owner's counts and all affected ancestor paths, not
only the output node's path. Otherwise descendant frontier counts become stale.
Completion remains compatible with later consumption of its final memory by an
ancestor; complete nodes never reenter the synthesis candidate list.

## Proposed operation journal and recovery protocol

Proposed autonomous-root layout:

```text
memories/r1.md, s1.md, ...       # existing canonical Markdown format
equations/*.json                # existing canonical equation definitions
identity.json                   # monotonic document allocation ledger
research/state.json             # tree, ordered lists, counters, revision
research/results/<id>.json      # durable bounded search evidence and provenance
journal/<operation-id>.json     # compact manifest and durable progress
journal/<operation-id>/...      # staged after-images of changed files only
events/<event-id>.json          # inspectable action and terminal events
.writer.lock
index.sqlite3                  # disposable, never authoritative
```

Staged payloads are necessary to finish a synthesis without asking the model to
regenerate different research. They contain only changed files, including the
tree state, never a routine corpus copy. Retain committed manifests for audit;
automatic payload cleanup/retention is deferred. Old affected document revisions
are not routinely copied; external backups remain separate.

Each versioned journal manifest contains operation ID/type, cycle ID, node ID,
allocated identities, exact input/output IDs, expected state revision, and an
ordered file list. Each file entry records a validated relative path, expected
before digest (or absent), after digest, staged payload path, and progress.
The manifest records prepared/applying/committed status and a commit revision.
Paths are root-confined and symlinks rejected. Operations create or replace files;
ordinary synthesis does not delete files. An event is included in the write set
so a crash cannot lose the terminal event while stopping research.

Protocol, under one cooperating-process advisory lock:

1. Assess incomplete operations before allowing reads/actions. Load the current
   canonical view, validate preconditions, allocate IDs and assemble the complete
   proposed change in memory. Validate the hypothetical corpus, lineage and tree.
2. Write/fsync changed-file after-images and their containing directories. Publish
   the prepared manifest with temp-file replacement and directory fsync **before
   any canonical replacement**. An interrupted staging directory without a
   prepared manifest is reported as unpublished and never adopted automatically.
3. Recheck before hashes. Replace each affected canonical file using a temporary
   file on the same filesystem, fsync the file, `os.replace`, then fsync its parent.
   Publish the synthesis document before its input consumption marks; replace
   allocator and state files toward the end. Durably update progress after every
   replacement. Never trust progress alone: a crash may precede its update.
4. Verify all after hashes and full canonical consistency. Atomically publish and
   fsync the committed journal status. Only now release the result to readers or
   the scheduler. Lazily rebuild SQLite against the new canonical revision.

Individual files are physically visible during application. Logical all-or-neither
visibility therefore requires every Mira reader/writer to hold the lock and refuse
an incomplete operation; a raw filesystem reader can see partial work. If the
architecture intends physical atomic visibility across raw files, that requirement
conflicts with a live directory plus individual replacements and needs resolution.
This proposal interprets it as logical transaction visibility through Mira.

Recovery assessment always compares current bytes with before/after hashes:

| Observed state | Assessment and permitted response |
| --- | --- |
| All before, staged payloads valid | Safely finishable, or safely cancellable with no canonical rollback. |
| Each file before or after, all required payloads valid | Safely finishable; show completed/remaining files and exact proposed replacements. |
| All after, validation succeeds, marker missing | Recognizably complete; explicit repair may finalize marker without duplicating IDs or memories. |
| Unknown digest, missing required payload, invalid lineage, conflicting operation | Ambiguous; pause and require human judgment. Preserve every artifact. |

Do not promise general rollback after partial application without before-images.
Report reversibility only when no canonical change occurred or when unchanged
original bytes are independently available and validated. Prefer explicit forward
completion. `recovery inspect` and `validate` are read-only; `repair` defaults to
dry run and needs explicit `--apply` with operation ID and a rechecked assessment.
Startup never silently repairs. An interrupted repair is itself idempotently
assessed using the same operation. Once committed, an operation ID can be queried
to resolve an ambiguous acknowledgment without rerunning the LLM.

Scope: local Linux filesystems honoring rename/fsync and cooperating processes.
Advisory locks cannot stop an external editor. Hash mismatches fail closed; disk
or hardware corruption is reported rather than claimed recoverable.

Recovery tests will kill a subprocess after preparation, after output creation,
after one input mark, after all input marks, after state replacement, and before/
after the committed marker. Also test interruption during repair, modified input,
missing payload, invalid references, stale SQLite, concurrent writers and repeated
repair. Assert exact remaining-file reports, blocked normal reads, no ID reuse,
no duplicate synthesis and preserved ambiguous bytes.

## Research adapters and LLM boundary

Historical candidates include Wikipedia, arXiv, PubMed, Crossref, Europe PMC,
ERIC and OpenAlex. arXiv's small urllib/Atom implementation is the proposed first
real adapter for a bounded physics/computing question: abstracts, authors, dates
and stable URLs provide useful provenance with standard-library dependencies.
PubMed adds a second fetch step; Crossref may lack abstracts; the others add scope
or configuration unnecessary for the initial demonstration. This is a source-code
assessment, not a fresh claim about provider availability or access requirements.
Verify the selected provider's official API contract and limits during Increment 4.
Do not carry over implicit keyword filtering, multi-provider fallback or AUTO routing.

The test adapter scripts successful, empty, failed and rate-limited responses.
Persist provider ID, submitted query, retrieval time, source IDs/URLs, title,
available authors/date, content and explicit abstract/excerpt/truncation labels.
An abstract is not silently represented as a read full paper. SQLite only searches
Mira's existing knowledge; it is never an external strategy database.

Proposed generation interface: one `generate(action, context, output_contract)`
call returning a validated structured proposal. R1 returns keywords; R3 returns
existing-format memory drafts plus cited result identifiers, or no-finding reason;
R4 returns decision/keywords/children/rationale; S2 returns a synthesis draft and
finding-level input references. Harness allocates all canonical IDs. Reject unknown
fields, unsupported references, incomplete output and attempts to set scheduler or
consumption state. An invalid response ends the attempt without another model
call. Exact prompts and fixture examples will be reviewed with each increment.
Provide a scripted fake first, then a configurable HTTP generation client; never
control the historical model service or add an SDK merely for one endpoint.

## Reviewable implementation sequence

| Increment/commit | Deliverable and acceptance evidence |
| --- | --- |
| 1, this proposal | Investigation, baseline tests, contracts and recovery design for owner approval. |
| 2a, approved persistence | Live-store integration through Knowledge, journal assessment/repair CLI, backward-compatible foundation API and crash tests. |
| 2b, controller | Explicit tree/action contracts, deterministic R1–R4 scheduler, fixture search and fake LLM, persistent pending results and read-only state CLI. Simulated multi-node trace demonstrates root 10/children 0, sustained turns, capped aging, oldest-first ties, all five decisions and terminal event. |
| 3, gardener | Five-action cadence, candidate scores, bounded source selection, atomic logical synthesis and lineage, all affected ancestor paths, completion and final drain. Demonstrate leaf-to-parent-to-root synthesis across three levels, zero/one-input completion and no resynthesis of complete nodes. |
| 4, integration | arXiv adapter, configurable generation client, real bounded question run, reproducible commands and inspectable artifacts. Assess citations, uncertainty and synthesis quality manually as well as structural tests. |

Keep existing tests passing. Add scheduling/state-transition, search-failure,
one-LLM-pass, restart, bookkeeping, batch-budget, termination and recovery tests.
Tests and demonstrations use isolated temporary roots and never historical data.
If a real endpoint is unavailable, report the integration demonstration as blocked
rather than substituting fixture output and calling it real research.

After approved implementation, open a code/tests PR with separate increment commits,
test/demo results, limitations and outstanding decisions. This proposal itself does
not claim implementation completion or authorize subsequent increments. Approval
requested for the numbered contracts and journal protocol above, particularly
empty-versus-failed searches, priority aging of new children, killed-node eligibility,
batch ordering/context reserves, final draining and logical transaction visibility.
