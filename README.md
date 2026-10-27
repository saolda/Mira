# Mira

A local, inspectable autonomous researcher with persistent R1–R5 research, branching and synthesis.
Canonical Markdown and equation JSON remain authoritative; SQLite full-text,
relationship and vector indexes can be rebuilt.

- [Project purpose](ProjectOverview.md)
- [Implemented architecture](architecture.md)
- [Working foundation, API and commands](docs/knowledge_foundation.md)
- [Local reference review](docs/reference_architecture_review.md)
- [Phase 1 results and limitations](docs/phase1_results.md)
- [Live persistence and crash recovery (Increment 2a)](docs/live_persistence.md)
- [Research controller, transcripts, gardener and reproduction commands](docs/research_execution.md)

Run tests with `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
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
are separate. See [storage, imports, viewer and review instructions](docs/persistent_decision_viewer.md).

LLM prompts are editable in [prompt_templates/](prompt_templates/README.md).
The viewer’s **Prompt templates** button shows current sources; each decision
shows the saved filled prompts and template provenance when recorded.

Start a real session using the exact [Fractal launch commands](docs/research_execution.md#start-a-sustained-session).
See [current validation results and limits](docs/revised_architecture_results.md).
