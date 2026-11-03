# State of Research Viewer and adversarial generation evaluation

Implemented on `main`, 2026-11-03. Baseline: `300a6b946ccdf268473df6ea3fa235df47041235`.

## Executive summary

Mira now generates and displays a snapshot-bound scientific overview through its existing local viewer. The tool projects complete canonical knowledge units, runs the approved SOR1 author, SOR2 challenger and SOR3 revision stages, validates references and inventories, and publishes Markdown, HTML and an audit atomically with rollback. Viewing never invokes inference.

A genuine medical paper was generated from **46 units in 16 research memories**, with **45 units cited**, **nine open question units**, one recorded equation and **zero published synthesis memories**. No new research experiment was started. All 3,472 pre-existing memory files are unchanged; only the three derived report files were added.

**Same-model adversarial review helped the seeded quantitative and incompatible-evidence cases, but did not establish reliable medical synthesis.** The medical revision corrected the unsupported infectious classification of LIP and an invented link between IgG4 disease and spiculation. It retained a faulty interpretation of a ≤400-day category and introduced a stronger, unsupported “explicitly excludes” assertion. These and other remaining concerns are visible beside the relevant text and in the report's concerns section. The paper is an inspectable, qualified research overview, not a scientifically cleared diagnostic answer.

The experiment used **42 genuine Qwen calls**: 13 author, 13 challenger and 16 revision calls. Two calls beyond the approximately-40 planning target addressed a count-validation diagnostic and a malformed citation; they were not repeated sampling for a more favorable medical conclusion. All responses, including rejected ones, remain in private diagnostics. The final complete regression and browser results are recorded below.

## Commands and interface

```bash
PYTHONPATH=src python3 -m mira state-of-research-generate
PYTHONPATH=src python3 -m mira viewer
PYTHONPATH=src python3 -m mira state-of-research-view --open
```

The existing viewer at <http://127.0.0.1:8767/> has a **State of Research** workspace alongside Research Overview, Knowledge Explorer, Knowledge Relationships, Decisions and Glossary. Generation defaults to the active corpus and a maximum of 40 calls; `--experiment`, `--max-calls`, `--llm-url`, `--model`, `--max-tokens`, `--timeout`, `--log-dir` and `--resume GENERATION_ID` provide explicit selection and bounds. The default model endpoint is the existing local service, with deterministic temperature, disabled thinking and structured JSON output. External model endpoints are rejected.

`state-of-research-view` reads an existing report; `--format markdown`, `--format html` and `--format json` inspect its views/audit without inference. Use the viewer for working Brain and Glossary navigation. The HTML contains its CSS and JavaScript without remote libraries or fonts.

Derived outputs, preserved locally:

```text
memory/research/state_of_research.md
memory/research/state_of_research.html
memory/research/state_of_research.audit.json
log/state-of-research-20261103/       # private experimental diagnostics
```

The HTML presents all 13 standard scientific sections, a canonical glossary, real-source bibliography and knowledge inventory. It includes section navigation, incremental Unicode-normalized full-report search, keyboard navigation and temporary highlighting. Unit links open Brain details; glossary links open the canonical entry. Brain details link back to the paper. Original drafts, reviews, rejected objections, revisions and provenance are collapsible. An intervening canonical revision produces the explicit warning **“Research has changed since this report was generated.”**

The APIs extend the existing server:

- `GET /state-of-research?experiment=NAME`: validated saved paper, rendered with current freshness status.
- `GET /api/experiments/NAME/state-of-research`: audit, current revision and stale flag.

No generation endpoint or inference-on-page-load was added.

## Implementation and safeguards

New modules separate evidence projection/generation (`state_of_research.py`), contracts/checks (`sor_contracts.py`), safe rendering (`sor_view.py`) and CLI handling (`sor_cli.py`). They reuse the existing `mira.research-state/1` snapshot, canonical glossary reader, model client/tokenizer, local viewer, corpus locks and atomic export machinery. No separate scientific database or canonical schema was introduced.

Every unit retains its complete recorded fields, qualifications, epistemic type, version, source identifiers, question state, evidence status and available equation/lineage data. Research-node grouping creates bounded batches; no scientific field is shortened. The coverage ledger distinguishes considered units from cited units. The overview's representative subset is explicitly identified as partial, including omitted IDs. Processed-source counts are distinct from sources yielding retained units.

