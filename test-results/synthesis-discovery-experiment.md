# Experimental knowledge-unit synthesis discovery

Completed review: **2 November 2026, Australia/Hobart**. Production baseline: `f1ed577`. Preparation and evaluation resumed after an interruption; phase timings below exclude the intervening pause.

**Executive assessment:** Finding-level discovery is feasible on this corpus and produces bounded, auditable groups. It does **not** yet justify replacing production synthesis. Hybrid retrieval found 12/16 reviewed relationships versus 8/16 for lexical retrieval, but missed useful links and included a hard negative. No genuine duplicate was established. Qwen returned nine ideas across three groups and rejected three groups, including the weak control. Several proposed ideas contain endpoint/population errors or restate known limitations. No new scientific knowledge, infection-versus-malignancy probability, or successful S3 synthesis was demonstrated.

All seven generation calls (six experimental S2 evaluations and one production-template control) completed with structurally valid references. The medical corpus, active experiment, journal, production code, prompts, architecture and future-work documentation were preserved. No literature searches, research-controller actions, S3 actions or canonical publications occurred.

## A. Existing infrastructure

The implementation inspected `index.py`, `embeddings.py`, `api.py`, `gardener.py`, `research_tree.py`, `format.py`, safe-reader/recovery code and their tests. Reused facilities are canonical parsing and hashes, `existing_reader`, journal validation, `NomicHTTPEmbedding`, vector validation/cosine, HTTP model transport, JSON proposal parsing, redaction and atomic local artifact writing.

Existing units already have stable `memory#anchor` identifiers and content revisions. `Knowledge.retrieve` exposes structured units and provenance; `SYNTHESIZES` relationships already address individual units and can trace inherited evidence. Canonical memory metadata carries source identifiers and qualifications. SQLite already supports FTS5, vectors and exact cosine scans. Existing public index queries may refresh their disposable index under a writer lock, so this experiment read the corpus through the noninitializing shared-lock reader and built a separate 61,440-byte FTS5 file under `log/`. It did not touch the active index.

Production S1 currently examines a global memory catalogue. Production S2 checks selected whole-memory versions, preserves complete or lossless structured inputs, requires an integrated finding referencing two parent memories, and consumes contributing **memories**. Its register excludes completed memory-version combinations and subsets. That is materially different from the proposed exact **unit-set** participation policy; this experiment does not migrate or change it.

Minimum additional mechanisms appear to be: a versioned scientific unit projection; representation/model-keyed embedding cache; bounded neighbour graph/group identity; separate reviewable duplicate annotations; and an exact-version unit-set evaluation register. Existing SQLite and relationship types suffice for investigation. No new database framework or runtime dependency was introduced.

## B. Corpus inventory and protection

The actual journal-validated corpus matches [the medical retrieval-repair report](medical-retrieval-repair-20261031.md):

| Item | Count |
| --- | ---: |
| Research memories / synthesis memories | 16 / 0 |
| Structurally finding-shaped units | 36 |
| Finding / claim / inference labels within those units | 30 / 5 / 1 |
| Hypothesis / synthesis findings | 0 / 0 |
| Question units / equation definitions | 9 / 1 |
| Existing synthesis attempts | 0 |

The projection retains unit ID, parent ID, semantic/structural type, proposition, complete explanation/qualification, status, source records, relationships, canonical revision and a scientific/source-content hash. Missing explicit evidence-status fields are conservatively projected as `unverified`, with an explicit-status flag retained. An author's interpretation remains an inference; author recommendations remain claims.

Canonical revision: `6834896a6c16813d3118f1b439f17ec1b11688e2c506e70d77234c8128f13992`. The saved snapshot is experimental JSON, not a new canonical memory. Protected-file hash checks covered **2,770 pre-existing paths**, including the active and legacy corpora, source tree, prompts and protected documents. Final verification found no changes to research data, source files, prompts or protected documents and no new files in those areas. Three existing ignored Python bytecode caches (`gardener`, `research`, `research_cli`) regenerated during imports/tests; the audit records these separately rather than claiming byte-for-byte preservation of runtime caches. Existing recovery-blocked legacy research was not opened for execution or modified.

