"""Initialization contracts, experiment-wide identities, temporary inputs and recovery."""
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mira import sources, strategies, research_tree as tree
from mira.decisions import ScriptedLLM
from mira.format import dumps, loads
from mira.interactions import read_records
from mira.research import Research
from mira.search import FixtureSearch
from test_research import evidence, draft, decision


def crash_cycle(root, stage, init=False):
    def fault(point):
        if point == stage: os._exit(74)
    llm = ScriptedLLM([{'strategy':'engineering','reason':'Technical question.'}] if init else [{"summary": "Scoped summary of all extracted results and their limitations.", 'results':[draft()]}])
    r = Research(root,llm,{})
    if init: r.initialize('Technical?',fault=fault, context_budget=12000)
    else: r.step(fault=fault)


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'run'

    def state(self): return loads((self.root/'research/state.json').read_text())

    def runner(self, responses=(), providers=None):
        self.llm = ScriptedLLM(responses)
        self.r = Research(self.root,self.llm,providers or {})
        return self.r

    def change(self, mutation):
        with self.r.store.lock():
            token,docs,eqs,ledger = self.r.store.read(); state = self.state()
            mutation(state)
            tree.refresh(state,docs)
            self.r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})

    def test_registry_domains_custom_file_and_validation(self):
        values = strategies.registry()
        self.assertEqual({s['id'] for s in values},{'general','engineering','humanities','biomedical','education'})
        self.assertEqual(strategies.select(values,'biomedical')['databases'][:2],['pubmed','europe_pmc'])
        path = Path(self.temp.name)/'strategies.json'
        path.write_text(dumps([{'id':'focused','name':'Focused','description':'One database.','databases':['arxiv']}]))
        with patch.dict(os.environ,{'MIRA_RESEARCH_STRATEGIES':str(path)}):
            r=self.runner(); state=r.initialize('Q?',strategy='focused', context_budget=12000)
        self.assertEqual(state['strategies'][0]['databases'],['arxiv'])
        for value in ([],[{'id':'oops'}],[{**values[0],'databases':['unknown']}],[values[0],values[0]]):
            path.write_text(dumps(value));self.assertRaises(ValueError,strategies.registry,path)

    def test_explicit_strategy_no_r0_and_freezes_registry_snapshot(self):
        r=self.runner();s=r.initialize('Engineering?',strategy='engineering', context_budget=12000)
        self.assertEqual(self.llm.requests,[])
        self.assertEqual(s['strategy_selection']['method'],'explicit')
        self.assertEqual(s['strategies'][0]['databases'],['arxiv','crossref','openalex','wikipedia'])
        self.assertEqual(r.inspect()['strategy']['id'],'engineering')
        self.assertRaisesRegex(ValueError,'immutable',self.change,lambda s:s['strategies'][0]['databases'].reverse())

    def test_r0_one_call_audited_then_never_recurs_on_resume_or_children(self):
        r=self.runner([{'strategy':'engineering','reason':'Technical question.'},{'keywords':['heat']}])
        s=r.initialize('Which heat-transfer techniques work?', context_budget=12000)
        self.assertEqual(len(self.llm.requests),1)
        self.assertEqual(s['research_cycles'],0)
        self.assertEqual(s['strategy_selection']['strategy'],'engineering')
        record=read_records(self.root)[0]
        self.assertEqual(record['request']['action'],'R0')
        self.assertEqual(record['request']['request']['messages'][0]['role'],'user')
        self.assertEqual(record['outcome']['action_committed'],'R0')
        def seed(s):
            s['nodes']['q2']=tree.node('q2','Child?','q1');s['nodes']['q1']['child_ids']=['q2'];s['next_node']=3
            s['nodes']['q1']['status']='exhausted'
            s['research_cycles_since_branching']=5
        self.change(seed)
        self.llm.responses=iter([{'questions':['New useful question?']},{'keywords':['heat']}])
        self.assertEqual(r.step()['action'],'R5')
        resumed=Research(self.root,self.llm,{})
        self.assertEqual(resumed.step()['action'],'R1')
        self.assertEqual(self.state()['strategy_selection'],s['strategy_selection'])
        self.assertEqual([x['request']['action'] for x in read_records(self.root)].count('R0'),1)

    def test_invalid_r0_leaves_no_research_state_and_cannot_start(self):
        values=[{'strategy':'unknown','reason':'guess'},{'strategy':'general'}, {'strategy':[],'reason':'bad'},
                {'strategy':'general','reason':'ok','databases':['arxiv']},'{bad JSON',RuntimeError('offline')]
        for i,value in enumerate(values):
            with self.subTest(value=value):
                root=Path(self.temp.name)/str(i);r=Research(root,ScriptedLLM([value]),{})
                self.assertRaises(Exception,r.initialize,'Root?')
                self.assertFalse((root/'research/state.json').exists())
                self.assertRaisesRegex(ValueError,'initialize research first',r.step)
                record=read_records(root)[0]
                self.assertFalse(record['validation']['accepted'])
                self.assertEqual(record['outcome']['status'],'rejected')
                self.assertRaises(ValueError,r.initialize,'Root?',strategy='general')

    def test_cli_explicit_automatic_and_compatibility_paths(self):
        script=Path(self.temp.name)/'script.json';script.write_text(dumps({'responses':[{'strategy':'education','reason':'Teaching question.'}]}))
        for name,options in [('explicit',['--strategy','engineering','--script',str(script)]),('auto',['--script',str(script)]),('compat',['--database','arxiv','--script',str(script)])]:
            root=Path(self.temp.name)/name
            output=subprocess.check_output([sys.executable,'-m','mira','--root',str(root),'research-init','Which teaching approaches work?',*options],text=True)
            s=loads(output)
            self.assertEqual(s['strategy_selection']['method'],{'explicit':'explicit','auto':'r0','compat':'databases'}[name])
            self.assertEqual(len(read_records(root)),int(name=='auto'))
        root=Path(self.temp.name)/'invalid'
        result=subprocess.run([sys.executable,'-m','mira','--root',str(root),'research-init','Q?','--strategy','invalid','--script',str(script)],capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((root/'research/state.json').exists())

    def test_multi_database_keywords_unchanged_failure_skip_and_retry_reset(self):
        a=FixtureSearch([{'status':'failed','results':[],'error':'offline'}])
        b=FixtureSearch([{'status':'empty','results':[]}])
        c=FixtureSearch([evidence()])
        r=self.runner([{'keywords':['heat']},{"summary": "Scoped summary of all extracted results and their limitations.", 'results':[draft()]},decision('retry'),{'keywords':['thermal']}],{'a':a,'b':b,'c':c})
        r.initialize('Root?',['a','b','c'],context_budget=20000)
        events=[r.step() for _ in range(5)]
        self.assertEqual([e['action'] for e in events],['R1','R2','R2','R2','R3'])
        self.assertTrue(all(e['status']=='committed' for e in events))
        self.assertEqual(a.queries,b.queries);self.assertEqual(b.queries,c.queries)
        self.assertEqual(r.step()['action'],'R4')
        n=self.state()['nodes']['q1'];self.assertIsNone(n['keywords']);self.assertEqual(n['next_database_index'],0)
        self.assertEqual(n['previous_search_terms'],['heat'])
        self.assertEqual(r.step()['action'],'R1')
        self.assertEqual(n['status'],'living')

    def test_all_unavailable_is_explicit_and_each_pointer_advances(self):
        r=self.runner([{'keywords':['heat']}],{'a':FixtureSearch([{'status':'failed','results':[]}]),
                                                'b':FixtureSearch([{'status':'rate_limited','results':[],'retry_after':'120'}])})
        r.initialize('Q?',['a','b'], context_budget=12000)
        out=r.run(10)
        self.assertEqual(out['status'],'providers_unavailable')
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],2)
        self.assertEqual(self.state()['nodes']['q1']['round_outcomes'],['failed','rate_limited'])
        self.assertEqual(len(self.llm.requests),1)
        self.assertIn('b',self.state()['provider_cooldowns'])

    def test_cooldown_persists_and_does_not_repeat_request_after_retry(self):
        a=FixtureSearch([{'status':'rate_limited','results':[],'retry_after':'3600'}]); b=FixtureSearch([{'status':'empty','results':[]}])
        r=self.runner([{'keywords':['heat']},decision('retry'),{'keywords':['thermal']}],{'a':a,'b':b})
        r.initialize('Q?',['a','b'], context_budget=12000)
        for _ in range(5):r.step()
        until=self.state()['provider_cooldowns']['a']
        restarted=Research(self.root,self.llm,{'a':a,'b':b})
        e=restarted.step();self.assertEqual(e['action'],'R2');self.assertEqual(e['search_status'],'rate_limited')
        self.assertEqual(len(a.queries),1)
        self.assertEqual(self.state()['provider_cooldowns']['a'],until)
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],1)

    def test_cross_provider_dedup_and_empty_extraction_marks_processed(self):
        first=evidence();first['results'][0].update(identifiers={'doi':'10.1234/PAPER'},authors=['Jane Smith'])
        second=deepcopy(first);second['results'][0].update(id='other-provider-id',url='https://doi.org/10.1234/paper')
        r=self.runner([{'keywords':['heat']},{"summary": "", 'results':[]}],{'a':FixtureSearch([first]),'b':FixtureSearch([second])})
        r.initialize('Q?',['a','b'], context_budget=12000)
        for _ in range(3):r.step()
        e=r.step();self.assertEqual(e['action'],'R2');self.assertEqual(e['duplicate_count'],1)
        self.assertIsNone(self.state()['nodes']['q1']['pending_results'])
        self.assertEqual(len(self.llm.requests),2)
        self.assertEqual(len(self.state()['source_index']),1)
        self.assertEqual(r.knowledge.validate()['documents'],0)

    def test_two_nodes_pending_same_source_is_deduped_again_before_r3(self):
        r=self.runner([{'keywords':['heat']},{"summary": "Scoped summary of all extracted results and their limitations.", 'results':[draft()]}],{'fixture':FixtureSearch([evidence(),evidence()])})
        r.initialize('Root?',['fixture'], context_budget=12000)
        r.step()
        def seed(s):
            s['nodes']['q2']=tree.node('q2','Child?','q1');s['nodes']['q1']['child_ids']=['q2'];s['next_node']=3
            s['nodes']['q1']['priority']=1;s['nodes']['q2'].update(keywords=['heat'],priority=2)
        self.change(seed)
        self.assertEqual(r.step()['node_id'],'q1')
        self.assertEqual(r.step()['node_id'],'q2')
        self.change(lambda s:s['nodes']['q2'].update(priority=0))
        self.assertEqual(r.step()['node_id'],'q1')
        before=len(self.llm.requests)
        self.change(lambda s:s['nodes']['q1'].update(priority=0))
        event=r.step()
        self.assertEqual(event['action'],'R3');self.assertEqual(event['node_id'],'q2')
        self.assertEqual(event['memory_ids'],[]);self.assertEqual(event['duplicate_count'],1)
        self.assertEqual(len(self.llm.requests),before)
        self.assertEqual(r.knowledge.validate()['documents'],1)

    def test_temporary_content_pruning_protects_pending_and_preserves_audit(self):
        r=self.runner([{'keywords':['heat']},{"summary": "Scoped summary of all extracted results and their limitations.", 'results':[draft()]}],{'fixture':FixtureSearch([evidence()])})
        r.initialize('Root?',['fixture'], context_budget=12000);r.step();r.step()
        ref=self.state()['nodes']['q1']['pending_results'];saved=loads((self.root/ref).read_text())
        self.assertNotIn('content',saved['results'][0]);self.assertNotIn('raw_api_response',saved)
        cached=self.root/saved['payload_ref'];self.assertTrue(cached.exists())
        self.assertEqual(r.prune_retrievals(apply=True)['removed'],[])
        restarted=Research(self.root,self.llm,{})
        self.assertEqual(restarted.step()['action'],'R3')
        self.assertTrue(cached.exists())  # Initial test retention.
        self.assertEqual(len(r.prune_retrievals()['discardable']),1)
        self.assertTrue(cached.exists())
        self.assertEqual(len(r.prune_retrievals(apply=True)['removed']),1)
        self.assertFalse(cached.exists())
        self.assertEqual(r.knowledge.validate()['documents'],1)
        self.assertIn('https://example.org/fixture',r.knowledge.document('r1').metadata['source']['url'])
        self.assertIn(evidence()['results'][0]['content'],read_records(self.root)[1]['request']['context']['research']['results'][0]['content'])
        self.assertEqual(r.prune_retrievals(apply=True)['removed'],[])
        # Canonical journals contain compact evidence, never the downloaded source text.
        source_text=evidence()['results'][0]['content']
        self.assertFalse(any(source_text in p.read_text() for p in (self.root/'journal').rglob('*.txt')))

    def test_missing_or_tampered_pending_cache_rejects_without_a_model_call(self):
        r=self.runner([{'keywords':['heat']}],{'fixture':FixtureSearch([evidence()])})
        r.initialize('Q?',['fixture'], context_budget=12000);r.step();r.step()
        ref=self.state()['nodes']['q1']['pending_results'];saved=loads((self.root/ref).read_text())
        cached=self.root/saved['payload_ref'];cached.write_text('tampered')
        event=r.step();self.assertEqual(event['status'],'rejected');self.assertIn('digest',event['error'])
        self.assertEqual(len(self.llm.requests),1);self.assertEqual(self.state()['nodes']['q1']['pending_results'],ref)
        cached.unlink();self.assertIn('missing',r.step()['error'])

    def test_r0_crash_repair_does_not_repeat_selection(self):
        for stage in ('prepared','replaced:research/state.json','before_commit'):
            root=Path(self.temp.name)/stage.replace(':','-').replace('/','-')
            p=multiprocessing.get_context('fork').Process(target=crash_cycle,args=(str(root),stage,True))
            p.start();p.join(10);self.assertEqual(p.exitcode,74)
            r=Research(root,ScriptedLLM([]),{})
            report=r.store.recovery_status()['operations'][0]
            r.store.repair(report['id'],apply=True)
            with r.store.lock():r.store.read();self.assertFalse(r._unresolved(r.store._files()))
            self.assertEqual(loads((root/'research/state.json').read_text())['strategy_selection']['strategy'],'engineering')
            self.assertEqual(len(read_records(root)),1)

    def test_r3_source_index_and_memory_recover_together(self):
        r=self.runner([{'keywords':['heat']}],{'fixture':FixtureSearch([evidence()])})
        r.initialize('Q?',['fixture'], context_budget=12000);r.step();r.step()
        p=multiprocessing.get_context('fork').Process(target=crash_cycle,args=(str(self.root),'replaced:memories/r1.md'))
        p.start();p.join(10);self.assertEqual(p.exitcode,74)
        self.assertRaises(Exception,r.prune_retrievals,apply=True)
        report=r.store.recovery_status()['operations'][0];r.store.repair(report['id'],apply=True)
        self.assertEqual(len(self.state()['source_index']),1)
        self.assertEqual(r.knowledge.validate()['documents'],1)
        with r.store.lock():self.assertFalse(r._unresolved(r.store._files()))

    def test_source_identity_normalization_and_conservative_conflicts(self):
        def item(identity='a',**extra):
            return {'id':identity,'url':'https://example.org/'+identity,'title':'A sufficiently specific publication title about recurrent neural networks',
                    'authors':['Jane Smith','John Doe'],'published':'2024',**extra}
        rows=[item(identifiers={'doi':'HTTPS://doi.org/10.1234/ABC'}),item('b',doi='10.1234/abc')]
        self.assertEqual(len(sources.unique(rows,{})[0]),1)
        a=item();b=item('b',title='  A sufficiently specific PUBLICATION title about recurrent neural networks  ',authors=['John Doe','Jane Smith'])
        self.assertEqual(len(sources.unique([a,b],{})[0]),1)
        for b in (item('b',authors=['Different Author']),item('b',published='2025'),item('b',title='A different sufficiently specific paper about recurrent neural networks')):
            self.assertEqual(len(sources.unique([a,b],{})[0]),2)
        self.assertEqual(len(sources.unique([item(doi='10.1234/a'),item('b',doi='10.1234/b')],{})[0]),2)
        self.assertEqual(len(sources.unique([item(arxiv_id='1234.56789v1'),item('b',arxiv_id='1234.56789v2')],{})[0]),2)
        self.assertEqual(len(sources.unique([item(title='Introduction'),item('b',title='Introduction')],{})[0]),2)

    def test_cross_node_doi_to_pmid_aliases_are_retained_after_restart(self):
        paper=evidence();paper['results'][0]['identifiers']={'doi':'10.1234/a','pmid':'1234'}
        other=deepcopy(paper);other['results'][0].update(id='pmid:1234',url='https://pubmed.ncbi.nlm.nih.gov/1234/',identifiers={'pmid':'1234'})
        r=self.runner([{'keywords':['heat']},{"summary": "Scoped summary of all extracted results and their limitations.", 'results':[draft()]}],{'a':FixtureSearch([paper])})
        r.initialize('Q?',['a'], context_budget=12000);r.step();r.step();r.step()
        def seed(s):
            s['nodes']['q1']['status']='answered'
            s['nodes']['q2']=tree.node('q2','A different question?','q1')
            s['nodes']['q1']['child_ids']=['q2'];s['nodes']['q2']['keywords']=['heat'];s['next_node']=3
        self.change(seed)
        resumed=Research(self.root,self.llm,{'a':FixtureSearch([other])})
        e=resumed.step()
        self.assertEqual(e['node_id'],'q2');self.assertEqual(e['duplicate_count'],1)
        self.assertEqual(len(self.llm.requests),2)
        self.assertEqual(self.state()['nodes']['q2']['next_database_index'],1)
        self.assertRaises(ValueError,self.change,lambda s:s.update(source_index={}))

    def test_legacy_canonical_pending_evidence_remains_processable(self):
        r=self.runner([{'keywords':['heat']},{"summary": "Scoped summary of all extracted results and their limitations.", 'results':[draft()]}],{'fixture':FixtureSearch([evidence()])})
        r.initialize('Q?',['fixture'], context_budget=12000)
        # Old layouts without retrieval_storage keep canonical results and the old raw feed.
        self.change(lambda s:s.pop('retrieval_storage'))
        r.step();r.step()
        ref=self.state()['nodes']['q1']['pending_results']
        self.assertIn('content',loads((self.root/ref).read_text())['results'][0])
        self.assertEqual(Research(self.root,self.llm,{}).step()['status'],'committed')
        self.assertEqual(r.knowledge.validate()['documents'],1)

    def test_duplicate_aliases_in_one_batch_do_not_premark_the_source(self):
        first=evidence()['results'][0];first['identifiers']={'doi':'10.1234/a'}
        second={**deepcopy(first),'id':'alternate','identifiers':{'doi':'10.1234/a','pmid':'1234'}}
        r=self.runner([{'keywords':['heat']},{"summary": "Scoped summary of all extracted results and their limitations.", 'results':[draft()]}],{'a':FixtureSearch([{'status':'ok','results':[first,second]}])})
        r.initialize('Q?',['a'], context_budget=12000);r.step();search=r.step()
        self.assertEqual(search['duplicate_count'],1)
        self.assertEqual(self.state()['source_index'],{})
        self.assertEqual(r.step()['action'],'R3')
        self.assertEqual(next(iter(self.state()['source_index'].values()))['identifiers']['pmid'],'1234')
