# Mira research architecture

This document specifies Mira's desired scientific research and knowledge-synthesis
architecture, independently of implementation milestones. Mira investigates
scientific questions through a research tree and develops understanding through
a cross-branch network of source-grounded knowledge units. Scientific evidence,
model-derived interpretations and unverified hypotheses retain distinct provenance
and status.

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

## Canonical research and synthesis memory formats

New canonical memories are readable Markdown files with stable identities:
`memories/r*.md` for source-derived research and `memories/s*.md` for synthesis.
Both use the same **compact version-2 layout**: a title, small JSON metadata
header, `## Summary`, `## Knowledge`, and terminal `## Relationships`.

**Research example** (illustrative values, not scientific evidence):

~~~markdown
# Research: Selected question

```json
{"version":2,"id":"r1","revision":1,"kind":"research","node_id":"q1","created_order":1,"next":{"f":2,"q":1,"e":1},"source":{"id":"source-1","url":"https://example.org/study"},"evidence_ref":"research/results/example.json","source_memories":[],"synthesized_by":null}
```

## Summary

A concise, source-qualified account of this paper's findings.

## Knowledge

### #f1 | Finding

A proposition extracted from the source.

Qualification: Limits, study population, uncertainty and context.

## Relationships

```json
{"relationships":[]}
```
~~~

A research memory represents **one source**. Its source ID/URL and immutable
retrieval reference establish provenance. `#f` anchors denote findings
(including claims, observations, inferences or hypotheses); `#q` denotes
questions; `#e` equations; `#i` images. Equation assets retain their
independent JSON records. Optional qualifications and explicit `RELATED_TO`
relationships are retained. The summary does not imply independent verification.

**Synthesis example** (illustrative values):

~~~markdown
# Synthesis: Combined evidence

```json
{"version":2,"id":"s1","revision":1,"kind":"synthesis","node_id":"q1","created_order":3,"next":{"f":2,"q":1,"e":1},"lineage_mode":"knowledge_units","source_memories":["r1","r2"],"synthesized_by":null,"synthesis_unit_versions":[{"id":"r1#f1","version":"0000000000000000000000000000000000000000000000000000000000000000"},{"id":"r2#f1","version":"0000000000000000000000000000000000000000000000000000000000000000"}]}
```

## Summary

Integrated findings and their unresolved limitations.

## Knowledge

### #f1 | Combined evidence

An integrated proposition supported by the cited memory units.

Evidence status: unverified
Explanation: How the cited findings agree, differ or remain limited.
Qualification: The inference remains limited by the supplied populations and methods.
Epistemic type: inference
Provenance: Interpretation restricted to the supplied sources.

## Relationships

```json
{"relationships":[{"from":"f1","type":"SYNTHESIZES","to":"r1#f1","status":"unverified"},{"from":"f1","type":"SYNTHESIZES","to":"r2#f1","status":"unverified"}]}
```
~~~

A synthesis memory is **not itself an independent source**. It has a
`summary`, integrated anchored findings, stable `SYNTHESIZES` relationships
to input knowledge units, and `source_memories`/optional `synthesis_inputs`
lineage metadata. It has **no separate `conclusion` field**: its propositions
carry conclusions, and the summary states their scope and limitations.
Each synthesis finding retains its `Kind=synthesis` and
`Evidence status=unverified`; the compact parser derives the Kind from
memory metadata, not the human-readable finding label. Preserve exact input
anchors, source lineage, qualifiers, revisions and ID allocators.

Markdown should display the scientific content first. Machine-only
bookkeeping stays in compact metadata; do not duplicate it in prose.
Rendering and parsing must be lossless, including journal/recovery,
relationships and historical citations. **Existing verbose version-1
synthesis memories remain parseable** for compatibility, but new synthesis
memories use the compact format. No model-generated content is rewritten
or invented during format conversion.

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

R0, R1, R3–R5, S2 and S3 receive an appropriate `research_brief` projection
alongside the task-specific question, objective and evidence. All objectives
are retained; background paragraphs are relevance-ranked and bounded (initially
2048 UTF-8 bytes for R0/R1, 1536 for R3, and 4096 for R4/R5/S2/S3).
S1 is deterministic and does not have an LLM prompt. The projection identifies
the source hash and explicitly flags excerpted context. The raw document is not
repeated in prompts. R2 has no model prompt and uses R1's query. Exact rendered-
request token validation includes the brief and output reserve; essential
questions, objectives and scientific evidence are never silently shortened.
`research-state` exposes the parsed question-document fields separately.

## Persistent tree and action states

New experiments use `mira_research: 2` in `research/state.json`. Each node stores:

- Identity and monotonic creation order, question, reciprocal parent/child links.
- Research status, nonnegative priority, current keywords, previously tried terms,
  next database index and an optional immutable pending-evidence reference.
- Direct memory IDs, including research and synthesis memories with distinct kinds.
- An optional immutable `split_attempt` receipt, including proposed and accepted
  questions, discarded duplicates and whether the committed attempt was empty.
