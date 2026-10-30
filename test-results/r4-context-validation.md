# R4 context correction and extended validation

Recorded: 30 October 2026, Australia/Hobart. **The demonstrated R4 overflow is resolved without removing scientific evidence.** Re-tokenizing the saved blocked request reduces 17,006 to 8,834 tokens including the unchanged 4,096-token reserve; all 12 chronological searches and the complete scientific context remain. The fresh alternative-profile run completes three rounds and 30 direct actions, with three valid R4 retry decisions, then stops at its original wall-clock deadline guard. One S2 rejection is preserved and normal controller progression later produces a valid integration. It does not establish a clinical answer.

## Commits, scope and synchronization

- Implementation: `4cb524f834dca8cf3d58fac26e555eaf424f4066`.
- Dedicated regression tests: `1545c85dba658f91c1a864e5c695e63a15b7690e`.
- Reports are a separate subsequent commit; its SHA is reported after publication.
- Clean `main` safely synchronized with fetched `origin/main` at `82a5661`; no incoming change or unrelated local work needed handling.

Only `src/mira/research.py` changes production behavior. `search_outcome()` now projects R4’s search history through an explicit field allowlist. R4 still receives every committed provider search for its node, including empty, failed, rate-limited, deferred and unavailable outcomes. Ordering remains ascending timestamp then reference, exactly as before. There is no last-N cutoff, query alteration, relevance filter or extra model call.

Each entry contains `round`, `provider`, `profile_id`, `query`, `query_submitted`, `status`, `returned_record_count`, `unique_record_count`, `duplicate_count`, plus `http_status` when recorded. Exact query text and submitted=false survive. Legacy round/profile/submission metadata stays null when unknown; missing counts are derived from retained unique and duplicate lists, while explicitly stored zero counts remain zero. No historical submission or scientific result is invented.

Repeated profile configuration, request receipts, timestamps, UUIDs, source-disposition maps, payload pointers and arbitrary error prose are absent from the LLM history projection. They remain unchanged in original retrieval records and execution logs. Status and applicable HTTP status preserve the distinction between unsuccessful retrieval and scientific findings. R4’s existing unsuccessful-search cautions, its three-way decision contract and every accumulated research memory/equation are unchanged.

No changes were made to `architecture.md`, `futureWork.md`, any `prompt_templates/*` file, `gardener.py`, provider scheduling, query-profile defaults or existing experiments. OpenAlex remains suspended only in predefined strategies; adapters and explicit configuration support are unchanged. The proposed 0–6 R1 concept change remains unimplemented.

## Read-only reproduction of the original overflow

Original corpus: `memory/research/medical-no-openalex-baseline-20261030`. The third R4 request was recovered from its independent execution log’s `model_request_blocked` record. Its old serialized body was reproduced byte-for-byte from the unchanged R4 template, saved context and generation settings. The corrected context was built through the current controller projection using that corpus’s canonical state, without calling `Research.step()` or resuming it.

| Measurement | Original blocked R4 | Corrected same-state R4 |
| --- | --- | --- |
| Prompt tokens | 12910 | 4738 |
| Output reserve | 4096 | 4096 |
| Total request plus reserve | 17006 | 8834 |
| Context window | 16384 | 16384 |
| Remaining headroom | exceeds by 622 | 7550 |
| Serialized request bytes | 43539 | 17906 |
| Search entries | 12 | 12 |
| Scientific context | original | exact equality with original |
| Model inference calls | 0 | 0 |

Measurements use the existing Qwen server’s native `/apply-template` and `/tokenize` endpoints, including thinking settings and special-token handling—not a character heuristic or a model completion. Both checks use the same model/chat-template hash; the measured original exactly reproduces its recorded 12,910 prompt tokens. The reduction is **8,172 prompt tokens (63.3%)**, or **48.1%** of prompt-plus-reserve. All context fields other than `search_history`, including the complete `research_results`, are exactly equal. The original corpus hashes remain identical before/after inspection.

This resolves the demonstrated failure at this recorded state. An arbitrarily larger body of scientific evidence or an indefinitely growing complete search history may still exceed the context window; the genuine-overflow guard remains active. The correction never truncates evidence to guarantee fit.

