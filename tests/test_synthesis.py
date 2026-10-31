"""Deterministic S1/S2 contracts, scheduling, versions and durable attempts."""
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

from mira import gardener, research_tree as tree
from mira.decisions import ScriptedLLM
from mira.decisions import request
from mira.format import Unit, dumps, loads, render
from mira.interactions import read_records
from mira.live import LiveStore
from mira.research import Research
from test_gardener import seed


def selection(ids=('r1', 'r2'), **changes):
    return {"disposition": "select", "memory_ids": list(ids),
            "objective": "Compare attributed evidence, its complementarity and limitations.",
            "scores": {"R": 5, "C": 4, "X": 1, "N": 3, "E": 3},
            "reason": "These inputs support a focused comparison.", **changes}


def synthesis(refs=('r1#f1', 'r2#f1'), **changes):
    return {"disposition": "synthesis", "title": "Qualified integration",
            "summary": "An attributed comparison with unresolved uncertainty.",
            "findings": [{"label": "Integrated evidence", "proposition": "The sources jointly support a scoped inference.",
                          "explanation": "Complementary observations support comparison, with no independent replication.",
                          "provenance": "Derived from the supplied knowledge units.", "source_findings": list(refs)}], **changes}


class ExitDuringCall(ScriptedLLM):
    def complete(self, wire): os._exit(79)


def crash_s1(root):
    def fault(stage):
        if stage == 'replaced:research/state.json': os._exit(78)
    Research(root, ScriptedLLM([selection()]), {}).step(fault=fault)


def crash_dispatch(root): Research(root, ExitDuringCall([]), {}).step()