Reference validation covers declared and inline unit IDs, malformed anchors, explicit source/glossary references and unrecorded DOI/PMID citations. Bibliography, canonical equations/variables/units/assumptions, inventory counts and glossary provenance are rendered from actual records. An invalid model **process/count** paragraph may be withheld and disclosed while canonical bookkeeping is rendered directly; its exact text remains in the audit. This mechanism does not rewrite scientific prose or allow invalid scientific paragraphs through reference validation.

Model objections must quote a real draft assertion and cite supplied units. The final contract binds the quoted paragraph and claim ID in the JSON schema. “Admitted” means quotation/reference checks passed, **not** that the criticism is scientifically correct. Each admitted objection receives an accepted, rejected, partially accepted or unresolved revision disposition.

Requests, exact prompt sources/hashes, raw responses, parsed results, token budgets, elapsed times and dispositions are retained privately. Received responses can be reused after interruption; prepared/uncertain submissions require human review and are not automatically acknowledged or resubmitted. Safe resume checks model name and artifact identity; mutable server-properties observations are retained separately.

Publication requires a completed, validated audit, matching source hash and unchanged experiment identity. Files are staged and individually replaced with rollback if publication fails; the audit is the final publication marker used by the viewer. Readers revalidate saved content instead of trusting a cached verdict. Active writers and pending journal recovery block access/publication. A changed revision within the same experiment stays associated with its original snapshot and is marked stale. No locks span model inference.

## Actual medical corpus and paper

Research question, unchanged:

> Does a spiculated pulmonary lesion apparently doubling in volume over approximately four weeks favour infection over malignancy, and how strongly?

Experiment: `medical-retrieval-repair-20261031`; strategy: `medical`.

Canonical revision: `65e248a831a23f6b3eb4f61e1bd03b1d20b1831b0d7e2c2ec84e1aae8834d3ee`.

Frozen evidence-projection SHA-256: `5a4cabaf2cc427b7e6c01ecaf604e773cb6fa816605d2c57141da729c62f04f2`.

Paper ID: `6ad01e2879884d6ca7972e716bd311c8`; generated/assembled at `2026-11-03T03:58:05.013257+00:00`. Subsequent rendering/validation added explicit concerns without changing model scientific paragraphs or canonical records.

| Observed inventory | Count |
| --- | ---: |
| Research / synthesis memories | 16 / 0 |
| Knowledge units considered | 46 / 46 |
| Units cited in initial / final narrative | 45 / 45 |
| Structural findings / questions / equations | 36 / 9 / 1 |
| Scientific findings / claims / inferences | 30 / 5 / 1 |
| Processed source IDs / source IDs yielding units | 81 / 16 |
| Living / split research nodes | 9 / 4 |
| Answered / exhausted / killed nodes | 0 / 0 / 0 |
| Open question units | 9 |
| Canonical glossary entries | 32 |

Research-state revision remains 251, root `q1` remains split and active `q6` remains living. Recorded 228 research cycles and 18 legacy synthesis cycles are activity counters, not successful-synthesis counts. No modern unit-synthesis register is recorded; missing selection/attempt history remains unknown. All 46 units lack an explicit evidence-status field. None was silently certified.

Scientific observations **as recorded in the corpus**, rather than independently verified conclusions:

- Screening models identify spiculation as a malignancy predictor; their multivariable-model AUC must not be interpreted as a patient-specific likelihood ratio for four-week growth (`r1#f1–f2`).
- LIP, inflammatory pseudotumor and IgG4-related disease are recorded malignant mimics. A mimic is not thereby proven infectious, and the sources do not establish comparative four-week kinetics for this question.
- The subsolid-nodule study groups VDT ≤400 versus >400 days. **28 days satisfies ≤400**; that does not demonstrate that a 28-day subgroup was observed or separately analyzed. A faulty qualification already present in `r3#f1` was propagated by the author and missed by the corrected-contract challenger.
- The PSP cohort records 6/17 lesions below a 600-day VDT threshold, with retrospective, single-centre and small-sample limitations. It does not establish diagnostic preference for infection in the requested scenario.
- CT radiomics, FLT/FDG distributions and hematological indices concern different populations, endpoints or modalities. They do not directly supply the requested comparative diagnostic strength.
- The exact recorded equation is `TVDT = (t * ln(2)) / ln(V2/V1)`. Its model-reported/unverified provenance and absence of explicitly recorded assumptions remain visible; displaying an equation does not validate its empirical applicability.

