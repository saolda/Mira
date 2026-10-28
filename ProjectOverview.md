# Mira: Autonomous Research and Knowledge Development

## Project purpose

Mira is a locally operated autonomous AI research system designed to investigate questions, accumulate structured knowledge, discover relationships between findings, develop hypotheses, evaluate evidence and identify productive directions for further research.

The long-term objective is an autonomous researcher capable of building an increasingly coherent, interconnected and evidence-grounded body of knowledge.

Mira should not merely accumulate research documents. She should develop and maintain an inspectable network of findings, evidence, reasoning, uncertainty and relationships.

The system should remain understandable, maintainable and recoverable without relying on any particular LLM or database implementation.

## Development approach

This is a substantial redesign of the existing `autonomous_ai` project.

The existing repository, `../autonomous_ai`, is available as a reference implementation and source of engineering lessons.

It is not the new system's architectural specification.

The new Mira will begin with an empty research-memory corpus.

Existing research memories will not be imported by default.

The original system and its data must be preserved.

We will reuse existing code only where its design and behaviour are appropriate for the new architecture.

The redesign should avoid carrying forward unnecessary compatibility requirements.

## Core architectural principles

### 1. Canonical knowledge storage

Research and synthesis memories are stored as structured, human-readable Markdown files.

Each memory has a permanent identity independent of its title and filename.

The fundamental knowledge unit is a finding, identified by an anchor such as:

`[#f1]`

Findings represent claims, observations, inferences, hypotheses, conclusions or syntheses.

A finding's identity must remain stable across ordinary edits. Material changes, splitting, merging and retirement require explicit identity-management rules.

### 2. Equations and other formal objects

Equations are first-class research objects.

They may be referenced in Markdown using anchors such as:

`[#e1]`

Equation definitions are stored in structured external JSON files.

Their identities, assumptions, variables, provenance and relationships to findings must be explicitly defined.

Additional object types may be introduced when justified by concrete research requirements.

Avoid unnecessary proliferation of object types.

### 3. Knowledge relationships

Each Markdown memory contains canonical structured JSON describing its outgoing relationships.

Incoming relationships are discovered through a derived relationship database.

A relationship is recorded canonically only once.

Relationships may connect findings, equations, sources and other supported objects.

Relationship types must have clearly defined meanings and directions.

The system must distinguish explicit provenance, descriptive relationships, inferred relationships and evidential claims.

Uncertain or proposed relationships must not be silently promoted to verified knowledge.

### 4. Retrieval architecture

Retrieval operates primarily at finding level, not merely document level.

The system supports:

- Exact identity lookup.
- Structured database queries.
- Full-text search.
- Vector-based semantic retrieval.
- Relationship-based graph navigation.

Vector embeddings are derived from actual finding content.

Similarity is a candidate-discovery mechanism, not proof of a relationship.

All derived indexes must be rebuildable from canonical data.

### 5. Evidence and reasoning

Research findings must document how they were reached.

The system distinguishes:

- What is claimed.
- Who or what supplied the claim.
- What evidence is available.
- What reasoning connects evidence to conclusions.
- Which assumptions apply.
- What remains uncertain.

Claims, observations, inferences, hypotheses and syntheses must not be conflated.

A synthesis must preserve traceable connections to the findings and evidence it integrates.

### 6. LLM responsibilities

LLMs perform tasks requiring interpretation, research judgment, synthesis, planning or complex reasoning.

Deterministic software handles identity allocation, retrieval, schema validation, reference resolution, persistence, scheduling and transaction management.

Before requesting an LLM judgment, the harness should assemble relevant, accurate and appropriately bounded context.

LLM outputs must follow explicit structured contracts.

Deterministic errors may be corrected automatically where safe.

Semantic errors, unsupported claims and ambiguous relationships must be reconsidered, qualified, rejected or deferred rather than silently repaired.

LLM agreement alone does not constitute independent verification.

### 7. Autonomous operation

[`architecture.md`](architecture.md) is the **authoritative specification** for Mira's autonomous execution model, persistent research-question tree, deterministic research actions, priority scheduling and synthesis gardener. This overview defines goals and principles; it does not prescribe a competing execution cycle.

The controller selects one action per cycle from persisted state, with at most one LLM pass. Research and synthesis use separate scheduled cycles within the same process. The older fixed sequence of objective selection, planning, research, reflection and goal management is superseded. Those activities may occur within appropriate actions but are not mandatory stages.

Mira must support safe pause, shutdown, recovery and resumption. Autonomous actions require bounded resource budgets and explicit permissions.

### 7A. Research strategies and source retention

A **research strategy** is a predefined, ordered list of external research
databases suitable for a question domain, such as humanities or engineering.
One strategy must be selected for the entire experiment before any research cycle:
use the named strategy specified on the command line, or, **by default when no
strategy is specified**, run the one-time R0 LLM selection. Initialization must
not proceed without a valid, persisted selection.
All nodes inherit that strategy, while each independently tracks its next database.
A set of R1 keywords is tried against the strategy's database sequence; after
that round, R4 may request new keywords and restart the sequence. Unresponsive
providers are recorded and skipped, not allowed to stall research indefinitely.
The exact controller contract belongs in [architecture.md](architecture.md).

