# Mira Architecture

**Status:** Provisional design, 24 October 2026  
**Reference:** local `../autonomous_ai` (read-only)

## 1. Purpose and knowledge

Mira researches an overarching question, develops expertise, and presents human-readable research. Mira 2 begins with an empty corpus.

A **memory** is a structured Markdown document stored directly in `memories/`, with a stable document ID (e.g. `r2f`, `s4`). Findings use `[#f1]` / `r2f#f1`; questions `[#q1]`; equations `[#e1]` with external JSON IDs such as `e_r2f_1`; images `[#i1]` with stable asset IDs such as `i_r2f_1` and a separate file extension. Findings record proposition, explanation, provenance, kind and evidence status. A terminal `## Relationships` JSON section records outgoing edges; incoming edges are derived. A rebuildable knowledge index supports exact, full-text, semantic and relationship retrieval.

## 2. Research strategies

A research strategy is an ordered list of searchable database IDs. Different question types may use different strategies. A strategy can be preselected or selected by one preliminary LLM pass; once selected, its index is fixed for the run.

```json
{
  "strategies": [
    {"id": "general", "databases": ["web", "academic"]},
    {"id": "physics", "databases": ["academic", "web"]}
  ]
}
```

Database IDs above are illustrative, not promises of implemented adapters.

## 3. Persistent state

The core state is a tree of research questions/objectives. The initial tree contains one living root, marked active, with priority 10. Research and synthesis memories are linked to their originating nodes.

**Logical schema** (fields below are required by the currently described algorithms; indexes and cache representations are not prescribed):

```json
{
  "strategy_index": 0,
  "active_node_id": "q1",
  "research_cycles_since_synthesis": 0,
  "synthesis_interval": 5,
  "priority_max": 10,
  "terminal_synthesis_bonus": 1000,
  "nodes": {
    "q1": {
      "parent_id": null,
      "child_ids": [],
      "question": "Overarching research question",
      "status": "living",
      "priority": 10,
      "keywords": null,
      "next_database_index": 0,
      "pending_results": null,
      "memory_ids": [],
      "unsynthesized_memory_count": 0,
      "living_descendant_count": 0,
      "synthesis_score": 0
    }
  },
  "living_priority_order": ["q1"],
  "synthesis_candidate_order": []
}
```

`status` is `living`, `exhausted`, `killed` or `complete`. `pending_results` is null or a durable search-result reference. The strategy index is global; `next_database_index` is per node and can reset after new keywords are chosen.

### 3.1 Memory metadata and synthesis accounting

There is **no separate memory-record object**. Each memory is one `.md` document in `memories/`; its document metadata identifies its originating tree node and synthesis lineage. Illustrative metadata for a synthesis memory:

```yaml
id: s4
kind: synthesis
node_id: q1
synthesized_by: null
source_memories: [r2f, s3]
```

`kind` is `research` or `synthesis`. `source_memories` is populated for synthesis memories and lists the exact input memory IDs. `synthesized_by` is initially null; after a successful synthesis commit, each input memory receives the ID of the synthesis memory that consumed it. Thus a **synthesized research memory** and a **synthesized synthesis memory** are simply consumed memories of different kinds. Neither is deleted.

`memory_ids` on a node links its directly associated documents. `unsynthesized_memory_count` counts **all unconsumed memories** at the node and throughout its descendants, regardless of kind. This is the subtree's synthesis-input frontier. When a synthesis consumes K inputs and creates one new synthesis memory, the relevant subtree count changes by `1 - K`. Only committed changes affect counts.

`synthesis_score` is **separate** from `unsynthesized_memory_count`: the count measures available material; the score orders synthesis candidates and may include a completion bonus. The score formula is defined in section 6; the minimum eligible synthesis batch is two memories. `living_descendant_count` counts living nodes below the node, excluding the node itself. These three values are updated along the ancestor chain after a relevant mutation.

## 4. Scheduling

Each cycle performs one action, with **at most one LLM pass**. The scheduler runs a synthesis cycle after every `synthesis_interval` research cycles (initially 5). The synthesis gardener is part of this scheduler, **not a separate process**.

```python
if research_cycles_since_synthesis >= synthesis_interval:
    run_one_synthesis_cycle()
    research_cycles_since_synthesis = 0
else:
    run_one_research_cycle()
    research_cycles_since_synthesis += 1
```

New child nodes start living with **priority 0**; the initial root starts at 10. Inactive living nodes accrue priority up to the maximum. This discourages immediate repeated descent into newly created branches but does not mathematically guarantee a balanced tree. Track maximum depth and the distribution of living nodes by depth; consider corrective tree-tending rules if imbalance emerges.

