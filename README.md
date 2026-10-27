# Mira

A local, inspectable autonomous researcher with persistent R0 strategy selection, multi-database R1–R5 research, branching and synthesis.
Canonical Markdown and equation JSON remain authoritative; SQLite full-text,
relationship and vector indexes can be rebuilt.

- [Project purpose](ProjectOverview.md)
- [Implemented architecture](architecture.md)

Keep project documentation in these three files; edit minimally and preserve existing directives.

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
are separate.

LLM prompts are editable in [prompt_templates/](prompt_templates/).
The viewer’s **Prompt templates** button shows current sources; each decision
shows the saved filled prompts and template provenance when recorded.