Existing extraction defects remain visible: r3's incorrect inequality qualification, r4's single-center label despite a two-hospital source, r7's diagnostic-certainty/morphology overstatement, rc's unsupported equation-origin attribution, and rf's misassigned AUC uncertainty. These were neither repaired nor treated as verified facts.

## C. Similarity analysis

Nomic model: `nomic-embed-text-v1.5.Q5_K_M.gguf`, artifact SHA256 `0c7930f6c4f6f29b7da5046e3a2c0832aa3f602db3de5760a95f0582dbd3d6e6`. Actual local llama.cpp service: port 8091, **768 dimensions**, 2,048-token context, mean pooling, one slot, GPU layers enabled on ROCm0/ROCm1. Every input used `search_document: `; no token-hashing test double was used. Cosine normalizes vector lengths during comparison. Full properties, server flags and text/vector hashes are retained locally.

**A** embeds the full proposition and qualification. **B** adds type, scientific label, explanation and other scientific fields. Dedicated ID, citation, source-identity and bookkeeping fields are excluded from both. Qualifications remain verbatim; an embedded author attribution or negated scope statement can still introduce retrieval noise. In this corpus, separate explanation fields are empty; B mostly adds type/label framing rather than additional scientific exposition. Therefore this is a limited test of contextual representation, not a general comparison of rich versus sparse scientific context.

Lexical similarity uses Unicode/HTML/whitespace-normalized significant token sets, inverse-document-frequency weights and normalized dot products. Common research vocabulary is filtered. Hybrid score is `0.5 × lexical + 0.5 × max(0, semantic)`. Seed neighbourhoods retain the top four matches above 0.42, with unit-ID tie-breaking. These are experimental settings, not calibrated biological thresholds.

The reviewed diagnostic benchmark has **24 pairs: 16 plausible relationships and eight weak/unrelated pairs**. Labels follow the supplied scientific content, but pair selection was informed by neighbour inspection. It is not blinded, held out, independently clinically adjudicated or large enough for reliable population estimates. Thresholds were not tuned to maximize its scores. Retrieval means an edge in either direction of the bounded neighbour graph, not merely exceeding a pairwise threshold or co-occurring through a third unit.

| Retrieval method | TP | FP | FN | TN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| lexical | 8 | 0 | 8 | 8 | 1.000 | 0.500 |
| semantic-A | 11 | 0 | 5 | 8 | 1.000 | 0.688 |
| semantic-B | 12 | 0 | 4 | 8 | 1.000 | 0.750 |
| hybrid-A | 12 | 0 | 4 | 8 | 1.000 | 0.750 |
| hybrid-B | 12 | 1 | 4 | 7 | 0.923 | 0.750 |

Lexical uses a fixed 0.15 threshold; semantic uses 0.75, with the same top-four limit. These operating points are illustrative, not matched false-positive rates. B increased graph edges (91 hybrid versus 76 for A) without improving reviewed recall, and introduced one hard-negative edge. There is no demonstrated representation-B superiority. The hard negative relates COP prognosis to IgG4 morphology without a supplied connecting hypothesis.

Important misses include r6#f2–rd#f1 (malignancy mimicry across reviews), r1#f1–re#f1 (spiculation across different endpoints), rg#f1–rf#f1 (PET/CT texture comparison), and r2#f2–rd#f2 (benign histology and avoiding surgery). A low score does not establish scientific unrelatedness. Conversely, qualifications saying that a source **does not** address spiculation/doubling time introduce those exact words into retrieval: the experimental FTS spiculation query ranked r5#f1 first, although its proposition concerns the reversed-halo sign. Negated evidence-gap language can create misleading topical similarity.

The inspectable pair benchmark follows; all expected duplicate labels are false. The source reports and distinct qualifications prevent interpreting apparent near duplicates as equivalent evidence.

