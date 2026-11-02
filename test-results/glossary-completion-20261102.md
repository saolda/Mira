# Active glossary completion and owner-controlled prompt restriction

Recorded: 2026-11-02. Branch: `main`. Baseline: `c5f9ac37905fa2e25a25aca00c5aa05df64360bf`.

## Executive summary

The permitted glossary maintenance, persistence, CLI and viewer work is implemented and tested. The actual active `memory/` corpus was processed in full and its standard HTML and Markdown regenerated. **Definition coverage remains 6/32; this is not a completed-definition glossary.** All 26 missing terms are visible, individually marked `approval_required`. No term was removed or given an invented definition to improve coverage.

The owner superseded the original request with a restriction on architecture and production prompts. A new dedicated glossary-generation prompt is necessary to finish model-based completion. It has not been approved, so production model completion is disabled. Existing R1 was not repurposed: its approved responsibility remains search planning with optional definitions. There were **zero real model calls, zero model-generated definitions and zero generation tokens** during this active enrichment run. Fixture-based transport/recovery tests are not scientific generation experiments.

## Protected files and approval dependency

During initial development, this task changed `architecture.md` and introduced an executable glossary-generation prompt constant in the new Python module. These changes were neither committed nor pushed and the prompt was never sent to a model. On receipt of the owner's restriction, the architecture file was restored to its clean starting content and the new prompt removed from executable code. There were no pre-existing architecture modifications to preserve. `prompt_templates/*.txt` and all existing production prompts remained unchanged throughout.

The exact proposed prompt and architecture patch are retained separately in [glossary-completion-approval-proposals.md](glossary-completion-approval-proposals.md), clearly marked **not applied; owner approval required**. The proposal describes a dedicated bounded definition/abstention contract and independent maintenance/provenance documentation. The original `AGENTS.md` workflow instructions are preserved and the owner's five protection rules appended. No unapproved protected-file changes are included in the commits.

The command contains no production glossary-generation instruction text and the normal CLI supplies no prompt factory. Synthetic test messages exercise batching, provenance and recovery without enabling production generation. The configured Qwen service was discovered read-only, but not used for completion. Its reported model was `/home/eric/models/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-Q4_K_M.gguf`, with a 16,384-token active context. Completing the 26 outstanding model definitions depends on owner approval and subsequent explicit integration of the proposed prompt.

## Coverage before and after

| Metric | Before | After |
|---|---:|---:|
| Total terms | 32 | 32 |
| Terms with authoritative definitions | 6 | 6 |
| Terms with research-source definitions | 0 | 0 |
| Terms with provisional definitions only | 0 | 0 |
| Terms requiring scientific clarification | 0 | 0 |
| Terms without usable definitions | 26 | 26 |
| Terms awaiting prompt approval | 0 | 26 |

Authority and research-source categories can overlap; provisional-only is exclusive. Clarification is a subset of undefined terms. `approval_required` is an implementation dependency, not a claim that a term is scientifically ambiguous. No generated definitions were scientifically verified.

The six initial authoritative records were audited directly. The old scope heuristic recognized only four: it rejected relevant PET/CT and pulmonary-infarction descriptions because their descriptive vocabulary did not overlap the selected question. An exact expanded MeSH preferred name occurring in local evidence now establishes contextual identity without that incidental vocabulary requirement. Each term is evaluated in its own recorded node scope. The table counts the six definitions actually present before maintenance, rather than claiming two old definitions as new discoveries.

## Actual maintenance results

| Metric | Observed |
|---|---:|
| Terms processed | 32 |
| Authority lookups | 26 |
| Authority HTTP API calls | 30 |
| Exact matches with no descriptive definition | 2 |
| No exact authoritative match | 22 |
| Authority lookup validation failures | 2 |
| Newly admitted authoritative definitions | 0 |
| Newly extracted explicit source definitions | 0 |
| Model-generated definitions / model calls | 0 / 0 |
| Generation tokens | 0 |
| Active enrichment wall time | 71.204 seconds |
| Glossary revision before / after | 35 / 74 |

The matched but undefined concepts were `Relapse` (`M0018663`) and `Inflammatory pseudotumor` (`M0009614`); neither supplied a descriptive scope note through the existing exact-concept adapter. `Reverse halo sign` and `Reversed halo sign` failed with `ValidationError: invalid MeSH concept link`. These failures remain in the canonical terminology history with the existing service cooldown. The adapter was not bypassed and no failed lookup was converted into an authoritative definition. The source passages did not supply new explicit definition statements accepted by the conservative extractor.

Twenty-six model-setup dependency outcomes were logged, one per undefined term; these were not rejected LLM outputs. No generated definition was rejected for scientific quality because none was generated. In tests, malformed/circular definitions, invented citations, unsupported abbreviation expansions and an explicit volume/diameter-doubling conflation are rejected. Those deterministic checks do not prove general scientific correctness.