When selecting a new active node, ties are broken by **oldest node creation order** (stable node ID order only if IDs encode creation order). If no living nodes remain, log a detailed terminal event with the root question, node-status totals, unsynthesized counts and pending work before stopping research. Synthesis may continue as needed to finish the tree; a no-living-node event is unusual and must not silently terminate the process.\n\nThe active research node receives a sustained turn. After each research cycle on it, its priority decreases by 1; every *other living* node gains 1, capped at `priority_max`. Only when the active node reaches 0 (or ceases to be living) is the highest-priority living node selected. A global priority offset may implement inactive-node increments without modifying every node. Tie-breaking remains to be specified.

## 5. Research cycle

Action selection is deterministic, based on the active node:

| State | Predicate | Action | LLM |
|---|---|---|---|
| R1 | `keywords == null`, no pending results | Generate search keywords; store on node | Yes |
| R2 | Keywords exist, no pending results, database pointer within strategy | Search the next database using keywords; advance pointer; save results on node | No |
| R3 | Pending research results exist | Interpret results and create at least one structured research memory when evidence supports one; clear processed results | Yes |
| R4 | Keywords exist, no pending results, pointer past last database | Decide future of node from its question and linked memories | Yes |

R4's allowed decisions:

- `kill`: mark unproductive node killed.
- `exhaust`: mark direct research exhausted.
- `retry`: replace keywords and reset database pointer.
- `retry_split`: replace keywords, reset pointer, create related contributing child questions.
- `exhaust_split`: exhaust direct research and create child questions.

An empty search is recorded as an unsuccessful result and does not require an R3 LLM pass. A killed or exhausted node is removed from living research scheduling. These decisions may change synthesis eligibility.

## 6. Synthesis gardener

Synthesis has its **own priority-ordered candidate list**. Each research cycle recomputes the affected node's synthesis score and candidate position. Changes to memories, node status, or children also update affected ancestor counts and candidate scores up to the root.

An exhausted node with no living descendants and sufficient unconsumed material is given preferential synthesis priority. Use `synthesis_score = unsynthesized_memory_count + terminal_bonus`, where `terminal_bonus = 1000` only for an **exhausted** node with zero living descendants and at least two eligible unsynthesized input memories. The 1000 bonus is intentionally large: monitor whether terminal nodes actually dominate the candidate list and revisit the value if not. **Completed nodes are excluded** from synthesis candidates regardless of their unsynthesized count. Context budget and candidate tie-breaking remain configurable decisions.

### 6.1 Synthesis states

| State | Predicate | Action | LLM |
|---|---|---|---|
| S1 | No top candidate, or fewer than two eligible unconsumed inputs | Log the condition; do not synthesize | No |
| S2 | Candidate has at least two eligible unconsumed inputs | Find a fitting node or bounded batch; synthesize inputs into one synthesis memory | Yes |

### 6.2 Selection and synthesis algorithm

```python
candidate = synthesis_candidates.top()
if candidate is None or candidate.unsynthesized_memory_count < 2:
    log_synthesis_no_candidate()
    return

node = candidate
while estimated_frontier_tokens(node) > context_budget:
    child = highest_priority_descendant_with_eligible_inputs(node)
    if child is None:
        break
    node = child

inputs = choose_unsynthesized_memories(node, context_budget)
# If even the node's own inputs exceed budget, choose a bounded batch.
if len(inputs) < 2:
    log_synthesis_no_fitting_inputs(node)
    return

context = ancestor_questions(node) + [root_question()]
proposal = llm_synthesize(question=node.question,
                          context=context,
                          input_memories=load_complete_memories(inputs))
commit_synthesis_memory_and_consumption_marks(proposal, inputs, node)
update_counts_and_candidate_scores_up_to_root(node)
if node.status == "exhausted" and no_living_descendants(node) \
   and node.unsynthesized_memory_count <= 1:
    node.status = "complete"
    update_counts_and_candidate_scores_up_to_root(node)
```

`choose_unsynthesized_memories` selects research memories not yet consumed **and** synthesis memories not yet consumed, without also including memories already represented by those syntheses. This avoids counting the same source twice. A synthesis memory can subsequently be consumed by a higher-level synthesis. If a node's only remaining unsynthesized memory belongs to a descendant, that memory is still eligible for its ancestors; completion does not require relocating it. The operation records exactly which input memory IDs contributed.

A context budget must be checked using estimated tokens, not memory counts alone. The input selector must never choose fewer than two inputs; if the context budget cannot accommodate two, log an explicit blocked-synthesis condition. If a subtree is too large, descend; if one node's own material is too large, synthesize a bounded batch. A synthesis is committed together with its input-consumption marks, or neither is committed.

