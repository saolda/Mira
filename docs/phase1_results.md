# Phase 1 implementation results

Completed 23 October 2026 on the Fractal Ubuntu development workspace. The
original two project documents were preserved unchanged. Work began from clean
`main` at `1aac829`; fetching origin before completion found no remote changes.

## Delivered

A standalone Python foundation creates research/synthesis memories, findings,
questions, external equation definitions and outward relationships. Stable unit
IDs resolve to complete canonical content and containing documents. SQLite
provides exact lookup, literal-phrase full-text retrieval, incoming/outgoing edge
queries with type/status filters, document summaries and replaceable vector search.
Deleting SQLite and rebuilding retains equivalent query results. Canonical writes
validate the entire corpus and publish a complete staged snapshot atomically.

Implementation contracts and commands: [knowledge_foundation.md](knowledge_foundation.md).
Local investigation and reuse decisions:
[reference_architecture_review.md](reference_architecture_review.md).
No reference-project modules, memories, logs, goals or runtime state were imported.
No old service was modified, started or stopped. The separately launched Mira
CPU embedding server on localhost:18091 was stopped after the demonstration.

The local Nomic model artifact and existing Markdown parser were reused. HTTP
embedding request shape, Nomic prefixes, cosine retrieval, simple Markdown anchors,
derived-only relationships and status-filtered navigation were adapted as patterns.
The modules were independently written to avoid old runtime/config dependencies.

## Verification and actual outputs

**34 automated tests passed**, using Python 3.14.4. Complete output is saved in
[test_output.txt](test_output.txt). Tests cover malformed/duplicate anchors and JSON,
missing endpoints, invalid endpoint combinations and synthesis actor direction,
unsupported statuses/types, duplicate/reversed symmetric edges, stable IDs,
equation reuse, CAS conflicts, prohibited unit edits, empty stores, vector validation,
model changes, stale-index rebuilding, SQLite/FTS/canonical integrity, external-file
modification detection and index deletion/rebuild equivalence.

Process tests actually call `os._exit(23)` before and after pointer publication.
Both title changes and a two-file equation-plus-Markdown update expose either the
old complete state or the new complete state after reopening. Four concurrent
processes append questions with distinct monotonically allocated IDs. These are
application-crash/concurrency tests, not physical power-loss tests.

Editable package installation succeeded in an isolated `/tmp` virtual environment
using existing site packages and no dependency downloads. The installed `mira`
entry point, source compilation and whitespace checks also passed.

[demo_output.json](demo_output.json) records the synthetic end-to-end run:

| Demonstration | Actual result |
| --- | --- |
| Initial corpus | 2 research documents, 1 synthesis; 6 findings, 2 questions, 2 equation anchors, 1 shared equation definition. |
| Search index | 14 records: 3 summaries, 6 findings, 2 questions, 2 equation aliases, 1 definition. |
| Relationships | 6 canonical assertions, including one rejected SUPPORTS proposal; rejected/proposed assertions excluded by default. |
| Incoming traversal | `s1#f1 SYNTHESIZES r1#f1` returned from `r1#f1` incoming lookup. |
| Lexical query `thermal energy` | `r2#f1`, `r1#f1`. |
| Exact and equation retrieval | Complete `e_r1_1` JSON returned; reuse keeps the origin and global identity. |
| Delete/rebuild | Identical lexical hits, vector hits, relationships and summaries. |
| Invalid target | Rejected with `missing target: rzz#f1`. |
| Stale draft | Rejected with `newer document revision exists`. |
| Interrupted publication | Current snapshot unchanged; one unpublished generation reported. |
| Final integrity | `ok`, 15 records and 6 relationships after an additional conflict-test question. |

The deterministic test-double vector results in that output verify plumbing and
rebuild equivalence only. They are **not semantic-search quality evidence**.
The readable fixture files are in [examples/corpus](../examples/corpus).

## Real semantic retrieval

[semantic_demo_output.json](semantic_demo_output.json) contains the real Nomic run,
including model SHA-256, 768-dimensional embeddings, scores and top three findings.
It used the pre-existing `nomic-embed-text-v1.5.Q5_K_M.gguf` on a separate CPU server;
no large model download or GPU/service reconfiguration was needed.

| Authored paraphrase query | Authored expected finding | Rank | Cosine |
| --- | --- | ---: | ---: |
| How can a jacket slow the escape of warmth? | `r2#f1`, Thermal barrier | 1 | 0.6184 |
| What makes a hot item cool down? | `r1#f1`, Heat transfer | 1 | 0.6784 |
| When is treating an entire object as one temperature inaccurate? | `r2#f2`, Scope limitation | 1 | 0.7460 |

All three literal-phrase searches returned no findings. The vector results show
useful paraphrase retrieval on these authored fixtures. This is three selected
queries over six findings, with expectations authored by the implementing assistant;
there was no held-out human-adjudicated evaluation, adversarial distractor set,
threshold calibration or production recall estimate. Similarity did not create or
approve any relationships. The fictional external citation was not fetched or
represented as verified evidence.

## Limitations and decisions requiring review

- The exact v1 Markdown/header/relationship format, evidence/question/status
  vocabularies and endpoint matrix are provisional implementations of open items
  in architecture Draft 0.2. Review them before declaring a durable public format.
- Existing unit/equation contents are immutable; even minor wording and question
  lifecycle changes are rejected. Document title/summary/metadata and explicit
  relationship updates work, with revision guards. Material revision, retirement,
  splitting, merging, relocation and source equivalence are not implemented.
- Structural validation cannot assess support, contradiction, historical attribution
  or matching assumptions. A supplied `reviewed` status is not independent evidence.
  No semantic admission pipeline or passage-level evidence revision pins exist.
- Snapshot copying and retained generations consume O(corpus size) per mutation.
  Locking is Linux/local-filesystem/cooperative. External manual generation edits
  fail closed; there is no supported bulk file import, compaction or history reset.
- Derived indexing is lazy after canonical publication. Queries rebuild if needed
  and fail rather than serving an old generation; an unavailable embedding backend
  may therefore delay the first vector-configured query after a write. Canonical
  commit success remains distinct from indexing success.
- Full-text input is a literal phrase. Vector search scans all records. There is
  no hybrid reranking, calibrated relevance cutoff, bounded context assembler,
  automatic model lifecycle or production-scale retrieval backend.
- No LLM interface module was added: this phase makes no LLM calls and a speculative
  unused interface would add scaffolding. Future integration must use explicit
  structured contracts and canonical context.
- The implementation was reviewed and tested by its implementing assistant. An
  independent human/code review and human semantic assessment remain outstanding.
- All requested scope exclusions remain excluded: no autonomous cycles, goal
  selection, external research, relationship discovery, automatic synthesis,
  chat/web UI, migration, graph viewer, HistoryOfAI or deployment.

Recommended next milestone: review the v1 canonical contracts and implement a
bounded finding/question revision policy with semantic-continuity checks and
revision-pinned evidence. Build a small human-adjudicated retrieval/direction/scope
set before connecting LLM research or relationship admission.

## Files and Git handoff

New code: `src/mira/{format,store,index,embeddings,api,cli,demo}.py`, package entry
points, `pyproject.toml`, `.gitignore`. Tests: `tests/test_foundation.py`.
Artifacts: `examples/corpus/*.md`, `examples/corpus/e_r1_1.json`,
`examples/semantic_demo.py`, and the three output files linked above.
`README.md` links the original specification and the three new reports.

The implementation and its results are committed in separate reviewable commits.
The completion message records the final pushed SHA, avoiding a self-referential
commit hash in this report.
