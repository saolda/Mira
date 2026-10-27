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
# Automatic strategy selection: R0 uses the root question and predefined registry.
PYTHONPATH=src python3 -m mira research-init \
  'How is dropout applied to recurrent neural networks?' \
  --experiment dropout-sustained --no-thinking \
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
The loop stops on rejected model output, model transport failures, an all-provider
outage at the end of a round, explicit context blocks, blocked synthesis or finished
work, with inspectable records. Individual failed, timed-out or rate-limited
providers are recorded and skipped, advancing the node's database pointer once. It does not
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

## Strategy selection and database providers

Exactly one strategy is selected and persisted for the entire experiment. Children
inherit the experiment selection; each node independently tracks its next database.
R1 terms remain fixed through that sequence. Successful, empty, failed and
rate-limited searches each advance the pointer; only useful nonduplicate results
need R3. R4 retry clears keywords and resets the pointer to the first database.
No LLM is called between databases just to select a provider.

For an explicit strategy, initialize without a model call:

```bash
PYTHONPATH=src python3 -m mira research-init \
  'Which teaching interventions improve retention?' \
  --experiment teaching-study --strategy education --context-budget 16000
```

Omit `--strategy` for mandatory R0 selection. Initialization uses `--llm-url` or
`MIRA_LLM_URL` (default `http://127.0.0.1:8090`); model identity uses `--model` or
`MIRA_LLM_MODEL`, otherwise the single served model is discovered. Multiple served
models require an explicit model identifier. `--no-thinking`, `--max-tokens`,
`--timeout`, API-key environment selection and JSON output options work for R0 too.
R0 failure or an unknown selection fails initialization, retaining its audit
record and leaving no research state. Use a fresh experiment after a failed R0;
there is no silent default strategy. `--database arxiv --database crossref`
remains an explicit compatibility path and skips R0. It cannot be combined with
`--strategy`.

| Strategy | Ordered databases |
| --- | --- |
| General (`general`) | Wikipedia, OpenAlex, Crossref, arXiv |
| Engineering (`engineering`) | arXiv, Crossref, OpenAlex, Wikipedia |
| Humanities (`humanities`) | Crossref, OpenAlex, Wikipedia |
| Biomedical (`biomedical`) | PubMed, Europe PMC, Crossref, OpenAlex, Wikipedia |
| Education (`education`) | ERIC, Crossref, OpenAlex, Wikipedia |

Configure a JSON list with `id`, `name`, `description` and ordered `databases`
using `research-init --strategies /path/to/strategies.json` or
`MIRA_RESEARCH_STRATEGIES`. The packaged defaults live in
`src/mira/strategies.json`; the controller does not need editing. Duplicate IDs,
unknown providers and duplicate/empty database lists fail validation. The selected
entry is snapshotted, so later registry edits affect only new experiments.
Database IDs are `wikipedia`, `arxiv`, `pubmed`, `crossref`, `europe_pmc`, `eric`,
and `openalex`. No implicit routing, substitute provider or hidden fallback query
is used. Other providers use the joined R1 terms; arXiv preserves its explicit
quoted-word conjunction and existing exact `id:` query compatibility.

All adapters return stable IDs, titles, authors when supplied, URLs and available
abstracts/excerpts. When only bibliographic metadata is available, the content is
labelled accordingly; no abstract is fabricated. Long excerpts are explicitly
marked truncated. `research-run --search-limit` accepts 1–10 (default 2).

Optional provider credentials are read from `MIRA_NCBI_API_KEY` and
`MIRA_OPENALEX_API_KEY` (or `OPENALEX_API_KEY`). `MIRA_CONTACT_EMAIL` adds contact
information to PubMed and Crossref requests. Keys stay outside model context and
are redacted from recorded transport errors. Mira does not obtain keys, register
accounts, change authentication or purchase access.

Provider requirements were checked against primary documentation:

