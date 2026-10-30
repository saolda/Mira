# Mira research architecture

Implemented architecture, 27 October 2026. This document describes the controller
in `src/mira/research.py`, tree contracts in `research_tree.py`, capacity/branching
in `branching.py`, and the synthesis gardener.

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

Python also owns the construction of bounded, task-specific **LLM input projections**.
It need not supply every stored item to every model call: indexed retrieval,
deterministic relevance ranking, recency, usage state, diversity and fair rotation
may select a manageable subset from much larger persistent collections. For
example, a node might retain 100 unused candidate search concepts and 30
previously used concepts while R1 receives only the 10 most relevant unused
candidates, plus a separate, appropriately bounded view of prior usage and
search outcomes. These figures illustrate the principle, not fixed limits.
Selection policies and omission counts must be inspectable, deterministic and
tested; an absent item in a projection does not mean that it was never known or
searched. Information excluded from a prompt remains in durable state for later
retrieval, with its provenance and status intact. Do not silently truncate
essential questions, complete research objectives or scientific evidence where
an action's contract requires them in full. The final rendered request must
still pass the actual model-tokenizer/context-budget check. Context curation is
a Python-harness responsibility; scientific interpretation and search choices
remain with the assigned LLM action, and child-question creation remains R5's
responsibility.

## Research question documents

`research-init` accepts either the existing positional question or
`--question-file PATH`. The UTF-8 Markdown document starts with a single
`# Research question` containing mandatory prose. Optional, unique `## Context`
and `## Research objectives` sections contain background and a Markdown list.
Unknown/deeper headings, empty sections and non-list objectives are rejected.
The parsed question preserves its original text, excluding blank separators,
and becomes the root node's question without normalization.

Initialization publishes the exact original bytes at `research/question.md`
together with `question_document` in `research/state.json`: canonical path,
SHA-256, question, separate context and verbatim objective Markdown items.
Both source and parsed fields are immutable and validated together on reads,
publication and journal recovery. Restart does not reread the external input.
Experiments without a question document retain the positional/legacy interface.

R0, R1, R3–R5 and S1/S2 receive a `research_brief` projection, alongside their
existing exact question/root/ancestor slots. All objectives are retained;
background paragraphs are ranked by selected-question word overlap, then bounded
to 2048 UTF-8 bytes for R0/R1, 1536 for R3, 3072 for S1 and 4096 for R4/R5/S2.
The projection identifies the source hash and explicitly flags excerpted context.
The raw document is never repeated in prompts. R2 has no model prompt and uses
R1's query. Existing exact rendered-request token validation includes the brief
for research capacity, selection and synthesis; essential questions/objectives
are never silently shortened to fit. A saved legacy S2 context defaults to no
brief. `research-state` exposes the parsed fields separately.

## Persistent tree and action states

New experiments use `mira_research: 2` in `research/state.json`. Each node stores:

- Identity and monotonic creation order, question, reciprocal parent/child links.
- Research status, nonnegative priority, current keywords, previously tried terms,
  next database index and an optional immutable pending-evidence reference.
- Direct memory IDs, including research and synthesis memories with distinct kinds.
- An optional immutable `split_attempt` receipt, including proposed and accepted
  questions, discarded duplicates and whether the committed attempt was empty.
- Auditable `research_capacity`, structured ripeness counts and score.
- Separate synthesis frontier count, living-descendant count and
  `synthesis_complete` flag.
- Experiment-wide synthesis-attempt register, pending S2 selection and
  terminal catalogue-evaluation fingerprint.

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

### Research strategies and query profiles

A **research strategy** is an ordered sequence of provider IDs, each with an
explicitly named query profile. Supported providers are Wikipedia, arXiv,
PubMed, Crossref, Europe PMC, ERIC and OpenAlex. Profiles are centrally
configured, named independently of providers and reusable: one provider may
have several compatible profiles, and one profile may serve several providers.
Every provider entry in a new strategy has a profile; explicit provider lists
use the compatible `default` profile unless another profile is selected.
An existing persisted experiment without profile metadata retains the exact
query semantics under which its search round began.

Exactly **one strategy is selected per experiment**, before its first R1.
The operator can select a named strategy explicitly; otherwise R0 uses its
editable `prompt_templates/R0.txt` to select from the predefined strategy
IDs, descriptions and ordered provider lists, returning a structured ID and
reason for Python validation. R0 runs once, outside the recurring research
cycles, and cannot invent strategies. Research begins only after its strategy
is validated and persisted. The strategy, provider order, profile IDs and
profile configurations/versions are snapshotted at initialization and
inherited by R5 descendants; R1–R5 cannot change them.

