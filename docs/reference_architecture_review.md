# Local reference architecture review

Inspected on 23 October 2026, using only `../../autonomous_ai` relative to this
report (`../autonomous_ai` relative to Mira's project root). No runtime imports,
service control, corpus migration or writes to that project were performed.
The Mira working tree initially was clean on `main`, origin
`https://github.com/saolda/Mira.git`, at `1aac829`.

## Reuse assessment

| Area and concrete local files | Assessment | Phase 1 action |
| --- | --- | --- |
| `src/memory.py`: `SemanticDirectory`, `memory_metadata`, `regenerate_directory` | Substantial adaptation. SQLite replacement, cosine ranking and Nomic search prefixes are useful; title/about vectors and path identities do not meet unit retrieval requirements. Goal-directory rendering couples indexing to runtime state. | Reimplemented unit records, FTS5, document summaries and model metadata in `src/mira/index.py`; conceptual reuse of cosine search and document/query prefixes. |
| `src/models.py`: `LocalModels.embed`, `_post`, `_start`, `_recover` | The embedding HTTP request shape needs minimal adaptation. The class's process ownership, global configuration, inference gates and automatic recovery should not carry forward into this foundation. | Small independent `NomicHTTPEmbedding` client. Reused local Nomic GGUF artifact for a real CPU demonstration. No import of the reference backend or automatic service startup. |
| `experiments/memory_relationships/phase1c/format.py`: `blocked_lines`, `mask_inline_code`, `markers`, `headings`, `parse` | Useful minimal marker and terminal-fence grammar, Markdown token inspection and digest patterns. Requires adaptation for new metadata, questions, equations and standard finding fields. | New bounded parser with the same principles; ignores code/quote/list markers, validates reserved syntax, uses `markdown-it-py` already available locally. No wholesale code copy. |
| `experiments/memory_relationships/phase1c/index.py`: `validate`, `edge_key`, `rebuild`, `neighbors` | Useful derived-only edges, incoming target index, symmetric duplicate detection and status filtering before LIMIT. Experimental evidence schema and finding-only targets differ. | Reimplemented whole-corpus validation and SQLite indexing. Rejected/proposed edges excluded by default but explicitly queryable. |
| `src/equations.py`: `candidate_schema`, `validate_candidates`, `stage` | Requires substantial adaptation. Structured expression, variables, assumptions and provenance are useful. Sequential legacy IDs, path arrays, implicit deduplication and transaction-local staging depend on old COMMIT semantics. | New stable `e_<origin>_<ordinal>` JSON objects and local equation-reference anchors. Identity is preserved when another memory references an equation. No automatic equivalence merge. |
| `src/commit.py`, `src/state_update.py`: memory creation, `canonical_memory_path`, provenance updates | Redesign. Goal ownership/title overlap/path slugs and replacement of whole research bodies are unsuitable for stable finding IDs. | Explicit monotonic allocators, standard finding fields and structural identity guards. No heuristic identity reuse. |
| `src/commit_persistence.py`: `persist`; `src/util.py`: `atomic_write`, `FileMutex` | Single-file replacement and serialization patterns are useful. Temporary backup plus exception rollback is not crash-safe multi-file commitment. | New complete canonical snapshots, fsynced files/directories and atomic CURRENT pointer. No reuse of rollback implementation. |
| `src/validation.py`, `src/update_contract.py`, `src/cycle_inference.py` | Structured response contracts, output-length rejection and bounded repair are lessons for later LLM integration. Structural validity cannot prove warranted reasoning. | Deterministic schema/endpoint validation only; no speculative LLM abstraction. |
| `src/state_synthesize.py`: `synthesis_context`, `validate_synthesis` in `src/validation.py` | Source selection and explicit truncation are useful lessons, but path-based context and generated conclusions require redesign for complete finding/provenance retrieval. | Complete canonical unit/document retrieval. No automatic synthesis. |
| `src/goals.py`, `src/long_term_goals.py`, `src/state_goal_management.py` | Redesign/adapt later. Keep question identity distinct from goal lifecycle; avoid embedding goal projections inside knowledge index rebuilds. | Questions stored independently; goal orchestration excluded. |
| `src/cycle.py`, `src/state_registry.py`, `src/state_commit.py`, `src/run_provenance.py` | Stage contracts and auditable state transitions useful later. Existing runtime projections and staged operations cannot simply be ported. | No cycle engine, runtime state or service launcher carried forward. Snapshot parent lineage supplies bounded commit history. |
| `tests/test_equations.py`, `tests/test_memory_relationship_phase1b.py`, `tests/test_memory_relationship_phase1c.py`, `requirements.txt` | Reuse testing ideas: invalid references, malformed markers, deletion/rebuild equivalence and scope/direction negatives. Avoid importing runtime fixtures or large speech/model dependencies. | New unittest suite with synthetic fixtures, process-crash and concurrent-writer tests; one lightweight parser dependency. |

No existing Python modules were copied verbatim. The actual reused assets are the
local embedding model, available Markdown parser, and the engineering patterns
identified above. Rewriting small components avoids their old configuration,
process-management and runtime-state dependencies.

## Experiment lessons

Read `docs/memory_relationship_architecture.md` (Phase 1),
`docs/memory_relationship_llm_experiment.md` (Phase 1B), and
`docs/memory_relationship_phase1c.md` plus the Phase 1C format/index modules.
These are local reports, not newly reproduced experimental findings.

Phase 1 establishes path-coupling and the gap between rollback and durable commit.
Its HTML/end-marker schema was subsequently superseded by simpler Phase 1C markers.
Phase 1B reports erroneous relationship directions, fragile quotation reproduction,
and title/about candidate vectors. Phase 1C reports structural segmentation success
but failed overall semantic acceptance, reversed synthesis direction and blanket
critic rejection of real proposals. Agreement from two same-model roles does not
supply independent evidence. Corpus preservation is not evidence of unit coherence.

Mira therefore does not migrate these findings, infer relationships from similarity,
claim structural validation establishes entailment, or promote model proposals.
`reviewed` records a supplied review status, not independently verified truth.
The synthetic fixture's example.org citation is explicitly fictional evidence.
