from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

from mira import decisions, gardener, research_tree as tree
from mira.decisions import ScriptedLLM
from mira.format import Unit, Relationship, digest, dumps, loads, render
from mira.interactions import read_records
from mira.research import Research
from mira.research_demo import DemoLLM
from test_gardener import seed
from test_synthesis import selection


def crash_collection(root, stage):
    def fault(point):
        if point == stage: os._exit(74)
    Research(root, DemoLLM(), {}).step(fault=fault)


def populate(r, count=8):
    seed(r, own=count, child=0, leaf=0)
    with r.store.lock():
        token, memories, equations, ledger = r.store.read()
        state=loads(r.store._files()['research/state.json'])
        for m in memories:
            url='https://example.org/study-'+m.id
            m.metadata['sources']=[{'id':'study-'+m.id,'url':url,'title':'Authored synthetic study'}]
            for i in range(6):
                u=Unit(m.allocate('f'),'Synthetic evidence',{
                    'Kind':'claim','Evidence status':'unverified',
                    'Proposition':(f'Study {m.id} reports result {i}. '+('Tool execution improved reliability under controlled conditions. '*7)).strip(),
                    'Explanation':('Limited task sample; no independent replication. '+('Results may differ across domains and models. '*3)).strip(),
                    'Provenance':url})
                m.units.append(u)
                m.relationships.append(Relationship(u.anchor,'CITES',url,'unverified'))
            m.units[1].fields['Proposition']='A contradictory study reports no improvement in reliability.'
            m.units.append(Unit(m.allocate('q'),'Unresolved generalization',{
                'Question':'Does the result generalize across domains?','State':'open','Origin':'derived',
                'Qualification':'The available evidence does not resolve this.','Provenance':url}))
            m.revision+=1
        tree.refresh(state,memories)
        r.store.publish(memories,equations,ledger,token,files={'research/state.json':dumps(state)})
        # Budget exactly for all condensed inputs, while full Markdown cannot fit.
        supplied=gardener.context(state,memories,equations,'q1',memories,summarized=True, objective='Compare the fictional barrier measurements and their uncertainty.')
        limit=len(decisions.request(r.llm.model,r.llm.settings,'S2',supplied).encode())+2048
        state.update(context_budget=limit,research_capacity_tokens=limit*3//4)
        token,_,_,_=r.store.read()
        r.store.publish(memories,equations,ledger,token,files={'research/state.json':dumps(state)})
        return {m.id:deepcopy(m) for m in memories}


class CollectionTests(unittest.TestCase):
    def make(self, root, **config):
        r=Research(root,DemoLLM(),{})
        r.initialize('Which techniques improve autonomous research?', ['fixture'],context_budget=200000,**config)
        return r

    def test_broad_collection_condenses_realistic_memories_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root); original=populate(r)
            self.assertTrue(all(len(render(m).encode())>6000 for m in original.values()))
            self.assertEqual(r.step()['action'], 'S1')
            event=r.step()
            self.assertEqual((event['action'],event['status']),('S2','committed'))
            self.assertEqual(len(event['input_ids']),8)
            record=read_records(root)[1]
            supplied=record['request']['context']['input_memories']
            self.assertEqual(len(r.llm.requests),2)
            self.assertLessEqual(event['context_usage']['estimated_tokens'],r.inspect()['context_budget'])
            for summary in supplied:
                m=original[summary['id']]
                self.assertEqual(summary['representation'],'structured_summary')
                self.assertEqual(summary['memory_sha256'],digest(render(m)))
                self.assertEqual(summary['units'],[{'id':m.id+'#'+u.anchor,
                    'text':'\n'.join(key+': '+value for key,value in u.fields.items())} for u in m.units])
                self.assertEqual(summary['relationships'],[e.payload() for e in m.relationships])
                self.assertEqual(summary['sources'],m.metadata['sources'])
                self.assertIn('contradictory',dumps(summary))
                self.assertIn('does not resolve',dumps(summary))
                self.assertEqual(r.knowledge.document(m.id).units,m.units)
            synthesis=r.knowledge.document('s1')
            self.assertEqual(synthesis.metadata['source_memories'],list(original))
            self.assertTrue(all(s['representation']=='structured_summary' for s in synthesis.metadata['synthesis_inputs']))
            self.assertEqual({e.target for e in synthesis.relationships},{m+'#f1' for m in original})
            self.assertEqual(r.step()['status'],'finished')

    def test_summary_cache_is_reused_and_invalidated_by_memory_content(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root); original=populate(r,3)
            m=original['r1']; gardener._summary.cache_clear()
            first=gardener._summary(render(m)); again=gardener._summary(render(m))
            self.assertEqual(first,again)
            self.assertEqual(gardener._summary.cache_info().hits,1)
            m.units[0].fields['Explanation']='Changed qualification, not a new verified result.'
            updated=gardener._summary(render(m))
            self.assertNotEqual(updated,first)
            self.assertEqual(gardener._summary.cache_info().misses,2)

    def test_deferral_preserves_memories_and_other_research_continues(self):
        with tempfile.TemporaryDirectory() as root:
            llm=ScriptedLLM([selection(['r1','r2']), {'keywords':['measurement']}, selection(['r1','r2'])])
            r=Research(root,llm,{})
            r.initialize('Research?', ['fixture'],context_budget=12000)
            seed(r,own=2,child=0,leaf=0,living=('q3',))
            with r.store.lock():
                token,memories,equations,ledger=r.store.read(); state=loads(r.store._files()['research/state.json'])
                for m in memories:
                    m.units.append(Unit(m.allocate('f'),'Detailed evidence',{
                        **m.units[0].fields,'Proposition':('Unabridged experimental evidence. '*2000).strip()}))
                    m.revision+=1
                state['nodes']['q3']['status']='living'; state['research_cycles_since_synthesis']=5
                tree.refresh(state,memories)
                r.store.publish(memories,equations,ledger,token,files={'research/state.json':dumps(state)})
            event=r.step()
            self.assertEqual((event['action'],event['status']),('S1','committed'))
            self.assertEqual(event['deferred']['attempts'],1)
            self.assertEqual(len(llm.requests),1)
            self.assertEqual(r.step()['action'],'R1')
            self.assertEqual(len(llm.requests),2)
            self.assertTrue(all(r.knowledge.document(i).metadata['synthesized_by'] is None for i in ('r1','r2')))
            # Deferral is recorded and retried at cadence, rather than abandoned.
            with r.store.lock():
                token,memories,equations,ledger=r.store.read(); state=loads(r.store._files()['research/state.json'])
                state['research_cycles_since_synthesis']=5
                r.store.publish(memories,equations,ledger,token,files={'research/state.json':dumps(state)})
            self.assertEqual(r.step()['deferred']['attempts'],2)
            self.assertEqual(r.inspect()['synthesis_deferred']['attempts'],2)

    def test_summary_references_must_have_actually_been_supplied(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root); original=populate(r,3); memories=list(original.values())
            state=loads(Path(root,'research/state.json').read_text())
            supplied=gardener.context(state,memories,[],'q1',memories,summarized=True)['input_memories']
            supplied[0]['units']=[u for u in supplied[0]['units'] if u['id']!='r1#f1']
            value={'disposition':'synthesis','title':'Test','summary':'Test','findings':[{'label':'Test','proposition':'Test','explanation':'Test',
                'provenance':'Fixture','source_findings':['r1#f1','r2#f1','r3#f1']}]}
            self.assertRaisesRegex(ValueError,'invalid synthesis finding reference',gardener.validate,value,memories,supplied)

    def test_unresolved_question_references_survive_corpus_admission(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root); populate(r,3)
            r.llm=ScriptedLLM([selection(['r1','r2','r3']), {'disposition':'synthesis','title':'Unresolved generalization','summary':'The fixtures leave generalization open.',
                'findings':[{'label':'Open question','proposition':'Cross-domain generalization remains unresolved.',
                    'explanation':'These synthetic inputs provide no measurement answering the question.',
                    'provenance':'Supplied open questions only.', 'source_findings':['r1#q1','r2#q1','r3#q1']}]}])
            self.assertEqual(r.step()['action'],'S1')
            e=r.step()
            self.assertEqual((e['action'],e['status']),('S2','committed'))
            output=r.knowledge.document('s1')
            self.assertEqual({edge.target for edge in output.relationships},{'r1#q1','r2#q1','r3#q1'})
            self.assertTrue(all(u.fields['Evidence status']=='unverified' for u in output.units))
            self.assertEqual(r.knowledge.validate()['documents'],4)

    def test_condensed_collection_recovery_commits_once_without_another_call(self):
        for stage in ('prepared','replaced:memories/s1.md','before_commit'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as root:
                r=self.make(root); original=populate(r,4)
                self.assertEqual(r.step()['action'],'S1')
                r.llm.requests.clear()
                process=multiprocessing.get_context('fork').Process(target=crash_collection,args=(root,stage))
                process.start(); process.join(10)
                self.assertEqual(process.exitcode,74)
                pending=r.store.recovery_status()['operations'][0]
                self.assertIn(pending['assessment'],{'safely_finishable','complete'})
                r.store.repair(pending['id'],apply=True)
                r.store.repair(pending['id'],apply=True)
                self.assertEqual(r.step()['status'],'finished')
                self.assertFalse(r.llm.requests)
                self.assertEqual(len(read_records(root)),2)
                output=r.knowledge.document('s1')
                self.assertEqual(output.metadata['source_memories'],list(original))
                self.assertEqual({s['memory_id']:s['memory_sha256'] for s in output.metadata['synthesis_inputs']},
                                 {i:digest(render(m)) for i,m in original.items()})
                self.assertFalse(r.store.recovery_status()['blocked'])

    def test_separate_synthesis_output_reserve_is_used_and_validated(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root,synthesis_output_reserve=4096); seed(r,own=3,child=0,leaf=0)
            self.assertEqual(r.step()['action'],'S1')
            e=r.step()
            self.assertEqual(e['context_usage']['output_reserve'],4096)
            self.assertEqual(e['selection']['output_reserve'],4096)
        self.assertRaisesRegex(ValueError,'synthesis output reserve',tree.initial,'Q?',['fixture'],synthesis_output_reserve=9000)
