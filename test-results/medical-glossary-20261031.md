# Medical glossary experiment — stopped for low research yield

## Executive summary

**The experiment failed to answer the question or demonstrate useful glossary enrichment.** The user stopped it after **520.032 seconds (8 minutes 40 seconds)** of research, before the 2,400-second allowance. The final committed corpus contains **four research memories**, ten finding units and one derived question, from **149 controller actions**. The last progress snapshot showed two memories; two more were committed during the final child-node actions before shutdown. There are **no synthesis memories, no answered nodes and no quantified diagnostic conclusion**.

The low yield is observable, but it is not explained by lost writes: all four nonempty R3 extractions became durable memories. The principal bottlenecks were unproductive compound searches, predominantly metadata-only retrieval, inconsistent selection of adjacent evidence by R3, and repeated synthesis selection without new material. MeSH enrichment added aliases for one concept but **zero definitions or scope notes**. It consumed 31 terminology API calls and 109.414 seconds of lookup time.

The root eventually selected an entirely repeated search, received an appropriately conservative R4 assessment, exhausted through `search_blocked`, and split into three living children. That is exhaustion of the selected search plan, **not evidence that the scientific literature is exhausted**. The retained corpus and logs are intact and recovery checks pass. No implementation fixes or scientific-content repairs were applied.

Exact research question:

> Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

## Preparation, configuration and safe stop

`origin/main` was synchronized with `git pull --ff-only origin main`; the working tree was clean. The implementation tested was **`7441335c6795455b0e1cabe261de49d509281eaa`**, containing the R1 partial-validation and R3 MeSH-enrichment changes. There were no unexplained local modifications or other active research runners. The active corpus passed journal, canonical-record, glossary and external-submission verification before reset. The separate legacy `memory/research/dropout-sustained/` corpus has an unresolved historical model interaction and was left untouched.

The explicitly authorized `research-init --new-experiment --experiment medical-glossary-20261031 --strategy medical` reset replaced 459 verified generated files belonging to the previous active corpus. It did not create an experiment archive. Hash checks confirmed preservation of **596 pre-existing private-input, legacy-corpus and log artifacts**, including symlinks without traversing them.

The existing local server passed `/health`. `/v1/models` and `/props` identified **Qwen3.6-35B-A3B Q4_K_M**, with **16,384 tokens per request** and two slots. All **83 saved generation requests** used temperature 0, thinking disabled, JSON-object output and 4,096 maximum output tokens. Output reserve was 4,096; default research capacity was 12,288. No supplementary question context, objectives, terms or evidence were supplied.

The unchanged default medical strategy was PubMed → Europe PMC → Crossref → Wikipedia, with two results per provider. PubMed and Europe PMC retain three concepts and combine them with AND; Europe PMC quotes phrases. Crossref retains four concepts as plain text; Wikipedia retains three. R1 therefore received `term_limit=4`. Model timeout was 120 seconds and provider timeout 25 seconds. Terminology defaults were two terms, at most six requests, three seconds per request and eight seconds per R3 action. The production terminology cache was initially absent. MedGen was not enabled.

The supervisor used `Research.execution()` and sequential `Research.step()`, with a monotonic 2,400-second deadline and no cycle ceiling. It reserved 150 seconds before starting another action. Research began **10:17:44.461805 UTC / 21:17:44 AEDT** and stopped at **10:26:24.493866 UTC / 21:26:24 AEDT** on the user's instruction. Initialization, audit and export are outside that interval. This is an early-stopped experiment, not a completed 40-minute run.

The driver lacked a cooperative stop flag. Two attempts to attach a Python stop hook failed without changing the runner. Shutdown then acquired the exclusive corpus writer lock, allowing the current action to finish and preventing another action from dispatching, before interrupting the supervisor. No in-flight provider or model request was killed. The final canonical action was committed, but interruption during diagnostic serialization left **148 complete supervisor step rows for 149 canonical actions**. Counts below reconcile canonical events with all 83 completed interaction outcomes; no partial supervisor JSON line or uncertain submission remained. The execution log records the interruption.

## Action and resource statistics

Initialization is excluded. Every attempted scientific/controller action committed; there were no rejected LLM responses or corrective LLM retries.

| Action | Actions | Model calls | Prompt tokens | Completion tokens |
| --- | ---: | ---: | ---: | ---: |
| R1 | 19 | 19 | 38,639 | 4,476 |
| R2 | 66 | 0 | 0 | 0 |
| R3 | 30 | 30 | 60,007 | 4,590 |
| R4 | 16 | 16 | 26,599 | 1,927 |
| S1 | 17 | 17 | 31,968 | 2,213 |
| S2 | 0 | 0 | 0 | 0 |
| R5 | 1 | 1 | 1,806 | 248 |
| **Total** | **149** | **83** | **159,019** | **13,454** |

