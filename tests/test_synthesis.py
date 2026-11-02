"""Production knowledge-unit discovery, planning, synthesis and durable recovery."""
from copy import deepcopy
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from mira import synthesis as sy, synthesis_discovery as sd, research_tree as tree, gardener
from mira.decisions import ScriptedLLM
from mira.embeddings import TestEmbedding
from mira.format import Memory, Unit, Relationship, digest, dumps, loads, parse, render
from mira.interactions import read_records
from mira.live import RecoveryRequired, validate_lineage
from mira.research import Research
from test_gardener import seed


def selection(ids=('r1','r2'), **changes):
    """Historical selection fixture used only in compatibility tests."""
    return {'disposition':'select','memory_ids':list(ids),'objective':'Compare attributed evidence.',
        'scores':dict.fromkeys('RCXNE',3),'reason':'Historical fixture.',**changes}


def synthesis(refs=('r1#f1','r2#f1'), **changes):
    """Historical synthesis fixture; canonical legacy parsing remains supported."""
    return {'disposition':'synthesis','title':'Qualified integration','summary':'A comparison.',
        'findings':[{'label':'Comparison','proposition':'A qualified integration.','explanation':'Fixture only.',
        'provenance':'Supplied units.','source_findings':list(refs)}],**changes}


def idea(ids=('r1#f1','r2#f1'), objective='Compare the qualified measurements.'):
    return {'category':'comparison','objective':objective,'unit_ids':list(ids),
        'potential_new_understanding':'An explicit cross-source methodological comparison.',
        'limitations':['Source independence and conditions remain unverified.'],
        'novelty':'Integrate the scoped relationship rather than paraphrase a single measurement.'}


def plans(*ideas):
    return {'disposition':'ideas' if ideas else 'no_candidate','ideas':list(ideas),'reason':'Review the supplied scientific context.'}


def result(units, existing=(), proposition='A cross-memory comparison exposes shared measurement limitations.'):
    return {'disposition':'synthesis','title':'Qualified comparison','summary':'A comparison with explicit uncertainty.',
        'findings':[{'label':'Comparison','proposition':proposition,
        'explanation':'The attributed statements support comparison, not independent replication.',
        'qualification':'No real-world conclusion follows from these fixtures.','epistemic_type':'inference',
        'source_findings':[u['id'] for u in units],
        'evidence_checks':[{'unit_id':u['id'],'quote':u['fields'].get('Proposition',u['fields'].get('Question','')),
            'use':'The attributed premise for this comparison.'} for u in units],
        'quantitative_checks':[],'novelty':'An explicit relationship between qualified premises.',
        'novelty_comparisons':[{'unit_id':u['id'],'assessment':'distinct','reason':'A qualified comparison, not an individual premise.'} for u in existing]}]}


class FixtureModel(ScriptedLLM):
    """One prewritten objective then abstention; never scientific inference."""
    def __init__(self, *, publish=False, objectives=1):
        super().__init__([]);self.publish=publish;self.objectives=objectives;self.planned=False
    def complete(self, wire):
        self.requests.append(wire);text=loads(wire)['messages'][0]['content'];decoder=json.JSONDecoder()
        units=decoder.raw_decode(text.split('SELECTED KNOWLEDGE UNITS\n',1)[1])[0]
        if text.startswith('Identify scientific'):
            value=plans() if self.planned else plans(*(idea([u['id'] for u in units],f'Compare qualified measurements, objective {i}.') for i in range(self.objectives)))
            self.planned=True
        elif self.publish:
            existing=decoder.raw_decode(text.split('EXISTING KNOWLEDGE FOR NOVELTY COMPARISON\n',1)[1])[0]
            value=result(units,existing)
        else:value={'disposition':'no_synthesis','reason':'No defensible new conclusion is established.'}
        return dumps({'model':self.model,'choices':[{'finish_reason':'stop','message':{'content':dumps(value)}}],'usage':None})


class ExitModel(ScriptedLLM):
    def complete(self,wire):os._exit(79)


def crash(root, stage, publish=False):
    def fault(point):
        if point==stage:os._exit(78)
    Research(root,FixtureModel(publish=publish),{}).step(fault=fault)


