# Medical retrieval-repair experiment — 31 October 2026

## Executive summary

**The repairs improved acquisition and scheduling, but Mira still did not answer the four-week-growth question.** All **443 automated tests passed**. The fresh experiment ran for **1,235.126 seconds (20 minutes 35 seconds)** of its 2,400-second allowance, then stopped on a genuine **S1 context-budget block before generation**. It was not a completed 40-minute run.

The run produced **16 research memories, no synthesis memories, 32 glossary entries and six MeSH scope notes**. It processed 72 abstracts and nine metadata-only records, compared with seven abstracts among 30 processed sources in the stopped experiment. All 18 dispatched S1 calls used distinct scientific catalogue/scope fingerprints. Actual enriched definitions reached **37 of 39 R1 requests**. These are operational improvements, not proof of an improved scientific answer.

Some retrieved studies inform components of the question: baseline spiculation risk, growth categories and static imaging differences between benign and malignant lesions. **None of the supplied sources directly estimated how strongly approximately 28-day volume doubling distinguishes infection from malignancy.** Extraction and downstream reasoning also introduced several concrete errors, including an incorrect interpretation of a growth-time inequality, overstated diagnostic certainty, a misplaced numerical uncertainty and unsupported equation attribution. R5 imported the unresolved infection-favouring premise into child questions.

The final S1 request required **12,341 prompt tokens + 4,096 reserved output tokens = 16,437**, exceeding the 16,384-token window by **53 tokens**. No model call was dispatched for it, no rejected model response was retried, and no state or budget was changed to bypass it. The corpus, logs and glossaries remain local and recovery-safe.

Exact research question:

> Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

## Repairs and pre-experiment validation

Implementation commit: **`921f079`**. Separate regression-test commit: **`eb4534f`**. Both were pushed before initialization; the working tree was clean and synchronized with `origin/main`.

| Repair | Result and scope |
| --- | --- |
| Experimental queries | Added opt-in `pubmed_or` and `phrase_or`. They reuse existing PubMed term handling and quoted-phrase escaping, respectively. Ordered provider prefixes, exact compiled-query identity, duplicate checks, pacing and restart semantics are retained. Production profiles and strategies are unchanged. |
| Repeated S1 | Every valid `no_candidate` now persists the existing catalogue fingerprint, including during living research. An unchanged eligible scientific catalogue and question scope do not trigger another S1. New eligible memory versions or relevant question changes reopen selection. The fingerprint format and rejected S1/S2 safeguards are preserved. |
| Terminology failures | Temporary failures use a 900-second cooldown in the response cache and canonical/backlog eligibility. Unattempted terms remain eligible; confirmed results retain 24-hour caching. Due failed lookups on source-defined terms also reopen without losing definitions. Index rebuilding and recovery preserve the gate. |
| R3 definitions | Added exactly the requested verbatim-definition instruction within the terminology section. The rest of R3 and its source-grounding validator are unchanged. |

The full repository runner was:

```bash
PYTHONPATH=src python3 scripts/run_tests.py \
  --report log/medical-retrieval-repair-20261031/tests-frozen.md
```

**443 tests passed, zero failures/errors/skips, in 58.611 seconds.** This includes 26 additional tests, with coverage for OR escaping and retrieval fixtures, ordered prefixes, duplicate/restart/journal behavior, living-node S1 guards, changed memory/question scope, rejected outputs, pending R3 scheduling, cooldown boundaries, legacy caches, source-defined retries, index rebuilding, provenance and crash recovery. Existing R1/R4 tests passed. Tests using transport fixtures do not establish clinical correctness or live-service reliability. Existing non-failing SQLite `ResourceWarning` messages remain.

No architecture, futureWork, R1/R4/R5/S1/S2 prompt, scientific memory schema or research-capacity policy was changed. No stagnation-based exhaustion or corrective LLM retry was introduced. Production R3 lookup defaults remain two terms, three seconds per request and eight seconds per action. Recommended documentation changes are recorded separately in local `log/medical-retrieval-repair-20261031/documentation-proposals.md`; `architecture.md` and `futureWork.md` were preserved.

