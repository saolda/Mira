# Mira Architecture

**Status:** Draft 0.2 for review  
**Project:** Mira  
**Reference implementation:** `saolda/autonomous_ai`

## 1. Purpose and boundaries

Mira is a locally operated autonomous research system that investigates questions, builds evidence-grounded findings, discovers relationships, tests hypotheses, synthesizes knowledge, and identifies useful next questions. The new system starts with an **empty research corpus**. The old `autonomous_ai` repository is a read-only design reference, not a compatibility requirement.

Mira's canonical knowledge is human-readable and inspectable independently of an LLM. Deterministic software handles identities, retrieval, validation, scheduling, persistence and recovery. LLMs handle interpretation, research planning, inference and semantic judgments.

## 2. Canonical storage and identity

- Research and synthesis memories are structured Markdown documents with stable short IDs, e.g. `r2f.md`, `s4.md`.
- A document title may change without changing its identity. IDs are never reused.
- The primary knowledge unit is a **finding**, anchored `[#f1]` and globally referenced as `r2f#f1`.
- **Questions** are anchored `[#q1]`, globally `r2f#q1`. An independent research goal may refer to a question; the question's identity remains with its originating document.
- **Equations** use local Markdown shorthand `[#e1]` and an external canonical JSON definition with a globally stable ID such as `e_r2f_1`. The embedded document ID denotes origin, not an exclusive future location.
- Future candidate unit types: definitions, algorithms, datasets, and experimental results. Do not implement until a concrete need justifies them.
- Material revisions, splits, merges, retirement, and relocation require explicit identity and reference-preservation rules. Do not silently reuse or repurpose IDs.

## 3. Standard finding format

A finding separates **proposition**, **explanation**, and **provenance**.

```markdown
[#f2] Attention-only architectures enable training parallelism

**Kind:** Inference
**Evidence status:** Supported

**Proposition:** Removing recurrent sequence dependencies enables
greater parallelism during training.

**Explanation:** The conclusion follows from the architecture's
lack of recurrent processing across sequence positions. This does
not imply that attention is free of computational or memory costs.

**Provenance:** Inferred from the cited architecture description
and the earlier finding on recurrent dependencies. See outgoing
relationships below for canonical references.
```

The proposition is short and independently intelligible. Explanation records reasoning, assumptions, qualifications, and scope. Provenance describes how the finding was reached **without duplicating canonical citations or relationship records**. The outgoing relationship JSON identifies the actual premises, findings, equations and external sources.

A simple observation may have a short explanation; a complex inference may require substantial prose. Relationship JSON need not encode the detailed logical nuances of `A + B + C ⇒ X`; the prose does that.

Initial kinds: observation, claim, inference, hypothesis, synthesis. Kind and evidence status are separate concepts. Evidence-status vocabulary is not yet final.

## 4. Relationships

Every Markdown memory has a terminal `## Relationships` section containing structured JSON for **outgoing** relationships only. No `[#s]` source unit exists: external source references belong in the relationship JSON. Incoming relationships are resolved through a derived relationship index.

Illustrative schema, not yet frozen:

```json
{
  "version": 1,
  "relationships": [
    {"from": "f2", "type": "BUILDS_ON", "to": "r1a#f3", "status": "proposed"},
    {"from": "f2", "type": "CITES", "to": "https://arxiv.org/abs/1706.03762", "status": "unverified"}
  ]
}
```

Candidate relationship types: `CITES`, `SUPPORTS`, `CONTRADICTS`, `QUALIFIES`, `DEPENDS_ON`, `BUILDS_ON`, `SYNTHESIZES`, `RELATED_TO`, `INFLUENCED_BY`. Their meanings, direction, evidence requirements and allowed endpoint types must be specified before implementation. Descriptive provenance and evidential support require different standards. An inferred relationship begins as a proposal and must not silently become verified.

A relationship is canonical only in the originating document. A derived SQLite database indexes incoming and outgoing edges, validity, type and status. It must be completely rebuildable from canonical files.

## 5. Equations and questions

Equation definitions are external JSON objects recording the expression, variables, units where relevant, assumptions, provenance and revision. Markdown uses a local anchor; other documents may reference the stable global equation ID. Equation equivalence, revision and reuse rules remain to be designed.

Questions are first-class units with a lifecycle such as open, partially answered, answered or superseded (exact states TBD). Goals are managed independently but can refer to `r2f#q1`. Goal management must not change or take ownership of the question's identity.

## 6. SemanticDirectory and retrieval

