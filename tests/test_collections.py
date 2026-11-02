"""Bounded production unit contexts, whole scientific fields and budget integrity."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from mira import gardener, research_tree as tree, synthesis as sy, synthesis_discovery as sd
from mira.decisions import ScriptedLLM
from mira.format import Unit, dumps, loads, render
from mira.interactions import read_records
from mira.research import Research
from test_gardener import seed
from test_synthesis import FixtureModel, result


class CollectionTests(unittest.TestCase):
    def make(self,root,**config):
        r=Research(root,FixtureModel(),{})
        r.initialize('Which qualified techniques improve research?', ['fixture'],context_budget=200000,**config)
        seed(r,own=5,child=2,leaf=1)
        return r
    def test_bounded_units_replace_global_memory_catalogue_with_full_provenance(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root);first=r.step();self.assertEqual(first['action'],'S1');self.assertFalse(r.llm.requests)
            group=first['selection'];self.assertLessEqual(len(group['unit_ids']),5)
            self.assertTrue(group['relationships']);self.assertIn('s3_estimate',group['context_requirements'])
            self.assertEqual(r.step()['action'],'S2')
            supplied=read_records(root)[0]['request']['context']
            self.assertEqual(supplied['knowledge_units'],group['context']['knowledge_units'])
            self.assertLess(len(supplied['parent_memories']),8)
            for unit in supplied['knowledge_units']:
                original=r.knowledge.document(unit['memory_id']);anchor=unit['id'].split('#')[1]
                self.assertEqual(unit['fields'],next(u.fields for u in original.units if u.anchor==anchor))
    def test_legacy_lossless_summary_cache_still_available_for_diagnostics(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root);m=r.knowledge.document('r1');gardener._summary.cache_clear()
            first=gardener._summary(render(m));self.assertEqual(first,gardener._summary(render(m)))
            self.assertEqual(gardener._summary.cache_info().hits,1)
            m.units[0].fields['Explanation']='Changed qualification.';self.assertNotEqual(first,gardener._summary(render(m)))
    def test_selected_evidence_never_truncated_to_fit_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root);r.step()
            with r.store.lock():
                token,docs,eqs,ledger=r.store.read();s=loads(r.store._files()['research/state.json'])
                selected=deepcopy(s['unit_synthesis']['groups'][s['unit_synthesis']['selected_group']]['context'])
                s.update(context_budget=2100,research_capacity_tokens=2000);tree.refresh(s,docs)
                r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(s)})
            event=r.step();self.assertEqual(event['status'],'rejected');self.assertFalse(r.llm.requests)
            group=next(iter(r.inspect()['unit_synthesis']['groups'].values()))
            self.assertEqual(group['context'],selected);self.assertIn('blocked_context_budget',event['error'])
    def test_separate_output_reserve_both_s2_and_s3(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root,synthesis_output_reserve=4096);r.step()
            for action in ['S2','S3']:
                event=r.step();self.assertEqual(event['action'],action);self.assertEqual(event['context_usage']['output_reserve'],4096)
        with self.assertRaises(ValueError):tree.initial('Q?',['fixture'],synthesis_output_reserve=9000)
    def test_question_only_and_unsupplied_units_cannot_publish_synthesis(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root)
            with r.store.lock():_,docs,eqs,_=r.store.read()
            units=sd.project(docs,eqs)[:2]
            value=result(units);value['findings'][0]['evidence_checks'][0]['unit_id']='r99#f1'
            with self.assertRaises(ValueError):sy.validate_s3(value,units,[])
    def test_small_context_deferral_preserves_research_and_avoids_loop(self):
        with tempfile.TemporaryDirectory() as root:
            r=self.make(root)
            with r.store.lock():
                token,docs,eqs,ledger=r.store.read();s=loads(r.store._files()['research/state.json']);s.update(context_budget=2100,research_capacity_tokens=2000)
                tree.refresh(s,docs);r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(s)})
            first=r.step();self.assertEqual(first['reason'],'no_fitting_candidate')
            self.assertEqual(r.step()['status'],'blocked_synthesis');self.assertFalse(r.llm.requests)
            self.assertEqual(r.knowledge.validate()['documents'],8)