### Bounded retrieval comparison

Before resetting the corpus, a separate read-only comparison reused the first two saved R1 selections from the stopped experiment. It compared production three-term AND, controlled two-term AND and experimental two-term OR for both providers, with two results per search. **Twelve logical searches / 16 HTTP requests completed in 18.818 seconds**, without rate limits or retries. No real model or active research action was invoked.

| Configuration | Returned records | Abstracts | Manually component-relevant abstracts | Direct four-week diagnostic-strength evidence |
| --- | ---: | ---: | ---: | ---: |
| Production three-term AND | 2 | 0 | 0 | 0 |
| Controlled two-term AND | 6 | 6 | 2 | 0 |
| Experimental two-term OR | 8 | 8 | 3 | 0 |

The controlled AND result shows that **shortening the prefix itself mattered**. OR also retrieved off-organ material, including hepatic pseudotumor and adrenal carcinoma. The relevance judgments concern supplied abstracts, not search hit counts or unseen full texts; this small comparison is not a causal effectiveness trial. Exact queries, replies, abstracts and review notes are preserved under local `retrieval-comparison/`.

### Bounded live MeSH smoke

Two previously successful names were tested in disposable fixture corpora, using existing retrieved source passages, one term per action, ten-second requests and a 23-second action budget:

| Term | API calls | Lookup/admission action time | Admitted authority description |
| --- | ---: | ---: | --- |
| Organizing pneumonia | 2 | 9.928 s | MeSH M000751452, 335-character scope note |
| Cryptogenic organizing pneumonia | 2 | 9.613 s | MeSH M0027812, 462-character scope note |

Both notes were admitted with full authority provenance; immediate cache reuse made zero additional API calls. No real LLM call or active-corpus write occurred. Pre-network fixture setup errors are retained separately and are not counted as terminology API failures. Successful smoke admission validates the enrichment boundary, not whether Qwen follows the new R3 instruction.

## Fresh experiment configuration and supervision

Experiment: **`medical-retrieval-repair-20261031`**. The approved `--new-experiment` reset ran only after clean-tree, idle-lock, model-health, submission and canonical recovery checks passed. It replaced the previous generated active corpus while preserving reports, private inputs and logs. The recovery-blocked legacy `memory/research/dropout-sustained/` was not deleted. No per-experiment memory archive was created.

The temporary registry retained strategy ID **`medical`**, so medical terminology enrichment stayed enabled, but selected only:

1. PubMed, `experimental_pubmed_or2`, compiler `pubmed_or`, maximum two concepts.
2. Europe PMC, `experimental_phrase_or2`, compiler `phrase_or`, maximum two concepts.

Exact registries are saved locally as `log/medical-retrieval-repair-20261031/strategies.json` and `query-profiles.json`, and snapshotted at initialization. R1 received `term_limit=2`; one shared ordered selection served each provider round. Crossref and Wikipedia were not used. Repository production defaults were untouched.

The existing **Qwen3.6-35B-A3B Q4_K_M** server was healthy with a **16,384-token request context**. Every actual generation used temperature 0, thinking disabled, JSON-object output and 4,096 maximum output tokens. Output reserve was 4,096; normal research capacity remained 12,288. Each provider returned at most two results. Experimental terminology settings were explicitly **one term / ten-second request timeout / 23-second total action budget**, with the existing six-request ceiling. The shared terminology cache was preserved rather than cleared; the smoke cache was separate.

Research ran **10:55:50.061351–11:16:25.187271 UTC**, or **21:55:50–22:16:25 AEDT**. Initialization, repairs, tests and final analysis are excluded. The sequential `Research.step()` supervisor had no controller-action ceiling and a 2,400-second allowance. Its 150-second safe-dispatch reserve was not the stop reason.

