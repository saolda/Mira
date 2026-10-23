from copy import deepcopy
from dataclasses import asdict
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from mira import ConflictError, Knowledge, ValidationError
from mira.demo import populate
from mira.embeddings import TestEmbedding
from mira.format import Equation, Relationship, Unit, loads, parse, render, validate_corpus


def crash_save(root, stage):
    k = Knowledge(root)
    memory = k.document("r1")
    memory.title = "Published after restart"
    def crash(point):
        if point == stage:
            os._exit(23)
    k.save_memory(memory, expected_revision=memory.revision, fault=crash)



def crash_equation(root, stage):
    k = Knowledge(root)
    original = k.store.publish
    def publish(documents, equations, ledger, expected, fault=None):
        def crash(point):
            if point == stage:
                os._exit(23)
        return original(documents, equations, ledger, expected, crash)
    k.store.publish = publish
    k.add_equation("r1", "Cooling", "dT/dt=-kT", {"T": "temperature", "k": "rate", "t": "time"}, ["Uniform temperature"], "Synthetic fixture.")


def add_concurrently(root, number):
    k = Knowledge(root)
    k.add_question("r1", f"Question {number}", f"What about case {number}?")


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.k = Knowledge(self.temp.name, TestEmbedding())
        self.d = self.k.create_memory("Experiment", "Heat transfer experiment.")
        self.f = self.k.add_finding(self.d.id, "Thermal energy", "Heat flows to cooler surroundings.", "Under matching conditions.", "Authored fixture.")

    def test_round_trip_and_multiline_fields(self):
        m = self.k.document("r1")
        self.assertEqual(parse(render(m)), m)
        self.k.add_finding("r1", "Multiline", "A short claim.", "First paragraph.\n\nSecond paragraph with `[#f99]` literal.\n\n```text\n[#f88] example\n## Relationships\n```", "A fixture.")
        self.assertEqual(parse(self.k.retrieve("r1")), self.k.document("r1"))

    def test_duplicate_anchor(self):
        m = self.k.document("r1")
        m.units.append(deepcopy(m.units[0]))
        with self.assertRaisesRegex(ValidationError, "duplicate anchor"):
            render(m)

    def test_malformed_anchor(self):
        with self.assertRaises(ValidationError):
            parse(self.k.retrieve("r1").replace("[#f1]", "[#s1]"))

    def test_malformed_json_and_duplicate_keys(self):
        with self.assertRaises(ValidationError):
            parse(self.k.retrieve("r1").replace('"version": 1', '"version": nope', 1))
        with self.assertRaises(ValidationError):
            loads('{"a":1,"a":2}')

    def test_terminal_relationships_required(self):
        with self.assertRaises(ValidationError):
            parse(self.k.retrieve("r1") + "unexpected text\n")

    def test_code_and_quote_anchors_are_not_units(self):
        self.k.add_question("r1", "Code", "Example:\n\n> [#f9] quoted\n\n    [#f8] indented\n\n`[#f7]` inline")
        self.assertEqual(len(self.k.document("r1").units), 2)

    def test_anchor_in_plain_prose_rejected(self):
        with self.assertRaises(ValidationError):
            self.k.add_question("r1", "Bad", "Unescaped [#f9] marker")

    def test_missing_target(self):
        current = self.k.store.current()
        with self.assertRaisesRegex(ValidationError, "missing target"):
            self.k.add_relationship("r1", "f1", "CITES", "rzz#f1")
        self.assertEqual(self.k.store.current(), current)

    def test_missing_source(self):
        with self.assertRaisesRegex(ValidationError, "source"):
            self.k.add_relationship("r1", "f9", "CITES", "https://example.org")

    def test_unsupported_type_and_status(self):
        for edge_type, status in [("SIMILAR", "proposed"), ("CITES", "verified")]:
            with self.subTest(edge_type=edge_type, status=status), self.assertRaises(ValidationError):
                self.k.add_relationship("r1", "f1", edge_type, "https://example.org", status=status)

    def test_external_cites_and_doi(self):
        self.k.add_relationship("r1", "f1", "CITES", "https://example.org", status="unverified")
        self.k.add_relationship("r1", "f1", "CITES", "doi:10.1234/example", status="unverified")
        self.assertEqual(len(self.k.relationships(self.f)), 2)

    def test_endpoint_restrictions(self):
        with self.assertRaisesRegex(ValidationError, "external targets"):
            self.k.add_relationship("r1", "f1", "SUPPORTS", "https://example.org")
        self.k.add_question("r1", "Question", "Why?")
        with self.assertRaisesRegex(ValidationError, "finding endpoints"):
            self.k.add_relationship("r1", "q1", "SUPPORTS", self.f)

    def test_synthesis_direction(self):
        self.k.add_finding("r1", "Second", "Another claim.", "A scope.", "A fixture.")
        with self.assertRaisesRegex(ValidationError, "synthesis finding"):
            self.k.add_relationship("r1", "f1", "SYNTHESIZES", "r1#f2")

    def test_duplicate_relationships_even_status_differs(self):
        self.k.add_relationship("r1", "f1", "CITES", "https://example.org")
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            self.k.add_relationship("r1", "f1", "CITES", "https://example.org", status="reviewed")

    def test_symmetric_related_duplicate(self):
        self.k.add_finding("r1", "Second", "Another claim.", "A scope.", "A fixture.")
        self.k.add_relationship("r1", "f1", "RELATED_TO", "r1#f2")
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            self.k.add_relationship("r1", "f2", "RELATED_TO", self.f)

    def test_equation_creation_reuse_and_complete_retrieval(self):
        eq = self.k.add_equation("r1", "Cooling", "dT/dt=-kT", {"T": "temperature", "k": "rate", "t": "time"}, ["Uniform temperature"], "Fixture.")
        s = self.k.create_memory("Synthesis", "A model summary.", kind="synthesis")
        ref = self.k.reference_equation(s.id, eq, "Same model")
        self.assertEqual(self.k.retrieve(ref)["definition"]["id"], eq)
        self.assertEqual(self.k.retrieve(eq)["origin"], "r1")
        self.assertIn("# Synthesis", self.k.containing_document(ref))

    def test_equation_invalid_and_missing(self):
        with self.assertRaises(ValidationError):
            self.k.add_equation("r1", "Bad", "x", {}, [], "Fixture")
        with self.assertRaisesRegex(ValidationError, "missing equation"):
            self.k.reference_equation("r1", "e_r1_99", "Missing")

    def test_stable_ids_title_change_and_cas(self):
        draft = self.k.document("r1")
        old = draft.revision
        draft.title = "Renamed"
        saved = self.k.save_memory(draft, expected_revision=old)
        self.assertEqual(saved.revision, old + 1)
        self.assertEqual(self.k.retrieve(self.f)["label"], "Thermal energy")
        with self.assertRaises(ConflictError):
            self.k.save_memory(draft, expected_revision=old)

    def test_unit_edits_deletes_and_allocator_regression_rejected(self):
        for change in (lambda m: m.units.clear(), lambda m: m.units[0].fields.update(Proposition="Changed"), lambda m: m.next_ids.update(f=1)):
            draft = self.k.document("r1")
            change(draft)
            with self.assertRaises(ValidationError):
                self.k.save_memory(draft, expected_revision=draft.revision)

    def test_duplicate_document_identity(self):
        m = self.k.document("r1")
        with self.assertRaisesRegex(ValidationError, "duplicate document"):
            validate_corpus([m, m], [])

    def test_index_exact_fulltext_vector_and_model_metadata(self):
        self.assertEqual(self.k.directory.exact(self.f)["document"], "r1")
        self.assertEqual(self.k.search("cooler surroundings")[0]["id"], self.f)
        self.assertEqual(self.k.search("cooler surroundings", mode="vector")[0]["id"], self.f)
        self.assertEqual(self.k.rebuild()["model"], TestEmbedding.identity)
        self.assertEqual(self.k.directory.integrity()["integrity"], "ok")

    def test_model_change_rebuild_and_invalid_vectors(self):
        self.k.rebuild()
        other = Knowledge(self.temp.name)
        self.assertEqual(other.rebuild()["model"], "none")
        self.assertEqual(len(other.search("Heat")), 2)
        with self.assertRaises(ValidationError):
            other.search("heat", mode="vector")
        class Bad:
            identity = "bad"
            def embed(self, texts, **kwargs):
                return [[float("nan")]] * len(texts)
        with self.assertRaises(ValidationError):
            Knowledge(self.temp.name, Bad()).rebuild()

    def test_derived_database_deletion_and_rebuild_equivalent(self):
        before = self.k.search("heat", mode="vector")
        self.k.directory.path.unlink()
        self.assertEqual(self.k.search("heat", mode="vector"), before)

    def test_incoming_outgoing_filter_before_limit(self):
        self.k.add_finding("r1", "Second", "Another claim.", "A scope.", "A fixture.")
        self.k.add_relationship("r1", "f1", "SUPPORTS", "r1#f2", status="rejected")
        self.k.add_relationship("r1", "f2", "CITES", self.f, status="reviewed")
        self.assertEqual(self.k.relationships(self.f), [])
        self.assertEqual(len(self.k.relationships(self.f, statuses=("rejected",))), 1)
        self.assertEqual(self.k.relationships(self.f, direction="incoming", limit=1)[0]["source"], "r1#f2")

    def test_stale_index_never_returned(self):
        self.k.rebuild()
        q = self.k.add_question("r1", "New", "What happens next?")
        self.assertEqual(self.k.directory.exact(q)["type"], "question")

    def test_external_document_modification_fails_closed(self):
        self.k.rebuild()
        p = Path(self.temp.name) / "generations" / self.k.store.current() / "documents/r1.md"
        p.write_text(p.read_text().replace("cooler", "warmer"))
        with self.assertRaisesRegex(ValidationError, "changed externally"):
            self.k.search("heat")

    def test_index_integrity_detects_tampering(self):
        self.k.rebuild()
        with sqlite3.connect(self.k.directory.path) as db:
            db.execute("DELETE FROM edges")
            db.execute("UPDATE units SET label='tampered' WHERE id=?", (self.f,))
        with self.assertRaisesRegex(ValidationError, "units differ"):
            self.k.directory.integrity()

    def test_real_process_crash_before_publication(self):
        before = self.k.store.current()
        context = multiprocessing.get_context("fork")
        process = context.Process(target=crash_save, args=(self.temp.name, "staged"))
        process.start(); process.join(10)
        self.assertEqual(process.exitcode, 23)
        reopened = Knowledge(self.temp.name)
        self.assertEqual(reopened.store.current(), before)
        self.assertEqual(reopened.document("r1").title, "Experiment")
        self.assertEqual(len(reopened.store.recovery_status()["unpublished"]), 1)
        reopened.add_question("r1", "Recovery", "Can writes resume?")

    def test_real_process_crash_after_publication(self):
        self.k.rebuild()
        context = multiprocessing.get_context("fork")
        process = context.Process(target=crash_save, args=(self.temp.name, "published"))
        process.start(); process.join(10)
        self.assertEqual(process.exitcode, 23)
        reopened = Knowledge(self.temp.name)
        self.assertEqual(reopened.document("r1").title, "Published after restart")
        self.assertEqual(reopened.directory.exact("r1")["label"], "Published after restart")

    def test_multifile_equation_publication_is_all_or_nothing(self):
        context = multiprocessing.get_context("fork")
        for stage in ("staged", "published"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as root:
                k = Knowledge(root)
                k.create_memory("Atomic equation", "Synthetic model fixture.")
                process = context.Process(target=crash_equation, args=(root, stage))
                process.start(); process.join(10)
                self.assertEqual(process.exitcode, 23)
                reopened = Knowledge(root)
                counts = reopened.validate()
                aliases = [u for u in reopened.document("r1").units if u.kind == "equation"]
                self.assertEqual(counts["equations"], 1 if stage == "published" else 0)
                self.assertEqual(len(aliases), counts["equations"])
                if aliases:
                    self.assertEqual(reopened.retrieve("r1#e1")["definition"]["id"], "e_r1_1")
                self.assertEqual(reopened.directory.integrity()["integrity"], "ok")

    def test_document_metadata_and_vector_integrity(self):
        self.k.rebuild()
        with sqlite3.connect(self.k.directory.path) as db:
            db.execute("UPDATE documents SET summary='tampered'")
        with self.assertRaisesRegex(ValidationError, "metadata differs"):
            self.k.directory.integrity()
        self.k.rebuild()
        with sqlite3.connect(self.k.directory.path) as db:
            db.execute("UPDATE units SET vector='[1.0]'")
        with self.assertRaisesRegex(ValidationError, "dimension mismatch"):
            self.k.directory.integrity()

    def test_concurrent_processes_allocate_unique_ids(self):
        context = multiprocessing.get_context("fork")
        processes = [context.Process(target=add_concurrently, args=(self.temp.name, n)) for n in range(4)]
        for p in processes: p.start()
        for p in processes:
            p.join(10)
            self.assertEqual(p.exitcode, 0)
        questions = [u.anchor for u in self.k.document("r1").units if u.kind == "question"]
        self.assertEqual(questions, ["q1", "q2", "q3", "q4"])

    def test_empty_store(self):
        with tempfile.TemporaryDirectory() as p:
            k = Knowledge(p, TestEmbedding())
            self.assertEqual(k.rebuild()["records"], 0)
            self.assertEqual(k.search("anything", mode="vector"), [])
            self.assertEqual(k.validate()["documents"], 0)

    def test_synthetic_corpus(self):
        with tempfile.TemporaryDirectory() as p:
            k = Knowledge(p, TestEmbedding())
            refs = populate(k)
            self.assertEqual(k.rebuild()["documents"], 3)
            self.assertEqual(len(k.relationships(refs["finding"], direction="incoming")), 1)
            self.assertEqual(k.validate()["equations"], 1)
            self.assertEqual(len(k.summaries()), 3)
            self.assertEqual(k.directory.integrity()["integrity"], "ok")


if __name__ == "__main__":
    unittest.main()
