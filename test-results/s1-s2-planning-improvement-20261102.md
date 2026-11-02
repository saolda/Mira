# S1 candidate ranking and S2 planning validation

Date: 2026-11-02, Australia/Hobart. Repository: `/home/eric/Dev/Mira`, branch `main`.
Baseline: `2b782321891f629d9db064ecda4af2f9cbd36b0e`, including production S1–S3,
the committed synthesis-discovery experiment and R1 glossary improvements.

Implementation: `5fb020e502b01e225c7f7175d11c981ba59b95c0`.
Unchanged user-authored `AGENTS.md`: `56eeaa024ea02dd63af8292364212aa0d40558fb`.

## Executive assessment

S1 retains hybrid retrieval and adds bounded opportunity neighbours, interpretable
ranking and a soft recent-group overlap penalty. All **95 baseline candidates**
survive; the revised medical pool contains **128 candidates**. S2 now generates
objectives without receiving an assigned objective. Scientific evidence precedes
deduplicated question background; worthwhile narrower comparisons are explicitly
permitted. S3's prompt, execution contract and scientific checks are unchanged.

Actual Qwen/Nomic evaluation replayed the **13 distinct groups** underlying the
previous **15 `no_candidate` responses**, then evaluated the five leading revised
selections. **Five of 18 evaluations proposed objectives; 12 of 13 proposals passed
structural validation.** This is increased planning activity, not demonstrated
scientific progress. Several proposals invent unsupported mechanistic links or
overstate diagnostic discrimination. One new pair suggests a useful comparison
of prediction endpoints, but its stronger conclusions exceed the supplied data.
Root-question bias and inequality mistakes remain observable despite explicit
instructions. No S3 calls, new empirical findings or medical synthesis memories
were produced.

## Implemented changes

S1 keeps the original lexical/semantic retrieval threshold, top-four related
neighbours, full neighbourhoods and pairs. A second top-four opportunity heap adds
complementary candidates without discarding the original candidates. Both paths
retain bounded neighbour storage; no quadratic matrix is persisted. Questions
remain contextual guidance rather than primary retrieval premises. Embedding
representation and cache keys are unchanged.

Each group's pairwise dimensions are averaged. The base priority is clamped to
`[0,1]`:

`0.55 relatedness + 0.25 complementarity_hint + 0.10 qualified_difference + 0.10 evidence_variety − 0.20 redundancy_hint`.

| Dimension, range `[0,1]` | Interpretation and limits |
| --- | --- |
| Relatedness | Existing hybrid lexical/semantic similarity; explicit relationships retain their retrieval boost. Similarity suggests relevance, not equivalence. |
| Complementarity hint | Explicit support/qualification/build-on/contradiction links, generic method–measurement–outcome role differences, or differing structural unit types. Words and extracted links may be misleading. |
| Qualified difference | Bounded differences in numerical/comparator markers, polarity, measurement units and scientific type. Different values need not be comparable measurements. The new score does not use disease-specific condition keywords. |
| Evidence variety | Different nonempty source-ID sets. This measures catalogue variety, never empirical independence. |
| Redundancy hint | Identical scientific fields, overlapping original leaf ancestry, or an existing possible-semantic-duplicate annotation. Shared-paper origin alone incurs no penalty. All units remain available. |

A further penalty of at most `0.18` uses the largest exact-version Jaccard overlap
with up to eight recent selections. It changes order without subset, superset or
overlap exclusions. Original groups and exact-version evaluated/failed registers
are retained. New receipts record selection cycles; older receipts use a stable
fallback ordering. Ranking-policy changes reopen scanning through the existing
discovery-identity mechanism, after canonical validation, without changing the
persisted catalogue formula or replaying evaluated unit sets. Lexical token
iteration is sorted for reproducibility across Python hash seeds.

S2 and S3 now have separate template-slot declarations. S2 omits `objective`;
S3 still requires it. S2 receives complete units, relationships and parent
provenance before background questions. Repeated tree-question metadata becomes
an explicit `same_as` reference; scientific fields, qualifications, research-brief
objectives and source records remain complete. A saved pending S2 context is
projected locally for the new contract without rewriting its historical receipt.
Budgeting uses the actual rendered request, and S3 is budgeted separately.
The demo parser was updated; viewer inspection already handles absent objectives
and JSON question references. Historical snapshots remain readable.

