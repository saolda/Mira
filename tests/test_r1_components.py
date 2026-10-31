"""Partial R1 admission, explicit validation blocks and unchanged one-call budget."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from mira import research_tree as tree, r1
from mira.decisions import ScriptedLLM, validate
from mira.format import dumps, loads
from mira.interactions import read_records
from mira.research import Research
from mira.search import FixtureSearch
from test_r1_planning import plan


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'memory'

    def make(self,value):
        search=FixtureSearch([{'status':'empty','results':[]}])
        r=Research(self.root,ScriptedLLM([value]),{'fixture':search})
        r.initialize('Which lung growth measurements matter?', ['fixture'], context_budget=40000)
        return r,search

    def state(self):return loads((self.root/'research/state.json').read_text())

    def test_one_or_two_invalid_selected_items_preserve_order_and_discoveries(self):
        for count in [1,2]:
            with self.subTest(count=count),tempfile.TemporaryDirectory() as tmp:
                self.root=Path(tmp)/'memory'
                selected=['volume doubling time','one two three four five six','pulmonary infection','lung cancer']
                if count==2:selected[-1]='FDG PET/CT spiculated nodule volume doubling'
                value=plan(selected,['CT volumetry','heat AND transfer'])
                r,search=self.make(value)
                first=r.step();r.step()
                expected=['volume doubling time','pulmonary infection']+(['lung cancer'] if count==1 else [])
                self.assertEqual(first['status'],'committed')
                self.assertEqual(first['search_plan']['search_concepts'],expected)
                self.assertEqual(first['search_plan']['new_concepts'],['CT volumetry'])
                self.assertEqual(len(first['rejected_components']),count+1)
                self.assertEqual(search.queries,[' '.join(expected)])
                self.assertEqual(len(r.llm.requests),1)
                rec=read_records(self.root)[0]
                self.assertEqual(rec['validation']['proposed_response'],value)
                self.assertEqual(rec['validation']['normalized_response'],first['search_plan'])
                self.assertIn('at most five words',first['rejected_components'][1]['error'])

    def test_all_invalid_is_durable_validation_block_not_exhaustion_or_retry(self):
        r,search=self.make(plan(['one two three four five six','heat AND transfer'],['CT volumetry']))
        result=r.run(10)
        self.assertEqual(result['status'],'validation_blocked')
        self.assertEqual(len(r.llm.requests),1)
        node=self.state()['nodes']['q1']
        self.assertEqual(node['status'],'living');self.assertFalse(node['search_blocked'])
        self.assertEqual(node['concept_candidates'][0]['term'],'CT volumetry')
        self.assertEqual(node['concept_candidates'][0]['submitted_queries'],[])
        self.assertEqual(search.queries,[])
        self.assertEqual(self.state()['research_cycles'],0)
        restarted=Research(self.root,ScriptedLLM([]),{})
        self.assertEqual(restarted.step()['status'],'validation_blocked')
        self.assertEqual(restarted.inspect()['validation_blocked_nodes'],['q1'])
        rec=read_records(self.root)[0]
        self.assertEqual(rec['validation']['normalized_response']['new_concepts'],['CT volumetry'])
        self.assertEqual(len(rec['validation']['rejected_components']),2)

    def test_validation_block_allows_other_living_node_to_work(self):
        r,search=self.make(plan(['one two three four five six']))
        with r.store.lock():
            token,docs,eqs,ledger=r.store.read();state=self.state()
            child=tree.node('q2','Other lung measurement question?',parent='q1')
            state['nodes']['q2']=child;state['nodes']['q1']['child_ids']=['q2'];state['next_node']=3
            tree.refresh(state,docs)
            r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
        r.step()
        r.llm=ScriptedLLM([plan(['CT volumetry'])])
        event=r.step()
        self.assertEqual(event['node_id'],'q2');self.assertEqual(event['status'],'committed')
        self.assertEqual(len(r.llm.requests),1)

    def test_empty_selection_and_invalid_discovery_keep_deliberate_block_semantics(self):
        r,_=self.make(plan([],['one two three four five six','CT volumetry']))
        event=r.step()
        self.assertEqual(event['status'],'committed');self.assertTrue(event['search_blocked'])
        self.assertEqual(event['search_plan']['new_concepts'],['CT volumetry'])
        self.assertNotIn('r1_validation_blocked',self.state()['nodes']['q1'])

    def test_schema_is_still_strict_and_controls_are_not_silently_deleted(self):
        for invalid in [plan([True]),plan('abcdefg'),{'new_concepts':[],'search_concepts':[]},plan(new=[1])]:
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):validate('R1',invalid,4)
        value=plan(['summary lung cancer','lung cancer','LUNG CANCER','volume doubling time'])
        validate('R1',value,4)
        accepted,rejected=r1.components(value,r1.controls([]))
        self.assertEqual(accepted['search_concepts'],['lung cancer','volume doubling time'])
        self.assertEqual([r['text'] for r in rejected],['summary lung cancer','LUNG CANCER'])
        accepted,rejected=r1.components(plan(['Monte','Carlo estimates']),r1.controls(['Monte Carlo']))
        self.assertEqual(accepted['search_concepts'],['Monte'])
        self.assertEqual(rejected[0]['text'],'Carlo estimates')


if __name__=='__main__':unittest.main()
