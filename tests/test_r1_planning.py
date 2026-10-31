"""Round planning, full-history guards and durable blocked handoff."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mira import r1, retrieval, query_profiles, research_tree as tree
from mira.decisions import ScriptedLLM, validate
from mira.experiments import file_hashes
from mira.format import dumps, loads
from mira.interactions import read_records
from mira.research import Research
from mira.search import FixtureSearch


def plan(selected=(), new=(), reason='Distinct scientific search.'):
    return {'new_concepts': list(new), 'search_concepts': list(selected), 'reason': reason}


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'memory'

    def make(self, responses, providers=None, **config):
        r = Research(self.root, ScriptedLLM(responses), providers or {})
        r.initialize('How does thermal resistance affect heat flux?', list(providers or {'fixture': None}),
            context_budget=40000, **config)
        return r

    def state(self):
        return loads((self.root / 'research/state.json').read_text())

    def seed_history(self, r, rows):
        with r.store.lock():
            token, docs, eqs, ledger = r.store.read()
            files = {f'research/results/history-{i}.json': dumps({'node_id': 'q1', 'timestamp': f'{i:03}',
                'status': 'empty', 'query_submitted': True, 'results': [], **row}) for i, row in enumerate(rows)}
            r.store.publish(docs, eqs, ledger, token, files=files)

    def test_empty_and_all_control_selections_block_without_more_calls(self):
        for selected in ([], ['metadata']):
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp) / 'memory'
                r = self.make([plan(selected, ['heat capacity'])])
                event = r.step()
                self.assertEqual((event['action'], event['status']), ('R1', 'committed'))
                node = self.state()['nodes']['q1']
                self.assertTrue(node['search_blocked']); self.assertEqual(node['status'], 'living')
                self.assertFalse(node['synthesis_complete'])
                self.assertEqual(node['concept_candidates'][0]['term'], 'heat capacity')
                before = file_hashes(self.root)
                restarted = Research(self.root, ScriptedLLM([]), {})
                for _ in range(3):
                    outcome = restarted.step()
                    self.assertEqual(outcome['status'], 'waiting_for_r4_upgrade')
                    self.assertEqual(outcome['pending_r4'], ['q1'])
                self.assertEqual(file_hashes(self.root), before)
                self.assertEqual(len(read_records(self.root)), 1)

    def test_all_repeated_selection_checked_beyond_bounded_history(self):
        r = self.make([plan(['thermal resistance'])])
        self.seed_history(r, [{'provider': 'fixture', 'query': 'thermal resistance'},
            *[{'provider': 'fixture', 'query': f'thermal resistance extra {i}'} for i in range(20)]])
        event = r.step()
        self.assertTrue(event['search_blocked'])
        self.assertEqual(event['search_blocked_reason'], 'completed_queries_only')
        self.assertGreater(event['r1_projection']['completed_queries']['omitted_count'], 0)
        self.assertEqual(event['repeated_queries'][0]['original_reference'], 'research/results/history-0.json')

    def test_one_r1_shared_plan_prefixes_and_individual_provider_skip(self):
        a, b = FixtureSearch([]), FixtureSearch([{'status': 'empty', 'results': []}])
        registry = query_profiles.registry()
        registry['profiles'][0]['max_terms'] = 1
        alternate = deepcopy(registry['profiles'][0]); alternate.update(id='larger', max_terms=6)
        # Use actual providers so profile compatibility is validated at init.
        registry['profiles'].append(alternate)
        profile_path = Path(self.temp.name) / 'profiles.json'; profile_path.write_text(dumps(registry))
        strategy_path = Path(self.temp.name) / 'strategies.json'
        strategy_path.write_text(dumps([{'id':'fixture', 'name':'Fixture', 'description':'Different prefixes.',
            'databases':['crossref','wikipedia'], 'profiles':{'crossref':'default', 'wikipedia':'larger'}}]))
        r = Research(self.root, ScriptedLLM([plan(['thermal resistance', 'heat flux'], ['heat flux', 'thermal diffusivity'])]),
            {'crossref':a, 'wikipedia':b})
        r.initialize('Heat flux?', strategy='fixture', registry=strategy_path, profile_registry=profile_path, context_budget=40000)
        self.seed_history(r, [{'provider': 'crossref', 'query': 'thermal resistance'}])
        self.assertEqual(r.step()['r1_projection']['term_limit'], 6)
        skipped = r.step()
        self.assertEqual(skipped['search_status'], 'duplicate_skipped')
        self.assertFalse(skipped['query_submitted']); self.assertEqual(a.queries, [])
        restarted = Research(self.root, r.llm, {'crossref': a, 'wikipedia': b})
        event = restarted.step()
        self.assertEqual((event['action'], event['provider']), ('R2', 'wikipedia'))
        self.assertEqual(b.queries, ['thermal resistance heat flux'])
        self.assertEqual(len(r.llm.requests), 1)
        used, unused = self.state()['nodes']['q1']['concept_candidates']
        self.assertEqual(len(used['submitted_queries']), 1)
        self.assertEqual(unused['submitted_queries'], [])
        self.assertEqual(unused['selected_rounds'], [])
        self.assertEqual(used['selected_rounds'], [1])
        self.assertEqual(unused['discovery_event'], skipped['tree']['q1']['concept_candidates'][1]['discovery_event'])

    def test_failed_and_unsubmitted_queries_do_not_block_retry(self):
        r = self.make([plan(['thermal resistance'])])
        self.seed_history(r, [{'provider': 'fixture', 'query': 'thermal resistance', 'status': status,
            'query_submitted': submitted} for status, submitted in [('failed', True), ('deferred', False),
            ('rate_limited', True), ('unavailable', True), ('empty', False)]])
        self.assertFalse(r.step()['search_blocked'])

    def test_duplicate_effective_queries_normalize_case_and_spacing_without_merging_syntax(self):
        entry = {'provider': 'pubmed', 'query': '(Thermal resistance)',
                 'request_parameters': {'term': '(Thermal resistance)'}}
        old = {'provider': 'pubmed', 'query': '(thermal  resistance)',
               'request_parameters': {'term': '(thermal  resistance)'}, 'reference': 'original'}
        self.assertEqual(r1.repeated(entry, [old]), old)
        self.assertIsNone(r1.repeated({**entry, 'query': 'Thermal resistance'}, [old]))

    def test_unused_candidates_reappear_and_known_discoveries_keep_original_provenance(self):
        r = self.make([plan(['heat flux'], ['thermal diffusivity']),
            {'decision': 'retry', 'reason': 'More research.'},
            plan(['thermal diffusivity'], ['THERMAL diffusivity'])],
            {'fixture': FixtureSearch([{'status': 'empty', 'results': []}])})
        first = r.step(); r.step(); r.step(); second = r.step()
        candidate = self.state()['nodes']['q1']['concept_candidates'][0]
        self.assertEqual(candidate['discovery_event'], first['event_id'])
        self.assertEqual(candidate['considered_rounds'], [2])
        self.assertEqual(candidate['selected_rounds'], [2])
        self.assertEqual(candidate['submitted_queries'], [])
        self.assertEqual(second['search_plan']['new_concepts'], [])
        self.assertEqual(second['r1_projection']['term_context']['unused_candidates']['entries'][0]['term'],
                         'thermal diffusivity')

    def test_term_limit_and_exact_response_schema(self):
        validate('R1', plan([]), 1); validate('R1', plan(['heat flux']), 1)
        for value in (plan(['heat flux', 'thermal resistance']), {'keywords': ['heat']}, plan(new=['term'] * 7)):
            with self.subTest(value=value), self.assertRaises(ValueError): validate('R1', value, 1)
        r = Research(self.root, ScriptedLLM([plan(['heat flux'])]), {})
        r.initialize('Heat?', strategy='medical', context_budget=40000)
        event = r.step()
        self.assertEqual(event['r1_projection']['term_limit'], 4)
        self.assertNotIn('query_profiles', event['r1_projection'])

    def test_candidates_survive_r1_journal_repair_without_another_call(self):
        r = self.make([plan([], ['thermal diffusivity'])])
        def fault(point):
            if point == 'prepared': raise RuntimeError('simulated crash')
        with self.assertRaises(RuntimeError): r.step(fault=fault)
        operation = r.store.recovery_status()['operations'][0]['id']
        r.store.repair(operation, apply=True)
        restarted = Research(self.root, ScriptedLLM([]), {})
        self.assertEqual(restarted.run(2)['status'], 'waiting_for_r4_upgrade')
        self.assertEqual(len(self.state()['nodes']['q1']['concept_candidates']), 1)
        self.assertEqual(len(r.llm.requests), 1)
        self.assertEqual(len(read_records(self.root)), 1)

    def test_projection_relevance_rotation_omissions_and_untrusted_filter(self):
        state = tree.initial('Thermal resistance?', ['fixture'])
        node = state['nodes']['q1']; node['search_round'] = 4
        node['previous_search_terms'] = [f'thermal term {i}' for i in range(30)]
        node['concept_candidates'] = [{'term': f'thermal candidate {i}', 'order': i + 1,
            'selected_rounds': [], 'submitted_queries': [], 'last_considered_round': 0} for i in range(25)]
        one = r1.context(state, [], {}, 'q1')
        self.assertEqual(one, r1.context(state, [], {}, 'q1'))
        entries = one['term_context']['unused_candidates']['entries']
        self.assertEqual(len(entries), 10)
        self.assertEqual(one['term_context']['unused_candidates']['omitted_count'], 15)
        for entry in entries: node['concept_candidates'][entry['order'] - 1]['last_considered_round'] = 5
        two = r1.context(state, [], {}, 'q1')
        self.assertTrue({r['order'] for r in entries}.isdisjoint({r['order'] for r in two['term_context']['unused_candidates']['entries']}))
        self.assertLess(len(dumps(two).encode()), 6500)

    def test_blocked_node_does_not_starve_other_living_node(self):
        r = self.make([plan([]), plan(['heat capacity'])])
        with r.store.lock():
            token, docs, eqs, ledger = r.store.read(); state = self.state()
            state['next_node'] = 3
            state['nodes']['q2'] = tree.node('q2', 'Heat capacity?', 'q1')
            state['nodes']['q1']['child_ids'] = ['q2']
            tree.refresh(state, docs)
            r.store.publish(docs, eqs, ledger, token, files={'research/state.json': dumps(state)})
        self.assertTrue(r.step()['search_blocked'])
        event = r.step()
        self.assertEqual((event['action'], event['node_id']), ('R1', 'q2'))
        self.assertTrue(self.state()['nodes']['q1']['search_blocked'])