- Auditable `research_capacity`, structured ripeness counts and score.
- Synthesizable knowledge-unit counts, living-descendant count and the
  derived `synthesis_complete` flag.
- An experiment-wide, unit-version-based synthesis-attempt register, deterministic
  candidate frontier, pending S2 evaluations and pending S3 objectives.

R1–R5 and S1–S3 are **actions**, selected for one controller cycle. They are not
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

**R1–R5 are controller actions, not persistent node states.** One controller
cycle performs one action and at most one LLM call. A **research round** is
one R1 search plan executed against the selected strategy's ordered
providers, with R3 extraction between provider searches, followed by R4.
Other research nodes and synthesis actions may be scheduled between steps.

| Action | Name | Responsibility | Key variables / effects | LLM calls |
| --- | --- | --- | --- | ---: |
| **R1** | **Plan** | Discover 0–6 genuinely new concepts and select one ordered search plan for the **whole provider round**. | Read selected `question` and bounded context; supply `term_limit = max(profile.max_terms)` for this strategy; persist new candidates and accepted `keywords`/`search_concepts`; increment `search_round`; reset `next_database_index=0`. Empty/repeat-only selection sets a durable `search_blocked` flag. | **1** |
| **R2** | **Search** | Compile and execute **one logical provider search** using the **same R1 concept list**. | Read `keywords`, `next_database_index` and the provider's snapshotted query profile; advance index **once on first visit**; record `provider_outcomes`, query/receipt and optional `deferred_searches`; set `pending_results` for new sources. | **0** |
| **R3** | **Extract** | Extract one previously unprocessed retrieved source. | Read `pending_results` and the per-source processed cursor; create at most one `r*` memory, accepted glossary terms/equations and source disposition; advance processing state atomically. | **1** |
| **R4** | **Assess** | Assess whether relevant direct and synthesized scientific evidence answers the selected question, is irrelevant to both parent and root, or remains unresolved. | Read `question`, `question_scope`, `scientific_evidence`; return `answered|kill|unresolved`. Python persists `last_r4_assessment`, updates `status=answered|killed`, resets R1 when unresolved and unblocked, or sets `exhaustion_reason=search_blocked` and `status=exhausted` when unresolved and blocked. | **1** |
| **R5** | **Branch** | Develop child research questions from an eligible exhausted node. | Read `status=exhausted` and ripeness; allocate child node IDs; persist `child_ids`, `split_attempt` and `status=split` (even for an empty split). | **1** |

A normal progression is `R1 → R2 → R3 (one action per source, if any)
→ R2 → … → R4`. In particular, **R1 is not re-run between providers**.
R2 may make multiple HTTP requests as part of **one logical provider search**,
but never searches two providers within one controller action.

Each living node keeps its own selected concepts, `next_database_index`
(the **next unvisited provider**, starting at zero), pending evidence,
completed outcomes and deferred-provider requests. These survive node switches,
crashes and journal recovery. A provider visited for the first time advances
the index exactly once, even on an empty/failed/deferred outcome. An eligible
deferred request is retried with the **original query** without advancing
the index again. R3 fully processes pending unique sources before the
next R2 action. R4 cannot assess a normal completed round while R3
evidence or deferred work remains.

Python compiles each provider's **own prefix** of the shared ordered list
using that provider's snapshotted `max_terms` and compiler. If a compiled
provider query for this node has already completed with `ok` or `empty`,
R2 records a deterministic duplicate skip referring to the original
search outcome; it does not make a duplicate network call or fabricate
retrieval evidence. Failed or unsubmitted/deferred queries are not evidence
that a search has been adequately performed. At least one non-duplicate
effective provider query is needed for a productive R1 round.

When R1 returns no selected concepts, or every effective provider query
would repeat completed work, Python records its discoveries plus
`search_blocked=true` and its reason, with **no fictitious R2/R3 actions**.
A blocked node remains `living` for its next eligible R4 assessment.
R4 judges the available science; Python declares it `exhausted` only if
R4 returns `unresolved`. An `answered` or `kill` assessment instead
sets the corresponding terminal research status. No R1/R4 retry loop is
permitted while `search_blocked`. Capacity exhaustion remains separate.

### R2: query compilation and evidence

R1 supplies **one ordered list of 0–`term_limit` concepts** for
the entire provider round, where `term_limit` is the largest configured
`max_terms` in the selected snapshotted strategy (currently 1–6 by
profile validation). An empty or repeat-only list is **blocked** and does
not dispatch R2. R1 separately discovers 0–6 new concepts, which need not
be used in the current list. Python validates and filters both arrays.
Each concept is one scientific term or established multiword phrase of at
most five words, without provider syntax.

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

### R1: discovery and search-term selection