| Pair | Lexical | Nomic A | Nomic B | Scientific review |
| --- | ---: | ---: | ---: | --- |
| r1#f1 / r1#f2 | 0.425 | 0.814 | 0.879 | Related: Predictor versus whole-model performance; same screening evidence. |
| r3#f2 / r3#f3 | 0.261 | 0.860 | 0.887 | Related: Selected feature versus integrated growth-category model. |
| rf#f1 / rf#f2 | 0.368 | 0.911 | 0.915 | Related: Discrimination claim versus feature families from the same cohort. |
| rf#f1 / rf#f3 | 0.192 | 0.823 | 0.850 | Related: Discrimination claim qualified by moderate AUC; saved uncertainty transcription is flawed. |
| rg#f1 / rg#f2 | 0.806 | 0.976 | 0.978 | Related: Mismatch and match are complementary partitions of the same 24/31 lesions, not independent replication. |
| r9#f1 / rd#f1 | 0.226 | 0.853 | 0.868 | Related: Respiratory manifestations versus systemic IgG4 pathology; overlapping description is not equivalence. |
| r6#f2 / rd#f1 | 0.075 | 0.670 | 0.693 | Related: Separate reviews describe malignant mimicry; shared primary evidence is unknown. |
| r2#f1 / r7#f1 | 0.185 | 0.808 | 0.847 | Related: Different benign/inflammatory presentations, with unequal diagnostic certainty. |
| r7#f2 / r8#f1 | 0.086 | 0.756 | 0.775 | Related: Reduction versus enlargement occurs in different patients, organs and follow-up periods. |
| r3#f1 / rc#f1 | 0.156 | 0.809 | 0.834 | Related: Different growth cutoffs/populations; neither cutoff establishes a four-week diagnostic comparison. |
| r1#f1 / rb#f1 | 0.051 | 0.920 | 0.926 | Related: Cancer prediction in screening versus invasiveness within adenocarcinoma. |
| r1#f1 / re#f1 | 0.059 | 0.793 | 0.831 | Related: Screening predictor versus morphology frequencies among malignant nodules. |
| rg#f1 / rf#f1 | 0.037 | 0.746 | 0.800 | Related: Different imaging modalities/comparators can motivate a methodological comparison, not pooled accuracy. |
| r3#f3 / rf#f3 | 0.073 | 0.797 | 0.840 | Related: AUC values concern growth category versus malignancy/IPT; not a direct performance ranking. |
| r2#f2 / rd#f2 | 0.059 | 0.725 | 0.753 | Related: Histologic benign mimic and caution against unnecessary surgery; not equivalent evidence. |
| r6#f1 / r8#f1 | 0.109 | 0.745 | 0.798 | Related: Review lists orbital involvement; case describes orbital and other nonpulmonary lesions. |
| r4#f2 / rg#f3 | 0.030 | 0.590 | 0.633 | Weak/unrelated: COP relapse timing and PET-based tumor proliferation interpretation have no supplied connecting mechanism. |
| r5#f1 / rf#f2 | 0.019 | 0.692 | 0.764 | Weak/unrelated: Reversed halo differential versus texture feature families; generic imaging vocabulary is insufficient. |
| r8#f1 / rb#f1 | 0.052 | 0.695 | 0.769 | Weak/unrelated: Orbital/CNS IPT growth versus invasiveness in pulmonary adenocarcinoma. |
| r4#f3 / rg#f1 | 0.030 | 0.756 | 0.823 | Weak/unrelated: COP fibrosis/mortality outcomes versus PET uptake distribution. |
| r9#f2 / re#f2 | 0.015 | 0.643 | 0.703 | Weak/unrelated: Need for IgG4 diagnostic criteria versus within-malignancy CT frequency comparisons. |
| r4#f2 / rf#f2 | 0.013 | 0.629 | 0.680 | Weak/unrelated: Steroid-associated COP relapse versus CT radiomics feature families. |
| r4#f3 / rb#f1 | 0.066 | 0.731 | 0.810 | Weak/unrelated: Absence of COP fibrosis/death does not supply a comparison with adenocarcinoma invasiveness. |
| r4#f3 / r9#f1 | 0.100 | 0.678 | 0.757 | Weak/unrelated: COP prognosis and IgG4 morphology share pulmonary vocabulary without a supplied analytical connection. |

## D. Duplicate detection

Conservative exact matching retains numerical values, punctuation/comparators, negation, full qualification/explanation, evidence type/status and source relationship. Candidate annotations also inspect polarity/direction vocabulary, magnitudes, time/measurement units and selected population/species/condition words. These safeguards are incomplete lexical checks, not a clinical equivalence test. Different source IDs are explicitly **not proof of independent studies**; review articles may reuse primary evidence.

