"""Persistence tests use synthetic synthesis proposals, never a gardener or model."""
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mira import Knowledge, LiveStore, Memory, RecoveryRequired, Unit, Relationship, ValidationError
from mira.format import base36, digest, dumps, loads
from mira.live import revision
from mira.store import ConflictError


def metadata(kind="research", sources=None):
    return {"kind": kind, "node_id": "q1", "source_memories": sources or [], "synthesized_by": None}


def synthesis(memories, equations, ledger):
    identity = "s" + base36(ledger["s"])
    ledger["s"] += 1
    sources = [m for m in memories if m.id in {"r1", "r2"}]
    for m in sources:
        m.metadata["synthesized_by"] = identity
        m.revision += 1
    output = Memory(identity, "Combined", "Synthetic integration.", metadata=metadata("synthesis", [m.id for m in sources]))
    anchor = output.allocate("f")
    output.units.append(Unit(anchor, "Combined finding", {"Kind": "synthesis", "Evidence status": "unverified",
        "Proposition": "Two synthetic observations combine.", "Explanation": "Fixture only.", "Provenance": "Synthetic inputs."}))
    output.relationships = [Relationship(anchor, "SYNTHESIZES", m.id + "#f1") for m in sources]
    memories.append(output)
    return identity


def crash_synthesis(root, point):
    k = Knowledge(store=LiveStore(root))
    def fault(stage):
        if stage == point:
            os._exit(73)
    k.transaction(synthesis, files={"research/state.json": dumps({"revision": 2, "frontier": 1})},
                  operation_type="synthesis", context={"node_id": "q1", "cycle_id": "fixture", "input_ids": ["r1", "r2"], "output_ids": ["s1"]}, fault=fault)


def crash_repair(root, operation, point):
    def fault(stage):
        if stage == point:
            os._exit(74)
    LiveStore(root).repair(operation, apply=True, fault=fault)


