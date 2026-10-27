"""Local viewer and storage tests: canonical bytes are never changed by inspection/reviews."""
from contextlib import contextmanager
from email.message import Message
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mira.decisions import ScriptedLLM
from mira.experiments import Experiments, file_hashes, memory_home
from mira.format import dumps, loads
from mira.inspection import Inspector
from mira.research import Research
from mira.reviews import Reviews
from mira.search import FixtureSearch
from mira.store import ConflictError
from mira.viewer import Handler, ViewerServer
from test_research import evidence, draft, decision


def make_run(root):
    r = Research(root, ScriptedLLM([{"keywords": ["heat"]}, {"results": [draft()]}, decision("kill")]),
                 {"fixture": FixtureSearch([evidence()])})
    r.initialize("Original recorded question?", ["fixture"], context_budget=12000)
    r.run(5)
    return r


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "memory"
        self.catalog = Experiments(self.home)
        self.root = self.catalog.create("run-a")
        self.research = make_run(self.root)
        self.inspector = Inspector(self.home)
        self.reviews = Reviews(self.catalog)
        self.timeline = self.inspector.run("run-a")["timeline"]
        self.r4 = next(t["id"] for t in self.timeline if t["action"] == "R4")

    def request(self, method, path, payload=None, headers=None):
        """Exercise the actual HTTP handler without needing a network socket in unit tests."""
        handler = Handler.__new__(Handler)
        handler.server = SimpleNamespace(inspector=self.inspector, reviews=self.reviews, token="test-token", server_port=8767)
        handler.path, handler.command, handler.request_version = path, method, "HTTP/1.1"
        handler.requestline = method + " " + path + " HTTP/1.1"
        handler.headers = Message(); handler.headers["Host"] = "127.0.0.1:8767"
        body = dumps(payload).encode() if payload is not None else b""
        if body:
            handler.headers["Content-Type"] = "application/json"
            handler.headers["Content-Length"] = str(len(body))
            handler.headers["X-Mira-Token"] = "test-token"
        for key, value in (headers or {}).items():
            if key in handler.headers: handler.headers.replace_header(key, value)
            else: handler.headers[key] = value
        handler.rfile, handler.wfile = BytesIO(body), BytesIO()
        getattr(handler, "do_" + method)()
        response = handler.wfile.getvalue()
        head, content = response.split(b"\r\n\r\n", 1)
        status = int(head.split()[1])
        return status, content, head

    def test_persistent_default_cli_storage_and_phase1_default_unchanged(self):
        env = {**os.environ, "MIRA_MEMORY_DIR": str(self.home)}
        script=Path(self.temp.name)/'script.json'; script.write_text(dumps({'responses':[]}))
        output = subprocess.check_output([sys.executable, "-m", "mira", "research-init", "Persistent?", "--database", "fixture", "--experiment", "cli-run", "--script", str(script)], env=env, text=True)
        state = loads(output)
        self.assertEqual(Path(state["storage_root"]), self.home / "research/cli-run")
        self.assertTrue(Path(state["storage_root"], "journal").is_dir())
        self.assertFalse(Path(state["storage_root"], "generations").exists())
        # Existing explicit Phase 1 root retains its snapshot layout.
        phase1 = Path(self.temp.name) / "phase1"
        subprocess.check_call([sys.executable, "-m", "mira", "--root", str(phase1), "create", "Trial", "Phase 1"], stdout=subprocess.DEVNULL, env=env)
        self.assertTrue((phase1 / "generations").is_dir())
        self.assertFalse((phase1 / "journal").exists())

    def test_multiple_experiments_require_selection_and_are_isolated(self):
        b = self.catalog.create("run-b"); make_run(b)
        self.assertRaises(ValueError, self.catalog.select)
        self.assertEqual(self.catalog.select("run-a"), self.root)
        self.assertEqual({r["name"] for r in self.inspector.experiments()}, {"run-a", "run-b"})
        self.assertRaises(ValueError, self.inspector.decision, "run-b", self.r4)
        self.assertRaises(ValueError, self.catalog.path, "../run-a")
        self.assertRaises(ValueError, self.catalog.create, "run-a")

    def test_explicit_import_preserves_every_byte_and_source(self):
        original = file_hashes(self.root)
        exported = Path(self.temp.name) / "original.md"; exported.write_bytes(b"Original transcript\r\n")
        copied = self.catalog.import_run(self.root, "copied", transcript=exported)
        self.assertEqual(file_hashes(self.root), original)
        self.assertEqual(file_hashes(copied), original)
        self.assertEqual((self.home / "transcripts/copied/imported-original.md").read_bytes(), exported.read_bytes())
        r4 = self.inspector.decision("copied", self.r4)
        self.assertEqual(r4["inputs"]["root_question"], "Original recorded question?")
        self.assertRaises(ValueError, self.catalog.import_run, self.root, "copied")
        self.assertEqual(file_hashes(copied), original)

    def test_symlink_import_rejected_without_touching_source(self):
        (self.root / "external-link").symlink_to(Path(self.temp.name) / "outside")
        self.assertRaises(ValueError, self.catalog.import_run, self.root, "unsafe-copy")
        self.assertFalse(self.catalog.path("unsafe-copy").exists())

    def test_full_request_response_exact_and_r4_evidence_explicit(self):
        before = file_hashes(self.root)
        data = self.inspector.decision("run-a", self.r4)
        original_request = loads((self.root / "interactions" / self.r4 / "request.json").read_text())
        original_response = loads((self.root / "interactions" / self.r4 / "response.json").read_text())
        self.assertEqual(data["serialized_request"], original_request["serialized_request"])
        self.assertEqual(data["raw_response"], original_response["raw"])
        payload = loads(data["serialized_request"])
        self.assertIsNone(data["inputs"]["system_messages"])
        self.assertEqual(data["inputs"]["user_messages"][0], payload["messages"][0])
        self.assertIsNone(data["inputs"]["developer_messages"])
        self.assertIn("The fixture describes", data["structured_context"]["research_results"]["memories"][0]["markdown"])
        self.assertEqual(len(data["inputs"]["existing_memories"]), 1)
        self.assertEqual(len(data["retrieved_before_decision"]), 1)
        self.assertEqual(data["tree_before"]["q1"]["status"], "living")
        self.assertEqual(data["tree_after"]["q1"]["status"], "killed")
        self.assertTrue(data["historical_corpus"][0]["included_in_request"])
        self.assertEqual(file_hashes(self.root), before)

    def test_input_view_never_fills_from_current_state_or_memories(self):
        data = self.inspector.decision("run-a", self.r4)
        # Simulate current canonical files edited outside Mira; actual past inputs
        # and historical availability must still come from recorded artifacts.
        state_file = self.root / "research/state.json"
        state = loads(state_file.read_text()); state["nodes"]["q1"]["question"] = "Changed current question"
        state_file.write_text(dumps(state))
        (self.root / "memories/r1.md").write_text("Changed current memory")
        again = self.inspector.decision("run-a", self.r4)
        self.assertEqual(again["serialized_request"], data["serialized_request"])
        self.assertEqual(again["inputs"], data["inputs"])
        self.assertEqual(again["historical_corpus"], data["historical_corpus"])
        self.assertEqual(again["inputs"]["search_evidence"], data["inputs"]["search_evidence"])

    def test_task_and_slot_panels_use_only_actual_recorded_messages(self):
        data = self.inspector.decision("run-a", self.r4)
        actual = loads(data["serialized_request"])["messages"]
        self.assertEqual([m["role"] for m in actual], ["user"])
        self.assertEqual(data["plain_text_prompt"], actual[0]["content"])
        self.assertEqual({slot["name"]: slot["value"] for slot in data["prompt_slots"]},
                         data["record"]["request"]["prompt_template"]["bindings"]["context"])
        slots = {slot["name"]: slot for slot in data["prompt_slots"]}
        self.assertEqual(slots["question_context"]["status"], "Empty collection")
        self.assertEqual(slots["research_results"]["value"]["equations"], [])
        self.assertEqual(slots["research_results"]["status"], "Supplied")

    def test_missing_and_interrupted_record_is_visible_without_state(self):
        path = self.root / "interactions" / "00000004-interrupted"
        path.mkdir()
        (path / "request.json").write_text(dumps({"action": "R4", "timestamp": "2099-01-01", "question": "Recorded?"}))
        (self.root / "research/state.json").unlink()
        data = self.inspector.decision("run-a", path.name)
        self.assertEqual(data["status"], "interrupted")
        self.assertIsNone(data["inputs"]["system_messages"])
        self.assertIsNone(data["raw_response"])
        self.assertIsNone(data["historical_corpus"])
        self.assertIsNone(data["tree_before"])
        self.assertTrue(any(t["id"] == path.name for t in self.inspector.run("run-a")["timeline"]))
        (path / "request.json").write_text("{torn")
        self.assertTrue(self.inspector.decision("run-a", path.name)["warnings"])

    def test_committed_event_must_have_commit_marker_and_matching_hash(self):
        data = self.inspector.decision("run-a", self.r4)
        path = self.root / "events" / (data["committed_event"]["id"] + ".json")
        event = loads(path.read_text()); event["action_committed"] = "modified"
        path.write_text(dumps(event))
        self.assertIsNone(self.inspector.decision("run-a", self.r4)["committed_event"])

    def test_review_persistence_history_conflicts_and_experiment_isolation(self):
        before = file_hashes(self.root)
        first = self.reviews.save("run-a", self.r4, "questionable", "Review context sufficiency.", expected_revision=0)
        self.assertEqual(first["revision"], 1)
        self.assertEqual(Reviews(Experiments(self.home)).read("run-a", self.r4), first)
        self.assertRaises(ConflictError, self.reviews.save, "run-a", self.r4, "approved", "stale", expected_revision=0)
        second = self.reviews.save("run-a", self.r4, "needs_investigation", "Inspect actual instructions.", expected_revision=1)
        self.assertEqual(len(second["history"]), 2)
        self.assertEqual(file_hashes(self.root), before)
        # Importing the same run retains its decision IDs, but annotations stay separate.
        self.catalog.import_run(self.root, "copy")
        self.assertIsNone(self.reviews.read("copy", self.r4))
        self.assertEqual(self.research.step()["status"], "finished")
        self.assertEqual(file_hashes(self.root), before)

    def test_real_http_handler_read_only_routes_reviews_and_local_boundary(self):
        before = file_hashes(self.root)
        status, content, headers = self.request("GET", "/")
        self.assertEqual(status, 200); self.assertIn(b"Decision viewer", content)
        self.assertIn(b"connect-src 'self'", headers)
        self.assertEqual(self.request("GET", "/app.js")[0], 200)
        status, content, _ = self.request("GET", "/api/experiments")
        self.assertEqual(status, 200); self.assertEqual(json.loads(content)[0]["name"], "run-a")
        path = f"/api/experiments/run-a/decisions/{self.r4}"
        status, content, _ = self.request("GET", path)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(content)["serialized_request"], self.inspector.decision("run-a", self.r4)["serialized_request"])
        review_path = f"/api/experiments/run-a/reviews/{self.r4}"
        payload = {"status": "questionable", "comments": "<script>local text only</script>", "expected_revision": 0}
        self.assertEqual(self.request("POST", review_path, payload, {"X-Mira-Token": "wrong"})[0], 403)
        self.assertEqual(self.request("POST", review_path, payload, {"Origin": "https://external.example"})[0], 403)
        self.assertEqual(self.request("GET", "/api/session", headers={"Host": "external.example"})[0], 403)
        self.assertEqual(self.request("GET", "/api/experiments/%2e%2e")[0], 400)
        self.assertEqual(self.request("POST", path, payload)[0], 404)
        self.assertEqual(self.request("POST", review_path, payload)[0], 200)
        self.assertEqual(self.request("POST", review_path, payload)[0], 409)
        self.assertEqual(self.reviews.read("run-a", self.r4)["comments"], payload["comments"])
        self.assertEqual(file_hashes(self.root), before)

    def test_transcript_exports_are_persistent_and_do_not_change_corpus(self):
        before = file_hashes(self.root)
        env = {**os.environ, "MIRA_MEMORY_DIR": str(self.home)}
        output = subprocess.check_output([sys.executable, "-m", "mira", "transcript", "--experiment", "run-a", "--full"], env=env, text=True)
        saved = (self.home / "transcripts/run-a/full.md").read_text()
        self.assertEqual(output.rstrip(), saved.rstrip())
        self.assertIn("serialized_request", saved)
        self.assertEqual(file_hashes(self.root), before)

    def test_template_catalog_http_route_is_read_only(self):
        before = file_hashes(self.root)
        status, content, _ = self.request("GET", "/api/prompt-templates")
        self.assertEqual(status, 200)
        data = json.loads(content)
        self.assertEqual({entry["action"] for entry in data}, {"R0", "R1", "R3", "R4", "R5", "S2"})
        self.assertEqual(len(data[0]["files"]), 1)
        status, content, _ = self.request("GET", f"/api/experiments/run-a/decisions/{self.r4}")
        self.assertTrue(json.loads(content)["template_verification"]["matches_recorded_request"])
        self.assertEqual(file_hashes(self.root), before)

    def test_default_server_binding_is_localhost(self):
        with patch("mira.viewer.ThreadingHTTPServer.__init__", return_value=None) as parent:
            ViewerServer(self.home)
        self.assertEqual(parent.call_args.args[0], ("127.0.0.1", 8767))

    def test_failed_rejected_and_completed_decisions_are_distinguished(self):
        for name, response, status in [("failed", RuntimeError("network failure"), "failed"),
                                       ("rejected", "{malformed response", "rejected")]:
            root = self.catalog.create(name)
            r = Research(root, ScriptedLLM([response]), {})
            r.initialize("Diagnostic?", ["fixture"]); r.step()
            item = next(t for t in self.inspector.run(name)["timeline"] if t["kind"] == "decision")
            self.assertEqual(item["status"], status)
            data = self.inspector.decision(name, item["id"])
            self.assertEqual(data["status"], status)
            if status == "rejected": self.assertEqual(data["raw_response"], response)
            self.assertIsNone(data["committed_event"]["action_committed"])
        self.assertEqual(self.inspector.decision("run-a", self.r4)["status"], "completed")

    def test_missing_historical_payload_never_uses_current_memory_as_replacement(self):
        before = self.inspector.decision("run-a", self.r4)
        for manifest_path in (self.root / "journal").glob("*.json"):
            manifest = loads(manifest_path.read_text())
            for entry in manifest["files"]:
                if entry["path"] == "memories/r1.md": (self.root / entry["payload"]).unlink()
        result = self.inspector.decision("run-a", self.r4)
        self.assertEqual(result["inputs"], before["inputs"])
        self.assertIsNone(result["historical_corpus"][0]["markdown"])
        self.assertTrue(result["warnings"])

    def test_default_local_memory_is_ignored_by_git(self):
        repository = Path(__file__).resolve().parents[1]
        result = subprocess.run(["git", "check-ignore", "--quiet", "memory/research/example/interactions/request.json"], cwd=repository)
        self.assertEqual(result.returncode, 0)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(memory_home(), repository / "memory")