| Provider | Endpoint/format and local pacing |
| --- | --- |
| [Wikipedia](https://www.mediawiki.org/wiki/API:Etiquette) | MediaWiki query API, JSON introductory extracts; descriptive user agent, maxlag, serial requests; 1-second local minimum |
| [arXiv](https://info.arxiv.org/help/api/tou.html) | Atom API; existing 3-second single-request spacing retained |
| [PubMed](https://eutilities.github.io/site/API_Key/usageandkey/) | ESearch JSON then batched EFetch XML; 0.35 seconds per request, below the keyless 3 requests/second limit |
| [Crossref](https://www.crossref.org/blog/announcing-changes-to-rest-api-rate-limits/) | Works JSON with optional JATS abstract and mailto contact; 1-second local minimum, respecting the public list-query rate |
| [Europe PMC](https://europepmc.org/RestfulWebService) | Search JSON with resultType=core; 1-second local minimum |
| [ERIC](https://eric.ed.gov/pdf/Using_ERIC_API_for_Research_Topics.pdf) | ERIC JSON docs; 1-second conservative local minimum; no higher undocumented quota assumed |
| [OpenAlex](https://help.openalex.org/api/authentication/) | Works JSON, reconstruct abstract inverted index; optional API key, 1-second local minimum |

Pacing is process-wide, shared by host for the six added adapters; arXiv retains
its existing process-wide lock. Provider failures establish a persisted 60-second
cooldown; rate limits honor Retry-After, including HTTP dates. Nodes skip providers
still cooling down without extending that cooldown or making another request.
Actual quotas remain provider/account/IP dependent; simultaneous independent Mira
processes do not share the in-memory pacing lock. If every database is unavailable
in a round, the final R2 records `providers_unavailable` and the run stops with
its advanced pointer saved. A later explicit run can reach R4 and retry; nothing
is marked answered or killed solely because providers were unavailable.

## Source deduplication and temporary retrievals

An experiment-wide `source_index` is committed with successful R3 processing,
including valid empty extraction. DOI, PMID, arXiv version, PMCID and other
canonical IDs are preferred. A conservative exact normalized title/full-author
fingerprint is used for sufficiently specific titles when IDs do not resolve the
identity. Conflicting publication IDs, explicit arXiv versions, or different known
years without a shared stable ID are retained as distinct/ambiguous works.
Aliases are reconciled only when a known source matches defensibly. There is no
fuzzy title or author-initial matching.

R2 removes already processed sources and duplicates within its batch. R3 checks
again before dispatch, because another node may process the same pending paper
first. An entirely duplicate pending batch is cleared deterministically without a
model call. Rejected R3 output never marks sources processed. Memories retain
compact `sources` metadata with identifiers, titles, authors and URLs, plus their
stable finding-level citations. Source processing and memory creation recover
atomically through the existing journal.

During initial testing, new runs retain unique normalized inputs in
`retrieved/<id>.json`, outside the canonical corpus. Canonical evidence stores
metadata and a payload digest/reference, not source text or raw API envelopes.
The input is durably saved before R2 publication; pending R3 validates its digest
and metadata after restart. Missing/changed pending content stops explicitly,
without guessing or repeating the model call. Rejected R3 keeps that input.

```bash
# Preview completed, discardable temporary inputs:
PYTHONPATH=src python3 -m mira research-prune --experiment dropout-sustained
# Apply after inspecting the preview:
PYTHONPATH=src python3 -m mira research-prune --experiment dropout-sustained --apply
```

Pruning runs under the writer lock and recovery gate, preserves every pending
(and legacy-pending) input, ignores ambiguous orphan files and never changes
canonical memory/evidence/state bytes. It is idempotent. Completed inputs may be
removed even if R3 extracted nothing, since processing is durably recorded.
Essential exact model request/response audits remain, so their supplied excerpts
remain inspectable even after the separate cache is removed. This is not a raw
paper/API archive. Existing experiments retain their old canonical evidence
policy and are not implicitly rewritten or pruned.

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

## Bounded real-model verification

The complete suite passes 178 tests, including R0 initialization/failure/crash
recovery, named CLI and registry selection, independent node progress, provider
skipping/cooldowns, cross-provider and cross-node deduplication, temporary payload
integrity/pruning and atomic source-index/R3 recovery, alongside the existing
lifecycle/synthesis/persistence/viewer tests.

A 12-cycle isolated run (`strategies-real-20261027`) used the existing Qwen3.6
server and real providers. R0 selected Engineering, then R1–R4 traversed arXiv,
Crossref, rate-limited OpenAlex and Wikipedia, with restart between every action.
OpenAlex was skipped, R4 retried, and a second pass began. Eight model calls
(including R0) committed; two research memories were created and four sources
were marked processed. All prior experiments remained byte-for-byte unchanged.
The test used one result per search, a 15000 research threshold and synthesis
interval 100 to isolate multi-database progression; it does not add new evidence
about S2 quality. Exact records are available in the existing viewer/transcripts. A separate real
CLI initialization also verified default model discovery and one-time R0 selection.

Separate single-query API probes returned useful results from Wikipedia, arXiv,
PubMed, Crossref and ERIC. Europe PMC returned HTTP 503; OpenAlex returned HTTP
429. Their normalization/error contracts pass deterministic tests, but successful
live retrieval from those two providers was not established in this environment.
The model selected the appropriate domain and retained task qualifications, but
one extracted paper on hardware noise was only indirectly relevant to preserving
recurrent connections. Structural success is not proof of a complete or accurate
research answer. No model service, GPU, authentication or unrelated project was
modified.