**Observed:** no exact duplicate, likely semantic duplicate or verified independent corroboration was established among the 630 pairs. The broad r9#f1/rd#f1 resemblance (B=0.868) concerns respiratory versus systemic IgG4 descriptions and remains related but distinct. Separate reviews r6/rd offer a corroboration hypothesis with unresolved primary-evidence overlap. No actual directly contradictory result under matched conditions was established; enlargement versus reduction in r8/r7 involves different patients, organs and follow-up periods.

The strongest pair, **rg#f1/rg#f2**, has lexical 0.806 and semantic B **0.978**. It reports complementary mismatch/match proportions in the same 24 malignant and 31 benign lesions. It is neither duplicate evidence nor independent corroboration. A numerical safeguard prevented duplicate classification. Likewise, rf#f1/rf#f2 (B=0.915) states discrimination and describes feature families; these are complementary units from one source.

Embedding-only duplicate cutoffs flag **338 / 121 / 25 / 7 / 1** corpus pairs at 0.75 / 0.80 / 0.85 / 0.90 / 0.95. On the reviewed sample, those flags include **20 / 13 / 7 / 3 / 1** nonduplicates, respectively. Even 0.95 falsely selects the complementary PET pair. No real duplicate-positive benchmark cases exist, so duplicate precision/recall cannot be credibly estimated. Conservative-rule duplicate predictions and false-positive duplicate declarations are both zero; that is abstention, not demonstrated sensitivity.

A significant prototype failure is the polarity heuristic: **502/630 pairs** are labelled `potential_contradiction_or_qualification`, usually because one qualification contains a negation or directional word absent from the other. It does not correctly distinguish contradictions from unrelated caveats. All labels require review, and no evidence is merged, deleted or suppressed. Nonmedical fixtures test exact duplicates, semantic-equivalence bookkeeping, conflicting directions, numeric/time/species distinctions and source retention; they are not fabricated additions to the medical corpus.

## E. Candidate groups

Thirty-six seed neighbourhoods produced **33 unique versioned unit sets**, avoiding three repeated exact sets. Each group holds at most five units, with an order-independent hash ID, parent/source IDs, scientific records, edge scores, duplicate annotations, reason and a labelled conservative byte-based S2 token estimate. Native tokenizer counts for evaluated groups are below. The group distribution spans one/two/three/four/five memories in **1/3/17/10/2** groups. Thus 29/33 span the intended three-to-five-memory range; smaller groups were not padded.

Ranking is deterministic by mean seed-edge hybrid score, then group ID. Groups can overlap. They are star neighbourhoods, not claims that every pair in a group is mutually relevant. That accounts for weak additions such as pulmonary infarction alongside IgG4 disease. Generic context still contaminates groups, despite the hard size limit.

Actual duplicate-equivalent suppression avoided **zero additional groups**: no uncertain semantic pair was granted equivalence. Exact-set suppression discarded no distinct unit set. Scientifically useful opportunities incorrectly suppressed by semantic equivalence cannot be measured because that policy was deliberately not activated. Overlapping groups still repeat some scientific themes.

## F. Experimental S2 evaluation

The existing local **Qwen3.6-35B-A3B-Q4_K_M.gguf** served all calls on port 8090. Temperature 0, thinking disabled, JSON output, max output/reserve **4,096**, native context **16,384**. Server flags report a 32,768 aggregate allocation across two slots; the actual per-request window remains 16,384. No generation settings, provider strategy or research-capacity configuration were changed. Configuration SHA256: `f813944ed1dc5be11b9877815ff0234cdb3533d3fdcbc52b06e63286f7a4a60f`; model artifact and chat-template hashes are saved separately. No Python random sampling was used.

The experimental prompt is embedded only in the standalone script, clearly labelled separately from production prompts. It asks for opportunities, references, limitations and novelty, permits `no_candidate`, and explicitly warns about endpoint/population mismatches and the 400/600-day inference error. This additional scientific guidance is a **comparison confounder**, not evidence that grouping alone improves reasoning.

