# Mira research architecture

Implemented architecture, 27 October 2026. This document describes the controller
in `src/mira/research.py`, tree contracts in `research_tree.py`, capacity/branching
in `branching.py`, and the synthesis gardener. Operational commands and live-run
evidence are in [research execution](docs/research_execution.md).

## Purpose and canonical knowledge

Mira investigates a root question, retains inspectable research and develops
specific child questions. A memory is a canonical Markdown document with a stable
ID (`r1`, `s1`), ordered units, provenance and a terminal Relationships section.
Findings use `#f1`, questions `#q1`, equations `#e1`, images `#i1`. Equation JSON
assets retain LaTeX, variable definitions, units and provenance. Images retain
source URLs or figure references; Mira does not download or invent images.
SQLite full-text, vector and relationship indexes are derived and rebuildable.

Models propose data. Python validates responses and owns all IDs, node creation,
priorities, memory construction, transitions, persistence and scheduling. Extracted
claims and model reasoning remain unverified; structural validity does not prove
scientific correctness.

## Persistent tree and action states

New experiments use `mira_research: 2` in `research/state.json`. Each node stores:

- Identity and monotonic creation order, question, reciprocal parent/child links.
- Research status, nonnegative priority, current keywords, previously tried terms,
  next database index and an optional immutable pending-evidence reference.
- Direct memory IDs, including research and synthesis memories with distinct kinds.
- An optional immutable `split_attempt` receipt, including proposed and accepted
  questions, discarded duplicates and whether the committed attempt was empty.
- Auditable `research_capacity`, structured ripeness counts and score.
- Separate synthesis frontier count, score, living-descendant count and
  `synthesis_complete` flag.

R1–R5 and S1–S2 are **actions**, selected for one controller cycle. They are not
persistent node statuses. Research statuses are:

| Status | Meaning | Further action |
| --- | --- | --- |
| living | Eligible for direct research | R1, R2, R3 or R4 according to local state |
| answered | R4 established a sufficiently complete contextual answer | Synthesis; descendants may still be active |
| killed | R4 found the direction irrelevant to parent/root | Retain corpus; exclude branch from normal synthesis |
| exhausted | Python determined direct research reached its token capacity | Eligible for the independent R5 queue |
| split | Its one branching opportunity was durably committed | Synthesis; descendants may still be active |

Normal transitions are `living → answered`, `living → killed`,
`living → exhausted`, and `exhausted → split`. R4 retry stays living. Synthesis
never changes these statuses. Canonical publication validates transitions and
rejects a cleared/changed split receipt or additional children after splitting.

The root starts at priority 10. R5 children start living at priority 0. Nodes and
memories are never deleted as a consequence of a research-status transition.

## Per-node research progression

The strategy is a configured ordered list of database IDs, with one pointer per
node. The CLI currently supplies arXiv; fixture providers support deterministic
tests. R2 calls no model. Action selection for a living node is:

| Action | Predicate | Result | Model calls |
| --- | --- | --- | --- |
| R1 | No keywords and no pending results | Generate targeted terms, apply deterministic control filter, persist terms | 1 |
| R2 | Keywords, no pending results, database pointer within strategy | Search next database; save evidence and advance on success/empty | 0 |
| R3 | Pending results | Validate ordered extraction; create a memory for a nonempty batch; clear pending reference | 1 |
| R4 | Keywords, no pending results, all databases tried | Evaluate direct research in question context | 1 |
| R5 | Selected exhausted node, no committed split receipt | Develop children, persist IDs and receipt; mark split even if empty | 1 |

An empty search skips R3. Failed/rate-limited searches retain the database pointer,
record the failure and stop the current bounded run. They do not kill the question.
Per-node keywords, pointer, pending results and history survive scheduling switches.

### R1: targeted terms

R1 receives the selected question, distinct root/ancestor context, previously used
terms, relevant memory excerpts and prohibited control terms. Prior terms are soft
avoidance guidance; essential terms may recur. Python removes prohibited literal
whole terms/phrases and rejects an all-control query. Previous terms never become
control terms. R1 memory excerpts remain explicitly untrusted and bounded; this
small retrieval projection is distinct from R5's complete direct-research context.

The prompt asks for one or two literal topic phrases. The arXiv controller joins
their distinct words as `all:"word1" AND all:"word2"`. Multiword components
are tokenized rather than requiring an exact contiguous sentence fragment.
Bare space-separated words otherwise produce broad OR-style arXiv retrieval.
The exact constructed query appears in evidence, events and history. The adapter
sends that query unchanged; other adapters retain their existing space joining.
No hidden fallback query or negative control-term operator is introduced.

### R3: ordered extraction and provenance

R3 returns exactly `{"results":[...]}`. Accepted result types are `finding`,
`observation`, `claim`, `inference`, `hypothesis`, `question`, `equation`, `image`.
Results preserve their sequence, source IDs, qualifications and optional
`related_to` indexes. Python validates source membership, type-specific fields,
index bounds and acyclic relationships before creating Markdown.

