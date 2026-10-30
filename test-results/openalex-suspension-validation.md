# OpenAlex suspension and extended medical validation

Recorded: 30 October 2026, Australia/Hobart. Implementation: `1bfb62f2912dee591a7b8b1ecc13fb03f323a386`.

**Result:** OpenAlex is excluded from new predefined strategies, and compatibility/preservation checks pass. The OpenAlex-free baseline completes two research rounds but stops on an oversized third R4 request. The alternative improves first-round Europe PMC retrieval but stops on repeated S1 output/selection failures. No calibrated answer to the infection-versus-malignancy question was established; one baseline synthesis and an alternative R3 summary introduce unsupported etiologic inferences.

## Scope and implementation

Removed `openalex` from all six predefined strategy database lists and profile mappings, preserving descriptions, IDs and the relative order of all other providers. New `medical` and `biomedical` experiments use `pubmed → europe_pmc → crossref → wikipedia`; general uses `wikipedia → crossref → arxiv`, engineering `arxiv → crossref → wikipedia`, humanities `crossref → wikipedia`, education `eric → crossref → wikipedia`.

The adapter, compiler support, `openalex_broad` profile, host pacing/retry policy and existing provider tests remain. Explicit provider lists and custom strategy registries still support OpenAlex. Four added regressions cover all predefined sequences/profile mappings, automatic R0 selection, an old five-provider snapshot with a deferred OpenAlex request surviving registry replacement/restart, and actual explicit-list fixture submission using `default`. Existing medical/engineering tests now expect the suspended predefined lists; OpenAlex parsing/deduplication tests remain active.

`main` was clean and already matched fetched `origin/main` (`cea3c43`). The change is a configuration suspension, not a scheduler bypass. No old experiment was resumed, reconfigured or migrated. Architecture, future-work planning, every prompt template, committed query-profile defaults and the question bytes were hash-protected. R1 retains its approved 2–6-concept contract. No unrelated source changes were made.

## Automated validation

The complete suite passed **343 tests, zero failures/errors/skips**, before experiments (**56.493 s**) and after experiments (**56.203 s**). The first development invocation had five stale expected-provider-list failures; these assertions were updated for the requested configuration, then the complete suite passed. Full logs remain local. The same suite covers scientific-text preservation, query-profile validation, provider pacing, deferred rounds, uncertain submissions and journal repair. Existing OpenAlex adapter tests still pass; no live OpenAlex call was needed to establish compatibility.

Commands: `PYTHONPATH=src python3 scripts/run_tests.py ...`; final logs `memory/benchmarks/openalex-suspension-20261030/tests-after-experiments.log`. `git diff --check`, repository object integrity and final local/remote ref equality are checked before/after publication as appropriate. The implementation and tests are a separate commit from this report.

## Controlled provider comparisons

Before complete research execution, the existing adapters submitted 12 bounded logical searches (at most two records each), with centrally configured host pacing and unchanged endpoint parameters. OpenAlex was never contacted. Numeric match totals came from the same captured PubMed ESearch / Europe PMC search responses; PubMed EFetch supplied abstracts. Full responses, exact parameters and automatic translations are local in `memory/benchmarks/openalex-suspension-20261030/controlled-queries.json`. No probe evidence or scientific answer was inserted into any Mira experiment. These were 14 HTTP requests, including two PubMed EFetch calls. No HTTP 429 occurred in these probes. A 429 would have stopped that provider and retained Retry-After, without probing around it.

Fixed concepts, in priority order: `volume doubling time`; `spiculated nodule`; `lung neoplasms`; `pulmonary infection`; `interval growth`. All profile variants were temporary; the default registry was not edited. “Returned” below is the bounded top two, not the total match count. Abstract availability and relevance were inspected from the actual adapter payloads. More matches do not establish better scientific evidence.

| Probe | Exact query | Total matches | Returned identifiers / evidence |
| --- | --- | --- | --- |
| pubmed_2 | `(volume doubling time) AND (spiculated nodule)` | 6 | pmid:39807982 (abstract); pmid:41869733 (abstract) |
| pubmed_3 | `(volume doubling time) AND (spiculated nodule) AND (lung neoplasms)` | 5 | pmid:39807982 (abstract); pmid:41869733 (abstract) |
| pubmed_4 | `(volume doubling time) AND (spiculated nodule) AND (lung neoplasms) AND (pulmonary infection)` | 0 | none |
| europe_pmc_2 | `"volume doubling time" AND "spiculated nodule"` | 9 | europe_pmc:MED:37998584 (abstract); europe_pmc:MED:39728910 (abstract) |
| europe_pmc_3 | `"volume doubling time" AND "spiculated nodule" AND "lung neoplasms"` | 3 | europe_pmc:MED:39728910 (abstract); europe_pmc:MED:28972803 (abstract) |
| europe_pmc_4 | `"volume doubling time" AND "spiculated nodule" AND "lung neoplasms" AND "pulmonary infection"` | 0 | none |
| europe_pmc_plain3 | `volume doubling time spiculated nodule lung neoplasms` | 168 | europe_pmc:MED:42780873 (abstract); europe_pmc:MED:42625155 (abstract) |
| epmc_initial_phrase2 | `"spiculated pulmonary nodule" AND "volume doubling time"` | 0 | none |
| epmc_initial_phrase3 | `"spiculated pulmonary nodule" AND "volume doubling time" AND "lung malignancy"` | 0 | none |
| epmc_initial_plain3 | `spiculated pulmonary nodule volume doubling time lung malignancy` | 181 | europe_pmc:MED:42780873 (abstract); europe_pmc:MED:42469902 (abstract) |
| crossref | `volume doubling time spiculated nodule lung neoplasms pulmonary infection` | not captured | doi:10.1016/s0169-5002(85)80158-6 (bibliographic_metadata); doi:10.1016/j.chest.2022.08.414 (bibliographic_metadata) |
| wikipedia | `volume doubling time spiculated nodule lung neoplasms` | not captured | none |

