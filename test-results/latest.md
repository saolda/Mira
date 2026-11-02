# Latest development test results

Recorded: 2026-11-02T22:08:03.268696+11:00 (Australia/Hobart).

Tested implementation and tests commit: `1d04d849c17c2df5be2a2062d6680a9deac50e76`.

Tests: **553**; failures: **0**; errors: **0**; skipped: **0**.
Result: **PASS** (131.125 seconds).

## Validation

Approved G1 template loading and request attribution; independent complete-backlog enrichment; source-payload hydration and corruption rejection; scientific-definition exclusion without erasing provenance; received-component revalidation without generation or receipt overwriting; MeSH supplementary-record validation; native token/call limits, recovery and uncertain-submission safeguards; standard glossary/browser integration. Existing research and synthesis regressions remain enabled.

## Active glossary

**32/32 terms defined**: six MeSH-defined, one directly source-defined technical entry and 25 provisional-only. No undefined or genuinely ambiguous entries. Eight genuine local Qwen calls used 19,139 total tokens. Five flawed model versions were explicitly excluded, including two GLCM attempts; a directly attributed technical-source definition resolved that mathematical object. Model-only definitions remain provisional.

Real Chromium tests passed canonical/alias search, case/whitespace normalization, partial matching, keyboard navigation, focus/scrolling, sticky search, temporary highlighting and names-only search. The normal viewer served the same current export at glossary revision 126. Ordinary rerun made no record changes or model/provider calls.

The owner-approved architecture and existing production prompts are unchanged; the new G1 file exactly matches the approved wording. Research memories, equations, private inputs and existing evidence remain intact. One new source record intentionally supports the GLCM definition.

See [overnight-glossary-completion-20261102.md](overnight-glossary-completion-20261102.md) for the complete scientific review, corrections, caveats and preservation checks. Earlier evaluations remain available, including [scientific-synthesis-evaluation-20261102.md](scientific-synthesis-evaluation-20261102.md).

## Local diagnostics

- `log/overnight-glossary-20261102/verified-suite.stderr`
- `log/overnight-glossary-20261102/generation-ledger.json`
- `log/overnight-glossary-20261102/preservation.json`
- `log/overnight-glossary-20261102/final-browser-check.json`

Ordinary runs replace this report. Specifically requested milestone reports are retained.
