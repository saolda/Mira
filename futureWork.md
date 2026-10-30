# Future work

This file tracks planned or pending changes. It is not an implemented specification.
The authoritative behavioural specification is `architecture.md`; the actual
LLM instructions are the versioned files in `prompt_templates/`.
Changes to either require user review and approval before being committed.
Codex implements approved specifications and reports proposed amendments
instead of editing `architecture.md` or independently rewriting LLM prompts.

Updated: 2026-10-30.

## Roadmaps recovered from 29 October: Priority 1–3

These labels refer to previously proposed priorities, not three new approvals.
**Priority 1 was implemented; Priorities 2 and 3 remain substantive unfinished
scientific-research work.** Preserve these distinct goals when planning later tasks.

### Priority 1 — provider-specific query generation — IMPLEMENTED, tuning OPEN

- Named reusable query profiles, provider-aware deterministic compilation,
  configurable `max_terms`, strategy snapshots, provider/host pacing, deferred
  retries, crash recovery and provenance were implemented in
  `df75a8792e59ed68e8b74cea3e74bb610761d0d0`.
- Real benchmarks showed useful PubMed abstracts, but Europe PMC's exact-phrase
  profile is sometimes over-restrictive. Controlled probes found PubMed matches
  of 6/5/0 and Europe PMC 9/3/0 for 2/3/4 concepts in one fixed bundle.
  A plain-text Europe PMC profile retrieved an infectious-mimic abstract in a
  later alternative experiment. **Profile optimisation is NOT completed.**
- OpenAlex was temporarily removed from all *predefined* strategies in
  `1bfb62f2912dee591a7b8b1ecc13fb03f323a386`; explicit OpenAlex use,
  saved strategy snapshots, and pending searches remain supported.
- Distinguish one query profile **per provider per research round** (implemented)
  from a **multi-query research plan for multiple evidence gaps** (not yet
  designed or implemented).

### Priority 2 — broaden and diversify scientific research — PENDING DESIGN

- Choose *substantively distinct evidence objectives*, derived from the
  selected question, unresolved memory gaps and previous retrievals. Examples
  for the medical benchmark: malignant doubling-time distributions, rapid
  cancer subtypes, infectious/inflammatory growth rates, CT measurement
  reliability, spiculation risk, and direct comparative diagnostic evidence.
- Avoid treating lexical permutations and near-synonyms as distinct discoveries;
  permit useful terminology reuse without repeating unproductive provider queries.
- Investigate multi-query/gap-specific search planning: how many focused
  directions per round, how they interact with the per-node database cursor,
  how deduplication and completed/deferred work are tracked, and how to keep
  R2 deterministic without uncontrolled extra LLM calls.
- The proposed R1 **0–6 NEW-concepts** contract below is an important component,
  **not the whole Priority 2 design**. Novel terms alone do not guarantee
  coverage of distinct scientific questions. User and ChatGPT must approve
  exact `architecture.md` and R1 prompt revisions first.
- Evaluate progress by new scientific evidence and gap coverage, not query
  novelty or raw record counts alone.

### Priority 3 — evidence-grounded synthesis and source quality — PENDING DESIGN

- R3/S1/S2 must preserve the population, exposure, comparator, outcome,
  timescale, measurement units, uncertainties and limits actually reported
  by each cited study. Do not infer infection-vs-malignancy odds from findings
  restricted to patients with confirmed cancer.
- Explicitly distinguish (a) source-reported observations, (b) independently
  supported cross-source conclusions, (c) model-derived hypotheses and
  (d) unresolved or conflicting evidence. Validate attribution and cited
  memory anchors, not just output JSON structure.
- Evaluate incomplete, conflicting, metadata-only and low-quality evidence;
  avoid summary claims stronger than their supporting study populations.
- Benchmark failures to address: grouped lobulation+spiculation misreported
  as spiculation alone; `≤400 days` misread as slow-only; ALI odds in known
  NSCLC promoted to an infection-vs-cancer preference; unsupported S1/S2
  etiologic claims despite missing direct comparison.
- Strengthen source quality/retrieval depth: source-reported quantitative
  results, abstract versus full-text limits, provenance, and noninvented
  citations; preserve existing source deduplication.