Local reproducible assertion script: `memory/benchmarks/r4-context-20261030/compare-blocked.py`; exact before/after bodies, context, template provenance and measurements: `blocked-comparison.json`; small measurement log: `blocked-comparison.log`. These local medical artifacts are not committed.

## Automated validation

The complete suite passed **350 tests, zero failures/errors/skips**, before the experiment (**56.847 s**) and after it (**56.934 s**). Command: `PYTHONPATH=src python3 scripts/run_tests.py ...`. Full logs: `memory/benchmarks/r4-context-20261030/tests-before.log` and `tests-after.log`. Focused R4 tests also passed **7/7**. No source/test changes followed the final complete-suite pass.

Seven new regressions cover: all 30 chronological outcomes across six statuses and repeated rounds with unchanged original records; equal-timestamp reference ordering; legacy null metadata and inferred counts; a verbose synthetic overflow fitting after compaction while retaining every entry and scientific input; an actual dispatched R4 retaining the entire normal scientific projection and original retrieval bytes; genuinely oversized scientific input blocking before any model dispatch; and R4 journal repair/restart without a second completion or changed retrieval record. The synthetic offline boundary uses the explicitly labeled conservative UTF-8 fallback; the actual medical-token claim is established independently by the tokenizer assertion above.

The existing prompt-input test now verifies offline failure status/provider preservation and that detailed error text remains in persisted evidence rather than in R4’s compact history. The full suite also retains deferred-provider, pacing, source fidelity, deduplication, budget and journal recovery tests.

## Investigation of the two previous S1 failures

Corpus: `memory/research/medical-query-comparison-20261030`. Both actual saved rendered requests were inspected and verified through the read-only Inspector; their serialized bodies are **byte-identical** (SHA-256 `eea566fa9e575d8d62d0754fee6759474dcb6bb290bbf93cc370f112df3a9e17`). Recomputing `gardener.selection_context()` from the unchanged corpus reproduces the exact input catalogue. No inference or controller action was run against that corpus.

| Interaction | Output behavior | Recorded rejection |
| --- | --- | --- |
| 00000004-7d747491d83041f6bab16704b01c2774 | 1,896 prompt / 4,096 completion; finish=length; 15,113 content characters; invalid/unclosed JSON | incomplete model output |
| 00000005-a86d104ad10a4992b1ddcac5e4609a46 | 1,896 prompt / 1,100 completion; finish=stop; valid JSON; memory_ids=[r2] | S1 requires at least two distinct eligible memory IDs |

**Model output behavior is the immediate failure.** The first response starts a single-memory selection and fills its reason with repeated deliberation over whether to include `r1` or return `no_candidate`; it exhausts the output allowance without closing the object. The second finishes JSON but leaves disposition `select` and just `r2`, while its reason argues for `no_candidate` and contains conflicting proposed corrections. Thinking is disabled in both actual requests; this deliberation is inside ordinary JSON/content output, not a separate reasoning channel. Increasing the output allowance cannot explain or repair the second response’s selection error.

**Input construction is correct for the current catalogue contract, with a scientific-quality limitation.** Both `r1` and `r2` are present, have distinct eligible IDs, hashes, source provenance, summaries and S2 cost estimates; the exclusion list is empty. No missing second memory or unexpected eligibility filter explains the one-ID output. A valid local two-memory budget/validation probe using complete memories and a diagnostic objective measures **2,992 prompt + 4,096 reserve = 7,088 / 16,384**, so a pair fits. This is a tokenizer-only audit, not a proposed model decision or proof that a synthesis is scientifically worthwhile. Individual catalogue costs already include overhead/reserve and should not be naively summed as a collection cost. A correctly formed `no_candidate` response also validates unchanged.

The catalogue exposes model-written summaries rather than every finding-level qualification, as designed. `r2` already makes an unsupported malignancy-versus-infection inference from cancer-only ALI findings; S1 repeats it. `r1`’s summary explicitly includes ≤400 and >400 growth groups, but both rejected outputs treat it as slow growth only. Thus some limitations are upstream summary fidelity and model reading, not catalogue omission. Identical request bytes yielded different invalid responses; this observation does not isolate the backend cause or establish deterministic reproducibility at temperature zero.