Five retrieved groups plus one manually assembled weak control were evaluated. All complete system/user messages were printed to the console before dispatch and saved verbatim. All six outputs passed JSON/reference validation, with no retry, rejected output, transport error or context overflow. Structural validation is not scientific validation.

| Group | Supplied units | Parent memories | Input tokens | Outcome |
| --- | --- | --- | ---: | --- |
| G539f24e149 | r1#f1, r1#f2, r3#f2, r3#f3, rb#f1 | r1, r3, rb | 4,382 | ideas (3 ideas) |
| Gd5c788bc5a | re#f1, re#f2, rg#f1, rg#f2, rg#f3 | re, rg | 4,509 | no_candidate (0 ideas) |
| Gb2072df33e | r5#f2, r9#f1, r9#f2, rd#f1, rd#f2 | r5, r9, rd | 4,201 | ideas (3 ideas) |
| Gab55c4d9cc | r3#f3, re#f2, rf#f1, rf#f2, rf#f3 | r3, re, rf | 4,386 | ideas (3 ideas) |
| G7ffd9d97a8 | r3#f1, r3#f2, r3#f3, rc#f1, re#f1 | r3, rc, re | 4,505 | no_candidate (0 ideas) |
| Gcontrol | r4#f2, rg#f3 | r4, rg | 1,474 | no_candidate (0 ideas) |

Every row reserves another 4,096 tokens. Maximum total is **8,605**, well within 16,384. The six calls used **23,457 input and 3,766 completion tokens**, producing nine proposals from three groups; the other three returned `no_candidate`.

Scientific review of the actual proposals:

- **G539f24e149:** compare spiculation's roles across screening cancer probability, growth categories and within-adenocarcinoma invasiveness; compare model performance; describe the missing four-week etiologic evidence. Endpoint taxonomy is a plausible analytical objective. However, the first idea explicitly calls rb#f1 an invasive-potential result in **solid** nodules, despite its supplied **nonsolid** population, and assigns a solid-only scope to r1 without support. Cross-target AUC comparison and suggested distinct biological mechanisms remain unsupported. The evidence-gap idea largely restates supplied limitations.
- **Gd5c788bc5a:** rejected static CT/PET findings as inadequate for the growth-conditioned question. This is defensible, but does not demonstrate recognition of the complementary proportions as a duplicate trap: the model's reason focuses on missing kinetics, not duplicate identity. It may also overlook a useful bounded methodological comparison unrelated to answering the whole root question.
- **Gb2072df33e:** proposes comparing infarction with IgG4 diagnostic mimics, linking criteria to unnecessary surgery, and comparing diagnostic pitfalls. These are review/hypothesis topics, not established shared mechanisms. Two ideas substantially repeat the mimicry-comparison theme. The criteria proposal introduces a causal contribution to a **high rate** of misdiagnosis without supporting rate or causal data; its own limitations acknowledge the lack of performance data.
- **Gab55c4d9cc:** proposes comparing growth-prediction radiomics with cancer/IPT discrimination, relating qualitative morphology to texture features, and mapping the missing etiologic prediction evidence. Useful endpoint separation is visible. Proposed correlations or primary feature drivers cannot be established without shared measurements. The last idea drifts from re's within-malignancy morphology comparison toward etiology prediction, despite recognizing that limitation.
- **G7ffd9d97a8:** correctly declines an infection-probability synthesis, but repeats the erroneous assertion that a **≤400-day category is significantly slower than 28 days**, copied from the qualification. That range includes 28 days. The explicit prompt warning did not prevent the error. Missing an isolated 28-day subgroup is the defensible limitation.
- **Gcontrol:** rejects COP relapse versus PET hypoxia/proliferation interpretation as lacking a supported connection. This is a successful negative control, not proof that all weak groups will be rejected.

There were zero exact repeated objective strings, but semantic redundancy remains: evidence-gap restatements recur across groups, and the IgG4 group's two mimicry comparisons overlap. Nine ideas must not be counted as nine novel findings or nine independent synthesis opportunities. **No S3 was run.**

## G. Experimental attempt register and novelty gate

