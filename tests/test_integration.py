from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from mira.clients import HTTPModel, CallError
from mira.decisions import request, ScriptedLLM
from mira.format import loads, dumps
from mira.interactions import read_records
from mira.research import Research
from mira.search import ArxivSearch
from test_research import draft

ATOM = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/1234.56789v1</id><title>A controlled paper</title>
<summary>This is an abstract about uncertainty and model assumptions.</summary>
<published>2020-01-01T00:00:00Z</published><author><name>Fixture Author</name></author>
</entry></feed>'''


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        ArxivSearch._last_request = None

    def test_arxiv_query_provenance_and_explicit_truncation(self):
        calls = []
        def opener(req, timeout):
            calls.append(req); return BytesIO(ATOM)
        adapter = ArxivSearch(opener=opener, max_abstract_chars=20)
        result = adapter.search('all:"Monte Carlo" AND dropout')
        self.assertEqual(result["status"], "ok")
        self.assertIn("Monte+Carlo", result["request_url"])
        self.assertEqual(result["raw_api_response"], ATOM.decode())
        row = result["results"][0]
        self.assertEqual(row["authors"], ["Fixture Author"])
        self.assertEqual(row["content_kind"], "abstract"); self.assertTrue(row["truncated"])
        self.assertEqual(len(row["content"]), 20)
        self.assertIn("Mira/", calls[0].headers["User-agent"])

    def test_arxiv_empty_error_and_invalid_xml_are_distinct(self):
        for body, status in [(b'<feed xmlns="http://www.w3.org/2005/Atom"/>', "empty"),
            (ATOM.replace(b"http://arxiv.org/abs/1234.56789v1", b"http://arxiv.org/api/errors#bad-query"), "failed"),
            (b"bad XML", "failed"), (b"<html/>", "failed")]:
            ArxivSearch._last_request = None
            self.assertEqual(ArxivSearch(opener=lambda *a, **kw: BytesIO(body)).search("test")["status"], status)

    def test_arxiv_rate_limit_and_request_spacing(self):
        def limited(req, timeout): raise HTTPError(req.full_url, 429, "limit", {"Retry-After": "10"}, BytesIO(b"limit"))
        adapter = ArxivSearch(opener=limited)
        result = adapter.search("test")
        self.assertEqual(result["status"], "rate_limited"); self.assertEqual(result["retry_after"], "10")
        with patch("time.sleep") as sleep:
            self.assertEqual(adapter.search("test")["status"], "rate_limited")
            sleep.assert_called_once()
        ArxivSearch._last_request = None
        def failed(*a, **kw): raise URLError("offline")
        self.assertEqual(ArxivSearch(opener=failed).search("test")["status"], "failed")

    def test_http_sends_exact_serialization_with_auth_outside_body(self):
        model = HTTPModel("http://localhost:8090/v1", "test-model", api_key="private-key", no_thinking=True)
        serialized = request(model.model, model.settings, "R1", {"question": "Q?"})
        captured = []
        class Opener:
            def open(self, req, timeout): captured.append(req); return BytesIO(b'{"raw":"complete"}')
        with patch("mira.clients.build_opener", return_value=Opener()):
            self.assertEqual(model.complete(serialized), '{"raw":"complete"}')
        self.assertEqual(captured[0].data, serialized.encode())
        self.assertEqual(captured[0].full_url, "http://localhost:8090/v1/chat/completions")
        self.assertEqual(captured[0].headers["Authorization"], "Bearer private-key")
        self.assertNotIn("private-key", serialized)
        self.assertEqual(loads(serialized)["chat_template_kwargs"], {"enable_thinking": False})

    def test_http_error_and_binary_response_are_preserved(self):
        class Opener:
            def open(self, req, timeout): raise HTTPError(req.full_url, 500, "bad", {}, BytesIO(b"full error body"))
        with patch("mira.clients.build_opener", return_value=Opener()):
            with self.assertRaises(CallError) as raised: HTTPModel("http://localhost", "m").complete("{}")
            self.assertEqual(raised.exception.raw, "full error body")
        class BinaryOpener:
            def open(self, *a, **kw): return BytesIO(b"\xff\xfe")
        with patch("mira.clients.build_opener", return_value=BinaryOpener()):
            with self.assertRaises(CallError) as raised: HTTPModel("http://localhost", "m").complete("{}")
            self.assertEqual(raised.exception.raw, "base64://4=")
        for url in ("http://user:pass@localhost", "http://localhost?api_key=secret"):
            self.assertRaises(ValueError, HTTPModel, url, "m")

    def test_search_to_model_to_knowledge_keeps_raw_feed_out_of_context(self):
        with tempfile.TemporaryDirectory() as root:
            result = ArxivSearch(opener=lambda *a, **kw: BytesIO(ATOM)).search("uncertainty")
            proposal = draft(); proposal["findings"][0]["evidence_ids"] = [result["results"][0]["id"]]
            llm = ScriptedLLM([{"keywords": ["uncertainty"]}, {"memories": [proposal], "no_finding_reason": None}])
            r = Research(root, llm, {"arxiv": ArxivSearch(opener=lambda *a, **kw: BytesIO(ATOM))})
            r.initialize("What does this abstract claim?", ["arxiv"])
            with patch("time.sleep"):
                for _ in range(3): self.assertEqual(r.step()["status"], "committed")
            self.assertNotIn("raw_api_response", llm.requests[-1])
            self.assertIn("abstract", llm.requests[-1])
            ref = r.knowledge.document("r1").metadata["evidence_ref"]
            self.assertIn("raw_api_response", loads(Path(root, ref).read_text()))
            self.assertEqual(r.knowledge.relationships("r1#f1")[0]["target"], result["results"][0]["url"])

    def test_server_usage_identifier_and_rejected_complete_response_retained(self):
        envelope = dumps({"model": "actual-server-model", "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [{"finish_reason": "stop", "message": {"content": '{"keywords":["test"]}'}}]})
        with tempfile.TemporaryDirectory() as root:
            r = Research(root, ScriptedLLM([envelope]), {}); r.initialize("Q?", ["fixture"])
            self.assertEqual(r.step()["status"], "committed")
            record = read_records(root)[0]
            self.assertEqual(record["response"]["raw"], envelope)
            self.assertEqual(record["validation"]["model"]["usage"]["prompt_tokens"], 10)
            self.assertEqual(record["validation"]["model"]["model"], "actual-server-model")

    def test_escaped_secret_not_written_to_phase_or_journal(self):
        secret = 'secret-"quote\\value'
        class SecretModel(ScriptedLLM): secrets = (secret,)
        with tempfile.TemporaryDirectory() as root:
            r = Research(root, SecretModel([CallError(secret, secret)]), {}); r.initialize("Q?", ["fixture"])
            self.assertEqual(r.step()["status"], "rejected")
            record = read_records(root)[0]
            self.assertEqual(record["response"]["raw"], "[REDACTED]")
            self.assertEqual(record["response"]["error"], "[REDACTED]")
