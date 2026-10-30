# Scientific-text preservation and query-profile validation

Recorded: 30 October 2026, Australia/Hobart. **Implemented both approved stages.** All 339 final tests passed. In the bounded live run PubMed returned two useful growth-related abstracts where the previous R1 benchmark returned none, but Europe PMC returned no records and the infection-versus-malignancy question remained unanswered. The run stopped normally on a long OpenAlex cooldown, preserving its original query.

## Commits and approved scope

- Stage 1 — scientific-text extraction: `87ed8ae99747ab896ba5db64ac5477273ab6d9b5`.
- Stage 2 — profiles, scheduling and recovery: `df75a8792e59ed68e8b74cea3e74bb610761d0d0`.
- Planning base: `86227cb`; a clean `main` safely fast-forwarded from `f8c3952` after `git fetch origin main`. The incoming commit only added `futureWork.md`.
- `architecture.md`, `futureWork.md` and every `prompt_templates/*` file remained byte-identical to GitHub’s approved versions. R1 still returns 2–6 ordered concepts. No proposed 0–6 novelty design or scientific prompt-policy change was implemented.
- Stage 1 and Stage 2 implementation/test-summary commits were made separately. This follow-up report records their exact SHAs and the completed live validation, avoiding a self-referential commit SHA inside its own report. All completed commits are pushed together after validation.

## Stage 1: scientific text

`providers.plain()` now uses the standard-library `HTMLParser` with entity conversion. It recognizes genuine tags before entity decoding, handles nested tags/attributes and malformed fragments, preserves Unicode and numerical punctuation, and inserts useful spacing at tag boundaries without inserting a space before a following comma. Identifiers, URLs, authors, dates and metadata meaning are unchanged. Length limits and `truncated` still refer to cleaned text before the existing character cap.

An isolated regression reproduces the old defect and verifies the correction:

| Input | Previous regex output | New output |
| --- | --- | --- |
| `P < 0.05 and tumour volume > 10 cm³` | `P 10 cm³` | `P < 0.05 and tumour volume > 10 cm³` |
| `P &lt; 0.05 and confidence interval &gt; 1.0` | Entity-dependent behavior | `P < 0.05 and confidence interval > 1.0` |
| `<p>Volume doubling time was <b>43 days</b>, P &lt; 0.001.</p>` | Markup stripped | `Volume doubling time was 43 days, P < 0.001.` |

Tests also cover nested JATS/HTML, attributes containing `>`, adjacent blocks, unclosed tags, unchanged ordinary abstract prose, unspaced numeric comparisons, `1.2e−3`, Greek characters, encoded literal markup and exact source metadata/length bounds. This establishes the regex failure mechanism for literal comparisons; it does not claim that every number omitted in a previous provider response had that cause.

**Stage 1 complete suite: 315 tests, 0 failures/errors/skips, 54.682 seconds.** The correction was committed before profile work began.

## Stage 2: configuration and deterministic compilers

Profiles are centrally configured in `src/mira/query_profiles.json`, included in package data and selected by explicit mappings in every predefined strategy. Strategy names, descriptions and provider order are unchanged. An alternative registry can be supplied with `research-init --query-profiles PATH` or `MIRA_QUERY_PROFILES`.

| Profile | Version | Providers | max_terms | Minimum seconds | Query behavior |
| --- | ---: | --- | ---: | ---: | --- |
| default | 1 | wikipedia, arxiv, pubmed, crossref, europe_pmc, eric, openalex | 6 | 0 | Original basic space joining; original word-wise arXiv field query |
| pubmed_balanced | 1 | pubmed | 3 | 0.35 | Unquoted concept groups joined with AND; preserves automatic term mapping |
| europe_pmc_balanced | 1 | europe_pmc | 3 | 1 | Escaped exact phrases joined with AND |
| openalex_broad | 1 | openalex | 3 | 1 | Plain supported search text |
| crossref_bibliographic | 1 | crossref | 4 | 1 | Plain text through query.bibliographic |
| wikipedia_general | 1 | wikipedia | 3 | 1 | Plain search text through gsrsearch |
| arxiv_subject | 1 | arxiv | 3 | 3 | Escaped concept phrases in explicit all: fields, joined with AND |
| eric_education | 1 | eric | 4 | 1 | Escaped concept phrases joined with AND |