The separate register distinguishes discovered groups, durable submitted/uncertain calls, completed evaluations and rejected/failed outputs. Identity is a hash of sorted `(unit ID, content version)` pairs. Discovery alone does not register completion. Transport/interruption leaves an uncertain state and disallows automatic replay; a request file also prevents the experiment CLI from silently repeating a call. The register is an experimental single-process artifact, not a replacement crash-safe production journal.

Recorded demonstrations and tests establish:

| Case | Result |
| --- | --- |
| Reorder/repeat an evaluated r1#f1 + r3#f2 set | Same fingerprint; completed/suppressed |
| Add actual rb#f1 evidence | Different available set; no blanket overlap/subset exclusion |
| Change a unit version in an explicitly labelled simulation | Available; original evidence untouched |
| Discover but do not evaluate a set | Still available |
| Interrupt after durable submission | Uncertain; no automatic retry |
| Fail output validation | Not a completed scientific evaluation |
| Apply reviewed equivalence to the exact reviewed versions | Equivalent wording can share a class; original IDs remain |
| Add a different source or change a reviewed version | Different equivalence identity; no silent evidence loss |

The actual register contains six completed S2 evaluations, including three scientific rejections, with proposals/objectives and empty S3/contributor/result fields. Production synthesis-attempt records remain unchanged. Reviewed semantic equivalence is a separate mechanism and is not automatically granted from an embedding score.

The novelty-gate prototype flags normalized identical qualified conclusions for review and compares their source evidence. A replay of an existing real finding is flagged without publishing anything. It considers proposition, qualification, explanation, type/status and evidence basis; a new source is visible even when the proposition repeats. It does **not** reliably recognize every paraphrase, infer study independence, or adjudicate novelty under changed assumptions. A future S3 gate must combine candidate retrieval with explicit scientific review; approximate fingerprints cannot silently veto publication. No actual synthesis finding was generated to test that future gate end to end.

## H. Computational cost and scaling

Observed warm-service costs on the 36-unit snapshot:

| Operation | Observed cost |
| --- | ---: |
| A embeddings: 36 HTTP requests | 0.254 s; 12,769 scientific-text UTF-8 bytes |
| B embeddings: 36 HTTP requests | 0.239 s; 14,301 bytes |
| Pairwise lexical, both embeddings and annotations: 630 pairs | 0.087 s |
| Complete 36×36 one-representation matrix | 0.042 s |
| Incremental exact pair updates into top-four heaps | 0.021 s; same neighbours as full matrix |
| Retaining top four from existing pair rows | 0.000224 s |
| FTS5 build / index size | 0.0046 s / 61,440 bytes |
| Three example FTS queries | Approximately 0.018–0.399 ms each |
| Saved A+B vector JSON / pair-analysis JSON | 1,560,848 / 632,089 bytes |
| Seven generation calls including matched control | 81.248 s; 27,183 input + 3,919 output tokens |

There were **72 embedding-generation requests**; metadata/tokenizer calls are separate and do not perform generation. Model loading, file hashing, waiting between turns and final report work are outside those phase timings. These are small, warm, sequential measurements, not service throughput guarantees. Actual JSON/Python memory overhead is much larger than packed-array estimates; no peak-RSS claim is made.

Complete pairwise construction costs O(N²D) time and O(N²) stored similarities. Streaming exact top-k construction can retain O(ND + Nk) storage, but still needs O(N²D) initial comparisons; inserting one new unit needs one embedding and O(ND) exact comparison work, updating existing heaps as well. Both representations require separate version/model/representation-keyed caches. The current diagnostic script intentionally saves all pairs and builds a full matrix for comparison, so its **overall run is still quadratic in storage**. The bounded-heap result demonstrates the alternative, not a completed production incremental index.

Illustrative one-representation comparison-time extrapolation from the 630-update heap measurement; vector memory includes **both** representations at float32, and heap payload uses an ideal 16 bytes/edge:

| Units | Unique pairs | Full float64 matrix | Two vector arrays | Top-four edge payload | Extrapolated initial exact comparisons |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 499,500 | 0.008 GB | 6.14 MB | 0.064 MB | 16 s |
| 10,000 | 49,995,000 | 0.800 GB | 61.44 MB | 0.640 MB | 1645 s |
| 100,000 | 4,999,950,000 | 80.000 GB | 614.40 MB | 6.400 MB | 164532 s |