The redesigned `SemanticDirectory` indexes **individual knowledge units**, not just memory titles and summaries. A unit record includes stable ID, type, parent document, label, proposition or searchable content, revision and embedding metadata. It may include carefully selected explanatory context, but should not substitute document titles for finding content.

The directory also stores a **document-summary record** linked to the entire canonical document for broad discovery.

Retrieval combines:
1. Exact stable-ID lookup.
2. Structured metadata and relationship queries.
3. Full-text search.
4. Vector similarity over unit content.
5. Graph expansion to related units.

The retrieval layer returns candidate IDs; the context assembler loads complete canonical content, provenance and relevant relationships before LLM judgment. Vector similarity does not establish support, contradiction or any other semantic edge. The vector backend is replaceable and its indexes are derived and rebuildable; embedding model/version metadata is retained.

## 7. Evidence and reasoning

Mira distinguishes source statements, observations, claims, inferences, hypotheses and syntheses. An accurate citation does not imply the cited claim is true. Provenance records whether a source was directly examined, indirectly cited or interpreted. Evidence status and uncertainty must be explicit where material.

A finding may be concise: `A + B + C + D + E ⇒ X`. The proposition states `X`; outward relationships identify A through E; explanation prose describes **why** the premises warrant X and any qualifications. A flat graph is not required to represent a full formal derivation.

Synthesis records outgoing `SYNTHESIZES` or other appropriate relationships to its inputs and must not silently promote uncertain premises to established conclusions.

## 8. Autonomous cycle

Proposed conceptual sequence:

```text
SELECT OBJECTIVE → RETRIEVE CONTEXT → ASSESS GAPS → PLAN
→ RESEARCH / ACT → CONSTRUCT FINDINGS → DISCOVER RELATIONSHIPS
→ VALIDATE → COMMIT → UPDATE GOALS → REFLECT → PAUSE / CONTINUE
```

Stages may be skipped for bounded task types, but the transition protocol must be explicit. Mira may investigate new questions, extend knowledge, verify uncertain claims, resolve contradictions or synthesize existing findings.

**Construction-time relationships** are recorded while the evidence and inference are in context. **Retrospective discovery** retrieves existing units and proposes additional edges for review. The system must not depend on recovering all provenance after the fact.

Plans and external actions have explicit permissions and budgets. The harness supports safe pause, interruption, shutdown, restart and recovery.

## 9. LLM orchestration and validation

The deterministic harness assembles relevant, bounded context before requesting LLM decisions. Requests specify objective, available evidence, permitted choices, output schema and abstention conditions.

LLM responses are proposals. Structural problems (malformed JSON, missing fields, invalid IDs) receive deterministic validation and bounded repair. Semantic problems (unsupported inference, wrong relationship direction, disputed scope) require reconsideration, qualification, rejection or deferral, **not silent correction**. Multiple agreeing model calls do not constitute independent evidence.

A semantic review evaluates evidence and reasoning using the actual retrieved passages, not only titles or similarity scores.

## 10. Persistence, indexing and audit

Canonical Markdown and external JSON are durable authority. SQLite relationship/full-text indexes and vector indexes are disposable derived state. Database rebuilds must be tested.

Multi-file updates require staging, validation and crash-safe commit/recovery; a simple try/except rollback is insufficient. Identity allocation, goal transitions, research actions, validation decisions and commit results must be auditable. A cycle log records objective, retrieved context IDs, actions, proposed changes, accepted/rejected changes and committed state, without requiring exposure of private model reasoning.

## 11. Implementation and review

Development roles: the project owner decides scope and approves architecture; ChatGPT assists with design and independent review; Codex investigates, implements, tests and commits bounded approved changes. Consult `saolda/autonomous_ai` for lessons and reusable components, not inherited architectural constraints.

**First milestone:** a small manually inspectable knowledge network with research/synthesis documents, findings, questions, external equation JSON, outward relationships, incoming relationship lookup, unit-level and document-level retrieval, revision safety, validation, index rebuilding and interruption recovery. No autonomous research engine until this foundation is reviewed.

## 12. Open design decisions

- Exact Markdown and relationship JSON schemas.
- Stable ID allocation, relocation, revision, split/merge and retirement semantics.
- Evidence-status and question-state vocabularies.
- Equation reuse, equivalence and revision.
- External source canonicalization and passage-level provenance.
- Retrieval ranking, embedding model and vector backend.
- Multi-file transactional commit and recovery protocol.
- Precise state transitions, goal policy and research budgets.
- Human-adjudicated semantic evaluation and relationship admission criteria.
