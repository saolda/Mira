# Comprehensive scientific synthesis evaluation

Date: 2 November 2026, Australia/Hobart. Branch: `main`.
Baseline: `04f751d91c69034edda5e97c6b4d3a41bd9a6af1`.

Validated corrections: `9186808c6ce444fe2ffe2398814743826ba5210d`.
Experimental scripts and regression tests: `02a76b0834cc40b9131faab697f33aae76bc947c`.

## Executive findings

**Mira did not demonstrate a fully defensible new medical discovery.** It did
generate small, potentially useful methodological comparisons, including a
comparison of operational growth thresholds. Several such outputs failed
structural checks. The one medical memory published during the generation
experiment mixed a valid distinction between prediction tasks with unsupported
claims about feature robustness and study independence; it requires review.

The experiment completed **60 genuine Qwen generations: 14 S2, 45 S3 and one
experimental critique**. The 45 S3 attempts comprised 30 medical and 15
mathematical attempts: **26 abstentions, 12 structural/publication rejections and
seven disposable publications**. Of those publications, six were mathematical
controls and one was medical. Only two published mathematical controls were
unambiguously correct answers to their supplied problems. Correct artificial
deductions are not evidence of a discovery from published medical research.

S3 repeated S2's erroneous 9.33-day prediction for a 28-day volume doubling time.
However, removing anticipated answers did not reliably improve reasoning: the
neutral condition also failed, and sometimes failed where full guidance worked.
This supports concern about answer echoing, **not a measured general causal
effect of S2 contamination**. Four comparable positive conversion controls gave
three correct full-guidance answers versus no consistently correct complete
neutral responses; this small, exploratory comparison is not an accuracy estimate.

Larger groups generated plans, but ordinary S2 proposals reduced their S3
execution sets to two memories. Separate investigator-assigned three-, four-
and five-memory execution controls generated multi-source candidates but all
failed structural checks and contained scientific weaknesses. More references
did not demonstrate better science.

The original corpus, question tree, scientific memories, source records, logs,
private inputs and prompts remain unchanged. Two demonstrated production defects
were corrected: questions satisfying the second substantive-parent requirement,
and compact formatting rejecting literal scientific prose. No production S4,
scientific-content repair, new research campaign or prompt redesign was added.

## Methods and accounting

All execution used uniquely named disposable copies. The active corpus remained
at canonical revision
`6834896a6c16813d3118f1b439f17ec1b11688e2c506e70d77234c8128f13992`:
16 research memories, 36 finding-shaped units, nine questions, one equation and
13 question-tree nodes. Previous generated outputs were treated as hypotheses
or controls, never independent empirical evidence.

Qwen: `Qwen3.6-35B-A3B-Q4_K_M.gguf`, artifact SHA-256
`671e47e0ec53c665d048b98c3ecbfd5236b5ca9c3e02ed19fc8f81f7b85140c7`.
Nomic: `nomic-embed-text-v1.5.Q5_K_M.gguf`, 768 dimensions, artifact SHA-256
`0c7930f6c4f6f29b7da5046e3a2c0832aa3f602db3de5760a95f0582dbd3d6e6`.
Generation used temperature 0, thinking disabled, JSON output, a native 16,384-token
window and 4,096 output tokens/reserve. No semantic test double was substituted.

| Quantity | Observed |
| --- | ---: |
| Genuine generation calls | 60, all received; no uncertain submissions |
| Input / output tokens | 258,556 / 44,026 |
| Sum of generation-request elapsed time | 935.797 seconds |
| Largest S3 input plus reserved output | 7,262 + 4,096 = 11,358 tokens |
| Largest generated output | 2,573 tokens |
| API finish reasons | 60 `stop`; no output-limit termination |
| Medical S3: abstain / rejected / published | 23 / 6 / 1 |
| Mathematical S3: abstain / rejected / published | 3 / 6 / 6 |
| Provider research searches / active research actions | 0 / 0 |

Elapsed generation time excludes analysis, setup, tokenization, embedding calls,
article retrieval and tests. Six explicitly labelled investigator-assigned S2
protocol receipts were nongenerative; a seventh protocol setup fell into R5 and
was rejected. They are excluded from the 60 calls and proposal-yield statistics.
One later offline storage replay reused identical saved response bytes, added no
generation, and produced another unverified disposable memory. Thus there are
eight local publications across the original experiment and that software replay,
not eight independent scientific results.