R1 performs exactly **one LLM call per research round**, with three tasks
in priority order: **discover** 0–6 genuinely new scientific concepts,
**select** up to `term_limit` concepts for the shared search plan, and
optionally **define** up to three relevant existing glossary terms that lack
applicable independently sourced definitions. Definition generation is subordinate
to search planning and does not require an additional LLM call. Zero discoveries,
zero selected concepts or zero definitions are each permitted when justified.
Selection may reuse established concepts and need not use newly discovered ones.
R1 does not create subquestions; R5 does that. Do not invent terminology merely
to appear novel.

Python supplies **only the inputs that inform these tasks**:

| R1 input | How R1 uses it |
| --- | --- |
| `question` and `question_scope` | Identify the assigned scientific target; ancestor context only disambiguates scope, never replaces the question. |
| `research_context` | Use relevant qualified findings, limitations and unresolved evidence gaps to guide terminology; do not assume extracted claims are verified. |
| `term_context` | Consider compact relevant glossary terms, previously selected terms and unverified unused R1 discoveries; reuse known terms but do not report them as new concepts. |
| `completed_queries` | **Do not repeat** provider searches already completed for this node. The input is a bounded relevant view; Python validates against the **complete** persisted history. |
| `term_limit` | The **single integer maximum** across the profiles of providers in the current strategy; order up to this many concepts by search value. No individual-provider profile list is supplied. |
| `control_terms` | Exclude supplied prohibited terms/phrases. |

The structured response contains `new_concepts`, `search_concepts`,
optional `provisional_definitions` and `reason`. Definition proposals identify
an existing supplied glossary ID and include `definition`, `scope` and
`ambiguity`; the list is bounded to three and may be empty. Legacy responses
without the optional field remain interpretable. New concepts number 0–6;
selected concepts number 0–`term_limit`. An empty selection is valid when
no worthwhile distinct search exists. Each concept is one meaningful term
or phrase of at most five words, without Boolean operators, provider names,
field tags or query syntax. Python validates individual components; malformed
or unsupported optional definitions do not invalidate an otherwise valid
search plan. Accepted `search_concepts` become the round's `keywords`.

Python retains every newly proposed concept in a **durable per-node
candidate register**, separate from the source-supported glossary.
Preserve original and normalized spelling, node, discovery round/event,
order, `unverified` status, selection/consideration state and actual
submitted-query usage. A concept not selected immediately must not be
lost; a concept merely considered or selected has not necessarily been
used by a submitted provider query. Deduplicate conservatively.

Python constructs bounded, deterministic, inspectable projections, rather
than flooding R1 with all stored information: initial limits are up to
10 relevant unused candidates and 10 relevant prior terms, with stable
ranking, fair rotation and visible omitted counts. The complete candidate
records, provider-query results and source provenance remain durable.
The exact rendered prompt and output reserve must fit the tokenizer
budget; essential question/objectives are not silently truncated.

For a nonempty selection, compile its effective query for each active
provider **without network submission** and compare against the node's
complete completed-query history. R1 must avoid repeated completed searches;
Python enforces the rule and R2 skips any individually repeated provider
query. If all providers would repeat, the entire selection is nonproductive
and treated like an empty selection, not an invalid JSON/model response.
No hidden fallback, LLM retry with identical context or automatic
Python-generated scientific terms is permitted. Preserve the exact raw
model response and normalized outcome for auditing.

Empty/repeat-only selections set durable `search_blocked` with reason
and make the next eligible direct research action R4. Python does not
automatically exhaust or answer the node; it applies the R4 scientific
decision as specified below.

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
extraction. Empty sources are also marked processed. R3 remains extractive; S3 integrates across knowledge units.

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
monotonic and independent of memory IDs. Records retain canonical spelling,
aliases, source-supported and model-generated definitions and qualifications,
supporting passages, source IDs, immutable retrieval references, node context
and typed links to other terms. Status distinguishes `candidate`, `provisional`,
`source_defined` and `multiple_definitions`; provisional availability must not
be confused with independently sourced evidence. Definitions with different
scope or provenance remain separate. Glossary entries are terminology records,
not new scientific knowledge units.

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

Applicable definition precedence is: authoritative terminology description,
source-extracted definition, then provisional LLM-generated definition. An
authoritative match without an applicable descriptive definition does not count
as a completed definition. All definitions and qualifications remain preserved
when a preferred definition changes. Provisional definitions record the actual
model identity, scope, ambiguity, generating interaction/event, template and
request provenance, and `verification=provisional`; they are terminology guidance,
not independent scientific evidence. Their presence does not suppress later
MeSH enrichment. Previously accepted applicable provisional definitions are
reused without routine same-scope regeneration. Contextual applicability uses
conservative lexical signals and is not infallible scientific disambiguation.