The system should avoid repeatedly processing the same publication across
providers. Prefer stable scholarly identifiers, with conservative title/author
matching when needed. Keep unique retrieved research-source content during early
testing so extraction and citations can be checked. Once the implementation is
validated, do not indefinitely accumulate downloaded source payloads: retain
canonical research/synthesis memories and sufficient source identifiers/URLs to
re-download and check provenance when necessary. Essential persistence, audit
and crash-recovery information must still be preserved. The historical
`../autonomous_ai/src/actions.py` offers provider adapters for Wikipedia,
arXiv, PubMed, Crossref, Europe PMC, ERIC and OpenAlex; these are reference
implementations, not evidence that every provider is already integrated.

### 7B. Research memories and presentation outputs

Canonical research and synthesis memories are **agent-oriented knowledge documents**, designed for accurate retrieval, evidence tracking, reuse and further synthesis. They need not themselves be polished publications.

Each new research memory contains one source, an R3-generated summary and compact anchored knowledge units with inherited source provenance. Derived questions/equations keep explicit origins; S2 integrates across memories.

A separate **presentation generation** objective transforms selected synthesis memories and supporting evidence into polished, human-readable presentation documents (for example `presentation.md`). Presentation outputs are **derived**, not canonical research memories; they must retain citations and traceability to the source memories and must not silently introduce unsupported claims.

Presentation format, editorial style and publication workflow can be **project-specific**, outside Mira's core research/synthesis controller. For example, a HistoryOfAI project may build chronological historical articles from Mira's synthesis memories, while HumanLegacy may use a different publication format to populate its research library. The exact document schemas, generation schedule and project adapters remain to be designed. The core memory format stays common across projects.

### 8. Persistence and recoverability

Canonical knowledge must survive database deletion, model replacement and process crashes.

Derived indexes must be reconstructible.

Memory updates must be validated before commitment.

Multi-file updates require a crash-safe persistence strategy.

Research history, provenance and important state transitions must be auditable.

### 9. Simplicity

Prefer clear, small, comprehensible components over elaborate frameworks.

Markdown should remain pleasant for a human to read and edit.

JSON schemas should be compact and understandable.

Do not introduce a database, abstraction, agent role or metadata field without a demonstrated purpose.

The system should be sophisticated in its research capabilities, not unnecessarily complicated in its implementation.

## Development roles

### Project owner

The user determines priorities, approves architectural decisions and authorises major changes.

### ChatGPT

ChatGPT assists with architecture, design alternatives, research methodology, experimental design, code review and evaluation of Codex results.

ChatGPT should challenge weak assumptions and identify architectural risks rather than merely endorse proposals.

### Codex

Codex investigates repositories, prepares technical designs, implements approved components, writes tests, conducts experiments and documents results.

Codex should work in bounded, reviewable increments.

Major architectural decisions must be presented for approval rather than made implicitly during implementation.

## Development workflow

Use the following workflow for substantial changes:

1. Define the objective and constraints.
2. Investigate relevant existing code or prior experiments.
3. Produce a concise design proposal.
4. Review and approve the design.
5. Implement a bounded component.
6. Run tests and realistic demonstrations.
7. Commit code, documentation and relevant artifacts.
8. Independently review the results.
9. Decide whether to proceed, revise or abandon the approach.

Do not equate passing structural tests with successful semantic reasoning.

Evaluate research quality using real examples and independently reviewed judgments wherever practical.

## Reference project

Existing implementation:

Repository: `../autonomous_ai`

Relevant historical investigations:

- Memory relationship architecture, Phase 1.
- LLM-assisted memory segmentation, Phase 1B.
- Evidence-first relationship discovery, Phase 1C.
- Existing autonomous-cycle and persistence documentation.
- Existing semantic retrieval implementation.

These materials document both useful engineering patterns and known shortcomings.

Do not assume their experimental designs are correct merely because they have been implemented.

## Initial priorities

Before implementing the autonomous research system, develop and review:

1. The canonical Markdown memory schema.
2. Finding and equation identity rules.
3. Relationship vocabulary, direction and verification semantics.
4. Finding-level retrieval and indexing.
5. Evidence and provenance representation.
6. Finding revision, retirement, splitting and merging.
7. The autonomous state cycle.
8. Transactional persistence and recovery.
9. The boundaries between deterministic logic and LLM judgment.

The first implementation milestone should demonstrate a small, manually inspectable knowledge network containing real findings, sources, equations and relationships.

It must support creation, retrieval, revision, validation and index reconstruction.

Only after the knowledge foundation is reliable should autonomous research be added.

## Guiding principle

Mira should be able to explain what she has learned, where that knowledge came from, how it relates to other findings, why a conclusion was reached and what remains uncertain.

The system's knowledge should be inspectable independently of the LLM that produced it.