def dispatch_crash(root):Research(root,ExitModel([]),{}).step()


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'memory'
        self.llm=FixtureModel()
        self.r=Research(self.root,self.llm,{})
        self.r.initialize('How do qualified measurements compare?', ['fixture'],context_budget=200000)
        seed(self.r,own=2,child=0,leaf=0)
    def state(self):return loads((self.root/'research/state.json').read_text())
    def change(self,callback):
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=self.state();callback(state,docs,eqs,ledger)
            tree.refresh(state,docs);self.r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
    def units(self):
        with self.r.store.lock():
            _,docs,eqs,_=self.r.store.read();return sy.records(self.state(),docs,eqs)
    def advance(self):
        self.assertEqual(self.r.step()['action'],'S1');self.assertEqual(self.r.step()['action'],'S2')
    def test_three_stages_zero_one_one_calls_and_no_consumption(self):
        self.r.llm=FixtureModel(publish=True);before={i:(self.root/'memories'/f'{i}.md').read_bytes() for i in ['r1','r2']}
        for action,calls in [('S1',0),('S2',1),('S3',2)]:
            e=self.r.step();self.assertEqual((e['action'],e['status']),(action,'committed'),e);self.assertEqual(len(self.r.llm.requests),calls)
        for i,raw in before.items():self.assertEqual((self.root/'memories'/f'{i}.md').read_bytes(),raw)
        output=self.r.knowledge.document('s1');self.assertEqual(output.metadata['lineage_mode'],'knowledge_units')
        self.assertEqual({e.target for e in output.relationships},{'r1#f1','r2#f1'})
        self.assertEqual(parse(render(output)),output);self.assertEqual(self.r.knowledge.validate()['documents'],3)
        objective=next(iter(self.state()['unit_synthesis']['objectives'].values()))
        self.assertEqual(objective['contributing_unit_ids'],['r1#f1','r2#f1'])
    def test_no_synthesis_is_completed_without_memory_or_repeat(self):
        self.advance();self.assertEqual(self.r.step()['disposition'],'no_synthesis')
        self.r.step();calls=len(self.llm.requests);self.assertEqual(self.r.step()['status'],'finished');self.assertEqual(len(self.llm.requests),calls)
        self.assertEqual(self.r.knowledge.validate()['documents'],2)
    def test_configured_semantic_backend_reopens_discovery_without_s2_replay(self):
        self.advance();self.r.step();self.r.step();self.assertEqual(self.r.step()['status'],'finished')
        backend=Mock(identity='real-fixture:new-artifact',embed=Mock(return_value=[[1.,.5,.25]]))
        reopened=Research(self.root,ScriptedLLM([]),{},embedding_backend=backend)
        event=reopened.step();self.assertEqual(event['action'],'S1');self.assertTrue(event['embedding_capability']['semantic'])
        self.assertEqual(backend.embed.call_count,2);self.assertFalse(reopened.llm.requests)
        self.assertEqual(reopened.step()['status'],'finished')
    def test_only_actual_s3_subset_establishes_participation(self):
        with tempfile.TemporaryDirectory() as root:
            r=Research(root,ScriptedLLM([]),{});r.initialize('Question?', ['fixture'],context_budget=200000)
            seed(r,own=3,child=0,leaf=0)
            with r.store.lock():_,docs,eqs,_=r.store.read();state=loads(r.store._files()['research/state.json'])
            units=sy.records(state,docs,eqs);groups,capability=r.synthesis_discovery.discover(units)
            full=next(g for g in groups if len(g['unit_ids'])==3)
            r.synthesis_discovery.discover=Mock(return_value=([full],capability))
            self.assertEqual(r.step()['action'],'S1')
            r.llm=ScriptedLLM([plans(idea([u['id'] for u in units])),result(units[:2],units)])
            self.assertEqual(r.step()['action'],'S2');self.assertEqual(r.step()['action'],'S3')
            output=r.knowledge.document('s1')
            self.assertEqual(output.metadata['source_memories'],['r1','r2'])
            self.assertEqual({e.target for e in output.relationships},{'r1#f1','r2#f1'})
            self.assertTrue(all(r.knowledge.document(i).metadata['synthesized_by'] is None for i in ['r1','r2','r3']))
    def test_multiple_distinct_objectives_survive_restart(self):
        self.r.llm=FixtureModel(objectives=3);self.advance()
        self.assertEqual(len(self.state()['unit_synthesis']['objectives']),3)
        for _ in range(3):
            self.r=Research(self.root,ScriptedLLM([{'disposition':'no_synthesis','reason':'Insufficient support.'}]),{})
            self.assertEqual(self.r.step()['action'],'S3')
        self.assertTrue(all(o['status']=='completed' for o in self.state()['unit_synthesis']['objectives'].values()))
    def test_independent_s2_proposal_validation(self):
        self.r.step();self.r.llm=ScriptedLLM([plans(idea(),idea(['r1#f1','unknown']),idea(objective='Compare a different methodological feature.'))])
        e=self.r.step();self.assertEqual(e['status'],'committed');self.assertEqual(len(e['accepted_objectives']),2);self.assertEqual(len(e['rejected_components']),1)
    def test_all_invalid_s2_is_failed_not_scientific_rejection(self):
        self.r.step();self.r.llm=ScriptedLLM([plans(idea(['r1#f1','unknown']))]);e=self.r.step()
        self.assertEqual(e['status'],'rejected');self.assertEqual(next(iter(self.state()['unit_synthesis']['groups'].values()))['status'],'failed')
        self.assertFalse(self.state()['unit_synthesis']['objectives'])
        self.r.step();self.assertEqual(self.r.step()['status'],'blocked_synthesis')
    def test_s2_duplicate_and_limit_validation(self):
        accepted,rejected=sy.validate_s2(plans(idea(),idea(),idea(objective='A different comparison.'),idea(objective='Fourth objective.')),self.units())
        self.assertEqual(len(accepted),2);self.assertEqual(len(rejected),2)
    def test_only_supplied_eligible_references_may_reach_s3(self):
        units=self.units();bad=result(units);bad['findings'][0]['source_findings'].append('r99#f1')
        with self.assertRaisesRegex(ValueError,'references'):sy.validate_s3(bad,units,[])
        bad=result(units[:1])
        with self.assertRaises(ValueError):sy.validate_s3(bad,units,[])
    def test_misattributed_evidence_rejected(self):
        units=self.units();bad=result(units);bad['findings'][0]['evidence_checks'][0]['quote']='Not in the attributed source.'
        with self.assertRaisesRegex(ValueError,'misattributed'):sy.validate_s3(bad,units,[])
    def test_quantitative_arithmetic_and_incorrect_inequality(self):
        units=self.units()
        for u,n in zip(units,['4','8']):u['fields']['Proposition']=f'The matched quantity is {n} units.'
        operands=[{'unit_id':u['id'],'quote':u['fields']['Proposition'],'value':n} for u,n in zip(units,['4','8'])]
        lookup={u['id']:u for u in units}
        check={'operation':'ratio','operands':operands,'result':'0.5','assumptions':'Matched conditions and units.'}
        sy.numeric_checks([check],lookup)
        for change in [{'result':'2'},{'operation':'greater_than','result':True}]:
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'incorrect numerical'):sy.numeric_checks([{**check,**change}],lookup)
        sy.numeric_checks([{**check,'operation':'less_than','result':True}],lookup)
    def test_numeric_operand_source_attribution_required(self):
        units=self.units();u=units[0];u['fields']['Proposition']='Measured quantity 4.'
        operand={'unit_id':u['id'],'value':'5','quote':'Measured quantity 4.'}
        with self.assertRaisesRegex(ValueError,'operand not in quote'):sy.numeric_checks([{'operation':'sum','operands':[operand,operand],'result':'10','assumptions':'Fixture.'}],{u['id']:u})
    def test_numeric_sign_and_small_quantity_errors_not_hidden_by_tolerance(self):
        u=self.units()[0];lookup={u['id']:u}
        u['fields']['Proposition']='The signed quantity is −4.'
        operand={'unit_id':u['id'],'value':'4','quote':u['fields']['Proposition']}
        with self.assertRaisesRegex(ValueError,'operand not in quote'):
            sy.numeric_checks([{'operation':'sum','operands':[operand,operand],'result':'8','assumptions':'Matched quantities.'}],lookup)
        signed={**operand,'value':'-4'}
        sy.numeric_checks([{'operation':'sum','operands':[signed,signed],'result':'-8','assumptions':'Matched signed quantities.'}],lookup)
        u['fields']['Proposition']='The quantity is 0.0000000000000000001.'
        operand={'unit_id':u['id'],'value':'0.0000000000000000001','quote':u['fields']['Proposition']}
        with self.assertRaisesRegex(ValueError,'incorrect numerical'):
            sy.numeric_checks([{'operation':'sum','operands':[operand,operand],'result':'0.0000000000000000003','assumptions':'Matched quantities.'}],lookup)
    def test_questions_are_context_not_independent_evidence(self):
        units=self.units()
        for u in units:u['structural_type']='question';u['fields']={'Question':'What remains unresolved?'}
        with self.assertRaisesRegex(ValueError,'questions alone'):sy.validate_s3(result(units),units,[])
    def test_every_finding_must_integrate_two_memories(self):
        units=self.units();bad=result(units);f=deepcopy(bad['findings'][0]);f['source_findings']=['r1#f1'];bad['findings'].append(f)
        with self.assertRaises(ValueError):sy.validate_s3(bad,units,[])
    def test_hypotheses_explicit_and_unsupported_assertions_not_verified(self):
        units=self.units();value=result(units);value['findings'][0]['epistemic_type']='hypothesis';sy.validate_s3(value,units,[])
        value['findings'][0]['epistemic_type']='established_empirical_fact'
        with self.assertRaises(ValueError):sy.validate_s3(value,units,[])
    def test_novelty_exact_prior_synthesis_rejected_but_new_evidence_retained(self):
        units=self.units();finding=result(units)['findings'][0]
        existing=deepcopy(units[0]);existing['id']='s1#f1';existing['fields']['Proposition']=finding['proposition'];existing['fields']['Qualification']=finding['qualification'];existing['leaf_units']=['r1#f1','r2#f1']
        accepted,audit=sy.novelty([finding],units,[existing]);self.assertEqual(accepted,[]);self.assertEqual(audit[0]['existing_unit_ids'],['s1#f1'])
        existing['leaf_units']=['r1#f1'];self.assertEqual(len(sy.novelty([finding],units,[existing])[0]),1)
    def test_uncertain_semantic_equivalence_does_not_veto(self):
        units=self.units();f=result(units)['findings'][0];f['novelty_comparisons']=[{'unit_id':'s1#f1','assessment':'uncertain','reason':'Different endpoints.'}]
        existing=deepcopy(units[0]);existing['id']='s1#f1';existing['leaf_units']=['r1#f1','r2#f1']
        self.assertEqual(len(sy.novelty([f],units,[existing])[0]),1)
    def test_changed_and_additional_evidence_not_blanket_suppressed(self):
        self.r.step();key=self.state()['unit_synthesis']['selected_group'];first=self.units()
        self.assertEqual(sd.fingerprint(first),sd.fingerprint(list(reversed(first))))
        self.change(lambda s,docs,*_: (docs[0].metadata.update(sources=[{'id':'fixture-new-source','url':'https://example.org/new-source'}]),setattr(docs[0],'revision',2)))
        self.assertNotEqual(sd.fingerprint(self.units()),key)
        accepted,_=sy.validate_s2(plans(idea()),self.units());self.assertEqual(len(accepted),1)
        self.assertNotEqual(sy.objective_id(idea(),first),sy.objective_id(idea(objective='A new objective.'),first))
    def test_selected_version_change_fails_before_dispatch(self):
        self.r.step();self.change(lambda s,docs,*_: (docs[0].metadata.update(sources=[{'id':'fixture-new-source','url':'https://example.org/new-source'}]),setattr(docs[0],'revision',2)))
        e=self.r.step();self.assertEqual(e['status'],'rejected');self.assertIn('versions changed',e['error']);self.assertFalse(self.llm.requests)
    def test_s3_selected_version_change_fails_before_dispatch(self):
        self.advance();self.change(lambda s,docs,*_: (docs[0].metadata.update(sources=[{'id':'fixture-new-source','url':'https://example.org/new-source'}]),setattr(docs[0],'revision',2)))
        e=self.r.step();self.assertEqual(e['status'],'rejected');self.assertEqual(len(self.llm.requests),1)
    def test_failure_durable_and_no_automatic_model_retry(self):
        self.advance();self.r.llm=ScriptedLLM([RuntimeError('Transport unavailable')]);e=self.r.step()
        self.assertEqual(e['status'],'rejected');self.assertEqual(len(self.r.llm.requests),1)
        self.r.step();self.assertEqual(self.r.step()['status'],'blocked_synthesis');self.assertEqual(len(self.r.llm.requests),1)
    def test_late_failure_rolls_back_publication_and_ids(self):
        self.r.llm=FixtureModel(publish=True);self.advance()
        from unittest.mock import patch
        with patch('mira.research.branching.assess',side_effect=[[],RuntimeError('late failure')]):e=self.r.step()
        self.assertEqual(e['status'],'rejected');self.assertFalse((self.root/'memories/s1.md').exists());self.assertEqual(loads((self.root/'identity.json').read_text())['s'],1)
    def test_completed_register_immutable(self):
        self.advance();self.r.step()
        with self.assertRaisesRegex(ValueError,'immutable'):
            self.change(lambda s,*_:next(iter(s['unit_synthesis']['objectives'].values())).update(reason='Altered history.'))
    def test_context_block_is_durable_and_not_finished(self):
        self.change(lambda s,*_:s.update(context_budget=2100,research_capacity_tokens=2000))
        e=self.r.step();self.assertEqual(e['reason'],'no_fitting_candidate');self.assertFalse(self.llm.requests)
        self.assertEqual(self.r.step()['status'],'blocked_synthesis')
    def test_cross_branch_owner_and_killed_exclusion(self):
        with tempfile.TemporaryDirectory() as root:
            r=Research(root,FixtureModel(),{});r.initialize('Question?', ['fixture'],context_budget=200000)
            seed(r,own=1,child=1,leaf=1,killed=True)
            with r.store.lock():
                _,docs,eqs,_=r.store.read();s=loads(r.store._files()['research/state.json']);units=sy.records(s,docs,eqs)
            self.assertEqual({u['memory_id'] for u in units},{'r1','r2'})
            self.assertEqual(sy.owner(s,units),'q1')
            self.assertEqual(r.step()['selection']['memory_ids'],['r1','r2'])
    def test_fairness_yields_after_pipeline_with_more_objectives_pending(self):
        with tempfile.TemporaryDirectory() as root:
            r=Research(root,FixtureModel(objectives=3),{});r.initialize('Question?', ['fixture'],context_budget=200000)
            seed(r,own=2,child=0,leaf=0,living=('q3',))
            with r.store.lock():
                token,docs,eqs,ledger=r.store.read();s=loads(r.store._files()['research/state.json']);s['research_cycles_since_synthesis']=5
                r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(s)})
            for action in ['S1','S2','S3']:self.assertEqual(r.step()['action'],action)
            r.llm=ScriptedLLM([{'new_concepts':[],'search_concepts':['measurement','uncertainty'],'reason':'Research continues.'}])
            self.assertEqual(r.step()['action'],'R1')
            s=loads(Path(root,'research/state.json').read_text());self.assertEqual(sum(o['status']=='pending' for o in s['unit_synthesis']['objectives'].values()),2)
    def test_restart_at_each_stage_preserves_pending_work(self):
        for action in ['S1','S2','S3']:
            self.r=Research(self.root,self.llm,{})
            self.assertEqual(self.r.step()['action'],action)
    def test_recovery_at_selection_planning_and_publication_boundaries(self):
        for action,stages in [('S1',['prepared','replaced:research/state.json']),('S2',['prepared','before_commit']),('S3',['prepared','replaced:memories/s1.md','replaced:research/state.json','before_commit'])]:
            for stage in stages:
                with self.subTest(action=action,stage=stage),tempfile.TemporaryDirectory() as d:
                    root=Path(d)/'memory';shutil.copytree(self.root,root)
                    r=Research(root,FixtureModel(publish=True),{})
                    for _ in range({'S1':0,'S2':1,'S3':2}[action]):self.assertEqual(r.step()['status'],'committed')
                    proc=multiprocessing.get_context('fork').Process(target=crash,args=(root,stage,True));proc.start();proc.join(15);self.assertEqual(proc.exitcode,78)
                    with self.assertRaises(RecoveryRequired),r.store.lock():r.store.read()
                    recovery=r.store.recovery_status()['operations'][0];r.store.repair(recovery['id'],apply=True);r.store.repair(recovery['id'],apply=True)
                    r=Research(root,ScriptedLLM([]),{});r._recover_outcomes()
                    with r.store.lock():r.store.read()
                    state=loads((root/'research/state.json').read_text())
                    self.assertEqual(len(read_records(root)),{'S1':0,'S2':1,'S3':2}[action])
                    if action=='S1':self.assertIsNotNone(state['unit_synthesis']['selected_group'])
                    elif action=='S2':self.assertEqual(len(state['unit_synthesis']['objectives']),1)
                    else:
                        self.assertEqual(next(iter(state['unit_synthesis']['objectives'].values()))['result_memory_id'],'s1')
                        self.assertEqual(len(list((root/'memories').glob('s*.md'))),1)
                    self.assertFalse(r.llm.requests)
    def test_unknown_dispatch_s2_and_s3_never_retried(self):
        for stage in ['S2','S3']:
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as d:
                root=Path(d)/'memory';shutil.copytree(self.root,root);r=Research(root,self.llm,{})
                r.step()
                if stage=='S3':r.step()
                proc=multiprocessing.get_context('fork').Process(target=dispatch_crash,args=(root,));proc.start();proc.join(15);self.assertEqual(proc.exitcode,79)
                restarted=Research(root,ScriptedLLM([]),{})
                self.assertEqual(restarted.inspect()['pending_model_submissions'][0]['status'],'uncertain_submission')
                with self.assertRaisesRegex(ValueError,'unknown model call'):restarted.step()
                self.assertFalse(restarted.llm.requests)
    def test_historical_consumption_remains_readable_and_not_a_new_exclusion(self):
        self.change(lambda s,docs,eqs,ledger:gardener.apply(s,docs,ledger,'q1',list(docs),synthesis()))
        units=self.units();self.assertTrue({'r1#f1','r2#f1','s1#f1'}<={u['id'] for u in units})
        self.assertEqual(self.r.knowledge.document('r1').metadata['synthesized_by'],'s1')
        self.assertEqual(self.r.knowledge.validate()['documents'],3)
    def test_circular_ancestry_rejected(self):
        with self.r.store.lock():_,docs,_,_=self.r.store.read()
        for number,targets in [(1,['r1#f1','s2#f1']),(2,['r2#f1','s1#f1'])]:
            m=Memory('s'+str(number),'Cyclic fixture','Must be rejected.',metadata={'node_id':'q1','kind':'synthesis',
                'synthesized_by':None,'source_memories':[t.split('#')[0] for t in targets],
                'lineage_mode':'knowledge_units','created_order':number+2,
                'synthesis_unit_versions':[{'id':t,'version':'0'*64} for t in targets]})
            m.units.append(Unit(m.allocate('f'),'Invalid cycle',{'Kind':'synthesis','Evidence status':'unverified',
                'Proposition':'Invalid cyclic inference.','Explanation':'Cycle fixture.','Qualification':'Invalid.',
                'Epistemic type':'inference','Provenance':'Cycle fixture.'}))
            m.relationships=[Relationship('f1','SYNTHESIZES',t,'unverified') for t in targets];docs.append(m)
        with self.assertRaisesRegex(ValueError,'cyclic synthesis ancestry'):validate_lineage(docs)
        with self.assertRaisesRegex(ValueError,'cyclic knowledge-unit ancestry'):sd.project(docs)
    def test_killed_pending_evidence_is_not_dispatched(self):
        with tempfile.TemporaryDirectory() as root:
            r=Research(root,FixtureModel(),{});r.initialize('Question?', ['fixture'],context_budget=200000)
            seed(r,own=1,child=0,leaf=1,living=('q3',))
            with r.store.lock():
                token,docs,eqs,ledger=r.store.read();state=loads(r.store._files()['research/state.json'])
                state['research_cycles_since_synthesis']=5;r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
            self.assertEqual(r.step()['action'],'S1')
            with r.store.lock():
                token,docs,eqs,ledger=r.store.read();state=loads(r.store._files()['research/state.json'])
                state['nodes']['q3']['status']='killed';tree.refresh(state,docs)
                r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
            event=r.step();self.assertEqual(event['status'],'rejected');self.assertIn('ineligible',event['error']);self.assertFalse(r.llm.requests)
    def test_historical_pending_execution_is_preserved_and_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            r=Research(root,ScriptedLLM([]),{});state=tree.initial('Legacy?', ['fixture'],context_budget=200000)
            del state['unit_synthesis']
            with self.r.store.lock():_,docs,eqs,ledger=self.r.store.read()
            state['nodes']['q1'].update(status='answered',memory_ids=['r1','r2'])
            versions=tree.memory_versions(docs)
            state['synthesis_attempts']=[{'id':'historical-selection','node_id':'q1','selected_memory_ids':['r1','r2'],
                'memory_versions':versions,'objective':'Historical execution.','scores':dict.fromkeys('RCXNE',1),'score':5,
                'selection_reason':'Historical selection.','s1_interaction_id':'old-selection','s2_interaction_id':None,
                'status':'pending','disposition':None,'contributing_memory_ids':[],'unused_memory_ids':['r1','r2'],
                'result_memory_id':None,'reason':''}]
            pending={'attempt_id':'historical-selection','selection':{},'context':{'node':{'id':'q1'},
                'objective':'Historical execution.','input_memories':[{'id':v['memory_id'],'memory_sha256':v['content_hash']} for v in versions]}}
            state['pending_synthesis']=pending;tree.refresh(state,docs)
            with r.store.lock():
                token,_,_,_=r.store.read();r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
            before=(Path(root)/'research/state.json').read_bytes()
            self.assertEqual(r.step()['status'],'blocked_legacy_synthesis')
            self.assertEqual((Path(root)/'research/state.json').read_bytes(),before);self.assertFalse(r.llm.requests)
    def test_population_endpoint_and_causal_limits_are_explicit_in_prompts(self):
        from mira.prompts import PromptTemplates
        for stage in ['S2','S3']:
            text=PromptTemplates().sources(stage)[0]['source']
            for distinction in ['populations','endpoints','causal','independent','<=400','28','uncertainty']:
                self.assertIn(distinction,text)
        text=PromptTemplates().sources('S3')[0]['source']
        self.assertIn('AUC',text);self.assertIn('no_synthesis',text)
    def test_unit_version_ignores_consumption_and_memory_bookkeeping(self):
        with self.r.store.lock():_,docs,eqs,_=self.r.store.read()
        first=sd.project(docs,eqs)
        docs[0].revision+=1;docs[0].metadata['synthesized_by']='s99'
        self.assertEqual(first,sd.project(docs,eqs))
        docs[0].units[0].fields['Explanation']='Changed qualification.'
        self.assertNotEqual(sd.project(docs,eqs)[0]['version'],first[0]['version'])


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.r=Research(self.tmp.name,ScriptedLLM([]),{});self.r.initialize('Question?', ['fixture'],context_budget=200000)
        seed(self.r,own=3,child=1,leaf=1)
        with self.r.store.lock():_,self.docs,self.eqs,_=self.r.store.read()
        self.units=sd.project(self.docs,self.eqs)
    def test_bounded_groups_order_and_exact_set_identity(self):
        discovery=sd.Discovery(self.r.store)
        groups,capability=discovery.discover(self.units);reverse,_=discovery.discover(list(reversed(self.units)))
        self.assertEqual(groups,reverse);self.assertFalse(capability['semantic'])
        self.assertTrue(groups);self.assertTrue(all(2<=len(g['unit_ids'])<=5 for g in groups))
        self.assertEqual(len({g['id'] for g in groups}),len(groups))
        a,b=groups[0],groups[-1];self.assertNotEqual(a['id'],b['id'])
    def test_real_backend_cache_identity_representation_and_changed_content(self):
        backend=Mock(identity='nomic-http:fixture-artifact-sha256:prefix-v1')
        backend.embed.side_effect=lambda texts,query=False:[[1.,.5,.25] for _ in texts]
        d=sd.Discovery(self.r.store,backend);_,first=d.discover(self.units);self.assertTrue(first['semantic']);self.assertEqual(first['generated'],5)
        _,second=d.discover(self.units);self.assertEqual(second['cache_hits'],5);self.assertEqual(backend.embed.call_count,5)
        changed=deepcopy(self.units);changed[0]['version']=digest('changed scientific content')
        _,third=d.discover(changed);self.assertEqual(third['generated'],1)
        backend.identity+='-different-model';_,fourth=d.discover(self.units);self.assertEqual(fourth['generated'],5)
    def test_test_double_and_unavailable_service_explicitly_degraded(self):
        for backend in [TestEmbedding(),Mock(identity='real-model',embed=Mock(side_effect=OSError('offline')))]:
            groups,status=sd.Discovery(self.r.store,backend).discover(self.units)
            self.assertTrue(groups);self.assertEqual(status['mode'],'lexical_only');self.assertFalse(status['semantic'])
    def test_question_only_groups_not_dispatched_as_evidence(self):
        units=deepcopy(self.units)
        for unit in units:unit.update(type='question',structural_type='question')
        groups,_=sd.Discovery(self.r.store).discover(units)
        self.assertEqual(groups,[])
    def test_bad_vectors_are_not_semantic_success(self):
        for vectors in [[[float('nan')]],[[0.,0.]],[]]:
            backend=Mock(identity='real-fixture',embed=Mock(return_value=vectors))
            _,status=sd.Discovery(self.r.store,backend).discover(self.units)
            self.assertFalse(status['semantic'])
    def test_same_paper_exact_duplicates_and_distinct_corroboration(self):
        a,b=deepcopy(self.units[:2]);a['source_ids']=b['source_ids']=['one-paper'];a['leaf_units']=['r1#f1'];b['leaf_units']=['r2#f1']
        self.assertEqual(sd.annotate(a,b,1.,1.)['category'],'exact_duplicate')
        b['source_ids']=['different-paper'];self.assertEqual(sd.annotate(a,b,1.,1.)['category'],'potential_corroboration')
    def test_population_endpoint_numbers_and_conflicting_qualifications_preserved(self):
        a,b=deepcopy(self.units[:2]);a['fields']['Proposition']='In pediatric solid lesions AUC 0.8 estimates malignancy; volume doubling time <=400 days.'
        b['fields']['Proposition']='In adults with nonsolid lesions AUC 0.8 estimates invasiveness; volume doubling time 28 days.'
        a['fields']['Qualification']='Retrospective, no infection comparison.';b['fields']['Qualification']='Prospective, no causal mechanism.'
        row=sd.annotate(a,b,.9,.99)
        self.assertNotEqual(row['category'],'exact_duplicate');self.assertFalse(row['automatic_equivalence'])
        self.assertTrue({'conditions','numbers_and_comparators','qualification'}<=set(row['distinctions']))
    def test_explicit_complementarity_and_contradiction_are_not_duplicates(self):
        a,b=deepcopy(self.units[:2]);b['fields']['Proposition']='The complementary partition of the same study.'
        for relation,category in [('CONTRADICTS','apparent_contradiction'),('QUALIFIES','complementary_findings')]:
            a['relationships']=[{'type':relation,'to':b['id']}]
            self.assertEqual(sd.annotate(a,b,.1,.1)['category'],category)
    def test_cache_symlink_rejected_without_writing_target(self):
        target=Path(self.tmp.name)/'target';target.write_text('private')
        (Path(self.tmp.name)/'synthesis.sqlite3').symlink_to(target)
        backend=Mock(identity='real-fixture',embed=Mock(return_value=[[1.]]))
        _,status=sd.Discovery(self.r.store,backend).discover(self.units)
        self.assertFalse(status['semantic']);self.assertEqual(target.read_text(),'private')
    def test_defined_validation_premises_are_canonical_before_model_dispatch(self):
        import runpy
        script=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/validate_unit_synthesis.py'))
        model=ScriptedLLM([]);model.context_window=16384
        root=Path(self.tmp.name)/'mathematical-fixture'
        snapshot=script['mathematical_fixture'](root,model,None,matched=True)
        r=Research(root,model,{})
        with r.store.lock():token,docs,_,_=r.store.read()
        self.assertEqual(snapshot['revision'],token);self.assertEqual(len(docs),2)
        self.assertTrue(all(parse(render(m))==m for m in docs));self.assertFalse(model.requests)