- Scientific-text HTML sanitisation was **fixed** in
  `87ed8ae99747ab896ba5db64ac5477273ab6d9b5`, but that correct parser
  is only one completed subtask, **not completion of Priority 3**.

## Other previously stated operational priorities

A separate 29 October list identified: (1) prevent R4 context overflow;
(2) improve R1 research breadth; and (3) improve source-quality handling.
R1 breadth aligns with Priority 2 above; source quality belongs to Priority 3.

### R4 correction completed; scientific follow-up pending review

- **COMPLETED in `4cb524f` (tests `1545c85`, report `72a7f87`):** compact
  R4 history while preserving all scientific research and all 12 search
  outcomes. Same-state request + reserve fell from **17,006 to 8,834**
  tokens, within the 16,384 context. The full suite reports **350 passing**
  tests; the continuation experiment completed three R4 rounds. Longer future
  contexts may still need bounded-history design review.
- **INVESTIGATED; mitigation PENDING:** earlier S1 failed once by truncating
  at 4,096 tokens, then by selecting one memory despite the >=2 requirement.
  The new run did not reproduce S1 rejection, but did record an S2 rejection;
  scientific faithfulness and recoverable invalid-selection behaviour remain
  open for user-controlled design.
- **COMPLETED in the new report:** fresh continuation with temporary PubMed
  `max_terms=2` and Europe PMC plain-text `max_terms=3`, preserving defaults.
  Three rounds / 30 direct actions completed; no evidence-grounded answer to
  the medical comparison yet. Analyse source quality before changing defaults.
- **Status:** R4 implementation and tests committed and reported; user and
  ChatGPT have not yet reviewed the complete scientific validation. This
  planning update does not change any active experiment or prompt.

### Additional follow-up after that work

- Assess whether an unchanged memory catalogue warrants another S1
  `no_candidate` model call; distinguish this from rejected/invalid S1
  responses that currently can obstruct pending R3 extraction.
- Review whether provider retry queues should hold R4/research-round completion
  for many hours, or whether other research directions could proceed in
  parallel. Any change must preserve query identity, durable cursors, provider
  rate limits and honest accounting; this is an **unapproved architecture
  proposal**, not an implementation instruction.
- Benchmark alternative provider profiles with equal-work/equal-evidence
  comparisons. An observed result-count change is not proof of better science.


## Completed provider infrastructure: implementation history

The following work was completed on 30 October 2026 and is retained for
traceability. The medical benchmark and configuration tuning remain ongoing.

### 1. Scientific-text sanitisation — COMPLETE (`87ed8ae`)

- `src/mira/providers.py:plain()` uses `re.sub(r'<[^>]+>', ...)`. This may
  erase scientific comparison text between a literal `<` and a later `>`
  (e.g. `P < 0.05; group size > 10`).
- Replace with bounded HTML-aware text extraction that preserves literal
  comparisons, numeric inequalities, Unicode and encoded `&lt;`/`&gt;`,
  while correctly stripping genuine HTML tags and preserving useful spacing.
- Regression tests must check realistic medical abstracts, inequality signs,
  nested HTML, entities, bare comparison symbols, and unchanged result metadata.
- Preserve source text/provenance and existing source-deduplication semantics.
  Confirm cause with tests; benchmark observations alone do not prove this
  regex caused all omitted numbers.
- Run tests and commit this correction before starting query-profile work.

### 2. Query-profile architecture — COMPLETE (`df75a87`)

- Implement the named, reusable profiles, mandatory strategy-to-profile
  mappings, `default` compatibility, provider-specific query compilation,
  configurable `max_terms`, profile/host pacing, backoff, deferred searches,
  durable R2 provider-index progression and `waiting_for_provider` contracts
  already stated in `architecture.md`.
- Preserve existing R1 wording and 2–6-concept output contract during this
  implementation. Do not independently introduce the proposed 0–6 change.
- Test compiler syntax and provider compatibility; run deterministic scheduling,
  retry, recovery, deduplication and budget tests. Compare multiple configured
  term limits (e.g. 2, 3 and 4) without assuming that two is optimal.
