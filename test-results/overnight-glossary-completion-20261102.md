# Overnight active glossary completion

Recorded: 2026-11-02T22:01:07.604629+11:00 (Australia/Hobart).

## Executive summary

Mira's actual active glossary now has a usable attributed definition for **32/32 terms**: **6 MeSH-defined, 1 directly source-defined and 25 provisional-only**. No terms are undefined or marked as genuinely ambiguous. All original 32 identities remain present. This is terminology completion, not new evidence answering the pulmonary research question, and the model-only definitions have **not** been independently scientifically verified.

The normal HTML and Markdown were regenerated and tested in a real browser. The browser decision viewer serves the same current export. Eight genuine local Qwen G1 calls produced 30 definition proposals. A substantive review excluded five flawed versions across four concepts, preserved every original output and corrected the preferred glossary. The GLCM mistake persisted across two model attempts; an exact official technical-source definition resolved it without further generation. One rejected Relapse component was recovered from its saved response after a verified implementation fix, without another call.

## Approved baseline and protected files

Started with a clean `main`, fetched GitHub and fast-forwarded safely to owner-approved architecture commit `a8c34a742fc46177a39fe5ece8c07a052ff75b03`. Read the repository workflow/prompt policy and existing implementation and evaluation reports. The approved architecture is unchanged. Existing R1–R5/S1–S3 prompt files are byte-identical to that baseline; no research or synthesis prompt was rewritten. R1's existing optional DEFINE transition remains deferred as explicitly instructed for this task.

The **only new production prompt** is the exact approved Section 4 text in `prompt_templates/G1.txt`, 2,862 UTF-8 bytes including its final newline. SHA256:

`0a2726f28234058e7147459493b4c338bdf6d66976ea72c2dccda11c0d6ed673`

G1 is loaded through the normal template catalog. Its complete instruction source is a separate system message, unchanged; the bounded scientific context is a separate JSON user message. Each interaction retains exact source/hash, bindings, submitted messages/request/hash, response, token counts, actual model identity and committed per-term provenance. There is no hidden Python generation prompt. Existing research/synthesis scheduling is unchanged.

## Coverage

| Metric | Before | After |
|---|---:|---:|
| Total terms | 32 | 32 |
| Authoritative definitions | 6 | 6 |
| Research/source-supported definitions | 0 | 1 |
| Provisional-only terms | 0 | 25 |
| Undefined terms | 26 | 0 |
| Unresolved ambiguities | 0 | 0 |

Counts are unique terms. Authority/source categories may overlap in general; provisional-only is exclusive. The new source-supported entry is a **technical documentation definition**, not a quotation from a clinical study or a newly verified clinical finding. Thirty model definition versions are retained canonically; five are explicitly excluded, leaving 25 model-only preferred meanings. Excluded versions do not count toward coverage and are not displayed as legitimate alternative meanings.

Remaining unresolved terms: **none**. Coverage and applicability were re-audited against all canonical records and committed hashes after completion.

## Actual generation and execution statistics

| Metric | Observed |
|---|---:|
| Genuine G1 calls | 8 of 60 authorised |
| Unique submitted request hashes | 8 |
| Input tokens, server reported | 14,359 |
| Output tokens, server reported | 4,780 |
| Total tokens | 19,139 |
| Initial term proposals | 26 |
| Replacement proposals | 4 |
| Saved components revalidated without generation | 1 |
| Explicitly excluded scientific definition versions | 5 |
| Malformed/truncated model responses | 0 |
| Uncertain submissions remaining | 0 |

Token usage is counted **once per genuine interaction**, not summed again when a response is revalidated. All eight requests received responses and committed durable outcomes. There were no identical-request retries, failed-response sampling loops, same-model critique calls or substitute models.

Actual served model:

`/home/eric/models/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-Q4_K_M.gguf`

Local artifact SHA256:

`671e47e0ec53c665d048b98c3ecbfd5236b5ca9c3e02ed19fc8f81f7b85140c7`

Endpoint: `http://127.0.0.1:8090`. Active per-request context: **16,384 tokens**. Every generation used temperature **0**, JSON output, **4,096** maximum output tokens and `enable_thinking=false`. Native server chat-template/tokenizer checks included the output reserve. The model and configuration were discovered/read from the existing service; weights and server configuration were not changed.