[evaluate_scientific_synthesis.py](../scripts/evaluate_scientific_synthesis.py)
uses `Research.step()` and production S3 validation/publication. Experimental
scheduling selects a pending objective without deleting other objectives.
Neutral conditions change only objective guidance; question-metadata ablations
are separately labelled. Exact prompts, responses, settings, versions, validation,
state, generated Markdown and copied journals are retained. A durable ledger
refuses duplicate requests, uncertain submissions and calls beyond 60. Received
scientific outputs were neither retried nor edited.

The first 40 calls used the baseline validator. Later controls used the stricter
substantive-parent check; their selected primary units satisfy both policies.
The formatting correction was assessed after all generations by offline replay.
Per-run source hashes distinguish these conditions. All production prompt bytes
are unchanged, including S3 SHA-256
`e9c3f5674569a49525d137c982bd8c67cc762a195d5ccdf126b973ee19a442ba`.

## Audit of the 13 existing S2 proposals

The complete 18 prior S2 evaluations, selected units and proposals were recovered
from `log/s1-s2-improvement-20261102/live/result.json`. The five proposing groups
contained 13 proposals, 12 originally structurally accepted. Investigator review
classified **one A, two B, three C and seven D**. A means an integration worth
attempting under its stated limits; B means a worthwhile hypothesis; C means
insufficient/incompatible evidence; D means invalid or redundant. A/B do not
certify anticipated conclusions. Full original wording and support records remain
in `proposal-audit.json`.

| Proposal | Actual support | Category | Scientific reason |
| --- | --- | --- | --- |
| T6-P1 | `rg#f1`, `re#f1`, `rg#f3` | B | A testable morphology–metabolism association is conceivable, but no paired observations establish it; specific hypoxia/spiculation mechanisms remain unsupported. |
| T6-P2 | `re#f1`, `rg#f1`, `rg#f2` | D | Spiculation frequencies within malignant subtypes cannot supply specificity against benign disease or rank modalities against PET malignancy discrimination. |
| T8-P1 | `rg#f1`, `rg#f2`, `rc#q1`, `rg#q1` | D | Uses open questions as the second-memory support and assumes unmeasured inflammatory metabolic behaviour. |
| T8-P2 | `re#q1`, `rg#f1`, `rc#q1` | D | Only one empirical memory; questions do not establish comparative diagnostic utility. |
| T8-P3 | `rg#f2`, `rc#q1`, `rg#q1` | D | Treats a contextual PSP question as an observed cross-memory premise; no PSP PET observations. |
| T10-P1 | `re#f1`, `re#f2`, `rg#f1`, `rg#f3` | C | No co-registered morphology/PET measurements or verified cohort independence; proposed aggressive phenotype not established. |
| T10-P2 | `re#f1`, `re#f2`, `rg#f1`, `rg#f2` | D | Confuses subtype discrimination with malignant/benign discrimination and claims diagnostic superiority across different denominators. |
| T10-P3 | `re#f1`, `re#f2`, `rg#f3` | D | Invents spatial hypoxia/proliferation explanations for particular CT features without joint evidence. |
| T11-P1 | `r3#f1`, `rc#f1` | C | Category definitions do not establish measured benign/malignant growth-distribution overlap or continuity. |
| T11-P2 | `rb#f2`, `rc#f1` | C | No PSP morphological/radiomic measurements link the adenocarcinoma model to PSP growth. |
| T11-P3 | `rc#e1`, `rc#f1` | D | Both requested units are from one memory; cohort heterogeneity does not establish within-lesion nonexponential growth. |
| T14-P1 | `r3#f3`, `rb#f2` | A | Attempting a bounded comparison of predictive tasks and endpoints is defensible. Aggregate performance cannot isolate feature weights; anticipated stronger conclusions are unsupported. |
| T14-P2 | `r3#f3`, `rb#f2` | B | Combining distinct endpoint predictors is a testable methodological hypothesis, not demonstrated independence or improved accuracy; patient-level data are missing. |

## Audit of extracted evidence

Six full primary papers were retrieved through Europe PMC and hash-preserved;
PubMed abstracts supplied additional checks. The primary sources resolve the
following distinctions:

| Units | Review and origin |
| --- | --- |
| `r3#f1` | **Verified R3 error.** The retrieved abstract correctly states the ≤400-day category. R3 adds that it is significantly slower than 28 days. Later S2/S3 repeat that invalid interpretation. The primary paper supports the category, not that comparison. [Primary paper](https://doi.org/10.1186/s12880-023-01143-x) |
| `r4#f2` | **Verified R3 error.** “Single-center” conflicts with the two hospitals named in the supplied abstract, full methods and another finding in the same memory. [Primary study](https://pubmed.ncbi.nlm.nih.gov/42604996/) |
| `r7#f1` and summary | **Verified overstatement.** The source describes suspected PIPT with unresolved differentiation from PIMT. R3 strengthens diagnostic wording, though its qualification retains uncertainty. The patient-specific CT description does not establish spiculation merely because the paper's background discusses it. [Case report](https://pubmed.ncbi.nlm.nih.gov/42694241/) |
| `rc#e1` | **Attribution unsupported by R3 input; expression retrospectively verified.** Its truncated abstract names a modified Schwartz formula without displaying it. R3 supplies an expression labelled source-derived. The full primary methods do contain the equivalent volume-ratio equation. This is not evidence that the equation itself was fabricated. [Primary study](https://doi.org/10.21037/jtd-2026-0786) |
| `rc#f1` | **Correct scoped extraction.** Six of 17 serial-imaging cases meet the <600-day category. This establishes neither an individual 28-day observation nor an infection/malignancy likelihood. [Primary study](https://doi.org/10.21037/jtd-2026-0786) |
| `rf#f3` | **Verified R3 transcription error.** The uncertainty attached to 0.748 was taken from another feature family: the primary abstract gives 0.731 ± 0.075 and 0.748 ± 0.038. [Primary paper](https://doi.org/10.1186/s12880-020-00475-2) |
| `r3#f3`, `rb#f2` | **Correct aggregate values, different tasks.** Growth-category AUCs and an invasiveness-model C-index are not head-to-head performance estimates. The latter paper separately reports a spiculation odds ratio in `rb#f1`; it cannot be inferred from the aggregate score. [Growth model](https://doi.org/10.1186/s12880-023-01143-x), [invasiveness model](https://pubmed.ncbi.nlm.nih.gov/41432561/) |
| `rg#f1–f3` | **Counts supported; mechanism remains interpretation.** Matched/mismatched observations partition the same 55-person study. They are not independent replication, and they do not establish a spiculation–hypoxia mechanism. [Primary paper](https://doi.org/10.3892/ol.2017.6840) |
| `ra#f1` | **Original abstract is nuanced.** Its broad null-association statement coexists with a weak significant NLR correlation. R3 retains that exception in its qualification. Neither statement establishes absence of incremental predictive value in another model. [Primary abstract](https://pubmed.ncbi.nlm.nih.gov/42787882/) |

The growth-model paper describes image-level random splitting across repeated
scans. This is a methodological dependence/leakage concern to investigate, not
proof of actual leakage or an R3 numerical transcription error. Full methods for
the invasiveness model were not independently verified here; external validation
or comparable cohorts must not be assumed from aggregate abstract results.

The matched threshold control replaced only the erroneous `r3#f1` qualification
in a clearly documented experimental branch. Production storage correctly refused
editing an existing unit. The final controlled branch was therefore seeded as a
new validated corpus, retaining source IDs, events, question tree and term records,
and linking its first journal operation to the untouched original snapshot and
journal. Its imported glossary commitment was rebased transparently. No production
immutability check was bypassed.

Both raw threshold responses recognized that 28 days lies in the categories;
the corrected condition also calculated the boundary ratio 600/400 = 1.5.
Both failed publication, respectively on response-field placement and quotation
attribution. The latter also contains further undeclared/incorrectly attributed
numeric quotations. This comparison demonstrates a possible bounded methodological
inference, **not a measured improvement in accepted synthesis after correction**.

## S3 results and scientific review

All 12 historically accepted objectives were executed, including the weak
question-supported controls, plus five neutral counterparts. All 17 abstained.
Some correctly identified missing evidence; others substituted the collection
question for the actual assigned task. For example, the growth/invasiveness
comparison was rejected for lacking infection-versus-malignancy kinetic data.
IgG4 descriptive comparisons were similarly rejected for lacking doubling times.
Abstention prevented unsupported publication, but these reasons do not establish
that every narrower opportunity was exhausted.

The rubric below uses **P** = adequate for the scoped claim, **M** = mixed,
conditional or requiring review, **F** = unsupported/incorrect, **–** = not
applicable. PV uses the A–D proposal categories. E = evidence adequacy;
S = source grounding; L = logical validity; Q = quantitative validity;
N = novelty; U = usefulness; C = epistemic calibration. No total score is computed.
“Abstain” records the publication decision; M/F can still identify a faulty
abstention reason. Structural rejection is separate from scientific rejection.

| S3 attempt | PV | E | S | L | Q | N | U | C | Review decision | Controller result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `control-endpoint-background` | A | P | M | M | – | integration | M | M | review | published |
| `control-feature-effect-background` | A | P | M | M | – | integration | M | M | review | rejected |
| `control-threshold-corrected-v2` | A | P | M | P | M | integration | P | M | review | rejected |
| `control-threshold-original-v2` | A | P | M | P | M | integration | P | M | review | rejected |
| `geometry-ambiguous-protocol-B` | A | F | P | P | – | none | M | P | abstain | abstained |
| `geometry-area10-A` | A | P | P | P | P | derived | P | P | accept | published |
| `geometry-area10-B` | A | P | M | F | M | mixed | F | F | reject | rejected |
| `geometry-changing-shape-A` | B | F | P | M | P | conditional | M | M | review | published |
| `geometry-changing-shape-B` | A | F | P | P | – | none | M | P | abstain | abstained |
| `geometry-diameter84-A` | A | P | P | P | P | derived | P | P | accept | published |
| `geometry-diameter84-B` | A | P | P | F | F | invalid | F | F | reject | published |
| `geometry-linear-A` | A | F | M | M | – | none | M | M | abstain | abstained |
| `geometry-linear-B` | A | F | F | F | F | invalid | F | F | reject | rejected |
| `geometry-unknown-growth-A` | D | F | M | M | P | conditional | M | M | review | published |
| `geometry-unknown-growth-B` | A | F | M | F | F | mixed | F | F | reject | rejected |
| `geometry-volume12-A` | A | P | M | P | M | derived | P | M | review | rejected |
| `geometry-volume12-B` | A | P | F | F | F | invalid | F | F | reject | rejected |
| `geometry-volume28-A` | D | P | P | F | F | invalid | F | F | reject | published |
| `geometry-volume28-B` | A | P | M | F | F | invalid | F | F | reject | rejected |
| `group-endpoint-feature-2-S3` | C | F | M | M | – | none | M | M | abstain | abstained |
| `group-igg4-2-S3` | C | F | M | M | – | none | M | M | abstain | abstained |
| `group-models-3-S3` | C | F | M | M | – | none | M | M | abstain | abstained |
| `group-models-4-S3` | C | F | M | M | F | none | M | M | abstain | abstained |
| `group-models-5-S3` | C | F | M | M | – | none | M | M | abstain | abstained |
| `group-pet-3-S3` | C | F | P | P | – | none | M | P | abstain | abstained |
| `larger-3-execution` | A | M | M | M | – | mixed | M | M | review | rejected |
| `larger-4-execution` | A | M | M | M | – | mixed | M | M | review | rejected |
| `larger-5-execution` | A | M | M | M | – | mixed | M | M | review | rejected |
| `medical-06-1-A` | D | F | M | M | – | none | M | M | abstain | abstained |
| `medical-06-1-B` | A | F | M | M | – | none | M | M | abstain | abstained |
| `medical-06-2-A` | B | F | M | M | – | none | M | M | abstain | abstained |
| `medical-08-1-A` | D | F | P | P | – | none | M | P | abstain | abstained |
| `medical-08-1-B` | A | F | P | P | – | none | M | P | abstain | abstained |
| `medical-08-2-A` | D | F | P | P | – | none | M | P | abstain | abstained |
| `medical-08-3-A` | D | F | P | P | – | none | M | P | abstain | abstained |
| `medical-10-1-A` | D | F | M | M | – | none | M | M | abstain | abstained |
| `medical-10-1-B` | A | F | P | P | – | none | M | P | abstain | abstained |
| `medical-10-2-A` | C | F | M | M | – | none | M | M | abstain | abstained |
| `medical-10-3-A` | D | F | P | P | – | none | M | P | abstain | abstained |
| `medical-11-1-A` | C | F | M | M | – | none | M | M | abstain | abstained |
| `medical-11-1-B` | D | F | M | M | – | none | M | M | abstain | abstained |
| `medical-11-2-A` | C | F | M | M | F | none | M | M | abstain | abstained |
| `medical-14-1-A` | B | F | M | M | – | none | M | M | abstain | abstained |
| `medical-14-1-B` | A | F | M | M | F | none | M | M | abstain | abstained |
| `medical-14-2-A` | A | F | M | M | – | none | M | M | abstain | abstained |

### Significant candidate findings, including rejected outputs

The original 60-generation experiment contains 27 proposition-shaped candidate
findings and seven malformed field-name strings in one response. Every candidate
is reviewed below; the strings are structural failures, not seven scientific
findings. Exact per-attempt tokens and source versions are in `summary.json`.

| Candidate / contributing units | Novelty type | Scientific decision and explanation |
| --- | --- | --- |
| `control-endpoint-background:f1` — `r3#f3`, `rb#f2` | integration / overclaim | **review**: Different task endpoints are a useful comparison; aggregate model scores do not isolate spiculation robustness or prove independent/orthogonal biological processes. |
| `control-feature-effect-background:f1` — `r3#f2`, `rb#f1` | integration / overclaim | **review**: Spiculation appears in both contexts, but feature selection does not establish a positive fast-growth effect or histological aggressiveness. |
| `control-threshold-corrected-v2:f1` — `r3#f1`, `rc#f1` | derived methodological inference | **review**: Boundary ratio 1.5 and a hypothetical 500-day classification contrast follow. They compare operational rules, not biological growth distributions. |
| `control-threshold-corrected-v2:f2` — `r3#f1`, `rc#f1` | integration / summary | **review**: Both rules include 28 days without establishing cohort-specific short-interval evidence. Much repeats the corrected qualification; further numeric quotation errors remain. |
| `control-threshold-original-v2:f1` — `r3#f1`, `rc#f1` | integration | **review**: Both category rules include 28 days; membership is not an observed subgroup. Correct core, invalid output placement and numeric/quote declarations. |
| `geometry-area10-A:f1` — `r1#f1`, `r2#f1` | derived inference | **accept**: Area doubles in 10 days under fixed-shape exponential growth, so linear size doubles in 20 days. |
| `geometry-area10-B:f1` —  | invalid inference | **reject**: Five days reverses the correct time scaling. |
| `geometry-area10-B:f2` — `r1#f1`, `r2#f1` | derived inference | **review**: Twenty days is correct, but coexists with a contradictory first finding and invalid fields/calculation encoding. |
| `geometry-changing-shape-A:f1` — `r1#f1`, `r2#f1` | counterfactual derived inference | **review**: The constant-shape 84-day theorem is correct under the added assumption, which conflicts with the supplied varying-shape model. |
| `geometry-diameter84-A:f1` — `r1#f1`, `r2#f1` | derived inference | **accept**: Correct conditional volume interval, 28 days; artificial mathematical result only. |
| `geometry-diameter84-B:f1` — `r1#f1`, `r2#f1` | invalid inference | **reject**: 252 days is wrong; 84/3=28 days is required. |
| `geometry-linear-B:f1` — `r1#f1`, `r2#f1` | invalid inference | **reject**: No constant interval follows; first diameter doubling occurs at 196 days. Proposition and calculations also disagree. |
| `geometry-unknown-growth-A:f1` — `r1#f1`, `r2#f1` | conditional theorem / unsupported bound | **review**: 84 days follows only after adding exponential growth. Observations alone establish no such lower bound or unique interval. |
| `geometry-unknown-growth-B:f1` —  | invalid inference | **reject**: Neither an exponential trajectory nor the proposed conversion is established. |
| `geometry-unknown-growth-B:f2` — `r1#f1` | repetition | **reject**: Restates the input cubic relationship. |
| `geometry-unknown-growth-B:f3` — `r2#f1` | repetition | **reject**: Restates the input two-observation volume change. |
| `geometry-volume12-A:f1` — `r1#f1`, `r2#f1` | derived inference | **review**: 36 days is correct; the declared calculation is malformed, so no publication. |
| `geometry-volume12-B:f1` —  | invalid inference | **reject**: Proposition gives a false interval while explanation reaches and abandons the correct 36-day result; remaining entries are malformed labels. |
| `geometry-volume28-A:f1` — `r1#f1`, `r2#f1` | invalid inference | **reject**: 9.33 days is arithmetically consistent division but scientifically wrong mapping. Published unverified. |
| `geometry-volume28-B:f1` — `r1#f1`, `r2#f1` | invalid inference | **reject**: Same wrong mapping despite removing the anticipated answer; also omits the second numeric operand. |
| `larger-3-execution:f1` — `r1#f2`, `r3#f3`, `rb#f2` | integration / grounding gap | **review**: Task comparison has merit, but the selected baseline-tool unit does not itself identify spiculation; other supplied premises must not be borrowed silently. |
| `larger-3-execution:f2` — `r3#f1`, `r3#f2`, `r3#f3` | summary / repeated gap | **reject**: Repeats the known absence of four-week etiological data and uses units from only one memory. |
| `larger-4-execution:f1` — `r3#f2`, `rb#f2`, `re#f1` | integration / overclaim | **review**: Different feature roles are compared, but adverse direction/robustness is not established by selected-feature presence. |
| `larger-4-execution:f2` — `r3#f1`, `rc#f1` | invalid inference | **reject**: Category boundaries and unspecified SSN etiologies do not establish observed malignant/benign kinetic overlap. |
| `larger-4-execution:f3` — `r3#f3` | repetition | **reject**: Repeats r3#f3 model-performance statement from one parent. |
| `larger-5-execution:f1` — `r1#f1`, `r3#f3`, `ra#f1`, `rf#f3` | integration / incompatible comparison | **review**: Different endpoints and moderate texture performance do not establish a general high-accuracy CT versus blood-marker contrast. |
| `larger-5-execution:f2` — `rg#f1`, `ra#f1` | summary / unsupported comparison | **reject**: Repeats PET mismatch proportions; absent blood-marker/SUVmax correlation does not establish added PET discrimination over SUVmax. |

The threshold-ratio candidate is a small, defensible comparison of **operational
definitions**, under the qualification that boundaries are not measured
distributions. A hypothetical 500-day value would fall into different categories
under the two rules. This does not establish an observed cross-population growth
difference, diagnostic superiority or the etiology of a four-week doubler.
It was not published. The distinct-prediction-task comparisons are also useful
directions, but their generated explanations overstate individual feature effects,
population compatibility or independence. None was silently rewritten into a
successful scientific finding.

The output contains three clear repetitions: two restated mathematical premises
and a restatement of the existing nomogram-performance finding. Larger responses
also repeat gap statements and sometimes make multiple versions of the same
feature-context claim. Novelty comparisons marked `distinct` do not establish
novelty when the proposition merely rephrases an input.

## Answer guidance and mathematical controls

Twelve A/B pairs have byte-identical scientific units, novelty evidence and all
non-objective context. A receives the complete original S2 proposal; B receives
a neutral task and necessary conditions. This preserves evidence, but it is not
a uniformly clean causal ablation: some neutral tasks broaden or change the
original objective. In particular, `medical-11-1-B` asks about growth categories
while its selected inputs are a radiologic model and a PSP finding; exclude it
from conclusions about answer contamination. Negative geometric pairs also
contrast counterfactual versus actual-assumption questions.

The four positive conversions are the clearest comparison:

| Premises / ground truth | Full S2 guidance, A | Neutral guidance, B |
| --- | --- | --- |
| Exponential volume doubling 28 days, cubic geometry → diameter 84 days | Wrong 9.33 days, published | Wrong 9.33 days, rejected for missing operand |
| Exponential diameter doubling 84 days, cubic geometry → volume 28 days | Correct 28 days, published | Wrong 252 days, published |
| Exponential volume doubling 12 days → diameter 36 days | Correct 36 days, rejected for malformed calculation | Wrong/internally inconsistent answer and malformed findings |
| Exponential area doubling 10 days, square geometry → linear size 20 days | Correct 20 days, published | Both 5 and 20 days in one malformed response |

The formal check is independent of the model's chosen operation:
`D(t)=D0·2^(t/(3·TV))`, so `TD=3·TV`. At the erroneous time `TV/3`, diameter
has increased only by `2^(1/9)`, not doubled. The reverse conversion is `TV=TD/3`.
[scientific_review_oracles.py](../scripts/scientific_review_oracles.py) checks
explicit fixture assumptions; it is not a prose parser or production S4.

For **linear volume growth** `V(t)=V0(1+t/28)`, the first diameter doubling is
196 days and there is no constant diameter-doubling interval. A abstained with a
faulty explanation about missing geometry; B invented an incorrect constant
interval and contradictory calculations. For an **unspecified trajectory**,
the same two volume observations permit different future doubling intervals;
A added exponential growth and overstated an 84-day lower bound. Its conditional
exponential theorem is true, but is not entailed by the original observations.
For **varying shape**, A explicitly substituted constant shape and published an
84-day counterfactual; B correctly recognized underdetermination. The **ambiguous
“size doubled”** case produced S2 `no_candidate`; an explicitly investigator-assigned
S3 probe also abstained appropriately.

The same-Qwen critique independently writes the correct 84-day derivation and
states that the candidate must be rejected, yet returns top-level `verdict=accept`.
This disagreement is preserved. Agreement fields or a second call to the same
model cannot be treated as scientific verification. No production review stage
was introduced.

## Group size and scientific usefulness

Production discovery currently yields **134 groups**, retaining all 95 baseline
groups. Audit correction: the previous report's 128 count describes an earlier
scoring snapshot; its final-ranking artifact and current code contain 134.
No ranking weights were tuned during this evaluation.

| Controlled group | Memories / units | Existing S1 rank | S2 ideas | S2 input / output tokens | Ordinary S3 execution |
| --- | ---: | ---: | ---: | ---: | --- |
| models-2 | 2 / 2 | 1 | 2 (reused) | 2,417 / 969 (reused) | Two-memory prior attempts; abstained |
| models-3 | 3 / 5 | 18 | 3 | 5,677 / 1,531 | Two-memory subset; abstained |
| models-4 | 4 / 5 | 25 | 3 | 6,047 / 1,206 | Two-memory subset; abstained |
| models-5 | 5 / 5 | 33 | 3 | 6,467 / 1,218 | Two-memory subset; abstained |
| igg4-2 | 2 / 3 | 74 | 2 | 3,197 / 851 | Two-memory subset; abstained |
| endpoint-feature-2 | 2 / 4 | curated | 2 | 3,156 / 915 | Two-memory subset; abstained |
| pet-3 | 3 / 5 | curated | 2 | 4,282 / 1,091 | Two-memory subset; abstained |

Selection was investigator-controlled, even when the group already existed in
the production pool; it was not an autonomous choice of all top-ranked groups.
The five-memory group is broadly about lesion characterization, but its systemic
biomarker component is a weak mechanistic bridge. Diversity alone does not
establish scientific complementarity.

All six newly generated group plans proposed ideas: 15 objectives in total.
Their ordinary S3 executions each selected two memories. Consequently those runs
do not test five-memory execution merely because S1 supplied five memories.
The additional neutral three-/four-/five-memory execution controls explicitly
supplied all selected units; all were rejected. Their raw findings respectively
used up to three, three and four memories in an individual proposition, with
lesser subsets or repeated premises in other findings. There is no observed
larger-group success advantage. Larger inputs also change scientific content,
so this is not a controlled estimate of group size alone.

## Confirmed defects and targeted corrections

1. **Substantive evidence admission.** The old rule counted distinct referenced
   memories, even if only one contained substantive evidence. Three formerly
   accepted proposals used questions this way. The new S2 and S3 check requires
   substantive premises from two memories; questions/definitions do not count.
   Equations, qualified claims, inferences and hypotheses remain eligible for
   conditional reasoning, without being labelled empirical proof. Old pending
   invalid objectives fail durably before a new dispatch. Historical completed
   records remain readable. Revalidation retains nine of the original 13 proposals,
   versus 12 under the earlier structural rule.
   This check uses declared roles; it cannot recognize a definition disguised as
   an ordinary claim, establish study independence or prove scientific truth.
2. **Lossless scientific storage.** A real response's first proposition was an
   ordinary capitalized sentence containing a colon. Compact parsing mistook it
   for a field label and created an empty proposition. Synthesis now tries compact
   output, then the existing expanded layout when needed; both require a validated
   lossless round-trip. No scientific strings or validation results are repaired.
   Offline replay of identical saved messages/response now publishes that memory
   with exact text, provenance and `scientific_validation=unverified`. Its scientific
   overclaims remain, so this is a storage correction, not a research success.

`architecture.md` clarifies only substantive contributions and the lossless
formatting fallback. Prompts, research strategies, provider configuration and
the active corpus were not changed. No general scientific-equivalence classifier,
growth-law text heuristic or production S4 was added.

## Recommendations and readiness

| Priority | Recommendation | Evidence / expected value / cost |
| --- | --- | --- |
| 1 | Keep the assigned scientific task distinct from collection questions throughout S3. Test objective-first/background presentation with genuinely matched tasks. | Confirmed task substitution in saved reasons; question-metadata ablations produced candidates. High expected value, low-to-medium implementation cost; exact causal contribution remains unresolved. |
| 2 | Add assumption- and quantity-aware verification for formal deductions, with independently checked equations/counterexamples. | Confirmed wrong mappings pass scalar arithmetic and publish. High value; medium cost for declared mathematical domains, much larger for general science. Avoid fragile prose-keyword “proof.” |
| 3 | Strengthen source-grounded R3 extraction and preserve exact supporting passages, uncertainty, metric associations and study design. | Multiple verified extraction errors and unsupported attribution. High value, medium cost; prompt instructions alone did not prevent propagation. |
| 4 | Improve representation at the quotation boundary and finding-level failure diagnostics without weakening attribution. | Correct-looking `>` versus stored `&gt;` fails literal checks; misplaced novelty rows reject complete responses. Medium value/cost. Version any normalization explicitly; do not repair model outputs after the fact. |
| 5 | Evaluate objective quality and group coherence before tuning diversity/yield. | Larger groups generated more speculative plans and still executed two-memory subsets. Medium value; requires varied, preferably blinded review cases rather than this one corpus. |
| 6 | Investigate independently validated scientific review as a separate design decision. | Same-model critique's verdict contradicts its own correct derivation. Potentially high value, uncertain cost/reliability. An extra LLM vote alone is insufficient. |

Confirmed defects above differ from likely weaknesses such as root-context
dominance, and from unresolved questions about optimal group size or a general
verification stage. Supervised disposable experiments are justified. Broader
autonomous publication of scientific conclusions is **not yet justified** by these
results. Better grounding and derivation checking should precede that claim.

## Verification, preservation and reproduction

**516 tests passed, zero failures/errors/skips, 125.284 seconds.** The complete
suite includes R1–R5, glossary, provenance, deterministic ranking, context limits,
attempt registration, historical formats and crash/journal recovery. New tests
cover substantive versus contextual support, legitimate equations/hypotheses,
historical completed records, durable pre-dispatch rejection, exact mathematical
oracles, incompatible populations/endpoints, shared primary evidence and causal
limitations, literal-prose round trips, corrected-branch provenance, stopped
diagnostic selection, call uncertainty and completed-critique recovery.
These tests do not claim to certify arbitrary generated scientific reasoning.

The final audit checked **3,268 pre-existing files**. Its only change is the
authorized clarification in `architecture.md`; all other protected files are
unchanged, with no new corpus files. The active canonical revision and its
16 memories/one equation are unchanged. This includes original/legacy research,
private inputs, original logs, all prompts, `futureWork.md`, earlier synthesis
reports and `AGENTS.md`. `git diff --check` passed. Full-suite results are in
[latest.md](latest.md) and local `final-tests.stdout`/`final-tests.stderr`.

Complete local diagnostics are under `log/scientific-synthesis-evaluation-20261102/`:
`generation-ledger.json`, `services.json`, `generation-artifact.json`,
`calls/01..60/`, `trials/*/result.json`, execution logs, `proposal-audit.json`,
`source-audit.json`, `source-review.json`, `primary/manifest.json` and primary XML,
`summary.json`, `finding-review-inputs.json`, rubric decisions, paired-input checks
and preservation manifests. Every trial records its disposable corpus/journal path.
Generated and rejected scientific content remains local, not committed.

Setup failures are retained separately: a fixture allocator error, protocol-token
budgeting that inadvertently reached R5, refused in-place unit correction,
experimental import/commitment setup errors, and a missing derived-critique output
directory. The completed critique was recovered from its durable call-60 response
without generation. No uncertain external submission was acknowledged. Completed
scientific failures were never resubmitted to obtain a preferred result.

Offline accounting can be regenerated without model service access:

```sh
PYTHONPATH=src python3 scripts/evaluate_scientific_synthesis.py \
  --output log/scientific-synthesis-evaluation-20261102 summarize
PYTHONPATH=src python3 scripts/run_tests.py
```

For a new generation experiment, choose a new diagnostic directory and run the
documented `existing`, `geometry`, `groups`, `corrections`, `larger-execution` and
`critique` phases, retaining the private corpus and prior S2 artifacts. Baseline
reproduction requires baseline source at `04f751d`; current admission/storage
corrections intentionally change behaviour. The mathematical fixtures are defined
controls, not invented clinical observations. Source versions, exact messages and
raw outputs permit inspection without rerunning generation. The earlier reports
remain unchanged: [discovery](synthesis-discovery-experiment.md),
[production](knowledge-unit-synthesis-production-20261102.md), and
[S1/S2 planning](s1-s2-planning-improvement-20261102.md).