`glossary.sqlite3` is a disposable exact-name/alias, FTS5 and relationship directory.
Normal retrieval and deduplication use indexed bounded lookup and deserialize only
selected or touched records. An absent, stale or corrupt directory is rebuilt or
incrementally caught up from committed journal hashes and canonical records.
Rebuilds and explicit full integrity audits may scan all terms; ordinary R1 does
not. The index is refreshed lazily after commitment, so a cache failure cannot
partially publish terminology. `glossary-rebuild --experiment NAME` explicitly
rebuilds it. `glossary-export --experiment NAME` atomically regenerates the derived,
case-insensitive alphabetical `research/glossary.md` and searchable
`research/glossary.html`, including definitions, provenance, evidence and links.
R3 and R1 do not rewrite these whole exports; explicit regeneration produces
consistent derived views. Model-defined entries are visually marked provisional.

### R4: assess research progress

R4 makes a **scientific assessment**, not a search-planning or scheduling
decision. It runs after a complete provider round (no pending R3 evidence
or deferred provider searches) **or** after R1 has durably recorded
`search_blocked=true`. It makes one LLM call and returns exactly
`{"decision":"unresolved","reason":"Brief evidence-based explanation."}`.

#### Inputs and how to use them

Python supplies exactly these three R4 prompt inputs:

| Input | Contents | How R4 uses it |
| --- | --- | --- |
| `question` | The selected research question. | Decide whether **this question**, not a related one, has been answered. |
| `question_scope` | Immediate parent question (if any), root question, `is_root` and relevant research objectives. | Judge relevance to **both** parent and root; objectives set scope, not scientific evidence. |
| `scientific_evidence` | Relevant direct and synthesis memories, anchored findings, supporting sources/relationships, qualifications, unresolved questions and coverage details. | Assess completeness, citation support, contradictions and limitations; check synthesized claims against source findings. |

R4 receives **no** provider configuration, search concepts, query histories
or search scheduling state. Python retains these separately.

The evidence projection deterministically includes eligible direct
research, applicable synthesis findings
(including relevant descendant/related lineage), exact supporting
finding anchors, source citations, relevant questions, equations,
qualifications and relationships. Killed-branch evidence is excluded.
Present each scientific unit once; do not replace full scientific
support with an unsupported summary or add model-generated interpretation
when constructing the projection. Preserve attribution and uncertainties.

Check whether findings support conclusions for the populations,
comparators, measurements, timescales and limitations actually supplied.
A synthesis is **not independent scientific evidence**; valid anchors
prove traceability, not scientific correctness. One sufficiently
conclusive reliable direct source may answer a question without requiring
a synthesis, while numerous syntheses may remain inadequate.

The evidence projection explicitly identifies its coverage and missing
support. If necessary scientific context would exceed the model budget,
fail with the existing explicit context-budget error **before dispatch**,
rather than silently truncating evidence and claiming completeness.
Unsuccessful searches do not establish a scientific proposition's truth
or falsity.

#### Decisions and deterministic effects

| R4 decision | Scientific meaning | Python transition |
| --- | --- | --- |
| `answered` | Available evidence adequately addresses all material aspects of the selected question with justified, appropriately qualified conclusions. | Set `status=answered`. |
| `kill` | The selected question is irrelevant to **both** its immediate parent and the root research objectives. **Invalid for root nodes.** | Set `status=killed`; retain records and killed-branch synthesis restrictions. |
| `unresolved` | The question remains relevant but is not adequately answered by the supplied evidence. | If unblocked, remain `living`, preserve history and reset `keywords`/`next_database_index` for another R1 round. If `search_blocked=true`, set `status=exhausted` and `exhaustion_reason=search_blocked`. |

The validator accepts exactly `answered|kill|unresolved` and a nonempty
`reason`. The root cannot return `kill`; R4 never generates search terms,
child questions or research plans. Python decides whether searches remain,
rather than asking R4 to judge provider availability.

Every R4 assessment is durably recorded in `last_r4_assessment` with
the decision, interaction ID, committed event reference and prior
`search_blocked` status. Search-blocked exhaustion additionally persists
`exhaustion_assessment`, linking that validated `unresolved` decision
to the `exhausted` state. These updates, the event and state transition
commit atomically and survive restart and journal repair.

For an unresolved search-blocked node, R5 may run **below** the normal
research-capacity threshold, but only after validating this exact
R4 exhaustion receipt. Capacity-based exhaustion remains independent.
Neither search exhaustion nor lack of evidence is proof that the question
has been answered.

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
It estimates the full request plus reserve. Direct research remains included regardless of subsequent synthesis participation.
Descendant research and every synthesis memory are excluded. Synthesis
participation metadata does not change research capacity. No direct research is truncated or replaced
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

Only nodes with `status=exhausted` enter `ripeness_order`. Two
exhaustion causes are:

1. **`research_capacity_reached`:** a living node crosses the
   deterministic R5 context-capacity threshold with direct research,
   after its pending retrieval/extraction obligations are resolved.
2. **`search_blocked`:** R1 has no distinct worthwhile search and
   a committed R4 assessment returned `unresolved`. Python stores
   and validates the exact R4 event/receipt; R5 accepts this cause
   even when the capacity threshold has **not** been reached.

The causes remain distinct. Failed/deferred searches alone prove
neither scientific exhaustion nor an answer. A future
research-stagnation guard, if approved, would require its **own**
exhaustion cause and reviewed transition policy. The score starts as:

