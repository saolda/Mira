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