`architecture.md` clarifies only S1 ranking and diversity, S2-generated objectives
and background-only research questions. It contains no task history. The existing
user-authored `AGENTS.md` was inspected, contained no credentials/private material,
and is included unchanged.

## Controlled evaluation

[validate_synthesis_planning.py](../scripts/validate_synthesis_planning.py) takes a
journal-validated disposable snapshot. Saved groups are checked against current
unit versions and replayed through production `Research.step()` S1/S2 operations.
Historical-group replay deliberately fixes selection; it is not represented as
a revised S1 choice. Each group has its own disposable copy, so pending objectives
never cause S3 execution. No failed response was retried or scientifically repaired.

Qwen: `Qwen3.6-35B-A3B-Q4_K_M.gguf`, temperature 0, thinking disabled, JSON output,
4,096 maximum output tokens, native context 16,384. Nomic:
`nomic-embed-text-v1.5.Q5_K_M.gguf`, 768 dimensions, artifact SHA-256
`0c7930f6c4f6f29b7da5046e3a2c0832aa3f602db3de5760a95f0582dbd3d6e6`.
The baseline scan generated 37 vectors in the disposable cache; the revised scan
reused all 37. A final-code check again reused all 37, generated none, took
approximately 0.102 seconds, and selected the same five evaluated groups.

### Ranking comparison

| Position | Baseline group | Revised group | Revised priority |
| --- | --- | --- | ---: |
| 1 | `r3#f1, rc#e1, rc#f1` | `r3#f3, rb#f2` | 0.652213 |
| 2 | `re#f1, re#f2, rg#f1, rg#f2, rg#f3` | `ra#f1, rg#f1` | 0.642441 |
| 3 | `r3#f1, r8#f1, rb#f2, rc#e1, rc#f1` | `r7#f2, rc#f1` | 0.634724 |
| 4 | `r9#f1, rd#f1, rd#f2` | `r1#f2, r3#f2` | 0.625784 |
| 5 | `r9#f1, rd#f1` | `rb#f2, rc#f1` | 0.575611 |

These are fitting selections, including the recent-group penalty. Mean pairwise
group Jaccard overlap falls from **0.1267 to 0.0667**. However, revised selections
are all pairs: they cover **8 unique units in 10 slots**, versus **13 in 18 slots**
previously. Lower overlap does not establish greater evidence coverage or better
science. Generic role and numerical differences can reward weakly connected
observations; the revised top five produced useful directions only selectively.

### S2 actions and token counts

Each row is one S1 selection plus one S2 generation. Historical group 3 occurred
in all three earlier passes and is replayed once, preserving exact-set semantics.
All 36 actions committed. There were no provider searches or S3 generations.