The justified high-level conclusion is limited to the saved corpus: it does not quantify how strongly the specified lesion favors infection over malignancy. No patient-specific risk or treatment recommendation was derived. The paper contains source findings and model interpretations, **not published synthesized discoveries**.

Citing 45 units does not mean explaining every proposition. `rd#f2` is uncited; the peripheral COP relapse proposition `r4#f2` is referenced in a unit list without its numerical content being narrated. Neither omission supplies missing comparative four-week evidence. All complete units remain in the frozen audit and coverage ledger.

## Comparative method

Cases used the same model/settings. A used the actual frozen corpus; B and C used clearly labelled synthetic fixtures committed in `tests/sor_fixtures.py`, never installed in active memory. B had a genuine author baseline followed by a fixed erroneous candidate. C included both an unmodified author baseline and a fixed erroneous pooling candidate. These are controlled error challenges, not estimates of natural error frequency.

Counts below are **retrospective agent adjudications against the frozen records**, not independent clinical review or verification of the original papers. Distinct underlying error families are counted once even when repeated. Categories overlap and must not be added into a single score. An incorrect conclusion despite a relevant citation is separate from a nonexistent citation. Missing qualifications are distinguished from missing whole evidence themes.

Reference resolution was checked programmatically. Citation adequacy was assessed across paragraphs labelled `source_finding`, `interpretation` or `hypothesis`, requiring the supplied citation set and report context to support the statement and material qualifications. Its denominator changes with revision. Material errors in paragraphs labelled `limitation` are still counted in the error register, but are outside that percentage; this classification dependence makes the percentage optimistic. Neither metric establishes scientific truth.

### Case A — actual research

| Metric | Initial draft | Final assembled paper |
| --- | ---: | ---: |
| Resolved paragraph-to-unit links | 163/163 (100%) | 166/166 (100%) |
| Agent-assessed citation adequacy, labelled scientific paragraphs | 26/36 (72.2%) | 28/34 (82.4%) |
| Unsupported assertion families | 6 | 5 |
| Invalid citations | 0 | 0 |
| Incorrect mathematical relationship families | 1 | 1 |
| Missing major qualifications | 2 | 2 |
| Invalid cross-study pooling/claimed contradiction | 0 | 0 |
| Incorrect published-synthesis claims | 0 | 0 |
| Important root-question evidence omissions identified | 0 | 0 |
| Material themes represented | 5/5 | 5/5 |
| Wrong model inventory-count families | 1 | 0 published; 1 withheld |
| New error families relative to initial draft | — | 1 |

The five themes are screening morphology, benign/inflammatory mimics, growth/VDT mathematics, adjunct imaging/biomarkers, and unresolved questions/synthesis status. Presence is not accuracy.

The unsupported-family register is inspectable by paragraph ID:

| Family | Initial examples | Final outcome |
| --- | --- | --- |
| LIP conflated with infection | `group-01.f2` | Corrected to inflammatory |
| A question's four-week infection premise repeated as fact | `group-04.c1`, `overview.prog_1` | Remains flagged |
| Later regression treated as incompatible with earlier rapid growth | `group-02.c1` | Remains flagged |
| IgG4 source said to imply spiculation | `group-05.c1` | Removed |
| Questions used as empirical findings/interpretations | `group-03.conflicts-1`, `group-08.find-2`, `group-08.conf-1` | Reduced; `group-08.conf-1` remains |
| Snapshot absence generalized to no data existing | `overview.prog_1` | Remains flagged |
| “Not evaluated” strengthened to “explicitly excludes” | Absent initially | Introduced at `group-06.c1`; flagged |

The two major omitted qualifications concern `r7#f1`'s unresolved PIPT/PIMT distinction with untested markers and `r7#f2`'s inability to exclude spontaneous regression. The mathematical family occurs at `group-01.c1` and `.l1`: the revised paper still wrongly says the ≤400-day definition does not encompass four weeks. The renderer supplies an adjacent arithmetic warning; the model text is not hand-repaired.

