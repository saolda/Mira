# Mira Architecture

**Status:** Working outline, 24 October 2026  
**Project:** Mira  
**Historical reference implementation:** local `../autonomous_ai` (read-only)

## 1. Purpose

Mira autonomously researches questions, develops expertise in the selected topic, and presents its research in human-readable form. Research may produce findings, syntheses, questions, equations, illustrations, and relationships between knowledge units.

Mira 2 begins with an empty research corpus. The old local `autonomous_ai` project is a reference, not a compatibility requirement.

## 2. Research objectives and state

The core state object is a **hierarchical tree of research questions/objectives**.

- Each node represents a research question or objective.
- Individual research memories are linked to nodes in this tree.
- The system has an **active node**.
- The state of the tree and active node determines what action the system takes next.
- When the tree is **unhealthy**, an LLM action tends or repairs it, potentially by splitting a node/question into subnodes/questions.
- When the tree is **healthy**, the next action depends on the state of the active node.

The exact node fields, tree-health rules, active-node states, and action-selection algorithm are **not yet designed**. They must be specified as concrete data structures and deterministic algorithms before implementation.

## 3. Execution model

Each execution cycle consists of:

1. Read the persistent state object.
2. **Deterministically** select an action from that state.
3. Execute the action. It may be a deterministic operation or an LLM pass.
4. Apply the action's result to the state object and persist it.

**At most one LLM pass per cycle.**

Potential actions include online retrieval, research-memory creation, knowledge synthesis, and goal-tree tending. This is a candidate set, not an approved action registry. Each action will require an explicit input schema, algorithm or LLM prompt, output schema, and state-update rules.

There is **no fixed multi-stage research cycle**. The earlier SELECT/REVIEW/PLAN/ACT/INTERPRET/COMMIT/UPDATE GOALS sequence is superseded.

## 4. Knowledge representation

Canonical research and synthesis memories are human-readable structured Markdown, with stable document IDs such as `r2f` and `s4`.

- **Findings:** local `[#f1]`, global `r2f#f1`. Each finding contains a proposition, explanation, and provenance, with kind and evidence status.
- **Questions:** local `[#q1]`, global `r2f#q1`. A question may be linked to a research-objective node without changing its identity.
- **Equations:** local `[#e1]`, external JSON identity such as `e_r2f_1`.
- **Images/illustrations:** local `[#i1]`; proposed global asset identity `i_r2f_1`, stored as e.g. `i_r2f_1.jpg`. The file extension is not part of the stable logical identity. Images require source and attribution metadata; precise schema remains to be designed.

Each Markdown memory has a terminal `## Relationships` section containing canonical **outgoing** relationship JSON. Incoming relationships are derived. External sources are referenced in relationships, without separate `[#s]` units.

## 5. Retrieval and persistence

The knowledge directory indexes individual findings/questions and document summaries. Retrieval supports stable-ID lookup, full-text search, vector similarity, and relationship traversal. Similarity alone is not evidence of a semantic relationship.

Canonical Markdown and external JSON are authoritative. SQLite and vector indexes are rebuildable derived data.

The state object must be persisted so execution can resume after interruption. Exact persistence and recovery algorithms, including handling actions with external effects, remain to be designed.

## 6. Design method and next work

Specify **data structures first**, with only fields actually needed by the algorithms. Then specify deterministic action-selection rules and each action's exact inputs, operations, outputs, and state changes. For LLM actions, include the complete prompt and supplied context.

Next design tasks:

1. Define the research-objective tree and active-node data structures.
2. Define measurable tree-health conditions.
3. Define deterministic action selection from state.
4. Define the action contracts, one at a time.
5. Define durable state updates and recovery.

Do not implement an autonomous controller from this outline; its operational contracts are not yet specified.