| Phase | Terms selected | Genuine calls | Command wall time |
|---|---:|---:|---:|
| Representative validation: g11, g2, g25, g4 | 4 | 1 | 25.360 s |
| Immediate repeat of those entries | 0 | 0 | 0.609 s |
| Entire remaining backlog | 22 | 6 | 92.973 s |
| Saved Relapse component revalidation | 1 | 0 | 1.586 s |
| Reviewed replacement batch with additional retained source titles | 4 | 1 | 28.324 s |
| Completion metadata/source reconciliation | 28 | 0 | 26.717 s |
| Due MeSH upgrade verification | 2 | 0 | 9.722 s |
| Final ordinary idempotence run | 0 | 0 | 0.671 s |

These are command wall times, including persistence, metadata and lookup work, not isolated GPU inference timings. The reconciliation revisited definitions after input-context hashing was extended for explicit reviews; it regenerated none. Implementation, scientific review, browser work and regression tests are outside the generating-phase times. No artificial overnight delay was introduced after useful work completed.

## MeSH investigation and correction

Actual paced provider responses reproduced both failures. `Reverse halo sign` and `Reversed halo sign` map to **M000755226**, linked to **C000721353** through `preferredConcept`. The adapter wrongly assumed that the linked record must be a `D` Descriptor Record. It is a Supplementary Concept Record. NLM documents the distinct record types in [MeSH Record Types](https://www.nlm.nih.gov/mesh/intro_record_types.html).

The fix accepts verified `C` records only in the record-link binding, stores them separately as `supplemental_ids`, and continues requiring `M` concept identities and `T` term identities on the official host. A `C` ID is still rejected if presented as the concept ID. Both stable glossary entries are preserved; common authority identity is not used to merge them automatically. The [Fleischner glossary](https://pmc.ncbi.nlm.nih.gov/articles/PMC10902601/) also recognizes reversed halo as an atoll-sign synonym.

Two diagnostic lookups made **4 HTTP requests**. During backlog processing, two cached failure outcomes were retained without network calls. Once normal cooldowns expired, the corrected standard enrichment command made **2 lookups / 4 HTTP requests**, both successfully matched. Thus terminology work totalled **6 lookup outcomes, including 2 cached, and 8 actual HTTP requests**. No cooldown was bypassed and no failure cache was deleted to force a request.

The concept supplies **no descriptive scope note** through this exact-concept retrieval, so no authoritative definition was invented or counted. Both entries appropriately retain G1 provisional definitions. The view explicitly distinguishes an authoritative name match without a supplied definition from an authoritative description. Existing six MeSH descriptions retain their original attribution.

## Scientific review and substantive corrections

Every newly proposed meaning was read and assessed; structural acceptance alone was not treated as scientific approval. The first four-term batch passed JSON/identity/content/scope checks and was visibly attributed in the standard HTML before the rest of the backlog ran. Repeating it made zero calls or record changes. Volume doubling time referred to volume, not diameter, and supplied no unsupported diagnostic probability.

One deterministic rejection was an implementation false positive: the Relapse occurrence excerpt contained only patient/count/time vocabulary, while the model's clinically appropriate definition used recurrence/remission vocabulary. The plausibility check had omitted the supplied research question. It now uses that question as well as the occurrence passage. The already received response was revalidated and committed without regenerating it; the original response and outcome receipt were preserved. The additional replay event makes the correction inspectable.

The first G1 pass had four substantive issues:

- g5 attributed spiculation to tumour invasion without preserving benign possibilities.
- g29 included an insufficiently justified fluid interpretation for the CT vacuole sign.
- g30 inserted study-specific 24% versus 0% cohort frequencies into a definition.
- g32 defined the GLCM as an extraction method rather than the mathematical object.

These outputs were explicitly excluded, not silently edited. New append-only review records identify the exact definition hash, reviewer, timestamp and reason. Original text, model identity, source evidence and interaction provenance remain intact. Exclusions reopen enrichment and remove invalid text from preferred definitions and coverage. The viewer discloses exclusion reasons. A regression guard rejects explicit percentage/cohort findings masquerading as terminology definitions.

The original occurrence excerpts sometimes contained only associations or cohort numbers. Additional retained source titles changed the replacement request without changing G1; one bounded replacement call handled the four excluded terms. A final request-provenance audit established that this particular call had empty full-text windows: canonical result rows were metadata descriptors, and the new projector had not hydrated their cached payloads. That implementation defect was corrected using Mira's existing payload hash/metadata validation, with a corruption regression test and a native-tokenizer preflight on the actual corpus. The corrected projector includes nonempty verbatim source windows. A nongenerating real-corpus preflight measured 3,442 input tokens plus the 4,096-token output reserve, within the 16,384-token window; five retained excerpts ranged from 114 to 971 characters. No further generation was performed after this correction, and no scientific improvement is attributed to full text that the eight actual calls did not receive. The spiculation and vacuole core meanings improved; airway descriptions no longer contained numerical cohort frequencies. Qualitative cohort comparisons remain in g29/g30 and must be read as context-specific, not universal diagnostic rules.

GLCM's second model output still called the matrix a method. It was excluded too, and there was **no third model attempt**. An exact, short definition sentence was verified against the [official scikit-image `graycomatrix` documentation](https://scikit-image.org/docs/stable/api/skimage.feature.html#skimage.feature.graycomatrix), retrieved once and retained with URL, title/version, timestamp, extraction description and original-HTML hash. Normal source-passage validation merged it into existing g32, with no new term ID. The [IBSI specification](https://ibsi.readthedocs.io/en/latest/03_Image_features.html#grey-level-co-occurrence-based-features) independently supports the matrix/count/probability distinction. No model text was relabelled as a source quotation.

### Independent quantitative checks

Under **constant-shape exponential volume growth**, `V ∝ D³`, so diameter doubling requires three volume doublings: `T_diameter = 3 × T_volume`. A 28-day volume doubling gives a diameter factor of approximately 1.2599 at day 28 and a factor of 2 at day 84. This was checked deterministically as a conditional mathematical relation, not asserted for arbitrary lesion growth. The stored g11 definition contains no such equation and does not equate the quantities.

SII, NLR and PLR arithmetic was checked independently using consistent count units: platelets 240, neutrophils 4 and lymphocytes 2 produce SII 480, NLR 2 and PLR 120. A two-by-two image with right-neighbour pairs `(0,1)` and `(1,1)` produces count matrix `[[0,1],[0,1]]`, sum 2, and normalized matrix `[[0,.5],[0,.5]]`. This checks the mathematical object independently of model agreement. It does not establish clinical diagnostic performance.

### Per-concept review of the 26 formerly undefined terms

The table records a terminology review, not independent clinical certification. Five excluded versions remain inspectable in the corpus and events.

| ID | Term | Assessment and qualification |
|---|---|---|
| g1 | Pulmonary nodules | Useful morphology/density definition. The 3 cm boundary is conventional; this is not a management rule. |
| g2 | Spiculation | Appropriate morphology and risk association; association does not establish malignancy or mechanism. |
| g3 | Risk stratification | Useful clinical grouping concept; no invented risk probability. |
| g4 | Lymphocytic interstitial pneumonia | Appropriate interstitial lymphocytic process and common CT phenotype; cysts are not mandatory. |
| g5 | Spiculated pulmonary nodule | Original unsupported tumour-invasion explanation excluded. Replacement preserves inflammatory mimics. |
| g7 | Reverse halo sign | Central ground-glass opacity with surrounding consolidation; nonspecific differential preserved. |
| g8 | volumetric assessment | Core volume-measurement meaning appropriate. Claims of accuracy depend on segmentation and consistent acquisition. |
| g9 | growth rate | Appropriate clinical growth-kinetics usage. VDT is a time-valued summary/proxy for growth rate, not its identical physical dimension. |
| g10 | Subsolid pulmonary nodules | Correct subsolid family and pure/part-solid distinction; visibility refers to the ground-glass component. |
| g11 | Volume doubling time | Volume, not diameter, doubles. No unsupported doubling-time threshold or diagnostic probability. |
| g14 | Relapse | Appropriate disease recurrence after stability/remission. Saved response accepted after fixing the incomplete vocabulary check. |
| g15 | Reversed halo sign | Same radiological pattern as reverse halo sign. Stable entries remain distinct; no lexical automatic merge. |
| g17 | Inflammatory pseudotumor | Useful historical inflammatory mass-lesion meaning. Terminology is heterogeneous; the label alone does not certify benign behaviour. |
| g18 | Small bubble signs | Useful small intranodular air-lucency description. Pathological associations are context-dependent, not diagnostic criteria. |
| g19 | Delta radiomics | Appropriate longitudinal change in imaging features. Pre/post-therapy is a common example, not a required restriction. |
| g20 | Immunoglobulin G4 (IgG4)-related disease | Appropriate fibroinflammatory pathology and characteristic histological pattern; no invented diagnostic probability. |
| g22 | Systemic Immune-Inflammation Index | Formula platelet × neutrophil / lymphocyte is correct; diagnostic/prognostic applications remain context-specific. |
| g23 | Neutrophil-to-Lymphocyte Ratio | Correct absolute neutrophil / lymphocyte ratio; arithmetic checked independently. |
| g24 | Platelet-to-Lymphocyte Ratio | Correct absolute platelet / lymphocyte ratio; arithmetic checked independently. |
| g25 | Maximum Standardized Uptake Value | Correct maximum regional normalized tracer uptake; body-weight normalization is the stated convention, not a malignancy test. |
| g26 | Nonsolid nodules | Correct pure ground-glass/nonsolid distinction and lack of obscuration of underlying structures. |
| g27 | Minimally invasive adenocarcinoma | Correct ≤3 cm tumour and ≤5 mm invasive-component quantities; radiological models do not replace histopathology. |
| g28 | Invasive adenocarcinoma | Useful broad invasion description. It does not provide all criteria distinguishing invasive from minimally invasive categories. |
| g29 | vacuole sign | Original fluid interpretation excluded. Replacement describes air-containing lucency; comparative frequency is supported by the retained cohort, not a universal rule. |
| g30 | natural air bronchograms | Original 24%/0% cohort-statistic definition excluded. Replacement gives airway morphology; its qualitative cohort comparison remains source-specific. |
| g32 | Gray-Level Co-occurrence Matrix | Both model versions misidentified the object as a method and are excluded. Preferred definition is an exact, attributed official technical-source sentence describing a histogram/matrix. |

### Compact examples of current preferred definitions

All examples below except g32 are attributed to the actual Qwen artifact identified above and marked **provisional**. They were not presented as quotations from clinical papers.

- **g11 Volume doubling time** — The time required for a pulmonary nodule's volume to double, calculated based on serial volumetric measurements, used to categorize growth kinetics into fast or slow growth groups. Source: local Qwen G1; verification: provisional.
- **g2 Spiculation** — A morphological feature of pulmonary nodules characterized by irregular, spiky margins extending into the surrounding lung parenchyma, often associated with higher malignancy risk. Source: local Qwen G1; verification: provisional.
- **g25 Maximum Standardized Uptake Value** — The maximum standardized uptake value of a radiotracer, typically 18F-FDG, measured within a region of interest on PET/CT imaging, representing the highest concentration of tracer uptake normalized for injected dose and patient body weight. Source: local Qwen G1; verification: provisional.
- **g23 Neutrophil-to-Lymphocyte Ratio** — A hematological biomarker calculated as the ratio of absolute neutrophil count to absolute lymphocyte count in peripheral blood. It serves as an indicator of systemic immune and inflammatory status. Source: local Qwen G1; verification: provisional.
- **g5 Spiculated pulmonary nodule** — A solitary pulmonary nodule exhibiting spiculated margins, defined by linear densities radiating from the nodule periphery into the surrounding lung parenchyma. This morphological feature is highly suspicious for malignancy but can also be present in inflammatory conditions such as lymphocytic interstitial pneumonia. Source: local Qwen G1; verification: provisional.

For **g32**, the preferred source-supported definition describes a histogram of paired grayscale values at a specified image offset. Its source is the official scikit-image documentation, with an exact extractive quotation and retained supporting evidence. It is not attributed to Qwen. The six existing MeSH-defined concepts retain their source descriptions and are not counted as new model work.

## Standard glossary, browser and index verification

Current standard files:

- `/home/eric/Dev/Mira/memory/research/glossary.html`
- `/home/eric/Dev/Mira/memory/research/glossary.md`

Canonical glossary revision: **126**. Commitment:

`be2e6aefb05670a83eee19fbd797adf2b838327d1de830e03323ed5e2d242483`

The final HTML was loaded from its real local `file://` URL in Chromium with network resolution disabled and an isolated temporary browser profile. Tests exercised all 32 entry anchors; case/whitespace-normalized `VDT` alias lookup to g11; partial canonical-name search; arrow/Enter selection; actual focus and scrolling; sticky search; temporary highlight and expiry; no-match feedback; and exclusion of definition text from search. A rendered screenshot was inspected. The final browser marker matches canonical revision 126. The real normal Mira viewer's **Glossary** link served exactly these standard HTML bytes through its read-only route.

`glossary-rebuild` and subsequent standard export succeeded. Ordinary completion rerun processed zero entries, made zero model/provider calls and preserved revision 126. Current views display preferred source attribution, scope, ambiguities, provisional labels, exclusion notices, supporting passages/references, existing relationships and a complete-coverage summary. No temporary experiment or alternate glossary store is required.

```bash
PYTHONPATH=src python3 -m mira glossary-enrich --status
PYTHONPATH=src python3 -m mira glossary-enrich
PYTHONPATH=src python3 -m mira glossary-view
xdg-open memory/research/glossary.html
```

## Persistence, privacy and recovery

No research experiment was initialized or reset. The active corpus remains `memory/`; 16 research memories and one equation are unchanged. Before/after hashes show **no deletions or unexpected modified files**. Research state differs only in glossary metadata. Every previous definition, evidence row, alias, relationship and node association is retained, including excluded generated versions with their original provenance. Existing source/retrieval records, interactions, private inputs, logs and synthesis experiment artifacts were preserved.

One new source-evidence record was intentionally journaled for the official GLCM documentation; it is marked `query_submitted=false`, carries no research-node search assignment, and is not misrepresented as a provider research search or a new research finding. No research memory was created. The record path is preserved in local audit diagnostics. There are no unresolved model submissions or pending journal recovery operations.

Canonical corpus revision before:

`2e8ce5d205ef8cfc8467a214d7a0904216e5fd8fb659b02fd66c98809eb1a153`

After:

`615733d54e7f71d43828da5bdf591a50e3b121e3f374b9fe7306971b4f0801c5`

Generated views, active corpus, source captures, model requests/responses, execution logs and browser profiles remain local/ignored and are not committed. The implementation, exact approved G1 template, tests and this report are the publication deliverables.

## Regression results and limitations

Full suite: `PYTHONPATH=src python3 -m unittest discover -s tests` — **553 tests passed, 0 failures, 0 errors, 0 skipped**, 131.125 seconds. `git diff --check` passed. Tests cover exact G1 loading and message/provenance construction, independent term selection, budgets, multiple definitions, ambiguity, invalid outputs, explicit review/exclusion, safe received-component revalidation, original outcome preservation, idempotence, interrupted and uncertain submissions, token limits, standard export/rendering and normal viewer integration. Existing R1–R5 and S1–S3 regressions remain enabled.

Earlier full runs exposed an obsolete viewer-catalog expectation omitting G1; that expectation was updated to include the newly approved independent action. The earlier failure logs were retained. Existing SQLite resource warnings were logged; the final suite completed successfully.

Complete usable-definition coverage does not imply complete scientific verification. Twenty-five preferred meanings remain model-only and provisional. Some retain broad diagnostic or comparative language that merits future subject-expert review, especially g8 accuracy, g17 heterogeneous pathology, g28 invasive-category boundaries and g29/g30 cohort generalization. No independently validated diagnostic probability, biological mechanism or new clinical conclusion is claimed. The matrix error persisting across two outputs demonstrates why completion counts alone are insufficient.

## Recommendations for owner review only

- Preserve the approved architecture and G1 wording in this task. No prompt edits beyond exact G1 creation were applied.
- Separately approve the exact R1 prompt/output transition removing optional DEFINE before changing that production responsibility. Architecture already describes the intended separation; this task explicitly deferred the prompt transition.
- Consider a later owner-approved G1 revision discouraging cohort comparisons and requiring definitions of mathematical objects as objects rather than methods. The present task did not add those instructions to G1 or a hidden Python prompt.
- Consider a reviewed source-admission interface for technical definitions and structured mathematical validation. Keep manual disposition, original model provenance and authority name-match/description distinctions inspectable.

Detailed local diagnostics: `log/overnight-glossary-20261102/` contains the immutable baseline, all phase statistics, generation ledger, MeSH raw provider responses, scientific rejections, GLCM source admission, independent mathematical checks, preservation audit, real-browser/viewer checks and complete regression logs. Normal execution JSONL logs remain in project `log/`.

Tested implementation and tests commit: `1d04d849c17c2df5be2a2062d6680a9deac50e76`. The following report commit changes documentation only.
