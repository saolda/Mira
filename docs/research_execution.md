# Autonomous research implementation milestones

Current persistent storage and local viewer instructions are in [Persistent research and the decision viewer](persistent_decision_viewer.md). The `/tmp` paths in historical run reports below are original locations, not current defaults.

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
PYTHONPATH=src python3 -m mira research-demo --experiment fixture-demo
PYTHONPATH=src python3 -m mira research-state --experiment fixture-demo
PYTHONPATH=src python3 -m mira transcript --experiment fixture-demo --full
PYTHONPATH=src python3 -m mira transcript --experiment fixture-demo --concise
PYTHONPATH=src python3 -m mira --live --root memory/research/fixture-demo integrity
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

## Increment 4

The standard-library HTTP client sends the exact recorded UTF-8 request body to
`/v1/chat/completions`. Endpoint, model ID, temperature, output limit, timeout,
JSON-format hint and optional llama.cpp/Qwen thinking flag are configurable.
Authentication comes from the environment variable named by `--api-key-env`
(default `MIRA_LLM_API_KEY`) and is added only as an HTTP header. Redirects are
rejected so credentials are not forwarded to another host. Non-UTF8 error/response
bodies are retained with an explicit base64 prefix. Known credentials are redacted
before processing model output as well as before writing records.

`ArxivSearch` is the single initial real provider. The small historical Atom
adapter was adapted without its global config, provider fallback or silent query
rewriting. arXiv's [query and Atom contract](https://info.arxiv.org/help/api/user-manual.html)
and [API terms](https://info.arxiv.org/help/api/tou.html) inform the adapter. Requests
are spaced by at least three seconds within a process, with a bounded result count
(default two) and 30-second timeout. Transport/rate-limit/parse failures remain
failed searches, never successful pointer advancement. A failed run stops; retry
requires another explicit invocation. No provider fallback or unbounded retry loop.

Each result labels its content as an abstract and records URL/ID, title, author,
date and explicit truncation. The complete raw Atom feed is stored in immutable
search evidence, but only the bounded normalized results are provided to R3.
The full transcript shows both the actual R3 context and original R2 evidence.
SQLite remains Mira's rebuildable internal index, separate from arXiv.
The local HTTP protocol is documented by the
[llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
No model server is started, stopped or reconfigured by Mira.

### Bounded real experiment on Fractal

A localhost model was available, so an actual run was performed on 24 October 2026
in `/tmp/mira-real-dropout.9TANbP`, separate from any important research corpus.
Question: "Using arXiv abstracts only, what does Monte Carlo dropout approximate
when estimating predictive uncertainty? Focus on this single narrow question."
Model: `/home/eric/models/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-Q4_K_M.gguf`,
served by the already-running localhost endpoint on port 8090. Temperature 0,
maximum output 2048, thinking disabled, total byte-estimated budget 16000. The
runner allowed at most six cycles; it stopped after four committed research actions
and a final no-work check. The model reported 3242 prompt tokens and 749 completion
tokens across three calls (3991 total; provider counts, not independently measured).

R1 generated the query:
`Monte Carlo dropout predictive uncertainty approximation MC dropout Bayesian approximation deep learning what does Monte Carlo dropout approximate uncertainty`.
R2 returned two actual arXiv abstracts:

- [An Empirical Study on Variance-based MC Dropout Uncertainty-Error Correlation in 2D Brain Tumor Segmentation](https://arxiv.org/abs/2510.15541v2).
- [A Multilevel Monte Carlo Asymptotic-Preserving Particle Method for Kinetic Equations in the Diffusion Limit](https://arxiv.org/abs/1902.04347v4).

R3 admitted one research memory with two unverified findings derived from the
first abstract. The second result was not used. R4 chose **kill**, explicitly
stating that the retrieved material did not answer what MC dropout approximates.
The retained memory documents domain-specific empirical limitations rather than
answering the theoretical question. The run has one killed node and one unconsumed
memory. No synthesis occurred, correctly respecting the two-memory minimum.
Canonical/SQLite integrity passed (three records and two citation relationships).

This run **did not answer the research question**. It exposes weak keyword/query
formation and premature abandonment: a retry aimed at theoretical sources could
have been more productive than kill. No policy was silently changed to make the
experiment look successful. The actual prompts, response bodies, usage and
rejection/commit results can be inspected in the isolated corpus. A full export is
at `/tmp/mira-real-dropout-transcript.md` on this workspace. Raw external evidence
and model prose are not copied into the public sample transcript; the checked-in
full sample uses fictional fixtures. The next increment imported this run and its original export into ignored project-local
`memory/`; see the persistent-viewer instructions. The original temporary sources
were preserved unchanged.

### Reproduce a real bounded run

Against the independently managed model already available on Fractal:

```bash
PYTHONPATH=src python3 -m mira research-init \
  'Using arXiv abstracts only, what does Monte Carlo dropout approximate when estimating predictive uncertainty? Focus on this single narrow question.' \
  --experiment dropout-evaluation --database arxiv --context-budget 16000 --output-reserve 2048
PYTHONPATH=src python3 -m mira research-run --experiment dropout-evaluation \
  --llm-url http://127.0.0.1:8090 \
  --model /home/eric/models/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-Q4_K_M.gguf \
  --no-thinking --max-tokens 2048 --max-cycles 6
PYTHONPATH=src python3 -m mira transcript --experiment dropout-evaluation --full
PYTHONPATH=src python3 -m mira transcript --experiment dropout-evaluation --concise
PYTHONPATH=src python3 -m mira --live --root memory/research/dropout-evaluation integrity
```

Use `/v1/models` to obtain the model identifier if a different model is served.
If the endpoint is unavailable, these commands record a failed call and stop;
Mira never substitutes a scripted response for a real result. The full response,
including malformed output, is available for evaluation. After interruption,
inspect `transcript --full` and `recovery inspect` before deciding whether to repair
or explicitly pass `research-run --acknowledge-interrupted` to retry an unknown
call. Regular rejected calls are already resolved and can be retried explicitly.
Bounded runs can stop at `cycle_limit`; this is not completion of the research.

Milestone verification: all 75 tests pass (67 retained plus 8 integration tests).
Network-independent HTTP tests assert exact wire-body equality, separate auth,
provider errors/spacing, abstract labels/truncation, source citations, raw-feed
preservation outside model context, usage/model reporting and escaped-secret
redaction. The real run supplies separate connectivity/behavior evidence; it is
not a semantic-quality test or a basis for promoting any finding to verified.
No graphical viewer, presentation layer, image generation, historical-data import
or extra search provider/dependency was added.
