# Mira

A local, inspectable knowledge foundation for a future autonomous researcher.
Canonical Markdown and equation JSON remain authoritative; SQLite full-text,
relationship and vector indexes can be rebuilt.

- [Project purpose](ProjectOverview.md)
- [Architecture draft](architecture.md)
- [Working foundation, API and commands](docs/knowledge_foundation.md)
- [Local reference review](docs/reference_architecture_review.md)
- [Phase 1 results and limitations](docs/phase1_results.md)
- [Live persistence and crash recovery (Increment 2a)](docs/live_persistence.md)

Run tests with `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
Run a synthetic demonstration with
`PYTHONPATH=src python3 -m mira --root /tmp/mira-demo --test-embedding demo`.
The test embedding is not a semantic model; actual local-model results are recorded
separately. No old memories or runtime state are imported.
