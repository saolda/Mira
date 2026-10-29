# Question-file implementation and medical validation

Recorded: 2026-10-29. Tested implementation: `94cbe5e1c74f235d38d26dfc19336710528bd2b1`.

**PASS: 301 tests, 0 failures, 0 errors, 0 skipped** (`PYTHONPATH=src python3 -m unittest discover -s tests -q`, 53.079 seconds). Fourteen new tests cover parsing, positional/CLI compatibility, long inputs, exact Unicode/CRLF preservation, immutable publication, four journal interruption/recovery points, restart, research/synthesis inputs and budget rejection. Existing non-failing SQLite resource warnings remain in legacy fixtures.

## Implementation

`research-init --question-file PATH` is mutually exclusive with the positional question. Python validates the documented Markdown sections, journals the original at `research/question.md`, and persists its SHA-256, exact main question, separate context and verbatim objective list in immutable `question_document` state. Restart uses the saved snapshot. R0, R1, R3–R5 and S1/S2 receive complete objectives and bounded supplementary background; R2 uses R1's query. Existing native token-budget checks include these inputs and reject oversized essential text. README and architecture describe the interface. Canonical memory formats and controller scheduling are unchanged.

## Live experiment

Experiment: `medical-question-file-20261029-074524`, initialized through the new CLI option with explicit `medical` strategy and the requested question, without added background or a predetermined answer.

Qwen3.6-35B-A3B Q4_K_M; native context **16,384** tokens; temperature 0; thinking disabled; generation limit/output reserve **4,096**; default research-capacity threshold **12,288**. The temporary local server was stopped after validation.

Run: **113.095 seconds**, 07:45:24–07:47:18 UTC; **40 research cycles**, **42 total controller cycles**, **18 model actions**. Actions: R1×5, R2×24, R3×7, R4×4, S1×1, S2×1. Stopped normally at the requested research-cycle limit, below five minutes; the experiment remains resumable.

| Provider | Opportunities | Returned records | Unique / R3-processed | Duplicate records | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| PubMed | 5 | 0 | 0 | 0 | Empty for these queries |
| Europe PMC | 5 | 10 | 4 | 6 | Successful |
| OpenAlex | 5 | 0 | 0 | 0 | One HTTP 429; four cooldown skips |
| Crossref | 5 | 10 | 3 | 7 | Successful |
| Wikipedia | 4 | 0 | 0 | 0 | Empty for these queries |

Four complete database rounds followed the configured order; the fifth reached Crossref. Rate limiting was an ordinary pointer advance, not an error. Seven unique publications/records were processed once; 13 repeated records were suppressed. No PubMed/Europe PMC overlap was returned, so cross-provider deduplication was not exercised live; existing deterministic coverage passed.

Europe PMC supplied three abstracts: a pictorial review, a retrospective single-centre deep-learning study, and another PET-CT review; plus metadata for a conference abstract book. Crossref supplied metadata for a Radiopaedia case, an educational doubling-time mnemonic and an NCI terminology record. Publication descriptions follow supplied titles/abstracts, not independent study appraisal. Available authors, dates, identifiers and URLs survived; no full texts or images were examined by Mira.

## Search, extraction and synthesis

The first R1 query joined “spiculated pulmonary nodule volume doubling time” with “malignancy versus infection differentiation”. Later queries added “rapid interval growth granuloma versus carcinoma”, mostly exchanging “lung” and “pulmonary”. Five R1 decisions produced four distinct joined queries; one repeated a previous query. Later rounds added no research memories. Search diversification was weak.

R3 created `r1` (review: two findings and one explicitly derived question; 711 Qwen tokens) and `r2` (case-title report: one finding; 496 tokens). Five other sources produced empty results. One nonempty summary accompanying empty results was discarded successfully, without rejection or repeated extraction.

The glossary admitted four source-grounded candidates: **metabolically occult**, **waxing-and-waning interval changes**, **Pulmonary invasive mucinous adenocarcinoma / PIMA**, and **SE-DAS ResNet**. Two other proposals failed deterministic passage/alias checks. Each subsequent R1 received the first two candidates and recent provider outcomes; none was used in submitted queries. Operational retrieval worked but did not improve the searches here.

