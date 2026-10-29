# S1/S2 synthesis redesign — 29 October 2026

Implementation commit: `907cef3efd5d72d68cac4fcce41b9c6ccc0a860a`.

## Implementation

Implemented the supplied synthesis architecture using the existing controller,
templates, canonical memories, interaction records and live-store journal:

- S1 makes one fresh model call, validates eligible IDs and five integer scores,
  records the analytical objective, and persists a pending S2 selection. Cross-branch
  outputs belong to the inputs' deepest common ancestor.
- S2 runs in a separate cycle, validates exact supplied unit references, and requires
  at least one finding supported by two distinct input memories. Only referenced
  contributors are consumed. Partial synthesis and `no_synthesis` are supported.
- The attempt register records content hashes, objectives, scores, interaction IDs,
  dispositions, contributors, unused inputs and outputs. Completed combinations
  exclude themselves and their subsets; failed/pending attempts do not. Changed
  hashes reopen eligibility.
- Pending dispatches use the existing independent request receipts. Completion,
  synthesis publication and consumption share one journaled operation. Repeated
  repair does not repeat inference or allocate duplicate memories.
- Terminal completion waits for research, R5, pending S2 and permitted synthesis.
  A terminal `no_candidate` fingerprint prevents repeated calls on unchanged data.
  Complete S2 inputs are preferred, with lossless projections as fallback; selected
  memories are never silently removed to fit the budget.
- Old v1/v2 experiments remain readable without migration during inspection.
  New bookkeeping is added on the next successful action. Memory formats, unit
  types, equation handling, provenance and historical files are preserved.

The supplied `architecture.md` revision is included unchanged. Unrelated existing
R0/R3/R4/R5 prompt edits and R3/provider fixes remain outside these commits.

## Changed files

- `architecture.md` — supplied authoritative synthesis specification.
- `prompt_templates/S1.txt`, `prompt_templates/S2.txt` — selection, objective,
  selective synthesis and dispositions.
- `src/mira/{prompts,gardener,research,research_tree,research_demo}.py` — prompt
  bindings, validation, scheduling, persistence, compatibility and fictional demo.
- `tests/test_{synthesis,budget,collections,gardener,prompts,r3,strategies,viewer}.py`
  — deterministic contracts, budget boundaries, exclusions/revisions, selective
  consumption, scheduling, restart, crash recovery and compatibility coverage.
- `test-results/synthesis-redesign.md` — this report.

## Automated tests

Command: `PYTHONPATH=src python3 -m unittest discover -s tests -q`.

| Tested tree | Result |
| --- | --- |
| Exact staged implementation, exported into an isolated Git repository | **228 passed**, 39.4 seconds |
| Workspace including pre-existing uncommitted changes and eight additional tests | **236 passed**, 40.0 seconds |

The workspace baseline had 211 tests and three fixture failures caused by editable
prompts losing action-name prefixes. Fixtures now identify labelled input sections
and verify prompt contents without requiring those prefixes. Existing SQLite
`ResourceWarning`s remain non-fatal. The first isolated export needed `git init`
for the existing Git-ignore test; its subsequent full run passed.

## Short local-model validation

Used Qwen3.6-35B-A3B-Q4_K_M with the server's native chat template/tokenizer,
16,384 context tokens and 4,096 output tokens. Four abstract-based research memories
were copied into fresh experiments; no retrieval, new R3 extraction or endurance
run was performed. The controller was reopened between every cycle.

Final experiment: `synthesis-redesign-20261029-052906`.
Local results: `/home/eric/Dev/Mira/memory/research/synthesis-redesign-20261029-052906/`.
Inspect `validation.json`, `validation-inputs.json`, `research/state.json`,
`interactions/`, `memories/s1.md` and `transcript.md` there.

- **46.0 seconds, four model calls:** S1 → S2 → S1 → S2.
- S1 selected ReasFlow (`r2`) and TRACE (`r3`), score **23/25**, to compare verification
  and runtime self-correction. S2 created `s1`, citing stable references from both
  memories and discussing differing domains, self-reported evaluations and lack of
  independent verification in the supplied material.
- The next S1 selected `r1` and `s1`, score **21/25**, confirming that an existing
  synthesis remains eligible for further integration.
- That S2 incorrectly cited unsupplied originals such as `r2#f3` and `r3#f1`.
  Python rejected it, registered a **failed, retryable** attempt, created no second
  synthesis and consumed neither selected input. The frontier remained
  `r1`, `r4`, `s1`; completion correctly remained false.
- Total request estimates including output reserve were **6,796; 6,742; 6,773;
  7,901 tokens**. No context overflow occurred.
- Canonical validation passed; the rebuilt index reported **integrity: ok**.
  Five documents and 27 indexed records remained. Recovery reported no pending
  operations or problems. Historical/protected file hashes were unchanged.

Earlier experiment: `synthesis-redesign-20261029-052722`, at the corresponding
directory under `/home/eric/Dev/Mira/memory/research/`. It took **26.6 seconds** and
three calls: a successful synthesis followed by terminal `no_candidate`, leaving
three frontier memories without repeated S1 dispatch. Its rationale incorrectly
treated synthesis memories as unsuitable raw evidence. S1 now explicitly identifies
memory kinds and clarifies that synthesis memories are eligible; the final run
demonstrated that correction.

The temporary model server was stopped afterwards. `autonomous_ai` remains disabled.
No downloaded documents, generated memories or raw transcripts are committed.

## Limitations and deviations

No intentional deviations from the supplied synthesis architecture. Cross-memory
references establish structural integration, not scientific validity or novelty.
The model can still invent references or overstate author-reported results in
otherwise qualified prose; the final experiment demonstrates the reference guard,
not independent verification of the underlying papers. The failed experiment is
preserved for inspection and can resume through fresh S1 selection.

This was a controlled synthesis check using frozen abstracts, not a new retrieval
or sustained-research evaluation. Partial synthesis and `no_synthesis` were verified
deterministically rather than forced into the model experiment. Large catalogues
can still exceed S1's context budget; oversized requests fail explicitly, and
oversized S2 selections are deferred or blocked without dropping inputs.