`ripeness = F + 2*H + 2*Q - D`

F counts distinct structured `Kind: finding` propositions; H counts distinct
hypothesis propositions; Q counts distinct open/partially answered question units;
D is root-relative depth (root zero). Counts use direct research units produced by
R3, not Markdown text-pattern guesses or syntheses.
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

Each cycle performs exactly one controller action and at most one LLM call.
S1 is deterministic and uses zero model calls. S2 and S3 each use at most one
model call in separate cycles. Research, synthesis and branching actions may
interleave; pending synthesis state survives intervening actions and restarts.

After each successful direct research action, active research priority falls
by one to a minimum of zero and other living nodes gain one to a maximum of
`priority_max` (10). The active node retains its turn until priority zero
or ineligibility; then the highest-priority living node is chosen, breaking
ties by creation order. R5 and synthesis do not age or reset research nodes.

Controller ordering is:

1. Reassess direct research, node-splitting eligibility, provider cooldowns,
   pending model submissions, outstanding synthesis objectives and candidate
   eligibility. An uncertain submitted LLM call requires recovery assessment;
   it must not be silently repeated.
2. Process eligible pending S3 objectives and pending S2 evaluations according
   to the synthesis cadence and fair scheduling policy. The same unchanged
   objective and evidence set is not submitted repeatedly.
3. When synthesis is due and no earlier synthesis stage is pending, S1
   deterministically selects one unevaluated eligible knowledge-unit group
   and persists its selection for S2.
4. When branching is due, run R5 on the highest-ripeness exhausted node.
5. Otherwise, run the next eligible R1–R4 research action. Nodes awaiting
   provider cooldown do not prevent other ready nodes from progressing.
6. When direct research and R5 work are absent, continue eligible S1–S3
   work, then finish only when no pending recoveries or eligible actions remain.
   Living nodes waiting for a future provider retry remain unfinished.

When all otherwise eligible work is waiting only on provider retry times,
return `waiting_for_provider` with the earliest retry time, without consuming
research-cycle counters.

`branching_interval` defaults to five direct research actions between R5
attempts while living nodes exist. An R5 action resets its branching cadence.
When only exhausted nodes remain, R5 need not await nonexistent research work.
The synthesis cadence defaults to five research/branching actions; an R5 action
counts as a work slot. Synthesis does not starve research or R5.

At most three synthesis actions form a consecutive burst while direct research
or R5 work is ready. Pending objectives remain durable when the controller
yields. Ordinary discovery follows the configured research/branching cadence;
when no other work is ready, eligible synthesis can proceed immediately.

A completed S2 `no_candidate` or S3 `no_synthesis` is a valid scientific
outcome and must not trigger a loop on the same unchanged evidence.
A changed knowledge-unit version, new relevant evidence or explicitly
authorized reevaluation can reopen an opportunity. The controller records a
terminal event only when direct research, splitting, pending/uncertain
synthesis work and eligible candidate groups have all been resolved.

## Synthesis actions: S1, S2 and S3

Mira maintains a research question tree for investigations and a cross-branch
knowledge-unit network for scientific synthesis. Candidate discovery is global
across eligible scientific units, not confined to a selected research node.
The same unit may support several scientifically distinct synthesis objectives.
The word **ripeness** refers only to R5 node splitting.

### Scientific units and source independence

Research memories retain stable source identities and individually addressed
units such as `r1#f1`, `r1#q1` and `r1#e1`. A paper may contain several
different findings and may also contain repetitive statements: neither shared
paper origin nor high semantic similarity proves equivalence or non-equivalence.
R3 seeks distinct, nonredundant extractive units while preserving scientifically
meaningful distinctions. The synthesis system preserves original source
propositions, their qualifications, unit types and their evidence status.

Separate source records are not necessarily independent empirical studies.
Reviews and republished analyses may share underlying primary evidence.
Synthesis findings are derived knowledge, not independent empirical sources;
their lineage must remain traceable to original sources.

### S1: Deterministic candidate discovery

S1 is a Python operation with **zero LLM calls**. It identifies bounded,
overlapping groups of scientifically related knowledge units, retrieving
the relevant parent memories for provenance and context. Groups can cross
research branches and include existing synthesis findings when their complete
source ancestry is available and acyclic. Open questions and hypotheses
may guide opportunity discovery but do not independently establish evidence.

S1 combines:

- Lexical and terminology similarity.
- Semantic embedding similarity using an actual scientific-text embedding
  model, never a synthetic test hash represented as semantic evidence.
- Explicit knowledge-unit relationships and scientific metadata.
- Source identities, evidence qualifications, experimental conditions and
  scientific type.

Findings, equations and images form the primary evidence neighbourhood. Bounded
open-question projections from relevant parents guide planning without replacing
scientific premises or becoming independent empirical evidence.

Similarity is a discovery signal, not a scientific truth or duplication score.
Candidate discovery preserves relationships that are complementary or
methodologically important even when they are not nearest neighbours.