An immediate ordinary rerun processed **0** terms, made **0** authority requests and **0** model calls, and retained glossary revision 74. Completed unchanged work and approval-blocked entries are durable and idempotent. Explicit authority retries continue to respect canonical lookup deadlines and provider pacing.

## Scientific quality and representative records

All six retained descriptions remain verbatim attributable MeSH scope notes, with original concept IDs, URLs and retrieval timestamps. This is an attribution/context review, not independent verification of every medical assertion in MeSH. No clinical conclusion, malignancy likelihood or new research finding was generated.

- **g12 Radiomics** — retained source: [NLM MeSH M000763396](https://id.nlm.nih.gov/mesh/M000763396). Its description concerns algorithmic feature extraction from patient images. It is appropriate terminology context for the existing radiomics material, not independent evidence that a particular model is diagnostically useful.
- **g21 Positron Emission Tomography-Computed Tomography** — retained source: [NLM MeSH M000616299](https://id.nlm.nih.gov/mesh/M000616299). Definition excerpt: “An imaging technique that combines a POSITRON-EMISSION TOMOGRAPHY (PET) scanner and a CT X RAY scanner.” Its identity is supported by the expanded term in the research passage; this does not verify lesion aetiology.
- **g16 Pulmonary infarction** — retained source: [NLM MeSH M0018127](https://id.nlm.nih.gov/mesh/M0018127). The scope note describes lung-tissue necrosis associated with inadequate oxygen/blood supply. Its terminology meaning is relevant even though it does not repeat the research question's growth vocabulary.
- **g6 Organizing pneumonia**, **g13 Cryptogenic organizing pneumonia** and **g31 Pulmonary inflammatory pseudotumor** retain their distinct MeSH concepts (`M000751452`, `M0027812`, `M0025468`). Scope-note age/size descriptions are source wording, not universal diagnostic thresholds established by Mira. The terms were not merged merely because they share inflammatory context.

`Volume doubling time`, `Spiculation`, `Maximum Standardized Uptake Value`, the pulmonary-nodule categories, inflammatory pseudotumor and the mathematical/image-feature terms remain visibly undefined. The task did not supply general model knowledge as fabricated literature quotations. In particular, it did not equate volume-doubling time and diameter-doubling time or write an unapproved definition for either. The new validator's targeted conflation check is limited; mathematical relations in future generated definitions will still need independent review.

## Remaining terms and precise authority outcomes

Every row below also carries the canonical reason: **Owner-approved glossary-definition prompt required; provisional model generation is disabled.** None is silently hidden. “Not found” means no exact canonical-name match in the configured MeSH adapter, not absence of a legitimate scientific meaning or absence from all terminology authorities.

| ID | Term | Last authority status | Authority outcome |
|---|---|---|---|
| g19 | Delta radiomics | not_found | No exact MeSH canonical or entry-term match. |
| g32 | Gray-Level Co-occurrence Matrix | not_found | No exact MeSH canonical or entry-term match. |
| g9 | growth rate | not_found | No exact MeSH canonical or entry-term match. |
| g20 | Immunoglobulin G4 (IgG4)-related disease | not_found | No exact MeSH canonical or entry-term match. |
| g17 | Inflammatory pseudotumor | matched | Verified concept M0009614 has no descriptive definition. |
| g28 | Invasive adenocarcinoma | not_found | No exact MeSH canonical or entry-term match. |
| g4 | Lymphocytic interstitial pneumonia | not_found | No exact MeSH canonical or entry-term match. |
| g25 | Maximum Standardized Uptake Value | not_found | No exact MeSH canonical or entry-term match. |
| g27 | Minimally invasive adenocarcinoma | not_found | No exact MeSH canonical or entry-term match. |
| g30 | natural air bronchograms | not_found | No exact MeSH canonical or entry-term match. |
| g23 | Neutrophil-to-Lymphocyte Ratio | not_found | No exact MeSH canonical or entry-term match. |
| g26 | Nonsolid nodules | not_found | No exact MeSH canonical or entry-term match. |
| g24 | Platelet-to-Lymphocyte Ratio | not_found | No exact MeSH canonical or entry-term match. |
| g1 | Pulmonary nodules | not_found | No exact MeSH canonical or entry-term match. |
| g14 | Relapse | matched | Verified concept M0018663 has no descriptive definition. |
| g7 | Reverse halo sign | error | ValidationError: invalid MeSH concept link |
| g15 | Reversed halo sign | error | ValidationError: invalid MeSH concept link |
| g3 | Risk stratification | not_found | No exact MeSH canonical or entry-term match. |
| g18 | Small bubble signs | not_found | No exact MeSH canonical or entry-term match. |
| g5 | Spiculated pulmonary nodule | not_found | No exact MeSH canonical or entry-term match. |
| g2 | Spiculation | not_found | No exact MeSH canonical or entry-term match. |
| g10 | Subsolid pulmonary nodules | not_found | No exact MeSH canonical or entry-term match. |
| g22 | Systemic Immune-Inflammation Index | not_found | No exact MeSH canonical or entry-term match. |
| g29 | vacuole sign | not_found | No exact MeSH canonical or entry-term match. |
| g11 | Volume doubling time | not_found | No exact MeSH canonical or entry-term match. |
| g8 | volumetric assessment | not_found | No exact MeSH canonical or entry-term match. |

## Implemented behaviour

- `glossary-enrich` traverses all outstanding terms in deterministic index order; supports bounded term counts, progress/coverage inspection, retry reasons/cooldowns and authority supplementation. It does not depend on a further R1/R3 action. Local-model configuration is available but does not enable a new prompt while approval is pending.
- Canonical term records retain append-only completion history, input-context hashes, timestamps, failures and request identities. Existing journal commitments, hash validation, source evidence and allocator rules remain authoritative. No second glossary implementation, experiment archive or parallel canonical store was introduced.
- The model transport is covered using synthetic fixtures: bounded batches, native token checks, shrinking batches, separate term validation, actual model identity attribution, received-response replay, journal recovery and durable uncertain-submission blocking. No unknown call is acknowledged automatically. These capabilities remain inactive in the standard command until prompt approval/integration.
- Standard HTML/Markdown show prominent applicable definitions, attribution, alternatives, scope, evidence, available source titles/references, completion state and a consistent coverage summary. HTML retains offline name/alias search, keyboard navigation and injection-safe DOM construction. Stable snapshot timestamps and revision/commitment markers support reproducible regeneration.
- The browser decision viewer links to the same standard HTML export. It serves the existing file read-only and reports stale revisions rather than silently presenting them as current.

## Preservation and standard-view validation

The normal active corpus was selected through Mira's storage configuration: `/home/eric/Dev/Mira/memory`. No new experiment was initialized. The research corpus retains **16 memories and one equation**. Before/after file hashes show **no removed files or unexpected changes**. Research state is identical except for glossary revision/commitment. Existing scientific records, primary retrieval evidence, synthesis experiment artifacts, private inputs and existing logs were preserved.

All 32 glossary records changed only in `enrichment` and/or `terminology`; their identities, canonical terms, aliases, definitions, supporting evidence, relationships and node membership were preserved. The run added 39 glossary-only journal operations/events and no model interactions or research memories. The active canonical corpus revision changed from `6834896a6c16813d3118f1b439f17ec1b11688e2c506e70d77234c8128f13992` to `2e8ce5d205ef8cfc8467a214d7a0904216e5fd8fb659b02fd66c98809eb1a153` through normal journal publication.

Standard outputs:

- **HTML:** `/home/eric/Dev/Mira/memory/research/glossary.html`
- **Markdown:** `/home/eric/Dev/Mira/memory/research/glossary.md`
- Glossary revision: **74**.
- Commitment: `240ef626b094727bbb289b14fcbf045df5919f3fe7c27d9889fe5683674ff574`.

The actual local `file://` HTML was loaded in Chromium with an isolated temporary profile and network resolution disabled. Browser DOM inspection found all 32 anchored entries, the search input and the current commitment; a rendered screenshot was inspected. This is the enriched-maintenance state of the active glossary, not a disposable copy. Search behaviour, offline assets, relationship navigation, escaping and atomic export/rebuild behaviour are covered by the automated tests. Generated views, corpus data, execution logs and the browser profile are not committed.

## Validation and reproducibility

Full suite: `PYTHONPATH=src python3 -m unittest discover -s tests` — **543 passed, 0 failures, 0 errors, 0 skipped**, 132.441 seconds. This includes 26 new completion tests and the added standard-viewer route test, existing source-grounding/provisional-definition tests, research/synthesis regressions, reset/recovery tests, Unicode/injection tests and offline JavaScript search navigation. `git diff --check` passed. Existing SQLite resource warnings were logged; the suite completed successfully.

```bash
PYTHONPATH=src python3 -m mira glossary-enrich --status
PYTHONPATH=src python3 -m mira glossary-enrich
PYTHONPATH=src python3 -m mira glossary-view
xdg-open memory/research/glossary.html
```

Detailed local diagnostics remain under `log/glossary-completion-20261102/`: `before.json`, `initial-coverage.json`, `initial-coverage-current-rules.json`, `active-enrichment.json`, `idempotent-enrichment.json`, `preservation.json`, `export.json`, browser DOM/screenshot and full test output. Normal independent execution JSONL logs remain in project `log/`.

## Recommendations and unfinished dependency

Review the specific prompt and architecture proposals separately in ChatGPT. If the prompt contract is approved, integrate it explicitly, then complete the 26 remaining terms, independently review abbreviations and mathematical terminology, and regenerate the standard views. Do not interpret fixture coverage as evidence that Qwen produces scientifically correct definitions. Investigate the two MeSH identity-link validation failures and missing concept descriptions while preserving authority identity and cooldown safeguards. Complete definition coverage has **not** been achieved under the new approval restriction.

Implementation and tests are committed through `d1e7415dd836335c9c8e48cf9983e1866794394f`; the report commit changes documentation only.