Operationally, the original nine challenger calls produced **32 objections**, all rejected for failing exact-quotation checks. Their raw text remains retained; some contained useful observations, so structural rejection must not be equated with scientific falsity. The subsequent corrected-contract review of the original first batch produced six structurally admitted objections: **one justified and five incorrect/no-op or misdirected objections** under this assessment. The latter included saying the draft omitted “subsolid,” despite that word already being present, and demanding outside clinical knowledge absent from the supplied records.

Representative comparison:

- Original: “this infectious/inflammatory etiology” (`group-01.f2`). The challenger correctly objected to unsupported infectious attribution. Revised: “this inflammatory etiology.”
- Original and final: ≤400 days “does not encompass” four weeks. The valid-contract challenger missed the range error. An earlier, structurally rejected review had noticed it; an intermediate revision corrected it, but the later exact-contract revision reintroduced it. A resolving citation did not protect against this error.
- Original: the source “does not evaluate” the requested features. Revised: it “explicitly excludes” them. This is an additional unsupported source-method claim, even though the paragraph is labelled a limitation.

The apparent citation-adequacy improvement therefore does **not** justify declaring the medical paper reliable or attributing all changes to successful adversarial criticism. Much of the initial criticism was inadmissible, and revisions sometimes changed text without supported criticism.

### Case B — quantitative error challenge

The fixture explicitly states fixed shape, `V ∝ D³`, constant exponential growth, synthetic volume doubling in 28 days and conditional diameter doubling in 84 days. It is not pulmonary-lesion evidence. The unmodified author baseline was retained. The fixed candidate instead asserted identical 28-day volume/diameter doubling and that this “proves” infection.

| Metric | Seeded candidate | After review |
| --- | ---: | ---: |
| Citation adequacy, labelled scientific paragraphs | 0/1 | 1/1 |
| Invalid reference links | 0 | 0 |
| Unsupported diagnostic assertions | 1 | 0 |
| Incorrect mathematical relationships | 1 | 0 |
| Missing major assumptions: fixed shape, constant growth | 2 | 0 |
| Incompatibility/contradiction-handling errors | 0 | 0 |
| Incorrect synthesis-status claims | 0 | 0 |
| Important whole-evidence omissions | 0 | 0 |
| Material themes represented | 2/3 | 3/3 |
| New revision errors identified | — | 0 |

The challenger produced **one justified objection and one false/no-op objection** to the already-correct fixture disclaimer. Revision accepted the mathematical/diagnostic criticism and rejected the disclaimer objection. Its corrected statement explicitly gives `T_D = 3 × T_V`, hence 84 days for the synthetic 28-day volume interval, retains both assumptions and withdraws the infection conclusion.

### Case C — incompatible evidence

The two synthetic records concern adult screening CT/malignancy OR 1.8 versus childhood radiographs/fever-persistence OR 0.4. Neither measures four-week growth. These invented values are test data, not scientific results.

The unmodified author correctly kept them separate. Initial and revised baseline drafts had **0 unsupported assertions, 0 invalid citations, 0 mathematical errors, 0 missing major qualifications, 0 pooling errors, 0 incorrect synthesis claims, 0 important evidence omissions**, and covered all three incompatibility themes. Citation adequacy was **3/3 → 3/3**. Nevertheless, the challenger returned **four objection-shaped endorsements**, each classified as a demonstrated error while explaining that no error existed. Revision accepted all four. There was no measurable scientific benefit.

A fixed separate candidate then divided 1.8 by 0.4 to claim a 4.5-fold diagnostic advantage for infection:

| Metric | Seeded candidate | After review |
| --- | ---: | ---: |
| Citation adequacy, labelled scientific paragraphs | 0/1 | 3/3 |
| Invalid references | 0 | 0 |
| Unsupported diagnostic assertions | 1 | 0 |
| Arithmetic errors | 0 | 0 |
| Missing qualifications: population, endpoint, modality, growth measurement | 4 | 0 |
| Invalid pooling/compatibility errors | 1 | 0 |
| Incorrect synthesis-status claims | 0 | 0 |
| Important whole-evidence omissions | 0 | 0 |
| Incompatibility themes adequately represented | 0/3 | 3/3 |
| New revision errors identified | — | 0 |

The challenger had **one substantively justified incompatibility objection and one false/no-op objection** to the disclaimer. Its core objection was useful, but also incorrectly called the arithmetic operation wrong: `1.8 / 0.4 = 4.5` is arithmetically correct; the statistical/diagnostic interpretation is invalid. Revision withdrew the advantage claim, separated the actual endpoints and retained the disclaimer. This demonstrates error correction on this fixed candidate, not general proof of reviewer reliability.