At 100,000 units, one exact insertion scans 99,999 prior vectors: approximately 3.3 seconds by this naive extrapolation, excluding embedding/index writes. Two representations approximately double comparison work if both are retained. These estimates ignore cache, vectorization, hardware saturation and service batching. They justify avoiding stored full matrices; they do not establish a specific approximate-neighbour product as necessary. First evaluate exact batched/vectorized retrieval and bounded FTS candidates; investigate ANN only if measured corpus size/update latency demands it. No ANN infrastructure was introduced.

## I. Comparison against current S1

Saved history contains **18 dispatched production S1 calls, all `no_candidate`**. The final 16-memory attempt was blocked before generation at **12,341 + 4,096 = 16,437**, 53 tokens over the window. Scientific flaws already documented in that run remain relevant.

A new matched-parent-memory control used r1/r3/rb, the unchanged production S1 template and the same model/settings, without executing the controller or writing any canonical state. It returned valid `no_candidate` in **3.887 s**, using **3,726 input + 153 output tokens**. It incorrectly summarizes r3 as only having >400-day doubling times, repeating endpoint/range narrowing. The matched finding-level G539 call used **4,382 input tokens**—**17.6% more**, not less—because it supplies actual propositions/qualifications and verbose duplicate/edge annotations. Thus the gain is bounded access to findings across a large corpus, not a universal token saving over a small catalogue.

| Comparison | Production memory-catalogue selection | Experimental unit-group evaluation |
| --- | --- | --- |
| Final global baseline input | 12,341, blocked with reserve | Five retrieved groups: 4,201–4,509, all fit |
| Matched r1/r3/rb input | 3,726 | 4,382 |
| Matched outcome | No candidate | Three ideas, with population/endpoint mistakes |
| New generation calls in this investigation | One matched control | Six group evaluations |
| Historical context | 18 no-candidate calls | No comparable autonomous research trajectory |
| Duplicate proposals | No proposals in saved/control calls | Repeated gap/mimicry themes despite unique strings |
| Demonstrated new scientific findings | None | None; S3 deliberately absent |

The experiments differ in granularity, supplied evidence, task contract, scientific warnings, group count and call budget. They are not a controlled causal attribution of better science to embeddings. The global 16-memory request was not resent to force another known overflow. No matched ablation isolates duplicate labels, lexical versus embedding group selection, or the stronger S2 prompt. A more permissive opportunity task naturally yields more plans than a substantive-synthesis selection task; proposal count is not success.

## J. Proposed architecture and decision

**Recommendation: retain the experiment for review; do not replace production synthesis yet.** The observed evidence supports testing unit-level discovery and exact-set bookkeeping. It does not support automated semantic deduplication or claims of improved scientific synthesis.

The task authorizes investigation, not a production architecture change. Proposed principles and details requiring approval are:

1. **S1 deterministic discovery:** reuse canonical unit IDs, qualifications, existing FTS/cosine infrastructure and a rebuildable embedding cache. Retain bounded scored neighbours and versioned groups. Keep negated scope statements separate from affirmative findings for retrieval weighting. Measure missed cross-source connections, not just nearest-neighbour scores.
2. **Separate relationship and duplicate review:** high similarity may indicate shared topic, complementary partitions, contrary effects or different endpoints. Keep all source IDs and uncertainty. Require explicit, version-bound equivalence review before any semantic-set suppression; source independence needs evidence beyond distinct citations.
3. **S2 opportunity evaluation:** supply complete selected units, source identity and compact meaningful distinctions. Remove generic pairwise warning inflation and repeated source metadata after reviewing the actual full prompts. Decide whether a scoped method-comparison opportunity qualifies when it cannot answer the root question; require a novelty rationale that distinguishes a new inference from another gap statement.
4. **Unit participation register:** start with exact versioned sets, explicit discovered/submitted/uncertain/completed states and a deliberate retry policy. Preserve overlapping/superset opportunities. Unit participation must not automatically consume an entire parent memory; changing that production semantic requires migration/recovery design and architectural approval.
5. **S3, only after a later decision:** retrieve source-grounded evidence, validate precise contributing unit IDs and attach explicit synthesis relationships. Keep model hypotheses separate from findings; compare proposed conclusions and their assumptions, qualifications and evidence basis against existing findings before publication. This experiment implements no S3.