The supervisor checks `log/medical-retrieval-repair-20261031/STOP` between actions and while waiting for provider eligibility. A request finishes before stopping; the file does not alter canonical research state. It was not needed in this run. Normal shutdown logged the context block and reconciled **all 251 canonical controller events with 251 supervisor step records**, with no missing records. No in-flight request was interrupted, uncertain submission acknowledged, or model-generated content repaired. Source, prompt and registry hashes stayed frozen throughout execution.

## Action, token and retrieval statistics

Initialization is excluded. The one rejected controller attempt was the pre-dispatch S1 budget block, not an invalid model response.

| Action | Attempted | Committed | Actual LLM calls | Total generation tokens |
| --- | ---: | ---: | ---: | ---: |
| R1 | 39 | 39 | 39 | 107,873 |
| R2 | 71 | 71 | 0 | 0 |
| R3 | 81 | 81 | 81 | 207,587 |
| R4 | 37 | 37 | 37 | 92,044 |
| S1 | 19 | 18 | 18 | 118,452 |
| S2 | 0 | 0 | 0 | 0 |
| R5 | 4 | 4 | 4 | 8,941 |
| **Total** | **251** | **250** | **179** | **534,897** |

Usage was **498,889 prompt + 36,008 completion tokens**. Saved generation request/response intervals sum to **770.712 seconds**. All 179 responses finished with `stop`; none was retried. Native template/tokenizer requests are not generation calls. The largest dispatched prompt was 11,537 tokens. State records 228 research cycles, 18 synthesis cycles and four branching cycles.

| Provider | R2 actions | Actual submissions / HTTP requests | Outcomes | Returned / identity-unique / duplicates |
| --- | ---: | ---: | --- | ---: |
| PubMed | 37 | 35 / 70 | 33 successful; two failed; two pacing deferrals without submission | 66 / 40 / 26 |
| Europe PMC | 34 | 34 / 34 | 28 successful; six empty | 56 / 41 / 15 |
| **Total** | **71** | **69 / 104** | **61 successful, six empty, two failed; two deferrals** | **122 / 81 / 41** |

The two PubMed failures were recorded as response-validation/unavailable-provider failures. They were not uncertain submissions or observed HTTP 429 events; the retained generic error does not establish their precise remote cause. Provider pacing and deferred state were handled normally, without busy-waiting or bypassing cooldowns.

All **81 identity-unique sources received exactly one R3 extraction**; none remains pending. They comprised **72 abstracts and nine metadata-only records**, with five supplied sources flagged as truncated. Sixteen extractions created a research memory; 65 were empty. All nonempty accepted extractions were saved. Each R2 handled one provider search or its deferral, and each R3 handled one source.

All **69 actually submitted compiled queries were distinct**, both within and across nodes. R1 detected eight repeated effective queries across four entirely repeated plans, blocking those plans before R2. No R2 duplicate-skip event was needed. Exact identity did not eliminate semantic repetition: two provider query pairs repeated the same unordered concepts across q2/q5 with reversed OR order.

### Scientific relevance of supplied sources

The following is a manual interpretation against the **original root question**, not an independently blinded relevance benchmark or a count of independent studies:

| Source category | Processed records | Memory-creating extractions |
| --- | ---: | ---: |
| Abstracts informing a component of the question | 13 | 6 |
| Adjacent abstracts | 35 | 9 |
| Off-question abstracts | 24 | 1 |
| Metadata only | 9 | 0 |
| **Total** | **81** | **16** |

The 13 component-relevant records include reviews and an apparent preprint/publication pair: **PPR701453**, DOI `10.21203/rs.3.rs-3199652/v1`, and **PMID 37936095**, DOI `10.1186/s12880-023-01143-x`, share the 273-nodule/857-scan population and growth results. They required two R3 actions but produced one memory, not an independent replication. A descriptor/identity audit found no demonstrated metadata-to-abstract content upgrade discarded among these duplicate records; it does not assess unseen full texts.

## R1 planning and retained candidates

R1 made one call per node/round and selected at most two concepts. There were **63 retained per-node unverified candidates**, with provenance and actual query-use records; **17 remain unused**. These are not 63 globally novel scientific discoveries. Candidate/history reuse was observed alongside new selections.