Each query profile defines a deterministic compiler and compatible providers,
field/quoting/escaping/Boolean combination rules, `max_terms`, a
`min_interval_seconds` request spacing, `retry_initial_seconds`,
`retry_max_seconds`, and `max_attempts` per provider-query. Profile values
are configurable; the starting term limits and timings are hypotheses to be
evaluated rather than empirically established optima. The `default` profile
preserves compatible basic search behaviour.

### Research rounds and action selection

Every living node maintains its own R1 concept list, **next database index**
(starting at zero), pending R3 evidence and deferred-provider searches. A
single R1 concept list is used for one complete pass through the selected
strategy's ordered databases. The index denotes the **next unvisited
database**, not the last database used. It survives node scheduling switches.

| Action | Predicate | Result | Model calls |
| --- | --- | --- | --- |
| R1 | No current concepts, pending evidence, deferred round or recorded no-viable-search disposition | Discover and retain 0–6 new concepts; select 1–6 ordered search concepts, or record `no_viable_search` | 1 |
| R2 | Concepts exist, no pending R3 source, and an eligible provider remains in the ordered pass or deferred queue | Compile and submit that provider's query; record outcome, source evidence and deferred work as appropriate | 0 |
| R3 | At least one pending, unprocessed source | Extract **one** source; atomically advance its processed-source cursor and store any accepted memory/glossary terms | 1 |
| R4 | A normal completed provider round **or** an R1 `no_viable_search` disposition, with no pending R3/deferred work | Evaluate the question; for a normal round decide `kill`, `answered` or `retry`; for no viable search decide `kill`, `answered` or `exhausted` | 1 |
| R5 | Selected exhausted node (capacity or R4 no-viable-search exhaustion) with no committed split receipt | Develop children; persist IDs and split receipt, including an empty split | 1 |

For each database in the initial pass, R2 either submits its query or
recognises that it cannot yet be submitted. After recording that outcome,
R2 advances the node's **next database index by exactly one**, including
for `empty`, `failed`, HTTP 429 and deferred/cooldown cases. Successful
nonduplicate results become pending R3 evidence, which is fully processed
before the node's next R2 action. An empty response produces no R3 action.

A provider not yet eligible to submit, or returning a retryable HTTP 429,
places its original provider-query into the node's deferred queue with
the provider index, attempt count and retry timestamp. This is **not a
terminal search outcome**; it does not advance the database index a second
time when retried. Once the initial index reaches the provider count, R2
revisits eligible deferred entries in original provider order, subject to
the provider availability policy. A deferred entry is removed only after
an actual terminal result or exhaustion of its allowed submission attempts.
Other nodes may execute between any two actions.

R4 is ineligible while deferred entries remain, even when the database
index has reached the end of the strategy. On a normal round's `retry`,
R4 appends the selected concepts to `previous_search_terms`, clears current
concepts and round outcomes, and resets the index to zero. On `kill` or
`answered`, the node's research status changes accordingly. A valid R1
`no_viable_search` instead records a distinct durable no-search disposition
(with no fabricated R2 results, no database-index advancement and no R3).
The next direct research action is R4 using the accumulated existing
research/search history and the no-viable-search reason. In this special case
R4 cannot return `retry`, which would repeat R1 on unchanged information.
It may return `exhausted` (relevant but no productive direct search is
available), `kill` or `answered`. `exhausted` enters the existing R5
ripeness queue without declaring that scientific evidence is sufficient or
claiming the research-capacity threshold was reached. Exhaustion cause is
persisted; R5 must accept either capacity or this explicit R4 disposition.
An unsuccessful retrieval does not itself prove the question answered,
irrelevant or exhausted.

### R2: query compilation and evidence

R1 supplies a **selected list of 1–6 ordered scientific search concepts**
when its disposition is `search`. An R1 `no_viable_search` supplies no
selected concepts and never dispatches R2. R1 separately proposes 0–6 new
concepts, which need not be selected in the current round. Each concept is
one scientific term or established multiword phrase of at most five words,
without provider syntax. Python validates and filters both arrays, preserving
accepted order; a `search` selection must remain nonempty.

For a provider, R2 retains the first `max_terms` accepted concepts in
priority order and discards the rest **for that provider only**. A multiword
concept is not split to meet this limit. The selected query profile compiles
those concepts to a provider-compatible query and API parameters using its
declared field, quoting, escaping and combination rules. R2 makes no LLM
call and issues at most one search submission per action, including any
protocol-required follow-up requests for selected source records.