def concurrent_create(root):
    Knowledge(store=LiveStore(root)).create_memory("Concurrent", "Writer fixture.")


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = LiveStore(self.root)
        self.k = Knowledge(store=self.store)

    def seed(self):
        for n in range(2):
            m = self.k.create_memory("Observation", "Synthetic observation.", metadata=metadata())
            self.k.add_finding(m.id, "Observation", "Synthetic value.", "Fixture explanation.", "Fixture author.")
        self.k.transaction(lambda *args: None, files={"research/state.json": dumps({"revision": 1, "frontier": 2})})
        self.k.rebuild()

    def crash(self, point):
        p = multiprocessing.get_context("fork").Process(target=crash_synthesis, args=(str(self.root), point))
        p.start()
        p.join(10)
        self.assertFalse(p.is_alive())
        self.assertEqual(p.exitcode, 73)

    def pending(self):
        report = self.store.recovery_status()
        self.assertTrue(report["blocked"])
        return report["operations"][0]

    def verify_synthesis(self):
        self.assertEqual(self.k.validate()["documents"], 3)
        self.assertEqual(self.k.document("s1").metadata["source_memories"], ["r1", "r2"])
        for identity in ("r1", "r2"):
            self.assertEqual(self.k.document(identity).metadata["synthesized_by"], "s1")
        self.assertEqual(loads((self.root / "research/state.json").read_text())["frontier"], 1)
        self.assertEqual(self.k.directory.integrity()["integrity"], "ok")
        self.assertEqual(self.k.create_memory("Next", "No ID reuse.", kind="synthesis").id, "s2")
        self.assertFalse((self.root / "CURRENT").exists())
        self.assertFalse((self.root / "generations").exists())

    def test_empty_and_existing_api_equations_retrieval(self):
        self.assertEqual(self.k.validate()["documents"], 0)
        m = self.k.create_memory("Trial", "Test document.")
        f = self.k.add_finding(m.id, "Claim", "A value.", "Scope.", "Source.")
        equation = self.k.add_equation(m.id, "Identity", "x=x", {"x": "a value"}, [], "Fixture.")
        other = self.k.create_memory("Other", "Equation reuse.")
        self.k.reference_equation(other.id, equation, "Reused")
        self.assertEqual(self.k.retrieve(equation)["expression"], "x=x")
        self.assertEqual(self.k.retrieve(f)["fields"]["Proposition"], "A value.")
        self.assertTrue(self.k.search("value"))
        (self.root / "index.sqlite3").unlink()
        self.assertEqual(self.k.directory.integrity()["integrity"], "ok")
        self.assertRaises(ValueError, Knowledge, self.root)

    def test_synthesis_process_crashes_and_explicit_idempotent_repair(self):
        points = ["prepared", "replaced:memories/s1.md", "replaced:memories/r1.md",
                  "progress:memories/r2.md", "replaced:research/state.json", "before_commit", "committed"]
        for point in points:
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                # Use a separate complete fixture per interruption.
                self.root = Path(directory)
                self.store = LiveStore(self.root)
                self.k = Knowledge(store=self.store)
                self.seed()
                self.crash(point)
                self.store = LiveStore(self.root)  # startup does not repair
                self.k = Knowledge(store=self.store)
                if point != "committed":
                    report = self.pending()
                    self.assertEqual(set(report["completed"]) | set(report["remaining"]),
                                     {"memories/s1.md", "memories/r1.md", "memories/r2.md", "identity.json", "research/state.json"})
                    self.assertEqual(report["assessment"], "complete" if point in {"replaced:research/state.json", "before_commit"} else "safely_finishable")
                    self.assertEqual(report["safely_cancellable"], point == "prepared")
                    # Canonical access and stale-index retrieval both fail closed.
                    self.assertRaises(RecoveryRequired, self.k.document, "r1")
                    self.assertRaises(RecoveryRequired, self.k.search, "value")
                    class ForbiddenEmbedding:
                        identity = "must-not-run-during-recovery"

                        def embed(self, *args, **kwargs):
                            raise AssertionError("embedding ran before recovery gate")
                    blocked_vectors = Knowledge(store=self.store, embedding=ForbiddenEmbedding())
                    self.assertRaises(RecoveryRequired, blocked_vectors.search, "value", mode="vector")
                    before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
                    self.assertFalse(self.store.repair(report["id"])["applied"])
                    self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
                    self.assertTrue(self.store.repair(report["id"], apply=True)["applied"])
                    self.assertEqual(self.store.repair(report["id"], apply=True)["assessment"], "committed")
                self.assertFalse(self.store.recovery_status()["blocked"])
                self.verify_synthesis()

    def test_interrupted_repair_and_progress_is_not_authority(self):
        self.seed()
        self.crash("replaced:memories/r1.md")
        report = self.pending()
        manifest = self.root / "journal" / (report["id"] + ".json")
        data = loads(manifest.read_text())
        # Deliberately mark an unapplied file as completed: hashes still win.
        for entry in data["files"]:
            entry["completed"] = True
        manifest.write_text(dumps(data))
        p = multiprocessing.get_context("fork").Process(target=crash_repair, args=(str(self.root), report["id"], "replaced:memories/r2.md"))
        p.start(); p.join(10)
        self.assertEqual(p.exitcode, 74)
        self.assertIn("memories/r2.md", self.pending()["completed"])
        self.store.repair(report["id"], apply=True)
        self.verify_synthesis()

    def test_unknown_bytes_missing_payload_and_unrelated_changes_are_ambiguous(self):
        for damage in ("input", "payload", "unrelated"):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory); self.store = LiveStore(self.root); self.k = Knowledge(store=self.store)
                self.seed(); self.crash("replaced:memories/s1.md")
                report = self.pending()
                if damage == "input":
                    path = self.root / "memories/r1.md"; path.write_text(path.read_text() + "\nAmbiguous research\n")
                elif damage == "payload":
                    entry = next(e for e in report["files"] if e["path"] == "memories/r1.md")
                    (self.root / entry["payload"]).unlink()
                else:
                    path = self.root / "events/external.json"; path.write_text(dumps({"external": True}))
                before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
                self.assertEqual(self.pending()["assessment"], "ambiguous")
                self.assertRaises(ValidationError, self.store.repair, report["id"], apply=True)
                self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_unpublished_payloads_block_and_are_preserved(self):
        self.seed(); self.crash("staged")
        report = self.store.recovery_status()
        self.assertTrue(report["blocked"])
        self.assertEqual(len(report["unpublished"]), 1)
        self.assertRaises(RecoveryRequired, self.k.validate)
        self.assertEqual(self.k.store.recovery_status()["unpublished"], report["unpublished"])

    def test_changed_files_only_and_events_immutable(self):
        self.seed()
        before = (self.root / "memories/r2.md").stat().st_ino
        draft = self.k.document("r1"); draft.title = "Updated"
        self.k.save_memory(draft, expected_revision=draft.revision)
        self.assertEqual((self.root / "memories/r2.md").stat().st_ino, before)
        manifests = sorted(self.root.glob("journal/*.json"), key=lambda p: loads(p.read_text())["sequence"])
        last = loads(manifests[-1].read_text())
        self.assertEqual([e["path"] for e in last["files"]], ["memories/r1.md"])
        self.k.transaction(lambda *args: None, files={"events/terminal.json": dumps({"root": "Question", "pending": []})})
        self.assertRaises(ValidationError, self.k.transaction, lambda *args: None,
                          files={"events/terminal.json": dumps({"root": "Changed"})})

    def test_identity_and_revision_guards_and_atomic_rejection(self):
        self.seed()
        old = self.k.document("r1")
        self.k.add_question("r1", "Question", "What next?")
        self.assertRaises(ConflictError, self.k.save_memory, old, expected_revision=old.revision)
        def invalid(memories, equations, ledger):
            memories[0].units[0].fields["Proposition"] = "Changed identity."
        self.assertRaises(ValidationError, self.k.transaction, invalid)
        def reuse(memories, equations, ledger):
            ledger["r"] = 1
        self.assertRaises(ValidationError, self.k.transaction, reuse)
        self.assertFalse(self.store.recovery_status()["blocked"])
        self.assertEqual(self.k.document("r1").units[0].fields["Proposition"], "Synthetic value.")

    def test_lineage_rejects_single_input_missing_sources_and_cycles(self):
        self.seed()
        def invalid(memories, equations, ledger):
            synthesis(memories, equations, ledger)
            memories[-1].metadata["source_memories"] = ["r1"]
        self.assertRaises(ValidationError, self.k.transaction, invalid)
        def dangling(memories, equations, ledger):
            memories[0].metadata["synthesized_by"] = "s99"
            memories[0].revision += 1
        self.assertRaises(ValidationError, self.k.transaction, dangling)
        def cycle(memories, equations, ledger):
            for source, consumer in zip(memories, ["s1", "s2"]):
                source.metadata["synthesized_by"] = consumer
                source.revision += 1
            a = Memory("s1", "Cycle A", "Invalid cycle.", metadata=metadata("synthesis", ["s2", "r1"]))
            b = Memory("s2", "Cycle B", "Invalid cycle.", metadata=metadata("synthesis", ["s1", "r2"]))
            a.metadata["synthesized_by"] = "s2"
            b.metadata["synthesized_by"] = "s1"
            memories.extend([a, b]); ledger["s"] = 3
        with self.assertRaisesRegex(ValidationError, "cyclic synthesis lineage"):
            self.k.transaction(cycle)
        self.assertEqual(self.k.validate()["documents"], 2)

    def test_symlinks_unsafe_paths_corrupt_journals_and_committed_edits(self):
        self.seed()
        self.assertRaises(ValidationError, self.k.transaction, lambda *args: None, files={"../escape.json": "{}"})
        target = self.root / "research/results/unsafe.json"
        target.symlink_to(self.root / "identity.json")
        self.assertTrue(self.store.recovery_status()["blocked"])
        self.assertRaises(ValidationError, self.k.validate)
        target.unlink()
        manifest = next(self.root.glob("journal/*.json"))
        original = manifest.read_bytes(); manifest.write_text("{broken")
        self.assertEqual(self.store.recovery_status()["assessment"], "ambiguous")
        manifest.write_bytes(original)
        path = self.root / "memories/r1.md"; path.write_text(path.read_text() + "\n")
        self.assertTrue(self.store.recovery_status()["blocked"])
        self.assertRaises(ValidationError, self.k.validate)

    def test_concurrent_writers_allocate_unique_ids(self):
        jobs = [multiprocessing.get_context("fork").Process(target=concurrent_create, args=(str(self.root),)) for _ in range(4)]
        for p in jobs: p.start()
        for p in jobs:
            p.join(10); self.assertEqual(p.exitcode, 0)
        self.assertEqual({r["id"] for r in self.k.summaries()}, {"r1", "r2", "r3", "r4"})

    def test_cli_dry_run_and_apply(self):
        self.seed(); self.crash("prepared"); operation = self.pending()["id"]
        def cli(*args):
            return loads(subprocess.check_output([sys.executable, "-m", "mira", "--live", "--root", str(self.root), "recovery", *args], text=True))
        self.assertTrue(cli("inspect")["blocked"])
        self.assertTrue(cli("validate")["blocked"])
        self.assertFalse(cli("repair", operation)["applied"])
        self.assertTrue(cli("repair", operation, "--apply")["applied"])
        self.assertFalse(cli()["blocked"])

    def test_batch_revision_precondition_and_invalid_context_leave_no_artifacts(self):
        with self.store.lock():
            token = self.store.read()[0]
        self.k.create_memory("New", "Concurrent change.")
        self.assertRaises(ConflictError, self.k.transaction, lambda *args: None,
                          files={"research/state.json": "{}"}, expected_revision=token)
        self.assertRaises(ValidationError, self.k.transaction, lambda *args: None, operation_type="")
        self.assertFalse((self.root / "research/state.json").exists())
        self.assertFalse(self.store.recovery_status()["blocked"])

    def test_invalid_staged_reference_is_ambiguous_even_with_matching_hashes(self):
        self.seed(); self.crash("prepared")
        report = self.pending()
        path = self.root / "journal" / (report["id"] + ".json")
        manifest = loads(path.read_text())
        prospective = self.store._files()
        for entry in manifest["files"]:
            payload = self.root / entry["payload"]
            text = payload.read_text()
            if entry["path"] == "memories/s1.md":
                text = text.replace('"r1#f1"', '"r99#f1"')
                payload.write_text(text)
                entry["after"] = digest(text)
            prospective[entry["path"]] = text
        manifest["after_revision"] = revision(prospective)
        path.write_text(dumps(manifest))
        self.assertEqual(self.pending()["assessment"], "ambiguous")
        self.assertRaises(ValidationError, self.store.repair, report["id"], apply=True)

    def test_conflicting_and_unsafe_journals_are_not_repaired(self):
        self.seed(); self.crash("prepared")
        report = self.pending()
        path = self.root / "journal" / (report["id"] + ".json")
        manifest = loads(path.read_text())
        original = path.read_text()
        manifest["files"][0]["path"] = "../escape.md"
        path.write_text(dumps(manifest))
        self.assertEqual(self.store.recovery_status()["assessment"], "ambiguous")
        self.assertRaises(ValidationError, self.store.repair, report["id"], apply=True)
        path.write_text(original)
        duplicate = loads(original)
        duplicate["id"] = "0" * 32
        for i, entry in enumerate(duplicate["files"]):
            entry["payload"] = f"journal/{duplicate['id']}/{i}.txt"
        (self.root / "journal" / (duplicate["id"] + ".json")).write_text(dumps(duplicate))
        self.assertEqual(self.store.recovery_status()["assessment"], "ambiguous")

    def test_completed_files_do_not_need_payloads_to_finalize(self):
        self.seed(); self.crash("before_commit")
        report = self.pending()
        for entry in report["files"]:
            (self.root / entry["payload"]).unlink()
        self.assertEqual(self.pending()["assessment"], "complete")
        self.store.repair(report["id"], apply=True)
        self.verify_synthesis()


if __name__ == "__main__":
    unittest.main()
