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

### In progress with Codex now — do not duplicate or modify

- Compact **R4 search-history projection** without dropping any scientific
  research, source provenance or actual provider-query outcomes. The no-OpenAlex
  benchmark blocked at **17,006 tokens** against **16,384** available, even
  though the full R5 capacity estimate had not reached its threshold.
- Investigate **S1 invalid responses**: one truncated at the 4,096-token
  completion limit; the next selected only one memory despite the >=2
  requirement. Determine scheduling and recovery implications without
  unapproved changes to S1 semantics, prompt wording or selection rules.
- Validate research continuation using a temporary PubMed `max_terms=2`
  and Europe PMC plain-text `max_terms=3` profile configuration, keeping
  committed defaults unchanged; commit a separate validation report.
- **Status: IN PROGRESS.** Do not mark resolved until Codex's new commits,
  tests and actual report have been reviewed. This file update does not
  change any active experiment or Codex's working tree.

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

## Pending design review: R1 discovers only new concepts

**Not approved for implementation; requires a reviewed architecture amendment
and exact reviewed R1 prompt revision first.**

- Proposed R1 result: `{"keywords":[...]}` with **0–6 genuinely NEW**
  relevant scientific concepts, ordered by prospective value. Zero is valid;
  do not invent low-quality or pseudo-novel concepts merely to fill a quota.
- Interpret `new` relative to previously proposed/search-used concepts and
  relevant glossary aliases, not merely spelling differences. Synonyms may
  still have retrieval value, but lexical substitution is not automatically a
  new scientific direction. Specify how to distinguish these cases.
- Deterministic code should combine new concepts with useful established
  context/anchor concepts when needed for search precision; no extra LLM call.
  Select anchors and fallbacks using explicit, auditable rules. Avoid rebuilding
  the original five- or six-concept conjunctive query by indiscriminately
  appending old terms. Profile `max_terms` remains independently configurable.
- Design the zero-new-concept path, first-round empty response, no usable
  fallback, nonduplicate provider queries, and R4 eligibility so Mira cannot
  loop indefinitely on unchanged searches or claim nonexistent evidence.
- Update `architecture.md`, `prompt_templates/R1.txt`, output validation,
  persisted concept/provenance state, and tests **only after user review**.
  Prompt wording is not delegated to Codex.
- Compare semantic novelty, recall, retained concept utility, query uniqueness,
  relevant extracted evidence and total model/token cost in repeatable tests.

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
