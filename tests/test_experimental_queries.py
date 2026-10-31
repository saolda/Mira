"""Opt-in OR compilers share the established retrieval and recovery safeguards."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from mira import query_profiles as profiles, r1
from mira.decisions import ScriptedLLM
from mira.format import dumps, loads
from mira.providers import EuropePMCSearch, PubMedSearch
from mira.research import Research
from mira.search import FixtureSearch


TERMS = ['inflammatory pseudotumor', 'organizing pneumonia', 'necrotizing pneumonia']


def experimental_profile(provider, *, max_terms=2):
    original = 'pubmed_balanced' if provider == 'pubmed' else 'europe_pmc_balanced'
    profile = deepcopy(profiles.select(profiles.registry(), original))
    profile.update(id=provider + '_experimental_or', max_terms=max_terms,
                   compiler='pubmed_or' if provider == 'pubmed' else 'phrase_or', combination='OR')
    return profiles.validate(profile)


def plan(terms):
    return {'new_concepts': [], 'search_concepts': terms, 'reason': 'Fixture alternative diagnoses.'}


class ExperimentalCompilerTests(unittest.TestCase):
    def test_compilers_require_explicit_profiles_and_keep_default_profiles_unchanged(self):
        registry = profiles.registry()
        self.assertFalse({'pubmed_or', 'phrase_or'} & {p['compiler'] for p in registry['profiles']})
        for provider, original in [('pubmed', 'pubmed_balanced'), ('europe_pmc', 'europe_pmc_balanced')]:
            with self.subTest(provider=provider):
                profile = experimental_profile(provider)
                self.assertEqual(profiles.compile(provider, TERMS, profile)['retained_concepts'], TERMS[:2])
                self.assertEqual(profiles.select(registry, original)['combination'], 'AND')
                with self.assertRaisesRegex(ValueError, 'invalid compiler rules'):
                    profiles.validate({**profile, 'combination': 'AND'})
                with self.assertRaisesRegex(ValueError, 'incompatible'):
                    profiles.compile('arxiv', TERMS, profile)

    def test_or_queries_keep_ordered_whole_concept_prefixes(self):
        expected = {'pubmed': '(inflammatory pseudotumor) OR (organizing pneumonia)',
                    'europe_pmc': '"inflammatory pseudotumor" OR "organizing pneumonia"'}
        for provider, query in expected.items():
            with self.subTest(provider=provider):
                result = profiles.compile(provider, TERMS, experimental_profile(provider))
                self.assertEqual(result['query'], query)
                self.assertEqual(result['original_concepts'], TERMS)
                self.assertEqual(result['retained_concepts'], TERMS[:2])
                self.assertEqual(result['discarded_concepts'], TERMS[2:])
                self.assertEqual(result['request_parameters'], {profiles.QUERY_PARAMETERS[provider]: query})
                self.assertFalse(result['legacy_query_semantics'])
        self.assertEqual(TERMS, ['inflammatory pseudotumor', 'organizing pneumonia', 'necrotizing pneumonia'])

    def test_pubmed_or_preserves_existing_unquoted_literal_term_handling(self):
        terms = ['FDG PET/CT', 'non-small cell lung cancer']
        original = profiles.select(profiles.registry(), 'pubmed_balanced')
        old = profiles.compile('pubmed', terms, original)['query']
        new = profiles.compile('pubmed', terms, experimental_profile('pubmed'))['query']
        self.assertEqual(new, '(FDG PET/CT) OR (non-small cell lung cancer)')
        self.assertEqual(new, old.replace(' AND ', ' OR '))
        unusual = ['a "quoted" term', 'back\\slash [field]']
        self.assertEqual(profiles.compile('pubmed', unusual, experimental_profile('pubmed'))['query'],
                         profiles.compile('pubmed', unusual, original)['query'].replace(' AND ', ' OR '))

    def test_phrase_or_quotes_and_escapes_without_changing_unicode(self):
        terms = ['a "quoted" term', 'back\\slash β-catenin']
        result = profiles.compile('europe_pmc', terms, experimental_profile('europe_pmc'))
        self.assertEqual(result['query'], '"a \\"quoted\\" term" OR "back\\\\slash β-catenin"')
        self.assertEqual(result['request_parameters']['query'], result['query'])
        for invalid in ['organizing pneumonia OR cancer', 'pubmed:infection', 'infection[Title]']:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                r1.validate_concepts([invalid])

    def test_compiled_query_identity_preserves_connectors_prefixes_and_order(self):
        for provider in ('pubmed', 'europe_pmc'):
            with self.subTest(provider=provider):
                profile = experimental_profile(provider)
                first = profiles.compile(provider, TERMS, profile)
                history = [{**first, 'reference': 'research/results/original.json'}]
                # Profile metadata and discarded concepts do not change actual request identity.
                renamed = {**profile, 'id': 'other_or_profile', 'version': 2}
                equivalent = profiles.compile(provider, TERMS[:2] + ['pulmonary hamartoma'], renamed)
                self.assertEqual(r1.repeated(equivalent, history), history[0])
                and_profile = {**profile, 'compiler': 'pubmed' if provider == 'pubmed' else 'phrase_and',
                               'combination': 'AND'}
                self.assertIsNone(r1.repeated(profiles.compile(provider, TERMS, and_profile), history))
                self.assertIsNone(r1.repeated(profiles.compile(provider, TERMS[:2][::-1], profile), history))
                self.assertIsNone(r1.repeated({**first, 'request_parameters': {'different': first['query']}}, history))
                self.assertIsNone(r1.repeated({**first, 'provider': 'another_provider'}, history))

    def test_real_adapters_receive_exact_or_queries_and_retain_abstracts(self):
        pubmed_xml = (b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1234</PMID><Article>'
                      b'<ArticleTitle>Fixture diagnostic comparison</ArticleTitle><Abstract><AbstractText>'
                      b'Fixture abstract; no clinical conclusion.</AbstractText></Abstract>'
                      b'</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>')
        responses = {
            'pubmed': [json.dumps({'esearchresult': {'idlist': ['1234']}}).encode(), pubmed_xml],
            'europe_pmc': [json.dumps({'resultList': {'result': [{'source': 'MED', 'id': '5678',
                'title': 'Other fixture diagnostic comparison',
                'abstractText': 'Other fixture abstract; no clinical conclusion.'}]}}).encode()]}
        for provider, adapter_type in [('pubmed', PubMedSearch), ('europe_pmc', EuropePMCSearch)]:
            with self.subTest(provider=provider):
                requests = []
                def opener(request, timeout):
                    requests.append(request)
                    return BytesIO(responses[provider].pop(0))
                query = profiles.compile(provider, TERMS, experimental_profile(provider))['query']
                result = adapter_type(opener=opener).search(query, before_request=lambda endpoint, params: None)
                self.assertEqual(parse_qs(urlsplit(requests[0].full_url).query)[profiles.QUERY_PARAMETERS[provider]], [query])
                self.assertEqual(len(requests), 2 if provider == 'pubmed' else 1)
                self.assertEqual(result['status'], 'ok')
                self.assertEqual(result['results'][0]['content_kind'], 'abstract')
                self.assertIn('no clinical conclusion.', result['results'][0]['content'])


class ExperimentalRoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / 'memory'
        self.registry = profiles.registry()
        self.registry['profiles'].extend([experimental_profile(p) for p in ('pubmed', 'europe_pmc')])
        for profile in self.registry['profiles']:
            profile['min_interval_seconds'] = 0
        self.registry['host_min_intervals'] = {host: 0 for host in self.registry['host_min_intervals']}
        self.profile_path = self.base / 'profiles.json'
        self.strategy_path = self.base / 'strategies.json'
        self.strategy_path.write_text(dumps([{'id': 'medical', 'name': 'Experimental medical',
            'description': 'Fixture OR profiles, explicitly selected.', 'databases': ['pubmed', 'europe_pmc'],
            'profiles': {p: p + '_experimental_or' for p in ('pubmed', 'europe_pmc')}}]))

    def make(self, responses, adapters, **kwargs):
        self.profile_path.write_text(dumps(self.registry))
        self.model = ScriptedLLM(responses)
        research = Research(self.root, self.model, adapters, **kwargs)
        research.initialize('Fixture diagnostic question?', strategy='medical', registry=self.strategy_path,
                            profile_registry=self.profile_path, context_budget=30000)
        return research

    def state(self):
        return loads((self.root / 'research/state.json').read_text())

    def test_shared_r1_then_one_provider_per_action_with_frozen_experimental_profiles(self):
        adapters = {p: FixtureSearch([{'status': 'empty', 'results': []}]) for p in ('pubmed', 'europe_pmc')}
        research = self.make([plan(TERMS[:2])], adapters)
        first = research.step()
        self.assertEqual(first['r1_projection']['term_limit'], 2)
        # Restart must use the frozen experiment configuration, not changed registries.
        frozen = deepcopy(self.state()['strategies'])
        self.profile_path.write_text('{}'); self.strategy_path.write_text('[]')
        research = Research(self.root, self.model, adapters)
        for index, provider in enumerate(('pubmed', 'europe_pmc'), 1):
            event = research.step()
            self.assertEqual((event['action'], event['provider']), ('R2', provider))
            self.assertEqual(event['database_index_after'], index)
            self.assertTrue(event['query_submitted'])
            self.assertEqual(adapters[provider].queries, [profiles.compile(provider, TERMS[:2], experimental_profile(provider))['query']])
        self.assertEqual(len(self.model.requests), 1)
        self.assertEqual(self.state()['strategies'], frozen)

    def test_duplicate_provider_prefix_skips_network_while_other_or_query_proceeds(self):
        next(p for p in self.registry['profiles'] if p['id'] == 'pubmed_experimental_or')['max_terms'] = 1
        adapters = {'pubmed': FixtureSearch([{'status': 'empty', 'results': []}]),
                    'europe_pmc': FixtureSearch([{'status': 'empty', 'results': []}] * 2)}
        research = self.make([plan(TERMS[:2]), {'decision': 'unresolved', 'reason': 'Fixture evidence gap.'},
                              plan([TERMS[0], TERMS[2]])], adapters)
        self.assertEqual([research.step()['action'] for _ in range(5)], ['R1', 'R2', 'R2', 'R4', 'R1'])
        skipped = Research(self.root, self.model, adapters).step()
        self.assertEqual((skipped['provider'], skipped['search_status']), ('pubmed', 'duplicate_skipped'))
        self.assertFalse(skipped['query_submitted'])
        self.assertEqual(adapters['pubmed'].queries, ['(inflammatory pseudotumor)'])
        event = research.step()
        self.assertEqual((event['provider'], event['search_status']), ('europe_pmc', 'empty'))
        self.assertEqual(adapters['europe_pmc'].queries,
                         ['"inflammatory pseudotumor" OR "organizing pneumonia"',
                          '"inflammatory pseudotumor" OR "necrotizing pneumonia"'])
        self.assertEqual(len(self.model.requests), 3)

    def test_deferred_or_request_keeps_exact_frozen_query_and_cooldown_after_restart(self):
        now = [1000.]
        adapters = {'pubmed': FixtureSearch([{'status': 'rate_limited', 'results': [], 'retry_after': '120'},
                                             {'status': 'empty', 'results': []}]),
                    'europe_pmc': FixtureSearch([{'status': 'empty', 'results': []}])}
        research = self.make([plan(TERMS[:2])], adapters, clock=lambda: now[0])
        research.step()
        deferred = research.step()
        self.assertEqual(deferred['search_status'], 'rate_limited')
        self.assertEqual(deferred['retry_at'], 1120.)
        self.assertEqual(research.step()['provider'], 'europe_pmc')
        before = self.state()
        self.assertEqual(research.step()['status'], 'waiting_for_provider')
        self.assertEqual(self.state(), before)
        self.profile_path.write_text('{}')
        now[0] = deferred['retry_at']
        resumed = Research(self.root, self.model, adapters, clock=lambda: now[0]).step()
        self.assertTrue(resumed['deferred_retry'])
        self.assertEqual(resumed['query'], deferred['query'])
        self.assertEqual(resumed['database_index_after'], 2)
        self.assertEqual(adapters['pubmed'].queries, ['(inflammatory pseudotumor) OR (organizing pneumonia)'] * 2)
        self.assertEqual(len(self.model.requests), 1)

    def test_all_repeated_or_queries_block_without_another_provider_request(self):
        adapters = {p: FixtureSearch([{'status': 'empty', 'results': []}]) for p in ('pubmed', 'europe_pmc')}
        research = self.make([plan(TERMS[:2]), {'decision': 'unresolved', 'reason': 'Fixture evidence gap.'},
                              plan(TERMS[:2]), {'decision': 'unresolved', 'reason': 'No distinct fixture search.'}], adapters)
        for _ in range(4): research.step()
        blocked = research.step()
        self.assertTrue(blocked['search_blocked'])
        self.assertEqual(blocked['search_blocked_reason'], 'completed_queries_only')
        self.assertEqual(len(blocked['repeated_queries']), 2)
        self.assertEqual(research.step()['action'], 'R4')
        self.assertEqual(self.state()['nodes']['q1']['status'], 'exhausted')
        self.assertEqual(sum(len(adapter.queries) for adapter in adapters.values()), 2)
        self.assertEqual(len(self.model.requests), 4)

    def test_or_outcome_journal_recovery_does_not_resubmit_provider_request(self):
        adapters = {p: FixtureSearch([{'status': 'empty', 'results': []}]) for p in ('pubmed', 'europe_pmc')}
        research = self.make([plan(TERMS[:2])], adapters)
        research.step()
        def fault(stage):
            if stage == 'prepared': raise RuntimeError('Fixture interrupted publication')
        with self.assertRaisesRegex(RuntimeError, 'interrupted publication'):
            research.step(fault=fault)
        pending = research.store.recovery_status()['operations'][0]
        research.store.repair(pending['id'], apply=True)
        event = Research(self.root, self.model, adapters).step()
        self.assertEqual((event['action'], event['provider']), ('R2', 'europe_pmc'))
        self.assertEqual(adapters['pubmed'].queries, ['(inflammatory pseudotumor) OR (organizing pneumonia)'])
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'], 2)
        self.assertEqual(len(self.model.requests), 1)


if __name__ == '__main__':
    unittest.main()