Questions require `origin: source|derived`. They become open `#q` units retaining
Origin, Qualification and Provenance; source relationships remain CITES edges and
result relationships become stable RELATED_TO edges. Derived questions must be
grounded in cited research, and are not attributed to its authors. Equations
preserve LaTeX, variable descriptions/units and source/derived attribution. Images
must reference supplied URLs or figure references. Empty extraction is valid and
creates no memory or ID. R3 never emits memory IDs or writes canonical files.

### R4: exactly three decisions

R4 receives the question, distinct ancestor context, all its direct research and
compact search history. It returns exactly `{"decision":"retry","reason":"..."}`.

- `kill`: the direction is off-track and does not meaningfully contribute to its
  parent or root. Unsuccessful retrieval alone is not grounds for killing it.
- `answered`: a sufficiently complete contextual answer is established; further
  direct investigation is unnecessary. This says nothing about descendant work.
- `retry`: it remains relevant and warrants more research. Python appends current
  terms to `previous_search_terms`, clears keywords, resets the database pointer
  and leaves it living. Its next direct action is R1.

R4 cannot generate keywords or children, declare exhaustion or create a separate
unresolved/blocked research disposition. Malformed or old five-way responses are
rejected with their raw output retained.

## Deterministic research capacity

`research_capacity_tokens` defaults to 75% of `context_budget`; both and
`output_reserve` are configurable. It is a threshold on the **estimated total R5
request**, including prompt/request overhead and the output reserve, rather than
on the number of memories. The conservative estimator uses UTF-8 request bytes
as estimated tokens. It intentionally overestimates typical English token counts;
it is not the server's tokenizer.

Before action selection and after successful actions, Python prepares the actual
R5 template using the selected model/settings, distinct question context, every
**direct research** memory in creation order and all referenced equation JSON.
It estimates the full request plus reserve. Direct research remains included even
when consumed by synthesis. Descendant research and every synthesis memory are
excluded. Consumption marks and revision changes are normalized in this view so
synthesis does not change capacity. No direct research is truncated or replaced
with summaries to make R5 fit.

At or above the configured threshold, a living node becomes exhausted and leaves
direct research scheduling. Pending retrieved evidence is processed before such
a transition, preserving it across upgrades/configuration changes. The assessment
stores byte/total estimates, threshold, hard context budget, reserve, direct input
IDs, model and request/template hashes. Exhaustion events record the crossing.

A newly committed memory may overshoot the threshold. The **entire** memory is
retained and the node is exhausted in that same journaled operation. The default
25% headroom reduces overshoots; it cannot guarantee arbitrary outputs fit. If
the complete R5 request exceeds the hard context budget, its assessment flags
`over_context_budget`, and the call stops explicitly with `blocked_context_budget`
before dispatch. No truncation, data loss or alternate research status occurs.
An operator must increase the configured budget within the server's actual limit,
or inspect the oversized material. This is a remaining operational limitation,
not an automatically repaired condition. Generation limits must fit output reserve.

Editable templates/settings are rechecked for future calls. Persisted assessments
are audit snapshots; canonical validation never reconstructs historical prompt
bytes from today's templates.

## Ripeness queue

Only exhausted nodes enter `ripeness_order`. The score starts as:

`ripeness = F + 2*H + 2*Q - D`

F counts distinct structured `Kind: finding` propositions; H counts distinct
hypothesis propositions; Q counts distinct open/partially answered question units;
D is root-relative depth (root zero). Counts use direct research units produced by
R3, including consumed research, not Markdown text-pattern guesses or syntheses.
Distinctness uses case-folded, whitespace-normalized text. Claims/observations do
not silently count as established findings. Q uses the stored question state;
Mira does not guess that a question is resolved from free prose.

Weights live in `ripeness_weights` and are easy to adjust. Higher scores run first,
with oldest monotonic creation order breaking ties. Scores may be negative at
depth; research priorities never are. There is no existing-children penalty.
The depth penalty discourages vertical growth without guaranteeing balance.

R5 sees all the selected node's direct accumulated research, root/parent context
and a configurable maximum child count (default 3). It may derive novel questions,
rather than only copying R3 questions/hypotheses. Output is an ordered
`{"questions":["Specific question?", ...]}`; an empty list is valid. Python removes
normalized duplicates against existing tree questions and within the proposal,
validates the child limit, allocates IDs and sets initial priority zero. An empty
or duplicate-only committed attempt still records `empty: true` and marks split.
Rejected/transport-failed attempts commit no split receipt and can be retried.

## Research priorities and controller scheduling

Each cycle performs one activity and **at most one model call**. There is no
uninterrupted global R1–R4 sequence: a different living node can run between any
two actions. After each successful direct research action, active priority loses
one down to zero and other living nodes gain one up to `priority_max` (10).
The active node keeps its turn until priority zero or ineligibility, when the
highest-priority living node is chosen, breaking ties by oldest creation order.
R5 and synthesis never age/reset another node's research progress.

Controller order is:

1. Reassess capacity and refresh queues.
2. If the synthesis cadence is due, run one S1/S2 and reset its counter.
3. Otherwise, if exhausted nodes exist and either no living nodes remain or
   `research_cycles_since_branching >= branching_interval`, run R5 on the ripest.
