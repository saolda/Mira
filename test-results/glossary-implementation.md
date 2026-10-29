# Persistent research glossary implementation

Validated on Fractal, 29 October 2026. Baseline: `1ab9092` on `main`.

## Implementation

Added per-experiment canonical `glossary/gN.json` records with stable IDs,
source passages, qualifications, multiple definitions, aliases, node ownership
and typed relationships. SQLite provides rebuildable exact/alias, FTS and
relationship lookup. Only touched term records are updated. The existing journal
commits terms, research memory, processed-source cursor and event together; a
small state commitment supports sparse integrity checks and forward recovery.
Explicit validation/recovery inspection audits the complete glossary.

R3's existing call accepts optional `terms`; legacy responses still work.
Python checks source IDs and exact passages. Definitions must quote a supported
definitional statement; unsupported proposals are logged independently of useful
research extraction. Glossary-only results allocate no empty research memory.
Source-supported parenthetical abbreviations are normalized, shared abbreviations
remain ambiguous, and conflicting definitions/provenance are retained.

R1 uses bounded, safety-filtered indexed retrieval: default 12 entries and a
3,200-byte conservative token upper bound, configurable at initialization.
Relevant question/ancestor/finding terminology precedes novelty. Suggested IDs
are logged separately from per-node IDs actually used in provider queries;
query history includes usage/outcomes. Cooldown skips do not mark usage.
Previous-search guidance, provider queries, scheduling, S1/S2 and canonical
knowledge-unit formats remain intact. No additional inference calls or actions.

`architecture.md` documents the contracts. Regenerate derived output explicitly:

```sh
PYTHONPATH=src python3 -m mira glossary-export --experiment NAME
PYTHONPATH=src python3 -m mira glossary-rebuild --experiment NAME
```

The export is `research/glossary.md`, alphabetized without case sensitivity.
R3 does not regenerate it automatically.

## Tests and scaling

Complete suite: **265 passed**, including 20 glossary tests covering grounding,
invalid optional proposals, candidates, deduplication, ambiguous abbreviations,
conflicting definitions, typed links, export, selective updates, recovery at four
publication boundaries, damaged payload rejection, index rebuild, relevance,
budgets, actual/suggested usage, cooldowns and legacy compatibility. Existing
synthesis/controller tests also pass. Existing test-fixture SQLite resource
warnings remain non-failing.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONPATH=src:tests python3 tests/benchmark_glossary.py
```

The synthetic benchmark uses **10,000 canonical term records** and a prewritten
committed fixture; it measures retrieval separately from fixture construction.
Thirty warm retrievals averaged **2.006 ms** (median 1.989, maximum 2.444).
Each selected **12 entries**, serialized to **2,990 bytes**, and deserialized
**12 canonical records**, with no glossary enumeration. A complete scripted R1
cycle took **0.780 s**, read the same 12 term records, and committed successfully.
Setup plus explicit integrity audit/index rebuild took 5.212 s. These are local
measurements, not latency guarantees. Normal controller journal/core-state scans
remain; this change avoids a full terminology scan/deserialization on each R1.

## Short medical validation

Fresh experiment: **`medical-glossary-20261029-065011`**.
Full local results:
`/home/eric/Dev/Mira/memory/research/medical-glossary-20261029-065011/`.
Inspect `validation.json`, `transcript.md`, `glossary/`, `research/glossary.md`,
`research/results/` and `interactions/` there. Generated research and raw responses
are excluded from this commit.

Used the requested pulmonary-mass question, explicit `medical` strategy, local
Qwen3.6-35B-A3B Q4_K_M, a verified 16,384-token server context and 4,096-token
output reserve. Stopped gracefully after two complete provider rounds:
**41.929 seconds, 20 committed cycles, 10 model calls** (R1: 2, R3: 7, R4: 1).
One research memory was created; synthesis was not reached in this short run.

R3 admitted **3 candidate terms, 0 definitions, 3 supporting passages, 0 merged
duplicates and 0 rejected proposals**: immune reconstitution inflammatory syndrome
(IRIS), cryptococcoma, and liposomal amphotericin B (LAmB). The abstract mentions
these terms without supplying extractive definitions; Python did not invent any.
All three were supplied to the second R1. It used **g1 and g2** in this new query:

> immune reconstitution inflammatory syndrome pulmonary mass cryptococcoma enlargement differential diagnosis

The initial query concerned rapidly enlarging spiculated pulmonary masses and
infectious/inflammatory/malignant differentiation. Thus both round queries were
novel, with **zero repeated rounds**. Actual g1/g2 usage was recorded for PubMed,
Europe PMC, Crossref and Wikipedia; the OpenAlex cooldown was correctly excluded.
The three glossary entries added **199 native tokenizer tokens** to the second R1;
the whole prompt was 1,515 tokens. Warm retrieval averaged **1.155 ms**.

| Provider | Two-round outcomes | Accepted sources | Duplicates |
| --- | --- | ---: | ---: |
| PubMed | 2 empty | 0 | 0 |
| Europe PMC | 2 successful | 3 | 1 |
| OpenAlex | HTTP 429, then cooldown skip | 0 | 0 |
| Crossref | 2 successful | 4 | 0 |
| Wikipedia | 2 empty | 0 | 0 |

All seven accepted sources were processed. Validation and recovery were clean;
no JSON, budget or extraction errors occurred. Historical experiment and protected
file hashes were unchanged during the run. The temporary Qwen server was stopped.
An earlier 39.598-second fresh probe exposed the redundant parenthetical-label
case, now covered by a regression test; its state remains in
`medical-glossary-20261029-064751`.

Compared with [the earlier medical test](medical-strategy.md), which repeated a
query after its third round, this run demonstrates discovery and actual reuse of
specific source terminology. Two rounds do not establish sustained improvement.
Empty/rate-limited retrieval is not negative clinical evidence. No individual
patient was assessed.

## Limits

Grounding checks establish textual support, not scientific truth. Conservative
extractive definitions and explicit naming/relationship patterns can reject valid
paraphrases or omit links to unavailable targets. Bare acronyms retain conservative
source/definition scope. Untouched record corruption is discovered at lookup or
an explicit full audit. A missing index requires a full rebuild once; exports
remain stale until requested. This short run exercises candidate discovery and
usage; sourced/conflicting definitions and crash recovery are demonstrated by
deterministic fixtures. The existing broader R4 history/context growth limit is
unchanged. R3's case-report summary still requires scientific review of attribution
and generalization; this test establishes terminology flow, not clinical validity.
