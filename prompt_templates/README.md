# Mira LLM prompt templates

These files supply the actual model messages. Every state has a complete task,
step-specific instructions, named information slots and a precise output format.
They are not example prompts or summaries reconstructed after a call.

| File | Task |
| --- | --- |
| `system.txt` | Shared system message: JSON only, evidence grounding, no invented IDs. |
| `R1.user.json`, `R1.contract.json` | Generate focused search-query components; return `keywords`. |
| `R3.user.json`, `R3.contract.json` | Interpret supplied evidence; return supported memory drafts or an explicit no-finding reason. |
| `R4.user.json`, `R4.contract.json` | Evaluate this research direction and choose one of the five dispositions, with rationale and conditional keywords/children. |
| `S2.user.json`, `S2.contract.json` | Integrate at least two selected memories with finding-level source references. |

The complete prompt is the shared system message plus the filled state user
message. No developer message is currently sent. R2 performs a provider search
without an LLM; S1 selects synthesis deterministically, so neither has a prompt.

## Tasks and exact outputs

Each user file contains `task`, `instructions`, `information_rules`,
`output_requirements`, `context` and `output_contract`. Contract files are JSON
Schemas with required fields, nested types, enums and no extra output fields.
R3 specifies the relationship between empty memories and `no_finding_reason`;
R4 specifies when keywords and child questions are required or forbidden. S2
requires finding references and explains that every selected input must contribute.
IDs, consumption marks, priorities, relationships and state transitions belong to
the harness; the model proposes only the fields specified for its task.

The Python admission validators remain authoritative, including checking source
IDs against actual supplied evidence and synthesis coverage of all consumed
memories. Editing a contract does not change those validators. Changes to accepted
fields or dispositions must be coordinated with code. No dependency on a JSON
Schema library or model-specific structured-output API is introduced.

## Named information slots

Every placeholder is a complete JSON value, for example
`"question": {{ question_json }}`. It is deliberately unquoted in the source.
All slots below must occur in their state template. Unknown/missing slot names,
undeclared context fields, invalid JSON and missing task instructions fail before
model dispatch. Values are substituted once: apparent placeholders inside source
text, memory contents or questions remain literal data.

| Slot | Supplied information |
| --- | --- |
| `root_question_json` | Overall objective. |
| `question_json` | Selected node's research question, explicitly. |
| `node_json` | Full selected-node record, including keywords, pointer, lifecycle, priorities and counts. |
| `ancestor_questions_json` | Question path from root through the selected node, inclusive. |
| `linked_memories_json` | Directly linked memory IDs and complete canonical Markdown (R1/R3/R4). |
| `children_json` | Existing direct child-node records (R1/R3/R4). |
| `strategy_json` | Active strategy ID and ordered provider list (R1/R3/R4). |
| `next_database_json` | Next provider, or null when the pass is finished (R1/R3/R4). |
| `search_history_json` | This node's recorded queries, provider, status, errors, timestamps and result references (R1/R3/R4). |
| `search_evidence_json` | R3: the pending result batch. R4: all this node's recorded batches, including failed/empty attempts and normalized result text. |
| `input_memories_json` | S2: complete selected unconsumed memories and their IDs, including descendant material selected by the gardener. |
| `equations_json` | Definitions referenced by the supplied memories. |
| `output_contract_json` | The corresponding contract file, inserted as a JSON Schema. |

A null slot means unavailable/not supplied; an empty array means an explicitly
empty collection. Full provider feeds are retained on disk but excluded from
prompts. Normalized evidence includes provider-supplied abstracts/excerpts, source
IDs and truncation metadata; this does not imply full papers were supplied.
Other nodes' memories are not automatically inserted into research decisions.
The viewer shows available corpus material separately from model inputs.

R4 now receives this node's search evidence and search outcomes as well as its
linked memories. Earlier R4 calls lacked this evidence; their saved requests
remain unchanged. The new R4 instructions explain all five dispositions and ask
for a rationale considering what was tried, evidence and remaining gaps. Running
out of databases is not itself evidence that no productive direction remains.
These are explicit prompt changes; no improvement in real research quality has
been measured by the scripted demonstration.

## Editing, budgets and recorded provenance

Edit the files directly in the IDE. Subsequent calls reload them from disk.
Source text is preserved, including line endings; contract JSON is compacted when
inserted to reduce request overhead. The default directory is this repository's
`prompt_templates/`; installed packages include `share/mira/prompt_templates`.
`MIRA_PROMPT_TEMPLATES` selects an explicit alternative. Missing files never
silently fall back to older or embedded prompts.

Full instructions, schemas and evidence count toward the existing conservative
UTF-8 request-byte budget. Defaults remain configurable **8192** total and **2048**
output reserve; larger requests need an explicit larger `--context-budget` (for
example `16000`). Oversized research contexts are blocked before dispatch instead
of silently dropping evidence. Synthesis still selects bounded complete-memory
batches. The fixture demonstration uses an explicit **11500 / 2048** budget to fit
its research prompts while exercising synthesis descent through three levels.

Click **Prompt templates** in the HTML viewer to inspect current source files.
Select a recorded decision to see **State task and exact output instructions**,
**Filled information slots**, filled messages, source snapshots and the exact
serialized request. Null/empty slots are labelled explicitly. These panels use the
saved request, never the current state or today's templates.

Before dispatch, records save template sources and hashes, filled values/messages
and the request-body digest. The viewer verifies the snapshot against the saved
body; known credential redaction still applies. Older calls are displayed exactly
as recorded, with absent instructions/provenance labelled rather than backfilled.

A new isolated, scripted example can be created with:

```bash
PYTHONPATH=src python3 -m mira research-demo --experiment state-prompt-check
PYTHONPATH=src python3 -m mira transcript --experiment state-prompt-check --full
PYTHONPATH=src python3 -m mira viewer
```

Select **state-prompt-check** and inspect R1, R3, R4 and S2. Existing experiment
names are not overwritten. This fictional example verifies prompts, bookkeeping
and inspection, not LLM research quality.
