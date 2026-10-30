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
runs default to ignored `memory/research/` directories; annotations and exports
are separate.

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
append-only JSONL file in ignored `memory/run-logs/` (under `--memory-dir` when
configured). Filenames include UTC time, experiment name and a unique suffix.
Resuming creates another file. Logs contain complete rendered prompts and inputs,
template sources/hashes, raw responses, validation/normalization, searches and
committed changes. Configured secrets are redacted; records are flushed and
fsynced incrementally. A missing `execution_end` indicates an abrupt interruption.
Inspect a log with an editor or, for example:

```bash
jq -r 'select(.kind == "interaction_request") | .data.request.messages[].content' memory/run-logs/FILE.jsonl
jq 'select(.kind == "interaction_response" or .kind == "interaction_validation")' memory/run-logs/FILE.jsonl
```

`Research.run()` also creates a log. Custom Python supervisors can group
initialization and repeated `step()` calls with `with research.execution():`.
Standalone `--root` runs default to a sibling `run-logs/` directory; provide
`--memory-dir` to choose the log home. Journals and interaction phase files remain
the recovery authority, and the viewer/transcript commands continue to use them.

List experiment names, dates, byte sizes, retention and completion/recovery status:

```bash
PYTHONPATH=src python3 -m mira research-cleanup
PYTHONPATH=src python3 -m mira research-cleanup --experiment NAME
```

These commands delete nothing. New research is retained by default; use
`research-init --disposable` for development runs. Demos are disposable.
Legacy experiments are unclassified and protected. To deliberately designate an
existing development run, then separately delete it once completed:

```bash
PYTHONPATH=src python3 -m mira research-cleanup --experiment NAME --disposable --apply
PYTHONPATH=src python3 -m mira research-cleanup --experiment NAME --apply
```

Repeat `--experiment` for multiple IDs; add `--older-than-days 7` to restrict
deletion by last modification. `--retain --apply` protects a selected run again.
Cleanup refuses active, incomplete, recovery-blocked or retained experiments and
symlinked paths. It archives inspectable records to `memory/run-logs/` before
deleting a selected disposable run. Execution logs are never removed by cleanup;
you may delete old log files manually.