Total API-reported generation usage was **172,473 tokens**. Saved model request/response intervals sum to **288.224 seconds**. All 83 responses finished with `stop`; the largest prompt was 2,862 tokens, or 6,958 including reserve. Native template/tokenizer requests are not counted as generation calls. State records 131 research cycles, 17 synthesis cycles and one branching cycle. No model context limit was reached.

## Why so few memories were created

| Pipeline stage | Observed result | Implication |
| --- | --- | --- |
| Provider submission | 63 actual searches; 41 empty | Most searches supplied no source to extract. |
| Retrieval | 43 returned records; 12 duplicates; 31 unique | Retrieval volume substantially exceeded unique evidence. |
| Processed source quality | 19 metadata-only records, four encyclopedia excerpts, seven abstracts | Most R3 calls had no substantive paper text. One further metadata record remains pending. |
| R3 | Four nonempty extractions; 26 empty | Four of seven abstracts produced memories; all 19 metadata records and four encyclopedia excerpts produced none. |
| Persistence | Four nonempty extractions → four saved memories | No observed loss of accepted scientific output. |
| Synthesis | 17 `no_candidate` selections; zero S2 calls | Sixteen selections considered the same r1/r2 catalogue; the last also included r3. |

R1 often selected several alternative diagnoses as one shared concept list. For example, the second PubMed query was `(inflammatory pseudotumor) AND (organizing pneumonia) AND (necrotizing pneumonia)`. Requiring distinct alternatives together, and quoting long mixed-concept phrases in Europe PMC, plausibly reduced recall. This is an interpretation supported by the empty-result pattern, not a controlled comparison with different queries. No alternative queries were manually submitted.

Crossref returned material for every submission, but often only titles and identifiers. Records included directly promising titles about volume doubling time and pulmonary neoplasms, yet no abstract was supplied. R3 appropriately could not reconstruct study results from those titles. Two differently identified records had the same attribute-modeling title; identity deduplication alone does not establish scientific novelty.

R3's relevance threshold was inconsistent. It saved adjacent COP/BAC and inflammatory-marker findings, and later a LIP case report, while omitting another content-rich case report about pulmonary infarction with Aspergillus infection mimicking organizing pneumonia ([source](https://doi.org/10.12890/2024_004501), action 81). The omitted case does not answer the four-week likelihood question, but could support a similarly qualified differential-diagnosis memory. This is evidence of inconsistent retention of adjacent material, not proof of a missed quantitative answer.

