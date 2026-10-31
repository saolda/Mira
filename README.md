# Mira

A local, inspectable autonomous researcher with persistent R0 strategy selection, multi-database R1–R5 research, branching and synthesis.
Canonical Markdown and equation JSON remain authoritative; SQLite full-text,
relationship and vector indexes can be rebuilt. Research memories retain one source,
an R3-generated summary and compact anchored knowledge with inherited provenance.

- [Project purpose](ProjectOverview.md)
- [Implemented architecture](architecture.md)

Keep project documentation in these three files; edit minimally and preserve existing directives.

Run tests with `PYTHONPATH=src python3 scripts/run_tests.py`. Each run replaces
`test-results/latest.md` with the commit, totals, failures and validation/log notes.
Use `--validation-summary`, `--limitation` and `--run-log` to include those details.
Specifically requested milestone reports are preserved.
Run a synthetic demonstration with
`PYTHONPATH=src python3 -m mira --root /tmp/mira-demo --test-embedding demo`.
The test embedding is not a semantic model; actual local-model results are recorded
separately. No old memories or runtime state are imported.

Inspect persistent research locally:

```bash
PYTHONPATH=src python3 -m mira viewer
```

Open http://127.0.0.1:8767 and select an experiment and decision. New research
runs use ignored project `memory/` directly as one active corpus. Private inputs
under `memory/questions/` and unrelated files survive explicit corpus resets.

Initialize with a positional question or `research-init --question-file PATH`,
never both. A question file starts with `# Research question` and a nonempty
prose question. Optional `## Context` and `## Research objectives` sections contain
background and a Markdown list of objectives, respectively. Other or duplicate
headings and empty sections are rejected. For example:

```bash
PYTHONPATH=src python3 -m mira research-init --question-file memory/questions/topic.md --strategy medical --experiment topic
```

The original UTF-8 Markdown is frozen at the experiment's `research/question.md`;
its SHA-256, exact question, separate context and objective list are persisted in
`research/state.json` and exposed by `research-state`. Restart uses this snapshot,
even if the input file changes. Prompts keep the question and objectives intact
while bounding supplementary background. Oversized essential inputs fail the
existing token-budget checks. Keep private question files under ignored `memory/`.

Query profiles live in `src/mira/query_profiles.json`; strategies assign one to
each provider. `research-init --query-profiles PATH` selects an alternative
registry, frozen with the strategy at initialization. Existing experiments keep
their original query semantics. Provider cooldowns retain deferred queries;
`research-run` stops with `waiting_for_provider` and a retry timestamp when no
other work is ready. Resume later without regenerating R1 concepts. After an
interrupted HTTP submission, inspect `retrieval_calls/` before explicitly using
`--acknowledge-interrupted-searches`; unknown results are never silently retried.

LLM prompts are editable in [prompt_templates/](prompt_templates/).
The viewer’s **Prompt templates** button shows current sources; each decision
shows the saved filled prompts and template provenance when recorded.

Each `research-init`, `research-run` and `research-demo` invocation writes a new,
append-only JSONL file in ignored project `log/` (beside `--memory-dir` when configured). Filenames include UTC time, experiment name and a unique suffix.
Resuming creates another file. Logs contain complete rendered prompts and inputs,
template sources/hashes, raw responses, validation/normalization, searches and
committed changes. Configured secrets are redacted; records are flushed and
fsynced incrementally. A missing `execution_end` indicates an abrupt interruption.
Inspect a log with an editor or, for example:

```bash
jq -r 'select(.kind == "interaction_request") | .data.request.messages[].content' log/FILE.jsonl
jq 'select(.kind == "interaction_response" or .kind == "interaction_validation")' log/FILE.jsonl
```

`Research.run()` also creates a log. Custom Python supervisors can group
initialization and repeated `step()` calls with `with research.execution():`.
Standalone `--root` runs default to a sibling `log/` directory; provide
`--memory-dir` to choose the log home. Journals and interaction phase files remain
the recovery authority, and the viewer/transcript commands continue to use them.

R1 discovers 0–6 new concepts and selects one ordered plan for the whole provider
round. Python uses each provider's own prefix, persists unused discoveries and
skips searches already completed for the selected node. Empty or entirely
repeated plans remain living and return `waiting_for_r4_upgrade`; R4's prompt
and decisions are unchanged pending their separate review.

Starting another experiment requires an explicit reset:

```bash
PYTHONPATH=src python3 -m mira research-init --question-file memory/questions/topic.md --strategy medical --experiment next --new-experiment
```

This replaces only verified generated corpus files: research/synthesis memories,
equations, state, results, glossary, interactions, temporary retrievals, journals
and derived indexes. Allocators restart. Ordinary `research-run` continues the
current corpus. Reset refuses held runner/writer locks, incomplete recovery and
unknown model/provider submissions. An interrupted reset has a durable receipt;
repeat the explicit reset to finish it. Private question inputs, reviews, unrelated
files and `log/` remain intact. No old scientific memories are archived.

Legacy corpora remain readable with `--experiment NAME`. Inspect and explicitly
remove verified idle legacy directories with:

```bash
PYTHONPATH=src python3 -m mira research-cleanup
PYTHONPATH=src python3 -m mira research-cleanup --experiment OLD --apply
```

Cleanup protects active locks and recovery-blocked runs, moves their diagnostic
files to `log/legacy/`, and never deletes the current active corpus. The earlier
retain/disposable catalogue and per-experiment imports are superseded. For an
explicit transition preserving an existing legacy corpus, Python callers can use
`Experiments().activate_legacy(NAME)`; this relocates it directly into `memory/`
with verified hashes and a resumable transition receipt. `move_run_logs()` moves
old `memory/run-logs/` files into `log/` without changing their contents.
