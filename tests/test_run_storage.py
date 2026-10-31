"""Self-contained execution exports and conservative, explicit cleanup."""
from copy import deepcopy
import json
import itertools
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from mira.decisions import ScriptedLLM
from mira.experiments import Experiments, file_hashes
from mira.format import digest, dumps, loads
from mira.interactions import ExecutionLog, read_records, transcript
from mira.research import Research
from mira.research_demo import DemoLLM, evidence
from mira.search import FixtureSearch


def extraction(summary="The fixture reports two heat measurements."):
    return {"summary": summary, "results": [{"type": "claim", "text": "The fixture authors report fictional heat measurements.",
        "qualification": "Synthetic fixture only.", "source_ids": ["fixture-1"], "related_to": None}]}


def interrupted(root):
    class ExitModel(ScriptedLLM):
        def complete(self, serialized): os._exit(73)
    Research(root, ExitModel([]), {}).run(1)


class RunStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "memory"
        self.catalog = Experiments(self.home)
        self.logs = self.home.parent / "log"

    def make(self, name="fixture", *, disposable=True, responses=None, search=None):
        root = self.catalog.create(name, reset=True)
        llm = ScriptedLLM(responses if responses is not None else [
            {"new_concepts": [], "reason": "Fixture search plan.", "search_concepts": ["fictional heat", "transfer"]}, extraction(), {"decision": "answered", "reason": "Fixture finished."}])
        r = Research(root, llm, {"fixture": FixtureSearch(search if search is not None else [evidence()])})
        return r

    def initialize(self, r):
        return r.initialize("How does the fictional heat barrier work?", ["fixture"], context_budget=60000)

    def finish(self, name="fixture", **kwargs):
        r = self.make(name, **kwargs)
        with r.execution(self.logs, command="fixture supervisor") as log:
            self.initialize(r); result = r.run(8)
        self.assertEqual(result["status"], "finished")
        return r, log.path

    def rows(self, path):
        return [loads(line) for line in path.read_text().splitlines()]

    def test_complete_rendered_prompts_context_templates_responses_and_changes(self):
        r, log = self.finish()
        rows = self.rows(log)
        requests = [row for row in rows if row["kind"] == "interaction_request"]
        self.assertEqual([row["action"] for row in requests], ["R1", "R3", "R4"])
        self.assertEqual([row["data"]["serialized_request"] for row in requests], r.llm.requests)
        canonical = read_records(r.store.root)
        for row, record in zip(requests, canonical):
            data = row["data"]
            self.assertEqual(data["context"], record["request"]["context"])
            self.assertEqual(data["prompt_template"]["filled_messages"], loads(r.llm.requests[requests.index(row)])["messages"])
            for source in data["prompt_template"]["files"]:
                self.assertEqual(source["sha256"], digest(source["source"]))
            self.assertTrue(data["context_usage"])
            self.assertEqual(row["model"], r.llm.model)
            self.assertEqual(row["generation_parameters"], r.llm.settings)
        responses = [row for row in rows if row["kind"] == "interaction_response"]
        self.assertEqual([row["data"]["raw"] for row in responses], [record["response"]["raw"] for record in canonical])
        checks = [row for row in rows if row["kind"] == "interaction_validation"]
        self.assertEqual(checks[1]["data"]["normalized_response"], extraction())
        changed = [row["data"]["canonical_changes"] for row in rows if row["kind"] == "action_outcome"]
        self.assertTrue(any("memories/r1.md" in change for change in changed))
        self.assertTrue(any("research/state.json" in change for change in changed))
        self.assertEqual([row["sequence"] for row in rows], list(range(1, len(rows) + 1)))
        self.assertEqual([row["timestamp"] for row in rows], sorted(row["timestamp"] for row in rows))
        self.assertEqual(rows[-1]["data"]["reason"], "finished")
        self.assertEqual(len({row["execution_id"] for row in rows}), 1)

    def test_all_actions_r0_through_r5_s1_s2_are_recorded(self):
        root = self.catalog.create("all-actions", disposable=True)
        registry = Path(self.temp.name) / "strategies.json"
        registry.write_text(dumps([{"id": "fixture", "name": "Fixture", "description": "Synthetic source.", "databases": ["arxiv"], "profiles": {"arxiv": "arxiv_subject"}}]))
        r = Research(root, ScriptedLLM([{"strategy": "fixture", "reason": "Controlled fixture."}]),
            {"arxiv": FixtureSearch([evidence("fixture-" + str(i)) for i in range(1, 20)])})
        with r.execution(self.logs) as log:
            r.initialize("What can the fictional heat-barrier fixture tell us?", registry=registry,
                         context_budget=24000, research_capacity_tokens=6000, synthesis_interval=3)
            r.llm = DemoLLM()
            ticks = itertools.count(1000)
            r.clock = lambda: next(ticks)
            r.sleep = lambda delay: None
            result = r.run(50)
        rows = self.rows(log.path)
        actions = {row.get("action") for row in rows if row["kind"] in {"interaction_request", "action_outcome"}}
        self.assertTrue({"R0", "R1", "R2", "R3", "R4", "R5", "S1", "S2"} <= actions, actions)
        self.assertNotEqual(result["status"], "rejected")
        self.assertEqual(len(list(self.logs.glob("*.jsonl"))), 1)

    def test_search_outcomes_include_full_returned_evidence_and_exact_query(self):
        result = evidence(); result["raw_api_response"] = "complete provider body\n" + "data" * 3000
        r, log = self.finish(search=[result])
        searches = [row for row in self.rows(log) if row["kind"] == "search_result"]
        self.assertEqual(len(searches), 1)
        data = searches[0]["data"]
        self.assertEqual(data["query"], r.adapters["fixture"].queries[0])
        self.assertEqual({k:v for k,v in data["retrieval"].items() if k!='requests'}, result)
        self.assertTrue(data['retrieval']['requests'])
        self.assertTrue(data["query_submitted"])

    def test_long_prompt_inputs_are_not_truncated(self):
        supplied = evidence(); supplied["results"][0]["content"] += " source text" * 1200 + " END-OF-INPUT"
        r, log = self.finish(search=[supplied])
        request = next(row["data"] for row in self.rows(log) if row["kind"] == "interaction_request" and row["action"] == "R3")
        self.assertIn("END-OF-INPUT", request["request"]["messages"][0]["content"])
        self.assertEqual(request["context"]["research"]["results"][0]["content"], supplied["results"][0]["content"])

    def test_rejected_output_and_normalized_response_are_preserved(self):
        r = self.make(responses=[{"new_concepts": [], "reason": "Fixture search plan.", "search_concepts": ["heat", "transfer"]}, {"summary": "Unused nonempty summary", "results": []},
            {"decision": "answered", "reason": "Fixture complete."}])
        self.initialize(r); result = r.run(8)
        checks = [row["data"] for row in self.rows(Path(result["execution_log"])) if row["kind"] == "interaction_validation"]
        self.assertEqual(checks[1]["proposed_response"]["summary"], "Unused nonempty summary")
        self.assertEqual(checks[1]["normalized_response"], {"summary": "", "results": []})
        r = self.make("invalid", responses=[{"new_concepts": [], "reason": "Fixture search plan.", "search_concepts": ["heat", "transfer"]}, "{not json", {"decision": "answered", "reason": "Fixture complete."}])
        self.initialize(r); result = r.run(8)
        rows = self.rows(Path(result["execution_log"]))
        rejected = next(row for row in rows if row["kind"] == "interaction_validation" and not row["data"]["accepted"])
        self.assertTrue(rejected["data"]["error"])
        self.assertIsNone(rejected["data"]["normalized_response"])
        self.assertTrue(any("{not json" in row["data"].get("raw", "") for row in rows if row["kind"] == "interaction_response"))

    def test_incremental_records_survive_abrupt_exit_and_resume_has_no_replayed_calls(self):
        r = self.make(); self.initialize(r)
        child = multiprocessing.get_context("fork").Process(target=interrupted, args=(str(r.store.root),))
        child.start(); child.join(15)
        self.assertEqual(child.exitcode, 73)
        log = next(self.logs.glob("*.jsonl")); before = log.read_bytes()
        rows = self.rows(log)
        self.assertEqual(rows[-1]["kind"], "interaction_request")
        self.assertIn("serialized_request", rows[-1]["data"])
        with self.assertRaisesRegex(ValueError, "interrupted/unknown"):
            r.run(1)
        self.assertEqual(log.read_bytes(), before)
        new = next(p for p in self.logs.glob("*.jsonl") if p != log)
        self.assertFalse(any(row["kind"] == "interaction_request" for row in self.rows(new)))
        self.assertEqual(self.rows(new)[-1]["data"]["reason"], "exception")

    def test_new_execution_for_resumed_experiment_and_cycle_limit_reason(self):
        r = self.make(); self.initialize(r)
        first = r.run(1); old = Path(first["execution_log"]).read_bytes()
        restarted = Research(r.store.root, r.llm, r.adapters)
        second = restarted.run(8)
        self.assertNotEqual(first["execution_log"], second["execution_log"])
        self.assertEqual(Path(first["execution_log"]).read_bytes(), old)
        self.assertEqual(self.rows(Path(first["execution_log"]))[-1]["data"]["reason"], "cycle_limit")
        ids = [row["interaction_id"] for p in (first["execution_log"], second["execution_log"]) for row in self.rows(Path(p)) if row["kind"] == "interaction_request"]
        self.assertEqual(len(ids), len(set(ids)))

    def test_recovered_commit_receipt_is_exported_once_without_repeating_model_call(self):
        r = self.make(); self.initialize(r)
        with self.assertRaises(RuntimeError):
            with r.execution(self.logs) as log:
                r.step(); r.step()
                def fault(point):
                    if point == "before_commit": raise RuntimeError("interrupted publication")
                r.step(fault=fault)
        old_log = log.path; old = old_log.read_bytes()
        operation = r.store.recovery_status()["operations"][0]["id"]
        r.store.repair(operation, apply=True)
        result = r.run(4)
        rows = self.rows(Path(result["execution_log"]))
        recovered = [row for row in rows if row["kind"] == "interaction_outcome" and row["data"].get("recovered_from_committed_event")]
        self.assertEqual(len(recovered), 1)
        self.assertEqual(old_log.read_bytes(), old)
        self.assertTrue(any(row["kind"] == "recovered_interaction_context" and "response" in row["data"] for row in rows))
        later = r.run(1)
        self.assertFalse(any(row["kind"] == "interaction_outcome" for row in self.rows(Path(later["execution_log"]))))
        self.assertEqual(len(r.llm.requests), 3)

    def test_cli_invocations_have_separate_logs_including_setup_failure(self):
        script = Path(self.temp.name) / "script.json"
        script.write_text(dumps({"responses": [{"new_concepts": [], "reason": "Fixture search plan.", "search_concepts": ["heat", "transfer"]}, extraction(), {"decision": "answered", "reason": "Done."}], "providers": {"fixture": [evidence()]}}))
        cmd = [sys.executable, "-m", "mira", "--memory-dir", str(self.home)]
        init = loads(subprocess.check_output([*cmd, "research-init", "Heat?", "--experiment", "cli", "--database", "fixture", "--disposable", "--script", str(script), "--context-budget", "60000"], text=True))
        run = loads(subprocess.check_output([*cmd, "research-run", "--experiment", "cli", "--script", str(script)], text=True))
        self.assertNotEqual(init["execution_log"], run["execution_log"])
        self.assertEqual(self.rows(Path(init["execution_log"]))[-1]["data"]["reason"], "initialized")
        self.assertEqual(self.rows(Path(run["execution_log"]))[-1]["data"]["reason"], "finished")
        before = set(self.logs.glob("*.jsonl"))
        failed = subprocess.run([*cmd, "research-init", "Q?", "--experiment", "failed", "--new-experiment", "--strategy", "invalid", "--script", str(script)], capture_output=True)
        self.assertNotEqual(failed.returncode, 0)
        failure_log = next(iter(set(self.logs.glob("*.jsonl")) - before))
        self.assertEqual(self.rows(failure_log)[-1]["data"]["reason"], "exception")
        standalone = Path(self.temp.name) / "explicit-root"
        subprocess.check_output([*cmd, "--root", str(standalone), "research-init", "Heat?", "--database", "fixture", "--disposable", "--script", str(script)], text=True)
        self.assertEqual(loads((standalone / "experiment.json").read_text())["layout"], "single-active-corpus")

    def test_test_runner_overwrites_latest_report_and_records_failures(self):
        directory = Path(self.temp.name) / "suite"; directory.mkdir()
        test = directory / "test_fixture.py"
        test.write_text("import unittest\nclass Fixture(unittest.TestCase):\n def test_fixture(self): self.fail('expected fixture failure')\n")
        report = Path(self.temp.name) / "latest.md"
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/run_tests.py"), "--start-directory", str(directory), "--report", str(report)]
        failed = subprocess.run(command, capture_output=True)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("FAIL", report.read_text()); self.assertIn("failures: **1**", report.read_text())
        test.write_text("import unittest\nclass Fixture(unittest.TestCase):\n def test_fixture(self): self.assertTrue(True)\n")
        passed = subprocess.run([*command, "--validation-summary", "Controlled fixture.", "--run-log", "example.jsonl"], capture_output=True)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertNotIn("FAIL", report.read_text()); self.assertIn("PASS", report.read_text())
        self.assertIn("Controlled fixture.", report.read_text()); self.assertIn("example.jsonl", report.read_text())

    def test_secrets_are_redacted_in_all_fields_and_api_exceptions(self):
        secret = 'private"token\\value'
        class SecretModel(ScriptedLLM): secrets = (secret,)
        r = self.make(); r.llm = SecretModel([RuntimeError("transport failed " + secret)])
        r.trace.secrets = (secret,)
        with patch.dict(os.environ, {"MIRA_NCBI_API_KEY": secret}):
            with r.execution(self.logs) as log:
                r.initialize("Question with " + secret, ["fixture"], context_budget=60000)
                result = r.run(1)
        text = log.path.read_text()
        self.assertNotIn(secret, text); self.assertNotIn(json.dumps(secret)[1:-1], text)
        self.assertIn("[REDACTED]", text)
        self.assertEqual(result["status"], "rejected")

    def test_termination_and_budget_failure_without_model_dispatch(self):
        r = self.make(); r.llm.settings = {**r.llm.settings, "max_tokens": 50}
        r.initialize("Tiny budget?", ["fixture"], context_budget=100, output_reserve=50)
        result = r.run(1)
        rows = self.rows(Path(result["execution_log"]))
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(r.llm.requests)
        self.assertTrue(any(row["kind"] == "model_request_blocked" for row in rows))
        self.assertEqual(rows[-1]["data"]["reason"], "rejected")
        with self.assertRaises(KeyboardInterrupt):
            with r.execution(self.logs) as log: raise KeyboardInterrupt()
        self.assertEqual(self.rows(log.path)[-1]["data"]["reason"], "interrupted")

    def test_rejected_concurrent_runner_has_its_own_failure_log(self):
        r, _ = self.finish()
        other = Research(r.store.root, ScriptedLLM([]), {})
        with r.execution(self.logs):
            before = set(self.logs.glob("*.jsonl"))
            with self.assertRaises(BlockingIOError): other.run(1)
            failed = next(iter(set(self.logs.glob("*.jsonl")) - before))
            self.assertEqual(self.rows(failed)[-1]["data"]["error_type"], "BlockingIOError")
            self.assertEqual(self.catalog.cleanup(["fixture"])["experiments"][0]["status"], "active_corpus")



if __name__ == "__main__": unittest.main()