The provider adapter performs transport and parses the response; query
construction and request pacing are profile-driven rather than hidden in
individual provider adapters. Persist and log the R1 concepts, retained and
discarded concepts, profile ID/version and configuration, compiled query,
actual request parameters (without credentials), submission status, result
identifiers, deduplication and retrieval outcomes. There are no hidden
fallback queries. A term is marked actually used in the glossary register
only when it appears in a **submitted** provider query, not merely in an R1
proposal or deferred request.

### Provider availability and retry scheduling

Availability is tracked per provider, independently of research nodes,
with persisted earliest permitted request time and consecutive rate-limit
failure count. Requests sharing an API host also obey the host's pacing
limit, even when their providers or query profiles differ.

A provider request must not begin before the later of its profile's
minimum-interval time, shared host pacing time and current cooldown expiry.
HTTP 429 is a retryable outcome, not an empty result. Valid numeric or
HTTP-date `Retry-After` values establish the earliest retry time; these
must not be shortened by local limits. Without a valid `Retry-After`,
retry delays grow exponentially from `retry_initial_seconds`, capped at
`retry_max_seconds`. Retry counters count actual network submissions, not
checks of an unexpired cooldown. A successful or empty response resets
consecutive rate-limit failures; other non-retryable failures are recorded
as `failed`.

Once a deferred request reaches `max_attempts` without a terminal
retrieval, its final outcome is `unavailable` and its deferred entry is
removed. `unavailable`, `failed` and `empty` are distinct; none
establishes a scientific conclusion about absent publications. A round
finishes only when every provider has a terminal `ok`, `empty`,
`failed` or `unavailable` outcome and all pending R3 sources are processed.

While one provider waits, other eligible providers, nodes, synthesis and
branching actions can proceed according to the existing scheduler.
If no productive action is eligible and the sole impediment is pending
provider availability, the controller returns `waiting_for_provider`
and the earliest retry timestamp, without publishing a research cycle,
calling an LLM or busy-looping. The supervisor may sleep until that time,
then resume the pending R2 query without invoking R1 again. Interrupted
submissions with uncertain outcomes require explicit recovery handling:
they are not silently retried or assumed empty.

Per-node concepts, database index, source cursor, deferred entries and
round outcomes, together with provider cooldown and pacing state, survive
scheduling switches, restarts and journal recovery.

### Research source deduplication and retention

Maintain a small **experiment-wide seen-source index**. Prefer stable publication
identifiers (DOI, PMID, arXiv ID or canonical source ID), with a normalized
(title, author) fingerprint as a conservative fallback; reconcile aliases across
providers where defensible. Previously accepted sources should be excluded from
later R3 extraction, including when another provider returns the same paper.
Avoid false matches between different versions or works; ambiguous identities
should not be silently discarded. During initial validation, retain **unique
retrieved source results** and enough identifiers/URLs to check provenance by
re-downloading the source. Do **not** require indefinite archival of full raw
provider responses or duplicate retrieval records: once the system is tested and
running, the intended normal policy is to discard cached research-source payloads
that are no longer needed, while keeping canonical research/synthesis memories,
source citations/identifiers and essential decision/recovery records. Retrieval
and retention policy must not break pending R3 processing, crash recovery or
existing experiments. This is a design target for implementation, not a claim
that current retention already behaves this way.

### R1: targeted search concepts

R1 receives the selected question, distinct root/ancestor context, previously used
terms, relevant memory excerpts and prohibited control terms. Prior terms are soft
avoidance guidance; essential terms may recur. Python removes prohibited literal
whole terms/phrases and rejects an all-control query. Previous terms never become
control terms. R1 memory excerpts remain explicitly untrusted and bounded; this
small retrieval projection is distinct from R5's complete direct-research context.
An indexed glossary projection adds relevant terms, aliases, concise definitions,
definition status, explicit relationships and per-node usage status. Selection
matches the question, its ancestors and relevant findings/gaps; novelty breaks
relevance ties, and sourced neighbours can extend discovery. At most 96 FTS hits
and eight neighbours per leading hit are considered, rather than scanning term
records. The default maximum is 12 entries (configurable up to 15), within a
3,200-token conservative UTF-8 byte upper bound. The independent
provider-search history has its own bounded input and does not consume this
budget. Both glossary settings are persisted by `research-init --glossary-token-budget` and
`--glossary-limit`. Sparse catalogues or smaller budgets supply fewer entries.
The complete request still passes the existing model-tokenizer budget check.
Glossary prose receives the existing untrusted-text filtering; definitions guide
terminology and are never independently verified scientific evidence.

