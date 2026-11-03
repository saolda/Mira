# R1 prompt transition and transparent glossary history

Completed 2026-11-03 on `main`.

R1 now performs DISCOVER/SELECT only. The standard glossary exposes original rejected proposals while retaining exclusions and scientific uncertainty. No scientific definitions were generated or reclassified in this task.

## Implementation

- Installed the owner's exact approved `R1.txt` replacement. The seven input slots are unchanged. Responses must contain exactly `new_concepts`, `search_concepts` and `reason`; even an empty `provisional_definitions` field is rejected.
- Removed R1 component forwarding, controller admission, directory generation, proposal validation and obsolete definition-eligibility projections. New model-definition transactions require committed G1 provenance. Independent G1, source-supported R3 admission, partial concept validation, concept reuse, query history and synthesis scheduling remain covered by regression tests.
- Historical generated-definition record parsing is retained. Existing R1-origin rows and interactions are readable without rewriting them. Journal recovery applies original hash-checked after-images; new R1 publications cannot add generated definitions. No parallel compatibility implementation was added.
- A shared presentation model drives HTML and Markdown: preferred applicable definition, scientific verification, one current issue, alternatives/history, attribution/evidence, relationships and technical provenance. Current issues use an extract of the stored first sentence, not generated scientific wording. The rest of the review remains inspectable with a link to that issue, avoiding repeated warnings in enrichment metadata.
- Every excluded version retains its exact original text, review reason, reviewer/time, hash and original source/model attribution. Native HTML disclosure opens by default if no definition is accepted; accepted entries can keep excluded history collapsed. No JavaScript is needed to read or expand history.
- Name/alias search, ranking, keyboard navigation, highlighting, stable anchors, scientific source links, CSP, escaping, revision metadata and atomic standard exports remain intact.

## g30: natural air bronchograms

Scientific-review status: **requires clarification; no accepted definition**. All three model proposals remain excluded. The precise study-specific modifier **natural** is not independently established by a definition of a general air bronchogram. The existing general-source passage remains attributed supporting context, not an authoritative definition of the complete phrase.

Original rejected model text, reproduced verbatim:

> A radiological sign on CT imaging where air-filled bronchi are visible within a pulmonary nodule or consolidation. In the context of differentiating malignant solid nodules from ground-glass opacities (GGOs), its presence is significantly more frequent in GGOs (24%) than in malignant solid nodules (0%).

Original exclusion reason:

> A term definition includes study-specific 24% versus 0% frequencies, conflating scientific terminology with empirical cohort findings.

Original model: `Qwen3.6-35B-A3B-Q4_K_M.gguf`; artifact SHA256 `671e47e0ec53c665d048b98c3ecbfd5236b5ca9c3e02ed19fc8f81f7b85140c7`. Original generation timestamp: `2026-11-02T10:38:08.101563+00:00`. Interaction: `interactions/00000182-c55f7ef0bf0f473f8c0065196ac7d34b/request.json`. Full local attribution and prompt/request hashes appear in both exports.

The second proposal adds a comparative frequency statement; its review notes that Fan2011 compared two malignant cohorts. The third describes generic air-bronchogram morphology and still does not establish the modified meaning. Their separate original wording and attribution are visible in the standard glossary. None is restored to accepted terminology.

## Validation

- Complete regression suite: **576 tests passed**, zero failures, errors or skips, **131.833 seconds**. Implementation `9a783589ff6234bbf35ad8ad4b7b09c9ad8f05b4` and tests `60a0826e5a5a8f46ff0ed07fb864959faa11d454` contain the working-tree code tested. The ordinary test report is `test-results/latest.md`.
- Focused regressions cover the exact approved prompt hash/slots, strict response fields, undefined and established terms, G1 completion, old R1 rows, provenance admission boundaries, source/authority preference, rejected historical versions, shared issue presentation, attribution, accepted/undefined entries and injection prevention. Existing full-suite recovery and R1–R5/S1–S3 tests pass.
- Regenerated the actual active corpus using `PYTHONPATH=src python3 -m mira glossary-view` into `memory/research/glossary.html` and `memory/research/glossary.md`.
- Real Chromium inspection verified all 32 entries, g30's three verbatim proposals, default-open history, a single current issue, retained exclusions/model attribution, honest coverage, aliases, partial search, arrow/Enter navigation, focus/scroll, temporary highlight, sticky search, relationships and clickable source references. Local-file operation uses no external resources. JavaScript-disabled reload retained readable history. Visually inspected the g30 screenshot locally.
- The existing local Mira viewer served the updated standard HTML byte-for-byte. Markdown contains all three g30 definition texts and the unrepeated current issue.
- Before/after hashes checked all 3,472 pre-existing memory files. Only the two derived glossary exports changed; no files were removed. Scientific memories, equations, sources, interactions, journal, research state and private inputs remain unchanged. No model calls or research actions were made.
- Canonical revision remains `65e248a831a23f6b3eb4f61e1bd03b1d20b1831b0d7e2c2ec84e1aae8834d3ee`. Glossary revision **166**, commitment `b381a4a2db502e619ed523f09cc1821a8e519862902b37693f94a67ad4f8cfb3`. Recovery is not blocked.
- Protected-file hashes confirm **only the specifically approved R1 prompt changed**. `architecture.md` and all other production prompts are unchanged. No additional prompt or architecture changes are proposed.

## Active glossary coverage

32 terms: **5 authoritative**, **21 research-source**, **5 provisional-only**, **1 without a usable definition / requiring clarification** (g30). There are 31 usable definitions at the concept level. Source categories can overlap; provisional-only is exclusive. Reading excluded history never increases accepted coverage.

## Limits and review notes

Scientific acceptance remains the recorded review decision; software validation is not independent scientific verification. The compact issue is a deterministic first-sentence extract and may retain source-specific wording. Historical texts are not corrected for readability. Ordinary Markdown escaping preserves rendered text while preventing markup injection.

The upcoming Brain Viewer request will be implemented separately against this committed baseline. No paper-generation capability is included here.

## Commits and synchronization

Implementation: `9a783589ff6234bbf35ad8ad4b7b09c9ad8f05b4`. Tests: `60a0826e5a5a8f46ff0ed07fb864959faa11d454`. This report and the ordinary test result are committed separately, then all three commits are pushed to `origin/main`; final remote verification is recorded in the task completion message. Private corpus, generated views, screenshots and diagnostic logs remain local and ignored.
