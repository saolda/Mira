# Future work

This file tracks planned or pending changes. It is not an implemented specification.
The authoritative behavioural specification is `architecture.md`; the actual
LLM instructions are the versioned files in `prompt_templates/`.
Changes to either require user review and approval before being committed.
Codex implements approved specifications and reports proposed amendments
instead of editing `architecture.md` or independently rewriting LLM prompts.

Updated: 2026-10-30.

## Next implementation: provider retrieval and query profiles

### 1. Correct scientific-text sanitisation first (approved to implement)

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

### 2. Implement existing approved query-profile architecture (next)

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