| Trial | Selected units | Input / output tokens | Proposed / accepted | Outcome |
| --- | --- | ---: | ---: | --- |
| 1 | `re#q1, rf#q1` | 2,597 / 193 | 0 / 0 | Question-only gaps; reasonable abstention |
| 2 | `r1#q1, r2#q1` | 2,460 / 174 | 0 / 0 | Question-only gaps; reasonable abstention |
| 3 | `r3#f1, rc#e1, rc#f1` | 3,705 / 307 | 0 / 0 | Root-question bias and incorrect inequality reasoning |
| 4 | `r2#q1, r7#q1` | 2,525 / 188 | 0 / 0 | Question-only gaps |
| 5 | `r1#q1, r2#q1, rc#q1, re#q1, rf#q1` | 6,419 / 92 | 0 / 0 | Question-only gaps |
| 6 | `re#f1, rg#f1, rg#f2, rg#f3, rg#q1` | 5,716 / 911 | 2 / 2 | Morphology/PET hypotheses and comparison; overreach |
| 7 | `r3#f1, r8#f1, rc#e1, rc#f1, rc#q1` | 6,067 / 268 | 0 / 0 | Distinct pathologies and missing comparable data; ranges interpreted correctly |
| 8 | `rc#q1, re#q1, rg#f1, rg#f2, rg#q1` | 6,004 / 1,278 | 3 / 3 | Unsupported application of PET findings to rapid-growth mimics |
| 9 | `r1#q1, r2#q1, r3#f1, r7#q1, r9#q1` | 6,300 / 158 | 0 / 0 | Mostly gaps; no useful integration |
| 10 | `re#f1, re#f2, rg#f1, rg#f2, rg#f3` | 5,687 / 1,492 | 3 / 3 | Morphology/PET mechanisms and specificity claims unsupported |
| 11 | `r3#f1, r8#f1, rb#f2, rc#e1, rc#f1` | 6,323 / 1,252 | 3 / 2 | Threshold comparison/hypothesis; one same-memory objective rejected |
| 12 | `r9#f1, rd#f1, rd#f2` | 3,162 / 176 | 0 / 0 | Descriptive mimicry; rejection still tied to root metrics |
| 13 | `r9#f1, rd#f1` | 2,405 / 239 | 0 / 0 | Descriptive overlap; root-target requirement persists |
| 14, revised rank 1 | `r3#f3, rb#f2` | 2,417 / 969 | 2 / 2 | Endpoint comparison and model-combination hypothesis |
| 15, revised rank 2 | `ra#f1, rg#f1` | 2,727 / 216 | 0 / 0 | No supplied common analytical framework |
| 16, revised rank 3 | `r7#f2, rc#f1` | 2,679 / 187 | 0 / 0 | Different longitudinal measures; root bias remains |
| 17, revised rank 4 | `r1#f2, r3#f2` | 2,401 / 357 | 0 / 0 | No empirical linkage; confused threshold rhetoric persists |
| 18, revised rank 5 | `rb#f2, rc#f1` | 2,579 / 185 | 0 / 0 | Incompatible endpoints without linked observations |

Totals: **18 generation calls**, **72,173 input / 8,642 output tokens**,
**261.424 seconds** for discovery, local setup and evaluation. Historical replays
used 59,370 / 6,728 tokens and produced four idea responses; new selections used
12,803 / 1,914 and produced one. Thirteen evaluations returned `no_candidate`.
All original memory hashes were unchanged in every copy.

### Scientific assessment of the actual objectives

These assessments concern saved findings and model outputs, not independent
verification of the underlying papers. Terminology, parent questions and model
proposals are not additional empirical evidence.

- **Trial 6:** linking spiculation to PET heterogeneity is explicitly hypothetical
  but lacks paired measurements. Comparing diagnostic specificity from malignant
  solid/fGGO frequencies versus malignant/benign PET frequencies is unsupported;
  acknowledged population differences do not rescue the proposed discrimination
  claim. Sources: `re` / PMID 21696561, `rg` / PMID 29098026.
- **Trial 8:** three proposals apply PET mismatch to inflammatory pseudotumors,
  rapidly growing lesions or PSP. They introduce unsupported expected metabolic
  behaviour and treat open questions as premises from another memory. Structural
  two-memory validation passes, but this is not two-source empirical support.
  None demonstrates the proposed diagnostic advantage in the target subset.
- **Trial 10:** two morphology–metabolism hypotheses introduce unmeasured
  spiculation/hypoxia/invasion mechanisms; parts overlap each other. The specificity
  comparison claims PET superiority without comparable denominators or endpoints.
  The response also calls cohorts independent without establishing that status.
  These are not established mechanistic or diagnostic insights.
- **Trial 11:** comparing `≤400` and `<600` definitions could clarify terminology
  and methodological limits. The generated objective instead infers continuity
  and benign/malignant kinetic overlap from category boundaries without the
  necessary distributions. Its radiomic/PSP hypothesis lacks PSP spiculation data.
  A third formula/heterogeneity objective was rejected because both referenced
  units came from `rc`; the other two remained durably accepted. Sources include
  `r3` / PMID 37936095, `rb` / PMID 41432561 and `rc` / PMID 42865833.
- **Trial 14:** comparing growth-rate and invasiveness prediction endpoints is
  the clearest useful narrower direction. However, aggregate AUC/C-index values
  do not isolate spiculation's weight or establish that it is universally robust.
  The second objective proposes combining predictors and inferring kinetic–invasive
  relationships without a common cohort or feature-level data. It is a research
  hypothesis, not a supported model-performance improvement. A defensible eventual
  synthesis would need to remain a qualified methodological comparison.

