# R1 and single-corpus storage validation — 31 October 2026

Active experiment: `medical-r4-context-20261030`, relocated directly into `memory/`.
All original canonical memory, equation, state, evidence, source, interaction and journal hashes were preserved. The active corpus validates with 7 memories, 33 relationships and 32 units including documents. User question files and review files (including browser-profile symlinks, without following them) are unchanged.

```text
memory/
  memories/                  # active r*.md and s*.md
  equations/
  glossary/
  identity.json
  experiment.json
  research/
    state.json
    question.md
    results/
    dropout-sustained/        # protected legacy corpus; unresolved interaction
  events/
  interactions/
  journal/
  retrieval_calls/
  retrieved/
  questions/                 # preserved user inputs
  reviews/                   # preserved user files
  benchmarks/                # preserved scripts and results
  imports/                   # preserved import receipts
log/
  *.jsonl                    # independent execution logs
  benchmarks/                # historical benchmark logs
  legacy/                    # historical diagnostics, no corpus archives
  transcripts/
  storage-transition-20261031.json
```

Historical log moves preserved contents: 16 execution logs, 24 benchmark logs, and existing transcript exports. No old scientific corpus was archived. `memory/research/medical-r4-context-20261030/` was removed after relocating its corpus.

The following 38 generated experiment directories were deleted after path, symlink, runner/writer lock, canonical journal, glossary and uncertain-submission checks:

- `memory/research/architecture-boolean-eval-20261027/`
- `memory/research/architecture-clean-eval-20261027/`
- `memory/research/architecture-eval-20261027/`
- `memory/research/architecture-final-eval-20261027/`
- `memory/research/architecture-focused-eval-20261027/`
- `memory/research/architecture-provider-eval-20261027/`
- `memory/research/autonomous-research-40min/`
- `memory/research/autonomous-research-40min-20261028-attribution/`
- `memory/research/autonomous-research-rate-limit-20261028-093851/`
- `memory/research/autonomous-research-recovery-20261028-091633/`
- `memory/research/autonomous-research-techniques-20261027/`
- `memory/research/capacity-autonomous-20261027-092523/`
- `memory/research/capacity-autonomous-20261027-092951/`
- `memory/research/capacity-branching-20261027-092523/`
- `memory/research/capacity-branching-20261027-092951/`
- `memory/research/capacity-collection-20261027-092523/`
- `memory/research/capacity-collection-20261027-092951/`
- `memory/research/capacity-collection-20261027-093437/`
- `memory/research/focused-r1-20261025/`
- `memory/research/medical-glossary-20261029-064751/`
- `memory/research/medical-glossary-20261029-065011/`
- `memory/research/medical-no-openalex-baseline-20261030/`
- `memory/research/medical-query-comparison-20261030/`
- `memory/research/medical-question-file-20261029-074524/`
- `memory/research/medical-r0-20261029-061459/`
- `memory/research/medical-r1-benchmark-20261030/`
- `memory/research/medical-strategy-20261029-061459/`
- `memory/research/monte-carlo-dropout/`
- `memory/research/ordered-r3-arxiv-20261025/`
- `memory/research/ordered-r3-arxiv-focused-20261025/`
- `memory/research/plain-text-prompts-20261025/`
- `memory/research/prompt-template-check/`
- `memory/research/query-profile-medical-20261030/`
- `memory/research/state-prompt-check/`
- `memory/research/strategies-cli-automatic-20261027/`
- `memory/research/strategies-real-20261027/`
- `memory/research/synthesis-redesign-20261029-052722/`
- `memory/research/synthesis-redesign-20261029-052906/`

`memory/research/dropout-sustained/` was not removed: it has an unresolved model interaction and remains recovery-blocked. Its complete file hashes are unchanged. No acknowledgement or recovery decision was fabricated.

R1 uses one discovery/selection call per round and shared provider concepts. Empty or repeated-only plans remain living and return recoverable `waiting_for_r4_upgrade`. R2 retains one provider search per action; R3 retains one source extraction per action. R4 prompt and decision schema are unchanged, as are `architecture.md`, `futureWork.md` and all other prompts.

Validation: see [latest.md](latest.md) for the full-suite totals. The local ignored [storage audit](../log/storage-transition-20261031.json) records all preservation hashes, deletion names and moved log paths.
