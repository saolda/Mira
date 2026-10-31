"""Single active corpus resets, legacy relocation and restricted deletion."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mira.decisions import ScriptedLLM
from mira.experiments import Experiments, file_hashes
from mira.format import dumps, loads, parse, render
from mira.interactions import ExecutionLog, read_records
from mira.live import RecoveryRequired
from mira.research import Research
from mira.search import FixtureSearch
from test_r1_planning import plan
from test_research import evidence, draft


class SingleCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'memory'; self.catalog = Experiments(self.home)

    def make(self, name='first', root=None, responses=None):
        root = root or self.catalog.create(name)
        r = Research(root, ScriptedLLM(responses or [plan(['heat flux']),
            {'summary': 'Synthetic source.', 'results': [draft()]}]),
            {'fixture': FixtureSearch([evidence()])})
        r.initialize('Fictional thermal question?', ['fixture'], context_budget=50000)
        return r

    def legacy(self, name='old'):
        root = self.home / 'research' / name; root.mkdir(parents=True)
        r = self.make(root=root)
        (root / 'supervisor.log').write_bytes(b'original\r\nlog\x00bytes')
        return r

    def test_new_experiment_requires_explicit_reset_and_preserves_private_files_logs(self):
        r = self.make(); r.run(3)
        (self.home / 'questions').mkdir(); question = self.home / 'questions/private.md'; question.write_text('Private question')
        unrelated = self.home / 'notes.txt'; unrelated.write_text('Keep unrelated notes')
        original_logs = file_hashes(self.catalog.log_home)
        self.assertEqual(self.catalog.select(), self.home)
        self.assertEqual(self.catalog.select('first'), self.home)
        self.assertFalse((self.home / 'research/first').exists())
        self.assertRaises(ValueError, self.catalog.create, 'second')
        self.assertEqual(self.catalog.create('second', reset=True), self.home)
        new = Research(self.home, ScriptedLLM([]), {})
        state = new.initialize('New question?', ['fixture'], context_budget=50000)
        self.assertEqual(state['nodes']['q1']['memory_ids'], [])
        self.assertEqual(loads((self.home / 'identity.json').read_text()), {'r': 1, 's': 1})
        self.assertEqual(question.read_text(), 'Private question'); self.assertEqual(unrelated.read_text(), 'Keep unrelated notes')
        self.assertEqual(file_hashes(self.catalog.log_home), original_logs)
        self.assertEqual(list((self.home / 'memories').glob('*.md')), [])
        self.assertEqual(read_records(self.home), [])

    def test_normal_continuation_never_resets(self):
        r = self.make(); r.step(); r.step()
        before = file_hashes(self.home)
        self.assertEqual(self.catalog.select('first'), self.home)
        resumed = Research(self.home, r.llm, r.adapters)
        self.assertEqual(file_hashes(self.home), before)
        self.assertEqual(resumed.step()['action'], 'R3')
        self.assertTrue((self.home / 'memories/r1.md').exists())

    def test_new_experiment_resets_legacy_explicit_root_metadata(self):
        self.make()
        (self.home / 'experiment.json').write_text(dumps({'version': 1, 'created_at': 'legacy', 'retention': 'retain'}))
        self.assertEqual(self.catalog.select(), self.home)
        self.catalog.create('replacement', reset=True)
        self.assertEqual(self.catalog.active_name(), 'replacement')

    def test_reset_refuses_runner_writer_pending_journal_and_unknown_interaction(self):
        r = self.make()
        with r.execution():
            with self.assertRaises(BlockingIOError): self.catalog.create('second', reset=True)
        with r.store.lock():
            with self.assertRaises(BlockingIOError): self.catalog.create('second', reset=True)
        def fault(point):
            if point == 'prepared': raise RuntimeError('crash')
        with self.assertRaises(RuntimeError): r.step(fault=fault)
        before = file_hashes(self.home)
        with self.assertRaises(RecoveryRequired): self.catalog.create('second', reset=True)
        self.assertEqual(file_hashes(self.home), before)
        operation = r.store.recovery_status()['operations'][0]['id']; r.store.repair(operation, apply=True)
        with r.store.lock(): r.trace.start({'action': 'R1'}, dumps({'messages': []}), {})
        before = file_hashes(self.home)
        with self.assertRaisesRegex(ValueError, 'unresolved model'): self.catalog.create('second', reset=True)
        self.assertEqual(file_hashes(self.home), before)

    def test_reset_and_legacy_cleanup_refuse_uncertain_provider_submissions(self):
        r = self.make(); r.step()
        with patch.object(r.adapters['fixture'], 'search', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): r.step()
        before = file_hashes(self.home)
        with self.assertRaisesRegex(ValueError, 'uncertain provider'): self.catalog.create('second', reset=True)
        after = file_hashes(self.home)
        self.assertEqual({p: after[p] for p in before}, before)

    def test_reset_resumes_after_partial_deletion_and_gates_continuation(self):
        r = self.make(); r.step()
        original = Path.unlink; interrupted = False
        def fail_once(path, *args, **kwargs):
            nonlocal interrupted
            if path.name == 'identity.json' and not interrupted:
                interrupted = True; raise OSError('simulated reset crash')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_once):
            with self.assertRaisesRegex(OSError, 'reset crash'): self.catalog.create('second', reset=True)
        self.assertTrue((self.home / '.reset.json').exists())
        with self.assertRaises(ValueError): self.catalog.select()
        with self.assertRaises(RecoveryRequired): r.inspect()
        self.catalog.create('second', reset=True)
        self.assertFalse((self.home / '.reset.json').exists())
        self.assertEqual(read_records(self.home), [])
        self.assertEqual(Research(self.home, ScriptedLLM([]), {}).initialize('New?', ['fixture'])['research_cycles'], 0)

    def test_reset_does_not_follow_symlinks_or_delete_unrelated_siblings(self):
        r = self.make()
        outside = Path(self.tmp.name) / 'outside'; outside.mkdir(); keep = outside / 'keep'; keep.write_text('Keep')
        (self.home / 'memories/r1.md').symlink_to(keep)
        with self.assertRaises(ValueError): self.catalog.create('second', reset=True)
        self.assertEqual(keep.read_text(), 'Keep')
        for name in ('../outside', '/tmp', 'bad/name'):
            with self.assertRaises(ValueError): self.catalog.create(name, reset=True)

    def test_legacy_cleanup_checks_locks_and_recovery_and_moves_diagnostics_without_archives(self):
        old = self.legacy(); root = old.store.root
        before = file_hashes(root)
        dry = self.catalog.cleanup(['old'])
        self.assertEqual(dry['deleted'], []); self.assertTrue(dry['experiments'][0]['would_delete'])
        self.assertEqual(file_hashes(root), before)
        with old.execution():
            result = self.catalog.cleanup(['old'], apply=True)
            self.assertEqual(result['deleted'], []); self.assertEqual(result['experiments'][0]['status'], 'active')
        with old.store.lock(): old.trace.start({'action': 'R1'}, dumps({'messages': []}), {})
        result = self.catalog.cleanup(['old'], apply=True)
        self.assertEqual(result['deleted'], []); self.assertEqual(result['experiments'][0]['status'], 'recovery_blocked')
        old.acknowledge_interrupted()
        self.assertEqual(self.catalog.cleanup(['old'], apply=True)['deleted'], ['old'])
        self.assertFalse(root.exists())
        self.assertEqual((self.catalog.log_home / 'legacy/old/supervisor.log').read_bytes(), b'original\r\nlog\x00bytes')
        self.assertEqual(list(self.catalog.log_home.rglob('r*.md')), [])
        self.assertEqual(list(self.catalog.log_home.rglob('state.json')), [])

    def test_legacy_activation_preserves_memory_journals_sources_and_ids(self):
        r = self.legacy(); r.run(3)
        original = {p: sha for p, sha in file_hashes(r.store.root).items() if p.startswith(
            ('memories/', 'journal/', 'research/', 'events/', 'interactions/', 'retrieval_calls/', 'retrieved/', 'glossary/')) or p == 'identity.json'}
        self.assertEqual(self.catalog.activate_legacy('old'), self.home)
        self.assertFalse((self.home / 'research/old').exists())
        after = file_hashes(self.home)
        self.assertEqual({p: after[p] for p in original}, original)
        self.assertEqual(self.catalog.select(), self.home)
        self.assertEqual(Research(self.home, ScriptedLLM([]), {}).knowledge.validate()['documents'], 1)
        self.assertEqual(self.catalog.cleanup(['old'], apply=True)['deleted'], [])

    def test_log_relocation_is_byte_preserving_and_collision_safe(self):
        source = self.home / 'run-logs'; source.mkdir(parents=True)
        (source / 'old.jsonl').write_bytes(b'{"kind":"old"}\r\n')
        self.catalog.move_run_logs()
        self.assertFalse(source.exists())
        self.assertEqual((self.catalog.log_home / 'old.jsonl').read_bytes(), b'{"kind":"old"}\r\n')
        source.mkdir(); (source / 'old.jsonl').write_bytes(b'conflicting')
        with self.assertRaisesRegex(ValueError, 'destination'): self.catalog.move_run_logs()
        self.assertEqual((source / 'old.jsonl').read_bytes(), b'conflicting')

    def test_legacy_activation_resumes_after_a_partial_move(self):
        r = self.legacy(); r.run(3)
        expected = (r.store.root / 'identity.json').read_bytes()
        import os
        original = os.rename
        def interrupted(source, target):
            if Path(source).name == 'identity.json': raise OSError('migration interrupted')
            return original(source, target)
        with patch('mira.experiments.os.rename', interrupted):
            with self.assertRaisesRegex(OSError, 'migration interrupted'): self.catalog.activate_legacy('old')
        self.assertTrue((self.home / '.transition.json').exists())
        with self.assertRaises(ValueError): self.catalog.select()
        self.catalog.activate_legacy('old')
        self.assertEqual((self.home / 'identity.json').read_bytes(), expected)
        self.assertEqual(Research(self.home, ScriptedLLM([]), {}).knowledge.validate()['documents'], 1)