**Prompt interpretation warrants review, not an implemented diagnosis of unavoidable ambiguity.** S1 already provides a `no_candidate` JSON alternative, requires at least two IDs for a selection and says not to include weakly related memories. These rules are compatible: return `no_candidate` when no suitable pair exists. Its unconditional prose “Select at least two eligible memories” could be made explicitly conditional to reduce the model’s demonstrated conflict. The model recognized both options and still failed to commit one valid output; this is not evidence that the validator should accept a singleton.

**Response validation is correct.** `decisions.proposal()` rejects a non-stop finish before attempting to admit incomplete JSON. `gardener.validate_selection()` rejects the valid JSON singleton before synthesis preparation. Neither case creates a selection, consumption or synthesis memory. The two-eligible-memory rule remains intact.

**Scheduling is a separate progress problem.** Five direct actions made synthesis due just after Europe PMC retrieval, before its pending R3 extraction. Rejected S1 rolls back the successful-action counters, leaving synthesis due against the same catalogue, so a subsequent step can repeat S1 and delay the infectious source. This behavior follows the existing scheduler; it did not cause the malformed content, but it repeatedly exposed the same unhelpful catalogue and blocked productive extraction. No S1 prompt, cadence, rejection fallback, cache or scheduling policy was changed here. Local assertions and details: `investigate-s1.py`, `s1-investigation.json` and `s1-investigation.log` under the task artifact directory.

## Fresh continued-research experiment

Fresh name: **medical-r4-context-20261030**. Question file and root text remain byte-identical: “Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?” No supplementary context, answer or research objective was injected.

The existing Qwen3.6-35B-A3B Q4_K_M local server was reused with verified 16,384 tokens/request, temperature 0, thinking disabled, JSON output, 4,096 output limit/reserve and two results/provider. Strategy snapshot is exactly `pubmed → europe_pmc → crossref → wikipedia`; OpenAlex was never submitted. Normal capacity (12,288), synthesis/branching cadence and all retry/pacing settings remain unchanged. Initialization is excluded from measured research time.

The temporary registry is an exact copy of the previous alternative registry, supplied through `profile_registry`: PubMed `pubmed_balanced` compiler with **max_terms=2**; Europe PMC **max_terms=3** and the supported `legacy` compiler’s compatible plain-text space joining (`provider_legacy` combination/quoting/escaping); Crossref 4/text and Wikipedia 3/text unchanged. IDs/version 1 and timing settings are retained in this local registry and its experiment snapshot. The committed `query_profiles.json` is unchanged. Local file: `memory/benchmarks/r4-context-20261030/alternative-profiles.json`.

The supervisor allowed up to 40 direct actions and 900 seconds. The first segment paused after a rejected S2 at 174.182 seconds. Inspection confirmed that the existing failed-S2 path clears pending synthesis, resets its cadence counter and permits normal direct research; continuing required no acknowledgement, retry substitution, code/prompt change or scheduling override. The same fresh experiment continued under its **original deadline**, not a fresh 15-minute allowance.

Final result: **30 direct actions**, **38 committed / 39 attempted controller actions**, **three completed rounds and a fourth begun**. Stop reason: **wall_clock_guard** after **806.255 seconds wall time**, including **255.385 seconds active execution** and **550.870 seconds paused for inspection/report preparation**. With under 95 seconds remaining, the supervisor reserved time for a complete bounded next request rather than dispatching another action or busy-waiting. This conservative guard stays inside the 900-second maximum; it did not reach the 40-action ceiling. All six S1 outputs remained valid, so the requested stop-on-invalid-S1 condition did not arise. No provider waiting, rate-limit error, context-budget error or transport error occurred. All later actions used the unchanged controller; the already-recorded S2 error is described below.

| Metric | Fresh run |
| --- | --- |
| R1 / R2 / R3 / R4 | 4 / 14 / 9 / 3 |
| S1 / S2 model calls | 6 / 3 (second S2 rejected) |
| Total model calls | 25 |
| Research / synthesis memories | 5 / 2 |
| Returned / unique / duplicate sources | 22 / 9 / 13 |
| Abstracts / metadata among unique sources | 6 / 3 |
| R3 sources processed / pending | 9 / 0 |
| Distinct submitted provider/query pairs | 8 |
| Glossary candidates / used | 6 / 1 (VDT) |
| Prompt / completion / total tokens | 72,138 / 9,792 / 81,930 |
| Largest dispatched prompt / with reserve | 5,507 / 9,603 |
| Branching / final deferred searches | 0 / 0 |

