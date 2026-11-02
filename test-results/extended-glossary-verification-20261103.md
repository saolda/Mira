# Extended scientific glossary verification

## Executive summary

The active glossary was independently reviewed against scientific society glossaries, professional guidelines, official terminology/technical documentation and original papers. All **32 original concepts**, including the **25 originally provisional-only concepts**, have an inspectable audit disposition. No new research experiment was started.

Twenty exact source definitions were admitted through the canonical journal: **19 formerly provisional concepts and one replacement for an unreliable MeSH description**. The existing technical-source GLCM definition was independently checked. Source support is terminology support, not a new clinical finding or formal scientific certification. No Qwen-generated wording was relabelled as a source quotation. The narrower usable-definition count reflects an unresolved meaning rather than concealing it as completed.

The most consequential correction is that the actual NLM organizing-pneumonia note conflates post-transplant organizing pneumonia with bronchiolitis obliterans syndrome. Its exact original attribution remains preserved, but that description is excluded from clinical use. This illustrates why an authority label cannot replace applicability and content review. The CT vacuole/airway comparison also concerned **two malignant groups**, not infection versus cancer.

**Final usable coverage: 31/32 concepts — five MeSH-defined, 21 directly source-defined and five provisional-only.** The remaining study-specific “natural air bronchograms” meaning is explicitly marked for clarification. One genuine G1 call used 3,998 tokens; its generic-airway replacement was excluded after review. Browser and automated validation are recorded below.

## Baseline, timing and restrictions

Recorded start: **2026-11-02 13:52:33 UTC**, or **2026-11-03 00:52:33 Australia/Hobart**. Seven-hour deadline: **2026-11-02 20:52:33 UTC**. Scientific verification and final validation completed at **2026-11-02T15:04:38.257072+00:00**, approximately **72.1 minutes** after the recorded start; Git publication followed. Work was organized in durable phases rather than delayed to fill the allowance.

Started with clean `main` at `0a743385dfdda09061721df816dfe029c9721b70`; fetched `origin/main` and confirmed it was already current. Read `AGENTS.md`, approved architecture and the [previous completion report](overnight-glossary-completion-20261102.md). Verified actual baseline: 32 concepts, six MeSH-defined, one technical-source-defined, 25 provisional-only, zero undefined; glossary revision126. The baseline full suite passed **553 tests in 132.159 seconds**. No active Mira research process, unresolved submission or pending journal operation was found; the existing local Qwen and embedding services were left running.

`architecture.md`, **all existing production prompts including G1**, synthesis behavior, strategies and provider profiles remain unchanged. The G1 template SHA256 remains `0a2726f28234058e7147459493b4c338bdf6d66976ea72c2dccda11c0d6ed673`. No protected change was made or needed reverting. All scientific records/views/logs remain local and ignored by Git.

## Coverage and disposition

| Metric | Before | After |
|---|---:|---:|
| Original concepts | 32 | 32 |
| Applicable MeSH/authority definitions | 6 | 5 |
| Source-supported concepts | 1 | 21 |
| Provisional-only concepts | 25 | 5 |
| Concepts with usable definitions | 32 | 31 |
| Without usable definitions | 0 | 1 |
| Explicitly requiring clarification | 0 | 1 |

The five remaining provisional concepts are **g5, g9, g15, g18 and g28**. The unresolved concept is **g30**, whose identity and all source/model history remain present.

Counts describe concepts with currently applicable, nonexcluded definitions. “Research-source” includes scientific publications, society guidance, government glossaries and technical documentation; it does **not** mean every source is an independent empirical clinical study. Authority name matches without descriptive text do not count as definitions. An unresolved modifier or inadequate definition is not concealed to preserve 100% coverage.

Seven additional definition versions were explicitly excluded in the initial review: g6, g10, g14, g17, g28, g29 and g30. Final review also excluded the generic g30 replacement and g8’s unqualified superiority/tumour-burden alternative. **Nine new exclusions** plus five from the preceding task make **14 retained excluded versions**, including one authority description. The reasons distinguish a definite false/generalized claim from a definition inadequate for its classification purpose. Original text, model/authority provenance, interactions and source passages were preserved.

## Independent verification of the original 25 provisional-only concepts