Unit embeddings are keyed by representation, model identity and scientific
content version and stored in rebuildable caches. Retrieval uses bounded
neighbour structures and may update incrementally. A full quadratic
similarity matrix is not required as durable production state. Unavailable
semantic services are reported as degraded operation rather than silently
substituted. Candidate ranking and tie-breaking are deterministic.

The semantic backend uses the existing embedding configuration:
`--embedding-url` and `--model-identity`, or `MIRA_EMBEDDING_URL` and
`MIRA_EMBEDDING_MODEL_IDENTITY`. The identity includes the model artifact identity.
`synthesis.sqlite3` is a disposable, safely confined embedding cache; its key
includes representation, model identity and scientific-content version. Exact
neighbour scans retain bounded per-unit heaps rather than a pair matrix. Full
neighbourhoods and bounded related pairs provide overlapping group opportunities,
including smaller groups that fit when a larger neighbourhood cannot.

A candidate contains the versioned selected unit IDs, parent memory and
source identities, scientific content and qualifications, similarity and
relationship evidence, candidate-duplicate annotations, rationale, priority,
and estimated downstream input cost. Groups generally contain units from
approximately three to five parent memories when coherent; useful smaller
groups are valid. Context capacity and scientific coherence take precedence
over an arbitrary group size.

S1 distinguishes exact duplicates, possible semantic duplicates,
informational redundancy, complementary findings, apparent contradictions
and potential corroboration. Equivalence considers numerical values, units,
negation, comparators, timeframes, populations, methods, endpoints and
source dependence. An embedding threshold alone cannot establish it.
Uncertain equivalence is recorded for review, without deleting,
collapsing or automatically excluding scientific evidence.

S1 selects a group not already *evaluated* in the same unchanged unit-version
form. A completed S2 evaluation suppresses replay of that exact unordered
set, but does not blanket-exclude overlapping, expanded or changed-version
groups. Candidate discovery without evaluation does not mark a set completed.

### S2: Synthesis opportunity planning

S2 uses one LLM call to examine the selected group and identify **specific
analytical objectives**, not to publish a conclusion. It may propose several
distinct synthesis opportunities or return `no_candidate`.

Each proposal includes:

- An explicit synthesis objective and exact selected unit IDs.
- The scientific relationship motivating the integration.
- The new understanding or hypothesis that might result.
- Evidence adequacy, source dependence, methodological or population
  differences, quantitative assumptions and scientific limitations.
- An explanation of why the proposed work is more than paraphrasing
  existing knowledge or restating an evidence gap.

S2 considers complementary observations, corroboration, contradictions,
methodological comparisons, mechanisms and potential quantitative
deductions. It does not infer a scientific relationship from shared
terminology alone. A meaningful synthesis need not directly answer the
original root question. Python independently validates every reference,
response field and eligible objective against the selected input, then
durably records accepted objectives for S3.

The JSON contract is `disposition=ideas|no_candidate`, `ideas` and `reason`.
There are at most three proposals; each contains `category`, `objective`,
`unit_ids`, `potential_new_understanding`, `limitations` and `novelty`.
Invalid proposals are rejected individually. A response with no valid proposed
objective is a validation failure, distinct from a valid `no_candidate`.

One completed evaluation covers all objectives proposed from its selected
set. The same unchanged set is not repeatedly sent to S2 merely to seek
different wording. New evidence or an explicitly authorised reconsideration
may reopen it.

### S3: Evidence-grounded synthesis execution

S3 uses one LLM call for one accepted S2 objective. It attempts a substantive,
new integration of the supplied scientific units and their evidence. A valid
result is either `synthesis` with one or more defensible new knowledge units,
or `no_synthesis` with a reason why no useful synthesis is supported.
Insufficient evidence does not oblige Mira to create a memory.

Scientific reasoning distinguishes original observations and claims,
derived conclusions, uncertainties and hypotheses. It considers populations,
endpoints, timeframes, statistical and measurement units, quantitative
relationships, contradictory evidence, source independence and limitations.
A synthesis must not invent empirical measurements, citations, mechanisms
or unsupported causal claims. Hypotheses remain identified as hypotheses.
The same underlying primary study is not double-counted as independent
corroboration.

A synthesis ordinarily integrates substantive knowledge from at least two
distinct parent memories. Multiple units from one source may be important
supporting context but do not alone establish cross-memory synthesis.
All accepted findings identify their **actual contributing unit IDs**, not
every S1/S2 candidate. Each finding contains a proposition, explanation,
qualification, evidence status and traceable provenance.

Python validates output structure, exact references, supported unit types,
lineage, journal transitions and mechanically checkable constraints.
Structural validation is not scientific proof; the LLM's scientific
reasoning remains inspectable and unverified unless separately corroborated.
Partial syntheses may be accepted when only some proposed relationships
justify defensible findings.