All initial profiles use **60 seconds initial exponential backoff**, **3,600 seconds fallback cap** and **three submission attempts per provider-query**. These and the term limits are configurable experimental starting values, not established optima. Profile validation checks unique IDs, positive integer versions, compatible providers, compiler/rule combinations, term/attempt bounds, finite timing values and mandatory provider mappings. Compatible profiles can be shared across providers, and different profiles can target the same provider.

The default profile adds no provider-specific interval of its own; centrally configured **host floors** remain effective: arXiv 3 seconds, PubMed 0.35 seconds, and the other public hosts 1 second. The effective interval is the larger of the profile interval and host floor. Both profiles and host configuration are frozen with the experiment. No adapter contains an independent request-spacing constant or keyword compiler. Standalone adapter calls use the same central configuration; controller calls use durable experiment pacing.

Provider syntax was checked against primary documentation: [PubMed automatic term mapping and Boolean search](https://pubmed.ncbi.nlm.nih.gov/help/), [Crossref bibliographic query parameters](https://github.com/Crossref/rest-api-doc), [arXiv field/query grammar](https://info.arxiv.org/help/api/user-manual.html), [Europe PMC REST documentation](https://dev.europepmc.org/RestfulWebService), [OpenAlex search](https://help.openalex.org/api/searching/), [ERIC API examples](https://eric.ed.gov/pdf/Using_ERIC_API_for_Research_Topics.pdf) and [MediaWiki search](https://www.mediawiki.org/wiki/API%3ASearch). PubMed terms are deliberately not automatically quoted; Crossref receives no invented Boolean syntax.

### Immutable snapshots and legacy compatibility

New experiments store each provider’s profile ID, version, complete compiler/rule/timing configuration and shared-host intervals inside their immutable selected-strategy snapshot. R0 still selects a predefined strategy once. Explicit provider lists use `default`, including existing custom-adapter IDs. R5 descendants share the same experiment-wide snapshot. Editing the registry later does not alter an existing experiment.

Previously initialized experiments without profile metadata retain **all** original concepts and their exact legacy query construction, including old arXiv word-wise `all:` searches and the explicit paper-ID path. They receive a separately persisted, immutable legacy pacing/retry policy on their next action, without rewriting their strategy or earlier evidence. A partially visited legacy round retains its cursor through an explicit completed-prefix register; no failed/empty result is invented for a historical visit whose outcome is not in that register. New legacy-mode outcomes keep null profile IDs while recording their effective policy and legacy query semantics.

### Pruning, evidence and request logging

R2 retains a **prefix of concepts**, never a prefix of words. Original, retained and discarded lists, provider, profile ID/version/configuration, exact compiled query, planned query parameter and actual credential-free HTTP parameters are saved in events, immutable retrieval evidence and execution logs. PubMed’s initial ESearch and required EFetch are logged as two protocol requests within one logical query submission. Source identifiers, returned/unique counts, duplicates, pending-R3 dispositions and subsequent extraction dispositions remain inspectable. Only actually submitted query text updates glossary usage. R2 makes no model call.

All supported adapters pass the compiled query unchanged. The old `ArxivSearch.query()` API delegates to the central legacy compiler; it is not a competing compilation implementation.

## Deterministic comparison: max_terms 2, 3 and 4

This compile-only fixture was evaluated **before** the live run; it was not supplied to the model as a preferred answer. Ordered concepts: `volume doubling time`, `spiculated nodule`, `lung neoplasms`, `pulmonary infection`, `interval growth`. The profile was cloned in memory with each term limit; committed initial defaults were not tuned.

| Profile | Limit | Exact query |
| --- | ---: | --- |
| pubmed_balanced | 2 | `(volume doubling time) AND (spiculated nodule)` |
| pubmed_balanced | 3 | `(volume doubling time) AND (spiculated nodule) AND (lung neoplasms)` |
| pubmed_balanced | 4 | `(volume doubling time) AND (spiculated nodule) AND (lung neoplasms) AND (pulmonary infection)` |
| europe_pmc_balanced | 2 | `"volume doubling time" AND "spiculated nodule"` |
| europe_pmc_balanced | 3 | `"volume doubling time" AND "spiculated nodule" AND "lung neoplasms"` |
| europe_pmc_balanced | 4 | `"volume doubling time" AND "spiculated nodule" AND "lung neoplasms" AND "pulmonary infection"` |
| openalex_broad | 2 | `volume doubling time spiculated nodule` |
| openalex_broad | 3 | `volume doubling time spiculated nodule lung neoplasms` |
| openalex_broad | 4 | `volume doubling time spiculated nodule lung neoplasms pulmonary infection` |
| crossref_bibliographic | 2 | `volume doubling time spiculated nodule` |
| crossref_bibliographic | 3 | `volume doubling time spiculated nodule lung neoplasms` |
| crossref_bibliographic | 4 | `volume doubling time spiculated nodule lung neoplasms pulmonary infection` |
| wikipedia_general | 2 | `volume doubling time spiculated nodule` |
| wikipedia_general | 3 | `volume doubling time spiculated nodule lung neoplasms` |
| wikipedia_general | 4 | `volume doubling time spiculated nodule lung neoplasms pulmonary infection` |
| arxiv_subject | 2 | `all:"volume doubling time" AND all:"spiculated nodule"` |
| arxiv_subject | 3 | `all:"volume doubling time" AND all:"spiculated nodule" AND all:"lung neoplasms"` |
| arxiv_subject | 4 | `all:"volume doubling time" AND all:"spiculated nodule" AND all:"lung neoplasms" AND all:"pulmonary infection"` |
| eric_education | 2 | `"volume doubling time" AND "spiculated nodule"` |
| eric_education | 3 | `"volume doubling time" AND "spiculated nodule" AND "lung neoplasms"` |
| eric_education | 4 | `"volume doubling time" AND "spiculated nodule" AND "lung neoplasms" AND "pulmonary infection"` |

All 21 compiled variants preserve concept order and boundaries. PubMed keeps automatic term mapping available; phrase compilers escape literal backslashes/quotes; plain-text compilers do not invent provider operators. The full retained/discarded/configuration snapshots are in the local `query-profile-compiled-comparison.json`. This is a syntactic comparison, not an empirical retrieval comparison of all three limits.

## Provider progression, availability and recovery

- The next database index denotes the next unvisited provider. Each initial visit advances it exactly once, including deferred or rate-limited visits. A deferred retry uses its original provider index, concepts, compiled query and profile snapshot and never increments that index again.
- Pending R3 sources take precedence over the node’s next provider or deferred retry. R4 requires the initial pass complete, no pending source and no deferred query. R4 retry resets concepts, the cursor and per-round bookkeeping before another R1.
- Provider availability and consecutive rate-limit failures are shared across nodes; host request times also pace protocol follow-ups. A cooldown check neither submits nor increments an attempt. Actual successful/empty outcomes reset consecutive rate-limit failures.
- Numeric or timezone-aware HTTP-date Retry-After establishes an earliest retry and is never shortened by the local fallback cap. Invalid/missing values use configured exponential backoff. Exhausted submission attempts become `unavailable`, never `empty`.
- Ready providers/nodes and due synthesis/branching may proceed while another provider waits. If only provider availability blocks progress, the controller returns `waiting_for_provider` and the earliest timestamp without a model call, canonical publication, research-cycle increment or busy-loop.
- Before HTTP I/O, fsynced `retrieval_calls/<id>/intent.json` and per-request receipts establish what might have been submitted. The outcome, queue, cursor and pacing state commit through the existing canonical journal. An uncommitted submission receipt blocks restart with `uncertain_provider_submission`; inspect it before explicitly using `--acknowledge-interrupted-searches`. Known journal after-images can be repaired without a second HTTP submission. A failed request-receipt write blocks dispatch rather than masquerading as a retrieval outcome.
- Credentials are added only to wire requests. Recorded parameter dictionaries omit API keys; configured secret redaction also covers error/log data. Tests inspect both canonical records and execution logs for credential leakage.

The independent submission receipts are additional recovery diagnostics; canonical memories, evidence, state and the existing journal remain in their established locations. No automatic retry of an uncertain in-flight request was added.

## Automated validation

**Final Stage 2 complete suite: 339 tests, 0 failures, 0 errors, 0 skipped; 57.152 seconds.** Command: `PYTHONPATH=src python3 scripts/run_tests.py --validation-summary ...`. The 24 focused profile/round tests include all named compilers, reusable/shared profiles, mandatory mappings, invalid configurations, pruning, snapshots, legacy partial rounds, all outcomes, R3/R4 ordering, server Retry-After, fallback backoff, host pacing, multiple nodes, waiting, explicit uncertain-call acknowledgement, request-receipt failure, journal repair without resubmission and secret-free actual parameter logging. Existing deduplication, extraction, prompts, restart and integrity suites also passed.

Existing non-failing SQLite resource warnings remain. Test fixtures that manually begin a new round now clear its terminal-outcome register together with the cursor. Tests expecting the superseded skip-429-and-call-R4 behavior were updated to require deferred waiting. Scientific prompt sources and R1 validation were unchanged.

## Bounded live medical validation

Experiment: `query-profile-medical-20261030`, under the committed Stage 2 implementation. Same immutable `memory/questions/lung-growth.md`, model Qwen3.6-35B-A3B Q4_K_M, 16,384-token native context, 4,096 output limit/reserve, temperature 0, thinking disabled, explicit medical strategy and two records per provider as the previous benchmark. The existing local server was reused and left running.

Question: Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

Execution ran **16:13:21–16:14:35 AEDT**, 30 October 2026, for **74.342 seconds**. Limits were 40 direct actions and five minutes; it stopped earlier with **`waiting_for_provider`** after **10 direct actions**, **12 committed controller actions** and **7 model calls**. Action counts: R1×1, R2×5, R3×4, S1×1, S2×1. The final waiting check was a return value, not a thirteenth published action.

### R1 and submitted queries

One actual rendered R1 request produced these concepts in original priority order:

1. `spiculated pulmonary nodule`
2. `volume doubling time`
3. `lung malignancy`
4. `pulmonary infection`
5. `lesion growth rate`

Raw and accepted lists were identical. No glossary, prior terms or search outcomes existed at that first decision. There was no second R1 solely because OpenAlex was cooling down. All seven saved model request bodies and prompt snapshots were verified against the actual sent messages.

| Provider / profile | Exact submitted query | Retained / discarded | Returned | Unique | Duplicates | Status |
| --- | --- | --- | ---: | ---: | ---: | --- |
| pubmed / pubmed_balanced v1 | `(spiculated pulmonary nodule) AND (volume doubling time) AND (lung malignancy)` | 3 / 2 | 2 | 2 | 0 | ok |
| europe_pmc / europe_pmc_balanced v1 | `"spiculated pulmonary nodule" AND "volume doubling time" AND "lung malignancy"` | 3 / 2 | 0 | 0 | 0 | empty |
| openalex / openalex_broad v1 | `spiculated pulmonary nodule volume doubling time lung malignancy` | 3 / 2 | 0 | 0 | 0 | rate_limited |
| crossref / crossref_bibliographic v1 | `spiculated pulmonary nodule volume doubling time lung malignancy pulmonary infection` | 4 / 1 | 2 | 2 | 0 | ok |
| wikipedia / wikipedia_general v1 | `spiculated pulmonary nodule volume doubling time lung malignancy` | 3 / 2 | 0 | 0 | 0 | empty |

Every provider had one actual query submission. PubMed required two HTTP protocol calls; each other provider required one, giving six actual HTTP requests. There were no cooldown resubmissions, hidden fallback queries, discarded-concept submissions or duplicate sources.

Actual endpoint/parameter logs were checked against each compiled query, including PubMed’s returned-ID EFetch. The following is a complete credential-free request audit (timestamps remain in local receipts):

**pubmed**

```json
[
  {
    "endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    "logical_submission": false,
    "parameters": {
      "db": "pubmed",
      "retmax": 2,
      "retmode": "json",
      "sort": "relevance",
      "term": "(spiculated pulmonary nodule) AND (volume doubling time) AND (lung malignancy)",
      "tool": "Mira"
    },
    "started_at": 1793337203.1830328
  },
  {
    "endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
    "logical_submission": false,
    "parameters": {
      "db": "pubmed",
      "id": "37936095,39807982",
      "retmode": "xml",
      "tool": "Mira"
    },
    "started_at": 1793337204.2982237
  }
]
```

**europe_pmc**

```json
[
  {
    "endpoint": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
    "logical_submission": false,
    "parameters": {
      "format": "json",
      "pageSize": 2,
      "query": "\"spiculated pulmonary nodule\" AND \"volume doubling time\" AND \"lung malignancy\"",
      "resultType": "core"
    },
    "started_at": 1793337257.0279667
  }
]
```

**openalex**

```json
[
  {
    "endpoint": "https://api.openalex.org/works",
    "logical_submission": false,
    "parameters": {
      "per_page": 2,
      "search": "spiculated pulmonary nodule volume doubling time lung malignancy"
    },
    "started_at": 1793337270.180103
  }
]
```

**crossref**

```json
[
  {
    "endpoint": "https://api.crossref.org/works",
    "logical_submission": false,
    "parameters": {
      "query.bibliographic": "spiculated pulmonary nodule volume doubling time lung malignancy pulmonary infection",
      "rows": 2,
      "select": "DOI,title,abstract,author,published,URL,type"
    },
    "started_at": 1793337270.4354558
  }
]
```

**wikipedia**

```json
[
  {
    "endpoint": "https://en.wikipedia.org/w/api.php",
    "logical_submission": false,
    "parameters": {
      "action": "query",
      "exintro": 1,
      "explaintext": 1,
      "format": "json",
      "formatversion": 2,
      "generator": "search",
      "gsrlimit": 2,
      "gsrsearch": "spiculated pulmonary nodule volume doubling time lung malignancy",
      "inprop": "url",
      "maxlag": 5,
      "prop": "extracts|info"
    },
    "started_at": 1793337273.8184893
  }
]
```

### Deferred search and restart check

OpenAlex returned HTTP **429** with **`Retry-After: 67530`**. Its exact three-concept query remains queued at provider index **2**, attempt **1 of 3**, with profile `openalex_broad` version 1. The global provider availability, node queue, profile snapshot and original query agree. The node’s next database index is **5**: the initial five-provider pass advanced once per visit, and the deferred retry will not advance it again.

Earliest retry: **2026-10-31T11:00:00.348989+11:00** (31 October, approximately 11:00 AEDT), far beyond the five-minute validation budget. Other providers and pending source extraction completed before stopping. R4 was not called, the root remains living, and its five R1 concepts are intact.

After the run, a fresh `Research` instance returned the same waiting state. All experiment file hashes, research-cycle counts and the seven interaction records remained unchanged, and no unresolved submission or incomplete journal was present. Long cooldown completion and final attempt exhaustion were tested with injected clocks, not waited out live.

### Retained evidence and scientific assessment

Four unique records were retained and R3-processed:

| Source | Provider / supplied content | Extraction |
| --- | --- | --- |
| Ma et al., *Prediction of subsolid pulmonary nodule growth rate using radiomics* — PMID **37936095**, PMCID **PMC10629176**, DOI [10.1186/s12880-023-01143-x](https://doi.org/10.1186/s12880-023-01143-x) | PubMed abstract | `r1`: three findings and a derived open question |
| Sun et al., *CT Predictors of Angiolymphatic Invasion in Non-Small Cell Lung Cancer 30 mm or Smaller* — PMID **39807982**, DOI [10.1148/radiol.240599](https://pubs.rsna.org/doi/10.1148/radiol.240599) | PubMed abstract | `r2`: four findings and a derived open question |
| Chandler et al., *Spiculated lung nodule: an unusual presentation of chronic pulmonary aspergillosis* — DOI [10.1016/j.chest.2022.08.414](https://doi.org/10.1016/j.chest.2022.08.414) | Crossref title/authors/date only | Empty extraction; no growth measurements supplied |
| *Biochemical measure of the volume doubling time of human pulmonary neoplasms* — DOI [10.1016/S0169-5002(85)80158-6](https://doi.org/10.1016/S0169-5002(85)80158-6) | Crossref title/date only | Empty extraction; no scientific results supplied |

The [Ma abstract](https://pubmed.ncbi.nlm.nih.gov/37936095/) reports 273 growing subsolid nodules and 857 CT scans, with growth classes **VDT ≤400** versus **>400 days**, selected imaging features including spiculation, and model AUCs **0.928/0.905**. Mira retained those distinctions and qualified them as growth-rate prediction, not etiologic diagnosis. These thresholds are not a measured VDT distribution for all malignant nodules and do not estimate a four-week infection probability.

The [Sun abstract](https://pubmed.ncbi.nlm.nih.gov/39807982/) concerns resected, already diagnosed NSCLC. Mira extracted an ALI association for spiculation, **OR 2.05 (95% CI 1.42–2.97; P < .001)**, a VDT association **OR 0.96**, and model AUC improvement **0.77→0.82**. These are useful quantitative cancer-aggressiveness findings, **not** odds ratios for malignancy versus infection. The abstract does not specify the VDT scaling underlying OR 0.96, so it cannot support a per-day clinical interpretation.

Both memories preserve the author/source identities, the correct study populations, numeric values and uncertainty qualifications. No infection growth-rate distribution, CT repeatability limits, fast malignant subtype-specific VDT distribution or direct infection-versus-cancer likelihood comparison was extracted. Neither Crossref title was promoted into an unsupported clinical finding.

**Unsupported model reasoning remains:** `r2`’s summary says rapid growth and spiculation “suggest malignancy,” which goes beyond a study restricted to known cancers; its own later qualification correctly acknowledges that limit. S1 additionally invokes infection being rapid and spiculation being less common in simple infection, without support from the supplied memories. S2 then refused synthesis appropriately, but incorrectly described `r1` as focusing only on >400-day nodules, ignoring its ≤400-day fast-growth group. No prompt or scientific-policy change was made to address these observations.

S1 selected `r1+r2` with score **16/25** (R4/C4/X2/N3/E3). S2 returned **`no_synthesis`**, stating that neither memory provides infection growth data or the direct four-week diagnostic comparison. No synthesis memory or final answered state was created. The justified limited answer remains: **the supplied evidence cannot establish whether infection is favored or quantify its strength**. S2’s explanation about only >400-day nodules should not be adopted.

### Scientific-text fidelity

The exact source payload text matched every R3 request. The first abstract retained **≤400** and **>400** with their intervening wording; the second retained repeated **P < .001** clauses, odds ratios, confidence intervals and later AUC results. Both abstracts were below the existing character cap and marked `truncated=false`. Canonical Markdown escapes angle brackets where necessary, while the parsed scientific text retains their meaning.

The two live abstracts do not contain a literal `<...>` comparison pair of the same form that triggered the old destructive regex; their intact inequalities are a useful fidelity check, but the controlled Stage 1 regressions provide the direct before/after proof of that defect. No unavailable numbers were reconstructed or invented.

Four glossary candidates were admitted: Subsolid pulmonary nodules (SSNs), Volume doubling time (VDT), Radiomics and Angiolymphatic invasion (ALI). Only the VDT candidate was subsequently registered as used. That concept was already in the initial R1 list, so its use does not demonstrate glossary-driven diversification. No later R1 received these candidates because the round was still waiting.

### Comparison with the previous R1 benchmark

Baseline: [r1-medical-benchmark.md](r1-medical-benchmark.md), implementation `5aa31cb`. Different stopping behavior is material: the baseline skipped cooldown providers and reached 40 research actions; this run correctly retains the unresolved deferred query and stops after one pass. Totals are therefore descriptive, not equal-budget performance estimates.

| Metric | Previous R1 benchmark | Query-profile validation |
| --- | ---: | ---: |
| Elapsed seconds | 104.114 | 74.342 |
| Direct / committed controller actions | 40 / 47 | 10 / 12 |
| R1 / R2 / R3 / R4 | 5 / 24 / 7 / 4 | 1 / 5 / 4 / 0 |
| S1 / S2 model calls | 7 / 0 | 1 / 1 |
| All model calls | 23 | 7 |
| Returned / unique / duplicate records | 20 / 7 / 13 | 4 / 4 / 0 |
| PubMed submissions / returned records | 5 / 0 | 1 / 2 |
| Europe PMC submissions / returned records | 5 / 10 | 1 / 0 |
| Research memories / synthesis memories | 2 / 0 | 2 / 0 |
| Glossary candidates / distinct used | 3 / 1 | 4 / 1 |
| Prompt / completion / total tokens | 56,336 / 3,480 / 59,816 | 15,243 / 2,734 / 17,977 |
| Largest prompt / including reserve | 5,395 / 9,491 | 3,152 / 7,248 |
| Context-budget failures / rejected responses | 0 / 0 | 0 / 0 |
| Quantitative evidence extracted | General progression frequencies, no relevant diagnostic growth estimates | Growth classification thresholds and conditional ALI odds/AUCs; no infection comparison |
| Final clinical question resolved | No | No |

**Observed improvement:** PubMed now supplies relevant growth/morphology abstracts and both resulting memories, instead of five empty searches. **Observed weakness:** Europe PMC’s three exact phrases joined with AND yield an empty result where its old broad combined strings retrieved records. Exact phrase constraints or terminology such as lung malignancy may be too restrictive; this run did not isolate which term/rule caused that difference. The Crossref records are the same two title-only leads seen early in the previous benchmark.

Prefix pruning and explicit PubMed concept grouping are plausible explanations for its better yield, but are not separately randomized or ablated here. Provider ranking/index changes and live transport conditions remain uncontrolled. One short run does not establish general improvement, an optimal max_terms value, or a stronger scientific answer. The approved strict deferred-round policy also means a long provider cooldown can end a short validation before another research round; it must not be presented as absence of evidence.

## Integrity, preservation and local artifacts

All **7** responses passed structural validation. No context-budget or model transport failure occurred. Maximum prompt plus reserve was **7,248 / 16,384** tokens. Corpus validation passed (two research documents, no equations); all journals were committed and no uncertain submission remained. Both execution logs ended normally. All **5,714** pre-existing research files retained their hashes, as did the question, architecture, future-work file and prompts.

Local artifacts remain excluded from GitHub:

- Experiment, memories, full prompts/responses, source payloads and journal: `/home/eric/Dev/Mira/memory/research/query-profile-medical-20261030`.
- Initialization log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_051320_query-profile-medical-20261030_118cbe5737c3.jsonl`.
- Research log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_051321_query-profile-medical-20261030_99354632fb7e.jsonl`.
- Supervisor record: `/home/eric/Dev/Mira/memory/research/query-profile-medical-20261030/supervisor.jsonl`.
- Run integrity/preservation: `/home/eric/Dev/Mira/memory/research/query-profile-medical-20261030/validation.json`.
- Request, source and restart audit: `/home/eric/Dev/Mira/memory/research/query-profile-medical-20261030/validation-analysis.json`.
- Compiled 2/3/4 comparison: `/home/eric/Dev/Mira/memory/benchmarks/query-profile-compiled-comparison.json`.
- Live supervisor script: `/home/eric/Dev/Mira/memory/benchmarks/run-query-profile-medical-20261030.py`.
- Stage 1 test output: `/tmp/mira-stage1-tests.log` (also summarized in its commit).
- Final Stage 2 test output: `/tmp/mira-stage2-verified-tests.log` (339 tests; also copied under `memory/benchmarks/`).

Only intended implementation, configuration, tests, README guidance and test reports are committed. No old experiment was resumed or altered. No branch, reset, discarded work or force-push was used. Final local/remote main equality and the report commit SHA are checked after pushing and reported in the final chat.
