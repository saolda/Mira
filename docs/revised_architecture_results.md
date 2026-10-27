# Revised architecture validation, 27 October 2026

The integrated R1–R5 controller, independent ripeness queue, priority scheduling,
synthesis integration and versioned persistence are implemented. Commands are in
[research execution](research_execution.md); the full contract is in
[architecture](../architecture.md).

## Deterministic checks

`PYTHONPATH=src python3 -m unittest discover -s tests -v`: **152 tests pass**.
This retains the foundation, R1/R3, live-persistence, HTTP transport, viewer,
inspection and prompt-history coverage, updating old five-way R4 fixtures and
old synthesis-completion expectations to the revised contract. Nineteen added
architecture tests cover direct-research capacity/equations, full-payload estimates,
retained overshoots, explicit hard-budget blocks, structured ripeness/ties/depth,
question origins/order/relations, child priorities/duplicates/limits/empty attempts,
periodic and no-living-node branching, pending-work switches/resumption, one call
per cycle, migration, killed-lineage exclusion and immutable split receipts.
Subprocess exits at prepared/state-replaced/before-commit boundaries validate R5
journal assessment and idempotent repair without another model call or new IDs.

Python compilation (`python3 -m compileall -q src examples`) and `git diff --check`
also pass. The fictional end-to-end demonstration covers multiple tree depths,
research retry, R5 and upward bounded synthesis. The suite can emit nonfatal SQLite
connection ResourceWarnings from existing test lifetimes; these do not fail checks.

## Actual model and provider

The independently running `http://127.0.0.1:8090/v1/models` endpoint was reachable.
It reported Qwen3.6-35B-A3B Q4_K_M at
`/home/eric/models/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-Q4_K_M.gguf`,
with 16384 served context tokens. Evaluation used temperature zero, max 2048
output tokens, JSON response hint and `enable_thinking=false`. No service, GPU,
model or operating-environment configuration was changed. Calls and arXiv searches
ran with explicitly authorized network access outside the default sandbox.

Early isolated experiments exposed poor search semantics rather than a response
validator failure:

| Experiment under `memory/research/` | Bound | Observed outcome |
| --- | --- | --- |
| architecture-eval-20261027 | 16 cycles | Broad space-joined queries retrieved unrelated Monte Carlo papers; R3 correctly returned no results; R4 retried |
| architecture-focused-eval-20261027 | 14 cycles | Quoting in model-generated components alone did not yield useful extraction |
| architecture-boolean-eval-20261027 | 16 cycles | Model did not consistently emit requested Boolean operators; no useful memories |
| architecture-provider-eval-20261027 | 12 cycles | Requiring entire long components as contiguous phrases was too restrictive |
| architecture-final-eval-20261027 | 16 initial + 16 resumed cycles | Explicit conjunction of component words retrieved relevant abstracts; R3 created four units, R5 produced three questions and children continued research |
| architecture-clean-eval-20261027 | 12 cycles from empty corpus | Final implementation exercised R1/R2/R3/R4/R5 with committed memory and branching, no rejected calls |

All experiments are separate new directories. Early unsuccessful results and
actual prompts/responses remain intact. They motivated a small deterministic
arXiv query builder: require the generated topic words, rather than rely on the
model to emit syntax or force a long exact phrase. Exact `id:` queries used by the
existing paper-check example remain supported. R1 now requests one or two short
literal components, while preserving its five context slots and control filtering.

## Clean-start run

Root question: “How is dropout applied to recurrent neural networks?”
Context budget 16000, reserve 2048, deliberately small research threshold 6000,
branching interval 5 and maximum three children.

The actual 12-action sequence was:

`R1 → R2 → R3 → R5 → R1 → S1 → R1 → R1 → R2 → R2 → R4 → S1`

All actions committed. There were seven real model calls, each in a separate
cycle. arXiv returned abstracts for `1312.4569v2` (handwriting recognition) and
`2001.10065v1` (robust RNN prediction). R3 created `r1` with two ordered units:
a finding about avoiding recurrent connections in that application of dropout,
and a claim about regularizing recurrent hidden states using noise. Both retain
source identifiers, qualifications, CITES relationships and unverified status.
No source equation or image was invented.

The complete R5 request was 4254 UTF-8 bytes plus a 2048 output reserve: estimated
total **6302**, crossing the **6000** threshold while fitting the **16000** hard
budget. The same commit retained the whole new memory and exhausted the root.
R5 then created three zero-priority children and a durable split receipt. The
children concerned recurrent versus input/output dropout constraints, noise and
robustness, and dropout rates across RNN variants. These go beyond merely copying
extracted questions. The first child progressed through search and R4 retry;
other child progress survived node switching. No living node was killed for an
empty search. At the bound there were **3 living children, 1 split root**, depth
one, 9 direct research actions, 1 branching action and 2 deterministic S1 actions.
The controller stopped at `cycle_limit` and can resume from that state.

Reloaded canonical validation succeeded. `integrity` reported `ok`, three indexed
records and two relationships. Full and concise exports are saved at:

- `memory/transcripts/architecture-clean-eval-20261027/full.md`
- `memory/transcripts/architecture-clean-eval-20261027/concise.md`

The exact local filenames are selected by the catalog exporter; use
`transcript --experiment architecture-clean-eval-20261027 --full` to inspect.
The canonical memory, evidence, independent interactions and journal are in the
experiment directory, and are also inspectable through the viewer.

## Semantic assessment and limits

The clean extraction is traceable to supplied abstracts and preserves its task
qualifications. However, the first finding's “must” wording can read as a universal
restriction on recurrent dropout even though its support is a specific older LSTM
handwriting approach. The R5 questions usefully investigate this tension, but the
first and third are fairly broad, and neither their novelty nor eventual answer
quality is established by JSON validation. The resumed experiment extracted
fraternal-dropout training and layer-specific NLI effects faithfully, but an R4
rationale also supplied an unsupported author attribution from model knowledge.
R4 rationale is audit prose, not a verified memory.

Child queries still sometimes contain too many discriminating words and return
nothing; the model may repeat essential earlier terms. The revised retry policy
keeps relevant questions alive and allows autonomous continuation, but **does not
guarantee useful progress on every branch**. Model output is not scientific
verification. No long-duration research-quality claim is made from these bounds.

The real run did not create a second memory, so S2 was not eligible; real S2
quality was not re-evaluated here. Deterministic integration tests exercise S2,
bounded batches, lineage coverage, upward synthesis, cadence and crash recovery.
R3 question source/derived origin and empty R5 receipts are covered deterministically;
this particular real extraction returned findings/claims rather than question units.

A sufficiently large new memory can exceed the hard R5 context budget despite the
headroom. Mira preserves it, records an auditable exhaustion transition and stops before dispatch;
it does not truncate or silently synthesize away research. This needs operator
budget/material inspection. Provider errors and malformed/unfinished model output
also stop the bounded run with retained evidence. These are explicit operational
limits rather than hidden new research dispositions.