The `question` input is the assigned scientific question. R1 neither
creates nor chooses child/subresearch questions: that is exclusively R5's
responsibility. `question_context` contains root/ancestor questions only to
resolve scope. `memory_context` supplies bounded relevant findings,
qualifications and gaps as terminology guidance, not independently established
truth. `research_brief` supplies optional background and complete research
objectives; background may be excerpted. `previous_search_terms` is a
bounded, labelled projection of previously proposed/selected terms, not a
claim that those terms succeeded or failed when searched.

R1 also receives a dedicated `search_outcomes` input: up to 12 most recent
committed provider-query outcomes for the selected node, in chronological order.
Each entry contains provider ID, profile ID when known, compiled query,
whether the query was actually submitted, outcome status, returned record count
and unique record count. Status distinguishes `ok`, `empty`, `failed`,
`rate_limited`, `deferred` and `unavailable`. An `ok` outcome confirms
retrieval, not relevance; `empty` means no provider matches for that query,
not absence of scientific evidence. Failed, deferred or rate-limited searches
give no evidence of query ineffectiveness. Search outcomes are built from
persisted retrieval records independently of the glossary and its byte budget.
Their absence means the retrieval history is unknown, not unsuccessful.
Only actual submitted queries count as glossary-term usage.

R1 records suggested glossary IDs in its event, without marking them used.
Only terms/aliases matched in an actually submitted provider query enter the
node's `used_glossary_term_ids` register and the corresponding R2
event/evidence history. Cooldown skips do not count; submitted rate-limited
requests do. Ambiguous abbreviations alone identify no concept. Previous
terms and outcomes inform soft reuse guidance without new query bans or
extra LLM calls.

R1 has exactly **two scientific responsibilities in one LLM call**:
(1) propose **0–6 genuinely new, useful concepts** for the assigned question
without inventing poor terms to fill a quota; and (2) **select 1–6 ordered
search concepts** from new or established terminology to advance that same
question. Selection requires scientific judgement by R1, not a deterministic
Python-assembled fallback. An unused discovery remains a candidate for later
rounds. R1 does not nominate a new subquestion or research objective.

The complete R1 JSON contract has exactly these fields:
`{"disposition":"search","new_concepts":[],"search_concepts":["term"],"reason":"Brief reason."}`.
`disposition` is `search` or `no_viable_search`; the latter requires
`search_concepts:[]` and a reason and is valid when no worthwhile untried
search can be selected. A `search` disposition requires 1–6 concepts and
a brief reason. Both concept arrays obey the existing at-most-five-words,
no-Boolean/provider-syntax and literal control-term validation. Python
conservatively normalizes/deduplicates terms, preserves complete raw and
accepted lists, and validates the selected concepts before publishing.

Python persists R1 discoveries in a durable **per-node concept-candidate
register**, separately from the source-grounded glossary. Record normalized
and original spelling, R1 origin, node, first discovery round/event, original
priority, unverified scientific status, selection count/last selected round
and actual submitted-provider usage count. Preserve unselected discoveries;
selection alone is not evidence of provider usage. Update actual usage only
when a profile retains the concept in a **submitted** R2 query; a term cut by
`max_terms`, a cooldown skip or a merely deferred query remains unused.
Existing selected and previously proposed terms remain available as distinct
historical terminology; do not upgrade a speculative R1 term to sourced
glossary status. Candidate state and audits survive restarts, journal recovery
and node scheduling. Legacy nodes/events without a register remain readable.

R1 receives separately labelled bounded projections: up to **10 unused R1
candidates** and up to **10 previous selected/proposed terms** by default,
with deterministic question/memory relevance, recency, stable ties and rotation
so omitted candidates are not permanently starved. These are configurable
projection limits, not caps on stored candidates. Each projection identifies
its full/visible/omitted counts, usage and unverified status. Keep the existing
independently bounded glossary and 12-search outcome projections; add a small
list of the active provider/profile IDs and `max_terms` to explain how the
ordered selection will be compiled. All underlying records remain durable,
including those omitted from R1, and the fully rendered request still passes
the tokenizer budget. Python handles the bounded input, not R1's scientific
term selection.

