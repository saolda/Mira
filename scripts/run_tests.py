"""Run unittest discovery and atomically replace the ordinary development report."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import unittest

from mira.experiments import atomic_text

ROOT = Path(__file__).resolve().parents[1]


def write_report(result, path, *, commit, validation, limitations=(), logs=()):
    lines = ["# Latest development test results", "",
        "Recorded: " + datetime.now(timezone.utc).isoformat(), "",
        "Tested implementation commit: `" + commit + "`.", "",
        f"Tests: **{result.testsRun}**; failures: **{len(result.failures)}**; errors: **{len(result.errors)}**; skipped: **{len(result.skipped)}**.",
        "Result: **" + ("PASS" if result.wasSuccessful() else "FAIL") + "**.", "",
        "## Validation", "", validation, "", "## Regressions and limitations", ""]
    failed = [test.id() for test, _ in [*result.failures, *result.errors]]
    lines.extend("- Failing test: `" + identity + "`." for identity in failed)
    lines.extend("- " + message for message in limitations)
    if not failed and not limitations: lines.append("None reported.")
    lines += ["", "## Execution logs", ""]
    lines.extend("- `" + str(path) + "`" for path in logs)
    if not logs: lines.append("No persistent experiment was run; automated fixtures use temporary directories.")
    lines += ["", "Ordinary runs replace this report. Specifically requested milestone reports are retained.", ""]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(path, "\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-directory", default=str(ROOT / "tests"))
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--report", default=str(ROOT / "test-results/latest.md"))
    parser.add_argument("--validation-summary", default="No external validation experiment was requested for this test invocation.")
    parser.add_argument("--limitation", action="append", default=[])
    parser.add_argument("--run-log", action="append", default=[])
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(args.start_directory, pattern=args.pattern)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
            commit += " (working tree under test)"
    except (OSError, subprocess.CalledProcessError): commit = "unavailable"
    write_report(result, args.report, commit=commit, validation=args.validation_summary,
                 limitations=args.limitation, logs=args.run_log)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__": raise SystemExit(main())
