# Future work

This file tracks **open work**, not implementation instructions. The
authoritative behaviour is documented in `architecture.md` and the
exact LLM prompts in `prompt_templates/`. Changes to either require
explicit user review and approval. Codex must not independently rewrite
these protected files.

Updated: 2026-10-31.

## Implemented baseline (reference only)

- **R1:** One discovery/selection LLM call per provider round; 0–6
  genuinely new concepts; up to the active strategy's maximum
  `max_terms` selected concepts; unused-candidate persistence and
  effective-query duplicate prevention. Commits `4c18972`, `89cc7e9`.
- **R2/R3:** One logical provider search per R2 action, the same R1 plan
  across providers, and one source extraction per R3 action. This
  granularity is **settled**; batch-all-providers R2 is no longer planned.
- **R4:** `answered|kill|unresolved` scientific assessment using
  direct and synthesis evidence and supporting lineage. No root `kill`.
  `unresolved + search_blocked` deterministically exhausts the node
  for R5, even below capacity. Commit `fe684fd`.
- **Memory/logs:** One active `memory/` corpus, explicit safe reset
  for a new experiment, compact new synthesis Markdown, project
  `log/`, and legacy format/corpus readers are implemented. The
  code supports legacy cleanup; the actual state of historical local
  directories has not been independently verified.
- Provider profiles, deterministic compilation, retries/pacing,
  deduplication, previous R4 context-overflow correction and scientific
  HTML parsing improvements are implemented. Predefined strategies
  currently omit OpenAlex; explicit selection remains possible.

The latest test report records **381 passing tests** but no live
scientific-quality validation of the new R1/R4 behaviour. Historical
implementation plans, old R1/R4 schemas, and completed task instructions
are intentionally omitted; consult Git history and `test-results/`.

## 1. Validate the integrated R1–R5 pipeline

The revised R4 architecture was documented in `1b7a7fc`; it now
describes the implemented decisions, input evidence, blocked transition
and two distinct R5 exhaustion causes.

Run a fresh controlled end-to-end experiment on the combined R1/R4
implementation. Verify the shared R1 search plan across providers,
one-provider R2 and one-source R3 actions, duplicate suppression,
synthesis support provenance, justified R4 scientific decisions,
`search_blocked -> unresolved -> exhausted -> R5`, journal recovery
and accurate source/result accounting. Record calls, tokens, time and
failure modes. Fixture-passing JSON and valid citation anchors do
**not** establish the scientific correctness of conclusions.

Check the active `memory/` and `log/` layout, and inventory any
legacy experiment directories still present. Use the supported
lock-/recovery-checked cleanup route rather than assuming old experiments
have all been removed.

## 2. Research-stagnation rule (PROPOSED, NOT IMPLEMENTED)

### Problem and distinction from ordinary search exhaustion

A node can keep running if R1 repeatedly produces *different*
effective provider queries, each round completes and R4 correctly
returns `unresolved`, but the searches discover little or no useful
new science. With few R3 research memories, the capacity threshold
may never be reached. The existing `search_blocked` flag means **R1
cannot select a viable distinct query**; it does **not** mean that
many distinct searches have failed to advance the investigation.
A stalled node could therefore consume arbitrarily many rounds.

### Observation-only instrumentation first

Track per node, for each **completed** research round, without new
model calls:

- Actual submitted effective provider queries; their `ok`, `empty`,
  failed, unavailable and deferred outcomes; distinct returned
  source identifiers and actual duplicate-skip references.
- Accepted R3 source-derived memories and anchored knowledge units,
  provenance and qualifications, separately from raw source counts.
- Known unresolved evidence gaps and whether new supplied research
  explicitly addresses one, where this is supported by existing
  structured records rather than guessed from lexical overlap.
- A reproducible `consecutive_unproductive_rounds` counter,
  a `stagnation_warning` indicator, round/event identifiers and
  cumulative time, LLM calls and tokens.

**Scientific progress is not synonymous with activity.** A new URL,
query formulation, glossary term, source record or paraphrased
proposition is not by itself evidence of increased scientific
understanding. But the opposite shortcut is also unsafe: Python
cannot reliably determine scientific novelty or quality merely
from the number of R3 findings. Keep raw counts and any
scientific-value classification distinguishable and auditable.