Hypotheses need modality/status-aware matching rather than being treated as established findings. Open questions can match methods/entities or missing evidence, but question wording is not supporting evidence. Equations require symbol/unit/dimension/assumption checks in addition to text embeddings; the saved source-origin error illustrates the risk. Existing synthesis findings could participate via their exact source-unit relationships, with ancestry/circularity checks and no double-counting of shared evidence. No hypotheses or synthesis findings existed here, and equation discovery was inventoried but not experimentally scored, so those recommendations remain unvalidated.

Next evidence needed: an independently labelled benchmark containing real duplicate positives, independently sourced corroboration with known study overlap, matched-condition contradictions, important low-lexical-overlap complements and hard negatives; held-out thresholds; matched-prompt/call-budget ablations; and a separate, explicitly authorized source-grounded S3 test. Fixing or adjudicating known extraction errors also needs its own review. Do not infer production readiness from structural tests.

## Reproduction, artifacts and validation

Permitted repository additions only: [standalone experiment](../scripts/synthesis_discovery_experiment.py), [focused tests](../tests/test_synthesis_discovery_experiment.py) and this report. No runtime dependencies or production-file changes were made. These experimental artifacts are committed for architectural review; raw model outputs, prompts, embeddings and research data remain local and uncommitted.

```bash
# Existing prepared run: analyse without repeating model calls.
PYTHONPATH=src python3 scripts/synthesis_discovery_experiment.py analyse
PYTHONPATH=src python3 scripts/synthesis_discovery_experiment.py verify
PYTHONPATH=src python3 -m unittest discover -s tests -p test_synthesis_discovery_experiment.py -v

# Independent reproduction: choose a NEW ignored output directory.
PYTHONPATH=src python3 scripts/synthesis_discovery_experiment.py \
  --output log/synthesis-discovery-experiment-reproduction prepare
PYTHONPATH=src python3 scripts/synthesis_discovery_experiment.py \
  --output log/synthesis-discovery-experiment-reproduction analyse
# Evaluate the selected IDs from evaluation-groups.json one at a time; every
# actual request prints in full. Re-evaluating an existing request is refused.
PYTHONPATH=src python3 scripts/synthesis_discovery_experiment.py \
  --output log/synthesis-discovery-experiment-reproduction evaluate G539f24e149
```

All raw artifacts are ignored local files under `log/synthesis-discovery-experiment/`: `corpus.json`, `embedding-service.json`, `final-service-configuration.json`, `embeddings-{A,B}.json`, `pairs.json`, `reviewed-benchmark.json`, `retrieval-evaluation.json`, `duplicate-threshold-sensitivity.json`, `groups.json`, `evaluation-groups.json`, `attempt-register.json`, `register-demonstration.json`, `call-summary.json`, `historical-s1-summary.json`, `reproduction-check.json`, and `preservation-check.json`. Cached vectors reproduced all 630 pair rows exactly, and all six experimental serialized requests were reconstructed byte for byte without inference.

**Complete prompt transcript:** `log/synthesis-discovery-experiment/full-prompts.txt`. Individual exact prompts, serialized requests, raw responses, timing/usage and validation results: `calls/<group-id>/{prompt.txt,request.json,response.json,validation.json}`. `responses-and-validation.json` combines the seven outputs. Prompt/configuration hashes and credential redaction are retained; no credentials are included. The full prompts were printed directly for all seven calls, not replaced by excerpts.

**Tests: 456 passed, zero failures/errors/skips, 58.953 s**, including 13 focused experimental tests. Full result and console logs: `repository-tests.md`, `repository-tests.stderr`. Tests cover deterministic grouping/ties, exact-set identities and supersets, source/version-sensitive reviewed equivalence, interrupted-call persistence, conservative duplicate safeguards, novelty review, supplied-unit validation, complete request roles/content and output separation from the read-only corpus. Tests used temporary nonmedical fixtures and did not publish active research. Passing them establishes contracts, not scientific accuracy.