Two other abstracts returned no findings: the [reversed-halo study](https://pubmed.ncbi.nlm.nih.gov/12704033/) concerns a different imaging sign, and the [nonresolving-consolidation abstract](https://europepmc.org/article/MED/33942755) supplies little relevant detail. Their omission is defensible. Five empty-result responses included explanatory summaries; existing normalization discarded those summaries for memory creation while preserving the proposed responses in interaction records. Python did not convert explanations of irrelevance into scientific findings.

The practical failure is therefore insufficient acquisition and consistent retention of **useful evidence**, not simply a missing memory allocator. Raising memory counts by saving unsupported statements or empty-source summaries would not resolve it.

## R1 plans, candidate reuse and duplicate handling

One R1 call supplied the shared list for each node/round. All 19 proposals passed component validation; **no independently invalid component occurred**, so this run confirms use of the new implementation but does not exercise its partial-rejection behavior.

The root completed 15 provider rounds; round 16 was blocked before provider dispatch. Its selections increasingly recycled extended versions of the same alternatives. The final root rounds illustrate the pattern:

| Root round / action | Selected concepts, in order | Result |
| --- | --- | --- |
| 1 / 1 | volume doubling time; spiculated pulmonary nodule; infectious vs malignant nodule; rapidly growing lung lesion | No research memory |
| 2 / 9 | inflammatory pseudotumor; organizing pneumonia; necrotizing pneumonia; pulmonary abscess | No research memory |
| 3 / 19 | fungal granuloma; pulmonary nodule growth rate; rapidly growing lung lesion; infectious vs malignant nodule | Reused two previously unused candidates; glossary candidates only |
| 6 / 46 | organizing pneumonia; cryptogenic organizing pneumonia; bronchioloalveolar carcinoma; mucinous adenocarcinoma | Created r1 and r2 |
| 10 / 85 | pulmonary infarction volume doubling; mucinous adenocarcinoma rapid growth; cryptogenic organizing pneumonia recurrence; necrotizing pneumonia mimicking malignancy | No new research memory |
| 15 / 126 | Same first three as round 10; pulmonary infarction mimicking malignancy fourth | Three provider queries skipped; changed Crossref query added no memory |
| 16 / 133 | Same complete selection as round 10 | All four effective queries already completed; `search_blocked` |

Some accepted items, such as `pulmonary infarction volume doubling`, still combine a disease and measurement rather than naming one established concept. Passing the five-word/syntax checks does not establish scientific terminology quality. Several reasons asserted growth characteristics not supported by saved findings; these remained unverified search hypotheses.

The candidate registers retain **50 per-node entries**: 35 root, six q2, five q3 and four q4. These are not 50 globally distinct scientific discoveries. Forty-three have actual submitted-query usage and seven remain unused. Root `pulmonary nodule growth rate` and `fungal granuloma` were discovered before their first selection and reused in round three, preserving provenance.

Unused entries are root `organizing pneumonia growth rate`; q2 `Minimally invasive adenocarcinoma`, `Organizing pneumonia`, `Corticosteroid responsive lung disease`; q3 `Inflammatory confounders`; q4 `Nocardiosis`, `Actinomycosis`. Some were selected fourth but had not reached a provider retaining four concepts when stopped. Unused does not imply lost.

## Actual searches and provider outcomes

| Provider | R2 actions | Submitted / HTTP requests | Empty / successful / repeat-skipped | Returned / unique / duplicates |
| --- | ---: | ---: | ---: | ---: |
| PubMed | 18 | 17 / 19 | 15 / 2 / 1 | 3 / 3 / 0 |
| Europe PMC | 17 | 16 / 16 | 14 / 2 / 1 | 4 / 4 / 0 |
| Crossref | 16 | 16 / 16 | 0 / 16 / 0 | 32 / 20 / 12 |
| Wikipedia | 15 | 14 / 14 | 12 / 2 / 1 | 4 / 4 / 0 |
| **Total** | **66** | **63 / 65** | **41 / 22 / 3** | **43 / 31 / 12** |

All **63 submitted provider/query pairs were distinct**. R1 detected seven repeated effective queries: three allowed a partially new round whose repeated R2 searches were skipped, and four blocked the final root selection entirely. No completed duplicate query was resubmitted. Twelve duplicate source records were excluded from extraction. Every R2 action handled one provider search or its deterministic skip; every R3 action handled one source. There were no provider rate-limit, cooldown or uncertain-submission events.

Duplicate suppression worked operationally. It did not prevent stagnation from distinct permutations and minor wording changes returning empty or previously seen material.

## Saved scientific findings and extraction quality

These are source-reported findings in the saved corpus, not independently established clinical conclusions.

| Memory / node / action | Source and retained content | Limits for the research question |
| --- | --- | --- |
| r1 / q1 / 48 | [PMID 21675931](https://pubmed.ncbi.nlm.nih.gov/21675931/): an 81-year-old patient's COP improved with steroids; BAC was diagnosed in new locations approximately 1.5 years later. The authors describe radiological mimicry and steroid-responsive inflammation accompanying BAC. Three qualified units. | Single case; no four-week doubling measurement or comparative diagnostic probability. Particle-exposure risk language is appropriately marked as an author claim. |
| r2 / q1 / 51 | [PMID 41292408](https://europepmc.org/article/MED/41292408): retrospective comparison of 125 lung-cancer and 21 OP patients; abstract reports lower median CRP in OP and no difference in other systemic inflammatory indexes. Three qualified units. | No growth-rate or spiculation analysis. CRP units, 45.2 versus 64 mg/dL, are reproduced from the supplied abstract and were not independently validated or corrected. |
| r3 / q2 / 143 | [PMID 37183641](https://pubmed.ncbi.nlm.nih.gov/37183641/): 115 ground-glass nodules, 27 growing, median volume doubling time 822 days; three-dimensional measurement, growth predictors and pathology of 32 resected nodules. Three findings and one explicitly derived question. | Different lesion population and timescale. The supplied abstract was truncated. Median doubling time describes growing nodules, not all lesions or a four-week malignancy threshold. |
| r4 / q3 / 149 | [LIP case report](https://doi.org/10.1002/rcr2.70416): inflammatory disease presented as a solitary spiculated nodule, diagnosed by resection and histopathology. One qualified finding. | Single case; no doubling-time data, infection-versus-malignancy comparison or likelihood estimate. |

The retained counts follow the supplied abstracts, with source qualifications largely preserved. One precision issue needs review: r3's predictor finding folds the age ≥63 cutoff into its multivariate statement, while the supplied abstract reports that cutoff under ROC analysis separately from multivariate age effects. No memory directly estimates how strongly a four-week volume doubling favours infection over malignancy. The GGN study cannot supply that estimate through extrapolation. No equations, images or synthesized conclusions were created.

## Glossary enrichment results

R3 proposed **17 terms**. Fourteen proposals were admitted, including one merge, leaving **13 candidate records**. Three optional proposals were rejected: BAC for an unsupported relationship; Organizing Pneumonia and Pulmonary ground glass nodules because their expanded names were absent from the quoted passages. All associated valid scientific extractions still committed.

| Canonical term | Saved terminology outcomes |
| --- | --- |
| Pulmonary aspergilloma | Eight unavailable; one no exact match |
| Aspergillus fumigatus | Ten unavailable |
| Pulmonary tuberculosis | Three unavailable; one not attempted |
| Cryptogenic organizing pneumonia | Four unavailable |
| reversed halo sign | Four unavailable |
| Lung Cancer | Three unavailable; one matched |
| Neutrophil-to-lymphocyte ratio | One unavailable; one no exact match |
| Systemic immune inflammation index | Two unavailable; one not attempted |
| C-reactive protein | Two unavailable; one not attempted |
| Volume doubling time | One unavailable |
| Spiculated sign | One unavailable |
| Lymphocytic interstitial pneumonia | One unavailable |
| Spiculated pulmonary nodule | One unavailable |

There were **31 API calls**, **16 term-cache hits**, zero concept-cache hits and **109.414 seconds** of aggregate enrichment time. Across 47 saved term outcomes, 41 were unavailable, three not attempted, two not found and one matched. Outcome counts include cached failures and must not be read as counts of new network requests. Unavailable reasons were 33 read-timeout outcomes and eight terminology-response-deadline outcomes. There were no ambiguous outcomes, provider-error statuses or recorded HTTP 429 responses. Three-second request limits and the eight-second R3 budget were observed; no retry limits or cooldowns were bypassed.

At action 80, `Lung Cancer` matched **MeSH M0012750**, preferred name Lung Cancer, exact matching term T024374. The returned concept had no descriptor IDs and **an empty descriptions list**. Authority aliases were admitted, but no definition or scope note was obtained. The other two completed exact-name lookups found no match; that does not establish absence of the concepts from all terminology resources. NLM terminology is attribution-bearing terminology data, not independent evidence about this medical question.

All 13 final records have empty `definitions` and status `candidate`. Later R1 requests received the alias-enriched Lung Cancer record, but its `definition` was null. **No subsequent R1 received an enriched definition**, so this experiment cannot demonstrate that enriched definitions improved search selection. Later choices continued to recycle the same disease/growth combinations.

There is an additional extraction weakness: R3 supplied null definitions even where source passages contained definitional wording, including the Aspergilloma excerpt and the reversed-halo parenthetical description. Thus API latency alone does not explain the lack of definitions. These observations support reviewing both R3's definition extraction and terminology latency budgets; neither was changed during the run.

## Synthesis, R4, branching and stagnation

All **17 S1 decisions were `no_candidate`**. Sixteen assessed the unchanged r1/r2 pair; the last, at action 148, also received the newly created r3. No S2 was dispatched and no synthesis conclusion exists to validate. Declining to combine these peripheral findings into an answer was reasonable; repeatedly paying for the unchanged catalogue was inefficient. S1 consumed **34,181 tokens** and **44.138 seconds** of model request/response time.

All **16 R4 assessments were `unresolved`** and concerned the root. Five had no scientific memories; the later assessments correctly recognized that the two root memories did not address doubling time or comparative diagnostic strength. There were no child assessments before the stop. R4's conservative judgments are supported by the supplied evidence.

Action 133 set `search_blocked=completed_queries_only`; action 134 assessed unresolved and exhausted the root through **`search_blocked`**. Root capacity was only **5,902 / 12,288 tokens**, so capacity did not cause exhaustion. R5 at action 135 created three living children: distinguishing neoplastic growth from inflammatory consolidation; testing growth as an independent predictor with inflammation as a confounder; and comparing infectious mimics and short-term morphology. Final states are **one split root, three living children, zero answered, zero killed and zero currently exhausted**. One metadata source remains pending for q3; the run stopped on user instruction, not because all work was blocked.

The first two child questions overlap substantially. More seriously, the first adds an unsupported current-classification premise about BAC and compresses the saved statement about **inflammation accompanying carcinoma** responding to steroids into carcinoma responding to steroids. Those premises are not established by the supplied root evidence. This is scientific drift in branching, even though the questions passed structural validation. No such premise was manually inserted by the supervisor.

Memory creation occurred only at actions **48, 51, 143 and 149**. Between r2 and r3, **91 intervening actions created no research memory**. Distinct query strings, retained candidate variants and repeated S1/R4 decisions gave an appearance of activity without comparable evidence accumulation. Duplicate checks worked, while semantic search stagnation persisted.

## Comparison with the previous experiment

The comparison is with [medical-r1-r4-20261031.md](medical-r1-r4-20261031.md). Both used the same question, Qwen model, 16,384-token context, temperature/thinking/output settings, default medical provider profiles, two results per provider and 12,288-token capacity. Implementation/prompt changes, live retrieval and different autonomous trajectories prevent attributing differences solely to enrichment.

| Measure | Previous run | This stopped run |
| --- | ---: | ---: |
| Actual research time | 142.666 s | 520.032 s |
| Controller actions | 50: 49 committed, one rejected | 149, all committed |
| LLM calls / total tokens | 30 / 60,623 | 83 / 172,473 |
| Actual provider submissions | 20 | 63 |
| Unique retrieved records | 17 | 31 |
| Research memories / synthesis | 2 / 0 | 4 / 0 |
| Processed abstracts | 5 | 7 |
| Glossary entries / definitions | 7 / 0 | 13 / 0 |
| R4 assessments | Five unresolved | 16 unresolved |
| Stop | Whole-response R1 validation rejection | User stop for low yield |
| Branching | None | Root search-blocked, then three children |

More than three times the controller actions yielded only two additional, still peripheral memories. Memory yield per processed source was 4/30 versus 2/17, but neither run produced direct evidence answering the question. The new partial validator did not encounter an invalid component in this live run. The new enrichment mechanism was exercised, but definition coverage remained zero. There is no observed scientific benefit from enriched definitions to claim.

## Recommendations for review

1. **Prioritize retrieval quality.** Review AND compilation of alternative diagnoses and long mixed-concept phrases. Obtain abstracts or suitable full text before spending R3 calls on promising metadata records. Preserve the one-provider-search and one-source-extraction action contracts.
2. **Make R3 retention consistent.** Compare the accepted and omitted adjacent case reports against an explicit evidence/gap policy. Preserve qualified relevant observations without demanding that every source answer the whole question. Do not create memories merely to raise counts.
3. **Diagnose terminology latency and missing definitions separately.** Evaluate the current three/eight-second budgets against measured endpoint latency, and test cases where a matched concept has no description. Improve source-definition extraction where the passage already provides one. Preserve bounded requests, cache provenance and cooldowns.
4. **Avoid repeated unchanged synthesis selection.** Consider remembering `no_candidate` for an unchanged eligible catalogue until new relevant input arrives.
5. **Detect semantic stagnation and strengthen branching grounding.** Surface repeated empty rounds and duplicate-source returns despite distinct strings. Audit child-question premises against source qualifications and reduce overlapping branches. Do not treat search-plan exhaustion as a scientific conclusion.
6. **Give supervisors a cooperative stop control.** Check a stop request between actions, retain canonical-event reconciliation and avoid requiring process attachment for safe operator shutdown.

These are proposals only. No source code, LLM prompt, architecture, strategy, provider configuration or model-generated scientific content was changed to improve this outcome.

## Preserved artifacts and verification

The experiment remains in the single active `memory/` corpus: four `memories/r*.md`, 13 `glossary/g*.json`, 66 provider outcome files under `research/results/`, current `research/state.json`, 83 interaction directories and 150 committed journals including initialization. The protected legacy corpus remains separate and untouched. No experiment memory archive was created and no legacy experiment directory was deleted.

Execution and audit files are under project `log/`, including `log/medical-glossary-20261031/`, the uniquely named execution JSONL and concise/full transcripts under `log/transcripts/medical-glossary-20261031/`. The stop receipt, recovery assessment, source audit and preservation hashes remain local. Both corpus locks are free and the supervised research process has exited.

Post-stop verification found **zero pending journal operations, zero unpublished journals, zero recovery problems and no uncertain model/provider submissions**. Repeating `glossary-view` produced identical exports; all **222 canonical files** were unchanged by export, and all 596 protected pre-existing artifacts retained their hashes. Runtime auditing and integrity checks were performed; no new implementation or automated test-suite changes were made.

Generated local exports:

- `memory/research/glossary.md`
- `memory/research/glossary.html`

```bash
PYTHONPATH=src python3 -m mira glossary-view --experiment medical-glossary-20261031
xdg-open memory/research/glossary.html
```

Only this report is intended for the Git commit. Research memories, logs, terminology caches and generated glossaries remain local.
