# Focused R1 search planning

> Historical milestone report. The current R1–R5 contract, three-way R4,
> question provenance and branching/synthesis policies are documented in
> [architecture](../architecture.md) and [execution](research_execution.md).


Historical implementation report. The later [R1 control correction](ordered_r3.md)
replaces the empty default with fixed prohibited heading words and filters useful
components rather than rejecting the entire component.

R1 now uses the exact requested `prompt_templates/R1.txt`. R3, R4 and S2 templates,
response contracts, context construction and scheduling are unchanged. No new
model call, dependency, database schema or research-state migration was added.

## Exactly five variables

| Variable | Actual supplied data |
| --- | --- |
| `question` | Selected question, preserving original wording. |
| `question_context` | Root and root-to-parent questions excluding the selected question and duplicates. Whitespace is normalized for comparison only; first original wording is retained. Empty when no distinct context exists. |
| `previous_search_terms` | Ordered, deduplicated component strings from successful committed R1 events for this node and question. Uses the recorded after-state keyword list, never words obtained by splitting a joined query. |
| `control_terms` | An explicit operator-supplied list; defaults to empty. No automatic exclusions are inferred from failed queries. |
| `memory_context` | A bounded projection of relevant linked findings and unresolved questions, with terminology, original finding kind/evidence status, reasoning/limitations, short attribution and omission flags. No full document, node metadata, equation object, path, timestamp or raw provider response. |

`src/mira/r1.py` constructs the R1 projection directly. The full shared research
context is still used by R3/R4, but is not constructed or supplied for R1.
Historical events with no recorded R1 component list cannot contribute previous
terms: the planner does not invent component boundaries from provider queries.
R4 replacement keywords are not mislabelled as earlier R1 output.

## Explicit control terms

No control-term mechanism existed. The minimal new mechanism is per-run input:

```python
research = Research(root, llm, adapters, control_terms=['solar', 'quantum'])
```

The CLI exposes repeatable flags on `research-run`:

```bash
PYTHONPATH=src python3 -m mira research-run --experiment my-experiment \
  --llm-url http://127.0.0.1:8090 --model MODEL_ID \
  --control-term solar --control-term quantum --max-cycles 1
```

Use the endpoint's real model ID in place of MODEL_ID. Terms apply only to R1 calls
in that invocation; resupply them on a later invocation if still required. Each
actual call records the exact list. Empty lists preserve existing behavior.

After the unchanged R1 structural validator succeeds, Python rejects any joined
R1 query containing a supplied whole term/phrase, matching case-insensitively with
normalized whitespace. This detects phrases spanning multiple components without
rejecting incidental substrings (`art` does not ban `particle`). A rejected proposal
is recorded and does not change keywords or reach R2. Terms are never converted
to negative provider operators or applied to R3/R4/S2. Repeated previous terms are
advisory because the requested prompt allows essential repeats.

## Memory projection and limitations

Only linked findings/questions sharing non-stopword lexical tokens with the
selected/contextual questions are included. Equation anchors, answered/superseded
questions and unrelated/unlinked units are excluded. Normal prose is extracted
with the existing Markdown parser; code, HTML-like passages, known instruction
patterns, paths, URLs and finding-reference IDs are omitted. No extra LLM summarizes
or judges the memories. The projection is marked `untrusted_memory_data`.

Original `kind` and `evidence_status` are retained: an unverified claim or inconclusive
hypothesis may supply terminology or a lead, but is never relabelled as supported.
Short reasoning/limitations and attribution remain visible. Per-finding
`excerpt_incomplete` and the overall `context_omitted_or_truncated` flag disclose
sanitization/truncation. The complete serialized memory projection is bounded at
3200 UTF-8 bytes; existing request-budget checks still apply to the full prompt.

This is conservative deterministic extraction, not a proof against all possible
natural-language prompt injection. It can miss paraphrase relevance or omit useful
material and can overfilter legitimate prose. Textual excerpts do not independently
verify underlying claims. These limits are exposed rather than hidden behind an
LLM-generated summary. No new assumptions or control terms are generated.

## Output and decision transparency

The R1 response contract was already minimal and stays exactly:

```json
{"keywords": ["component 1", "component 2"]}
```

Existing required-field/type/nonempty checks remain authoritative. R2 still joins
accepted components with single spaces into one provider query. The only new
admission rule enforces explicitly supplied R1 control terms.

The viewer's generic recorded-binding panels automatically show all five R1
variables and the exact completed prompt. No viewer schema or historical transcript
rewrite was needed. Older R1 calls retain their original larger input sets and
source templates; regression tests load the earlier real-call artifact to verify
that inspection does not apply today's slot declaration to historical data.

## Verification and real Qwen result

The complete suite passes **116 tests**. New R1 coverage includes identical root and
selected questions, duplicate ancestors, an empty ancestor list, previous-component
ordering/deduplication, accepted-event extraction, controls present/absent, control
phrase rejection, sanitization and uncertainty preservation, relevance, empty
memories, size bounds, unchanged downstream query joining, exact five-variable
viewer inspection and historical text-template compatibility. Existing research,
gardener, response-validation, persistence and viewer tests also pass.

One bounded real R1 call used the available local Qwen3.6-35B-A3B Q4_K_M endpoint,
temperature 0, 256 output tokens maximum, one user message and no extra summary
call. Persistent experiment: **focused-r1-20261025**. It supplied two explicitly
unverified synthetic findings, empty additional questions/previous terms, and
control terms `solar`, `quantum`. The model returned:

```json
{"keywords": ["synthetic insulation observations", "established conclusions", "unknowns", "synthetic fixture limitations", "uncertainty bounds", "empirical evidence"]}
```

The response passed the original R1 validator and the control-term check; neither
banned term appeared. The server reported **416 input tokens and 56 output tokens**.
No proposal was applied to the seeded research state. Generic components such as
“unknowns” show that validity does not guarantee highly discriminative query terms;
no broad search-quality improvement is claimed from one synthetic spot-check.

Exact source, filled request, response, validation and evaluation-only outcome:
[focused_r1_check.json](examples/focused_r1_check.json). The live records and full
transcript remain under `memory/research/focused-r1-20261025/` and
`memory/transcripts/focused-r1-20261025/`. Reproduce with a fresh experiment name:

```bash
PYTHONPATH=src python3 examples/plain_prompt_check.py \
  --experiment another-focused-r1-check --r1-only \
  --control-term solar --control-term quantum
```

The evaluator's new option runs R1 only; its R3/R4/S2 evaluation paths remain
unchanged. Existing research/transcript files and the R3/R4/S2 templates are
checked for preservation before delivery.

## Files changed

- `prompt_templates/R1.txt`: exact requested prompt.
- `src/mira/r1.py`: focused context, sanitizer and explicit-control validation.
- `src/mira/prompts.py`: R1's five declared slots only.
- `src/mira/research.py`: R1-only context/admission integration.
- `src/mira/research_cli.py`: explicit per-run control-term flag.
- `src/mira/research_demo.py`: fixture transport recognizes the new R1 prompt.
- `examples/plain_prompt_check.py`: focused real R1 evaluation option.
- `tests/test_r1.py`, `tests/test_prompts.py`, `tests/test_research.py`: regressions.
- This report, the template guide and the recorded R1 example.
