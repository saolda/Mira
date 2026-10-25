# Plain-text prompt refactor

Completed 25 October 2026 on `main`. The prompt layer now sends one plain-text
user message per model call. There is no shared system/developer prompt or persona.

## Changes

- Replaced `system.txt` and the eight `.user.json`/`.contract.json` files with
  self-contained `R1.txt`, `R3.txt`, `R4.txt`, `S2.txt` task templates.
- Replaced JSON-template/schema rendering with a single-pass text substitution
  renderer in `src/mira/prompts.py`. Declared variables are inserted as sorted,
  indented JSON values, without reindenting or modifying surrounding source text.
  Missing values fail; explicit null, empty strings and empty collections remain
  distinct. Unicode, multiline values, CRLF and literal braces are covered by tests.
- Kept `decisions.py` and `gardener.py` response validators unchanged, including all
  five R4 decisions, required/nested fields, conditional lists, evidence references,
  exact synthesis finding references, duplicate-reference checks and input coverage.
- Retained exact request/response/provenance/validation/outcome recording. Version-2
  snapshots contain source text and hash, context bindings, filled messages and the
  request hash. Template edits affect future calls only.
- Updated `inspection.py` and `viewer_assets/app.js` for text sources and saved
  variables. New binding snapshots are checked against their saved source, request
  context and filled user message. Mismatches show warnings and never override the
  authoritative saved HTTP request. The historical JSON reader remains supported;
  calls without template snapshots are not backfilled from current files.
- Updated package-data rules, prompt documentation and the explicitly scripted
  demonstration's fixture transport. That fixture now reads labelled values from
  text instead of pretending the whole user prompt is JSON. Its explicit test
  budget is 10000 instead of 11500 so it still tests three-level synthesis descent
  after prompt overhead shrank. Runtime budgets, scheduling, synthesis cadence,
  database adapters and memory architecture were not changed.

No new external dependencies, prompt frameworks, configuration layers or automatic
prompt optimization were added. Read [the template guide](../prompt_templates/README.md)
for variables, editing and transport details.

## Verification

The baseline suite passed **102 tests**. The updated complete suite passes
**105 tests**, including existing validator/research/gardener/persistence tests and
additional text-rendering and historical snapshot regressions. Regression coverage
includes all four actions, one user message only, unknown/malformed placeholders,
missing versus null/empty values, literal braces without recursive substitution,
source hashes, exact CRLF/Unicode preservation, future-only template edits, historical
JSON snapshots and older no-snapshot transcripts, mismatched binding warnings,
read-only viewer HTTP routes and the existing full scheduler demonstration.

`node --check src/mira/viewer_assets/app.js` and Python compilation pass. A headless
Chromium session loaded the new experiment's R4 decision through a temporary
localhost viewer. Its rendered DOM contained the raw `prompt_templates/R4.txt`
source, exact filled task instructions, variable panel, complete raw response,
validation results and committed audit action. The browser used a separate `/tmp`
profile and did not save reviews. Existing HTTP tests verify the catalog returns
one `.txt` source per action and historical requests remain readable.

SHA-256 checks compared **485 existing research/transcript files** before and after
work: **zero changed or removed**. Existing `docs/examples` transcripts were not
regenerated. New evaluation material lives in its own experiment and export.

## Four real model calls

The already-running local endpoint at `http://127.0.0.1:8090` was available. The
check used `/home/eric/models/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-Q4_K_M.gguf`,
reported system fingerprint `b1-091b6a7`, temperature 0, max 1600 output tokens,
JSON response hint and `enable_thinking=false`. No system/developer message was
required by this transport, and no service was started, stopped or reconfigured.

Run the repeatable check with a fresh name:

```bash
PYTHONPATH=src python3 examples/plain_prompt_check.py \
  --experiment another-plain-prompt-check
```

Actual persistent experiment: `memory/research/plain-text-prompts-20261025/`.
Exact full/concise exports: `memory/transcripts/plain-text-prompts-20261025/`.
Select that experiment in the viewer. The committed
[request/response artifact](examples/plain_text_prompt_check.json) preserves all
four request records (including raw sources and filled messages), complete raw
responses, validations and outcomes, plus model identity. It is real HTTP output,
not scripted proposals.

| Action | Actual outcome | Validation |
| --- | --- | --- |
| R1 | Five query components targeting fixture measurements, uncertainty and validation. | Accepted. |
| R3 | Memory proposals grounded in supplied fixture IDs, with explicit synthetic-data qualifications. | Accepted. |
| R4 | `exhaust_split`, null keywords and three child questions about missing conditions and empirical evidence. | Accepted. |
| S2 | Synthesis findings referencing both supplied memory IDs and preserving the fixture's uncertainty. | Accepted. |

The evaluator seeds two explicitly authored synthetic input memories and a small
fictional evidence batch. Each action is tested independently; later calls are not
presented as a research run generated by earlier calls. Proposals are validated and
recorded as **evaluation-only audit events**; they do not change node dispositions,
consume memories or create model-generated canonical findings. The resulting-action
panel records this explicitly via `evaluation_only: true`, `action_committed: null`.
The normal research execution path continues to apply accepted proposals as before.

## Limits observed

All four outputs were structurally valid, but this is not evidence of reliable
research judgment. R3 referred to the authored fixture as a “simulation,” which the
input did not establish. R4 described the fixture database as exhausted by relevant
queries and asserted further searching would be redundant; the limited supplied
history did not establish broad search exhaustion. Its decomposition was valid JSON
with legal questions, but that does not verify its epistemic judgment. S2's arithmetic
comparison is grounded in the synthetic inputs, not empirical confirmation.

No adversarial or held-out semantic benchmark was performed. This refactor makes
tasks and actual inputs easier to inspect; it does not claim a measured improvement
in research quality. Token/byte budget rules are unchanged, so shorter prompt text
can naturally change which complete synthesis inputs fit a batch. Transport failure
or malformed model output still produces recorded validation/rejection without
silently weakening the admission rules.
