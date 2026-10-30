# Revised R1 medical benchmark — 30 October 2026

**Result: no observed improvement in PubMed retrieval or evidence answering the selected question.** R1 produced valid ordered concepts and received correct independent search history, but five decisions still yielded only four distinct combined queries. The new run retained seven records and two research memories, matching the baseline; no synthesis was produced. Overall research-quality improvement is inconclusive, with higher token/model-call cost and mixed extraction quality. This is one uncontrolled live comparison, not a statistically reliable performance estimate.

## Setup and baseline

Implementation under test: `5aa31cb13f6c8173b98d054153a917865d8f56ab` on `main`. The baseline was retrieved with `git show d6fd05c:test-results/latest.md`: [original GitHub report](https://github.com/saolda/Mira/blob/d6fd05c/test-results/latest.md). Its experiment is `medical-question-file-20261029-074524`; the underlying implementation was `94cbe5e`. Architecture and current R1/controller/CLI were inspected before execution.

Exact selected/root question (`q1` throughout both runs):

> Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

`memory/questions/lung-growth.md` matched both that string and the baseline persisted root question exactly. It contains no supplementary background or research objectives. Its bytes and all 326 files in the baseline experiment were hash-checked and preserved.

Fresh experiment: `medical-r1-benchmark-20261030` (the name was unused). The existing Qwen3.6-35B-A3B Q4_K_M server at `127.0.0.1:8090` was reused without restarting or reconfiguring it. `/props` verified **16,384 tokens per request** (the process serves two slots with 32,768 total), the expected GGUF model and native chat template. Both runs used temperature **0**, thinking **disabled**, JSON response format, output limit/reserve **4,096**, explicit **medical** strategy, **two results per provider**, default provider ordering, glossary settings and research capacity **12,288**. Model HTTP timeout was 90 seconds; adapters retained their 25-second timeout.

Only existing `Research`, `HTTPModel`, `Experiments` and provider APIs were used. The local supervisor called `Research.step()` until 40 direct research actions, checking a five-minute deadline and arming a 300-second watchdog; no controller behavior or request contents were patched. S1 actions could execute normally between direct actions. Run duration excludes initialization and the later manual audit, matching the baseline timing convention.

Execution: **15:10:16–15:12:00 AEDT**, 30 October 2026 (2026-10-30T04:10:16.823100+00:00–2026-10-30T04:12:00.936804+00:00); **104.114 seconds**. Stopped normally at `research_cycle_limit`, well below five minutes. The root remains living and resumable; no final answered state was declared. The borrowed server was left running.

## Side-by-side results

| Metric | Previous medical experiment | Revised R1 |
| --- | ---: | ---: |
| Direct research actions | 40 | 40 |
| Total controller actions | 42 | 47 |
| R1 / R2 / R3 / R4 | 5 / 24 / 7 / 4 | 5 / 24 / 7 / 4 |
| S1 / S2 | 1 / 1 | 7 / 0 |
| Model calls | 18 | 23 |
| Provider opportunities / actual submissions | 24 / 20 | 24 / 20 |
| Records returned before deduplication | 20 | 20 |
| Unique records retained and R3-processed | 7 | 7 |
| Duplicates suppressed | 13 | 13 |
| Abstracts / metadata-only records among unique records | 3 / 4 | 3 / 4 |
| Research memories / synthesis memories | 2 / 1 | 2 / 0 |
| Glossary candidates / distinct candidates subsequently used | 4 / 0 | 3 / 1 |
| R1 decisions / distinct exact combined queries | 5 / 4 | 5 / 4 |
| Repeated combined query decisions | 1 | 1 |
| PubMed records | 0 | 0 |
| Europe PMC unique records | 4 | 3 |
| Crossref unique records | 3 | 4 |
| Diagnostic doubling-time values or infection-versus-cancer likelihood estimates in memories | 0 | 0 |
| Prompt tokens (API usage sum) | 41,736 | 56,336 |
| Completion tokens | 3,199 | 3,480 |
| Total tokens | 44,935 | 59,816 |
| Largest prompt / with 4,096 reserve | 5,084 / 9,180 | 5,395 / 9,491 |
| Context-budget failures / rejected responses | 0 / 0 | 0 / 0 |
| Elapsed seconds | 113.095 | 104.114 |

“Unique sources” here means retained provider records, not independently verified, relevant scientific evidence. The new seven consist of three abstracts, three journal/conference publication titles and one NCI terminology record. No cross-provider duplicate was returned in either run. Token sums for the baseline were checked against its saved API responses, rather than estimated from the report.

The new run was 8.981 seconds shorter (7.9%) but made five additional model calls (27.8%) and consumed 14,881 more tokens (33.1%; prompt tokens increased 35.0%). Seven S1 `no_candidate` decisions replaced the previous S1 selection and S2 synthesis. API latency, ranking/index changes, server load and the different action mix were uncontrolled; faster wall time does not demonstrate better R1 efficiency.

## Actual R1 prompts and decisions

All **23 actual serialized model requests** were inspected through their saved interaction records and the viewer verification path. Filled messages matched the recorded template sources/bindings and exact sent messages. For every R1 request, the JSON was decoded directly from the rendered `PREVIOUS PROVIDER SEARCH OUTCOMES`, `RESEARCH GLOSSARY` and `PREVIOUSLY GENERATED SEARCH TERMS` sections; these were not inferred from the template.

Each supplied history was independently compared with only the earlier committed R2 evidence for `q1`. All **39 supplied history entries** matched provider, exact compiled query, submission flag, status, returned count and unique count. Histories had **0, 5, 10, 12 and 12** entries in chronological order. Every profile ID was **null**, correctly reflecting the unchanged legacy R2 records. No `recent_search_outcomes` remained in glossary context. All eight prompt variables were present; root/ancestor context was empty because the selected node was the root, and the brief preserved the supplied question-document reference with empty context/objectives.

R1 template SHA-256 in every request: `118ab9500a04b6908cfa424ecb726e52ac673ff0f052fda2b5cdfa4824aa89bd`. Raw and accepted concept lists were identical for every decision. Each entry satisfied the 2–6-concept/five-word contract; no filtering was needed. The table under each decision lists the exact history supplied: query labels expand verbatim in the next section, and the cycle column identifies the committed retrieval, not an extra field supplied to the model.

### R1 decision 1: controller cycle 1

**Selected question:** Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

**Original priority order:** 1. `spiculated pulmonary nodule`; 2. `volume doubling time`; 3. `lung malignancy`; 4. `pulmonary infection`; 5. `lesion growth rate`.

**Glossary supplied:** none.

**Previously proposed terms supplied:** none.

**Novelty and gap assessment:** The initial five concepts cover the lesion, growth metric and competing etiologies. They are topically relevant but jointly mix several research needs. No memory-derived gap existed yet, and neither CT repeatability nor fast-growing malignant subtypes was targeted.

**Actual prompt tokens:** 1,028. **Interaction:** `00000001-c70e2e67bb494498a193bc494f8ae436`.

**Provider-search outcomes supplied:** none (fresh experiment).

### R1 decision 2: controller cycle 14

**Selected question:** Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

**Original priority order:** 1. `volume doubling time`; 2. `spiculated nodule`; 3. `lung cancer`; 4. `pulmonary infection`; 5. `interval growth`.

**Glossary supplied:** `g1` Volume doubling time (candidate; aliases: VDT); `g2` Metabolically occult (candidate; no aliases); `g3` Interval evolution (candidate; no aliases).

**Previously proposed terms supplied:** `spiculated pulmonary nodule`; `volume doubling time`; `lung malignancy`; `pulmonary infection`; `lesion growth rate`.

**Novelty and gap assessment:** The model moved volume doubling time to first priority, shortened the morphology phrase, substituted lung cancer for lung malignancy, and changed lesion growth rate to interval growth. These are mostly lexical/reordering changes, not a new scientific subquestion. The supplied derived question asks how a four-week doubling time discriminates etiologies; the concepts address it only broadly.

**Actual prompt tokens:** 2,332. **Interaction:** `00000009-1e6cd1cfd8ab48be90b5e87262344473`.

| Retrieval cycle | Provider | Query | Submitted | Status | Returned | Unique |
| ---: | --- | --- | --- | --- | ---: | ---: |
| 2 | pubmed | Q1 | true | empty | 0 | 0 |
| 3 | europe_pmc | Q1 | true | ok | 2 | 2 |
| 7 | openalex | Q1 | true | rate_limited | 0 | 0 |
| 8 | crossref | Q1 | true | ok | 2 | 2 |
| 11 | wikipedia | Q1 | true | empty | 0 | 0 |

### R1 decision 3: controller cycle 23

**Selected question:** Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

**Original priority order:** 1. `volume doubling time`; 2. `spiculated nodule`; 3. `lung neoplasms`; 4. `pulmonary infection`; 5. `interval growth`.

**Glossary supplied:** `g1` Volume doubling time (candidate; aliases: VDT); `g2` Metabolically occult (candidate; no aliases); `g3` Interval evolution (candidate; no aliases).

**Previously proposed terms supplied:** `spiculated pulmonary nodule`; `volume doubling time`; `lung malignancy`; `pulmonary infection`; `lesion growth rate`; `spiculated nodule`; `lung cancer`; `interval growth`.

**Novelty and gap assessment:** Only lung cancer changed to lung neoplasms. This is a potentially useful indexing synonym, but no substantive gap or mechanism changed. The same unresolved four-week diagnostic question was supplied.

**Actual prompt tokens:** 2,756. **Interaction:** `00000013-60583301f1584493b5b52d4ded73356e`.

| Retrieval cycle | Provider | Query | Submitted | Status | Returned | Unique |
| ---: | --- | --- | --- | --- | ---: | ---: |
| 2 | pubmed | Q1 | true | empty | 0 | 0 |
| 3 | europe_pmc | Q1 | true | ok | 2 | 2 |
| 7 | openalex | Q1 | true | rate_limited | 0 | 0 |
| 8 | crossref | Q1 | true | ok | 2 | 2 |
| 11 | wikipedia | Q1 | true | empty | 0 | 0 |
| 15 | pubmed | Q2 | true | empty | 0 | 0 |
| 16 | europe_pmc | Q2 | true | ok | 2 | 0 |
| 17 | openalex | Q2 | false | rate_limited | 0 | 0 |
| 19 | crossref | Q2 | true | ok | 2 | 1 |
| 21 | wikipedia | Q2 | true | empty | 0 | 0 |

### R1 decision 4: controller cycle 33

**Selected question:** Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

**Original priority order:** 1. `volume doubling time`; 2. `spiculated nodule`; 3. `lung neoplasms`; 4. `pulmonary infection`; 5. `interval growth`; 6. `lung cancer`.

**Glossary supplied:** `g1` Volume doubling time (candidate; aliases: VDT); `g2` Metabolically occult (candidate; no aliases); `g3` Interval evolution (candidate; no aliases).

**Previously proposed terms supplied:** `spiculated pulmonary nodule`; `volume doubling time`; `lung malignancy`; `pulmonary infection`; `lesion growth rate`; `spiculated nodule`; `lung cancer`; `interval growth`; `lung neoplasms`.

**Novelty and gap assessment:** The model appended lung cancer to the previous five concepts, retaining lung neoplasms as well. Adding a near-synonym did not create a different evidence target and may add unnecessary conjunctive demands in the unchanged PubMed query. Six concepts remained valid structurally.

**Actual prompt tokens:** 2,930. **Interaction:** `00000018-8a9d4e8148a046e185b7c24297453c1d`.

| Retrieval cycle | Provider | Query | Submitted | Status | Returned | Unique |
| ---: | --- | --- | --- | --- | ---: | ---: |
| 8 | crossref | Q1 | true | ok | 2 | 2 |
| 11 | wikipedia | Q1 | true | empty | 0 | 0 |
| 15 | pubmed | Q2 | true | empty | 0 | 0 |
| 16 | europe_pmc | Q2 | true | ok | 2 | 0 |
| 17 | openalex | Q2 | false | rate_limited | 0 | 0 |
| 19 | crossref | Q2 | true | ok | 2 | 1 |
| 21 | wikipedia | Q2 | true | empty | 0 | 0 |
| 25 | pubmed | Q3 | true | empty | 0 | 0 |
| 26 | europe_pmc | Q3 | true | ok | 2 | 1 |
| 28 | openalex | Q3 | false | rate_limited | 0 | 0 |
| 29 | crossref | Q3 | true | ok | 2 | 0 |
| 31 | wikipedia | Q3 | true | empty | 0 | 0 |

### R1 decision 5: controller cycle 43

**Selected question:** Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

**Original priority order:** 1. `volume doubling time`; 2. `spiculated nodule`; 3. `lung neoplasms`; 4. `pulmonary infection`; 5. `interval growth`.

**Glossary supplied:** `g1` Volume doubling time (candidate; aliases: VDT); `g2` Metabolically occult (candidate; no aliases); `g3` Interval evolution (candidate; no aliases).

**Previously proposed terms supplied:** `spiculated pulmonary nodule`; `volume doubling time`; `lung malignancy`; `pulmonary infection`; `lesion growth rate`; `spiculated nodule`; `lung cancer`; `interval growth`; `lung neoplasms`.

**Novelty and gap assessment:** This exactly repeated the third decision, removing the extra lung cancer from round four. It was not a meaningfully new search, despite earlier empty PubMed results for that exact query. None of the decisions specifically investigated CT volume repeatability or a rapidly growing malignant histology.

**Actual prompt tokens:** 2,949. **Interaction:** `00000023-6e89211a164f4ed7b2dcecb64483161f`.

| Retrieval cycle | Provider | Query | Submitted | Status | Returned | Unique |
| ---: | --- | --- | --- | --- | ---: | ---: |
| 19 | crossref | Q2 | true | ok | 2 | 1 |
| 21 | wikipedia | Q2 | true | empty | 0 | 0 |
| 25 | pubmed | Q3 | true | empty | 0 | 0 |
| 26 | europe_pmc | Q3 | true | ok | 2 | 1 |
| 28 | openalex | Q3 | false | rate_limited | 0 | 0 |
| 29 | crossref | Q3 | true | ok | 2 | 0 |
| 31 | wikipedia | Q3 | true | empty | 0 | 0 |
| 34 | pubmed | Q4 | true | empty | 0 | 0 |
| 35 | europe_pmc | Q4 | true | ok | 2 | 0 |
| 37 | openalex | Q4 | false | rate_limited | 0 | 0 |
| 38 | crossref | Q4 | true | ok | 2 | 1 |
| 40 | wikipedia | Q4 | true | empty | 0 | 0 |

The derived gap persisted in all four later R1 memory contexts: how a spiculated lesion doubling over four weeks changes the infection-versus-malignancy differential. Relevant findings and their qualifications were also supplied. Correctly delivering that gap did not ensure that R1 generated a different search strategy. Previous terms were always proposed concepts, while actual execution was represented only by the separate histories above.

### Glossary discovery and actual usage

R3 admitted three candidates: `g1` **Volume doubling time** (alias **VDT**, from the cohort abstract), `g2` **Metabolically occult** and `g3` **Interval evolution** (from the review). All lacked accepted definitions. Two additional proposals were rejected independently for source-reference/supporting-passage problems. All three entries were supplied to each later R1.

Only `g1` was registered as used, across **18 submitted provider queries** after its admission; the actual rate-limited OpenAlex submission counts, cooldown skips do not. However, volume doubling time was already proposed in the very first R1, before the glossary existed. Its later registration does **not** show that glossary discovery caused useful expansion. Neither newly supplied review phrase was used. Baseline: four candidates, zero registered uses.

## Provider retrieval and exact queries

These are the complete compiled query strings, sent unchanged to each provider when submission occurred. R2 still joins every accepted concept with spaces for all five medical providers; it does not retain a priority prefix or compile independent provider profiles. There were no hidden fallback queries.

**Q1**

```text
spiculated pulmonary nodule volume doubling time lung malignancy pulmonary infection lesion growth rate
```

**Q2**

```text
volume doubling time spiculated nodule lung cancer pulmonary infection interval growth
```

**Q3**

```text
volume doubling time spiculated nodule lung neoplasms pulmonary infection interval growth
```

**Q4**

```text
volume doubling time spiculated nodule lung neoplasms pulmonary infection interval growth lung cancer
```

Rounds used Q1, Q2, Q3, Q4 and Q3, respectively. All four distinct queries were actually submitted; Q3 was repeated in round five. Wikipedia had not been visited in the fifth round when the 40-action target was reached.

| Provider | Opportunities | Actual submissions | Returned | Unique | Duplicates | Empty | Actual HTTP 429 | Cooldown skips | Other failures | Research memories |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pubmed | 5 | 5 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| europe_pmc | 5 | 5 | 10 | 3 | 7 | 0 | 0 | 0 | 0 | 2 |
| openalex | 5 | 1 | 0 | 0 | 0 | 0 | 1 | 4 | 0 | 0 |
| crossref | 5 | 5 | 10 | 4 | 6 | 0 | 0 | 0 | 0 | 0 |
| wikipedia | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 |

Per-search audit (query IDs expand to the exact submitted strings above; a skipped entry is not an attempted network submission):

| Cycle | Provider | Query | Submitted | Outcome | Returned | Unique | Duplicates |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: |
| 2 | pubmed | Q1 | true | empty | 0 | 0 | 0 |
| 3 | europe_pmc | Q1 | true | ok | 2 | 2 | 0 |
| 7 | openalex | Q1 | true | rate_limited | 0 | 0 | 0 |
| 8 | crossref | Q1 | true | ok | 2 | 2 | 0 |
| 11 | wikipedia | Q1 | true | empty | 0 | 0 | 0 |
| 15 | pubmed | Q2 | true | empty | 0 | 0 | 0 |
| 16 | europe_pmc | Q2 | true | ok | 2 | 0 | 2 |
| 17 | openalex | Q2 | false | rate_limited (cooldown) | 0 | 0 | 0 |
| 19 | crossref | Q2 | true | ok | 2 | 1 | 1 |
| 21 | wikipedia | Q2 | true | empty | 0 | 0 | 0 |
| 25 | pubmed | Q3 | true | empty | 0 | 0 | 0 |
| 26 | europe_pmc | Q3 | true | ok | 2 | 1 | 1 |
| 28 | openalex | Q3 | false | rate_limited (cooldown) | 0 | 0 | 0 |
| 29 | crossref | Q3 | true | ok | 2 | 0 | 2 |
| 31 | wikipedia | Q3 | true | empty | 0 | 0 | 0 |
| 34 | pubmed | Q4 | true | empty | 0 | 0 | 0 |
| 35 | europe_pmc | Q4 | true | ok | 2 | 0 | 2 |
| 37 | openalex | Q4 | false | rate_limited (cooldown) | 0 | 0 | 0 |
| 38 | crossref | Q4 | true | ok | 2 | 1 | 1 |
| 40 | wikipedia | Q4 | true | empty | 0 | 0 | 0 |
| 44 | pubmed | Q3 | true | empty | 0 | 0 | 0 |
| 45 | europe_pmc | Q3 | true | ok | 2 | 0 | 2 |
| 46 | openalex | Q3 | false | rate_limited (cooldown) | 0 | 0 | 0 |
| 47 | crossref | Q3 | true | ok | 2 | 0 | 2 |

OpenAlex returned HTTP 429 with `Retry-After: 71344` on its one actual submission. The unchanged controller recorded the next four opportunities as `rate_limited` with `query_submitted=false` and `skipped=provider_cooldown`, rather than a new `deferred` status. R1 correctly saw the distinction through the submission flag. These records must not be called empty searches, five HTTP requests, or evidence against the terminology.

PubMed stayed at five actual empty searches, exactly as in the baseline. Europe PMC returned ten records but only three distinct abstracts (baseline four unique records, including one metadata-only record). Most later Europe PMC and Crossref returns were duplicates. Crossref supplied four unique metadata-only records and no usable abstract or research memory. Retrieval success therefore substantially overstates evidence yield.

## Unique records and extraction

| Source | Identifiers | Supplied evidence | R3 outcome / relevance |
| --- | --- | --- | --- |
| Zhou et al., *Clinical symptoms and prognosis of patients with pulmonary nodules: a real-world cohort study* | PMID 42780873; PMCID PMC13597835; DOI [10.3389/fmed.2026.1932201](https://doi.org/10.3389/fmed.2026.1932201) | Europe PMC abstract | `r1`; progression associations, no diagnostic infection-versus-cancer comparison |
| Lee, Yoon and Yoo, *Incidental Lung Lesions on the CT Component of Oncologic FDG PET/CT* | PMID 42793695; PMCID PMC13605315; DOI [10.3390/diagnostics16182910](https://doi.org/10.3390/diagnostics16182910) | Europe PMC abstract | `r2`; useful qualitative interpretive limitations, also present in baseline |
| Chandler, Patel and Cury, *Spiculated lung nodule: an unusual presentation of chronic pulmonary aspergillosis* | DOI [10.1016/j.chest.2022.08.414](https://doi.org/10.1016/j.chest.2022.08.414) | Crossref title/authors/date only | Empty extraction; title suggests a potentially relevant infectious mimic, but supplies no growth measurements |
| *Biochemical measure of the volume doubling time of human pulmonary neoplasms* | DOI [10.1016/S0169-5002(85)80158-6](https://doi.org/10.1016/S0169-5002(85)80158-6) | Crossref title/date only | Empty extraction; plausible growth-related publication, no results available to Mira |
| NCI, *Spiculated Nodule* | DOI [10.32388/s833ik](https://doi.org/10.32388/s833ik) | Crossref terminology metadata only | Empty extraction; not an empirical clinical study |
| Yu et al., *Pulmonary ground-glass opacity associated with cystic airspace: clinicopathological features and aggressiveness* | PMID 42291362; PMCID PMC13263805; DOI [10.21037/tlcr-2026-1-0027](https://doi.org/10.21037/tlcr-2026-1-0027) | Europe PMC abstract | Empty extraction; GGO progression over months, not a four-week etiologic comparison |
| *Role of the tumor volume and doubling time in lung cancer: Prognostic and therapeutic implications* | DOI [10.1016/S0169-5002(86)80363-4](https://doi.org/10.1016/S0169-5002(86)80363-4) | Crossref title/date only | Empty extraction; relevant-sounding title without usable scientific findings |

All seven records were R3-processed once. Five yielded no memory. For Yu et al., the model returned a nonempty summary with empty results; Python discarded that summary and recorded the normalization as designed. There were no invalid extractions or lost-source retries. Available authors, identifiers, publication dates and URLs were retained. Mira read no full texts or images.

## Scientific findings and attribution audit

### What the actual memories support

`r1` contains three findings from the cohort abstract: a 392-patient cohort, reported imaging/progression frequencies, a qualitative shorter-VDT association in progressing nodules, and associations with age, smoking and imaging features. These are progression observations, not malignancy-specific diagnostic probabilities. Its numeric percentages do not quantify whether a four-week doubling time favors infection.

**Extraction overstatement:** `r1#f1` assigns the supplied 33.7% figure to spiculation alone, while the source groups **lobulation and spiculation**. Its summary likewise simplifies a grouped imaging feature into a spiculation-specific association. The retained 25.2% progression figure and qualitative shorter-VDT statement are supported by the supplied abstract. `r1#f2` explicitly leaves the missing P-value unresolved rather than inventing a number. These points were checked against the [publisher abstract](https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2026.1932201/full).

`r2` contains two findings, one attributed author recommendation and one explicitly **derived** open question. Its statements about infection/inflammation mimicking malignancy on FDG PET/CT, PET-occult metastases and the limits of morphology/uptake are supported by the supplied review abstract. It limits them to the PET/CT interpretation setting and does not pretend that FDG partial-volume effects quantify CT volumetric repeatability. The open four-week question is correctly marked as derived, rather than attributed to the authors.

Attribution is mainly through each memory’s immutable source block; the prose still uses generic “the source”/“authors” rather than naming investigators. No incorrect author identity was introduced. The baseline’s biopsy-title overstatement and unsupported synthesis claims about guidelines did not recur in this run, but there was also **no S2 output to evaluate**. Their absence is not evidence that R1 fixed synthesis attribution.

| Requested evidence | New run actually obtained | Comparison with baseline |
| --- | --- | --- |
| Malignant lesion VDT distributions | Two metadata-only growth titles; cohort abstract only says progressing nodules had shorter VDT | Neither run extracted numeric malignant VDT values |
| Rapidly growing lung cancers | No relevant subtype-specific growth rates or examples | Unresolved in both |
| Infectious/inflammatory lesions | Review says they can mimic malignancy; aspergillosis title retained without findings | Different infectious lead; baseline had a granuloma case title, also inadequate for comparison |
| Spiculation and malignancy risk | Grouped morphology/progression association, simplified too far in `r1`; no malignancy odds or likelihood ratio | Some general quantitative cohort context, but no answer to the diagnostic question |
| CT measurement uncertainty | No repeatability limits, segmentation error estimates or four-week volume-change calibration | Unresolved in both |
| Comparative infection versus malignancy evidence | No comparative frequencies, likelihood ratios or posterior probabilities for the stated scenario | No improvement |

### Mira’s actual answer and uncertainty

No final synthesis or terminal answer was produced. The actual `r1` summary states:

> The source identifies that spiculation is a high-risk imaging feature associated with pulmonary nodule progression, but it does not provide specific volume doubling times or distinguish between infectious and malignant etiologies for spiculated lesions. Consequently, the evidence is insufficient to determine whether a four-week volume doubling time favors infection over malignancy in spiculated nodules.

The grouped-feature simplification in the first sentence needs the correction above. The limited “insufficient evidence” conclusion is appropriate for the material actually supplied. The final R4 (cycle 41) again returned `retry`, saying the retrieved studies lacked the needed doubling-time/etiology evidence. All four R4 decisions requested more research. Seven S1 decisions (cycles 6, 12, 18, 24, 30, 36 and 42) returned `no_candidate` because combining the two limited memories would not provide the missing evidence. No numerical confidence, preference for infection, or strength of such a preference was stated.

The run therefore leaves the clinical question unanswered. It demonstrates failure to retrieve/extract the required comparison, not absence of relevant literature. The baseline’s synthesis also concluded that the supplied evidence was insufficient; the revised R1 did not change that substantive result.

## Separate retrieval audit: restrictive queries and missed evidence

The following checks occurred **after the benchmark** and were never supplied to Mira, inserted into its corpus, counted in its seven sources, or used to alter its decisions. They distinguish retrieval limitations from claims about scientific absence.

### PubMed query-prefix probes

Three read-only NCBI ESearch probes used the same relevance sorting and two-record limit, with only the concept prefix changed. Full responses and automatic query translations are saved in `manual-pubmed-probes.json`.

| Separate audit query | Reported PubMed matches | First returned PMIDs |
| --- | ---: | --- |
| Q3, full five-concept string | 0 | none |
| `volume doubling time spiculated nodule` (first two concepts) | 6 | 39807982, 41869733 |
| `volume doubling time` (first concept) | 11,155 | 32398224, 39368222 |

NCBI’s returned `querytranslation` makes the additional concept groups conjunctive. The count change directly demonstrates that the full bundle excludes records retrievable by its prefix. It does **not** establish that any returned prefix record answers the question or that a one-concept search is a good profile; the latter is very broad and does not specify a pulmonary subject. ESummary titles sharpen the relevance caveat: the two-concept prefix returned studies on angiolymphatic invasion (PMID 39807982) and micropapillary adenocarcinoma (PMID 41869733), not a direct infection comparison. The one-concept query returned a hepatocellular-carcinoma meta-analysis (PMID 32398224) alongside a lung-cancer VDT meta-analysis (PMID 39368222). The latter is another potentially useful growth lead that Mira missed; the former demonstrates loss of pulmonary scope. These are title-level observations, not study appraisal. Full ESummary responses are retained locally.

### Publications not retrieved by Mira

A separate primary-source check found [Henschke et al., *Lung Cancers Diagnosed at Annual CT Screening: Volume Doubling Times*](https://pmc.ncbi.nlm.nih.gov/articles/PMC3329268/) (PMID **22454506**, DOI **10.1148/radiol.12102489**). Its 111 cancers had a median VDT of 98 days; the small-cell median was 43 days. That is useful malignant-growth evidence missing from both Mira runs, although it does not itself supply a calibrated infection-versus-malignancy likelihood for a four-week spiculated lesion.

[Horeweg et al., the NELSON nodule-probability analysis](https://pubmed.ncbi.nlm.nih.gov/25282285/?dopt=Abstract) (PMID **25282285**, DOI **10.1016/S1470-2045(14)70389-4**) is another missed primary publication linking nodule volume, VDT and cancer probability. Its abstract reports 9.9% cancer probability for the broad ≤400-day group; that screening-stratum estimate must not be applied as a four-week, morphology-specific probability or an infection comparison.

These are concrete examples of omitted relevant topics, not an exhaustive independent literature review. Forcing a publication to mention infection, spiculation, interval growth and malignant growth together is a plausible reason for losing papers that address just one necessary evidence gap. Exactly which term excluded each paper was not tested, so that causal explanation remains an inference.

The [full Zhou article](https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2026.1932201/full) also contains VDT numbers absent from Mira’s supplied abstract: group means 569.8 and 386.5, with P=0.023. These were not extracted by Mira and are progression-group data, not etiologic discrimination. This illustrates that retrieving an identifier or a partial abstract does not mean retrieving the numerical evidence in its full text.

### Other observable retrieval limitations

Europe PMC’s successful ranking returned a PET/CT pitfalls review, a general progression cohort and a GGO/cystic-airspace study; none supplied the requested four-week diagnostic comparison. The [Yu abstract](https://pubmed.ncbi.nlm.nih.gov/42291362/) concerns a different radiologic population and substantially longer evolution, so successful retrieval is not enough to call it relevant evidence.

The saved cohort and GGO abstracts contain missing clauses around P-value inequalities despite `truncated=false`. That flag measures the adapter’s character cap, not completeness of the scientific source. The existing `plain()` HTML-removal regex can consume text between literal `<` and a later `>`; this is a plausible data-loss mechanism, not a demonstrated R1 failure. Raw provider response bodies were not captured by these adapters, so precise transport-versus-cleaning attribution is limited. The complete adapter-returned source text seen by R3 is retained. No parser or adapter changes were made.

Crossref’s metadata-only results provide possible leads but cannot supply their study findings. The infection-versus-cancer bundle found a fungal-nodule title without usable text and two growth-related titles without growth values. Wikipedia returned nothing for the long combined strings. OpenAlex’s single real submission was unavailable because of rate limiting, so its potential relevance cannot be evaluated.

## Implications for the next query-profile task

Observed weaknesses to test within provider-specific query profiles:

1. **Prefix retention matters:** R1 now provides a usable priority order, but current medical queries still submit all five or six concepts together. The separate PubMed count probes provide a concrete restrictive-query example.
2. **Concept alternatives need provider-aware combination:** rounds three/five submit lung neoplasms alongside pulmonary infection and interval growth; round four adds lung cancer as well. Near-synonyms should be evaluated as alternatives rather than assumed useful extra constraints.
3. **Provider behavior differs:** identical strings produced zero PubMed records, duplicate-heavy Europe PMC abstracts and title-only Crossref leads. One combined string does not deliver equivalent evidence across providers.
4. **A relevant term list is not gap coverage:** the four-week uncertainty remained explicit in memory, yet no R1 decision isolated volumetric measurement error or fast malignant growth. Empty-query history and one known glossary term did not produce a substantive new topic.
5. **Availability is separate from terminology:** OpenAlex cooldown skips were correctly visible as unsubmitted. Query profiles and retries must retain that distinction; this run says nothing about OpenAlex search effectiveness.

No query profile, retry mechanism, prompt, adapter or architectural change was implemented. The comparison suggests that the R1 interface now supplies appropriate ingredients for profiles, but it does not demonstrate improved end-to-end retrieval while R2 still combines every concept.

## Validation, preservation and local artifacts

Automated suite: **313 tests passed, 0 failures, 0 errors, 0 skipped**, **53.911 seconds**. Command: `PYTHONPATH=src python3 scripts/run_tests.py --validation-summary ...`; full output is saved under `memory/benchmarks/r1-medical-tests.log`. Existing non-failing SQLite resource warnings remain. `git diff --check` passed.

All 23 responses passed structural validation; no context-budget or model transport failure occurred. Maximum model request plus reserve was 9,491 of 16,384 tokens. Final R5 capacity was 5,993 including reserve, below the 12,288 exhaustion threshold. Corpus validation passed (two documents, no equations), all journal operations were committed, and there were no unresolved interactions or pending synthesis calls. Both independent logs ended normally. Baseline hashes, question hash and protected implementation hashes were unchanged.

Local artifacts (all excluded from GitHub):

- Experiment / memories / source payloads / journal / exact interactions: `/home/eric/Dev/Mira/memory/research/medical-r1-benchmark-20261030`.
- Initialization execution log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_041016_medical-r1-benchmark-20261030_d80afefaf0c8.jsonl`.
- Research execution log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_041016_medical-r1-benchmark-20261030_717238b96201.jsonl`.
- Supervisor and per-step timings: `/home/eric/Dev/Mira/memory/research/medical-r1-benchmark-20261030/supervisor.jsonl`.
- Run integrity and preservation checks: `/home/eric/Dev/Mira/memory/research/medical-r1-benchmark-20261030/validation.json`.
- Machine-readable prompt/provider analysis: `/home/eric/Dev/Mira/memory/research/medical-r1-benchmark-20261030/benchmark-analysis.json`.
- Separate PubMed probes: `/home/eric/Dev/Mira/memory/research/medical-r1-benchmark-20261030/manual-pubmed-probes.json`.
- Separate probe result titles: `/home/eric/Dev/Mira/memory/research/medical-r1-benchmark-20261030/manual-pubmed-probe-titles.json`.
- Supervisor script: `/home/eric/Dev/Mira/memory/benchmarks/run-r1-medical-20261030.py`.
- Full automated test output: `/home/eric/Dev/Mira/memory/benchmarks/r1-medical-tests.log`.

Only this benchmark report and the necessary `test-results/latest.md` summary are intended for the report commit on `main`. Source code, tests, architecture, query configuration and prompts remained byte-identical to the implementation under test. Final commit SHA and actual local/remote `main` equality are verified after committing and pushing and recorded in the final chat.
