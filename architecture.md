# Mira Architecture

**Status:** Provisional design, 24 October 2026  
**Reference:** local `../autonomous_ai` (read-only)

## 1. Purpose and knowledge

Mira researches an overarching question, develops expertise, and presents human-readable research. Mira 2 begins with an empty corpus.

A **memory** is a structured Markdown document stored in `memories/`, with a stable document ID (e.g. `r2f`, `s4`). Findings use `[#f1]` / `r2f#f1`; questions `[#q1]`; equations `[#e1]` with external JSON IDs such as `e_r2f_1`; images `[#i1]` with stable asset IDs such as `i_r2f_1` and a separate file extension. Findings record proposition, explanation, provenance, kind and evidence status. A terminal `## Relationships` JSON section records outgoing edges; incoming edges are derived. A rebuildable knowledge index supports exact, full-text, semantic and relationship retrieval.

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

`synthesis_score` is **separate** from `unsynthesized_memory_count`: the count measures available material; the score orders synthesis candidates and may include a completion bonus. The score formula and minimum eligible count are not yet specified. `living_descendant_count` counts living nodes below the node, excluding the node itself. These three values are updated along the ancestor chain after a relevant mutation.

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

New child nodes start living with **priority 0**; the initial root starts at 10. Inactive living nodes accrue priority up to the maximum. This discourages immediate repeated descent into newly created branches but does not mathematically guarantee a balanced tree. Track maximum depth and the distribution of living nodes by depth; consider corrective tree-tending rules if imbalance emerges.\n\nThe active research node receives a sustained turn. After each research cycle on it, its priority decreases by 1; every *other living* node gains 1, capped at `priority_max`. Only when the active node reaches 0 (or ceases to be living) is the highest-priority living node selected. A global priority offset may implement inactive-node increments without modifying every node. Tie-breaking remains to be specified.

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

An exhausted node with no living descendants and sufficient unconsumed material is given preferential synthesis priority. The exact score, minimum-material threshold and context budget are configurable design parameters still to be fixed.

### 6.1 Synthesis states

| State | Predicate | Action | LLM |
|---|---|---|---|
| S1 | No top candidate, or candidate has no eligible unconsumed inputs | Log the condition; do not synthesize | No |
| S2 | Candidate has eligible unconsumed inputs | Find a fitting node or bounded batch; synthesize inputs into one synthesis memory | Yes |

### 6.2 Selection and synthesis algorithm

```python
candidate = synthesis_candidates.top()
if candidate is None or candidate.unsynthesized_memory_count == 0:
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
if not inputs:
    log_synthesis_no_fitting_inputs(node)
    return

context = ancestor_questions(node) + [root_question()]
proposal = llm_synthesize(question=node.question,
                          context=context,
                          input_memories=load_complete_memories(inputs))
commit_synthesis_memory_and_consumption_marks(proposal, inputs, node)
update_counts_and_candidate_scores_up_to_root(node)
if node.status == "exhausted" and no_living_descendants(node) \
   and no_unconsumed_inputs(node):
    node.status = "complete"
    update_counts_and_candidate_scores_up_to_root(node)
```

`choose_unconsumed_frontier_memories` selects research memories not yet consumed **and** synthesis memories not yet consumed, without also including memories already represented by those syntheses. This avoids counting the same source twice. A synthesis memory can subsequently be consumed by a higher-level synthesis. The operation records exactly which input memory IDs contributed.

A context budget must be checked using estimated tokens, not memory counts alone. If a subtree is too large, descend; if one node's own material is too large, synthesize a bounded batch. A synthesis is committed together with its input-consumption marks, or neither is committed.

An exhausted node becomes `complete` when it has no living descendants and its available inputs have been consolidated into a current final synthesis (or it has no useful material to synthesize). Its final synthesis memory remains unsynthesized so its parent can consume it. Therefore a nonzero `unsynthesized_memory_count` does **not** by itself prevent completion. Completing a node can make its parent's synthesis more urgent. Completion handling for nodes with no useful memories must not require an LLM pass.

### 6.3 Ancestor aggregates

For a mutation at node `n`:

```python
apply_local_mutation(n)
while n is not None:
    n.unsynthesized_memory_count = local_unsynthesized_count(n) + sum(\n        child.unsynthesized_memory_count for child in children(n))\n    n.living_descendant_count = sum(\n        int(child.status == 'living') + child.living_descendant_count\n        for child in children(n))\n    n.synthesis_score = score_synthesis_candidate(n)\n    update_synthesis_candidate(n)
    n = parent(n)
```

This traverses **O(tree height)** ancestors, not necessarily O(log n): the research tree is not guaranteed to be balanced. The displayed child sums also incur work proportional to the number of children; an implementation can maintain incremental aggregates. Priority-list maintenance has its own cost. Tree monitoring records maximum depth and node counts by depth to assess whether low child priorities are keeping growth reasonably balanced.

## 7. Persistence and design boundaries

State changes, new memories, and consumption marks must be durably committed with recovery semantics; a failed synthesis must not mark its inputs consumed. Canonical knowledge is authoritative; derived indexes can be rebuilt.

The following remain **undecided**: node-health/repair rules, synthesis scoring formula and minimum threshold, child-selection and batch-ordering policy, exact LLM prompts and JSON outputs, tie-breaking, context-budget reserve, completion of empty branches, exact final-synthesis currency test, tree-imbalance thresholds and repairs, and atomic persistence protocol. These are design tasks, not implied implementation details.

This document supersedes previous fixed-stage cycle proposals and previous synthesis proposals, including a separate synthesis process. Implementation notes may be created separately after these contracts are settled.