PubMed: two concepts found six publications; adding `lung neoplasms` left five, with the same first two PMIDs **39807982** and **41869733**. Adding `pulmonary infection` excluded all five remaining matches. Thus the fourth concept demonstrably excludes candidate publications; the two-vs-three difference did not improve the material actually returned at the two-record limit. Both returned abstracts concern already diagnosed cancer and morphology/aggressiveness, not cancer-versus-infection discrimination. The MPA abstract supplies a ≤310-day threshold and AUC 0.923, not a four-week etiologic probability. [ALI study](https://pubmed.ncbi.nlm.nih.gov/39807982/); [MPA study](https://pubmed.ncbi.nlm.nih.gov/41869733/).

The returned automatic translations confirm conjunctive concepts and PubMed term expansion: `lung neoplasms` maps to MeSH/all-field alternatives; the fourth adds pulmonary/infection alternatives under AND. Parentheses do not force whole-phrase matching for volume/doubling/time or spiculated/nodule. This is consistent with [PubMed’s search documentation](https://pubmed.ncbi.nlm.nih.gov/help/). The exact three translations, not reconstructed approximations, follow:

**pubmed_2**

```text
("volum"[All Fields] OR "volume"[All Fields] OR "volumes"[All Fields] OR "voluming"[All Fields]) AND ("double"[All Fields] OR "doubled"[All Fields] OR "doubles"[All Fields] OR "doubling"[All Fields] OR "doublings"[All Fields]) AND ("time"[MeSH Terms] OR "time"[All Fields]) AND (("spiculate"[All Fields] OR "spiculated"[All Fields] OR "spiculation"[All Fields] OR "spiculations"[All Fields] OR "spicule"[All Fields] OR "spicules"[All Fields]) AND ("nodulate"[All Fields] OR "nodulated"[All Fields] OR "nodulates"[All Fields] OR "nodulating"[All Fields] OR "nodulation"[All Fields] OR "nodulations"[All Fields] OR "nodulators"[All Fields] OR "nodule"[All Fields] OR "nodule s"[All Fields] OR "nodules"[All Fields]))
```

**pubmed_3**

```text
("volum"[All Fields] OR "volume"[All Fields] OR "volumes"[All Fields] OR "voluming"[All Fields]) AND ("double"[All Fields] OR "doubled"[All Fields] OR "doubles"[All Fields] OR "doubling"[All Fields] OR "doublings"[All Fields]) AND ("time"[MeSH Terms] OR "time"[All Fields]) AND (("spiculate"[All Fields] OR "spiculated"[All Fields] OR "spiculation"[All Fields] OR "spiculations"[All Fields] OR "spicule"[All Fields] OR "spicules"[All Fields]) AND ("nodulate"[All Fields] OR "nodulated"[All Fields] OR "nodulates"[All Fields] OR "nodulating"[All Fields] OR "nodulation"[All Fields] OR "nodulations"[All Fields] OR "nodulators"[All Fields] OR "nodule"[All Fields] OR "nodule s"[All Fields] OR "nodules"[All Fields])) AND ("lung neoplasms"[MeSH Terms] OR ("lung"[All Fields] AND "neoplasms"[All Fields]) OR "lung neoplasms"[All Fields])
```

**pubmed_4**

```text
("volum"[All Fields] OR "volume"[All Fields] OR "volumes"[All Fields] OR "voluming"[All Fields]) AND ("double"[All Fields] OR "doubled"[All Fields] OR "doubles"[All Fields] OR "doubling"[All Fields] OR "doublings"[All Fields]) AND ("time"[MeSH Terms] OR "time"[All Fields]) AND (("spiculate"[All Fields] OR "spiculated"[All Fields] OR "spiculation"[All Fields] OR "spiculations"[All Fields] OR "spicule"[All Fields] OR "spicules"[All Fields]) AND ("nodulate"[All Fields] OR "nodulated"[All Fields] OR "nodulates"[All Fields] OR "nodulating"[All Fields] OR "nodulation"[All Fields] OR "nodulations"[All Fields] OR "nodulators"[All Fields] OR "nodule"[All Fields] OR "nodule s"[All Fields] OR "nodules"[All Fields])) AND ("lung neoplasms"[MeSH Terms] OR ("lung"[All Fields] AND "neoplasms"[All Fields]) OR "lung neoplasms"[All Fields]) AND (("lung"[MeSH Terms] OR "lung"[All Fields] OR "pulmonary"[All Fields]) AND ("infect"[All Fields] OR "infectability"[All Fields] OR "infectable"[All Fields] OR "infectant"[All Fields] OR "infectants"[All Fields] OR "infected"[All Fields] OR "infecteds"[All Fields] OR "infectibility"[All Fields] OR "infectible"[All Fields] OR "infecting"[All Fields] OR "infection s"[All Fields] OR "infections"[MeSH Terms] OR "infections"[All Fields] OR "infection"[All Fields] OR "infective"[All Fields] OR "infectiveness"[All Fields] OR "infectives"[All Fields] OR "infectivities"[All Fields] OR "infects"[All Fields] OR "pathogenicity"[MeSH Subheading] OR "pathogenicity"[All Fields] OR "infectivity"[All Fields]))
```

Europe PMC: two exact phrases found nine matches, including CT volumetric phantom accuracy (PMID **37998584**) and observer variability (**39728910**). Three phrases found three, returning the observer study and margin-dependent reader variability (**28972803**). These are useful measurement evidence despite not directly comparing etiologies. The fourth phrase again reduced matches to zero. The three-concept plain-text variant found 168, returning a progression cohort (**42780873**) and persistent-subsolid-nodule growth study (**42625155**). This broadening changes ranking and evidence topics; it does not establish superior precision.

The prior first-round concepts were separately compiled without changing their wording. `"spiculated pulmonary nodule" AND "volume doubling time"` already returned zero; adding `"lung malignancy"` also returned zero. Therefore that third phrase is not required to explain the earlier empty response. Replacing exact phrases with compatible plain text for the same first three concepts returned 181 matches, including the progression cohort and a three-case pulmonary-cryptococcosis report (**42469902**). Comparing the two-phrase queries shows sensitivity to morphology terminology (long pulmonary-nodule phrase versus shorter spiculated-nodule phrase); the plain-text comparison also changes phrase and Boolean interpretation. These probes do not isolate the contribution of every individual word or establish which individual phrase fails alone.

The [Europe PMC API reference](https://dev.europepmc.org/RestfulWebService) documents relevance ranking and `core` results containing abstracts and full-text links; a returned link is not retrieved full text. Controlled measurement findings stayed outside Mira’s corpus: the phantom abstract reports volumetric underestimation of 20% / 24%, while the margin study reports spiculated manual-diameter variability ±3.5 mm and semiautomatic volume variability 28%. These distinct experimental settings cannot calibrate a particular patient’s apparent doubling. [Phantom study](https://pubmed.ncbi.nlm.nih.gov/37998584/); [margin study](https://pubmed.ncbi.nlm.nih.gov/28972803/).

Crossref’s one submission returned two metadata-only leads: *Biochemical measure of the volume doubling time of human pulmonary neoplasms* ([DOI](https://doi.org/10.1016/S0169-5002(85)80158-6)) and *Spiculated lung nodule: an unusual presentation of chronic pulmonary aspergillosis* ([DOI](https://doi.org/10.1016/j.chest.2022.08.414)). Titles alone supply no growth data. Wikipedia’s one submission was empty. Repeated independent probing was unnecessary; subsequent submissions occurred only as normal Mira controller actions.

## Research protocol and alternative configuration

Question unchanged: **Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?** The source is `memory/questions/lung-growth.md`, SHA-256 `43e60fbb66510702d399a4fff91b1226fdacbe73597c6a8cd845aa9408631069`; no context or research objectives supplied an answer.

All new experiments reuse the existing local Qwen3.6-35B-A3B Q4_K_M server (`127.0.0.1:8090`) without restarting it: verified context 16,384/request, output limit/reserve 4,096, temperature 0, thinking disabled, JSON output, medical strategy, two records/provider, normal 12,288 capacity threshold and unchanged synthesis/branching cadence. Each supervisor permits up to **40 direct R1–R4 actions** and **900 seconds**, with a watchdog, stopping on completion, noncommitted/error status or unproductive provider waiting. Controller/model/source logs are retained in full. Initialization is excluded from the elapsed research time, consistent with previous runs. No old experiment is used to conduct a live validation.

Baseline uses committed profiles. The alternative uses the temporary `memory/benchmarks/openalex-suspension-20261030/alternative-profiles.json` through `Research.initialize(profile_registry=...)` (the existing CLI interface is `--query-profiles`). It preserves all profile IDs/version 1 within the separate registry, provider order, host floors, retries and other settings. Frozen snapshots contain the exact alternative configuration:

| Provider/profile | Baseline | Alternative |
| --- | --- | --- |
| pubmed / pubmed_balanced | max_terms 3; compiler pubmed; AND / unquoted_atm / literal_words | max_terms 2; same compiler and rules |
| europe_pmc / europe_pmc_balanced | max_terms 3; phrase_and; AND / phrase / backslash | max_terms 3; legacy; provider_legacy combination/quoting/escaping (compatible plain space joining) |
| crossref / crossref_bibliographic | max_terms 4; text | unchanged |
| wikipedia / wikipedia_general | max_terms 3; text | unchanged |

The existing `text` compiler is not declared compatible with Europe PMC; the supported `legacy` compiler provides the tested plain search without inventing syntax or modifying source. Choosing PubMed two terms preserves more candidate matches, but its fixed-probe top two are identical to three; choosing Europe PMC plain three avoids the observed first-round exact-phrase zero. These are defensible experimental hypotheses, not approved new defaults.

## Cross-experiment comparison

| Metric | Previous R1 | Previous profiles | No-OpenAlex baseline | Alternative |
| --- | --- | --- | --- | --- |
| Implementation | 5aa31cb | df75a87 | 1bfb62f | 1bfb62f + temporary registry |
| Stop condition | 40-action limit | waiting_for_provider | R4 context blocked | S1 incomplete, then invalid single-memory selection |
| Direct actions committed | 40 | 10 | 23 | 5 |
| Controller actions committed / attempted | 47 / 47 | 12 / 12 (+ waiting return) | 28 / 29 | 5 / 7 |
| R1 / R2 / R3 / R4 dispatched or committed (R2 no model) | 5 / 24 / 7 / 4 | 1 / 5 / 4 / 0 | 3 / 12 / 6 / 2 | 1 / 2 / 2 / 0 |
| S1 / S2 model calls | 7 / 0 | 1 / 1 | 4 / 1 | 2 / 0 |
| Total model calls | 23 | 7 | 16 | 5 |
| R1 rounds started / R4 rounds completed | 5 / 4 | 1 / 0 | 3 / 2 | 1 / 0 |
| Distinct submitted strings / provider-query pairs | 4 / 17 | 4 / 5 | 12 / 12 | 2 / 2 |
| Repeated actual provider-query submissions | 3 | 0 | 0 | 0 |
| Provider opportunities / actual logical submissions | 24 / 20 | 5 / 5 | 12 / 12 | 2 / 2 |
| Returned / unique / duplicate records | 20 / 7 / 13 | 4 / 4 / 0 | 11 / 6 / 5 | 4 / 4 / 0 |
| Unique abstracts / metadata | 3 / 4 | 2 / 2 | 4 / 2 | 4 / 0 |
| Unique records R3-processed / pending | 7 / 0 | 4 / 0 | 6 / 0 | 2 / 2 |
| Relevant scientific abstract publications, including adjacent populations | 3 | 2 | 4 | 4 retrieved; 2 processed |
| Direct four-week infection-vs-cancer comparison | 0 | 0 | 0 | 0 |
| Research / synthesis memories | 2 / 0 | 2 / 0 | 4 / 1 | 2 / 0 |
| Glossary candidates / distinct used | 3 / 1 | 4 / 1 | 6 / 1 | 4 / 1 |
| Prompt tokens | 56,336 | 15,243 | 46,347 | 9,932 |
| Completion tokens | 3,480 | 2,734 | 5,416 | 7,267 |
| Total tokens | 59,816 | 17,977 | 51,763 | 17,199 |
| Largest dispatched prompt / plus reserve | 5,395 / 9,491 | 3,152 / 7,248 | 9,148 / 13,244 | 2,721 / 6,817 |
| Research elapsed seconds | 104.114 | 74.342 | 138.906 | 215.856 wall; 141.247 active |
| Final deferred searches | 0 (4 legacy cooldown skips) | 1 OpenAlex | 0 | 0 |
| Actual provider 429 / other provider failures | 1 / 0 | 1 / 0 | 0 / 0 | 0 / 0 |
| Invalid model responses / predispatch budget blocks | 0 / 0 | 0 / 0 | 0 / 1 | 2 / 0 |
| Branching calls | 0 | 0 | 0 | 0 |
| Scientific outcome | No answer | No answer | More adjacent findings; unsupported etiologic synthesis | Better EPMC retrieval; infectious abstract still pending |

Counts distinguish committed work, rejected actions and actual model dispatch. The blocked third baseline R4 is an additional attempted action, not a third model call. The alternative includes both rejected S1 calls and their token usage. Relevant abstract counts are reviewer-assessed topical evidence for at least one requested subquestion, **not** four-week diagnostic evidence; metadata leads are excluded. Previous statistics were cross-checked against preserved reports and local records. The previous R1 run repeated three actual provider/query submissions (the repeated fifth-round query in PubMed, Europe PMC and Crossref), in addition to legacy cooldown skips. The previous profiles run’s waiting return did not commit an action. No run retrieved full text.

Optional third experiment: **not run**, because the first two did not both complete successfully. Neither 40 direct actions nor 15 minutes was exceeded. Unequal workloads and different stopping conditions preclude an overall efficiency claim, even where token totals or runtime are lower. Reducing a prefix and changing LLM decisions, live rankings, source text and resulting memory summaries are not separately controlled after the first round. Temperature zero did not ensure byte-identical extraction/selection responses.

Earlier milestone reports: [revised R1](r1-medical-benchmark.md) and [query profiles](query-profile-validation.md). The new baseline completes two rounds where the previous deferred-OpenAlex validation completed none; its limiting factor becomes context size. The alternative demonstrates retrieval improvement on identical initial concepts but never completes a round because S1 rejects. These are distinct operational and scientific findings.

### New provider totals

| Run | Provider | Submissions / HTTP requests | Records / unique / duplicate | Distinct queries | Outcomes |
| --- | --- | --- | --- | --- | --- |
| medical-no-openalex-baseline-20261030 | crossref | 3 / 3 | 6 / 2 / 4 | 3 | {'ok': 3} |
| medical-no-openalex-baseline-20261030 | europe_pmc | 3 / 3 | 0 / 0 / 0 | 3 | {'empty': 3} |
| medical-no-openalex-baseline-20261030 | pubmed | 3 / 6 | 5 / 4 / 1 | 3 | {'ok': 3} |
| medical-no-openalex-baseline-20261030 | wikipedia | 3 / 3 | 0 / 0 / 0 | 3 | {'empty': 3} |
| medical-query-comparison-20261030 | crossref | 0 / 0 | 0 / 0 / 0 | 0 | {} |
| medical-query-comparison-20261030 | europe_pmc | 1 / 1 | 2 / 2 / 0 | 1 | {'ok': 1} |
| medical-query-comparison-20261030 | pubmed | 1 / 2 | 2 / 2 / 0 | 1 | {'ok': 1} |
| medical-query-comparison-20261030 | wikipedia | 0 / 0 | 0 / 0 / 0 | 0 | {} |


## Detailed research behavior and scientific audit

### Baseline: medical-no-openalex-baseline-20261030

Stopped at **23 committed direct actions**, **28 committed / 29 attempted controller actions**, after **138.906 s**, with **two R4-completed rounds and a third complete provider pass**. All three R4 opportunities became eligible without OpenAlex; the third was blocked before model dispatch. This establishes that the temporary suspension removes this experiment’s long OpenAlex wait. It does not establish that all other providers will remain available.

R1 generated three ordered lists:

1. `spiculated pulmonary nodule`; `volume doubling time`; `lung malignancy`; `pulmonary infection`; `lesion growth rate`.
2. `volume doubling time`; `spiculated nodule`; `pulmonary infection`; `lung neoplasm`; `benign nodule`; `differential diagnosis`.
3. `volume doubling time`; `spiculated nodule`; `lung neoplasm`; `pulmonary infection`; `benign lesion`; `malignancy`.

The second shifts infection into the three-concept provider prefix; the third moves a malignant synonym back into it. These change actual queries and can recover different records, but do not isolate measurement error, malignant VDT distributions or a rapidly growing histology. The six-term output remains structurally valid. None of the complete provider/query pairs repeats within this short run. Reusing VDT is reasonable anchoring; calling a switch from lung malignancy to lung neoplasm a new scientific direction would overstate novelty. All R1s received the correct available outcomes and prior concepts. The first memory projection explicitly flags its bounded excerpts; correct delivery of gaps did not ensure targeted new directions.

PubMed supplied four unique abstracts; Europe PMC’s three exact-phrase queries were all empty. Crossref supplied two metadata-only records and four duplicates; Wikipedia’s three queries were empty. The source IDs and outcomes appear in the provider appendix. R3 created four research memories; the two metadata extractions were appropriately empty.

The radiomics source preserves ≤400 / >400 days and its numerical AUCs; it does not give a malignant-growth distribution or four-week infection comparison. The ALI extraction preserves the reported spiculation OR 2.05, VDT OR 0.96 and CIs, and its finding-level qualification correctly restricts interpretation to confirmed NSCLC. The VDT effect’s unit/scaling is not supplied in the abstract, so it cannot yield a four-week likelihood ratio. However, the R3 summary still suggests that rapid growth and spiculation indicate malignancy; that inference is outside this cancer-only population’s diagnostic comparison.

The progression cohort (PMID [42780873](https://pubmed.ncbi.nlm.nih.gov/42780873/)) supplies **392** patients, **1.5-fold** growth risk for the grouped **spiculated and lobulated margins**, and shorter VDT with **P < 0.05** in the progression group. R3’s substantive finding retains both morphology terms, but its summary assigns the 1.5-fold result to spiculation alone. Its statement that VDT was not an independent predictor infers more than the abstract explicitly reports: it is absent from the listed independent predictors, not explicitly declared excluded by a full model comparison. None of these progression associations distinguishes infection from cancer.

The MPA source’s **≤310 days** threshold is retained in `r4`, with the lung-adenocarcinoma population and missing etiologic comparison acknowledged. It is evidence about a prognostic subtype-associated cutoff, not an observed ~28-day growth example or a subtype-specific VDT distribution. The extraction omits the source’s AUC 0.923; valid selection of a relevant finding does not mean every available number was retained.

Both dispatched R4s chose `retry`, appropriately preserving an unresolved research question. The second reason says that the literature lacks data; only the retrieved material has been evaluated, so that language overstates the search coverage. No retrieval error was treated as a negative scientific result in the committed history. No R5/branching occurred; direct-research R5 capacity was only **7,646 / 12,288** tokens, despite R4 no longer fitting.

S1 ran four times: three `no_candidate` decisions and one selection of `r2` + `r3` (R=4,C=4,X=2,N=3,E=3; total **16/25**). Its repeated `no_candidate` reasons misdescribe `r1` as only slow growth >400 days, ignoring the recorded ≤400 group. The selected objective is worth investigating, but S1 already claims the two memories jointly strengthen a malignancy inference without an infection comparator.

S2 created `s1` with valid anchor references and consumption bookkeeping, but an **unsupported etiologic conclusion**: its summary favors a malignant etiology over infection by combining ALI prediction in known cancers with progression risk in a mixed cohort. These neither estimate diagnostic odds nor compare four-week growth in infection and malignancy. The synthesis contains a later caveat acknowledging missing comparative data, which contradicts its stronger summary and does not repair that conclusion. Numeric transcription is mostly sound; scientific population attribution is the central error. The synthesis should not be treated as an answer to the clinical question.

The third R4’s rendered request measured **12,910 prompt + 4,096 reserve = 17,006**, exceeding **16,384**. It was recorded in the independent execution log as `model_request_blocked`; no model call or usage was charged. Its 12-entry search history includes repeated profile configs, original/retained/discarded concepts, request receipts, disposition maps, UUIDs and timestamps. That history occupies roughly **21,229 characters** in the stored context representation, versus **32,175** for all context, before prompt formatting. This is a concrete cause to investigate: R4 receives far more retrieval bookkeeping than the architecture’s compact-history intent, while R5 capacity measures a different request. No history pruning, budget increase, prompt revision or resumption after this deterministic block was attempted.

### Alternative: medical-query-comparison-20261030

This run committed **five direct / five total successful actions**: one R1, two R2 and two R3. It stopped on its first S1 after **119.165 s**; a single normal S1 retry, with identical model settings and the same original 900-second deadline, also failed. Final totals are **seven controller attempts, five model calls, zero completed rounds**. Active execution was **141.247 s**; elapsed time from the original start through the bounded retry was **215.856 s**, including **74.609 s** of inspection/setup between executions. Both elapsed definitions are reported; this partial run cannot be compared as equal work with the baseline or previous 40-action benchmark.

Its only R1 list is identical to the baseline’s first list. PubMed’s two-concept query returned the same two abstracts as the baseline’s three-concept query, so no observed first-round evidence gain can be attributed to reducing PubMed to two. Europe PMC’s plain-three query returned two unique abstracts instead of zero: the same progression cohort and a three-case cryptococcosis report (PMID [42469902](https://pubmed.ncbi.nlm.nih.gov/42469902/)). This comparison holds R1 concepts fixed, making the query-rule change a plausible retrieval explanation; provider ranking/index changes remain uncontrolled. It is a local retrieval gain, not demonstrated end-to-end reasoning improvement.

The two Europe PMC abstracts remain **pending R3**. They are retained as evidence but contributed no findings or glossary terms. The cryptococcosis source reports emerging/growing nodules in patients with previous malignancy, illustrating an infectious mimic, but supplies no VDT, spiculation-specific frequency, or infection-versus-cancer probability. Neither the controlled probes nor this pending source may be credited as successful Mira extraction. Crossref/Wikipedia were not reached, and no R4, S2 or R5 ran.

R3 created `r1` and `r2` from the PubMed sources, retaining numerical values and source IDs. An important new error appears in `r1`’s qualification: it describes the **≤400-day group** as significantly longer than ~28 days. That group includes 28 days; the upper threshold does not imply all included growth is slower. `r2`’s summary explicitly infers that rapid growth and spiculation favor malignancy over benign infection from an ALI study confined to resected NSCLC, even though its own derived question correctly acknowledges the missing comparison. This population error occurs before synthesis and can contaminate S1.

First S1: response `finish_reason=length`, exactly **4,096 completion tokens**, an unclosed JSON response containing a long argumentative reason and just `r2` in `memory_ids`. It alternates between obeying the two-memory constraint, adding a weakly related source and returning `no_candidate`, rather than making one valid selection. Thinking was disabled in the actual request; deliberation appeared inside ordinary output content. Python rejected the incomplete response without a synthesis, consumption or source-cursor change.

One ordinary controller retry was reasonable because the first rejection was recoverable and no partial selection had committed. Its response finished normally (`stop`, **1,100 completion tokens**) but again selected only `r2`; validation rejected it with **“S1 requires at least two distinct eligible memory IDs.”** Its reason includes contradictory proposed corrections and an eventual verbal `no_candidate` while the actual JSON disposition remains `select`. This is a distinct schema/selection failure, **not a second truncation**. No further identical-call loop, interruption acknowledgement, prompt adjustment or higher output allowance was used.

S1’s reasons repeat the same unsupported malignancy inference and the slow-only misreading of the radiomics population seen in the baseline. Its priority over pending R3 extraction means the newly retrieved infectious evidence never reaches the memory catalogue before the repeated selection failure. This is a concrete scientific-progress/scheduling limitation for review, not an externally unavailable provider. The optional third fresh run was omitted because the prerequisite that the first two complete successfully was not met; a third identical run would not provide a clean successful reproducibility comparison.

### Glossary, provenance and numeric fidelity

Baseline: **six** candidate terms (SSNs, VDT, Radiomics, ALI, Cox regression, MPA); alternative: **four** (SSNs, VDT, Radiomics, ALI). Only **VDT** was subsequently registered as used in either run. It was already present in the first R1, before glossary admission, so this is not evidence of useful glossary-driven direction expansion. Unsupported proposed standalone spiculation labels were independently rejected by the existing exact-passage validator; substantive findings were unaffected. No source-defined glossary definition was accepted and no glossary relationship established an etiologic finding.

All supplied inequalities and numerical values discussed above were checked against the exact R3 inputs, and all source IDs resolve to retained payloads and provider evidence. No full text, figures or new clinical recommendations were supplied to Mira. `content_kind=abstract` means an adapter-provided abstract, not a full publication. Metadata-only results cannot support study findings. Structural validation accepts some scientifically unsupported summaries, so a valid memory/synthesis must still be audited against study population and source wording.


## Evidence coverage and interpretation

| Evidence need | No-OpenAlex baseline | Alternative | Controlled probes / interpretation |
| --- | --- | --- | --- |
| Malignant VDT distributions | ≤400-day growth grouping; ≤310-day MPA threshold; no distribution | Same growth grouping; no distribution | Cancer-only top PubMed hits; two and three terms return identical material |
| Rapid malignant subtypes | MPA association retained; no ~28-day subtype observation | MPA not retrieved; no subtype rates | MPA cutoff is not a subtype growth distribution |
| Infection / inflammation growth | Aspergillosis title only, no findings | Three growing cryptococcosis cases retrieved, pending R3 | Same case abstract; no VDT or comparative probability |
| Spiculated margins | ALI/progression associations; source-population caveats needed | ALI association extracted; summary overstates etiology | Measurements and cancer aggressiveness, not a likelihood ratio for the question |
| CT measurement uncertainty | No CT repeatability evidence retrieved | No CT repeatability evidence retrieved | Useful phantom and reader-variability abstracts found only in separate probes |
| Quantitative infection-versus-malignancy comparison | None | None | None |

The baseline makes incremental progress in collecting numerical morphology/aggressiveness findings and an MPA threshold, but it does not answer the comparative question. The alternative collects an infectious mimic that Mira has not yet extracted. Neither provides a defensible direction or strength of diagnostic preference. In particular, a cancer-only odds ratio for ALI is not an odds ratio for cancer versus infection. No posterior probability, likelihood ratio or clinical recommendation can be derived from the supplied material. The unsupported model conclusions are errors to investigate, not scientific results.


## Recommendations and user-controlled planning

1. Keep the temporary suspension for predefined strategies; restore OpenAlex only through a reviewed configuration change when its availability is suitable. Existing deferred experiments retain their original work and server retry times; none was resumed here.
2. Continue testing **PubMed max_terms 2 versus 3**, not 4 for this concept bundle. Two preserves one extra match, but identical top-two records provide no demonstrated evidence-quality advantage over three. Keep the committed default pending stronger repeated evidence.
3. Continue **Europe PMC plain-text max_terms 3** as an experimental arm: it avoids the first-round empty exact phrase and returns an infectious lead. Also retain **phrase_and max_terms 2 or 3** as a precision/measurement-evidence arm: both found useful CT measurement papers with shorter terminology. Do not universally declare plain text better or permanently adopt either on these incomplete runs. Keep all existing timing/retry policies.
4. Investigate a bounded deterministic **R4 search-history projection** that retains actual query/status/submission/count semantics while excluding repeated transport/config bookkeeping from the model input. The observed 17,006-token request fails despite low R5 capacity. This aligns with the existing compact-history intent, but no implementation or prompt change was included in this configuration/report task.
5. Review **R3/S1/S2 population fidelity**, grouped morphology attribution, ≤ versus > interpretation and misleading summary propagation. A known-cancer aggressiveness association cannot decide infection versus cancer. Prompt wording remains user-controlled; no independent prompt rewrite is proposed as already approved.
6. Review recoverable **S1 rejection scheduling** and the progress consequence of blocking pending R3 on repeated invalid selections. The first error consumed the output budget; the second returned a prohibited single-memory selection. Increasing output allowance is not supported by the second failure. Any new fallback/skip policy needs review rather than an undocumented experiment-specific bypass.
7. Pursue actual evidence gaps—malignant VDT distributions, fast malignant histologies, infectious growth and CT repeatability—with approved research-direction work. R1 currently changes prefixes/terminology but does not reliably diversify underlying questions. The proposed 0–6-new-concepts revision remains unapproved and untouched.

For `futureWork.md`’s separate user-controlled update: scientific-text sanitization and the named-profile/durable retrieval implementation were completed in the earlier commits; this task adds live 2/3/4 concept comparisons, exact-phrase restriction evidence and two longer medical attempts. R1 novelty/diversification, S1 behavior, source-fidelity improvements and deeper retrieval remain outstanding. This investigation does **not** complete scientific-performance validation or establish an optimal permanent profile. `futureWork.md` was not edited.

## Integrity and local artifacts

All **5,851 pre-existing research files**, **8 prior execution logs** and protected question/configuration/document/prompt bytes retain their hashes. Read-only corpus/state/glossary validation passed for **39 initialized corpora**; every inspected journal is committed and no uncertain model/provider submission remains in the new experiments. Old experiments were inspected without controller steps. In particular, `memory/research/query-profile-medical-20261030` retains its five-provider snapshot, original OpenAlex query, one attempt and long retry timestamp unchanged.

All **21 dispatched model request snapshots** (16 baseline, five alternative) match the actual serialized messages through the read-only Inspector verification path. Every R3 source exactly equals its retained payload; every compiled plan and actual query parameter matches the snapshotted profile; logged API keys are absent. The **12 prior-outcome entries** supplied across baseline R1s match independent committed evidence. Both invalid S1 responses, the blocked R4 rendered request, accepted memories and pending R3 sources remain available for review. Full model usage includes rejected responses; predispatch blocks have no usage.

Local-only artifacts (not staged or pushed):

- Experiment: `/home/eric/Dev/Mira/memory/research/medical-no-openalex-baseline-20261030`.
- initialize_log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_055429_medical-no-openalex-baseline-20261030_9702da4e2e6b.jsonl`.
- run_log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_055429_medical-no-openalex-baseline-20261030_ebc9c5e63750.jsonl`.
- In that experiment: `research/state.json`, `research/results/`, `retrieved/`, `interactions/`, `retrieval_calls/`, `memories/`, `glossary/`, `journal/`, `supervisor.jsonl`, `server-properties.json`, `validation.json`, `validation-analysis.json` and `preservation-before.json`.
- Experiment: `/home/eric/Dev/Mira/memory/research/medical-query-comparison-20261030`.
- initialize_log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_055755_medical-query-comparison-20261030_8d187e8e9a5e.jsonl`.
- run_log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_055755_medical-query-comparison-20261030_00ade3b706e7.jsonl`.
- Recovery execution log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_060109_medical-query-comparison-20261030_a8b7e90d6187.jsonl`.
- In that experiment: `research/state.json`, `research/results/`, `retrieved/`, `interactions/`, `retrieval_calls/`, `memories/`, `glossary/`, `journal/`, `supervisor.jsonl`, `server-properties.json`, `validation.json`, `validation-analysis.json` and `preservation-before.json`.
- Controlled probes, temporary registry, supervisor/analysis/report scripts, both successful full-suite logs, initial failed-test log, preservation inventory and all-corpus integrity results: `/home/eric/Dev/Mira/memory/benchmarks/openalex-suspension-20261030/`.

The local model/embedding services were borrowed and left running. Only the strategy configuration, necessary tests and requested Markdown reports are committed. No branches, resets, discarded local work or force-push were used. The report commit SHA is supplied after committing rather than embedded self-referentially here; final `main` synchronization and uncommitted-file status are verified after push and reported in chat.

## Controlled-query title and availability catalogue

| Identifier | Publication title | Supplied evidence |
| --- | --- | --- |
| pmid:39807982 | CT Predictors of Angiolymphatic Invasion in Non-Small Cell Lung Cancer 30 mm or Smaller. | abstract; not character-truncated |
| pmid:41869733 | Prediction of high-risk factor in early-stage lung cancer: micropapillary adenocarcinoma. | abstract; not character-truncated |
| europe_pmc:MED:37998584 | Detectability and Volumetric Accuracy of Pulmonary Nodules in Low-Dose Photon-Counting Detector Computed Tomography: An Anthropomorphic Phantom Study. | abstract; not character-truncated |
| europe_pmc:MED:39728910 | Interobserver Variability in Manual Versus Semi-Automatic CT Assessments of Small Lung Nodule Diameter and Volume. | abstract; not character-truncated |
| europe_pmc:MED:28972803 | Influence of lung nodule margin on volume- and diameter-based reader variability in CT lung cancer screening. | abstract; not character-truncated |
| europe_pmc:MED:42780873 | Clinical symptoms and prognosis of patients with pulmonary nodules: a real-world cohort study. | abstract; not character-truncated |
| europe_pmc:MED:42625155 | Assessment of risk factors in persistent subsolid pulmonary nodules based on CT dynamic follow-up. | abstract; not character-truncated |
| europe_pmc:MED:42469902 | Pulmonary cryptococcosis showing a solitary nodule in patients with previous malignancy. | abstract; not character-truncated |
| doi:10.1016/s0169-5002(85)80158-6 | Biochemical measure of the volume doubling time of human pulmonary neoplasms | bibliographic_metadata; not character-truncated |
| doi:10.1016/j.chest.2022.08.414 | SPICULATED LUNG NODULE: AN UNUSUAL PRESENTATION OF CHRONIC PULMONARY ASPERGILLOSIS | bibliographic_metadata; not character-truncated |

“Not character-truncated” describes the adapter limit; it does not verify full publication completeness. Titles/abstracts can be relevant to a subquestion while failing to answer the comparative clinical question. PubMed and Europe PMC are overlapping indexes; their returned records are not independent studies merely because the providers differ.

## Exact new research-query audit

### medical-no-openalex-baseline-20261030

| Provider | Query | Status | Returned / unique / duplicate | Retained source IDs |
| --- | --- | --- | --- | --- |
| pubmed | `(spiculated pulmonary nodule) AND (volume doubling time) AND (lung malignancy)` | ok | 2 / 2 / 0 | pmid:37936095; pmid:39807982 |
| europe_pmc | `"spiculated pulmonary nodule" AND "volume doubling time" AND "lung malignancy"` | empty | 0 / 0 / 0 | none |
| crossref | `spiculated pulmonary nodule volume doubling time lung malignancy pulmonary infection` | ok | 2 / 2 / 0 | doi:10.1016/j.chest.2022.08.414; doi:10.1016/s0169-5002(85)80158-6 |
| wikipedia | `spiculated pulmonary nodule volume doubling time lung malignancy` | empty | 0 / 0 / 0 | none |
| pubmed | `(volume doubling time) AND (spiculated nodule) AND (pulmonary infection)` | ok | 1 / 1 / 0 | pmid:42780873 |
| europe_pmc | `"volume doubling time" AND "spiculated nodule" AND "pulmonary infection"` | empty | 0 / 0 / 0 | none |
| crossref | `volume doubling time spiculated nodule pulmonary infection lung neoplasm` | ok | 2 / 0 / 2 | none |
| wikipedia | `volume doubling time spiculated nodule pulmonary infection` | empty | 0 / 0 / 0 | none |
| pubmed | `(volume doubling time) AND (spiculated nodule) AND (lung neoplasm)` | ok | 2 / 1 / 1 | pmid:41869733 |
| europe_pmc | `"volume doubling time" AND "spiculated nodule" AND "lung neoplasm"` | empty | 0 / 0 / 0 | none |
| crossref | `volume doubling time spiculated nodule lung neoplasm pulmonary infection` | ok | 2 / 0 / 2 | none |
| wikipedia | `volume doubling time spiculated nodule lung neoplasm` | empty | 0 / 0 / 0 | none |

### medical-query-comparison-20261030

| Provider | Query | Status | Returned / unique / duplicate | Retained source IDs |
| --- | --- | --- | --- | --- |
| pubmed | `(spiculated pulmonary nodule) AND (volume doubling time)` | ok | 2 / 2 / 0 | pmid:37936095; pmid:39807982 |
| europe_pmc | `spiculated pulmonary nodule volume doubling time lung malignancy` | ok | 2 / 2 / 0 | europe_pmc:MED:42780873; europe_pmc:MED:42469902 |