S3 returns `disposition=no_synthesis` with `reason`, or `disposition=synthesis`
with `title`, `summary` and one to four findings. Each substantive finding
integrates at least two distinct input memories and records proposition,
explanation, qualification, `epistemic_type=inference|hypothesis`, exact
`source_findings`, attributed verbatim `evidence_checks`, declared
`quantitative_checks`, novelty rationale and comparisons with supplied existing
knowledge. Python checks literal quotation attribution and declared arithmetic
(sum, difference, ratio, product and numerical inequalities). These checks
do not establish compatible populations, causal validity, completeness of
calculations or the truth of quoted premises. Such limitations remain explicit.

### Novelty and scientific equivalence

Before publication, candidate synthesis propositions are checked against
relevant existing knowledge and prior syntheses. Exact repeated qualified
conclusions are not republished. Potential semantic repetition is reviewed
using scientific meaning, conditions, evidence and provenance rather than a
cosine cutoff alone. A new independently sourced observation may add
corroboration without providing a new synthesis conclusion.

Meaningful synthesis includes defensible new inference, integration,
explanation, reconciliation, methodological insight or evidence-grounded
hypothesis. Merely concatenating or paraphrasing source findings is not
synthesis. Uncertain equivalence cannot silently suppress scientifically
distinct conclusions.

### Knowledge-unit participation and lineage

Synthesis participation is **unit-level**, not whole-memory consumption.
Original research memories and their knowledge units remain available
after contributing to a synthesis; a unit may support several distinct
objectives. Selection by S1 or S2 does not itself constitute participation.
Only S3's accepted output establishes contributing source-unit relationships.

Each new synthesis finding has exact `SYNTHESIZES` edges to its contributing
knowledge units, with parent/source lineage retained in compact synthesis
metadata. Derived synthesis memories do not count as independent empirical
sources. Transitive ancestry must be acyclic; repeated use of one primary
source through multiple synthesis paths is not independent support.

Historical memory-level `synthesized_by` metadata remains readable for
compatibility, but it is not a consumption/exclusion mechanism for
knowledge-unit-based synthesis.

### Synthesis-attempt register

A durable register distinguishes discovered, selected, submitted,
uncertain, evaluated, rejected, failed and completed work. The identity
of a candidate group is a fingerprint of the sorted pair set
`(knowledge-unit ID, scientific-content version)`, independent of order.
Objectives have stable identities associated with their exact evidence
and a normalized scientific objective.

Records retain selected units and parents, provenance, S1 priority and
reason, S2 interactions and proposals, S3 objectives and results,
actual contributing units, scientific rejections and output memory IDs.
Completion of S2 suppresses repeat evaluation of that unchanged unit set;
completion of an S3 objective suppresses repeat execution of that unchanged
objective with unchanged evidence. Overlap, changed versions or additional
evidence can justify distinct attempts.

Submission uncertainty is distinct from `no_candidate` or
`no_synthesis`. Unknown LLM outcomes require explicit recovery handling;
model calls must not be silently replayed. Evaluated or rejected attempts
are durably committed, and successful synthesis publication, provenance,
attempt outcome and state changes are atomic.

## Synthesis integration and completion

Knowledge-unit synthesis does not replace contributing memories in a
consumptive frontier. A node's `synthesis_complete` indication reflects
the absence of eligible pending and unevaluated synthesis opportunities
relevant to its research subtree, not the exhaustion of its memories.
Cross-branch opportunities remain eligible independently of one node's
state. Answered or split parents may remain incomplete while descendants
are active. Exhausted nodes retain their separate R5 opportunity.

The controller terminates only when no living research, eligible R5 work,
pending S2/S3 objectives, uncertain submissions or unevaluated synthesis
opportunities remain. An unchanged corpus with no eligible opportunities
must not produce repeated S1/S2 calls; new scientific evidence or revised
unit versions may reopen discovery.

## Tree health and inspection

`research-state` exposes status totals (living, exhausted awaiting R5, answered,
killed, split), maximum depth, distributions by depth, active node, research and
R5 queues, priorities/progress, synthesis candidate priorities, pending S2/S3
objectives, versioned attempt accounting, R5-only ripeness counts/scores/weights,
capacity snapshots and configuration. It includes
branching/research/synthesis cycle totals, cadence counters and the last 20
successful actions with node IDs and timestamps. These provide evidence for later
policy tuning without an elaborate balancing mechanism now.

The read-only local viewer continues showing canonical state and the exact saved
request, prompt source/hash/bindings, raw model response, validation, outcome,
retrieved evidence, generated Markdown and historical tree changes. R5 is an
independent recorded action. Exports work without a running model or SQLite.

Research executions additionally export existing interaction phases and action
events incrementally to one append-only JSONL file under the project-level
`log/` folder (`/home/eric/Dev/Mira/log/` on the development machine),
**outside** the canonical `memory/` corpus. Each CLI initialization/run/demo and each
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

### Single active memory corpus and separate experiment logs

