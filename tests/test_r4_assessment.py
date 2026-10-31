"""One-call scientific assessment, cause-aware exhaustion and journal recovery."""
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

from mira import r4, research_tree as tree
from mira.decisions import ScriptedLLM, validate
from mira.experiments import file_hashes
from mira.format import dumps, loads, render
from mira.interactions import read_records
from mira.live import RecoveryRequired
from mira.prompts import PromptTemplates
from mira.research import Research
from mira.search import FixtureSearch
from test_budget import CountedModel
from test_r1_planning import plan
from test_r4_context import scientific_fixture, source, synthesis
from test_research import draft, evidence


def assessment(decision='unresolved', reason='The synthetic scientific question remains relevant and incomplete.'):
    return {'decision':decision,'reason':reason}


def crash_assessment(root, stage):
    def fault(point):
        if point == stage: os._exit(77)
    Research(root,ScriptedLLM([assessment()]),{}).step(fault=fault)


class R4AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'memory'

    def make(self, responses, model=None, **config):
        self.model=model or ScriptedLLM(responses)
        self.r=Research(self.root,self.model,{'fixture':FixtureSearch([{'status':'empty','results':[]}])})
        self.r.initialize('How do synthetic samples A and B compare?',['fixture'],context_budget=16000,
            synthesis_interval=100,**config)
        return self.r

    def state(self):return loads((self.root/'research/state.json').read_text())

    def mutate(self, operation):
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=self.state()
            operation(state,docs,eqs,ledger)
            tree.refresh(state,docs)
            self.r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})

    def completed_science(self, unsupported=False, conflicts=False):
        def seed(state,docs,eqs,ledger):
            _,fixtures=scientific_fixture()
            if unsupported:fixtures[-1].units[0].fields['Proposition']='Every real population has a mean of 1000 units.'
            if conflicts:
                fixtures[1].units[0].fields['Proposition']='Synthetic sample A has a mean of 20 units.'
                from mira.format import Relationship, Unit
                fixtures[1].relationships.append(Relationship('f1','CONTRADICTS','r1#f1','unverified'))
                fixtures[0].units.append(Unit(fixtures[0].allocate('q'),'Unresolved population gap',{
                    'Question':'Do other synthetic populations agree?','State':'open','Origin':'derived',
                    'Qualification':'Not studied in other populations.'}))
            docs.extend(fixtures);ledger.update(r=3,s=2)
            state['nodes']['q1'].update(memory_ids=[m.id for m in docs],keywords=['synthetic samples'],
                next_database_index=1,provider_outcomes={'0':'empty'},round_outcomes=['empty'])
        self.mutate(seed)

    def test_supported_synthesis_answer_preserves_original_memories_and_lineage(self):
        r=self.make([assessment('answered','r1#f1 and r2#f1 support s1#f1: synthetic B exceeds A by 4 units.')])
        self.completed_science();before=file_hashes(self.root/'memories')
        event=r.step()
        self.assertEqual((event['action'],event['status']),('R4','committed'))
        self.assertEqual(self.state()['nodes']['q1']['status'],'answered')
        self.assertEqual(file_hashes(self.root/'memories'),before)
        record=read_records(self.root)[0]
        self.assertEqual(set(record['request']['context']),{'question','question_scope','scientific_evidence'})
        self.assertEqual(record['request']['context']['scientific_evidence']['findings'][-1]['supporting_anchors'],['r1#f1','r2#f1'])
        self.assertEqual(self.state()['nodes']['q1']['last_r4_assessment']['event_ref'],'events/'+event['event_id']+'.json')
        self.assertEqual(len(self.model.requests),1)

    def test_unsupported_synthesis_and_conflicting_incomplete_evidence_remain_unresolved(self):
        for unsupported,conflicts in [(True,False),(False,True)]:
            with self.subTest(unsupported=unsupported,conflicts=conflicts),tempfile.TemporaryDirectory() as root:
                self.root=Path(root)
                reason=('s1#f1 is not supported by the 4 and 8-unit source findings.' if unsupported else
                        'r1#f1 and r2#f1 conflict; r1#q1 remains an evidence gap.')
                r=self.make([assessment(reason=reason)]);self.completed_science(unsupported,conflicts)
                before=file_hashes(self.root/'memories');event=r.step()
                self.assertEqual(event['status'],'committed')
                self.assertEqual(self.state()['nodes']['q1']['status'],'living')
                self.assertIsNone(self.state()['nodes']['q1']['keywords'])
                self.assertEqual(file_hashes(self.root/'memories'),before)
                science=read_records(self.root)[0]['request']['context']['scientific_evidence']
                if unsupported:self.assertIn('1000',science['findings'][-1]['proposition'])
                if conflicts:
                    self.assertEqual(science['unresolved_questions'][0]['id'],'r1#q1')
                    self.assertTrue(any(e['type']=='CONTRADICTS' for e in science['relationships']))

    def test_unresolved_with_available_searches_resets_round_then_one_new_r1(self):
        r=self.make([plan(['heat flux']),assessment(),plan(['thermal conductivity'])])
        self.assertEqual([r.step()['action'] for _ in range(3)],['R1','R2','R4'])
        n=self.state()['nodes']['q1']
        self.assertEqual(n['status'],'living');self.assertIsNone(n['keywords'])
        self.assertEqual(n['next_database_index'],0);self.assertEqual(n['previous_search_terms'],['heat flux'])
        self.assertEqual(n['provider_outcomes'],{});self.assertEqual(n['deferred_searches'],[])
        self.assertEqual(r.step()['action'],'R1')
        self.assertEqual([record['request']['action'] for record in read_records(self.root)],['R1','R4','R1'])

    def test_blocked_unresolved_exhausts_and_r5_runs_below_native_capacity_without_loop(self):
        model=CountedModel([plan([]),assessment(),{'questions':['Which synthetic measurement would resolve the gap?']}],prompt_tokens=100)
        r=self.make([],model=model,research_capacity_tokens=12000)
        r.step();self.assertEqual(self.state()['nodes']['q1']['status'],'living')
        restarted=Research(self.root,model,r.adapters)
        event=restarted.step();n=self.state()['nodes']['q1']
        self.assertEqual((event['action'],event['status']),('R4','committed'))
        self.assertTrue(n['search_blocked']);self.assertEqual(n['status'],'exhausted')
        self.assertEqual(n['exhaustion_reason'],'search_blocked')
        self.assertLess(n['research_capacity']['estimated_tokens'],n['research_capacity']['threshold'])
        proof=deepcopy(n['exhaustion_assessment'])
        self.assertEqual(proof['decision']['decision'],'unresolved')
        event=restarted.step();n=self.state()['nodes']['q1']
        self.assertEqual((event['action'],event['status']),('R5','committed'))
        self.assertEqual(n['status'],'split');self.assertEqual(n['exhaustion_assessment'],proof)
        self.assertEqual(n['child_ids'],['q2']);self.assertTrue(n['search_blocked'])
        self.assertEqual([record['request']['action'] for record in read_records(self.root)],['R1','R4','R5'])
        self.assertEqual(self.state()['nodes']['q2']['priority'],0)

    def test_root_kill_is_rejected_atomically_and_retry_decision_is_obsolete(self):
        r=self.make([plan([]),assessment('kill','Unrelated.'),{'decision':'retry','reason':'Old decision.'}])
        r.step();before=self.state()
        event=r.step()
        self.assertEqual(event['status'],'rejected');self.assertIn('root',event['error'])
        self.assertEqual(self.state(),before)
        self.assertEqual(r.step()['status'],'rejected')
        self.assertEqual(self.state(),before)
        for value in ({'decision':'retry','reason':'Old.'}, {'decision':'exhausted','reason':'Old.'},
                      {'decision':'unresolved','reason':'Gap.','extra':True}, {'decision':'answered'},
                      {'decision':'answered','reason':''}):
            with self.subTest(value=value),self.assertRaises(ValueError):validate('R4',value)

    def test_repeated_search_plan_hands_off_once_and_exhausts_without_fictitious_searches(self):
        r=self.make([plan(['heat flux']),assessment(),plan(['heat flux']),assessment(),{'questions':[]}])
        events=[r.step() for _ in range(6)]
        self.assertEqual([e['action'] for e in events],['R1','R2','R4','R1','R4','R5'])
        self.assertTrue(all(e['status']=='committed' for e in events))
        self.assertEqual(r.adapters['fixture'].queries,['heat flux'])
        node=self.state()['nodes']['q1']
        self.assertEqual(node['status'],'split');self.assertEqual(node['exhaustion_reason'],'search_blocked')
        self.assertEqual(len(node['child_ids']),0)
        self.assertEqual([record['request']['action'] for record in read_records(self.root)],['R1','R4','R1','R4','R5'])

    def test_nonroot_kill_criterion_checks_both_scopes_and_preserves_evidence(self):
        for decision_value,reason in [('kill','Irrelevant to both parent and root objectives.'),
                ('unresolved','Still relevant to the root objective despite its parent mismatch.'),
                ('unresolved','Still relevant to the parent objective despite its root mismatch.')]:
            with self.subTest(decision=decision_value,reason=reason),tempfile.TemporaryDirectory() as root:
                self.root=Path(root)
                r=self.make([assessment(decision_value,reason)])
                def child(state,docs,eqs,ledger):
                    state['next_node']=4;state['nodes']['q1']['child_ids']=['q2'];state['nodes']['q1']['status']='answered'
                    state['nodes']['q2']=tree.node('q2','Which synthetic measurement mechanism applies?','q1')
                    state['nodes']['q2'].update(status='answered',child_ids=['q3'])
                    n=tree.node('q3','Which unrelated hypothetical mechanism applies?','q2')
                    n.update(keywords=['mechanism'],next_database_index=1,provider_outcomes={'0':'empty'},memory_ids=['r1'])
                    state['nodes']['q3']=n;state['active_node_id']='q3'
                    docs.append(source('r1',1,owner='q3'));ledger['r']=2
                self.mutate(child);before=file_hashes(self.root/'memories')
                event=r.step();self.assertEqual(event['status'],'committed')
                self.assertEqual(self.state()['nodes']['q3']['status'],'killed' if decision_value=='kill' else 'living')
                self.assertEqual(file_hashes(self.root/'memories'),before)
                scope=read_records(self.root)[0]['request']['context']['question_scope']
                self.assertFalse(scope['is_root']);self.assertEqual(scope['root_question'],self.state()['nodes']['q1']['question'])
                self.assertEqual(scope['parent_question'],self.state()['nodes']['q2']['question'])
                self.assertNotEqual(scope['parent_question'],scope['root_question'])
        prompt=PromptTemplates().sources('R4')[0]['source']
        self.assertIn('irrelevant to BOTH its parent AND root research objectives',prompt)

    def test_pending_r3_and_deferred_provider_searches_prevent_r4(self):
        r=self.make([plan(['heat flux']),{'summary':'Synthetic study.','results':[draft()]}])
        r.adapters['fixture']=FixtureSearch([evidence()])
        self.assertEqual(r.step()['action'],'R1');self.assertEqual(r.step()['action'],'R2')
        self.assertFalse(r4.eligible(self.state(),self.state()['nodes']['q1']))
        self.assertEqual(r.step()['action'],'R3')
        self.assertTrue(r4.eligible(self.state(),self.state()['nodes']['q1']))
        # Existing provider scheduling remains authoritative for a deferred round.
        state=self.state();node=state['nodes']['q1'];node['deferred_searches']=[{'provider':'fixture'}]
        self.assertFalse(r4.eligible(state,node))

    def test_deferred_round_waits_without_r4_dispatch(self):
        r=self.make([plan(['heat flux'])])
        r.adapters['fixture']=FixtureSearch([{'status':'rate_limited','results':[],'retry_after':'3600'}])
        r.clock=lambda:1000.;r.sleep=lambda _:None
        r.step();self.assertEqual(r.step()['search_status'],'rate_limited')
        event=r.step();self.assertEqual(event['status'],'waiting_for_provider')
        self.assertEqual([record['request']['action'] for record in read_records(self.root)],['R1'])

    def test_blocked_r4_exhaustion_recovers_at_every_journal_stage_without_recalling_model(self):
        for stage in ('prepared','replaced:research/state.json','before_commit'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as root:
                self.root=Path(root);r=self.make([plan([])]);r.step()
                child=multiprocessing.get_context('fork').Process(target=crash_assessment,args=(str(self.root),stage))
                child.start();child.join(10);self.assertEqual(child.exitcode,77)
                with self.assertRaises(RecoveryRequired):r.inspect()
                operation=r.store.recovery_status()['operations'][0]['id'];r.store.repair(operation,apply=True)
                model=ScriptedLLM([{'questions':[]}]);resumed=Research(self.root,model,{})
                resumed._recover_outcomes()
                state=self.state();self.assertEqual(state['nodes']['q1']['status'],'exhausted')
                self.assertTrue(r4.search_exhausted(state['nodes']['q1']))
                self.assertEqual(read_records(self.root)[-1]['outcome']['action_committed'],'R4')
                self.assertEqual(resumed.step()['action'],'R5')
                self.assertEqual(len(model.requests),1)
                self.assertEqual([record['request']['action'] for record in read_records(self.root)],['R1','R4','R5'])

    def test_legacy_blocked_node_upgrades_through_r4_without_rewriting_research(self):
        r=self.make([plan([]),assessment()]);r.step()
        before=file_hashes(self.root/'memories')
        # Its existing R1 state has no R4-specific metadata and is read unchanged.
        model=ScriptedLLM([assessment()]);resumed=Research(self.root,model,{})
        self.assertNotIn('last_r4_assessment',self.state()['nodes']['q1'])
        self.assertEqual(resumed.step()['action'],'R4')
        self.assertEqual(file_hashes(self.root/'memories'),before)
        self.assertEqual(self.state()['nodes']['q1']['exhaustion_reason'],'search_blocked')

    def test_search_exhaustion_cause_cannot_be_forged_or_cleared(self):
        r=self.make([plan([]),assessment()]);r.step();r.step()
        before=self.state()
        with self.assertRaises(ValueError):
            self.mutate(lambda s,*_:s['nodes']['q1'].pop('exhaustion_assessment'))
        self.assertEqual(self.state(),before)
        with self.assertRaises(ValueError):
            self.mutate(lambda s,*_:s['nodes']['q1']['exhaustion_assessment'].update(event_ref='events/missing.json'))
        self.assertEqual(self.state(),before)

    def test_a_normal_unresolved_assessment_cannot_be_relabelled_search_exhaustion(self):
        r=self.make([plan(['heat flux']),assessment()]);r.step();r.step();r.step()
        before=self.state()
        def forge(state,*_):
            node=state['nodes']['q1']
            node.update(status='exhausted',search_blocked=True,search_blocked_reason='empty_selection',
                exhaustion_reason='search_blocked')
            node['last_r4_assessment']['search_blocked']=True
            node['exhaustion_assessment']=deepcopy(node['last_r4_assessment'])
        with self.assertRaisesRegex(ValueError,'not proved'):
            self.mutate(forge)
        self.assertEqual(self.state(),before)

    def test_a_blocked_plan_reaches_r4_before_new_capacity_exhaustion(self):
        model=CountedModel([assessment()],prompt_tokens=100)
        r=self.make([],model=model,research_capacity_tokens=12000);self.completed_science()
        def block(state,*_):
            state['nodes']['q1'].update(keywords=None,next_database_index=0,provider_outcomes={},
                search_blocked=True,search_blocked_reason='empty_selection')
        self.mutate(block)
        model.prompt_tokens=10000
        event=r.step()
        self.assertEqual((event['action'],event['status']),('R4','committed'))
        self.assertEqual(self.state()['nodes']['q1']['exhaustion_reason'],'search_blocked')
        self.assertEqual(len(model.requests),1)
