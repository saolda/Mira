# Running Mira research on Fractal

Current R1–R5 implementation, 27 October 2026. Read [architecture](../architecture.md)
for predicates, research statuses, queue policies, token capacity and recovery.
The older milestone reports remain historical evidence, not current contracts.

## Start a sustained session

Run from the Mira checkout. Use a fresh experiment name; initialization refuses to
overwrite a corpus. The model server is independently managed and must already be
running. These commands do not change GPU configuration or start/replace it.

```bash
cd /home/eric/Dev/Mira
curl --fail http://127.0.0.1:8090/v1/models
PYTHONPATH=src python3 -m mira research-init \
  'How is dropout applied to recurrent neural networks?' \
  --experiment dropout-sustained --database arxiv \
  --context-budget 16000 --output-reserve 2048 \
  --research-capacity-tokens 10000 --branching-interval 5 --max-children 3
PYTHONPATH=src python3 -m mira research-run --experiment dropout-sustained \
  --llm-url http://127.0.0.1:8090 \
  --model /home/eric/models/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-Q4_K_M.gguf \
  --no-thinking --max-tokens 2048 --timeout 120 --max-cycles 200
```

`--max-cycles` bounds each invocation; run the same `research-run` command again to
continue the persisted node progress. `cycle_limit` means the budget ended, not
that research is finished. Increasing the limit enables longer unattended sessions.
The loop stops on rejected output, transport/provider failures, explicit context
blocks, blocked synthesis or finished work, with inspectable records. It does not
silently loop on network errors or guess repairs. Relevant unanswered questions
remain living and may retry indefinitely; search quality is model/provider dependent.

Default synthesis interval is 5 work actions; R5 counts toward this interval.
Default branching interval is 5 direct research actions when living work exists;
with only exhausted nodes R5 runs without that wait (after any due synthesis).
Children start at zero priority and each R5 accepts at most three. No experiment
size cap or promise of balanced growth is imposed. Capacities use conservative
UTF-8 bytes plus reserve, so `16000` is deliberately conservative against a server
with 16384 actual context tokens. Never set the budget above your served model's
actual limit. A memory can overshoot the exhaustion threshold; see the architecture
for explicit oversized-R5 behavior and its operational limitation.

The currently exposed real provider is arXiv (abstracts, normally two results per
search). R1 generates one or two literal phrases. Python constructs an explicit
quoted `all:` word conjunction for arXiv, records it, and the adapter sends it unchanged.
Very specific conjunctions can still retrieve nothing; previous terms are soft
avoidance guidance, not a guarantee of search diversity. `--search-limit` accepts
1–10. Raw Atom, source IDs, source kind, truncation and request URL are retained.
Mira does not claim abstract-only research verifies full-paper conclusions.

## Inspect and export

```bash
PYTHONPATH=src python3 -m mira research-state --experiment dropout-sustained
PYTHONPATH=src python3 -m mira transcript --experiment dropout-sustained --concise
PYTHONPATH=src python3 -m mira transcript --experiment dropout-sustained --full
PYTHONPATH=src python3 -m mira --live --root memory/research/dropout-sustained integrity
PYTHONPATH=src python3 -m mira viewer
```

Open http://127.0.0.1:8767 and select an experiment/decision. State reporting shows
status totals, depth distributions, priorities, pending research, capacity snapshots,
ripeness counts/order, both cadences and recent research/branching/synthesis activity.
R5 records contain its ordered proposal, accepted questions, filtered duplicates,
child IDs and an explicit empty-attempt receipt. Full transcripts retain exact
request bytes, prompt sources/bindings, raw completions and commit/rejection results.
Exports are also stored in `memory/transcripts/<experiment>/` by the catalog CLI.
All research corpora and annotations live under ignored `memory/`; use explicit
`--root` only for isolated noncatalog runs. Existing experiments are not imported,
rewritten or upgraded by inspection.

## Recovery and continuation

```bash
PYTHONPATH=src python3 -m mira --live --root memory/research/dropout-sustained recovery inspect
PYTHONPATH=src python3 -m mira --live --root memory/research/dropout-sustained recovery validate
PYTHONPATH=src python3 -m mira --live --root memory/research/dropout-sustained recovery repair OPERATION_ID
# Only after inspecting a safely finishable operation:
PYTHONPATH=src python3 -m mira --live --root memory/research/dropout-sustained recovery repair OPERATION_ID --apply
```

Normal reads/actions block while a journal is incomplete. Repair defaults to dry
run. Explicit forward repair preserves one-time split receipts and IDs without
another model call. Unknown model calls with no committed event require transcript
inspection, then an explicit `research-run --acknowledge-interrupted` if another
attempt is intended. A known rejected response is already resolved; the next
invocation may retry it. A committed empty R5 never retries. See
[live persistence](live_persistence.md) for durability assumptions and ambiguity rules.

Version-1 experiments remain readable. The next successful action journals a
version-2 upgrade: old synthesis `complete` is not converted to `answered`, and
previously branched nodes retain their consumed branching opportunity. No old
memory, transcript, evidence or equation is discarded.

## Deterministic verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m mira research-demo --experiment revised-demo
```

The fictional demo exercises research retry, deterministic exhaustion, R5 including
empty splits, multiple depths and upward synthesis. Its prewritten responses and
synthetic evidence are explicitly labelled. Tests include every R4 decision,
question origins/media, full direct-research budgeting, overshoot retention,
ripeness/depth/tie ordering, living-node interleaving/resumption, one call per cycle,
malformed output, empty/duplicate/oversized child proposals, state migration and
subprocess crashes before/during R5 publication. Recovery tests reuse the same
journal and prove no duplicated nodes or additional model calls.

## Bounded real-model evaluation

See [27 October validation results](revised_architecture_results.md) for actual
model/provider behavior, isolated experiment names, semantic inspection and
remaining limits. JSON validity is reported separately from useful evidence.
No existing experiment is replaced by these runs.