A synthesis requires **at least two distinct unsynthesized input memories**; never synthesize a single memory into another memory. An exhausted node with no living descendants becomes `complete` when its subtree contains **zero or one** unsynthesized memory. The remaining memory, if any, is its final result and remains available for synthesis by an ancestor. A node with multiple inputs must be reduced to at most one through one or more bounded synthesis batches before completion. Its final synthesis memory remains unsynthesized so its parent can consume it. Therefore a nonzero `unsynthesized_memory_count` does **not** by itself prevent completion. Completing a node can make its parent's synthesis more urgent. Completion handling for nodes with no useful memories must not require an LLM pass.

### 6.3 Ancestor aggregates

For a mutation at node `n`:

```python
apply_local_mutation(n)
while n is not None:
    n.unsynthesized_memory_count = local_unsynthesized_count(n) + sum(
        child.unsynthesized_memory_count for child in children(n))
    n.living_descendant_count = sum(
        int(child.status == 'living') + child.living_descendant_count
        for child in children(n))
    n.synthesis_score = score_synthesis_candidate(n)
    update_synthesis_candidate(n)
    n = parent(n)
```

This traverses **O(tree height)** ancestors, not necessarily O(log n): the research tree is not guaranteed to be balanced. The displayed child sums also incur work proportional to the number of children; an implementation can maintain incremental aggregates. Priority-list maintenance has its own cost. Tree monitoring records maximum depth and node counts by depth to assess whether low child priorities are keeping growth reasonably balanced.

## 7. Persistence and design boundaries

### 7.1 Canonical storage and recovery

Use a **simple live memory directory**, not copy-on-write generations or whole-corpus snapshots. The authoritative corpus is `memories/*.md`, plus canonical equation JSON assets and a persistent research-tree state file. Do not adopt the Phase 1 `knowledge/CURRENT` and `knowledge/generations/` snapshot layout for the new autonomous corpus. Retain stable IDs, human-readable documents and rebuildable indexes.

Synthesis touches several files: its new synthesis memory, the `synthesized_by` metadata of each input memory, and node/state counts. Ordinary single-file atomic replacement is insufficient to make all of those changes atomic. Therefore every multi-file mutation must have a **small operation journal** recording a unique operation ID, operation type, affected IDs, expected preconditions, intended changes, and progress. Write and durably publish the journal **before** changing canonical files. Use temporary files plus atomic replacement for each individual document; publish completion only after all affected documents and state are consistent. Journal entries are small descriptions of operations, not full copies of the entire corpus.

On startup after an unclean exit, **pause autonomous actions and perform crash-recovery assessment**: inspect incomplete journal entries, compare actual files and metadata to intended changes, validate references, and report whether the operation is complete, safely finishable, safely reversible, or ambiguous. A small CLI recovery tool should expose `inspect`, `validate`, and `repair` capabilities, with a dry-run default and explicit confirmation for changes. Never silently guess or discard ambiguous research. Successful operations must be idempotently recognisable so replay does not duplicate memories or synthesis.

The exact journal file format and durability mechanism are implementation contracts for Codex to propose and test; the above recovery behaviour is mandatory. No routine full-corpus snapshots are required. External backups remain a separate concern.

SQLite/FTS/vector/relationship indexes remain **derived, rebuildable** aids to retrieval, not authoritative knowledge. Reuse appropriate search-database adapters or source definitions from the local read-only `../autonomous_ai` reference, subject to review; these external research databases are distinct from Mira's local SQLite retrieval index.

### 7.2 Monitoring and scope

Track maximum tree depth, living-node totals, nodes by depth, child counts, synthesis-score distribution, and whether exhausted terminal nodes actually receive prompt synthesis. Provide a basic read-only project-state viewer, taking inspiration from the historical `autonomous_ai` brain viewer, without making it a prerequisite for the first controller tests.

Equations retain the existing first-class JSON/anchor model. Image references may be collected with provenance; automatic image generation and project-specific presentation generation are deferred. The core memory format stays uniform across projects; `ProjectOverview.md` describes separate presentation layers.

The following remain **undecided**: node-health/repair rules, child-selection and bounded batch-ordering policy, exact LLM prompts and JSON outputs, synthesis-candidate tie-breaking, context-budget reserve, tree-imbalance thresholds and repairs, and exact journal/recovery protocol. Codex must surface design choices before implementing consequential changes. These are design tasks, not implied implementation details.

This document supersedes previous fixed-stage cycle proposals and previous synthesis proposals, including a separate synthesis process. Implementation notes may be created separately after these contracts are settled.
