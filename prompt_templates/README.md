# Plain-text task prompts

Edit `R1.txt`, `R3.txt`, `R4.txt` or `S2.txt` directly. Each is a complete,
independent task with its own context, decision criteria and concise JSON output
example. New calls reload the selected file. There is no shared prompt, persona,
system message or developer message. The HTTP transport receives one user message.
R2 is a deterministic provider call; S1 selects synthesis inputs without an LLM.

Python response validators remain authoritative and unchanged. The templates do
not contain JSON Schema or ask the model to assign IDs, priorities, relationship
records or consumption marks. R4 retains kill, exhaust, retry, retry_split and
exhaust_split with their existing conditional keywords/children requirements.
S2 still requires exact supplied finding references and coverage of every input.

## Variables

Use `{{question}}`, for example. Variables are declared in `src/mira/prompts.py`:

| Actions | Variables |
| --- | --- |
| R1 | question, question_context, previous_search_terms, control_terms, memory_context |
| R3, R4 | root_question, question, node, ancestor_questions, linked_memories, children, strategy, next_database, search_history, equations |
| R3, R4 additionally | search_evidence |
| S2 | root_question, question, node, ancestor_questions, input_memories, equations |

Each template includes all its declared variables; duplicate occurrences are
allowed. Unknown/malformed placeholders, omitted slots, undeclared context fields
and missing values fail before dispatch. Missing is never silently turned into
null. Explicit None becomes `null`; empty strings, arrays and objects become
`""`, `[]` and `{}` respectively. Every value is serialized as consistent sorted,
indented JSON with Unicode preserved. This applies to scalar strings too, so
multiline strings retain their exact value as escaped JSON newlines; structured
values span readable lines. Surrounding template text and line endings are kept
exactly. Substitution runs once over the source: braces in inserted evidence are
literal data and never recursively evaluated.

R1 uses the exact focused template and five-variable projection documented in
[focused R1 context](../docs/focused_r1.md). No node record, provider pointer, full
memory, equations or raw history is included. Control terms are operator-supplied,
not inferred from failed searches.

R3 receives the pending normalized result batch; R4 receives this node's result
batches, unsuccessful attempts and linked findings. Full provider feeds remain on
disk and are not inserted. S2 receives complete selected unconsumed memories,
including a synthesis's own finding IDs when it is an input. These data-selection
rules, scheduling and synthesis cadence are unchanged.

## Recorded provenance and historical inspection

Every call saves version-2 text-template provenance: source path/text/hash, bound
values, filled message and serialized-request digest. Existing request/response,
validation and outcome recording and credential redaction remain in place.
The viewer shows raw source, exact filled user text, each variable/value, the full
model response, validation and resulting action. New text bindings are checked
against the saved source, filled message and separately recorded context before
being labelled as actual inputs. The saved HTTP body remains authoritative.

Old JSON-template snapshots and calls without snapshots keep their original
messages and schemas. No historical requests, research data or transcripts are
rewritten. The current template catalog is separate from saved call provenance.

`MIRA_PROMPT_TEMPLATES` can select another directory. Otherwise the repository's
`prompt_templates/` is used, with `share/mira/prompt_templates` for installed
packages. A missing file fails rather than falling back to an embedded prompt.
No new dependency or transport-specific system-message requirement was introduced.

The existing UTF-8 request-byte budget and synthesis complete-input selection
still apply. Shorter prompts may naturally allow more inputs to fit the same
budget. Only the scripted demo's explicit fixture budget was adjusted from 11500
to 10000 to retain its three-level synthesis-descent test; runtime defaults and
scheduler logic are unchanged.

## Verification and bounded real evaluation

Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
[Prompt refactor results](../docs/plain_text_prompts.md) records tests, preservation
checks and the four-call real-model evaluation. To repeat the evaluation using an
already running localhost model, choose a fresh experiment name:

```bash
PYTHONPATH=src python3 examples/plain_prompt_check.py \
  --endpoint http://127.0.0.1:8090 --experiment my-new-prompt-check
PYTHONPATH=src python3 -m mira viewer
```

The evaluator uses authored synthetic evidence, validates all four real outputs,
and records audit events without applying proposals to research state or memories.
It starts no model service. This is a format/grounding spot-check, not an autonomous
research benchmark or proof of improved research quality.