S1 selected `r1+r2`, scored **17/25** (R5/C4/X3/N3/E2), and persisted the analytical objective. S2 created `s1` (1,371 tokens, three findings), with a substantive integration referencing `r1#f2` and `r2#f1`. All references validated; the attempt completed and consumed exactly `r1/r2`, leaving `s1` on the frontier. No branching occurred: the root remained living, with R5 capacity 5,798 tokens including reserve, below threshold. R4 requested further research four times.

Attribution needs improvement despite structural success. `r1` used generic findings rather than consistently naming the review authors; `r2` treated a title's biopsy account too directly as confirmed evidence. `s1#f2` incorrectly expanded missing information in one abstract into a claim about current guidelines and attributed a derived evidence gap to the source. `s1#f3` overreached from insufficient evidence to a general statement about diagnostic discrimination. Those stronger claims are not accepted as scientific conclusions here.

## Mira's evidence-grounded answer

The actual `s1` summary begins:

> The supplied materials do not provide sufficient evidence to determine whether a spiculated pulmonary lesion doubling in volume over four weeks favors infection over malignancy with any statistical strength.

That limited conclusion is supported by the run's inputs. [Lee, Yoon and Yoo's pictorial review](https://pubmed.ncbi.nlm.nih.gov/42793695/) discusses infectious/inflammatory mimics, but its supplied abstract provides no comparative doubling-time estimates. The [Radiopaedia case record](https://doi.org/10.53347/rid-157867) title reports a very rapidly doubling nodule, granuloma on biopsy and later resolution. Mira had only that title/metadata: no exact four-week interval, confirmed spiculation or microbiological proof of infection. A single such account cannot quantify an infection-versus-malignancy probability shift.

| Requested evidence | Actually obtained |
| --- | --- |
| Typical malignant volume doubling times | No numerical estimates; mnemonic title alone insufficient |
| Very rapid malignant growth | No relevant rates or examples |
| Infectious/inflammatory growth rates | One title-described rapid-growth granuloma; no measured rate distribution |
| Spiculation and malignancy risk | No quantitative risk estimate |
| CT volumetric uncertainty | No repeatability/error bounds; PET motion/partial-volume discussion is not such an estimate |
| Quantitative infection versus malignancy comparison | No likelihood ratios, comparative frequencies or calibrated probabilities |

**Confidence:** low in any etiological preference or its strength; high that this run's limited inputs do not establish one. Empty searches and rate limits are retrieval limitations, not negative clinical evidence. This is an incomplete literature search, not evidence that comparative studies do not exist.

## Persistence, budgets and local artifacts

All 18 responses passed JSON/schema validation; no context-budget or transport failures occurred. Largest prompt: 5,084 tokens, or 9,180 including reserve, below 16,384. All 18 saved prompt bindings and exact request/context/raw-response pairs matched the independent log. Both logs have end markers. Corpus/lineage, four glossary records, restart and immutable question/hash checks passed; no unresolved interactions or incomplete journals. All **5,023 historical files** checked retained their hashes.

Full local results, kept out of GitHub:

- Experiment, memories, source payloads, prompts/responses and journal: `/home/eric/Dev/Mira/memory/research/medical-question-file-20261029-074524/` (`validation.json` contains supervisor results).
- Original question file: `/home/eric/Dev/Mira/memory/questions/lung-growth.md`.
- Initialization log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-29_074525_medical-question-file-20261029-074524_3082b866ca79.jsonl`.
- Research log: `/home/eric/Dev/Mira/memory/run-logs/2026-10-29_074525_medical-question-file-20261029-074524_1e7c4c76f9e5.jsonl` (140 records, 1,964,784 bytes).

Live validation used a short question without context/objectives. Long documents, automatic R0, branching projections and interruption recovery were verified deterministically. The run confirms the new interface and persistence; it does not establish a clinically reliable answer or repair the observed search/attribution limitations.