Count only completed rounds eligible for assessment. An interrupted
call, outstanding R3 source, deferred provider retry, rate limit
or unknown/failed submission is **not** a completed, scientifically
unproductive round. Do not interpret temporary provider
unavailability as stagnation.

### Proposed stopping policy, subject to data and approval

Initially **observe and report** stagnation only; do not stop, block,
exhaust or generate substitute search concepts. Define and test the
counter's increment/reset semantics, including what constitutes
verified *useful* new evidence, before setting a threshold.

As a **hypothetical** starting point, review whether **three
consecutive eligible rounds** lacking any additional relevant,
source-grounded finding predicts genuinely unproductive research.
**Three is not an approved threshold.** Compare longer windows
and false-positive cases: useful research can yield several empty
rounds before discovering a rare or decisive source. Evaluate
changes in evidence gaps, not just added memory count.

If a termination rule is later approved, it must use a separate,
auditable cause such as `research_stagnant`, **not**
`search_blocked`. R4 still assesses scientific
`answered|kill|unresolved`. Only a valid `unresolved` assessment
plus the deterministic, approved stagnation predicate could
transition `status=exhausted` for R5, with persisted threshold,
round measurements, cause and R4 event receipt. Do not declare
a question answered or irrelevant because little evidence was
found; do not add LLM calls simply to measure stagnation.

Review how stagnation-based exhaustion interacts with R5's
below-capacity guard and monotone node statuses. Reopening a
formerly exhausted node after new sources or a better strategy
would require a **separate approved transition policy**, not
an undocumented state reset.

## 3. Research breadth and provider-profile tuning

- Test whether R1 searches distinct **scientific evidence gaps**
  rather than cycling near-synonyms. Relevant medical benchmark
  gaps include tumour/infection growth distributions, CT
  measurement reliability and direct comparative evidence.
- A multi-query evidence-gap research plan remains **unapproved**.
  Maintain one R1 selection per round and one provider per R2
  action while investigating benefits and state/cost implications.
- Compare alternative `max_terms` and provider query profiles
  under equal-work conditions, including Europe PMC exact-phrase
  restrictions. Measure **relevant evidence**, not hit counts.
  OpenAlex rate limiting is an availability issue, not proof that
  the search formulation is wrong.
- Evaluate abstract versus full-text coverage, quantitative
  extraction, source quality and provenance, particularly
  when metadata-only results cannot support an answer.

## 4. Scientific fidelity of extraction and synthesis

- R3/S1/S2 should accurately preserve each study's population,
  exposure/comparator, outcomes, timescales, units, uncertainty
  and limitations. Keep source observations, inferred claims,
  hypotheses and cross-source synthesis scientifically distinct.
- Earlier medical failures included grouped lobulation and
  spiculation being misattributed, `<=400 days` misinterpreted,
  noncomparative known-cancer findings promoted to
  infection-versus-cancer odds, and unsupported etiologic
  preferences or treatment conclusions. Use adversarial
  evidence-grounded fixtures and fresh controlled experiments.
- Investigate invalid/truncated S1 selections and repeated
  attempts against an unchanged catalogue that delay pending
  R3 work. Preserve the existing multi-input synthesis rules.
- Evaluate whether R4 reliably spots unsupported syntheses.
  Citation anchors and complete provenance are necessary,
  but do not ensure that a conclusion follows scientifically.

## 5. Scheduling, availability and resource limits

- Review very long provider cooldown/deferred requests that
  hold a research round open; preserve exact query identity,
  honest statuses, rate limits and crash-safe retries.
- Monitor R4/R5 evidence-context growth. Never silently remove
  scientifically required material to fit a prompt; retain
  explicit budget failures and inspectability.
- Measure LLM calls, tokens, elapsed time, new scientific
  evidence, repeated searches and research-node completion
  paths after the integrated live validation.

Keep detailed benchmarks and test logs in `test-results/` and
project `log/`, not duplicated in this roadmap.
