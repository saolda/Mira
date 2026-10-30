# Latest development test results

Recorded: 2026-10-30T06:03:36.545562+00:00

Tested implementation commit: `1bfb62f2912dee591a7b8b1ecc13fb03f323a386` (only validation reports differed during the final test run).

Tests: **343**; failures: **0**; errors: **0**; skipped: **0**.
Result: **PASS**.

## Validation

All 343 tests passed before experiments (56.493 s) and afterward (56.203 s). OpenAlex is omitted from all six predefined strategies; explicit usage and frozen snapshots remain supported. All 5,851 prior research files, eight prior logs and protected documents/prompts were preserved; 39 initialized corpora passed integrity checks. Full findings: [OpenAlex suspension validation](openalex-suspension-validation.md).

## Regressions and limitations

- Baseline completed two rounds (23 direct actions), then stopped before a third R4 dispatch because its request plus reserve required 17,006 of 16,384 tokens.
- Alternative retrieved two Europe PMC abstracts instead of zero, then stopped after five direct actions: S1 first exhausted its output limit, and one retry returned an invalid single-memory selection. Both new runs retained unsupported model inferences about infection versus malignancy; the clinical question remains unresolved.
- Controlled PubMed two/three/four-concept queries matched 6/5/0 publications; Europe PMC quoted equivalents matched 9/3/0. Committed query-profile defaults remain unchanged. Unequal workloads prevent an overall efficiency claim.

## Execution logs

- `memory/benchmarks/openalex-suspension-20261030/tests-after-experiments.log`
- Full experiments and execution-log paths are listed in the detailed report; local corpora and raw interactions remain outside GitHub.

Ordinary runs replace this report. Specifically requested milestone reports are retained.
