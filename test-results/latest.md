# Latest development test results

Recorded: 2026-10-30T05:12:44.102019+00:00

Tested implementation commit: `df75a8792e59ed68e8b74cea3e74bb610761d0d0`.

Tests: **339**; failures: **0**; errors: **0**; skipped: **0**.
Result: **PASS**.

## Validation

Stage 1 passed 315 tests. Final Stage 2 verification covers eight named profiles, legacy partial-round compatibility, durable retries, shared-host pacing, waiting, journal recovery and credential-free request logs.

## Regressions and limitations

All automated checks passed. Live validation stopped normally on a persisted OpenAlex HTTP 429 cooldown; Europe PMC returned no records and the clinical question remains unresolved. Details: query-profile-validation.md.

## Execution logs

- Initialization: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_051320_query-profile-medical-20261030_118cbe5737c3.jsonl`.
- Live validation: `/home/eric/Dev/Mira/memory/run-logs/2026-10-30_051321_query-profile-medical-20261030_99354632fb7e.jsonl`.
- Detailed report: `test-results/query-profile-validation.md`.

Stage 1: 315 tests passed in 54.682 seconds (`87ed8ae99747ab896ba5db64ac5477273ab6d9b5`). Final Stage 2: 339 tests passed in 57.152 seconds. The tested source bytes became commit `df75a8792e59ed68e8b74cea3e74bb610761d0d0`; subsequent changes are validation reports only.

Ordinary runs replace this report. Specifically requested milestone reports are retained.
