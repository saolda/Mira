# Medical research strategy — 29 October 2026

Added `medical` using the existing strategy catalogue, with the exact ordered
sequence `pubmed → europe_pmc → openalex → crossref → wikipedia`. All five
adapters were already implemented and registered. The existing `biomedical`
strategy and every other strategy retain their descriptions and provider order.
R0 receives the new catalogue entry automatically; explicit selection remains
`research-init QUESTION --strategy medical`. No controller actions, scheduling,
canonical memory formats or storage structures changed.

Metadata checks also repaired three omissions: PubMed now retains supplied date
components; Europe PMC's source-qualified MED/PMC record IDs retain their
PMID/PMCID meaning when redundant identifier fields are absent; OpenAlex retains
supplied PMCIDs and DOI values available through `ids`. Missing metadata is left
missing. Existing source descriptors retain author lists, titles, dates and
identifiers; canonical compact memories retain inherited source provenance, with
provider attribution available through their immutable evidence references.

These mappings follow [NCBI's PubMed XML documentation](https://www.ncbi.nlm.nih.gov/books/NBK3828/),
[Europe PMC's service reference](https://dev.europepmc.org/doc/EBI_Europe_PMC_Web_Service_Reference.pdf)
and [OpenAlex's work attributes](https://help.openalex.org/data/works/attributes/).

## Deterministic verification

`PYTHONPATH=src python3 -m unittest discover -s tests -q`

**245 tests passed**, including nine new tests covering registration, exact order,
explicit and R0 selection, real adapters with mocked HTTP, metadata/provenance,
restart-safe PubMed/Europe PMC deduplication (including PMID-only matches),
OpenAlex PMCID matching and preservation of all existing strategies.

## Short live validation

Root question: “What conditions cause rapidly enlarging spiculated pulmonary
masses in older adults, and which clinical, imaging, microbiological and
pathological findings distinguish infectious, inflammatory and malignant causes?”

The separate live R0 check selected **medical**, citing the clinical differential
and diagnostic scope. Its state and request are in
`/home/eric/Dev/Mira/memory/research/medical-r0-20261029-061459/`.

The actual research experiment explicitly selected `medical`:
`/home/eric/Dev/Mira/memory/research/medical-strategy-20261029-061459/`.
Inspect `validation.json`, `research/state.json`, `supervisor.jsonl`, `interactions/`,
`memories/` and `transcript.md` there. Historical experiments were unchanged.

Used local Qwen3.6-35B-A3B-Q4_K_M, its native chat template/tokenizer, a
**16,384-token context** and **4,096-token output reserve**, with normal research,
branching and synthesis scheduling. The ten-minute maximum was not reached:
the supervisor stopped on an R4 context-budget rejection after **383.4 seconds**.
There were **118 attempted cycles**, 117 committed actions and **52 research-run
LLM calls**, plus the separate R0 call.

| Provider | R2 outcomes | Retrieved rows | Unique accepted | Duplicates |
| --- | --- | ---: | ---: | ---: |
| PubMed | 13 empty responses | 0 | 0 | 0 |
| Europe PMC | 13 successful responses | 26 | 3 | 23 |
| OpenAlex | 1 HTTP 429; 12 cooldown skips | 0 | 0 | 0 |
| Crossref | 13 successful responses | 26 | 4 | 22 |
| Wikipedia | 13 empty responses | 0 | 0 | 0 |

All five providers were visited in the requested order in each of 13 rounds.
OpenAlex was rate-limited; no provider was silently substituted. Empty responses
reflect these queries, and retrieval failures/rate limits are not negative clinical
evidence. Later R1 calls repeated the same phrases, causing a discovery plateau.

Seven unique publications were processed in seven R3 calls: **three research
memories** (13 units total), four empty extractions and no invalid R3 responses.
One nonempty summary accompanying empty results was safely normalized. A separate
S2 call created **one synthesis** with validated cross-memory references.

The two Europe PMC research memories retain DOI, PMID and PMCID. The Crossref
memory for DOI `10.1136/bcr-2021-247495` retains its supplied DOI; missing PMID/PMCID
values were not invented. Source descriptors preserve authors and dates, and
provider identity is retained in each immutable evidence batch. Research memories
remain source-linked and qualified; explicit prose attribution is stronger in the
case-report extraction than in the general review propositions. This is structural
validation of abstract-based extraction, not independent clinical verification.

Deduplication excluded **45 repeat rows**. PubMed produced no live matches, so
PubMed/Europe PMC overlap was verified deterministically instead: the same
publication, including a PMID-only match with differently formatted author names,
produced exactly one R3 memory across a restart. No fuzzy clinical-title matching
or new identity store was introduced.

## Remaining limitations

The rejected R4 request required **12,307 prompt tokens + 4,096 output tokens =
16,403**, exceeding the configured 16,384 by 19. The rejection occurred before
inference; state was preserved. The root remains living, not answered. Accumulated
search history and repeated R1 phrases are existing controller/query-refinement
limitations; no controller or prompt changes were made to hide them.

Canonical validation and the rebuilt index passed (**4 documents, 21 indexed
records, 26 relationships; integrity: ok**). No incomplete recovery operations or
persistence problems remained. Protected code/prompts and historical files matched
their pre-run hashes. The temporary model server was stopped; `autonomous_ai`
remains disabled. The existing adapters use supplied abstracts or bibliographic
text, not newly downloaded full-text papers. No patient diagnosis was attempted.
Generated research, transcripts and downloaded responses remain local and ignored.