No R1 component was rejected in this live run, so preservation of independently valid components remains regression-tested rather than newly exercised here. Repeated plans produced durable search blocking rather than fabricated searches or forced answers. Some exact-new queries still recycled disease/growth phrases, changed order, or drifted into radiomics and PET/CT. Broad OR increased recall while also admitting off-organ material; syntax acceptance did not establish a useful scientific plan.

Definitions were genuinely present in later R1 requests, but lexical reuse is not causal proof of benefit. Several terms had already been selected before their descriptions became available. Branch questions also introduced unsupported premises, so improved vocabulary access did not ensure sound planning.

## Scientific findings and limitations

The corpus contains **36 finding units, nine derived questions and one equation** across 16 research memories. Findings below are author-reported material from supplied abstracts/reviews, not independently verified clinical conclusions. No study supplies the requested four-week infection-versus-malignancy likelihood ratio or probability.

| Memory | Source and study population/design | Actual contribution | Limit for the selected four-week question |
| --- | --- | --- | --- |
| r1 | [PMID 24004118](https://pubmed.ncbi.nlm.nih.gov/24004118/), DOI `10.1056/NEJMoa1214726`; prospective baseline screening model, PanCan 1,871 participants/7,008 nodules and BCCA 1,090/5,021. | Spiculation included among malignancy predictors; multivariable model AUC >0.90. | No dynamic growth comparison or spiculation-specific effect estimate in the supplied abstract. |
| r2 | [PMID 41321347](https://europepmc.org/article/MED/41321347), DOI `10.1002/rcr2.70416`; one 53-year-old man. | Pathologically confirmed LIP appeared as a solitary spiculated nodule. | Benign mimic, without doubling time or diagnostic probabilities; not proof of infection. |
| r3 | [PMID 37936095](https://europepmc.org/article/MED/37936095), DOI `10.1186/s12880-023-01143-x`; retrospective 273 growing subsolid nodules/857 scans. | Growth-category prediction incorporating spiculation; VDT groups ≤400 and >400 days. | No 28-day subgroup or etiologic comparison supplied; retained category/cutoff reasoning error. |
| r4 | [PMID 42604996](https://europepmc.org/article/MED/42604996), DOI `10.1097/cm9.0000000000004247`; 268 COP patients at two hospitals, prospective follow-up. | Relapse in 56/268 and typical CT appearances. | Relapse/prognosis rather than growth-based diagnostic discrimination; one qualification incorrectly says single-center. |
| r5 | [PMID 42445454](https://europepmc.org/article/MED/42445454), DOI `10.1002/ccr3.73140`; brief clinical-report abstract, no cohort supplied. | Reversed-halo appearance can occur with infection or infarction. | Different imaging feature; no growth data. |
| r6 | [PMID 12740472](https://pubmed.ncbi.nlm.nih.gov/12740472/), DOI `10.1148/rg.233025073`; review. | Inflammatory pseudotumor can mimic malignancy. | No quantitative growth or diagnostic discrimination. |
| r7 | [PMID 42694241](https://europepmc.org/article/MED/42694241), DOI `10.3389/fmed.2026.1873013`; one 55-year-old man with a suspected inflammatory mass. | Size reduction over 5–10 months; spontaneous regression not excluded. | Provisional diagnosis, no four-week doubling; summary adds unsupported spiculation and overstates diagnostic certainty. |
| r8 | [PMID 42927246](https://europepmc.org/article/MED/42927246), DOI `10.7759/cureus.116813`; one patient with HIV and CNS/orbital IPT. | Two-month enlargement then stability. | Nonpulmonary lesions, no volumetric measurements. |
| r9 | [PMID 30474465](https://pubmed.ncbi.nlm.nih.gov/30474465/), DOI `10.1080/14397595.2018.1548089`; IgG4-related respiratory disease review. | Intrathoracic disease can resemble malignancy. | No quantitative growth; derived question imports unsupported infection-growth premise. |
| ra | [PMID 42787882](https://europepmc.org/article/MED/42787882), DOI `10.1055/s-0046-1827247`; retrospective 184 lung-cancer patients. | Inflammatory blood indices have little association with stage/SUVmax; weak NLR/stage-IV association retained. | No benign comparator, target growth rate or spiculation analysis. |
| rb | [PMID 41432561](https://pubmed.ncbi.nlm.nih.gov/41432561/), DOI `10.1148/radiol.251524`; 1,683 adenocarcinoma patients/2,125 nonsolid nodules. | Spiculation OR 1.72 for invasiveness; whole-model C-index 0.92. | Within-cancer invasiveness, not cancer versus infection; no growth kinetics. |
| rc | [PMID 42865833](https://europepmc.org/article/MED/42865833), DOI `10.21037/jtd-2026-0786`; retrospective 68 PSP patients, 17 with serial CT. | Six of 17 in a VDT <600-day category. | No 28-day subgroup or etiologic comparator; passage truncated and equation source attribution unsupported. |
| rd | [PMID 18609677](https://pubmed.ncbi.nlm.nih.gov/18609677/), DOI `10.3748/wjg.14.3948`; clinicopathologic review of IgG4-related systemic disease. | Lung inflammatory disease may mimic malignancy. | No quantitative imaging accuracy or growth data. |
| re | [PMID 21696561](https://pubmed.ncbi.nlm.nih.gov/21696561/), DOI `10.1111/j.1754-9485.2011.02265.x`; retrospective 105 malignant solid nodules and 48 malignant fGGOs. | Spiculation frequencies 57% versus 40%, plus other static morphologic differences. | All lesions malignant; no benign/infectious comparator or growth analysis. |
| rf | [PMID 32631330](https://pubmed.ncbi.nlm.nih.gov/32631330/), DOI `10.1186/s12880-020-00475-2`; retrospective 21 PIPT and 21 peripheral lung-cancer patients. | CT texture features discriminate these groups with moderate AUCs around 0.717–0.748. | Relevant static differential, but no four-week kinetics or specified spiculation subtypes; one saved AUC uncertainty is misassigned. |
| rg | [PMID 29098026](https://europepmc.org/article/MED/29098026), DOI `10.3892/ol.2017.6840`; 55 histologically classified pulmonary lesions, 24 malignant/31 benign. | FDG/FLT uptake mismatch in 19/24 versus 12/31, respectively. | No rapid-growth or spiculation subgroup, no specified inflammatory-pseudotumor subgroup. |

The baseline screening model, within-adenocarcinoma spiculation estimate and static CT/PET comparisons offer more substantive component evidence than metadata titles. They do not combine into a growth-conditioned diagnostic probability: populations, endpoints and imaging features differ, and the necessary approximately 28-day etiologic comparison is absent. The LIP case also appeared in the stopped experiment under the same DOI, so not every fresh memory represents new knowledge relative to that benchmark.

### Concrete extraction and reasoning errors

- **Growth-range error:** r3#f1 treats VDT ≤400 days as slower than four weeks. That interval includes 28 days. S1 at cycle 25 and R4 at cycle 26 repeat the mistake; one S1 description also reduces the source to a >400-day group although both groups were supplied. Lack of a specific 28-day comparison supports caution, not the incorrect inequality reasoning.
- **Study design:** r4#f2 calls the COP cohort single-center, while the supplied source explicitly names two hospitals.
- **Morphology and certainty:** r7's summary adds spiculation to a source describing an irregular/lobulated mass and upgrades suspected inflammatory pseudotumor to a diagnosis, although PIMT was not excluded. Regression during treatment does not establish treatment efficacy; spontaneous regression remained possible.
- **Unsupported equation attribution:** rc#e1 marks `VDT = t·ln(2)/ln(V2/V1)` as source-origin. The supplied truncated abstract only names the modified Schwartz formula; it provides neither that expression nor its variable definitions. Familiarity with a formula is not evidence that it was present in the supplied source.
- **Numerical transcription:** rf#f3 attaches ±0.075 to AUC 0.748; the source pairs **0.748±0.038** and **0.731±0.075** separately.
- **Imported premise:** r9's derived question and R5 child questions assume four-week growth is classically/typically infection-favouring. The saved evidence does not establish that premise. This is an unsupported assertion within this run, distinct from a claim that it is externally false in all clinical settings.

These records were not edited. Structural validation and successful commitment do not validate their scientific truth. The errors limit confidence in downstream reasoning even where an `unresolved` disposition remains appropriate.

## Glossary enrichment

R3 proposed **64 terms**; **35 proposals were admitted**, including three merges, leaving **32 canonical entries**. Twenty-nine proposals were rejected/ignored: 11 passages absent from supplied text, six terms absent from the quoted passage, 11 unsupported relationships and one unsupported alias. Optional rejection did not discard valid scientific extraction.

All 64 model-proposed definitions were null or missing. Thus the exact new instruction produced **no research-source verbatim definitions in this run**. This alone does not prove that every source offered a missed definition; that requires passage-level review. The six obtained definitions are authority scope notes. The stored status label `source_defined` covers those authority-defined entries and must not be read as six research-derived definitions.

| Term and entry | MeSH concept | Scope note exposures in actual R1 requests |
| --- | --- | ---: |
| Organizing pneumonia, g6 | [M000751452](https://id.nlm.nih.gov/mesh/M000751452) | 8 |
| Radiomics, g12 | [M000763396](https://id.nlm.nih.gov/mesh/M000763396) | 14 |
| Cryptogenic organizing pneumonia, g13 | [M0027812](https://id.nlm.nih.gov/mesh/M0027812) | 8 |
| Pulmonary infarction, g16 | [M0018127](https://id.nlm.nih.gov/mesh/M0018127) | 30 |
| Positron Emission Tomography-Computed Tomography, g21 | [M000616299](https://id.nlm.nih.gov/mesh/M000616299) | 6 |
| Pulmonary inflammatory pseudotumor, g31 | [M0025468](https://id.nlm.nih.gov/mesh/M0025468), preferred name Plasma Cell Granuloma, Pulmonary | 2 |

Eight entries matched eight MeSH concepts; **Relapse** and general **Inflammatory pseudotumor** matched without descriptions. General and pulmonary-specific pseudotumor concepts remain separate. Full canonical scope notes retain authority URLs, preferred/matched names, term/descriptor IDs, aliases, retrieval times and qualifications. These are NLM terminology descriptions, not independent scientific evidence or diagnostic validation. MedGen was not enabled.

There were **45 terminology HTTP requests across 33 R3 actions**, one response-cache hit, zero concept-cache hits and **189.998 seconds** of total lookup-action time; the longest action was **10.466 seconds**. This includes pacing/parsing/cache work, not separately instrumented HTTP latency. The cache hit reused a pre-existing negative result. Counts exclude the preparatory smoke tests.

Saved outcomes were **22 not found, eight matched, four errors and 16 not attempted**; latest record states were 22 not found, eight matched and two errors. No live timeout, unavailable or ambiguous outcome occurred. “Not found” means no exact supported match, not absence of the concept from every terminology system.

The two error terms were **Reverse halo sign** and **Reversed halo sign**. Each attempt made two requests then failed strict MeSH-link validation; the invalid RDF identifier was not retained, so the precise ontology mismatch remains unresolved. They retried after **967.082** and **909.109 seconds**, respectively, respecting the 900-second cooldown. No unsupported definition was admitted. Exact boundary behavior, unavailable-provider handling, cache loss, index rebuilding and crash recovery were covered by fixtures; no live crash was induced.

The **132 cooldown exclusions across 73 R3 actions** are repeated excluded-entry observations, not 132 unique terms or avoided HTTP requests. Unattempted entries continued to be processed.

Actual serialized R1 prompts confirm **68 definition-entry exposures across 37/39 requests**. Organizing-pneumonia and COP notes were truncated to 240 characters on all eight exposures each, with explicit truncation flags; the other four notes were supplied completely. Full text remains canonical and in both exports. Twelve exposures had contemporaneous lexical associations with selected concepts, including infarction and PET/CT phrases. This does not establish that the notes caused better choices; some associations are contained phrases rather than equivalent concepts. No scientific improvement is inferred from definition counts alone.

## S1, R4, branching and the early block

All **18 dispatched S1 calls returned valid `no_candidate`** and had distinct reconstructed scientific catalogue/scope fingerprints. No S2 occurred. Same-memory selection after branching was legitimate because the question scope changed. This live observation supports the scheduling repair; it does not quantify an exact counterfactual number of saved calls. Declining unsupported synthesis was defensible, although individual S1 explanations repeated the growth-range error.

The final blocked attempt demonstrates a separate scalability limit:

| S1 request | Eligible memories | Prompt | Output reserve | Total |
| --- | ---: | ---: | ---: | ---: |
| Last valid request, cycle 237 | 15 | 11,537 | 4,096 | 15,633 |
| Blocked request, cycle 251 | 16 | 12,341 | 4,096 | 16,437 |

The same 13-question scope was supplied in both. Adding rg increased the prompt by 804 tokens. The final catalogue repeated 11,156 characters of owner/ancestor question strings within its entries; the question-tree section was another 5,259 characters. Growth of the global unconsumed catalogue and repeated scope/provenance text exceeded the context window independently of per-node research capacity. The controller prioritizes this pending synthesis selection, so another ordinary step would repeat the pre-dispatch block despite living research nodes. Continuing requires a context-preparation or approved scheduling change. Lowering the requested reserve, truncating scientific content or marking work evaluated to bypass it was not attempted.

All **37 R4 decisions were `unresolved`**. That disposition is supported by the missing comparative growth evidence, although not every stated reason was correct. Four R5 actions created three children each. Historical exhaustion was entirely **`search_blocked`**, not capacity or a new stagnation rule:

| Parent | Estimated capacity total at final state | Threshold | Final status |
| --- | ---: | ---: | --- |
| q1 | 9,550 | 12,288 | split |
| q2 | 4,487 | 12,288 | split |
| q3 | 5,840 | 12,288 | split |
| q5 | 4,566 | 12,288 | split |

Final totals are **four split, nine living, zero answered, zero killed and zero currently exhausted**. No R1 validation block occurred. The run ended operationally at S1, not because research finished or all nodes exhausted.

A further observed context weakness affects branching: q4 retrieved PMID 37936095, already represented by ancestor r3, as a duplicate at cycle 90; its next R4 at cycle 140 excluded r3 as `outside_question_scope`. Similar joins occurred for q2/q3 and ancestor r6. Global deduplication prevented another extraction while the child assessment did not receive that ancestor evidence. This establishes a context/reuse limitation, not that including those papers would answer the question. Repeated concept sets, duplicate returns, broad modality drift and unsupported child premises remained signs of scientific stagnation despite successful exact-query checks.

## Comparison with the stopped experiment

Comparison: [medical-glossary-20261031.md](medical-glossary-20261031.md). The model, exact root question, temperature/thinking/output settings, context window and normal capacity were the same. Provider composition, prefix length, compilers, terminology budgets, prompt instruction, software behavior, duration and autonomous trajectory differed.

| Measure | Stopped glossary run | Retrieval-repair run |
| --- | ---: | ---: |
| Actual research wall time | 520.032 s | 1,235.126 s |
| Controller attempts / committed | 149 / 149 | 251 / 250 |
| LLM calls / generation tokens | 83 / 172,473 | 179 / 534,897 |
| Provider submissions | 63, four providers | 69, two providers |
| Identity-unique sources processed | 30, plus one pending | 81, none pending |
| Abstracts / metadata / encyclopedia excerpts processed | 7 / 19 / 4 | 72 / 9 / 0 |
| Research / synthesis memories | 4 / 0 | 16 / 0 |
| S1 calls | 17; 16 used the same pair | 18; all fingerprints distinct |
| Glossary entries / definitions | 13 / 0 | 32 / 6 |
| Actual R1 requests receiving enriched definitions | 0 | 37 of 39 |
| Final nodes | one split, three living | four split, nine living |
| Stop | User requested stop for low yield | S1 context-budget block before dispatch |

At the matched **520.032-second** allowance, the repaired run had completed 96 actions, 27 submissions and seven research memories, with no synthesis; the last included action finished at 518.800 seconds. This helps separate elapsed time from raw final counts, but does not control the changed retrieval/enrichment configuration.

Acquisition improved in a useful, limited sense: the run obtained empirical component studies and two static-imaging comparisons instead of mostly titles. Prefix reduction, concentrating on abstract-bearing providers and OR semantics all changed together; the bounded controlled-AND result cautions against attributing the improvement to OR alone. Six definitions and more memories do not validate the answer. Neither run supplied a justified four-week infection-versus-malignancy strength estimate, and the repaired run exposed additional scientific and context limitations.

## Remaining problems and recommendations for review

1. **Address S1's global context limit next.** Review compact, budget-aware catalogue/scope representation, especially repeated owner/ancestor question text. Preserve provenance, the one-call action rule and normal research-capacity policy. The current block is safe and durable; it is not a reason to silently reduce the reserve or fabricate completion.
2. **Review scientific fidelity independently of syntax.** Use the saved inequality, diagnostic-certainty, numerical-pairing and equation-origin examples as regression/evaluation cases. Structural tests passing does not resolve these reasoning failures.
3. **Ground branching premises and evidence reuse.** Check child-question assumptions against actual qualified findings and review ancestor evidence access after global source deduplication. Do not assume that a source already processed elsewhere is scientifically available to a child.
4. **Keep OR profiles experimental.** Compare precision and component coverage as well as recall; distinguish alternative diagnoses from complementary search dimensions. Do not replace production defaults based on these small uncontrolled runs.
5. **Investigate reverse-halo identity failures without weakening validation.** Preserve bounded failed-response diagnostics sufficient to identify the RDF/link mismatch. Review exact-name negatives and word-boundary truncation of long definitions. Investigate verbatim source-definition opportunities separately from authority lookup success.
6. **Continue measuring stagnation without forcing exhaustion.** Report repeated concept sets and unproductive returns. No automatic stagnation-based node transition was implemented or used.

These are proposed next changes, not fixes applied during or after this frozen experiment.

## Preserved artifacts and final checks

The single active `memory/` contains 16 research Markdown files, one equation, 32 canonical glossary records, 71 provider-outcome files, 179 interaction directories and **252 committed journals including initialization and the blocked-action receipt**. There are no synthesis files or pending source extractions. No legacy experiment directory was removed; the recovery-blocked legacy corpus remains untouched.

Execution, frozen registries, smoke/comparison results, full and concise transcripts, native context measurements and read-only audits remain under project `log/`, including `log/medical-retrieval-repair-20261031/` and `log/transcripts/medical-retrieval-repair-20261031/`. The local supervisor and `STOP` mechanism are diagnostic files, not canonical research state.

Final verification found no pending journal operations, unpublished journals, uncertain model/provider submissions or active research lease. All 619 protected pre-existing input/log artifacts retained their hashes. Normal mutable terminology-cache refreshes were excluded from immutable-log comparisons. Repeated glossary export was deterministic and left **342 core canonical files plus 32 glossary records** unchanged; journal, interaction, receipt and retrieval-file hashes also remained unchanged by export. Architecture, protected prompts and production registry hashes passed preservation checks.

Generated local exports:

- `memory/research/glossary.md`
- `memory/research/glossary.html`

```bash
PYTHONPATH=src python3 -m mira glossary-view --experiment medical-retrieval-repair-20261031
xdg-open memory/research/glossary.html
```

Repair implementation and tests were committed separately before the run. This experiment report is a separate commit. Research memories, private files, caches, execution logs and generated glossaries are not committed.