def crash_partial(root, stage):
    def fault(point):
        if point == stage: os._exit(77)
    Research(root, ScriptedLLM([synthesis()]), {}).step(fault=fault)


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, responses=(), *, own=3, child=0, leaf=0, living=()):
        self.llm = ScriptedLLM(responses)
        self.r = Research(self.root, self.llm, {})
        self.r.initialize('How can evidence support sustained scientific research?', ['fixture'], context_budget=200000)
        seed(self.r, own=own, child=child, leaf=leaf, living=living)
        return self.r

    def state(self): return loads((self.root / 'research/state.json').read_text())

    def change(self, callback):
        with self.r.store.lock():
            token, memories, equations, ledger = self.r.store.read()
            state = self.state(); callback(state, memories, equations, ledger)
            tree.refresh(state, memories)
            self.r.store.publish(memories, equations, ledger, token, files={'research/state.json': dumps(state)})

    def test_same_question_selection_scores_and_separate_cycles(self):
        r = self.make([selection(), synthesis()])
        before = self.state()
        e = r.step(); self.assertEqual((e['action'], e['status']), ('S1', 'committed'))
        self.assertEqual(len(self.llm.requests), 1)
        pending = self.state()['pending_synthesis']; self.assertIsNotNone(pending)
        a = self.state()['synthesis_attempts'][0]
        self.assertEqual(a['status'], 'pending'); self.assertEqual(a['score'], 16)
        self.assertEqual(a['node_id'], 'q1'); self.assertEqual(a['scores'], selection()['scores'])
        self.assertEqual(r.knowledge.validate()['documents'], 3)
        catalogue = read_records(self.root)[0]['request']['context']['memory_catalogue']
        for entry in catalogue:
            self.assertEqual(entry['content_hash'], tree.memory_versions([r.knowledge.document(entry['id'])])[0]['content_hash'])
            self.assertTrue(entry['estimated_s2_tokens']); self.assertTrue(entry['ancestor_questions'])
            self.assertEqual(entry['knowledge_unit_types'], {'claim': 1})
        restarted = Research(self.root, self.llm, {})
        e = restarted.step(); self.assertEqual((e['action'], e['status']), ('S2', 'committed'))
        self.assertEqual(len(self.llm.requests), 2)
        state = self.state(); self.assertIsNone(state['pending_synthesis'])
        a = state['synthesis_attempts'][0]
        self.assertEqual(a['status'], 'completed'); self.assertTrue(a['s2_interaction_id'])
        self.assertEqual(a['result_memory_id'], 's1')
        self.assertEqual(state['research_cycles'], before['research_cycles'])
        self.assertEqual(state['nodes']['q1']['priority'], before['nodes']['q1']['priority'])

    def test_cross_branch_selection_uses_common_ancestor(self):
        r = self.make([selection(['r1','r2']), synthesis()], own=0, child=1, leaf=1)
        def siblings(s, *_):
            s['nodes']['q1']['child_ids'] = ['q2','q3']; s['nodes']['q2']['child_ids'] = []
            s['nodes']['q3']['parent_id'] = 'q1'
        self.change(siblings)
        self.assertEqual(r.step()['status'], 'committed')
        self.assertEqual(self.state()['synthesis_attempts'][0]['node_id'], 'q1')
        self.assertEqual(r.step()['status'], 'committed')
        self.assertEqual(r.knowledge.document('s1').metadata['node_id'], 'q1')
        self.assertEqual(r.knowledge.document('s1').metadata['source_memories'], ['r1','r2'])

    def test_invalid_s1_selections_and_scores_do_not_persist(self):
        r = self.make()
        bad = [selection([]), selection(['r1']), selection(['r1','r1']), selection(['r1','unknown']),
               selection(objective=' '), selection(reason=''), selection(disposition='invent'),
               selection(scores={**selection()['scores'], 'R': True}),
               selection(scores={**selection()['scores'], 'R': 5.5}),
               selection(scores={**selection()['scores'], 'E': 6}),
               selection(scores={'R': 5}), selection(extra='unexpected'),
               {'disposition':'no_candidate', 'reason':''}, {'disposition':'no_candidate', 'reason':'None', 'memory_ids':[]}]
        for proposal in bad:
            with self.subTest(proposal=proposal):
                r.llm = ScriptedLLM([proposal]); before = self.state()
                e = r.step(); self.assertEqual(e['status'], 'rejected', e)
                self.assertEqual(self.state(), before)
                self.assertEqual(len(r.llm.requests), 1)
        self.assertIsNone(r.knowledge.document('r1').metadata['synthesized_by'])

    def test_killed_and_consumed_memories_are_not_selectable(self):
        r = self.make([selection(), synthesis()], own=2, child=0, leaf=1, living=('q3',))
        self.change(lambda s, *_: s['nodes']['q3'].update(status='killed'))
        with r.store.lock(): _, docs, _, _ = r.store.read()
        with self.assertRaisesRegex(ValueError, 'eligible'):
            gardener.validate_selection(selection(['r1','r3']), self.state(), docs)
        self.assertEqual(r.step()['status'],'committed'); self.assertEqual(r.step()['status'],'committed')
        with r.store.lock(): _, docs, _, _ = r.store.read()
        with self.assertRaisesRegex(ValueError, 'eligible'):
            gardener.validate_selection(selection(), self.state(), docs)

    def test_partial_synthesis_consumes_contributors_only_and_updates_frontier(self):
        r = self.make([selection(['r1','r2','r3']), synthesis()])
        self.assertEqual(r.step()['action'], 'S1')
        e = r.step(); self.assertEqual(e['status'], 'committed')
        self.assertEqual(e['contributing_memory_ids'], ['r1','r2']); self.assertEqual(e['unused_memory_ids'], ['r3'])
        self.assertIsNone(r.knowledge.document('r3').metadata['synthesized_by'])
        self.assertEqual(r.knowledge.document('r1').metadata['synthesized_by'],'s1')
        output = r.knowledge.document('s1')
        self.assertEqual(output.metadata['source_memories'], ['r1','r2'])
        self.assertEqual(len(output.metadata['synthesis_inputs']), 3)
        with r.store.lock(): _, docs, _, _ = r.store.read()
        self.assertEqual([m.id for m in tree.frontier(self.state(), docs, 'q1')], ['r3','s1'])
        self.assertFalse(self.state()['nodes']['q1']['synthesis_complete'])
        self.assertTrue(tree.permitted(self.state(), [r.knowledge.document(i) for i in ('r3','s1')]))

    def test_no_synthesis_excludes_exact_subsets_but_allows_new_combinations(self):
        r = self.make([selection(['r1','r2','r3']), {'disposition':'no_synthesis','reason':'The evidence is insufficient.'}], own=4)
        r.step(); e = r.step(); self.assertEqual(e['status'],'committed')
        self.assertEqual(e['memory_ids'], []); self.assertEqual(r.knowledge.validate()['documents'],4)
        a = self.state()['synthesis_attempts'][0]
        self.assertEqual(a['unused_memory_ids'], ['r1','r2','r3']); self.assertFalse(a['contributing_memory_ids'])
        with r.store.lock(): _, docs, _, _ = r.store.read()
        for ids in (['r1','r2'], ['r3','r1'], ['r1','r2','r3']):
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, 'previously attempted'):
                gardener.validate_selection(selection(ids), self.state(), docs)
        self.assertEqual([m.id for m in gardener.validate_selection(selection(['r1','r2','r4']),self.state(),docs)], ['r1','r2','r4'])

    def test_exhausted_combinations_complete_with_multiple_frontier_memories(self):
        r = self.make([selection(), {'disposition':'no_synthesis','reason':'No defensible integration.'}], own=2)
        r.step(); r.step(); state = self.state()
        self.assertTrue(state['nodes']['q1']['synthesis_complete'])
        self.assertEqual(state['nodes']['q1']['unsynthesized_memory_count'],2)
        self.assertFalse(state['synthesis_candidate_order']); self.assertTrue(state['terminal_event'])
        self.assertEqual(r.step()['status'], 'finished'); self.assertEqual(len(self.llm.requests),2)

    def test_changed_memory_hash_reopens_excluded_combination(self):
        r = self.make([selection(), {'disposition':'no_synthesis','reason':'No defensible integration.'}], own=2)
        r.step(); r.step(); old = self.state()['synthesis_attempts'][0]['memory_versions']
        def revise(s, docs, *_):
            docs[0].units.append(Unit(docs[0].allocate('f'), 'New evidence', {**docs[0].units[0].fields, 'Explanation': 'New methodological qualification.'})); docs[0].revision += 1
        self.change(revise)
        self.assertTrue(self.state()['synthesis_candidate_order'])
        self.assertFalse(self.state()['nodes']['q1']['synthesis_complete'])
        with r.store.lock(): _, docs, _, _ = r.store.read()
        self.assertNotEqual(tree.memory_versions(docs),old)
        self.assertEqual(len(gardener.validate_selection(selection(),self.state(),docs)),2)

    def test_terminal_no_candidate_guard_and_revision_invalidation(self):
        r = self.make([{'disposition':'no_candidate','reason':'The sources do not form a coherent analysis.'}])
        r.step(); state = self.state()
        self.assertTrue(state['synthesis_evaluated_catalogue']); self.assertTrue(state['terminal_event'])
        self.assertTrue(state['nodes']['q1']['synthesis_complete'])
        for _ in range(2): self.assertEqual(r.step()['status'],'finished')
        self.assertEqual(len(self.llm.requests),1)
        def revise(s, docs, *_): docs[0].summary += ' Revised evidence.'; docs[0].revision += 1
        self.change(revise)
        self.assertTrue(self.state()['synthesis_candidate_order'])
        r.llm = ScriptedLLM([selection()]); self.assertEqual(r.step()['action'],'S1')
        self.assertEqual(len(r.llm.requests),1)

    def test_active_no_candidate_is_reassessed_at_cadence(self):
        responses = [{'disposition':'no_candidate','reason':'No coherent comparison yet.'}, {"new_concepts": [], "reason": "Fixture search plan.", "search_concepts":['methods', 'measurement']}, selection()]
        r = self.make(responses, own=2, living=('q3',))
        self.change(lambda s, *_: s.update(research_cycles_since_synthesis=5))
        self.assertEqual(r.step()['reason'],'no_candidate')
        self.assertIsNone(self.state()['synthesis_evaluated_catalogue'])
        self.assertIsNone(self.state()['terminal_event'])
        self.assertEqual(r.step()['action'],'R1')
        self.change(lambda s, *_: s.update(research_cycles_since_synthesis=5))
        self.assertEqual(r.step()['action'],'S1'); self.assertEqual(len(self.llm.requests),3)

    def test_pending_s2_precedes_research_and_branching(self):
        r = self.make([selection(), synthesis()], own=2, living=('q3',))
        self.change(lambda s, *_: s.update(research_cycles_since_synthesis=5))
        self.assertEqual(r.step()['action'],'S1')
        self.change(lambda s, *_: s['nodes']['q3'].update(status='exhausted'))
        self.assertEqual(r.step()['action'],'S2')
        self.assertIsNone(self.state()['terminal_event'])
        self.assertEqual(self.state()['ripeness_order'],['q3'])

    def test_one_cross_memory_finding_is_required_not_separate_source_summaries(self):
        r = self.make(own=2)
        with r.store.lock(): _, docs, _, _ = r.store.read()
        single = synthesis(['r1#f1']); separate = deepcopy(single)
        separate['findings'].extend(synthesis(['r2#f1'])['findings'])
        for value in (single, separate):
            with self.assertRaisesRegex(ValueError,'integrated finding'):
                gardener.validate(value,docs)
        self.assertEqual(gardener.validate(synthesis(), docs), ['r1','r2'])

    def test_invalid_references_dispositions_and_empty_findings(self):
        r = self.make(own=2)
        with r.store.lock(): _, docs, _, _ = r.store.read()
        bad = [synthesis(['r1#f1','r2#f999']), synthesis(['r1#f1','r1#f1','r2#f1']),
               synthesis(['r1#f1','r2#f1','r9#f1']), synthesis(findings=[]), synthesis(disposition='invent'),
               {'disposition':'no_synthesis','reason':''}, {'disposition':'no_synthesis','reason':'None','findings':[]}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError): gardener.validate(value,docs)
        self.assertEqual(gardener.validate({'disposition':'no_synthesis','reason':'Evidence is insufficient.'},docs), [])

    def test_failed_s2_retains_audit_and_is_retryable_without_consumption(self):
        r = self.make([selection(), synthesis(['r1#f1','r2#invented']), selection()])
        r.step(); before = {i:render(r.knowledge.document(i)) for i in ('r1','r2','r3')}
        e = r.step(); self.assertEqual(e['status'],'rejected')
        state = self.state(); a = state['synthesis_attempts'][0]
        self.assertEqual(a['status'],'failed'); self.assertTrue(a['s2_interaction_id'])
        self.assertIsNone(state['pending_synthesis']); self.assertTrue(state['synthesis_candidate_order'])
        for i, text in before.items(): self.assertEqual(render(r.knowledge.document(i)),text)
        self.assertEqual(r.step()['status'],'committed'); self.assertEqual(len(self.state()['synthesis_attempts']),2)
        self.assertFalse(read_records(self.root)[1]['validation']['accepted'])

    def test_transport_failure_is_recorded_and_does_not_exclude(self):
        r = self.make([selection(), RuntimeError('Temporary transport failure.')])
        r.step(); self.assertEqual(r.step()['status'],'rejected')
        self.assertEqual(self.state()['synthesis_attempts'][0]['status'],'failed')
        self.assertTrue(self.state()['synthesis_candidate_order'])

    def test_pending_input_revision_fails_before_dispatch(self):
        r = self.make([selection()]); r.step()
        def revise(s, docs, *_): docs[0].summary += ' New information.'; docs[0].revision += 1
        self.change(revise)
        e = r.step(); self.assertEqual(e['status'],'rejected'); self.assertIn('versions changed',e['error'])
        self.assertEqual(len(self.llm.requests),1)
        self.assertEqual(self.state()['synthesis_attempts'][0]['status'],'failed')

    def test_exact_s2_budget_and_oversized_collection_never_drops_selected_inputs(self):
        r = self.make([selection(['r1','r2','r3'])])
        # The catalogue fits, but full S2 and its lossless projection cannot fit.
        def counter(wire):
            content = loads(wire)['messages'][0]['content']
            return {'prompt_tokens': 500 if 'Eligible memory catalogue:' in content else 10000}
        self.llm.count_tokens = counter
        self.change(lambda s, *_: s.update(context_budget=8192,research_capacity_tokens=7000))
        e = r.step(); self.assertEqual(e['status'],'blocked_synthesis')
        self.assertEqual(e['selection']['input_ids'],['r1','r2','r3'])
        self.assertEqual(len(self.llm.requests),1); self.assertFalse(self.state()['synthesis_attempts'])
        self.assertIsNone(self.state()['pending_synthesis'])
        self.assertIsNone(self.state()['terminal_event'])

    def test_s1_catalogue_budget_rejected_before_model_dispatch(self):
        r = self.make()
        self.llm.count_tokens = lambda _: {'prompt_tokens': 200000}
        e = r.step(); self.assertEqual(e['status'],'rejected')
        self.assertIn('blocked_context_budget',e['error']); self.assertFalse(self.llm.requests)
        self.assertFalse(self.state()['synthesis_attempts'])

    def test_changed_s2_budget_fails_without_dispatch_and_consumption(self):
        r = self.make([selection()]); r.step()
        self.llm.count_tokens = lambda _: {'prompt_tokens': 200000}
        e = r.step(); self.assertEqual(e['status'],'rejected')
        self.assertIn('blocked_context_budget',e['error']); self.assertEqual(len(self.llm.requests),1)
        self.assertEqual(self.state()['synthesis_attempts'][0]['status'],'failed')
        self.assertIsNone(r.knowledge.document('r1').metadata['synthesized_by'])

    def test_s1_journal_recovery_restores_pending_selection_once(self):
        r = self.make(own=2)
        p=multiprocessing.get_context('fork').Process(target=crash_s1,args=(str(self.root),))
        p.start();p.join(10);self.assertEqual(p.exitcode,78)
        operation=r.store.recovery_status()['operations'][0]
        r.store.repair(operation['id'],apply=True);r.store.repair(operation['id'],apply=True)
        self.assertEqual(len(self.state()['synthesis_attempts']),1)
        r.llm=ScriptedLLM([synthesis()]);self.assertEqual(r.step()['action'],'S2')
        self.assertEqual(len(r.llm.requests),1)
        self.assertEqual(self.state()['synthesis_attempts'][0]['status'],'completed')
        self.assertFalse(r.store.recovery_status()['blocked'])

    def test_unknown_s2_dispatch_requires_explicit_acknowledgement(self):
        r=self.make([selection()],own=2);r.step()
        p=multiprocessing.get_context('fork').Process(target=crash_dispatch,args=(str(self.root),))
        p.start();p.join(10);self.assertEqual(p.exitcode,79)
        self.assertEqual(self.state()['synthesis_attempts'][0]['status'],'pending')
        with self.assertRaisesRegex(ValueError,'interrupted/unknown'):r.step()
        self.assertEqual(len(r.acknowledge_interrupted()),1)
        r.llm=ScriptedLLM([synthesis()]);self.assertEqual(r.step()['status'],'committed')
        self.assertEqual(len(self.state()['synthesis_attempts']),1)
        self.assertEqual(r.knowledge.validate()['documents'],3)

    def test_partial_synthesis_and_attempt_recover_atomically(self):
        r=self.make([selection(['r1','r2','r3'])]);r.step()
        p=multiprocessing.get_context('fork').Process(target=crash_partial,
            args=(str(self.root),'replaced:memories/s1.md'))
        p.start();p.join(10);self.assertEqual(p.exitcode,77)
        operation=r.store.recovery_status()['operations'][0]
        r.store.repair(operation['id'],apply=True);r.store.repair(operation['id'],apply=True)
        state=self.state();a=state['synthesis_attempts'][0]
        self.assertEqual(a['status'],'completed');self.assertEqual(a['contributing_memory_ids'],['r1','r2'])
        self.assertEqual(a['unused_memory_ids'],['r3']);self.assertIsNone(state['pending_synthesis'])
        self.assertIsNone(r.knowledge.document('r3').metadata['synthesized_by'])
        self.assertEqual(r.knowledge.document('r1').metadata['synthesized_by'],'s1')
        self.assertEqual(r.knowledge.validate()['documents'],4)
        self.assertEqual(len(read_records(self.root)),2)
        self.assertFalse(r.store.recovery_status()['blocked'])

    def test_s2_exact_budget_boundary_includes_objective_and_reserve(self):
        r=self.make(own=2)
        with r.store.lock():_,docs,eqs,_=r.store.read()
        objective='Compare qualifications and independently supported evidence.'
        state=self.state();wire=request(
            self.llm.model,self.llm.settings,'S2',gardener.context(state,docs,eqs,'q1',docs,objective=objective))
        exact=len(wire.encode())+state['output_reserve']
        state['context_budget']=exact
        identity,supplied,info=gardener.prepare(state,docs,eqs,docs,objective,self.llm.model,self.llm.settings)
        self.assertEqual(identity,'q1');self.assertIsNotNone(supplied)
        self.assertEqual(supplied['objective'],objective);self.assertEqual(info['estimated_total'],exact)
        self.assertEqual(info['representation'],'complete_memory')
        state['context_budget']=exact-1
        _,supplied,info=gardener.prepare(state,docs,eqs,docs,objective,self.llm.model,self.llm.settings)
        self.assertTrue(supplied is None or info['representation']=='structured_summary')
        self.assertEqual(info['input_ids'],['r1','r2'])

    def test_completed_register_is_immutable(self):
        r=self.make([selection(),{'disposition':'no_synthesis','reason':'Insufficient evidence.'}],own=2)
        r.step();r.step()
        for change in (lambda s,*_:s['synthesis_attempts'].clear(),
                       lambda s,*_:s['synthesis_attempts'][0].update(reason='Rewrite history.')):
            with self.assertRaisesRegex(ValueError,'forget|immutable'):self.change(change)
        self.assertEqual(self.state()['synthesis_attempts'][0]['reason'],'Insufficient evidence.')

    def test_old_v2_experiment_remains_readable_and_upgrades_on_action(self):
        r=self.make(own=2)
        with r.store.lock(): _, docs, eqs, ledger=r.store.read()
        state=self.state()
        for key in ('synthesis_attempts','pending_synthesis','synthesis_evaluated_catalogue'):state.pop(key)
        tree.refresh(state,docs)
        with tempfile.TemporaryDirectory() as directory:
            old=LiveStore(directory)
            with old.lock():
                token,*_=old.read();old.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
            before={m.id:render(m) for m in docs};raw=Path(directory,'research/state.json').read_bytes()
            restarted=Research(directory,ScriptedLLM([selection()]),{})
            restarted.inspect();self.assertEqual(Path(directory,'research/state.json').read_bytes(),raw)
            self.assertEqual(restarted.step()['status'],'committed')
            upgraded=loads(Path(directory,'research/state.json').read_text())
            self.assertEqual(len(upgraded['synthesis_attempts']),1)
            for identity,text in before.items():self.assertEqual(render(restarted.knowledge.document(identity)),text)


if __name__ == '__main__': unittest.main()