The revised instructions challenge the known inequality mistake explicitly.
Trial 7 correctly notes that the categories include but do not isolate 28-day
doublers. Trial 3 nevertheless repeats the invalid “significantly slower” claim
already present in `r3#f1`'s qualification. Trial 17 mixes correct acknowledgment
of membership with misleading threshold comparisons. The original bad extraction
was preserved as required; prompt warnings did not reliably counter it.

## Comparison, limitations and recommendations

The [previous production report](knowledge-unit-synthesis-production-20261102.md)
recorded 15 abstentions across three development passes. Here, the same unchanged
scientific unit-version sets were compared through 13 unique replays, with four
idea responses. Within the previous final five primary-unit groups, two now
proposed objectives; the new leading five produced one idea response. These are
historical comparisons on one corpus/model, not a randomized effectiveness study.
Question-only historical selections are replay controls and remain excluded from
normal primary scientific discovery.

The observations support improved diversity and a corrected planning contract.
They do **not** establish reliable scientific reasoning or net new knowledge.
Full retained qualifications and summaries still repeatedly emphasize the root
question and can contain errors. Role hints are coarse, distinct source IDs may
share primary evidence, smaller groups reduce context, and reduced overlap can
also reduce scientific coverage. Broader production validation is needed before
tuning ranking weights from these outcomes.

Recommendations for subsequent review: verify questionable R3 qualifications
against their saved evidence; distinguish endpoint comparison from feature-level
or diagnostic-performance claims; examine whether questions are being used as
empirical cross-memory support; evaluate ranking quality on varied domains and
group sizes. Do not count queued hypotheses as scientific progress. No S3 redesign
was undertaken. The known geometric error remains covered: under `V ∝ D³`, a
28-day volume doubling interval implies an 84-day diameter doubling interval;
correct division by three does not verify the model's choice of operation.

## Verification and preservation

**500 tests passed; zero failures, errors or skips; 124.587 seconds.**
The [development test report](latest.md) records the final full-suite invocation.
Coverage includes deterministic ranking across input order and Python hash seeds,
complementary versus duplicate evidence, retained overlapping opportunities,
source dependence, bounded diversity, embedding reuse, policy-upgrade reopening
without exact-set replay, cross-branch question deduplication, separate S2/S3
contracts, saved pending S2 projection, valid abstention and narrower objectives,
multiple proposals, budgets, immutable receipts, journal/crash recovery,
legacy formats, R1–R5, glossary and viewer inspection. The geometric regression
explicitly demonstrates the existing scientific-verification boundary rather
than claiming arithmetic validation catches the wrong growth-law mapping.

Command: `PYTHONPATH=src python3 scripts/run_tests.py`. `git diff --check` also
passed. Complete suite logs are retained as `final-suite.stdout` and
`final-suite.stderr` under the local diagnostic directory.

The before/after audit covers **2,681 protected files**, including the entire
active/legacy `memory/` tree, R prompts, S3, `futureWork.md`, the historical
diagnostic script/report and the original `AGENTS.md`: **zero changed files and
zero new corpus files**. No active experiment was reset or executed. Glossary
implementation, production R1–R5 and protected scientific history were preserved.
S3 SHA-256 remains
`e9c3f5674569a49525d137c982bd8c67cc762a195d5ccdf126b973ee19a442ba`.

Complete local diagnostics: `log/s1-s2-improvement-20261102/live/result.json`,
`ranking.json`, `final-ranking.json`, and `group-*/` execution logs. Each interaction
retains exact rendered prompts, bindings, responses, token counts and validation.
Disposable journals/corpora remain under `/tmp/mira-synthesis-planning-gk827yre/`.
These local research artifacts are ignored and are not committed. Earlier traces
under `log/knowledge-unit-synthesis-20261102/` remain intact. Development failure
logs are retained, including the initial missing `PYTHONPATH`, a fixture attempting
an immutable-event rewrite, and the policy-upgrade regression corrected before
final acceptance.