The three live R4 requests contained respectively **4 / 8 / 12 search entries** and measured **3,999 / 5,114 / 5,507 prompt tokens**, or **8,095 / 9,210 / 9,603** with reserve. All fit within 16,384 with complete direct-research input, including consumed research memories. All three decisions were `retry`. The fresh third-round 9,603-token request is a different scientific workload from the original blocked request; the same-state 8,834-token comparison remains the controlled before/after evidence.

### Actual R1, S1 and S2 behavior

1. R1: `spiculated pulmonary nodule`; `volume doubling time`; `lung malignancy`; `pulmonary infection`; `lesion growth rate`.
2. R1: `volume doubling time`; `spiculated nodule`; `lung cancer`; `pulmonary infection`; `benign nodule`; `growth rate`.
3. R1: `volume doubling time`; `spiculated nodule`; `lung cancer`; `pulmonary infection`; `benign nodule`; `growth rate`.
4. R1: `volume doubling time`; `spiculated nodule`; `lung cancer`; `pulmonary infection`; `benign nodule`; `growth rate`.

The second R1 primarily reorders growth/morphology and substitutes malignant terminology. Its correctly supplied four previous outcomes and unresolved research gaps do not produce a targeted CT measurement or malignant-growth-distribution query. The third and fourth R1 lists exactly repeat the second list. There are 14 actual provider submissions but only eight distinct provider/query pairs (six repeated submissions), and 13 duplicate records. Semantic diversification remains limited. Glossary use is VDT, already present before discovery, so it does not demonstrate a new direction generated by the glossary.

All six S1 calls are structurally valid: three `no_candidate` responses and three selections—`r2+r3` (**17/25**), then `s1+r4` (**20/25** and later **21/25**). The prior S1 format/selection failure does not recur in this one new run, but the inputs differ because R3 outputs differ, so S1 has not been proven fixed. The first selection excludes the infectious memory as insufficiently specific; the later selection includes it, yet describes a statistical malignancy preference that its inputs do not establish.

