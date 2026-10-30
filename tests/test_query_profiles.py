"""Query grammar, durable provider rounds, pacing and interrupted I/O regressions."""
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import format_datetime
from io import BytesIO
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from mira import query_profiles as profiles, retrieval, research_tree as tree
from mira.decisions import ScriptedLLM
from mira.experiments import file_hashes
from mira.format import dumps, loads
from mira.providers import PubMedSearch
from mira.research import Research
from mira.search import FixtureSearch
from test_research import evidence, decision


def legacy_snapshot(strategy, data):
    return {k:v for k,v in strategy.items() if k != 'profiles'}


class Clock:
    def __init__(self): self.value = 1000.; self.sleeps = []
    def __call__(self): return self.value
    def sleep(self, delay): self.sleeps.append(delay); self.value += delay
    def advance(self, delay): self.value += delay


class ProfileTests(unittest.TestCase):
    def test_initial_profiles_and_strategy_assignments(self):
        from mira.strategies import registry
        data = profiles.registry()
        self.assertEqual({p['id']:p['max_terms'] for p in data['profiles']}, {
            'default':6,'pubmed_balanced':3,'europe_pmc_balanced':3,'openalex_broad':3,
            'crossref_bibliographic':4,'wikipedia_general':3,'arxiv_subject':3,'eric_education':4})
        for strategy in registry():
            self.assertEqual(set(strategy['profiles']), set(strategy['databases']))
            for provider, identity in strategy['profiles'].items(): profiles.select(data, identity, provider)
        self.assertEqual(set(profiles.select(data,'default')['providers']),set(profiles.PROVIDERS))
        # Several profiles may serve one provider; one profile may serve several.
        alternate=deepcopy(profiles.select(data,'pubmed_balanced'));alternate['id']='pubmed_focused';alternate['max_terms']=2
        self.assertEqual(profiles.validate(alternate)['providers'],['pubmed'])
        shared=deepcopy(profiles.select(data,'europe_pmc_balanced'));shared.update(id='shared',providers=['europe_pmc','eric'])
        profiles.validate(shared)

    def test_provider_syntax_prefixes_and_escaping(self):
        data=profiles.registry();terms=['volume doubling time','spiculated nodule','lung neoplasms','infection']
        expected={'pubmed_balanced':'(volume doubling time) AND (spiculated nodule) AND (lung neoplasms)',
            'europe_pmc_balanced':'"volume doubling time" AND "spiculated nodule" AND "lung neoplasms"',
            'openalex_broad':'volume doubling time spiculated nodule lung neoplasms',
            'crossref_bibliographic':'volume doubling time spiculated nodule lung neoplasms infection',
            'wikipedia_general':'volume doubling time spiculated nodule lung neoplasms',
            'arxiv_subject':'all:"volume doubling time" AND all:"spiculated nodule" AND all:"lung neoplasms"',
            'eric_education':'"volume doubling time" AND "spiculated nodule" AND "lung neoplasms" AND "infection"'}
        for identity,query in expected.items():
            profile=profiles.select(data,identity);provider=profile['providers'][0]
            result=profiles.compile(provider,terms,profile)
            self.assertEqual(result['query'],query)
            self.assertEqual(result['retained_concepts'],terms[:profile['max_terms']])
            self.assertEqual(result['discarded_concepts'],terms[profile['max_terms']:])
            self.assertEqual(result['original_concepts'],terms)
            self.assertEqual(result['request_parameters'],{profiles.QUERY_PARAMETERS[provider]:query})
        escaped=profiles.compile('arxiv',['a "quoted" term','back\\slash'],profiles.select(data,'arxiv_subject'))
        self.assertEqual(escaped['query'],'all:"a \\"quoted\\" term" AND all:"back\\\\slash"')
        self.assertNotIn('"',profiles.compile('pubmed',terms,profiles.select(data,'pubmed_balanced'))['query'])
        for count in (2,3,4):
            profile=deepcopy(profiles.select(data,'pubmed_balanced'));profile['max_terms']=count
            self.assertEqual(profiles.compile('pubmed',terms,profile)['retained_concepts'],terms[:count])

    def test_default_and_exact_legacy_arxiv_semantics(self):
        profile=profiles.select(profiles.registry(),'default')
        self.assertEqual(profiles.compile('arxiv',['Monte Carlo','dropout'],profile)['query'],'all:"Monte" AND all:"Carlo" AND all:"dropout"')
        self.assertEqual(profiles.legacy_query('arxiv',['id:1234.56789']),'id:1234.56789')
        self.assertEqual(profiles.compile('crossref',['Monte Carlo','dropout'],profile)['query'],'Monte Carlo dropout')
        self.assertEqual(profiles.legacy_query('pubmed',[' '.join(['old']*10)]*8),' '.join(['old']*80))

    def test_configuration_validation(self):
        good=profiles.select(profiles.registry(),'pubmed_balanced')
        changes=[{'max_terms':0},{'max_terms':7},{'max_terms':True},{'max_attempts':0},{'max_attempts':1.5},
            {'version':0},{'version':True},{'min_interval_seconds':-1},{'retry_initial_seconds':0},
            {'retry_initial_seconds':20,'retry_max_seconds':10},{'retry_max_seconds':float('inf')},
            {'providers':['arxiv']},{'providers':['pubmed','pubmed']},{'compiler':'invented'},
            {'escaping':'none'},{'quoting':'exact'},{'id':'Bad Profile'}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):profiles.validate({**good,**change})
        with self.assertRaises(ValueError): profiles.compile('arxiv',['a','b'],good)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profiles.json';data=profiles.registry()
            for bad in ({**data,'profiles':data['profiles']*2},{**data,'host_min_intervals':{'h':-1}},
                        {**data,'profiles':data['profiles'][1:]},{}):
                path.write_text(dumps(bad))
                with self.assertRaises(ValueError):profiles.registry(path)
            from mira.strategies import registry
            path.write_text(dumps([{'id':'one','name':'One','description':'One.','databases':['arxiv']}]))
            with self.assertRaises(ValueError):registry(path)


class RoundTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'run';self.clock=Clock()
        data=profiles.registry()
        for p in data['profiles']:p.update(retry_initial_seconds=2,retry_max_seconds=8,max_attempts=3)
        data['host_min_intervals']={h:0 for h in data['host_min_intervals']}
        self.registry=self.base/'profiles.json';self.registry.write_text(dumps(data))

    def make(self, responses=(), outcomes=None, databases=None, **kwargs):
        self.llm=ScriptedLLM([{'keywords':['heat transfer','thermal insulation']},*responses])
        self.adapters=outcomes or {'a':FixtureSearch([{'status':'empty','results':[]}])}
        self.r=Research(self.root,self.llm,self.adapters,clock=self.clock,sleep=self.clock.sleep)
        self.r.initialize('How does heat transfer work?',databases or list(self.adapters),profile_registry=self.registry,context_budget=30000,**kwargs)
        self.assertEqual(self.r.step()['action'],'R1')
        return self.r

    def state(self):return loads((self.root/'research/state.json').read_text())

    def change(self, operation):
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=self.state();operation(state);tree.refresh(state,docs)
            self.r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})

    def restart(self):
        self.r=Research(self.root,self.llm,self.adapters,clock=self.clock,sleep=self.clock.sleep)
        return self.r

    def test_snapshots_immutable_and_disk_configuration_not_reread(self):
        self.make()
        snap=deepcopy(self.state()['strategies'])
        self.registry.write_text('{}')
        self.assertEqual(self.restart().step()['status'],'committed')
        self.assertEqual(self.state()['strategies'],snap)
        with self.assertRaisesRegex(ValueError,'immutable'):
            self.change(lambda s:s['strategies'][0]['query_profiles']['a'].update(max_terms=2))

    def test_legacy_experiment_queries_are_never_pruned_or_recompiled(self):
        with patch('mira.query_profiles.snapshot',side_effect=legacy_snapshot): self.make()
        self.change(lambda s:s['nodes']['q1'].update(keywords=['one two three four five six seven','extra']))
        e=self.restart().step()
        self.assertEqual(e['query'],'one two three four five six seven extra')
        self.assertIsNone(e['profile_id'])
        self.assertNotIn('query_profiles',self.state()['strategies'][0])

    def test_partially_completed_legacy_round_retains_cursor_without_inventing_results(self):
        self.llm=ScriptedLLM([decision()]);a=FixtureSearch([]);b=FixtureSearch([{'status':'empty','results':[]}])
        self.r=Research(self.root,self.llm,{'a':a,'b':b},clock=self.clock,sleep=self.clock.sleep)
        with patch('mira.query_profiles.snapshot',side_effect=legacy_snapshot):
            self.r.initialize('Legacy question?',['a','b'],context_budget=30000)
        self.change(lambda s:s['nodes']['q1'].update(keywords=['old multiword concept'],next_database_index=1))
        e=self.r.step()
        self.assertEqual((e['provider'],e['query'],e['database_index_after']),('b','old multiword concept',2))
        self.assertEqual(a.queries,[])
        self.assertEqual(self.state()['nodes']['q1']['legacy_completed_provider_indices'],[0])
        self.assertEqual(self.r.step()['action'],'R4')

    def test_named_strategy_r2_records_original_retained_discarded_and_profile(self):
        concepts=['volume doubling time','spiculated nodule','lung neoplasms','pulmonary infection','interval growth']
        model=ScriptedLLM([{'keywords':concepts}]);adapter=FixtureSearch([{'status':'empty','results':[]}])
        self.r=Research(self.root,model,{'pubmed':adapter},clock=self.clock,sleep=self.clock.sleep)
        self.r.initialize('Medical question?',strategy='medical',profile_registry=self.registry,context_budget=30000)
        self.r.step();event=self.r.step()
        self.assertEqual(event['profile_id'],'pubmed_balanced')
        self.assertEqual(event['profile_version'],1)
        self.assertEqual(event['original_concepts'],concepts)
        self.assertEqual(event['retained_concepts'],concepts[:3])
        self.assertEqual(event['discarded_concepts'],concepts[3:])
        self.assertEqual(adapter.queries,['(volume doubling time) AND (spiculated nodule) AND (lung neoplasms)'])
        saved=loads((self.root/event['evidence_ref']).read_text())
        for key in ['original_concepts','retained_concepts','discarded_concepts','profile_config','query','profile_version']:
            self.assertEqual(saved[key],event[key])
        self.assertEqual(len(model.requests),1)

    def test_fresh_node_can_generate_concepts_while_other_node_waits(self):
        self.make(responses=[{'keywords':['conductivity','insulation']}],outcomes={
            'a':FixtureSearch([{'status':'rate_limited','results':[]}])})
        self.r.step()
        def add(s):
            s['nodes']['q1']['child_ids']=['q2'];s['next_node']=3
            s['nodes']['q2']=tree.node('q2','How does conductivity affect heat?','q1')
        self.change(add)
        e=self.r.step()
        self.assertEqual((e['action'],e['node_id']),('R1','q2'))
        self.assertEqual(self.state()['nodes']['q1']['keywords'],['heat transfer','thermal insulation'])

    def test_deferred_work_prevents_capacity_exhaustion(self):
        from mira.branching import assess
        from test_gardener import seed
        self.make(outcomes={'a':FixtureSearch([{'status':'rate_limited','results':[]}])})
        self.r.step()
        # The controller must retain the round even when direct research fills R5.
        seed(self.r,own=1,child=0,leaf=0,living=('q1',))
        self.change(lambda s:s.update(research_capacity_tokens=1))
        with self.r.store.lock():
            _,docs,eqs,_=self.r.store.read();s=self.state()
            assess(s,docs,eqs,self.llm.model,self.llm.settings)
        self.assertEqual(s['nodes']['q1']['status'],'living')

    def test_native_http_429_and_long_retry_after_are_preserved(self):
        def opener(req,timeout):
            raise HTTPError(req.full_url,429,'rate limit',{'Retry-After':'99999'},BytesIO(b'limit'))
        self.make(outcomes={'pubmed':PubMedSearch(opener=opener)},databases=['pubmed'])
        e=self.r.step()
        self.assertEqual((e['search_status'],e['attempts']),('rate_limited',1))
        self.assertEqual(e['retry_at'],100999)
        saved=loads((self.root/e['evidence_ref']).read_text())
        self.assertEqual(saved['http_status'],429)
        self.assertEqual(saved['retry_after'],'99999')
        self.assertEqual(len(saved['requests']),1)

    def test_initial_success_empty_failure_each_advance_once_and_r3_has_precedence(self):
        self.make(responses=[{'summary':'','results':[]}],outcomes={
            'a':FixtureSearch([evidence()]),'b':FixtureSearch([{'status':'empty','results':[]}]),
            'c':FixtureSearch([{'status':'failed','results':[]}])})
        e=self.r.step();self.assertEqual((e['search_status'],e['database_index_after']),('ok',1))
        self.assertEqual(self.restart().step()['action'],'R3')
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],1)
        for status,index in [('empty',2),('failed',3)]:
            e=self.r.step();self.assertEqual((e['search_status'],e['database_index_after']),(status,index))
        self.assertEqual(self.adapters['b'].queries,['heat transfer thermal insulation'])

    def test_rate_limit_deferred_restart_wait_no_cycles_or_llm_then_retry_and_r4(self):
        self.make(responses=[decision('retry')],outcomes={'a':FixtureSearch([
            {'status':'rate_limited','results':[],'retry_after':'10000'},{'status':'empty','results':[]}]),
            'b':FixtureSearch([{'status':'empty','results':[]}])})
        first=self.r.step();self.assertTrue(first['query_submitted'])
        self.assertEqual(first['search_status'],'rate_limited')
        self.assertEqual(self.r.step()['provider'],'b')
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],2)
        before=file_hashes(self.root);calls=len(self.llm.requests);cycles=self.state()['research_cycles']
        waiting=self.restart().step()
        self.assertEqual(waiting['status'],'waiting_for_provider');self.assertEqual(waiting['retry_at'],11000)
        self.assertEqual(file_hashes(self.root),before)
        self.assertEqual((len(self.llm.requests),self.state()['research_cycles']),(calls,cycles))
        self.clock.advance(10000)
        again=self.r.step()
        self.assertTrue(again['deferred_retry']);self.assertEqual(again['query'],first['query'])
        self.assertEqual(again['attempts'],2);self.assertEqual(again['database_index_after'],2)
        self.assertEqual(self.state()['nodes']['q1']['deferred_searches'],[])
        self.assertEqual(self.state()['provider_availability']['a']['consecutive_rate_limits'],0)
        self.assertEqual(self.r.step()['action'],'R4')
        node=self.state()['nodes']['q1'];self.assertIsNone(node['keywords']);self.assertEqual(node['next_database_index'],0)

    def test_cooldown_deferral_is_not_submitted_and_has_zero_attempts(self):
        self.make()
        self.change(lambda s:s['provider_availability'].update(a={'next_request_at':1100,'consecutive_rate_limits':2}))
        e=self.r.step()
        self.assertEqual((e['search_status'],e['query_submitted'],e['attempts']),('deferred',False,0))
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],1)
        self.assertEqual(self.adapters['a'].queries,[])
        self.assertEqual(self.r.step()['status'],'waiting_for_provider')

    def test_exhausted_attempts_become_unavailable_without_second_index_advance(self):
        self.make(responses=[decision()],outcomes={'a':FixtureSearch([{'status':'rate_limited','results':[]}]*3)})
        first=self.r.step();self.assertEqual(first['retry_at'],1002)
        self.clock.advance(2);second=self.r.step();self.assertEqual(second['retry_at'],1006)
        self.clock.advance(4);third=self.r.step()
        self.assertEqual(third['search_status'],'unavailable')
        self.assertEqual(third['database_index_after'],1)
        self.assertEqual(self.state()['nodes']['q1']['deferred_searches'],[])
        self.assertEqual(len(self.adapters['a'].queries),3)
        self.assertEqual(self.r.step()['action'],'R4')

    def test_retry_after_dates_and_fallback_backoff(self):
        p=profiles.select(profiles.registry(),'default')
        date=format_datetime(datetime.fromtimestamp(100000,tz=timezone.utc),usegmt=True)
        self.assertEqual(retrieval.retry_time(date,1000,1,p),100000)
        self.assertEqual(retrieval.retry_time('99999',1000,10,p),100999)
        self.assertEqual(retrieval.retry_time('nonsense',1000,1,p),1060)
        self.assertEqual(retrieval.retry_time('-1',1000,2,p),1120)
        self.assertEqual(retrieval.retry_time(None,1000,10000,p),4600)
        self.assertEqual(retrieval.retry_time('0',1000,1,p),1000)

    def test_other_nodes_run_while_one_query_waits_and_keep_distinct_queries(self):
        self.make(outcomes={'a':FixtureSearch([{'status':'rate_limited','results':[],'retry_after':'10'},
            {'status':'empty','results':[]},{'status':'empty','results':[]}])})
        original=self.r.step()['query']
        def add(s):
            s['nodes']['q1']['child_ids']=['q2'];s['next_node']=3
            s['nodes']['q2']=tree.node('q2','How does insulation change heat?','q1')
            s['nodes']['q2'].update(keywords=['insulation','conductivity'],priority=8)
            s['nodes']['q1']['priority']=0
        self.change(add)
        e=self.r.step();self.assertEqual((e['node_id'],e['search_status']),('q2','deferred'))
        queues={i:n['deferred_searches'][0]['query'] for i,n in self.state()['nodes'].items()}
        self.assertEqual(queues['q1'],original);self.assertNotEqual(queues['q1'],queues['q2'])
        self.assertEqual(self.r.step()['status'],'waiting_for_provider')
        self.clock.advance(10)
        self.assertEqual(self.restart().step()['query'],queues['q2'])
        self.change(lambda s:s['nodes']['q2'].update(priority=0))
        self.assertEqual(self.r.step()['query'],queues['q1'])
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],1)

    def test_pending_sources_processed_before_retry_or_other_provider(self):
        self.make(responses=[{'summary':'','results':[]}],outcomes={
            'a':FixtureSearch([{'status':'rate_limited','results':[]}, {'status':'empty','results':[]}]),
            'b':FixtureSearch([evidence()])})
        self.r.step();self.r.step();self.clock.advance(3)
        self.assertEqual(self.r.step()['action'],'R3')
        self.assertEqual(self.r.step()['provider'],'a')
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],2)

    def test_pubmed_protocol_host_pacing_and_credential_free_parameter_logging(self):
        calls=[];secret='private-fixture-api-key'
        xml=b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article><ArticleTitle>A trial</ArticleTitle><Abstract><AbstractText>P &lt; 0.05 and n &gt; 10</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>'
        responses=iter([json.dumps({'esearchresult':{'idlist':['1']}}).encode(),xml])
        def opener(req,timeout):calls.append((self.clock(),req.full_url));return BytesIO(next(responses))
        data=loads(self.registry.read_text());data['host_min_intervals']['eutils.ncbi.nlm.nih.gov']=1
        self.registry.write_text(dumps(data))
        self.make(outcomes={'pubmed':PubMedSearch(opener=opener,api_key=secret)},databases=['pubmed'])
        with self.r.execution(self.base/'logs'):
            e=self.r.step()
        self.assertEqual(len(calls),2);self.assertGreaterEqual(calls[1][0]-calls[0][0],1)
        self.assertEqual(parse_qs(urlsplit(calls[0][1]).query)['api_key'],[secret])
        saved=loads((self.root/e['evidence_ref']).read_text())
        self.assertEqual(saved['requests'][0]['parameters']['term'],e['query'])
        self.assertEqual(saved['requests'][1]['parameters']['id'],'1')
        payload=loads((self.root/saved['payload_ref']).read_text())
        self.assertEqual(payload['results'][0]['content'],'P < 0.05 and n > 10')
        for p in [*self.root.rglob('*.json'),*self.base.glob('logs/*.jsonl')]:self.assertNotIn(secret,p.read_text())

    def test_shared_host_defers_other_provider_until_clock_allows(self):
        a=FixtureSearch([{'status':'empty','results':[]}]);a.host='shared.example'
        b=FixtureSearch([{'status':'empty','results':[]}]);b.host='shared.example'
        data=loads(self.registry.read_text());data['host_min_intervals']['shared.example']=2;self.registry.write_text(dumps(data))
        self.make(outcomes={'a':a,'b':b})
        self.r.step();e=self.r.step()
        self.assertEqual((e['search_status'],e['query_submitted']),('deferred',False))
        self.assertEqual(self.r.step()['status'],'waiting_for_provider')
        self.clock.advance(2)
        e=self.restart().step();self.assertEqual((e['provider'],e['database_index_after']),('b',2))
        self.assertEqual(len(b.queries),1)

    def test_uncertain_network_submission_blocks_restart_until_explicit_acknowledgement(self):
        self.make()
        def interrupted():
            class ExitAdapter:
                def search(self,query):os._exit(71)
            Research(self.root,self.llm,{'a':ExitAdapter()},clock=self.clock,sleep=self.clock.sleep).step()
        proc=multiprocessing.get_context('fork').Process(target=interrupted);proc.start();proc.join(10)
        self.assertEqual(proc.exitcode,71)
        with self.assertRaisesRegex(ValueError,'uncertain_provider_submission'):self.restart().step()
        self.assertEqual(self.adapters['a'].queries,[])
        self.assertEqual(len(self.r.acknowledge_interrupted_searches()),1)
        self.assertEqual(self.r.step()['search_status'],'empty')
        self.assertEqual(len(self.adapters['a'].queries),1)

    def test_request_receipt_failure_blocks_dispatch_and_requires_inspection(self):
        self.make()
        original=retrieval.receipt
        def broken(research,identity,phase,value):
            if phase.startswith('network-'): raise OSError('disk full')
            return original(research,identity,phase,value)
        with patch('mira.retrieval.receipt',side_effect=broken):
            event=self.r.step()
        self.assertEqual(event['status'],'rejected')
        self.assertEqual(self.adapters['a'].queries,[])
        with self.assertRaisesRegex(ValueError,'uncertain_provider_submission'):self.restart().step()

    def test_journal_recovery_keeps_outcome_and_does_not_resubmit(self):
        self.make(responses=[decision()])
        def fault(stage):
            if stage=='prepared':raise RuntimeError('power loss')
        with self.assertRaisesRegex(RuntimeError,'power loss'):self.r.step(fault=fault)
        pending=self.r.store.recovery_status()['operations'][0]
        self.r.store.repair(pending['id'],apply=True)
        self.assertEqual(self.restart().step()['action'],'R4')
        self.assertEqual(len(self.adapters['a'].queries),1)
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],1)

    def test_deferred_query_tampering_rejected(self):
        self.make(outcomes={'a':FixtureSearch([{'status':'rate_limited','results':[]}])});self.r.step()
        with self.assertRaisesRegex(ValueError,'changed deferred query'):
            self.change(lambda s:s['nodes']['q1']['deferred_searches'][0].update(query='different query'))