- Re-run a bounded medical retrieval benchmark, recording actual submitted
  queries, retrieved *relevant* evidence, source fidelity, model calls, tokens,
  retries, and differences from the 2026-10-30 R1 benchmark.
- OpenAlex's observed 429 / ~19.8-hour Retry-After is an availability issue,
  not a negative search result: do not busy-wait during short benchmarks.

## Pending design review: R1 discovers AND selects concepts

**Not approved for implementation; requires a reviewed architecture amendment
and exact reviewed R1 prompt revision first.** R1's original 2–6 keywords
contract remains operative until then.

- **One R1 call with two scientific responsibilities:** (A) discover **0–6
  genuinely NEW** useful scientific concepts, possibly none; (B) select an
  ordered **usable, non-repeated search-concept list** for the question R1 was
  assigned, drawing on discovered and existing concepts. Do not manufacture
  low-quality novelty to fill the discovery list. Selection is an **LLM
  scientific judgement**, not a deterministic Python fallback/assembly task.
- **R5 alone develops child/subresearch questions.** R1 must not create,
  reformulate or select new subquestions. R4 assesses research-round progress.
  No new R1 subquestion/objective field has been approved.
- New concepts that R1 does not select must survive in a **durable per-node
  unused-candidate register**, separate from source-supported glossary facts.
  Annotate origin=R1, node/question, discovery round, priority, validation,
  selection/actual-query usage, and `unverified` scientific status. An
  LLM-suggested term is not independently sourced evidence. Make duplicate
  merging conservative and preserve history across restarts/journals.
- **Python curates bounded inputs**, not the scientific search choice. It
  might retrieve, for example, 10 relevant unused candidates from 100 saved
  unused concepts while independently summarising 30 previously used ones.
  Use deterministic relevance, usage/recency and fair exposure; flag omitted
  counts, avoid starvation, and preserve all records for later rounds. This
  general principle is recorded in `architecture.md` at commit `b2f85f7`.
  Do not silently truncate essential questions/objectives or source evidence.
- Validate actual provider-compiled query usefulness/novelty against
  previously **submitted** provider-query combinations, respecting per-profile
  `max_terms`, not just comparing the full R1 lists. Distinguish an
  unsubmitted deferred query, an empty successful query and a failed attempt.
  The exact duplicate-submission policy is still to be designed.
- If R1 identifies **no viable search**, it should explicitly decline rather
  than invent terms or repeat a known unproductive query. Route this event
  to R4 for assessment, with a reviewed transition that avoids endless
  R1→R4→R1 cycles. R5 may eventually receive an exhausted node, **but current
  architecture sends nodes to R5 only via capacity exhaustion**; do not
  silently alter that contract. Review status/schema/flow first.
- Define output schema, projection budgets, unused-candidate persistence,
  no-viable-search outcome, R4/R5 integration, exact LLM prompt wording and
  deterministic regression tests **with user and ChatGPT approval** before
  Codex implementation. Prompt wording is not delegated to Codex.
- Evaluate scientific value, diversity, query uniqueness, useful R3 evidence
  and model/token cost, not just newly coined vocabulary.

## Subsequent investigation

- R1 research-direction diversification: distinguish underlying evidence
  questions (malignant and infectious growth distributions, CT repeatability,
  morphological risk), not just synonym changes; preserve prompt ownership.
- S1 `no_candidate` scheduling: assess whether an unchanged eligible memory
  catalogue warrants repeated model calls while research is active.
- R3 evidence fidelity: preserve grouped-vs-individual feature attribution,
  measured numeric values and uncertainty; improve tests using source excerpts.
- Retrieval depth: metadata-only Crossref hits and abstracts often omit
  quantitative results; separately assess permissible full-text access and
  source-specific limits, without inventing unavailable evidence.

## Baseline

`test-results/r1-medical-benchmark.md` (2026-10-30, implementation
`5aa31cb`): 40 direct research actions, 23 LLM calls, seven unique retrieved
records, two research memories, zero syntheses, no PubMed results and no
quantitative infection-versus-malignancy comparison. Separate PubMed probes
showed 0 matches for five concepts and 6 for a two-concept prefix, without
establishing an optimal universal `max_terms`.