“Source” means a newly admitted, literal extract with a reviewed mapping to the stable existing concept. Many are short defining fragments from a heading, table or defining complement; quotations are not padded with invented term prefixes. Qualifications remain separate. “Provisional” means attribution has not been promoted merely because the core meaning was corroborated.

| ID / canonical concept | Source examined and scientific assessment | Final disposition |
|---|---|---|
| g1 Pulmonary nodules | [Fleischner2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10902601/) defines a circumscribed opacity and ≤30 mm **average** diameter. TSANZ uses <30 mm; preserve the measurement/convention distinction. | Source fragment plus explicit size qualification; original model version retained. |
| g2 Spiculation | [Original spiculation methods paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7920914/) defines surface spikes; Fleischner confirms the risk association is nonspecific. | Source; no universal causal or malignant implication. |
| g3 Risk stratification | [NCI EDRN fourth report](https://edrn.nci.nih.gov/documents/101/edrn_4th-report_200801.pdf), glossary, explicitly defines risk quantification using stated criteria. Diagnostic and prognostic endpoints differ. | Source; not evidence of prediction performance. |
| g4 Lymphocytic interstitial pneumonia | [Original LIP case](https://pmc.ncbi.nlm.nih.gov/articles/PMC12663765/) gives a histological definition; [MedGen/HPO](https://www.ncbi.nlm.nih.gov/medgen/82682) corroborates lymphoid interstitial infiltration. Cysts are not obligatory. | Source. The case supports an exception, not its prevalence. |
| g5 Spiculated pulmonary nodule | Fleischner morphology and the [histologically confirmed LIP mimic](https://pmc.ncbi.nlm.nih.gov/articles/PMC12663765/) support the qualified core meaning. Neither supplies an admitted exact definition of this entire compound label. | Provisional; source corroboration does not change the generating attribution. |
| g7 Reverse halo sign | [Godoy2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3487053/) defines the ground-glass centre/peripheral consolidation pattern and its broad differential. | Source; nonspecific imaging observation. |
| g8 volumetric assessment | [TSANZ2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12231763/) explicitly describes software volume measurement and discusses segmentation/acquisition/software limitations. | Source; unqualified model superiority/tumour-burden alternative excluded. |
| g9 growth rate | [European growth guidance](https://pmc.ncbi.nlm.nih.gov/articles/PMC12712097/) distinguishes measured change and VDT summaries under a growth model. A rate and a time do not have identical dimensions. | Provisional clinical-kinetics meaning retained with independently grounded dimensional qualification. |
| g10 Subsolid pulmonary nodules | [ACCP guideline](https://pmc.ncbi.nlm.nih.gov/articles/PMC3749714/) explicitly distinguishes pure ground glass and part-solid. Visibility of structures through ground glass cannot describe the whole solid component. | Source; misleading earlier model definition excluded. |
| g11 Volume doubling time | [European guidance](https://pmc.ncbi.nlm.nih.gov/articles/PMC12712097/) explicitly defines volume doubling and its exponential estimate. | Source; neither diameter doubling nor a diagnostic threshold. |
| g14 Relapse | [NCI dictionary, term45866](https://www.cancer.gov/publications/dictionaries/cancer-terms/def/relapse) specifies return after improvement. Mere ongoing stability is too broad. | Source; earlier overly broad model definition excluded; addiction sense not selected. |
| g15 Reversed halo sign | [Walker2011, PMID21778868](https://pubmed.ncbi.nlm.nih.gov/21778868/) explicitly lists reverse/reversed naming equivalence; [full published page](https://www.bsctr.bg/media/documents/recommended_articles/Reversed_Halo_Sign_.12.pdf) inspected. | Provisional definition retained; supported `SYNONYM_OF` link to g7 admitted. No merge. |
| g17 Inflammatory pseudotumor | [Gleason/Hornick2008](https://jcp.bmj.com/content/61/4/428) defines a heterogeneous neoplastic/non-neoplastic umbrella; [2025 IMT review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12026078/) confirms the importance of specific classification. | Source; categorical benignity excluded. Not all IPT is IMT. |
| g18 Small bubble signs | [Subsolid review](https://pmc.ncbi.nlm.nih.gov/articles/PMC7481135/) describes intranodular bubbly/pseudocavitary change. This corroborates core morphology, not an exact universal synonym or mechanism for every “small bubble” occurrence. | Provisional; no automatic equivalence with g29. |
| g19 Delta radiomics | [Nardone2024 systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11322237/) explicitly defines temporal feature variation and reports substantial methodological limitations. | Source; pre/post-therapy is an example, not a requirement or demonstrated benefit. |
| g20 Immunoglobulin G4 (IgG4)-related disease | [2012 pathology consensus](https://pubmed.ncbi.nlm.nih.gov/22596100/) supports fibroinflammatory disease and characteristic histology; elevated serum IgG4 is neither mandatory nor sufficient. | Source; explicitly supported `IgG4-related disease` alias added. |
| g22 Systemic Immune-Inflammation Index | [Primary NSCLC methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC10831397/) explicitly supply P×N/L; [Hu2014](https://pubmed.ncbi.nlm.nih.gov/25271081/) verifies original index identity. | Exact formula source; count-concentration units and no universal cutoff qualified. |
| g23 Neutrophil-to-Lymphocyte Ratio | [Same primary methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC10831397/) supply N/L. | Exact formula source; dimensionless only with consistent units. |
| g24 Platelet-to-Lymphocyte Ratio | [Same primary methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC10831397/) supply P/L. The paper misspells the expansion as “ration”; the admitted literal formula does not silently rewrite it. | Exact formula source; no disease-specific diagnostic claim. |
| g25 Maximum Standardized Uptake Value | [EANM FDG guideline](https://pmc.ncbi.nlm.nih.gov/articles/PMC4315529/) distinguishes maximum single-voxel SUV/SUL from peak measures. | Source; weight versus lean-mass normalization distinguished. Uptake is not cancer specificity. |
| g26 Nonsolid nodules | [IASLC/ATS/ERS2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC4513953/) explicitly defines the pure-GGN/nonsolid morphology. | Source; morphology does not prove noninvasive histology. |
| g27 Minimally invasive adenocarcinoma | [NCI PDQ AJCC9 T1mi](https://www.cancer.gov/types/lung/hp/non-small-cell-lung-treatment-pdq) gives ≤3 cm total tumour and ≤5 mm invasion; primary classification supplies exclusions. | Source; histology, sampling and exclusions remain necessary. |
| g28 Invasive adenocarcinoma | [Primary classification](https://pmc.ncbi.nlm.nih.gov/articles/PMC4513953/) shows that MIA itself allows limited stromal invasion. A broad invasion sentence cannot establish the category boundary, and CT prediction is not histology. | One improved G1 replacement retained as provisional; invasion-pattern description is useful but not a complete standalone classification rule. |
| g29 vacuole sign | [Original CT methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11797000/) define air attenuation using an operational 1–2 mm criterion. [Fan2011](https://pubmed.ncbi.nlm.nih.gov/21696561/) compared **105 malignant solid nodules and 48 malignant fGGOs**. | Source; size is study-specific. Prior cohort-frequency definition excluded. |
| g30 natural air bronchograms | Fleischner supports general air-bronchogram morphology. Fan2011 does not independently establish a benign/malignant discriminator or a general definition of the modifier “natural.” | Generic G1 replacement excluded; explicit clarification required. No regeneration of unchanged context, including through legacy R1 eligibility. |

## Review of the seven already sourced/authoritative concepts

| Concept | Independent review and disposition |
|---|---|
| g6 Organizing pneumonia | [Original MeSH page](https://www.ncbi.nlm.nih.gov/mesh/2103144) reproduces the problematic OP/BOS wording. [Clinical definition and terminology review](https://pmc.ncbi.nlm.nih.gov/articles/PMC7120422/) distinguishes OP, secondary OP, idiopathic COP and bronchiolitis obliterans. MeSH text preserved but excluded; clinical source definition admitted. |
| g12 Radiomics | [IBSI official specification](https://ibsi.readthedocs.io/en/latest/03_Image_features.html) corroborates quantitative imaging features. Existing MeSH attribution retained; suggested clinical applications do not establish usefulness. |
| g13 Cryptogenic organizing pneumonia | OP literature corroborates its idiopathic distinction. Retained MeSH ages/onset are descriptive, not mandatory diagnostic bounds; no automatic merge with general OP. |
| g16 Pulmonary infarction | [Pathophysiology review](https://pmc.ncbi.nlm.nih.gov/articles/PMC9409643/) corroborates ischemic injury/necrosis and frequent embolic context. Not every embolus causes infarction. MeSH retained. |
| g21 PET/CT | [SNMMI terminology](https://snmmi.org/Web/Research-Publications/Glossary-of-Molecular-Imaging-Terms.aspx) corroborates combined functional/anatomical modalities; not restricted to FDG. MeSH retained. |
| g31 Pulmonary inflammatory pseudotumor | Historical pulmonary plasma-cell granuloma meaning retained with actual MeSH attribution. Broader IPT/IMT nomenclature is heterogeneous; do not use the umbrella name as assurance of benign behaviour. |
| g32 GLCM | [Official scikit-image documentation](https://scikit-image.org/docs/stable/api/skimage.feature.html#skimage.feature.graycomatrix) and IBSI confirm a matrix/count object, not the algorithm computing it. Offset, discretization, normalization and symmetry matter; the technical-source definition remains preferred. |

The retained delta-review text also gives inconsistent final-search-year statements (2023/2024). Its explicit temporal definition was used; no search cutoff or pooled performance claim was reconstructed from that inconsistency.

## Deterministic quantitative checks

For **exponential volume growth with constant shape**, `k = ln(2)/T_volume` and `T_diameter = 3 × T_volume`. A hypothetical 28-day volume doubling gives a diameter factor of approximately 1.2599 at day28 and diameter doubling at day84. These are conditional calculations, **not observations of this lesion** or evidence favoring infection.

With counts in `10^9/L`, platelets240, neutrophils4 and lymphocytes2 give SII480 (`10^9/L`), NLR2 and PLR120 (dimensionless ratios). Zero lymphocytes makes the ratios undefined. Changing count units changes numerical SII, so a dimensionless universal cutoff would be inappropriate.

For image `[[0,1],[1,1]]` and right-neighbour offset `(0,1)`, the pair-count matrix is `[[0,1],[0,1]]`, total2; normalization gives `[[0,.5],[0,.5]]`. It is not automatically symmetric. This checks mathematical objects and assumptions, not clinical discrimination.

## Implementation corrections

- Added reviewed literal-source admission through the existing canonical journal. It records stable concept identity, source ID/URL/title, original-document and retained-text hashes, retrieval time, exact passage, qualifications, reviewer and concept-mapping reason. Headings, singular labels, tables and defining fragments no longer require inventing an “X is…” source sentence. R3 proposal validation remains independent.
- Actual retrieval endpoints are retained separately from publication citation URLs in an append-only canonical provenance event covering19 source documents. This includes the official NCI dictionary JSON endpoint, term45866; its client-rendered HTML shell alone did not contain the definition. Some blocked publisher pages were verified through indexed abstracts. Unavailable/403/500 responses were not treated as scientific support.
- Source admission validates exact extraction, uses the runner lease and recovery/submission gates, preserves prior records, rejects source-ID reuse with changed content/URL and reuses an existing retained source record. Repeating the same admission changes no canonical bytes.
- Reviewed unresolved meanings can remain durably in clarification without automatic regeneration; the legacy optional R1 path respects the same eligibility restriction. The R1 DEFINE task itself is unchanged.
- R1 now receives research-source identifiers, extraction references, qualifications and truncation flags. Previously the outer branch admitted this metadata only for authority/model definitions, leaving research-source citations unreachable.
- The previous240-character definition clipping could remove late benign-mimic or invasion qualifications. Definitions now retain up to600 characters, covering complete allowed G1 definitions; the same shared byte cap and explicit truncation indication remain in force.
- Source windows now prefer the admitted exact passage over the first canonical-name occurrence. A missing modified name previously fell back to page-zero front matter. The corrected real-tokenizer preflight used3,690 input tokens plus4,096 output reserve within16,384, without generation. The one actual generation preceded this correction; its quoted passage was supplied, but the extra dictionary window was poorly located. No benefit is attributed to a correction the actual generation did not receive.
- Retrieval prioritizes exact names/aliases in the assigned question before incidental ancestor/memory vocabulary, bounds projected aliases, and budgets **final canonical entries including provenance**. An oversized first entry no longer prevents a later smaller entry from fitting. Even an empty projection respects the minimum128-byte cap.
- Added narrowly supported parenthetical synonym-list parsing and compound-name abbreviation handling. Neither fuzzy name similarity nor co-occurrence establishes equivalence. This admitted one reverse/reversed-halo link and the source-supported shortened IgG4 disease name.
- Standard HTML now provides clickable, escaped HTTP(S) source citations. Executable schemes, credentials, malformed ports, whitespace and backslashes are rejected; safe DOM search and the offline CSP remain intact.

There is one canonical glossary and its disposable SQLite index. No new database, research scheduler, scientific verifier prompt or production instruction was introduced.

## R1 retrieval in disposable corpus copies

The normal retrieval path and **actual unchanged R1 renderer** were exercised against disposable copies for six questions: nodule growth, PET/CT, inflammatory lesions, radiomics, prediction endpoints and quantitative imaging. An additional histopathology question checked classification boundaries, and a plant-photosynthesis question checked unrelated retrieval. Exact contexts and rendered requests were saved locally. These are construction evaluations, not genuine R1 generations or evidence of improved scientific answers.

| Question family | Before: entries / usable definitions | After: entries / usable definitions | Final bytes |
|---|---:|---:|---:|
| growth | 3 / 3 | 4 / 4 | 3191 |
| pet | 6 / 2 | 5 / 3 | 3047 |
| inflammation | 3 / 2 | 4 / 3 | 3161 |
| radiomics | 8 / 3 | 6 / 3 | 3031 |
| prediction | 6 / 0 | 5 / 3 | 2989 |
| quantitative | 4 / 4 | 4 / 4 | 3191 |
| histology | Not measured | 5 / 3 | 3117 |
| unrelated | 0 / 0 | 0 / 0 | 143 |

Every final projection is within3,200 bytes. Source identifiers are now present for every included definition. The g20 abbreviated-name fix brings IgG4-related disease into the inflammatory-question selection. Full model definitions retain late qualifications instead of silently clipping them; g19 still illustrates a scope false negative. The larger authority definition can crowd other relevant concepts out, including g17 in the final inflammatory-question example.

Applicability remains a conservative lexical heuristic. It can reject a useful meaning when the new question uses different vocabulary: the radiomics question retrieves g19 but initially omits its applicable temporal definition. Tight context budgets also omit relevant terms, and cached search relevance can include incidental pulmonary concepts. These are observed limitations, not solved by completing HTML coverage. The authority/source/provisional distinction must remain visible rather than forcing a meaning into every question.

The 10,000-entry regression still bounds canonical deserialization to12 candidates and checks byte limits. Source references/qualifications consume real space: the minimum returned-entry expectation was adjusted from eight to five under the unchanged3,200-byte fixture budget. The fixed budget was not increased to conceal provenance costs.

## Controlled generation and service availability

The initial setup attempt returned HTTP503 before request submission: **zero genuine model calls and zero generation tokens**. Both failed-term states retained their normal cooldown until14:37:18 UTC. Read-only health checks then returned200; independent source/audit work continued while cooldown elapsed.

After cooldown, one bounded unchanged-G1 request covered g28/g30: **3,635 input +363 output =3,998 total tokens**, 18.999 seconds for the maintenance invocation. It used the existing Qwen3.6-35B-A3B Q4_K_M artifact, temperature0, JSON, thinking disabled,4,096 output-token allowance and16,384 active context. The actual native request and response, unique request hash, artifact identity and both received/committed outcomes were retained. No uncertain submission remains.

The g28 replacement improves the histopathological meaning but remains provisional and incomplete as a full classifier. The g30 replacement again defines general airway morphology, leaves its modifier unqualified and claims direct derivation in its explanation. That is not an independently established definition of “natural”; it was excluded and given an explicit, durable clarification disposition. There was **no second generation seeking preferable wording**. The final unchanged maintenance rerun processed zero terms, made zero model/provider calls and preserved the glossary revision.

The original and new contexts, native token counts, exact model requests/responses and admission outcomes are retained locally. G1 was not edited. No source-supported definition was regenerated merely because an older model version was provisional. No additional research searches, evidence extractions or synthesis actions were run.

## Browser, integrity and regression validation

Full final suite: **570 tests passed**, zero failures, errors or skips, **129.803 seconds**. Command: `PYTHONPATH=src python3 scripts/run_tests.py` with validation/log arguments; raw results are preserved in `log/extended-glossary-20261103/verified-final-suite.stderr`. Seventeen regression tests were added beyond the553 baseline. Existing SQLite ResourceWarnings were retained in logs; they did not fail the suite. `git diff --check` passed.

Actual Chromium `file://` validation used an isolated temporary profile with external name resolution disabled. All32 anchors, canonical and case/whitespace/alias search, the new compound-name alias, partial search, arrow/Enter focus/navigation, scrolling, sticky search, temporary highlight expiry and no-match/names-only behavior passed. It also checked the supported relationship link, a clickable scientific-source URL, preferred and excluded definitions, provisional/scientific-scope labels, all six coverage counts, unresolved-modifier visibility and the exact canonical commitment. The screenshot was inspected. The existing local viewer served byte-for-byte the same current standard HTML. Temporary test browser/viewer processes were stopped.

Final glossary revision: **166**; commitment:

`b381a4a2db502e619ed523f09cc1821a8e519862902b37693f94a67ad4f8cfb3`

Canonical corpus revision before/after:

- `615733d54e7f71d43828da5bdf591a50e3b121e3f374b9fe7306971b4f0801c5`
- `65e248a831a23f6b3eb4f61e1bd03b1d20b1831b0d7e2c2ec84e1aae8834d3ee`

The full before/after active-corpus filesystem audit found **no deletions or unexpected modifications**. All16 scientific memories, the existing equation, private inputs, original source/retrieval records, prior interactions/logs and synthesis artifacts remain intact. Research state differs only in glossary metadata. Every previous definition, evidence row, alias, relationship and lookup/review history is retained. Nineteen source-document records and their exact retrieval-route/hash provenance were intentionally journaled. No unresolved external/model submission or pending recovery remains. An unchanged maintenance rerun processed zero terms and preserved the revision.

The standard outputs remain:

```text
memory/
  glossary/g1.json … g32.json
  memories/                         existing scientific memories
  equations/                        existing equation
  events/                           original and new glossary events
  journal/                          canonical transactions
  research/
    state.json                      glossary metadata updates only
    results/                        retained source records
    glossary.md
    glossary.html
log/extended-glossary-20261103/      progress, source captures and audit diagnostics
```

No per-experiment memory archive or replacement corpus was created. Source evidence is explicitly `query_submitted=false` without a top-level research-node search assignment. It does not become a completed provider search or a research finding.

```bash
PYTHONPATH=src python3 -m mira glossary-view
xdg-open memory/research/glossary.html
PYTHONPATH=src python3 -m mira viewer
```

## Remaining work and owner-review proposals

- Keep clinical terminology source review distinct from formal scientific or patient-level validation. The current corpus does not gain a diagnostic likelihood ratio or an answer to the infection-versus-malignancy question from this task.
- Improve context applicability beyond incidental lexical overlap, with explicit scoped sense evaluation and transparent omission reasons. Include counterexamples so a broadly named term does not acquire a wrong-domain authoritative meaning.
- The existing relationship types can express nonsolid-as-subsolid, COP-as-OP and spiculated-nodule-as-nodule distinctions. Their admission remains too dependent on literal source labels and simple phrase forms. The audit identifies these established distinctions; only the explicitly validated halo link was added. No unsupported merge or invented relationship type was introduced.
- Review the study-specific “natural” airway modifier and overlapping bubble/vacuole/pseudocavity labels against exact operational methods; do not generalize them from title matches or diagnostic associations.
- **R1 prompt proposal, not applied:** remove the third DEFINE task, the provisional-definition rules and `provisional_definitions` output field after the owner approves the exact replacement text. Suggested responsibility statement for that later review: “Use supplied attributed glossary definitions for terminology and disambiguation. Glossary maintenance is handled independently.” This task deliberately retains the existing approved production prompt.
- No architecture edit or G1 wording change is proposed as a prerequisite for the completed implementation.

Local durable record: `log/extended-glossary-20261103/progress.md`, `audit-register.json`, `admission-plan.json`, source captures and receipts, review exclusions, quantitative checks, before/after R1 projections, generation accounting, browser/viewer checks, preservation audit and complete test logs.

## Published changes

Implementation: `d70b8094484d7999ab343cb3c248258be99f549f`.

Regression tests: `0c3e1b87c17afd2542186016a56f579aae9d7175`.

The following documentation commit contains this scientific-quality report and updated ordinary test results. Only authorized implementation, tests and documentation are published. The active corpus, source captures, raw model traffic, generated glossaries, screenshots and execution logs remain local/ignored. The final completion message records the documentation SHA and verified `origin/main` synchronization.