First S2 produces `s1` and passes structural lineage validation, but retains the reversed VDT interpretation and infers malignancy preference from noncomparative populations. The second S2 receives `s1+r4` and returns four findings with input-anchor groups **[s1#f1]**, **[s1#f2]**, **[r4#f1, r4#f3]**, **[s1#f3]**. None integrates two distinct input memories in a single finding. Python correctly rejects it with **“at least one integrated finding must reference two distinct input memories”**, marks the attempt failed, creates no memory for that attempt, and leaves `s1`/`r4` unconsumed at that point. This is not an R4 overflow or an S1 singleton failure. No existing integration rule was relaxed. After two additional R3 actions and ordinary provider work, a later fresh S1 again selects `s1+r4`. The third S2 call supplies an integrated finding spanning those two inputs and creates `s2`, consuming its contributing inputs normally. This demonstrates the existing failed-attempt/reselection path without accepting the earlier invalid response. The new accepted synthesis still propagates the unsupported malignancy preference without correcting its scientifically flawed lineage; it also presents surgery as necessary rather than retaining the small-series qualification. Structural recovery is not scientific correction.

### Provider audit

| Provider | Submissions / HTTP requests | Returned / unique / duplicate | Outcome |
| --- | --- | --- | --- |
| crossref | 3 / 3 | 6 / 3 / 3 | {'ok': 3} |
| europe_pmc | 4 / 4 | 8 / 3 / 5 | {'ok': 4} |
| pubmed | 4 / 8 | 8 / 3 / 5 | {'ok': 4} |
| wikipedia | 3 / 3 | 0 / 0 / 0 | {'empty': 3} |

| Provider | Exact submitted query | Retained source IDs |
| --- | --- | --- |
| pubmed | `(spiculated pulmonary nodule) AND (volume doubling time)` | pmid:37936095; pmid:39807982 |
| europe_pmc | `spiculated pulmonary nodule volume doubling time lung malignancy` | europe_pmc:MED:42780873; europe_pmc:MED:42469902 |
| crossref | `spiculated pulmonary nodule volume doubling time lung malignancy pulmonary infection` | doi:10.1016/j.chest.2022.08.414; doi:10.1016/s0169-5002(85)80158-6 |
| wikipedia | `spiculated pulmonary nodule volume doubling time lung malignancy` | none |
| pubmed | `(volume doubling time) AND (spiculated nodule)` | pmid:41869733 |
| europe_pmc | `volume doubling time spiculated nodule lung cancer` | europe_pmc:MED:42625155 |
| crossref | `volume doubling time spiculated nodule lung cancer pulmonary infection` | doi:10.32388/s833ik |
| wikipedia | `volume doubling time spiculated nodule lung cancer` | none |
| pubmed | `(volume doubling time) AND (spiculated nodule)` | none |
| europe_pmc | `volume doubling time spiculated nodule lung cancer` | none |
| crossref | `volume doubling time spiculated nodule lung cancer pulmonary infection` | none |
| wikipedia | `volume doubling time spiculated nodule lung cancer` | none |
| pubmed | `(volume doubling time) AND (spiculated nodule)` | none |
| europe_pmc | `volume doubling time spiculated nodule lung cancer` | none |


## Scientific evidence audit

Every extracted numeric claim and cited source ID was compared with the exact source content saved in its R3 request, not inferred from the final memory alone. All nine unique sources were processed once: three metadata sources appropriately produced empty extractions; five abstracts produced five research memories; one adjacent growth/measurement abstract also produced an empty extraction. No full text, images or external audit material was supplied to Mira. Relevant identifiers remain available in the retained evidence and payloads.

**ALI study / r2:** [PMID 39807982](https://pubmed.ncbi.nlm.nih.gov/39807982/), [publisher abstract](https://pubs.rsna.org/doi/abs/10.1148/radiol.240599). The provided abstract reports spiculation OR **2.05** (CI **1.42–2.97**), VDT OR **0.96** (CI **0.94–0.98**), AUC **0.77→0.82**, and a cancer-only population. R3 copies these values but states that **longer VDT increases ALI odds**; an OR below 1 does not support that positive direction. Its summary repeats the reversal. S1 and accepted S2 propagate it into an apparent contradiction with the progression cohort. Unit/scaling details are not supplied, so a four-week quantitative conversion is unavailable. Even a correct ALI association within resected NSCLC cannot yield infection-versus-cancer odds.

**Radiomics / r1:** [PMID 37936095](https://pubmed.ncbi.nlm.nih.gov/37936095/). R3 retains **273 growing SSNs**, **857 scans**, **≤400 / >400 days**, spiculation as one selected feature and **AUC 0.928/0.905**. It correctly says the abstract does not analyze the four-week etiologic comparison. A ≤400-day category includes 28 days; it is not proof that rapid growth was excluded. The old S1 slow-only reading remains an error, not a property of this source.

**Progression cohort / r3:** [PMID 42780873](https://pubmed.ncbi.nlm.nih.gov/42780873/). R3 retains the **392-patient** population, **1.5-fold** grouped spiculated-and-lobulated margin association and shorter-VDT comparison (**P <0.05**). Its summary drops the lobulated grouping and attributes the effect to spiculation alone. The statement that VDT was not independently predictive is inferred from absence in the abstract’s listed final predictors, not an explicit negative full-model result. Progression is not an infection-versus-cancer outcome.

**Cryptococcosis / r4:** [PMID 42469902](https://pubmed.ncbi.nlm.nih.gov/42469902/). Three newly emerging/growing nodules in patients with previous malignancy were pathologically cryptococcosis. The two patients tested with FDG-PET had uptake; this is not a calibrated 2/3 diagnostic sensitivity, since the third was not reported as tested. R3 preserves the small-series limitation and surgery-as-observed-case-management qualification. Unlike the previous alternative, this run actually extracts the previously pending infectious evidence. It is new retained knowledge relative to that run, not a newly discovered publication or evidence of a four-week/spiculation likelihood. The rejected S2 adds rapid doubling, spiculation and a “rare mimic” label to this source without those measurements or a frequency denominator.

**MPA / r5:** [PMID 41869733](https://pubmed.ncbi.nlm.nih.gov/41869733/). The abstract’s **VDT ≤310 days** predictor, spiculation association and **AUC 0.923** are retained with the lung-adenocarcinoma population. This is an adjacent subtype/prognostic lead, not a rapidly growing cancer VDT distribution or a 28-day malignant-growth observation. Optional glossary proposals with ellipses substituted for exact passages are rejected, preserving the substantive extraction.

Crossref’s two publications are metadata only: [biochemical VDT title](https://doi.org/10.1016/S0169-5002(85)80158-6) and [aspergillosis nodule title](https://doi.org/10.1016/j.chest.2022.08.414). Their titles do not supply study findings, and Mira correctly creates no research memory from them. A third Crossref unique result is NCI terminology metadata, [Spiculated Nodule](https://doi.org/10.32388/s833ik), and creates no memory. Europe PMC also retrieves [PMID 42625155](https://pubmed.ncbi.nlm.nih.gov/42625155/), a persistent-subsolid-nodule study with 665 and 176 patients, cancer/non-cancer growth comparisons and P<0.001 for volumetric/doubling-time measures. R3 returns no results because it lacks the exact four-week/infection comparison; Python correctly discards its nonempty summary. This loses adjacent growth/measurement evidence despite successful retrieval. It is not direct CT repeatability/uncertainty evidence, and cancer/non-cancer grouping is not a specified infection comparison. No direct infection-versus-malignancy comparison is retrieved. The separate measurement papers found in the previous controlled probes are not part of this run’s evidence.

| Evidence need | New run actually supports |
| --- | --- |
| Malignant lesion doubling-time distributions | Growth-category/subtype thresholds only; no distribution |
| Rapid cancer subtypes | MPA predictor cutoff; no four-week subtype growth observation |
| Infectious growth | Three growing cryptococcosis cases, no VDT or spiculation-specific frequency |
| CT measurement uncertainty | No direct repeatability evidence |
| Direct infection-vs-malignancy comparison | None |
| Progress toward question | Additional infectious and subtype extraction; diagnostic direction/strength unresolved |

The accepted synthesis’s malignancy-favoring title and conclusion are unsupported. Absence of an infection comparison cannot favor the competing etiology, and known-cancer biology cannot be generalized into an infection-versus-cancer probability. Structural validation protects references and integration shape, not scientific correctness. R4’s decisions to continue are appropriate, but its third reason imports an unsupplied clinical claim that most primary lung cancers grow more slowly and that four-week growth may suggest infection/inflammation. None of these retrieved abstracts establishes that distribution or that differential preference; this is an unsupported statement relative to R4’s supplied evidence, not a finding from the new run. Clinical plausibility does not establish local provenance. Thus no numerical probability or clinical recommendation is warranted from this collection.

## Exact proposals for review only

No proposal below was applied to prompts, architecture or scheduling.

**S1 wording:** replace the standalone instruction `Select at least two eligible memories.` with the following conditional rule, retaining the existing schemas and all other requirements:

```text
If disposition is "select", include at least two distinct eligible memory IDs.
If no coherent, evidence-grounded combination of at least two eligible memories
exists, return "no_candidate". Never return a one-memory selection or add an
unrelated memory just to meet the minimum.
```

Add next to `reason`: `Give one settled decision. Keep reason to at most two concise sentences; do not include deliberation, proposed corrections or alternative JSON decisions.` This targets the observed behavior without reducing the two-memory requirement. Test it with the two preserved catalogues and explicit one-relevant-memory/no-pair fixtures before adoption. It is a proposed user-reviewed prompt revision, not a change made by Codex.

**Scientific fidelity:** propose adding to reviewed R3/S2 instructions: `Preserve the direction and scope of numeric associations. Do not translate a predictor within an already-diagnosed disease population into a comparison with another etiology. If the unit, coding or comparison needed for an interpretation is unavailable, retain the reported value and state that the interpretation is unresolved.` For S1, propose: `Missing comparative evidence is an evidence gap, not a negative finding against an etiology.` Add concrete evaluation cases for OR<1, mixed-margin predictors, ≤ thresholds and case-series denominator limits. These are audit/evaluation proposals; no clinical fallback is introduced.

**Catalogue input, if approved:** supplement each memory’s summary with a deterministic `qualifications` array of `{unit_id, qualification}` copied from its substantive units, and keep source provenance. Do not generate new population labels or silently truncate qualifications. Measure the full S1 request before dispatch and reject an actually oversized request. This would expose some finding-level limitations omitted from current summaries, but cannot by itself correct a false qualifier or a model ignoring the source title. It requires an approved input-contract/budget review.

**Rejection scheduling, if approved:** after an S1 validation rejection, preserve its raw response/error and record a failed-selection receipt keyed by catalogue memory hashes. If pending R3 or another productive direct/branching action exists, permit that work before another S1 against the unchanged catalogue; clear the rejection guard after a catalogue change. If no productive action exists, return an explicit blocked/review outcome rather than making repeated identical selections. Do not cache/reuse an accepted S1 decision, invent a `no_candidate` response, or permit singleton synthesis. The exact receipt, retry limit, terminal behavior and restart semantics require architecture review; no such guard is implemented here.

**S2 integration:** the existing prompt already states the two-input integrated-finding rule clearly, and the validator correctly enforces it. A reviewed clarification could say: `At least one individual source_findings array must contain anchors from two distinct listed input memories. Two anchors from the same memory do not satisfy this condition. If no such finding is justified, return no_synthesis.` Replaying the observed `[s1#f1] / [r4#f1,r4#f3]` pattern is an exact evaluation case. Keep the validator strict; do not add cross-memory anchors just to satisfy syntax without scientific support.

R4 itself needs no prompt/architecture amendment for this correction: the current architecture already calls for compact history and complete scientific inputs. Future scalability decisions about bounding all-history growth should be reviewed separately rather than silently dropping entries now. `futureWork.md` remains untouched.

## Preservation, artifacts and limitations

All **6,240 pre-existing research files** and **13 prior execution logs** retain their hashes. All protected document, prompt, question and default-profile bytes are unchanged. Read-only corpus/tree/glossary integrity checks passed across **40 initialized corpora**; no journal corruption was found. The new corpus has no uncertain model/provider submission, and failed S2 validation does not commit a partial memory or consumption.

All **25 actual dispatched requests** pass Inspector template/message verification. Every R3 source equals its retained payload, each provider query equals the snapshotted compiler output and recorded request parameter, and all **24** supplied R1 outcome entries match committed retrieval evidence. Each of the three R4 histories was independently matched against every earlier provider record; the corresponding complete scientific memory projections (four, five and five memories) were compared exactly. Results are retained in `memory/benchmarks/r4-context-20261030/final-request-audit.json`. All R4 entries are present with the allowlisted fields. The existing two blocked/failed experiments were inspected without controller actions and remain byte-identical.

Local-only experiment: `/home/eric/Dev/Mira/memory/research/medical-r4-context-20261030`. It contains complete model requests/responses, source payloads, retrieval receipts, memories, glossary, journal, state, supervisor timings, `validation.json` and `validation-analysis.json`.

Independent execution logs:

- `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_075914_medical-r4-context-20261030_156f83f91440.jsonl`
- `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_075914_medical-r4-context-20261030_1cfeae7c5f08.jsonl`

Continuation execution log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_081119_medical-r4-context-20261030_ab2943f54aca.jsonl`.

Supervisor and audit scripts, exact before/after R4 bodies, S1 investigation, temporary profiles, preservation hashes, complete test logs and integrity results: `/home/eric/Dev/Mira/memory/benchmarks/r4-context-20261030/`. These raw medical corpora and interaction logs remain excluded from GitHub. The local model/embedding servers were left running unchanged.

The successful same-state token comparison proves the specific R4 overflow correction. The fresh run provides three real compact R4 calls and progresses beyond the earlier failed S1 and the newly recorded failed S2 using normal controller behavior. It stops at a deadline guard below the 40-action ceiling. Its 806.255-second wall time includes a long inspection pause and must not be presented as equal active research time or used to claim an overall efficiency gain. The run does not establish S1 reliability or scientific validity. No experiment predating this task was resumed, no unapproved workaround was used, and no unrelated source change was made. Final repository integrity, push, actual remote-ref equality and clean-tree status are checked after completing these reports and summarized in chat.
