"""Lifecycle, full-context capacity, independent queues and durable R5 recovery."""
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mira import branching, decisions, r3, research_tree as tree, research_tree_v1 as legacy
from mira.decisions import ScriptedLLM
from mira.format import dumps, loads, parse, render, validate_corpus
from mira.interactions import read_records, transcript
from mira.research import Research
from mira.search import FixtureSearch
from test_research import draft, evidence, decision
from test_r3 import equation, research as media_evidence


def crash_split(root, stage):
    def fault(point):
        if point == stage: os._exit(73)
    Research(root, ScriptedLLM([{"questions": ["Which mechanism needs measuring?"]}]), {}).step(fault=fault)


class BranchingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, responses=(), **config):
        self.llm = ScriptedLLM(responses)
        self.r = Research(self.root, self.llm, {"fixture": FixtureSearch([evidence()] * 10)})
        self.r.initialize("What mechanism transfers heat?", ["fixture"], context_budget=20000, **config)
        return self.r

    def state(self): return loads((self.root / "research/state.json").read_text())

    def change(self, mutate):
        with self.r.store.lock():
            token, memories, equations, ledger = self.r.store.read()
            state = self.state()
            mutate(state, memories, equations, ledger)
            tree.refresh(state, memories)
            self.r.store.publish(memories, equations, ledger, token, files={"research/state.json": dumps(state)})

    def add_children(self, state, count=2):
        for _ in range(count):
            identity = 'q' + str(state['next_node']); state['next_node'] += 1
            state['nodes'][identity] = tree.node(identity, 'Child question ' + identity + '?', 'q1')
            state['nodes']['q1']['child_ids'].append(identity)

    def extraction(self, state, docs, eqs, ledger, identity='q1', results=None):
        return r3.create_memory(state, docs, eqs, ledger, identity, results or [draft()],
                                {**evidence(), 'reference': 'research/results/fixture.json'})

    def exhaust(self, state, *_): state['nodes']['q1']['status'] = 'exhausted'

    def test_threshold_uses_exact_r5_wire_and_crossing_memory_is_kept(self):
        r = self.make([{'keywords': ['heat']}, {'results': [draft()]}])
        empty_total = self.state()['nodes']['q1']['research_capacity']['estimated_tokens']
        self.change(lambda s, *_: s.update(research_capacity_tokens=empty_total + 1))
        for expected in ('R1', 'R2', 'R3'):
            event = r.step(); self.assertEqual(event['action'], expected); self.assertEqual(event['status'], 'committed')
        n = self.state()['nodes']['q1']; snapshot = n['research_capacity']
        self.assertEqual(n['status'], 'exhausted')
        self.assertGreater(snapshot['estimated_tokens'], snapshot['threshold'])
        self.assertEqual(snapshot['memory_ids'], ['r1'])
        self.assertEqual(len(event['exhaustion']), 1)
        self.assertEqual(r.knowledge.validate()['documents'], 1)
        with r.store.lock():
            _, docs, eqs, _ = r.store.read()
            wire = decisions.request(self.llm.model, self.llm.settings, 'R5', branching.context(self.state(), docs, eqs, 'q1'))
        self.assertEqual(snapshot['estimated_tokens'], len(wire.encode()) + 2048)
        self.assertEqual(snapshot['request_bytes'], len(wire.encode()))

    def test_capacity_includes_equations_and_excludes_descendants_and_syntheses(self):
        self.make()
        state = self.state(); docs, eqs, ledger = [], [], {'r': 1, 's': 1}
        self.add_children(state)
        root_doc = self.extraction(state, docs, eqs, ledger)
        initial_context = branching.context(state, docs, eqs, 'q1')
        self.extraction(state, docs, eqs, ledger, 'q2')
        from mira import gardener
        second = self.extraction(state, docs, eqs, ledger, 'q2')
        gardener.apply(state, docs, ledger, 'q2', docs[1:], {'title': 'Combined', 'summary': 'Fixture', 'findings': []})
        root_doc.metadata['synthesized_by'] = 's99'; root_doc.revision += 1
        self.assertEqual(branching.context(state, docs, eqs, 'q1'), initial_context)
        r3.create_memory(state, docs, eqs, ledger, 'q1', [equation(None)], media_evidence())
        ctx = branching.context(state, docs, eqs, 'q1')
        self.assertEqual(len(ctx['research_results']['equations']), 1)
        self.assertEqual([m['id'] for m in ctx['research_results']['memories']], ['r1', 'r4'])

    def test_ripeness_distinct_results_questions_depth_and_ties(self):
        self.make()
        def seed(s, docs, eqs, ledger):
            self.add_children(s)
            finding = {**draft(), 'type': 'finding'}
            hypothesis = {**draft(), 'type': 'hypothesis'}
            question = {**draft(), 'type': 'question', 'origin': 'derived'}
            for identity in ('q1', 'q2', 'q3'):
                s['nodes'][identity]['status'] = 'exhausted'
                self.extraction(s, docs, eqs, ledger, identity, [finding, deepcopy(finding), hypothesis, question])
        self.change(seed)
        s = self.state()
        self.assertEqual(s['nodes']['q1']['ripeness_counts'], {'findings': 1, 'hypotheses': 1, 'questions': 1, 'depth': 0})
        self.assertEqual(s['nodes']['q1']['ripeness'], 5)
        self.assertEqual(s['nodes']['q2']['ripeness'], 4)
        self.assertEqual(s['ripeness_order'], ['q1', 'q2', 'q3'])
        self.change(lambda s, *_: s['nodes']['q2'].update(status='split', split_attempt={'questions': []}))
        self.assertEqual(self.state()['ripeness_order'], ['q1', 'q3'])
        self.assertEqual(self.r.inspect()['nodes_by_depth'], {0: 1, 1: 2})

    def test_question_origin_order_relationships_and_roundtrip(self):
        s = tree.initial('Root?', ['fixture']); docs, eqs, ledger = [], [], {'r': 1, 's': 1}
        source = {**draft(), 'type': 'question', 'origin': 'source'}
        derived = {**source, 'origin': 'derived', 'text': 'Which mechanism is responsible?', 'related_to': 0, 'qualification': ''}
        memory = self.extraction(s, docs, eqs, ledger, results=[draft(), source, derived])
        self.assertEqual([u.anchor for u in memory.units], ['f1', 'q1', 'q2'])
        self.assertEqual([u.fields['Origin'] for u in memory.units[1:]], ['source', 'derived'])
        self.assertEqual(memory.relationships[-1].target, 'r1#f1')
        validate_corpus(docs, eqs)
        self.assertEqual(parse(render(memory)), memory)
        for origin in (None, 'invented', [], 3):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                r3.validate({'results': [{**source, 'origin': origin}]}, evidence())
        del source['origin']
        self.assertRaises(ValueError, r3.validate, {'results': [source]}, evidence())

    def test_no_living_nodes_split_children_zero_and_empty_one_time(self):
        for questions in ([], ['How is heat flux measured?', 'Which boundary condition applies?']):
            with self.subTest(questions=questions), tempfile.TemporaryDirectory() as directory:
                r = Research(directory, ScriptedLLM([{'questions': questions}]), {})
                r.initialize('Root?', ['fixture'])
                with r.store.lock():
                    token, docs, eqs, ledger = r.store.read(); s = loads(r.store._files()['research/state.json'])
                    s['nodes']['q1']['status'] = 'exhausted'; tree.refresh(s, docs)
                    r.store.publish(docs, eqs, ledger, token, files={'research/state.json': dumps(s)})
                event = r.step(); self.assertEqual(event['action'], 'R5'); self.assertEqual(event['status'], 'committed')
                s = loads(Path(directory, 'research/state.json').read_text())
                self.assertEqual(s['nodes']['q1']['status'], 'split')
                self.assertEqual(s['nodes']['q1']['split_attempt']['empty'], not questions)
                self.assertEqual([n['priority'] for i, n in s['nodes'].items() if i != 'q1'], [0] * len(questions))
                self.assertEqual(len(r.llm.requests), 1)
                self.assertNotIn('q1', s['ripeness_order'])
                if not questions:
                    self.assertEqual(r.step()['status'], 'finished')
                    self.assertIn('"empty": true', transcript(directory, full=True))
                    self.assertIn('"empty": true', transcript(directory))

    def test_periodic_branching_does_not_reset_other_progress_or_starve_research(self):
        self.make([{'questions': ['A new mechanism?']}, {'results': [draft()]}], branching_interval=3)
        def seed(s, *_):
            self.add_children(s, 2); self.exhaust(s)
            s['nodes']['q3']['status'] = 'exhausted'
            s['research_cycles_since_branching'] = 2
            s['nodes']['q2']['keywords'] = ['heat']; s['nodes']['q2']['priority'] = 5
        self.change(seed)
        self.assertEqual(self.r.step()['action'], 'R2')
        pending = self.state()['nodes']['q2']['pending_results']
        event = self.r.step(); self.assertEqual(event['action'], 'R5'); self.assertEqual(event['status'], 'committed')
        self.assertEqual(self.state()['nodes']['q2']['pending_results'], pending)
        self.assertEqual(self.state()['research_cycles_since_branching'], 0)
        self.assertEqual(self.state()['ripeness_order'], ['q3'])
        self.assertEqual(self.r.step()['action'], 'R3')
        self.assertEqual(self.state()['nodes']['q2']['next_database_index'], 1)

    def test_no_exhausted_node_never_schedules_r5(self):
        self.make([{'keywords': ['heat']}], branching_interval=1)
        self.change(lambda s, *_: s.update(research_cycles_since_branching=100))
        self.assertEqual(self.r.step()['action'], 'R1')
        self.assertEqual(self.state()['branching_cycles'], 0)
        self.assertRaisesRegex(ValueError, 'exhausted', branching.apply, self.state(), 'q1', {'questions': []}, 'fixture')

    def test_research_switch_and_resume_pending_keywords_pointer_history(self):
        self.make([{'results': [draft()]}])
        def seed(s, *_):
            self.add_children(s, 1)
            s['nodes']['q1'].update(priority=1, keywords=['root heat'], previous_search_terms=['old root'])
            s['nodes']['q2'].update(priority=2, keywords=['child heat'], previous_search_terms=['old child'])
        self.change(seed)
        self.assertEqual(self.r.step()['action'], 'R2')
        before = deepcopy(self.state()['nodes']['q1'])
        self.assertIsNotNone(before['pending_results'])
        self.assertEqual(self.state()['active_node_id'], 'q2')
        self.assertEqual(self.r.step()['action'], 'R2')
        self.assertEqual(self.state()['nodes']['q1']['pending_results'], before['pending_results'])
        self.change(lambda s, *_: s['nodes']['q2'].update(priority=0))
        event = self.r.step(); self.assertEqual((event['action'], event['node_id']), ('R3', 'q1'))
        after = self.state()['nodes']['q1']
        self.assertEqual(after['keywords'], ['root heat'])
        self.assertEqual(after['previous_search_terms'], ['old root'])
        self.assertEqual(after['next_database_index'], 1)

    def test_one_call_per_cycle_across_research_branching_and_synthesis(self):
        from mira.research_demo import DemoLLM
        self.make()
        self.r.llm = DemoLLM()
        from mira.research_demo import evidence as demo_evidence
        self.r.adapters = {'fixture':FixtureSearch([demo_evidence('fixture-'+str(i)) for i in range(1,11)])}
        self.change(lambda s, *_: s.update(research_capacity_tokens=6000, synthesis_interval=3))
        actions = set()
        for _ in range(35):
            before = len(self.r.llm.requests); e = self.r.step()
            self.assertLessEqual(len(self.r.llm.requests) - before, 1)
            if e['status'] == 'finished': break
            self.assertEqual(e['status'], 'committed', e.get('error')); actions.add(e['action'])
        self.assertTrue({'R1', 'R2', 'R3', 'R4', 'R5', 'S1', 'S2'} <= actions, actions)

    def test_malformed_r4_r5_and_child_limit_preserve_state(self):
        for value in ({'decision': 'exhaust', 'reason': 'old'}, {'decision': 'retry', 'reason': 'ok', 'keywords': ['bad']},
                      {'decision': [], 'reason': 'bad'}, {'decision': 'answered', 'reason': ''}):
            self.assertRaises(ValueError, decisions.validate, 'R4', value)
        self.make([{'questions': 'bad'}, {'questions': [None]}, {'questions': ['A?', 'B?']}], max_children=1)
        self.change(self.exhaust); before = self.state()
        for _ in range(3):
            event = self.r.step(); self.assertEqual(event['status'], 'rejected')
            self.assertEqual(self.state(), before)
        self.assertEqual(len(self.llm.requests), 3)
        self.assertFalse(any(r['validation']['accepted'] for r in read_records(self.root)))

    def test_duplicate_questions_are_filtered_and_attempt_still_completes(self):
        self.make([{'questions': [' What mechanism transfers heat? ', 'New question?', 'NEW  QUESTION?']}])
        self.change(self.exhaust)
        event = self.r.step(); self.assertEqual(event['status'], 'committed')
        self.assertEqual(event['branching']['accepted'], ['New question?'])
        self.assertEqual(len(event['branching']['duplicates']), 2)
        self.assertEqual(len(self.state()['nodes']), 2)
        self.assertRaises(ValueError, self.change,
            lambda s, *_: s['nodes']['q1'].update(status='exhausted', split_attempt=None))

    def test_oversized_memory_kept_and_r5_blocks_explicitly_without_truncation(self):
        self.make([{'questions': []}])
        def seed(s, docs, eqs, ledger):
            self.extraction(s, docs, eqs, ledger, results=[{**draft(), 'text': 'Long material ' * 1800}])
            branching.assess(s, docs, eqs, self.llm.model, self.llm.settings)
        self.change(seed)
        s = self.state(); self.assertTrue(s['nodes']['q1']['research_capacity']['over_context_budget'])
        self.assertEqual(s['nodes']['q1']['status'], 'exhausted')
        event = self.r.step()
        self.assertEqual(event['status'], 'rejected'); self.assertIn('blocked_context_budget', event['error'])
        self.assertEqual(self.state(), s)
        self.assertFalse(self.llm.requests)
        self.assertIn('Long material ' * 100, self.r.knowledge.document('r1').units[0].fields['Proposition'])

    def test_crash_recovery_replays_split_without_another_model_call(self):
        for stage in ('prepared', 'replaced:research/state.json', 'before_commit'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                r = Research(directory, ScriptedLLM([]), {}); r.initialize('Root?', ['fixture'])
                with r.store.lock():
                    token, docs, eqs, ledger = r.store.read(); s = loads(r.store._files()['research/state.json'])
                    s['nodes']['q1']['status'] = 'exhausted'; tree.refresh(s, docs)
                    r.store.publish(docs, eqs, ledger, token, files={'research/state.json': dumps(s)})
                p = multiprocessing.get_context('fork').Process(target=crash_split, args=(directory, stage))
                p.start(); p.join(10); self.assertEqual(p.exitcode, 73)
                report = r.store.recovery_status()['operations'][0]
                self.assertIn(report['assessment'], {'safely_finishable', 'complete'})
                r.store.repair(report['id'], apply=True)
                r.store.repair(report['id'], apply=True)
                with r.store.lock(): r.store.read(); self.assertFalse(r._unresolved(r.store._files()))
                s = loads(Path(directory, 'research/state.json').read_text())
                self.assertEqual(s['nodes']['q1']['status'], 'split'); self.assertEqual(s['next_node'], 3)
                self.assertEqual(s['branching_cycles'], 1)
                self.assertFalse(r.llm.requests)
                r.llm = ScriptedLLM([{'keywords': ['mechanism']}])
                self.assertEqual(r.step()['action'], 'R1')

    def test_legacy_state_is_readable_and_upgrade_is_journaled(self):
        self.make([{'questions': []}])
        # Build a genuine v1 corpus in a separate root; never downgrade a live v2 run.
        with tempfile.TemporaryDirectory() as directory:
            r = Research(directory, ScriptedLLM([{'questions': []}]), {})
            with r.store.lock():
                token, docs, eqs, ledger = r.store.read()
                s = legacy.initial('Legacy root?', ['fixture'])
                s['nodes']['q1']['status'] = 'exhausted'; legacy.refresh(s, docs)
                self.assertEqual(s['nodes']['q1']['status'], 'complete')
                r.store.publish(docs, eqs, ledger, token, files={'research/state.json': dumps(s)})
            self.assertEqual(r.inspect()['nodes']['q1']['status'], 'complete')
            event = r.step(); self.assertEqual(event['status'], 'committed')
            self.assertEqual(event['state_upgrade'], {'from': 1, 'to': 2})
            state = loads(Path(directory, 'research/state.json').read_text())
            self.assertEqual(state['mira_research'], 2)
            self.assertEqual(state['nodes']['q1']['legacy_status'], 'complete')
            self.assertEqual(state['nodes']['q1']['status'], 'split')

    def test_synthesis_never_changes_exhaustion_or_split_and_excludes_killed_branch(self):
        self.make()
        def seed(s, docs, eqs, ledger):
            self.add_children(s)
            self.exhaust(s)
            s['nodes']['q2']['status'] = 'killed'
            s['nodes']['q3']['status'] = 'answered'
            for identity in ('q1', 'q2', 'q3'): self.extraction(s, docs, eqs, ledger, identity)
        self.change(seed)
        s = self.state()
        self.assertEqual(s['nodes']['q1']['status'], 'exhausted')
        self.assertFalse(s['nodes']['q1']['synthesis_complete'])
        with self.r.store.lock():
            _, docs, _, _ = self.r.store.read()
            self.assertEqual([m.id for m in tree.frontier(s, docs, 'q1')], ['r1', 'r3'])
            self.assertEqual(tree.frontier(s, docs, 'q2'), [])
        self.assertEqual(self.r.knowledge.validate()['documents'], 3)

    def test_arxiv_query_requires_topic_words_and_preserves_exact_id_queries(self):
        from mira.search import ArxivSearch
        self.assertEqual(ArxivSearch.query(['Monte Carlo dropout', 'dropout uncertainty']),
            'all:"Monte" AND all:"Carlo" AND all:"dropout" AND all:"uncertainty"')
        self.assertEqual(ArxivSearch.query(['id:1512.05287']), 'id:1512.05287')
        self.assertEqual(ArxivSearch.query(['id:physics/0306182v1']), 'id:physics/0306182v1')
        self.assertEqual(ArxivSearch.query(['"recurrent dropout"']), 'all:"recurrent" AND all:"dropout"')
        self.assertRaises(ValueError, ArxivSearch.query, ['!!!'])
        self.llm = ScriptedLLM([{'keywords': ['recurrent dropout', 'neural networks']}])
        self.r = Research(self.root, self.llm, {})
        self.r.initialize('Question?', ['arxiv'], context_budget=20000)
        search = FixtureSearch([{'status': 'empty', 'results': []}])
        self.r.adapters = {'arxiv': search}
        self.r.step(); event = self.r.step()
        self.assertEqual(event['query'], 'all:"recurrent" AND all:"dropout" AND all:"neural" AND all:"networks"')
        self.assertEqual(search.queries, [event['query']])

    def test_existing_synthesis_with_killed_lineage_is_excluded(self):
        from mira import gardener
        self.make()
        def seed(s, docs, eqs, ledger):
            self.add_children(s, 1)
            self.extraction(s, docs, eqs, ledger, 'q1')
            self.extraction(s, docs, eqs, ledger, 'q2')
            gardener.apply(s, docs, ledger, 'q1', list(docs), {'title': 'Combined', 'summary': 'Fixture', 'findings': []})
            s['nodes']['q2']['status'] = 'killed'
        self.change(seed)
        s = self.state()
        self.assertEqual(s['nodes']['q1']['unsynthesized_memory_count'], 0)
        self.assertEqual(s['synthesis_candidate_order'], [])
        self.assertEqual(self.r.knowledge.validate()['documents'], 3)

    def test_upgrade_preserves_legacy_pending_evidence_for_previously_branched_node(self):
        s = legacy.initial('Legacy?', ['fixture'])
        s['nodes']['q2'] = legacy.node('q2', 'Existing child?', 'q1')
        s['next_node'] = 3; s['nodes']['q1']['child_ids'] = ['q2']
        s['nodes']['q1'].update(keywords=['heat'], next_database_index=1,
                                pending_results='research/results/legacy.json')
        legacy.refresh(s, [])
        converted = tree.upgrade(s, [])
        n = converted['nodes']['q1']
        self.assertEqual(n['status'], 'split')
        self.assertIsNone(n['pending_results'])
        self.assertEqual(n['legacy_pending_results'], 'research/results/legacy.json')
        self.assertTrue(n['split_attempt']['legacy'])
        self.assertEqual(s['nodes']['q1']['status'], 'living')
        tree.validate(converted, [], {})

    def test_answered_parent_is_not_synthesis_complete_while_descendant_is_active(self):
        self.make()
        def seed(s, *_):
            self.add_children(s, 1)
            s['nodes']['q1']['status'] = 'answered'
        self.change(seed)
        s = self.state()
        self.assertEqual(s['nodes']['q1']['status'], 'answered')
        self.assertFalse(s['nodes']['q1']['synthesis_complete'])
        self.assertEqual(s['active_node_id'], 'q2')
        self.assertEqual(s['nodes']['q1']['living_descendant_count'], 1)
        self.change(lambda s, *_: s['nodes']['q2'].update(status='answered'))
        self.assertTrue(self.state()['nodes']['q1']['synthesis_complete'])
