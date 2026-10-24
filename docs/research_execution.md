# Autonomous research implementation milestones

The owner approved continued development through Increments 2b, 3 and 4, including
persistent model-decision transparency. Phase 1 and the live journal remain intact.

## Increment 2b

State-driven R1–R4 selection, all five R4 dispositions, durable evidence pointers,
root priority 10, children priority 0, sustained turns, capped inactive aging and
oldest-first reselection are implemented. Empty searches advance their pointer;
failed/rate-limited searches preserve it and stop the bounded runner for inspection.
A subsequent explicit run retries the same provider. No automatic provider fallback.

`research_tree.py` validates reciprocal tree links, ownership, priorities, allocators,
pending evidence and cached counts/orderings. To keep the initial implementation
simple, a postorder refresh covers the bounded tree after each mutation, including
all source owners; this costs O(nodes + nodes*memories), not an optimized incremental
ancestor algorithm. No balance/health repair policy is invented.

Every actual LLM call gets an independent `interactions/<sequence>-<uuid>/` directory:
`request.json` (exact serialized JSON request body plus structured context),
`response.json` (complete raw completion envelope or transport error),
`validation.json` and `outcome.json`. Each immutable phase is fsynced. Requests are
recorded before dispatch and responses before parsing, including malformed outputs.
Canonical cycle events link the interaction to the actual committed action and
memory IDs. These events commit through the journal alongside memory/state changes.
If a crash occurs after canonical commitment but before outcome recording, the
transcript resolves it through that committed event. An unresolved call pauses the
controller; `--acknowledge-interrupted` explicitly authorizes another attempt after
inspection. Such a call may have executed on the server. A torn phase is visible
as corrupt/interrupted and is never silently overwritten.

No authentication headers are recorded. Generation settings have an allowlist;
known client credentials are redacted from errors/responses and any supplied
context before dispatch. Exactness is subject to this explicit secret redaction.
Timestamps use UTC ISO format; directory sequence orders calls across restarts.
Usage/model reported by the server are retained when present, otherwise unknown.
Model output is structural validation, not independent verification of claims.

`transcript --full` reads records/events directly, without SQLite or research state,
and exposes actual messages, serialized requests, context, responses, evidence,
validation and committed tree changes. `--concise` omits full request/response and
source bodies. Neither requires a model. `research-state` reports node status,
priorities, counts, candidates, child IDs, maximum depth and living nodes by depth.

Milestone verification: all 59 tests pass (49 retained plus 10 controller/trace tests).
The tests cover all dispositions, scheduling, search failures versus empty results,
restart with pending results, malformed outputs, unsupported citations, context
blocking, no-finding results, interrupted calls, secret redaction and independent
transcript inspection. Increment 2b uses scripted models and fixture search only;
its scheduled S1 hook is replaced by the gardener in Increment 3.

## Increment 3

The gardener now runs in the controller process after every configured number of
committed research actions (default five). With no living nodes it drains final
synthesis directly. Candidate score is frontier count plus 1000 only for exhausted
nodes with no living descendants and at least two inputs. Killed nodes retain
usable material without the bonus. Completed nodes are excluded permanently.
Exhausted terminal nodes complete at zero or one remaining inputs, without LLM work.

Selection descends to eligible children by score/creation order while the full
context exceeds budget. It chooses the oldest fitting pair, then adds remaining
inputs in creation order when they fit; this avoids falsely blocking when one old
large input crowds out two smaller inputs. The complete serialized request plus
output reserve is checked using conservative UTF-8 byte estimates. No complete
memory is silently truncated. Equations referenced by inputs include their JSON
definitions. If no pair fits, S1 logs `blocked_synthesis` and the runner stops.
Both the context budget and output reserve are configurable; actual max output
tokens must fit the reserve. A blocked pair requires an explicit configuration or
research-material review rather than automatic single-memory synthesis.

S2 requires finding-level source references covering every consumed memory. Its
new Markdown, reciprocal input consumption marks, all affected tree counts and
audit event commit through one journal operation. The final synthesis remains
unconsumed for ancestors. Malformed proposals preserve inputs and counters.

Milestone verification: all 67 tests pass, including 8 gardener tests. Coverage
includes the five-action cadence, killed-node scoring/material, zero/one-input
completion, bounded batches, three-level upward synthesis, no resynthesis of
completed nodes, input coverage, invalid proposals, blocked budgets and an actual
controller/gardener subprocess crash followed by explicit journal repair. Some
original foundation tests leave SQLite test connections unclosed and Python 3.14
may emit ResourceWarnings when collecting them; tests still pass.

### Fixture demonstration and transcript

```bash
MIRA_DEMO_ROOT=$(mktemp -d /tmp/mira-research-demo.XXXXXX)
PYTHONPATH=src python3 -m mira --root "$MIRA_DEMO_ROOT" research-demo
PYTHONPATH=src python3 -m mira --root "$MIRA_DEMO_ROOT" research-state
PYTHONPATH=src python3 -m mira --root "$MIRA_DEMO_ROOT" transcript --full > /tmp/mira-full-transcript.md
PYTHONPATH=src python3 -m mira --root "$MIRA_DEMO_ROOT" transcript --concise
PYTHONPATH=src python3 -m mira --live --root "$MIRA_DEMO_ROOT" integrity
```

The recorded run is in `examples/full_research_transcript.md` and
`examples/concise_research_transcript.md` beside this document. It uses the 8192 /
2048 default budget, and intentionally sets the research interval to 100 so that
all branches are researched before final draining. The separate cadence test
verifies the default five. Decisions and evidence are deterministic; timestamps,
run/operation UUIDs and directory names vary.

What it accomplished: four nodes across three levels performed 16 research actions,
created eight research memories and five synthesis memories, and finished with all
nodes complete and one unconsumed root result. Seventeen scripted model responses
were admitted. Upward synthesis included the leaf q4, intermediate q2 and root q1.
The sample evidence is explicitly fictional: this demonstrates controller behavior,
provenance, budgeting, accounting, recovery and inspectability, not new scientific
knowledge or autonomous research quality. No important corpus is used.