For a `search` disposition Python compiles the candidate ordered selection
under **every active query profile without submitting**, then compares the
provider ID, actual query text and relevant public request parameters against
the node's **complete** persisted history of actually submitted terminal
`ok`/`empty` searches. At least one provider must have a previously
unsubmitted effective query under this criterion; another provider's repeated
query does not invalidate the whole round. Failed, unavailable, rate-limited
and unsubmitted/deferred searches do not establish ineffectiveness and do not
count as completed-query duplicates. No hidden fallback, automatic query
replacement or additional LLM call is permitted. An invalid repeat-only
selection is rejected with its raw response retained, not misreported as
`no_viable_search`. R2 otherwise retains its existing one-query-per-provider
order, profile pruning, deduplication, retry and audit semantics.

On a valid `no_viable_search`, persist any new discoveries and its reason,
do not fabricate provider activity, and route immediately to R4. R4 can
choose `exhausted` for a relevant question with no useful direct search,
leading eventually to R5, or `kill`/`answered` when justified by existing
research. No `retry` is permitted in this special case. This is separate
from capacity exhaustion and never means that lack of search results proves
a scientific conclusion.

### R3: ordered extraction and provenance

R3 returns `{"summary":"...","results":[...],"terms":[...]}` in one model call per
source. The model summary covers the complete extraction and its limitations;
Python does not construct it from a finding. Accepted result types are `finding`,
`observation`, `claim`, `inference`, `hypothesis`, `question`, `equation`, `image`.
Results preserve their sequence, source IDs, qualifications and optional
`related_to` indexes. Python validates source membership, type-specific fields,
index bounds and acyclic relationships before creating Markdown.

Questions require `origin: source|derived`. They become open `#q` units retaining
Origin and nonempty Qualification; result relationships become stable RELATED_TO
edges. Derived questions must be grounded in cited research, and are not attributed
to its authors. Equations
preserve LaTeX, variable descriptions/units and source/derived attribution. Images
must reference supplied URLs or figure references. Empty extraction is valid and
creates no memory or ID. Python discards any supplied summary string when results
are empty and records that normalization; the raw response remains unchanged.
R3 never emits memory IDs or writes canonical files.
The optional `terms` array defaults to empty for legacy responses; its independent
admission contract is specified below. Empty results with useful terms create no
empty memory or research-memory ID.

Each independently identifiable source produces at most one research memory per
experiment. A pending batch is processed one source per R3 action; its processed
source index and memory commit together, allowing restart without duplicate
extraction. Empty sources are also marked processed. R3 remains extractive; S2
integrates across memories.

Invalid received R3 output (decoding, schema or memory-format errors) is logged
with the source ID and raw response. Python discards partial memory/equation/ID
changes, marks the source processed, and continues to the next pending source or
database without retrying it. The source disposition and scheduling counters commit
atomically; the interaction's validation record still marks the response invalid.
Context, transport, retrieval-cache and persistence failures retain their existing
safeguards rather than silently discarding evidence.

New single-source research Markdown has compact metadata (including the source
identifier, title, publication date, URL and content kind when supplied), Summary,
Knowledge and terminal structured Relationships sections. Knowledge headings retain
stable anchors and types, with propositions directly below, nonempty qualifications,
and explicit question/equation origins. Equation assets, variables, units and image
references remain intact. Allocators and required journal/lineage metadata persist;
author lists and repeated default evidence labels/citations are omitted.
Every unit inherits the memory's source in provenance resolution and rebuildable
relationship indexes; redundant canonical CITES edges are unnecessary. Retrieval,
synthesis lineage and evidence auditing can resolve this inheritance without
attributing derived objects to source authors. Legacy Markdown and explicit CITES
edges remain readable. Subsequent actions use the compact representation directly;
structured synthesis projections retain the source and all substantive units.

### Research glossary

Each experiment stores durable `glossary/g1.json`, `g2.json`, etc. IDs are decimal,
monotonic and independent of memory IDs. Records retain the canonical spelling,
aliases, multiple sourced definitions and qualifications, supporting passages,
source IDs, immutable retrieval references, relevant node IDs and typed links to
other terms. Status is `candidate`, `source_defined` or `multiple_definitions`;
different definitions remain separate with their provenance rather than silently
replacing one another. These are terminology records, not new knowledge-unit types.

R3 may propose up to five terms per source in its existing call. Each proposal has
exactly `term`, nullable `definition`, `aliases`, `relationships`, `source_id`,
`passage` and `qualification`. Relationship proposals name another term and use
`SYNONYM_OF`, `BROADER_THAN`, `NARROWER_THAN` or `RELATED_TO`. Python verifies the
source ID and exact supporting passage against supplied source content. Non-null
definitions must quote a definitional statement containing the term within that
passage. Otherwise the model should supply a candidate with null definition.
Aliases require explicit naming evidence, and relationships require explicit
supported wording; co-occurrence alone is insufficient. Unknown relationship
targets are logged and omitted. Invalid optional proposals are logged independently
and cannot reject otherwise valid substantive extraction. Invalid substantive
extraction retains the existing skipped-source behavior and admits no terms.

