# Latest development test results

Recorded: 2026-10-30T08:14:25.958305+00:00

Tested implementation and regression-test commits: `4cb524f` and `1545c85` (only validation reports differed during the final test run).

Tests: **350**; failures: **0**; errors: **0**; skipped: **0**.
Result: **PASS**.

## Validation

The saved blocked R4 request fell from **17,006 to 8,834 tokens**, including the unchanged 4,096-token reserve. All 12 search entries and the complete scientific context were retained. Full suites passed **350 tests** before and after live validation.

The fresh alternative-profile run completed **three rounds / 30 direct actions**. Its three R4 requests fit at **8,095 / 9,210 / 9,603** tokens. It stopped at the original deadline guard: 806.255 seconds wall time, including 255.385 seconds active execution and an inspection pause. Detailed findings and exact review proposals: [R4 context validation](r4-context-validation.md).

## Regressions and limitations

- S1 remained valid in the fresh run; one S2 integration rejection was handled by normal controller continuation. Scientific direction, population and unsupported-inference errors remain.
- The prior S1 catalogue contained both eligible memories, and a two-memory S2 request fit. The failures involved output deliberation/truncation and an invalid singleton selection; no S1 prompt, scheduling or validation rule changed.
- All 6,240 prior research files, 13 prior logs and protected prompts/documents remain unchanged; 40 initialized corpora passed integrity checks. The medical question remains unresolved.

## Execution logs

- `memory/benchmarks/r4-context-20261030/tests-after.log`
- Full experiment, continuation and independent execution-log paths are listed in the detailed report. Raw corpora, temporary profiles and interaction logs remain outside GitHub.

Ordinary runs replace this report. Specifically requested milestone reports are retained.
