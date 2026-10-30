# R1 prompt, inputs and output validation

Recorded: 2026-10-30 (Australia/Hobart). Base: approved architecture commit `04ae3f7` on `main`.

PASS: **313 tests, 0 failures, 0 errors, 0 skipped** in **54.235 seconds**.

Command: `PYTHONPATH=src python3 -m unittest discover -s tests -q`.

The suite emitted existing non-failing SQLite resource warnings. Validation used deterministic fixtures; no live model or external provider evaluation was performed.

## Changes

- Replaced `prompt_templates/R1.txt` with the user's exact supplied UTF-8 text; verified byte-for-byte against the attachment. SHA-256: `118ab9500a04b6908cfa424ecb726e52ac673ff0f052fda2b5cdfa4824aa89bd`.
- Declared all eight prompt variables. Preserved selected versus ancestor questions, bounded memory findings/gaps, research brief and indexed glossary retrieval.
- Added independent `search_outcomes`: the latest 12 committed retrieval records for the selected node, sorted chronologically. Entries retain provider, nullable profile ID, exact compiled query, submission flag, status, returned record count and unique record count. Counts come from persisted retrieval metadata or unique results plus duplicates; cached source payloads are unnecessary. Missing legacy profile or submission metadata stays null/unknown rather than being invented. Previous proposed terms never imply search success or failure.
- Removed `recent_search_outcomes` from glossary context and its budget accounting. The complete rendered request, including independent search history, still passes the existing context validation before dispatch; oversized requests are blocked without truncating queries.
- Validated exactly one `keywords` field with 2–6 nonempty strings, each at most five whitespace-delimited words. Rejected explicit Boolean operators, field tags, known provider names and query syntax; retained scientific punctuation and lowercase conjunctions in phrases. Scientific meaning is not assessed with string heuristics. The existing literal control filter preserves order and requires a nonempty accepted list.
- Verified raw, proposed and accepted outputs remain available in interaction phases and independent execution logs. Rejections retain their raw/proposed output without advancing research progress.
- Updated single-concept scripted responses to conform to the new proposal contract and updated the demo transport's R1 heading recognition. Legacy persisted keywords and historical prompt snapshots remain readable without revalidation or rewriting.

## Coverage

Twelve additional tests cover eight populated slots and selected-question roles; explicit trust/interpretation instructions; all six provider outcome statuses and counts; submitted versus deferred outcomes; node scoping, chronological ordering and the 12-entry cap; legacy records without payload/profile/submission metadata; valid 2–6-concept responses and invalid structures/syntax; raw/proposed/accepted logs; rejected-output rollback; legacy single-concept restart; full rendered history budget checks; and independence from glossary token/entry limits. Existing tests retain coverage for relevant findings/unresolved questions, complete research objectives/background, experiment upgrades, restart, deduplication and journal recovery.

## Scope and synchronization

The initial working tree was clean on `main`. `git fetch origin main` retrieved `830c0aa` and `04ae3f7`; both changed only `architecture.md`, so a safe `git merge --ff-only origin/main` synchronized local history. Local architecture exactly matched the fetched approved file (Git blob `2a53def63b89d007e0edeefdca2ab915186d6cca`). No local architecture edits were made.

`git diff --check` passed. Architecture, all other LLM prompts, R2, provider adapters and query compilation/configuration remain unchanged relative to `04ae3f7`. The larger query-profile/retry architecture remains outside this task; the new input can project deferred/unavailable records when persisted, without implementing new R2 scheduling.

The implementation and this report are committed together on `main`; the final chat records the resulting SHA and verified GitHub synchronization.

## Changed files

- `prompt_templates/R1.txt`
- `src/mira/decisions.py`
- `src/mira/glossary.py`
- `src/mira/prompts.py`
- `src/mira/r1.py`
- `src/mira/research_demo.py`
- `test-results/latest.md`
- `tests/benchmark_glossary.py`
- `tests/test_branching.py`
- `tests/test_budget.py`
- `tests/test_collections.py`
- `tests/test_gardener.py`
- `tests/test_glossary.py`
- `tests/test_integration.py`
- `tests/test_medical.py`
- `tests/test_prompts.py`
- `tests/test_questions.py`
- `tests/test_r1.py`
- `tests/test_r3.py`
- `tests/test_research.py`
- `tests/test_run_storage.py`
- `tests/test_strategies.py`
- `tests/test_synthesis.py`
- `tests/test_viewer.py`