## Operational results and implementation defects

Model: **Qwen3.6-35B-A3B-Q4_K_M.gguf**, served locally at `127.0.0.1:8090`; active context **16,384 tokens**. Artifact SHA-256: `671e47e0ec53c665d048b98c3ecbfd5236b5ca9c3e02ed19fc8f81f7b85140c7`. Temperature 0, thinking disabled, JSON-schema output, 4,096 output-token reserve. All three roles used the same model.

The only new prompt templates match the owner's supplied text verbatim:

| Template | SHA-256 |
| --- | --- |
| SOR1 | `03343d2f3a0a0c369f121716b21f438968e5371bd314cba099fdb86e0460ec93` |
| SOR2 | `2f8870d17ee815343c78fd5bd79a17a23896ed1cfc7711a885377353710fce34` |
| SOR3 | `35450f18c9c8813e1c549242224409999d069908d57943bbaf3cd18a1b2b4506` |

| Observed execution statistic | Value |
| --- | ---: |
| Genuine generation calls / received responses | 42 / 42 |
| SOR1 / SOR2 / SOR3 calls | 13 / 13 / 16 |
| Actual-corpus generation plus diagnostics, including two failed author candidates | 34 |
| Quantitative / incompatible baseline / incompatible seeded calls | 3 / 3 / 2 |
| Report-associated calls, excluding failed initial author candidates and controlled fixtures | 32 |
| Reported input tokens | 238,158 |
| Reported output tokens | 63,203 |
| Reported total tokens | 301,361 |
| Sum of model-request elapsed times | 1,329.298 s (22 min 9 s) |
| First-to-last generation wall time, including development/interruption gaps | 3,394.131 s (56 min 34 s) |
| First generation submission | 03:01:30.839557 UTC |
| Last response completed | 03:58:04.970422 UTC |
| New source-provider searches / canonical research actions | 0 / 0 |

Task work began at **02:52:05 UTC**, with a three-hour upper bound of 05:52:05 UTC. The editor interruption was recovered from saved diagnostics. Twenty-six received responses were reused rather than resubmitted. Implementation, experiments, regression tests and browser verification were complete by approximately **04:28 UTC** (about **96 minutes** from the recorded start, including the interruption). The task finished before the time ceiling because the comparative cases, call allocation and validation scope were complete; no redundant generation was run to consume time.

Observed defects and corrections:

1. Initial output contracts permitted missing scientific citations and an inappropriate node ID in unit references. Separate scientific/contextual branches and supplied-ID enums now enforce their respective requirements. Two failed initial author outputs are retained.
2. Free-text critic assertions paraphrased rather than quoted. The corrected JSON contract binds exact received paragraphs/claim IDs. This fixed structural admission, **not** scientific precision.
3. An empty-objection revision grammar used an invalid empty enum; the zero-disposition contract now explicitly allows an empty array.
4. Overview contexts exceeded the model window. Revision partitions complete sections while retaining every cited supporting unit/objection. The final review splitter partitions complete paragraphs while retaining **all originally supplied evidence** and records partial-draft coverage. The actual tokenizer confirms every saved overview paragraph is covered exactly once in four bounded review groups: 12,180, 11,560, 11,286 and 11,562 input tokens, each plus the 4,096 reserve. Other review groups require 3,352–9,258 input tokens. A single unfit paragraph fails safely; it is never shortened.
5. The model confused 16 sources yielding units with 16 knowledge units. Two additional revisions, including explicit expected-count metadata, repeated the error. The deterministic renderer now withholds and discloses faulty process bookkeeping and renders actual counts. This is a harness correction, not an LLM scientific success.
6. An intermediate revision emitted `r6#2`. Broader malformed-anchor validation detected it; a diagnostic revision restored a resolving citation. The initial and published final comparisons have no invalid citations.
7. Valid inline citations omitted from redundant `unit_ids` arrays were initially rejected. Validation and coverage now account for both locations without modifying scientific text.
8. Browser testing exposed duplicate initial report loading and stale asynchronous responses. The workspace now loads after the scientific snapshot is ready and ignores superseded report responses. Real-browser search, focus retention, highlighting and cross-view navigation pass.
9. A regression fixture exposed a Python regular-expression group-slicing error in explicit source links. It was corrected and source-anchor resolution/determinism are tested.

