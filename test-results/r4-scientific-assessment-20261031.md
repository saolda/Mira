# R4 scientific assessment — 31 October 2026

Implemented the exact supplied R4 prompt and `answered | kill | unresolved` contract. Full suite: **381 passed**, zero failures, errors or skips. See [latest.md](latest.md) for the invocation results.

R4 receives exactly three prompt inputs:

```text
question
question_scope
  parent_question, root_question, is_root, research_objectives
scientific_evidence
  memories: IDs, owning questions, summaries, sources, immutable evidence references, lineage
  findings: exact anchors, propositions, qualifications, evidence status, explanations, provenance
            synthesis findings also retain exact supporting_anchors
  unresolved_questions, other_questions, other_units, equations
  relationships: exact scientific endpoints, types and evidence status
  coverage: selection policy, included IDs, omitted memories/reasons,
            missing/excluded support anchors, uncited synthesis findings, truncation status
```

The deterministic projection includes all eligible research and synthesis in the selected subtree, related syntheses that integrate that evidence, and the complete supporting scientific-memory closure. Consumed originals remain available. Shared findings appear once by stable anchor. Contradictions, qualifications, unresolved questions, equation assets and source attribution remain intact. Killed branches and syntheses with killed lineage stay excluded. Legacy syntheses without exact citations are explicitly marked uncited; lineage evidence is supplied without inventing supporting anchors.

There are no provider configurations, queries, term lists, scheduling fields, full Markdown documents or extra model calls in R4 context construction. No selected scientific text is truncated. The complete rendered request uses the existing tokenizer/context-budget check and fails explicitly before dispatch if oversized. Known missing required support prevents an `answered` response from being accepted.

| Validated decision | Committed transition |
| --- | --- |
| `answered` | `living → answered`; memories, history and lineage preserved |
| `kill` | `living → killed`; root kill rejected; non-root criterion is irrelevance to **both** parent and root objectives |
| `unresolved`, searches available | Remain living; retain prior terms and reset concepts/provider cursor for R1 |
| `unresolved`, `search_blocked=true` | `living → exhausted`; retain blocked state and commit `exhaustion_reason=search_blocked` plus R4 decision, interaction and event reference |

A blocked plan reaches R4 on its next eligible direct action, including when no R2 search occurred. Pending R3 evidence and deferred searches continue to prevent R4. Independent capacity exhaustion remains intact; an already blocked plan receives its scientific assessment first. R5 accepts below-threshold search exhaustion only with its validated, immutable R4 cause and committed event proof. Its existing branching predicate, child allocation and split receipts are preserved. Repeated-only plans cannot restart an R1/R4 loop or fabricate searches.

Focused tests cover supported and unsupported synthesis, conflicting findings and evidence gaps, incomplete support, distinct parent/root relevance, root kill rejection, approved slots, exact scientific anchors and attribution, nested/descendant synthesis, consumed evidence, killed lineage, legacy uncited synthesis, both unresolved paths, below-capacity R5, immutable exhaustion causes, R3/deferred guards, repeated-search termination, context-budget failures and journal recovery at prepared/state-replaced/pre-commit interruption points. The full suite retains existing experiment, historical prompt, memory-format, research, capacity, synthesis, source and storage regressions.

Preservation: all **954** pre-existing research/log files and symlinks retain their exact contents or link targets. No research memories, historical experiments or execution logs were modified or deleted. `architecture.md`, `futureWork.md` and every prompt except R4 are unchanged.

Remaining defects: no known implementation or regression defects. Scientific assessment tests use controlled scripted fixtures; support judgments and parent/root relevance remain model responsibilities, and no live scientific-quality experiment was run.