4. Otherwise run the active living node's next R1–R4 action.
5. With no living or exhausted nodes, drain eligible synthesis and then finish.

`branching_interval` defaults to five **direct research actions** between attempts
while living nodes exist. Successful R5 resets this counter. Consequently R5 can
run alongside living work, but repeated branching cannot starve available direct
research. If only exhausted nodes remain, R5 creates fresh work without waiting
for nonexistent research actions. Per-attempt child limits constrain the number
of unresearched children added; there is intentionally no speculative global
balancing algorithm or guarantee of bounded total tree size.

The synthesis cadence defaults to five research/branching work actions; R5 counts
as a work slot so branching cannot starve synthesis. S1 is a deterministic empty
or blocked selection; S2 consumes one model call. Branching and synthesis never
share a cycle with research. A terminal event is recorded only when neither
living research nor pending R5 remains; zero living nodes alone is not completion.

## Synthesis integration

The frontier consists of unconsumed direct research **and synthesis** memories
from the eligible subtree. Consumed originals are not included alongside their
synthesis. Killed branches retain all files and provenance but contribute neither
inputs nor candidates to normal ancestor synthesis. Existing syntheses whose
lineage contains a now-killed branch are excluded too, without deleting them.

A node's `synthesis_complete` flag means no living/exhausted work remains in its
eligible subtree and its frontier has at most one memory. An answered parent can
therefore remain synthesis-incomplete while its descendants research or await
R5. Exhausted nodes always retain their branching opportunity. Split nodes can
remain incomplete while descendants work. Completion does not relocate or consume
the final memory: it remains available to an ancestor.

Candidates need at least two frontier memories. Score is frontier count plus a
1000 terminal bonus when no living/exhausted eligible work remains below or at the
node. Candidate ties use creation order. Selection descends to a fitting child if
needed, then takes the oldest fitting pair and adds complete fitting inputs in
creation order. All request overhead and reserve are budgeted. No fitting pair
produces an explicit blocked-synthesis action and stops a bounded run.

S2 validates every referenced stable finding/question/equation/image anchor and
requires coverage of every input. Its new synthesis and input consumption marks
commit atomically with state. It never consumes a single memory, deletes research
or overwrites originals. Question-only memories are valid synthesis inputs;
unresolved questions must remain qualified as unresolved.

## Tree health and inspection

`research-state` exposes status totals (living, exhausted awaiting R5, answered,
killed, split), maximum depth, all-node and living-node distributions by depth,
active node, both queues, all per-node priorities/progress, synthesis accounting,
ripeness counts/scores/weights, capacity snapshots and configuration. It includes
branching/research/synthesis cycle totals, cadence counters and the last 20
successful actions with node IDs and timestamps. These provide evidence for later
policy tuning without an elaborate balancing mechanism now.

The read-only local viewer continues showing canonical state and the exact saved
request, prompt source/hash/bindings, raw model response, validation, outcome,
retrieved evidence, generated Markdown and historical tree changes. R5 is an
independent recorded action. Exports work without a running model or SQLite.

## Persistence, compatibility and recovery

Canonical live layout remains `memories/*.md`, `equations/*.json`, `identity.json`,
`research/state.json`, immutable `research/results/*.json` and `events/*.json`.
Independent `interactions/` records save the exact request before dispatch and
then raw response, validation and outcome. Indexes remain disposable.

Every multi-file operation uses the existing small journal: validated changed-file
after-images are fsynced, a prepared manifest is published before canonical edits,
individual atomic replacements are fsynced, and a committed marker appears only
after complete validation. R5 commits its receipt, child IDs, allocator and event
through this same protocol. A crash cannot silently grant a second committed split.

On incomplete operations, canonical access blocks for recovery assessment.
`recovery inspect/validate` are read-only assessments; `recovery repair ID` defaults
to dry run and `--apply` explicitly completes a safely finishable operation.
Actual hashes determine progress. Ambiguous files are retained and rejected,
never guessed away. Repeated repair recognizes the same operation without a model
call or duplicate children/memories. Unknown calls without canonical commitment
require transcript inspection and explicit interruption acknowledgement.

Version-1 state remains readable and validated by a retained compatibility module.
On the next successful controller action, an upgrade is journaled with that action.
Legacy `complete` is treated as old synthesis bookkeeping, **never** proof of an
answered question: without children it becomes exhausted; previously branched
non-killed nodes become split with a legacy receipt. Original statuses are retained
as `legacy_status`. Pending evidence on a formerly living, previously branched
node is retained as `legacy_pending_results` and in its immutable evidence file,
rather than discarded or directly rescheduled on a split node. Existing memory bytes, stable IDs, events, equation assets and
historical prompts are preserved. Inspection does not migrate experiments.

The old Phase 1 snapshot store remains supported separately. New autonomous
experiments use live persistence; no implicit import or whole-corpus snapshot is
introduced. Journal scans and full-tree refresh favor inspectability over extreme
scale. Backups, server management and automated research-quality evaluation remain
outside this controller.
