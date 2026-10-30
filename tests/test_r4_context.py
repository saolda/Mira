"""Lossless scientific inputs and compact, complete R4 retrieval histories."""
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

from mira import branching, decisions, research_tree as tree
from mira.budget import measure
from mira.decisions import ScriptedLLM
from mira.experiments import file_hashes
from mira.format import dumps, loads
from mira.interactions import read_records
from mira.research import Research, search_outcome
from mira.search import FixtureSearch
from test_research import decision, draft, evidence


FIELDS = {'round', 'provider', 'profile_id', 'query', 'query_submitted', 'status',
          'returned_record_count', 'unique_record_count', 'duplicate_count'}


def crash_r4(root):
    def fault(stage):
        if stage == 'replaced:research/state.json': os._exit(76)
    Research(root, ScriptedLLM([decision('retry')]), {}).step(fault=fault)


class R4ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'run'
        self.model = ScriptedLLM([])
        self.r = Research(self.root, self.model, {})
        self.state = tree.initial('What does the evidence establish?', ['fixture'],
                                  context_budget=16384, output_reserve=4096)

    def context(self, files):
        return self.r._context(self.state, [], [], files, 'q1')[0]['search_history']

    def test_complete_chronological_history_all_outcomes_and_no_record_mutation(self):
        files = {}
        statuses = ['ok', 'empty', 'failed', 'rate_limited', 'deferred', 'unavailable']
        for i in reversed(range(30)):
            row = {'node_id':'q1', 'round':i//6+1, 'provider':'provider-'+str(i%6),
                'profile_id':'balanced', 'query':'("exact phrase") AND term-'+str(i),
                'query_submitted':i%6 != 4, 'status':statuses[i%6],
                'timestamp':f'2026-10-30T01:{i:02}:00Z', 'reference':str(i),
                'returned_record_count':3 if i%6==0 else 0,
                'unique_record_count':1 if i%6==0 else 0,
                'duplicates':[{'id':'dup-a'}, {'id':'dup-b'}] if i%6==0 else [],
                'results':[{'id':'a','content':'Exact scientific evidence: P < .05; N > 10.'}],
                'profile_config':{'huge':'configuration'}, 'requests':[{'receipts':'transport'}],
                'submission_id':'internal-uuid', 'source_dispositions':{'a':'memory_created'},
                'payload_ref':'retrieved/a.json', 'error':'failure details retained on disk'}
            if i%6 in (2,3,5):row['http_status'] = 429 if i%6!=2 else 503
            files[f'research/results/{i}.json'] = dumps(row)
        files['research/results/other.json'] = dumps({'node_id':'q2', 'query':'not this node'})
        before = deepcopy(files); history = self.context(files)
        self.assertEqual(len(history),30)
        self.assertEqual([h['query'] for h in history],['("exact phrase") AND term-'+str(i) for i in range(30)])
        for i,h in enumerate(history):
            self.assertEqual(set(h),FIELDS | ({'http_status'} if i%6 in (2,3,5) else set()))
            self.assertEqual(h['provider'],'provider-'+str(i%6))
            self.assertEqual(h['round'],i//6+1)
            self.assertEqual(h['status'],statuses[i%6])
            self.assertEqual(h['query_submitted'],i%6!=4)
            self.assertEqual(h['duplicate_count'],2 if i%6==0 else 0)
            self.assertEqual(h['returned_record_count'],3 if i%6==0 else 0)
            self.assertEqual(h['unique_record_count'],1 if i%6==0 else 0)
        self.assertEqual(files,before)

    def test_equal_timestamps_keep_reference_order(self):
        files={'research/results/'+r+'.json':dumps({'node_id':'q1','timestamp':'same',
               'reference':r,'provider':'fixture','query':r,'status':'empty'}) for r in ('c','a','b')}
        self.assertEqual([h['query'] for h in self.context(files)],['a','b','c'])

    def test_legacy_unknown_metadata_and_counts_are_not_invented(self):
        old={'provider':'pubmed','query':'legacy exact string','status':'ok',
             'results':[{'id':'unique'}],'duplicates':[{'id':'old-duplicate'}]}
        original=deepcopy(old);out=search_outcome(old)
        self.assertEqual(out,{'round':None,'provider':'pubmed','profile_id':None,'query':'legacy exact string',
            'query_submitted':None,'status':'ok','returned_record_count':2,'unique_record_count':1,'duplicate_count':1})
        self.assertEqual(old,original)
        self.assertEqual(search_outcome({**old,'returned_record_count':0,'unique_record_count':0})['returned_record_count'],0)
        self.assertEqual(search_outcome({**old,'query_submitted':False})['query_submitted'],False)

    def test_verbose_bookkeeping_overflow_fits_without_dropping_entries_or_science(self):
        rows=[{'node_id':'q1','round':i//4+1,'provider':'fixture','profile_id':'default',
            'query':'unchanged scientific query '+str(i),'query_submitted':True,'status':'empty',
            'results':[],'duplicates':[], 'timestamp':str(i).zfill(2),'reference':str(i),
            'profile_config':{'settings':'x'*1000}, 'requests':[{'receipt':'y'*2000}]} for i in range(20)]
        files={'research/results/'+str(i)+'.json':dumps(r) for i,r in enumerate(rows)}
        science={'memories':[{'id':'r1','markdown':'All evidence and qualifications: P < .05 and size > 10.'}], 'equations':[]}
        common={'question':'Q?', 'question_context':[], 'research_results':science, 'research_brief':None}
        verbose=[{k:v for k,v in r.items() if k not in {'results','duplicates'}} for r in rows]
        old=decisions.request(self.model.model,self.model.settings,'R4',{**common,'search_history':verbose})
        compact={**common,'search_history':self.context(files)}
        new=decisions.request(self.model.model,self.model.settings,'R4',compact)
        # Offline conservative UTF-8 byte budgeting, not a claim about model tokens.
        self.assertTrue(measure(old,4096,16384)['over_context_budget'])
        self.assertFalse(measure(new,4096,16384)['over_context_budget'])
        self.assertEqual(len(compact['search_history']),20)
        self.assertEqual(compact['research_results'],science)

    def test_actual_r4_retains_entire_scientific_context_and_original_retrieval_bytes(self):
        model=ScriptedLLM([{'keywords':['heat','transfer']},
            {'summary':'Scientific fixture summary.','results':[draft()]},decision('retry')])
        r=Research(self.root,model,{'fixture':FixtureSearch([evidence()])})
        r.initialize('Q?',['fixture'],context_budget=30000)
        for _ in range(3):self.assertEqual(r.step()['status'],'committed')
        with r.store.lock():
            _,memories,equations,_=r.store.read();s=loads((self.root/'research/state.json').read_text())
            expected=branching.context(s,memories,equations,'q1',action='R4')['research_results']
        before=file_hashes(self.root/'research/results')
        self.assertEqual(r.step()['action'],'R4')
        actual=read_records(self.root)[-1]['request']['context']
        self.assertEqual(actual['research_results'],expected)
        self.assertEqual(actual['search_history'][0]['query'],'heat transfer')
        self.assertEqual(set(actual['search_history'][0]),FIELDS)
        self.assertEqual(file_hashes(self.root/'research/results'),before)

    def test_genuinely_oversized_scientific_request_blocks_without_model_dispatch(self):
        context={'question':'Q?', 'question_context':[], 'research_brief':None,'search_history':[],
                 'research_results':{'memories':[{'id':'r1','markdown':'unabridged evidence '*2000}], 'equations':[]}}
        original=deepcopy(context)
        with self.assertRaisesRegex(ValueError,'blocked_context_budget'):
            self.r._model({'action':'R4','cycle':1,'node_id':'q1'},'R4',context,self.state)
        self.assertEqual(self.model.requests,[])
        self.assertEqual(read_records(self.root),[])
        self.assertEqual(context,original)

    def test_r4_projection_and_outcome_survive_journal_repair_and_restart(self):
        r=Research(self.root,ScriptedLLM([{'keywords':['heat','transfer']}]),
                   {'fixture':FixtureSearch([{'status':'empty','results':[]}])})
        r.initialize('Q?',['fixture'],context_budget=30000);r.step();r.step()
        before=file_hashes(self.root/'research/results')
        process=multiprocessing.get_context('fork').Process(target=crash_r4,args=(str(self.root),))
        process.start();process.join(10);self.assertEqual(process.exitcode,76)
        operation=r.store.recovery_status()['operations'][0]
        r.store.repair(operation['id'],apply=True)
        restarted=Research(self.root,ScriptedLLM([]),{})
        restarted._recover_outcomes()
        with restarted.store.lock():
            restarted.store.read();self.assertFalse(restarted._unresolved(restarted.store._files()))
        records=read_records(self.root);self.assertEqual(len(records),2)
        self.assertEqual(records[-1]['request']['action'],'R4')
        self.assertEqual(set(records[-1]['request']['context']['search_history'][0]),FIELDS)
        self.assertEqual(records[-1]['outcome']['action_committed'],'R4')
        self.assertEqual(file_hashes(self.root/'research/results'),before)
        self.assertIsNone(loads((self.root/'research/state.json').read_text())['nodes']['q1']['keywords'])
        self.assertEqual(restarted.llm.requests,[])