Matching uses Unicode normalization, case folding, whitespace and hyphen-spacing
normalization, without fuzzy scientific equivalence. A source-supported redundant
parenthetical abbreviation in a canonical label is separated into its alias.
Expanded names merge conservatively; shared abbreviations do not merge concepts,
and bare acronym labels retain definition/source scope. Definition and relationship
grounding is deliberately conservative textual validation, not semantic verification.

`glossary.sqlite3` is a disposable exact-name/alias, FTS5 and relationship directory.
Normal retrieval and deduplication use indexed bounded lookup and deserialize only
selected or touched records. An absent, stale or corrupt directory is rebuilt or
incrementally caught up from committed journal hashes and canonical records.
Rebuilds and explicit full integrity audits may scan all terms; ordinary R1 does
not. The index is refreshed lazily after commitment, so a cache failure cannot
partially publish terminology. `glossary-rebuild --experiment NAME` explicitly
rebuilds it. `glossary-export --experiment NAME` atomically regenerates the derived,
case-insensitive alphabetical `research/glossary.md`, including evidence and links.
R3 never rewrites that whole export; it may be stale until explicitly regenerated.

### R4: round evaluation and no-viable-search exhaustion

R4 receives the assigned question, ancestor context, all direct research,
compact **actual** provider-search history and a `search_availability`
projection indicating `completed_round` or `no_viable_search`, including
R1's reason for the latter. R4 returns exactly
`{"decision":"retry","reason":"Brief explanation."}` with one of these
context-dependent decisions:

- `kill`: off-track relative to the selected, parent or root question.
- `answered`: enough scientific evidence exists to answer the selected
  question adequately. Retrieval failure alone never suffices.
- `retry`: **completed provider round only**; further direct searches are
  worthwhile. Reset terms/index for another R1 as before.
- `exhausted`: **no-viable-search only**; question remains relevant but
  R1 identified no worthwhile untried direct search. Persist the distinct
  `no_viable_search` exhaustion cause and hand off to R5's existing queue.
  This does not claim that the research-capacity threshold has been reached.

The validated decision set is `kill|answered|retry` for a completed round
and `kill|answered|exhausted` for no viable search. R4 never creates terms
or child questions; R5 alone may develop child questions. A no-viable-search
result never fabricates a completed provider pass or invokes R2. Persist R4's
cause/decision atomically with the state transition, and retain the existing
complete research input and source provenance. Malformed outputs are rejected.

## Deterministic research capacity

`research_capacity_tokens` defaults to 75% of `context_budget`; both and
`output_reserve` are configurable. It is a threshold on the **estimated total R5
request**, including prompt/request overhead and the output reserve, rather than
on the number of memories. The HTTP model uses llama.cpp's chat template and
tokenizer, including special tokens; its active context window is the default
budget. UTF-8 byte estimates remain a labelled fallback for fixture transports.

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
stores token counts, byte sizes, threshold, hard context budget, reserve, direct input
IDs, model and request/template hashes. Exhaustion events record the crossing.
Exhaustion is published before that node's R5 dispatch.

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

Only exhausted nodes enter `ripeness_order`, whether exhausted by the
existing deterministic capacity threshold or by R4's explicit
`no_viable_search` exhaustion decision. Capacity-based R5 checks apply to
the former; for the latter record and validate the R4 decision/event as the
exhaustion cause instead of requiring a threshold crossing. The score starts as:

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
and a configurable maximum child count (default 3). Every child must be grounded
in specific supplied evidence or an unresolved issue and advance its parent/root.
Output is an ordered
`{"questions":["Specific question?", ...]}`; an empty list is valid. Python removes
normalized duplicates against existing tree questions and within the proposal,
validates the child limit, allocates IDs and sets initial priority zero. An empty
or duplicate-only committed attempt still records `empty: true` and marks split.
Rejected/transport-failed attempts commit no split receipt and can be retried.

## Research priorities and controller scheduling

Each cycle performs one action and **at most one model call**. S1 and S2
occupy separate cycles; a validated S1 selection persists for S2. There is no
uninterrupted global R1–R4 sequence: a different living node can run between any
two actions. After each successful direct research action, active priority loses
one down to zero and other living nodes gain one up to `priority_max` (10).
The active node keeps its turn until priority zero or ineligibility, when the
highest-priority living node is chosen, breaking ties by oldest creation order.
R5 and synthesis never age/reset another node's research progress.