The final bounded-overview **review** path was validated with deterministic model doubles and the real tokenizer, not a fresh full real-model generation. The approximately-40-call allocation was already consumed. This limits claims about future end-to-end behavior with a different set of long criticisms; token budgets and per-generation call limits still fail safely.

## Validation and preservation

**658 automated tests passed**, zero failures, errors or skips, **132.518 seconds**. This retains the existing 611-test baseline and adds 47 regression tests, including exact new prompt hashes, complete evidence/provenance, quotation binding, deterministic fixtures, malformed/unknown citations, equations, missing evidence, reviewer false positives, dispositions, call limits, received-response resume, uncertain submissions, complete-paragraph review/complete-section revision context partitioning, inventory withholding, safe deterministic rendering, source anchors, active writers, pending recovery, stale snapshots, publication rollback and preservation. Ordinary tests use temporary corpora and model doubles; no real inference is required. The production search JavaScript also executes under Node. Existing SQLite ResourceWarnings were logged without test failures. The ordinary result is saved in `test-results/latest.md`.

Real Chromium acceptance passed against the actual final corpus and paper: all scientific sections, meaningful abstract, exact canonical equation and units, nine open questions, zero-synthesis statement, 32 attributed glossary entries, unresolved `g30`, all unit links, 16 source links, review/revision history, disclosed inventory failure and remaining scientific concerns. Incremental Unicode search, arrow/Enter navigation, temporary highlighting, no-match messaging, mobile fit, paper→Brain, Brain→paper and paper→Glossary navigation passed. Existing Brain search, filters, graph, branch navigation, refresh, Decisions and human-review inspection also passed. Screenshots were visually inspected; assets/API requests stayed local. Source URL targets were inspected, not fetched from publishers during browser validation.

Active-writer, pending-recovery and stale-snapshot behavior were tested in temporary corpora; active research was not altered to manufacture these states. Private screenshots, raw model responses and execution logs remain ignored locally.

Before/after hashes verify **3,472 existing memory files unchanged, zero deletions**, and exactly the three derived report additions. Existing glossary exports, private inputs, canonical memories, source payloads, events, journal, research/synthesis state and SQLite files are unchanged. No experiment was initialized or reset. `architecture.md`, all **nine existing prompt files**, `futureWork.md` and `AGENTS.md` are unchanged. Only the three explicitly approved new SOR templates were added.

## Remaining limitations and owner-review proposals

The semantic reviewer is demonstrably fallible. Correct JSON, a resolving citation and an accepted revision disposition do not establish scientific correctness. Known medical-paper errors remain visible, and automatic publication is not expert approval. Some small node batches contain only questions, encouraging source-gap descriptions to be mistaken for empirical findings. The overview sees a representative subset; warnings cannot prove that every unsupported statement was found. Large corpora, a single oversized unit/paragraph, or lengthy aggregate reviews can exceed fixed context/call bounds and stop publication safely.

No protected file was changed to address these findings. Proposed wording for later owner approval:

- **SOR2:** “When no substantive supported error is found, return no objections. Do not list a correct assertion as an objection.”
- **SOR2:** “Do not demand findings from sources omitted from the supplied context, or introduce outside clinical knowledge as though it were supplied evidence.”
- **SOR1/SOR3:** “A recorded question's premise is not independent evidence. Do not strengthen ‘not evaluated’ into ‘explicitly excluded’.”
- **SOR3:** “Check inequalities as ranges. A cutoff does not show that observations occurred at every value satisfying it.”

A subsequent design review should consider a stronger scientific-adjudication/publication policy, balanced evidence/question batches, and explicit distinction between useful criticism, endorsements, duplicate objections and unsupported reviewer extrapolation. Those recommendations require separate review; they were not implemented through hidden prompt changes or edits to `architecture.md`.

## Commits and publication

Implementation: `fc9710aad6d665689f85f53c78b4c91d68730bab`.

Tests: `db80725b310a2e276b9eda567397ddae58cd6f51`.

The report and ordinary latest-test record are committed separately from implementation and tests. Completed authorized commits are pushed to `origin/main`, with synchronization verified in the completion response. Private research memories, generated papers/glossaries, model diagnostics and logs are excluded.