The **target** default storage root is the project's **one active
`memory/` corpus**, not `memory/research/<experiment-name>/` directories.
Canonical current files remain immediately under that root using the
existing paths: `memories/r*.md`, `memories/s*.md`,
`equations/*.json`, `identity.json`, `research/state.json`,
`research/results/*.json`, `events/*.json`, `glossary/g*.json`,
necessary `interactions/` and recovery journals. Rebuildable indexes and
temporary retrieval payloads remain separate from scientific memories.
Private user-authored question inputs, such as `memory/questions/*.md`,
are **not generated experiment memories** and must be preserved unless
the user explicitly identifies them for deletion.

Do **not** create a new memory child directory for each experiment.
Starting a **new** experiment resets/replaces the **previous generated
active corpus** at `memory/`, including its old research and synthesis
memories, state and temporary retrievals; no accumulating per-experiment
memory archives, renamed memory folders or retained old experiments.
A normal `research-run` or recovery/continuation **never** resets the
corpus. Initialization must have an explicit, distinguishable
new-experiment/reset operation, check active writer/runner locks and
uncertain submissions, and safely limit deletion to verified generated
paths (no symlink traversal or indiscriminate `memory/` deletion).
Existing `memory/research/<experiment>/` corpora are to be **removed in
the separately authorized storage-cleanup implementation**, not
silently copied into nested new directories. New experiments restart
their own allocators and scientific state; run history remains in logs.

The independent project-level `log/` folder contains run-specific
append-only execution logs, with unique run/session identifiers and
timestamps. Initialization, continuation and failure logs belong there,
not under `memory/run-logs/`. Logs are diagnostics, not additional
scientific memory copies or a competing recovery store; redact secrets
and preserve enough request/response/validation/decision trace for
inspection. Historical generated experiments are removed rather than
preserved as canonical memory snapshots inside `log/`. Keep log files
separate from current scientific memory and clearly label old runs.
Human-readable per-memory or per-question browsing should not require
navigating logs, journals or old experiment directories.

The single-active-corpus layout and project-level `log/` execution directory
are the default. New research does not create `memory/research/<name>/`
subfolders. Legacy corpora are readable through explicit compatibility
paths. Idle legacy experiment directories may be cleaned up only through
the separately authorized verified cleanup operation.

Every multi-file operation uses the existing small journal: validated changed-file
after-images are fsynced, a prepared manifest is published before canonical edits,
individual atomic replacements are fsynced, and a committed marker appears only
after complete validation. R5 commits its receipt, child IDs, allocator and event
through this same protocol. A crash cannot silently grant a second committed split.
Glossary edits use the same journal operation as their generating R1 or R3
research action, state and event. Only affected records are staged/replaced. State stores the term
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
Durable S1 selection, pending S2 evaluations, pending S3 objectives and exact
unit-version attempt states use the same recovery and journal rules. A successful
synthesis memory, its unit-level lineage, completed attempt and updated scheduler
state are committed atomically, preventing duplicate publication on restart.

`research/state.json` holds a versioned `unit_synthesis` register: selected and
evaluated groups, independently tracked S3 objectives, context requirements,
semantic capability, completed-corpus fingerprints and fair-scheduling counters.
Immutable interaction request/response/outcome receipts bind dispatch and
submission uncertainty to group/objective IDs. Read-only inspection exposes
uncommitted submissions separately from scientific rejection. Validation,
transport and context failures remain durable, are not automatically retried,
and cannot be reported as scientific exhaustion or successful synthesis.
With only such work remaining the controller reports `blocked_synthesis`.
Historical pending two-stage execution is preserved and reports
`blocked_legacy_synthesis` for operator review rather than being reinterpreted
or silently replayed. Historical committed events and memory bytes remain intact.

Version-1 state remains readable and validated by a retained compatibility module.
On the next successful controller action, an upgrade is journaled with that action.
Legacy `complete` is treated as old synthesis bookkeeping, **never** proof of an
answered question: without children it becomes exhausted; previously branched
non-killed nodes become split with a legacy receipt. Original statuses are retained
as `legacy_status`. Pending evidence on a formerly living, previously branched
node is retained as `legacy_pending_results` and in its immutable evidence file,
rather than discarded or directly rescheduled on a split node. Existing memory bytes, stable IDs, events, equation assets and historical
prompts remain interpretable by the compatibility parser while a legacy
corpus is selected. **Explicit new-experiment reset intentionally discards the
previous generated scientific corpus**, as separately authorized; this is
not an in-place scientific migration. Historical R3 responses without
glossary fields remain valid; the glossary initializes lazily when needed.

The historical Phase 1 snapshot store remains supported for compatible reads.
Autonomous research uses live persistence in the single active corpus;
no implicit import or accumulating per-experiment snapshot is introduced.
Historical synthesis memories and memory-level consumption metadata remain
parseable but do not make knowledge units unavailable for new synthesis. Journal scans and full-tree refresh favor inspectability over extreme
scale. Backups, server management and automated research-quality evaluation remain
outside this controller.