Controller order is:

1. Reassess capacity and refresh queues, including eligible deferred provider
   searches and per-node `waiting_for_provider` times.
2. If an S2 selection is pending, run S2. Otherwise, when synthesis is due
   and a permitted candidate combination exists, run S1.
3. Otherwise, if exhausted nodes exist and either no living nodes remain or
   `research_cycles_since_branching >= branching_interval`, run R5 on the ripest.
4. Otherwise run an eligible living node's next R1–R4 action. Nodes waiting
   exclusively on provider cooldown do not block other ready living nodes.
5. With no living or exhausted nodes, invoke S1 on unevaluated eligible
   combinations, then finish when no pending S2 or permitted opportunity remains.
   Living nodes awaiting deferred provider queries remain unfinished.

When all otherwise eligible work is blocked solely by provider retry times,
return `waiting_for_provider` and the earliest retry timestamp without
advancing research-cycle counters.

`branching_interval` defaults to five **direct research actions** between attempts
while living nodes exist. Successful R5 resets this counter. Consequently R5 can
run alongside living work, but repeated branching cannot starve available direct
research. If only exhausted nodes remain, R5 creates fresh work without waiting
for nonexistent research actions. Per-attempt child limits constrain the number
of unresearched children added; there is intentionally no speculative global
balancing algorithm or guarantee of bounded total tree size.

The synthesis cadence defaults to five research/branching work actions; R5 counts
as a work slot so branching cannot starve synthesis. S1 and S2 each consume one
model call and run in separate cycles. Branching and synthesis never share a
cycle with research. A terminal `no_candidate` must not trigger repeated S1
calls against an unchanged catalogue. A terminal event is recorded only when
neither living research, pending R5, pending S2 nor permitted synthesis work
remains; zero living nodes alone is not completion.

## Synthesis actions: S1 and S2

### S1: model-assisted synthesis selection

S1 is eligible whenever at least two frontier memories form a permitted,
previously unattempted combination. Python schedules S1 after every five
completed research or branching actions (configurable through
`synthesis_interval`), or immediately when no research or branching work
remains. A pending S2 action always takes precedence.

Python supplies a catalogue of eligible research and synthesis memories:
ID, content hash, owning question and ancestor context, summary, knowledge-unit
types, provenance, lineage and estimated S2 token cost. Killed branches and
ineligible synthesis lineage are excluded. S1 makes **one fresh LLM call**
to propose at least two memories and a specific analytical objective, or
return `no_candidate`. Selections may cross research branches.

S1 estimates *synthesizability* with five 0–5 scores: shared-question
relevance (R), complementarity (C), contradictions worth examining (X),
potential new understanding (N), and evidence adequacy (E). The initial
score is R+C+X+N+E. Addressing the same question increases R, but is neither
required nor sufficient. Prefer focused, coherent groups over large,
weakly related collections. Record the component scores and rationale.

Python rejects unknown, ineligible, previously attempted or oversized
selections. Budget measurement includes the full S2 request, chat overhead
and output reserve. Complete memories are preferred; deterministic structured
projections may omit bookkeeping but must preserve substantive units,
qualifications, sources and relationships. An oversized selection is rejected
or deferred, never silently reduced. Each S1 invocation reassesses current
evidence; model decisions are never cached or reused. `no_candidate`
creates no memory and consumes nothing.

### S2: analytical synthesis

S2 receives S1's objective and selected memories and performs cross-memory
analysis in **one LLM call**. It returns `synthesis` or `no_synthesis`.
A valid synthesis requires at least one substantive finding integrating
knowledge units from **two distinct input memories**. Findings cite stable
anchors, preserve uncertainty and provenance, and distinguish reported
claims from independently demonstrated results.

Python validates references and derives contributing memory IDs from the
accepted findings. Only contributing memories are consumed; unused inputs
remain on the frontier. A partial synthesis is valid. `no_synthesis` creates
no memory and consumes nothing. Both dispositions complete the attempt.
Invalid output commits no synthesis or consumption. On success, Python
atomically commits the synthesis memory, consumption marks and attempt record;
original memories remain stored and traceable.

### Synthesis-attempt register

Persist each S2 attempt with selected memory IDs and content hashes, S1
objective/scores, interaction IDs, S2 disposition, contributing/unused IDs,
reasons and resulting synthesis ID (if any).

For a **completed** attempt with memory-version set A, reject subsequent
selections B whenever **B ⊆ A**. Thus attempting `{r1,r2,r3}` excludes
`{r1,r2}`, but not `{r1,r2,r4}`. The rule applies to successful, partial
and `no_synthesis` outcomes; changed memory hashes count as new versions.
Pending and failed attempts do not permanently exclude combinations.
Record pending dispatches for crash recovery; completed attempt registration,
synthesis creation and consumption marks commit atomically.

## Synthesis integration

The frontier contains eligible, unconsumed research and synthesis memories
within a node's subtree. A synthesis replaces only contributing inputs in
the frontier; unused inputs remain. Consumed originals are retained. Killed
branches and syntheses with killed-branch lineage are excluded.

A node is `synthesis_complete` when no living/exhausted work remains in its
eligible subtree and no permitted synthesis combination remains. Multiple
frontier memories may remain after all combinations are attempted or S1
returns `no_candidate`. To prevent repeated terminal S1 calls on unchanged
evidence, record the evaluated catalogue fingerprint; this is a scheduling
guard, **not reuse of an S1 decision**. New or revised memories invalidate
the guard and reopen eligibility.

Answered or split parents may remain incomplete while descendants work.
Exhausted nodes retain their R5 opportunity. A final synthesis memory
remains available to ancestors.

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

Research executions additionally export existing interaction phases and action
events incrementally to one append-only JSONL file under `memory/run-logs/`,
independent of the experiment directory. Each CLI initialization/run/demo and each
`Research.run()` starts a fresh execution; custom supervisors may group calls with
`Research.execution()`. Records retain chronological sequence, experiment/node/
cycle and interaction IDs, model/settings, exact sent prompts and supplied inputs,
template provenance, raw/proposed/normalized responses, token measurements, full
returned search evidence and committed canonical after-images. Configured secrets
are redacted. Each record is flushed/fsynced; normal termination and exceptions
are recorded, while abrupt process death may leave no end marker or a partial last
line. These files are diagnostic exports, not a competing recovery store.

On resume, a missing interaction outcome may be reconstructed once from a proven
committed event. Its original request/response/validation are exported as recovery
context, without relabeling them as new model calls. Unknown calls still require
explicit acknowledgement; incomplete journals still require existing repair.

## Persistence, compatibility and recovery

Canonical live layout remains `memories/*.md`, `equations/*.json`, `identity.json`,
`research/state.json`, immutable `research/results/*.json`, `events/*.json` and
per-term `glossary/g*.json` records.
Independent `interactions/` records save the exact request before dispatch and
then raw response, validation and outcome. Indexes remain disposable.

Catalog metadata `experiment.json` records creation and explicit retain/disposable
policy outside the canonical corpus. A `.runner.lock` lease spans executions;
the existing writer lock continues to serialize individual operations. Cleanup is
an explicit CLI/catalog operation, never a scheduling action. Its default is a
read-only deletion plan with names, dates, sizes and status. Applying deletion
requires named, completed, explicitly disposable experiments and rechecks runner/
writer locks, pending work, interaction outcomes and recovery integrity. Legacy
unclassified and retained runs are protected. Retention designation is separate
from deletion. No symlinks are traversed; confined, fd-safe deletion follows a
durable archive of interaction and canonical records in the independent log home.
Cleanup never removes run logs, user reviews or milestone reports. Ordinary
development test reports overwrite `test-results/latest.md`.

Every multi-file operation uses the existing small journal: validated changed-file
after-images are fsynced, a prepared manifest is published before canonical edits,
individual atomic replacements are fsynced, and a committed marker appears only
after complete validation. R5 commits its receipt, child IDs, allocator and event
through this same protocol. A crash cannot silently grant a second committed split.
Glossary edits use the same journal operation as the R3 memory, processed-source
cursor and event. Only affected records are staged/replaced. State stores the term
allocator, revision, budgets and a hash-chain commitment to changed term hashes;
this binds sparse glossary updates into the canonical revision without reading
the full glossary on each action. Recovery checks touched after-images and their
commitment before completing the joint operation. Indexed reads verify selected
record hashes against the committed directory; full validation and recovery
inspection verify every term against journal hashes, including missing/unregistered
records and dangling glossary links. Untouched record damage is detected by its
next lookup or an explicit full audit, not by a full scan at each R1.

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
Experiments and historical R3 responses without glossary fields remain valid;
the glossary is initialized lazily when terminology is first admitted.

The old Phase 1 snapshot store remains supported separately. New autonomous
experiments use live persistence; no implicit import or whole-corpus snapshot is
introduced. Journal scans and full-tree refresh favor inspectability over extreme
scale. Backups, server management and automated research-quality evaluation remain
outside this controller.
