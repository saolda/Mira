"""Scientific-unit inventory, independent statuses, canonical snapshots and security."""
from copy import deepcopy
from email.message import Message
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

from mira import research_tree as tree
from mira.decisions import ScriptedLLM
from mira.experiments import Experiments, file_hashes
from mira.format import Memory, Unit, Relationship, Equation, dumps, loads, digest, validate_corpus
from mira.knowledge_inspection import KnowledgeInspector, SnapshotChanged, build_snapshot, SCHEMA
from mira.live import RecoveryRequired
from mira.research import Research
from mira.viewer import Handler
import test_synthesis as fixture
from test_gardener import seed


def finding(label='Measurement',kind='claim',evidence='unverified'):
    return Unit('f1',label,{'Kind':kind,'Evidence status':evidence,'Proposition':'A measured signal under laboratory conditions.',
        'Explanation':'No clinical interpretation.','Provenance':'Synthetic fixture.'})


def ordinary_memory(identity='r1',node='q1'):
    return Memory(identity,'Laboratory measurement','Fixture only.',metadata={'node_id':node,'kind':'research','source_memories':[],
        'synthesized_by':None,'created_order':int(identity[1:],36)},units=[finding()],next_ids={'f':2,'q':1,'e':1})


def synthesized(identity,targets):
    m=Memory(identity,'Qualified integration','Fixture only.',metadata={'node_id':'q1','kind':'synthesis',
        'source_memories':list(dict.fromkeys(i.split('#')[0] for i in targets)),'synthesized_by':None},
        units=[finding('Inference','synthesis')],next_ids={'f':2,'q':1,'e':1})
    m.relationships=[Relationship('f1','SYNTHESIZES',t,'unverified') for t in targets]
    return m


class ProjectionTests(unittest.TestCase):
    def state(self):return tree.initial('Laboratory research?',['fixture'],context_budget=200000)
    def snapshot(self,docs,state=None,equations=()):return build_snapshot('a'*64,docs,equations,state or self.state(),{})

    def test_every_unit_once_all_structural_and_scientific_types(self):
        m=ordinary_memory();m.units+=[Unit('f2','Observation',{**finding().fields,'Kind':'observation'}),
            Unit('f3','Hypothesis',{**finding().fields,'Kind':'hypothesis'}),
            Unit('f4','Inference',{**finding().fields,'Kind':'inference'}),
            Unit('q1','Question',{'Question':'Which conditions apply?','State':'open'}),
            Unit('e1','Equation',{'Equation':'e_r1_1'}),
            Unit('i1','Image',{'Image':'Recorded image description.','Figure reference':'Figure 1','Provenance':'Fixture.'})]
        m.next_ids={'f':5,'q':2,'e':2,'i':2}
        eq=Equation('e_r1_1','r1','Law','y=a*x',{'y':'signal','a':'factor','x':'input'},['Laboratory conditions.'],'Fixture.',units={'y':'V'})
        value=self.snapshot([m],equations=[eq]);ids=[u['id'] for u in value['units']]
        self.assertEqual(len(ids),7);self.assertEqual(len(set(ids)),7)
        self.assertEqual(value['inventory']['structural_types'],{'finding':4,'question':1,'equation':1,'image':1})
        self.assertEqual(value['inventory']['scientific_types'],{'claim':1,'observation':1,'hypothesis':1,'inference':1,'question':1,'equation':1,'image':1})
        self.assertEqual(next(u for u in value['units'] if u['id']=='r1#e1')['equation']['expression'],'y=a*x')

    def test_empty_corpus_and_missing_status_not_verified(self):
        value=self.snapshot([]);self.assertEqual(value['inventory']['total_units'],0)
        m=ordinary_memory();m.units=[Unit('q1','Question',{'Question':'Unresolved?','State':'open'})];m.next_ids['q']=2
        row=self.snapshot([m])['units'][0];self.assertIsNone(row['evidence_status']);self.assertEqual(row['question_state'],'open')
        self.assertIsNone(row['scientific_validation'])

    def test_historical_killed_and_answered_branches_included(self):
        state=self.state();state['nodes']['q2']=tree.node('q2','Historical branch?','q1');state['nodes']['q1']['child_ids']=['q2']
        state['nodes']['q2']['status']='killed';state['nodes']['q1']['status']='answered'
        m=ordinary_memory();m.units.append(Unit('q1','Open question',{'Question':'Still open?','State':'open'}));m.next_ids['q']=2
        value=self.snapshot([m,ordinary_memory('r2','q2')],state)
        self.assertEqual(value['inventory']['total_units'],3)
        self.assertFalse(next(u for u in value['units'] if u['id']=='r2#f1')['eligible_subtree'])
        self.assertEqual(next(u for u in value['units'] if u['id']=='r1#q1')['question_state'],'open')
        self.assertEqual(value['node_statuses'],{'answered':1,'killed':1})
        self.assertEqual(len(next(n for n in value['nodes'] if n['id']=='q1')['subtree_unit_ids']),3)

    def test_multiple_generation_lineage_directed_edges_and_unverified_synthesis(self):
        docs=[ordinary_memory('r1'),ordinary_memory('r2'),synthesized('s1',['r1#f1','r2#f1']),synthesized('s2',['s1#f1','r2#f1'])]
        value=self.snapshot(docs);row=next(u for u in value['units'] if u['id']=='s2#f1')
        self.assertEqual(row['leaf_units'],['r1#f1','r2#f1'])
        self.assertEqual(row['contributing_units'],['r2#f1','s1#f1'])
        self.assertEqual(row['origin'],'synthesized');self.assertEqual(row['evidence_status'],'unverified')
        edge=next(e for e in value['relationships'] if e['from']=='s2#f1' and e['to']=='s1#f1')
        self.assertEqual(edge['type'],'SYNTHESIZES');self.assertEqual(edge['status'],'unverified')
        self.assertEqual(value['inventory']['synthesized_units'],2)
        self.assertEqual(len(next(u for u in value['units'] if u['id']=='r2#f1')['synthesis_history']),2)

    def test_scientific_inference_remains_finding_structurally(self):
        docs=[ordinary_memory(),ordinary_memory('r2'),synthesized('s1',['r1#f1','r2#f1'])]
        docs[-1].units[0].fields['Epistemic type']='inference'
        # Production compact S3 shape includes the qualification and exact field set.
        docs[-1].metadata['lineage_mode']='knowledge_units';docs[-1].units[0].fields['Qualification']='Limited fixture.'
        value=self.snapshot(docs)
        self.assertEqual(value['inventory']['structural_types'],{'finding':3})
        self.assertEqual(value['inventory']['scientific_types'],{'claim':2,'inference':1})

    def test_missing_and_circular_synthesis_targets_rejected(self):
        with self.assertRaises(ValueError):self.snapshot([synthesized('s1',['r1#f1','r9#f1'])])
        with self.assertRaises(ValueError):self.snapshot([synthesized('s1',['s2#f1']),synthesized('s2',['s1#f1'])])

    def test_malformed_target_and_invalid_relationship_status_rejected(self):
        m=ordinary_memory();m.relationships=[Relationship('f1','RELATED_TO','../../private','proposed')]
        with self.assertRaises(ValueError):self.snapshot([m])
        m.relationships=[Relationship('f1','RELATED_TO','r2#f1','verified')]
        with self.assertRaises(ValueError):self.snapshot([m,ordinary_memory('r2')])

    def test_current_version_not_marked_selected_for_old_version(self):
        m=ordinary_memory();state=self.state()
        state['unit_synthesis']['groups']={'old':{'id':'old','unit_versions':[{'id':'r1#f1','version':'0'*64}],
            'status':'evaluated','selected_event':'old','s2_interaction_id':'recorded','disposition':'no_candidate'}}
        row=self.snapshot([m],state)['units'][0]
        self.assertEqual(row['participation'],[])
        self.assertTrue(row['synthesis_history']);self.assertTrue(all(not e['matches_current_version'] for e in row['synthesis_history']))

    def test_legacy_register_metrics_are_not_invented(self):
        state=self.state();del state['unit_synthesis'];value=self.snapshot([ordinary_memory()],state)
        self.assertIsNone(value['synthesis_summary']['groups_selected'])
        self.assertIsNone(value['coverage']['units_selected'])
        self.assertEqual(value['units'][0]['participation'],['not_recorded'])


class CanonicalKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)/'memory';self.catalog=Experiments(self.home);self.root=self.catalog.create('knowledge-fixture')
        self.model=fixture.FixtureModel(publish=True)
        self.r=Research(self.root,self.model,{})
        self.r.initialize('How do qualified laboratory measurements compare?',['fixture'],context_budget=200000)
        seed(self.r,own=2,child=0,leaf=0)
        self.inspector=KnowledgeInspector(self.catalog)

    def snapshot(self):return self.inspector.snapshot('knowledge-fixture')
    def row(self,identity='r1#f1'):return self.inspector.detail('knowledge-fixture',identity)['unit']
    def advance(self,*actions):
        for action in actions:self.assertEqual(self.r.step()['action'],action)

    def test_selection_evaluation_and_objective_are_not_synthesis(self):
        self.advance('S1');row=self.row()
        self.assertIn('selected',row['participation']);self.assertNotIn('evaluated',row['participation']);self.assertNotIn('contributed',row['participation'])
        self.advance('S2');row=self.row()
        self.assertIn('evaluated',row['participation']);self.assertIn('objective',row['participation']);self.assertNotIn('contributed',row['participation'])
        self.assertEqual(self.snapshot()['synthesis_summary']['memories_created'],0)

    def test_no_synthesis_does_not_invalidate_inputs(self):
        self.r.llm=fixture.FixtureModel(publish=False);self.advance('S1','S2','S3')
        row=self.row();self.assertIn('no_synthesis',row['participation']);self.assertNotIn('contributed',row['participation'])
        self.assertEqual(row['evidence_status'],'unverified');self.assertEqual(self.snapshot()['synthesis_summary']['memories_created'],0)
        self.assertEqual(self.snapshot()['synthesis_summary']['attempts_completed'],1)

    def test_failed_model_call_not_counted_as_generated_knowledge(self):
        self.advance('S1','S2');self.r.llm=ScriptedLLM(['invalid JSON']);event=self.r.step()
        self.assertEqual(event['status'],'rejected');row=self.row();self.assertIn('failed',row['participation'])
        self.assertNotIn('contributed',row['participation']);self.assertEqual(self.snapshot()['synthesis_summary']['memories_created'],0)
        self.assertEqual(self.snapshot()['synthesis_summary']['failed_or_blocked'],1)

    def test_published_synthesis_uses_actual_edges_and_remains_unverified(self):
        self.advance('S1','S2','S3');row=self.row();out=self.row('s1#f1')
        self.assertIn('contributed',row['participation']);self.assertEqual(out['contributing_units'],['r1#f1','r2#f1'])
        self.assertEqual(out['scientific_type'],'inference');self.assertEqual(out['evidence_status'],'unverified')
        self.assertEqual(out['scientific_validation']['status'],'unverified')
        self.assertEqual(self.snapshot()['inventory']['total_units'],3)
        self.assertIsNone(self.r.knowledge.document('r1').metadata['synthesized_by'])
        detail=self.inspector.detail('knowledge-fixture','s1#f1')
        self.assertEqual(detail['objective']['result_memory_id'],'s1')

    def test_repeated_reads_are_cached_and_never_call_models_or_write(self):
        before=file_hashes(self.root);calls=len(self.model.requests)
        original=self.snapshot()
        with patch('mira.knowledge_inspection.build_snapshot',side_effect=AssertionError('should reuse revision cache')):
            self.assertEqual(original,self.snapshot())
            self.inspector.inventory('knowledge-fixture',{'q':'measurement'})
            self.inspector.detail('knowledge-fixture','r1#f1')
        self.assertEqual(before,file_hashes(self.root));self.assertEqual(len(self.model.requests),calls)

    def test_snapshot_revision_consistency_and_cache_invalidation(self):
        old=self.snapshot();self.advance('S1');new=self.snapshot();self.assertNotEqual(old['revision'],new['revision'])
        with self.assertRaises(SnapshotChanged):self.inspector.detail('knowledge-fixture','r1#f1',old['revision'])
        with self.assertRaises(SnapshotChanged):self.inspector.inventory('knowledge-fixture',{'revision':old['revision']})

    def test_corrupt_canonical_state_not_hidden_by_cache(self):
        self.snapshot();path=self.root/'memories/r1.md';path.write_text(path.read_text().replace('Fictional measurement.','Altered measurement.'))
        with self.assertRaises(ValueError):self.snapshot()

    def test_incomplete_recovery_does_not_serve_cached_snapshot(self):
        self.snapshot()
        def fault(point):
            if point=='prepared':raise RuntimeError('interrupted fixture')
        with self.assertRaises(RuntimeError),self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();self.r.store.publish(docs,eqs,ledger,token,files={'events/incomplete.json':dumps({'fixture':True})},fault=fault)
        with self.assertRaises(RecoveryRequired):self.snapshot()

    def test_filters_combine_and_page_totals_are_exact(self):
        self.advance('S1','S2','S3')
        data=self.inspector.inventory('knowledge-fixture',{'origin':'source_extracted','participation':'contributed','type':'claim','node':'q1','descendants':'true','memory':'r1','evidence':'unverified','q':'r1 laboratory','limit':'1'})
        self.assertEqual(data['total'],1);self.assertEqual(data['corpus_total'],3);self.assertEqual(data['units'][0]['id'],'r1#f1')
        second=self.inspector.inventory('knowledge-fixture',{'offset':'2','limit':'1','sort':'id'})
        self.assertEqual(second['units'][0]['id'],'s1#f1');self.assertEqual(second['total'],3)
        self.assertEqual(self.inspector.inventory('knowledge-fixture',{'offset':'3'})['units'],[])
        for key in ['memory','node','type','evidence','participation']:
            self.assertEqual(self.inspector.inventory('knowledge-fixture',{'sort':key})['total'],3)

    def test_unknown_paths_and_invalid_parameters_rejected(self):
        for identity in ['../../secret','/etc/passwd','r1#f999','r1#f1/../../secret']:
            with self.subTest(identity=identity),self.assertRaises(ValueError):self.inspector.detail('knowledge-fixture',identity)
        for params in [{'file':'private.md'},{'limit':'0'},{'limit':'201'},{'offset':'-1'},{'sort':'mtime'},{'node':'q99'}]:
            with self.subTest(params=params),self.assertRaises(ValueError):self.inspector.inventory('knowledge-fixture',params)

    def test_export_omits_credentials_private_files_and_prompt_instructions(self):
        (self.root/'private-note.txt').write_text('PRIVATE_SENTINEL_CREDENTIAL')
        snapshot=self.snapshot();wire=dumps(snapshot)
        self.assertNotIn('PRIVATE_SENTINEL_CREDENTIAL',wire)
        for key in ['serialized_request','prompt_template','api_key','generation_settings']:
            self.assertNotIn('"'+key+'"',wire)
        self.assertEqual(snapshot['schema'],SCHEMA)

    def test_source_and_related_unit_search(self):
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=loads(self.r.store._files()['research/state.json'])
            m=ordinary_memory('r3');m.metadata['source']={'id':'fixture:original','title':'A qualified laboratory publication','url':'https://example.org/publication'}
            m.units[0].label='Claim'
            m.units[0].fields={k:v for k,v in m.units[0].fields.items() if k in {'Kind','Proposition','Qualification'}}
            docs.append(m);ledger['r']=4;state['nodes']['q1']['memory_ids'].append('r3');tree.refresh(state,docs)
            self.r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
        for query in ['fixture:original','laboratory publication','r3#f1','qualified laboratory']:
            self.assertIn('r3#f1',[r['id'] for r in self.inspector.inventory('knowledge-fixture',{'q':query})['units']])

    def test_relationship_neighbourhood_includes_direction_status_and_leaf_lineage(self):
        self.advance('S1','S2','S3');data=self.inspector.relationships('knowledge-fixture','s1#f1')
        self.assertEqual({r['id'] for r in data['nodes']},{'r1#f1','r2#f1','s1#f1'})
        self.assertEqual(data['leaf_units'],['r1#f1','r2#f1'])
        self.assertTrue(all(e['from']=='s1#f1' and e['status']=='unverified' for e in data['edges']))

    def request(self,path,method='GET'):
        handler=Handler.__new__(Handler);handler.server=SimpleNamespace(inspector=SimpleNamespace(catalog=self.catalog),knowledge=self.inspector,server_port=8767)
        handler.path=path;handler.command=method;handler.request_version='HTTP/1.1';handler.requestline=method+' '+path+' HTTP/1.1'
        handler.headers=Message();handler.headers['Host']='127.0.0.1:8767'
        handler.rfile=BytesIO();handler.wfile=BytesIO();getattr(handler,'do_'+method)()
        head,body=handler.wfile.getvalue().split(b'\r\n\r\n',1)
        return int(head.split()[1]),body,head

    def test_structured_http_endpoints_share_one_revision(self):
        before=file_hashes(self.root)
        base='/api/experiments/knowledge-fixture'
        status,body,_=self.request(base+'/overview');self.assertEqual(status,200);overview=loads(body)
        for suffix in ['/snapshot','/knowledge','/knowledge/r1%23f1','/relationships/r1%23f1','/questions/q1']:
            status,body,headers=self.request(base+suffix+'?revision='+overview['revision'])
            self.assertEqual(status,200,suffix);self.assertEqual(loads(body)['revision'],overview['revision'])
            self.assertIn(b'no-store',headers);self.assertIn(b"script-src 'self'",headers)
        self.assertEqual(file_hashes(self.root),before)

    def test_http_stale_revision_unavailable_state_and_traversal(self):
        base='/api/experiments/knowledge-fixture'
        self.assertEqual(self.request(base+'/overview?revision='+'0'*64)[0],409)
        for path in ['/knowledge/..%2F..%2Fprivate','/knowledge/r1%23f1?path=/etc/passwd','/knowledge?limit=999','/snapshot?file=private','/knowledge?q=a&q=b']:
            self.assertEqual(self.request(base+path)[0],400,path)
        path=self.root/'memories/r1.md';path.write_text(path.read_text()+'\nChanged canonical bytes.')
        self.assertEqual(self.request(base+'/overview')[0],400)

    def test_http_recovery_unavailable_and_no_fallback_to_old_snapshot(self):
        self.snapshot()
        def fault(point):
            if point=='prepared':raise RuntimeError('interruption')
        with self.assertRaises(RuntimeError),self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();self.r.store.publish(docs,eqs,ledger,token,files={'events/fixture.json':dumps({'fixture':True})},fault=fault)
        status,body,_=self.request('/api/experiments/knowledge-fixture/overview')
        self.assertEqual(status,503);self.assertIn(b'unavailable',body)

    def test_complete_original_memory_and_equation_available_in_detail(self):
        data=self.inspector.detail('knowledge-fixture','r1#f1')
        self.assertEqual(data['memory']['markdown'],(self.root/'memories/r1.md').read_text())
        self.assertEqual(data['unit']['fields']['Provenance'],'Fixture author.')

    def test_large_corpus_pagination_no_omissions_or_model_calls(self):
        from mira.format import base36
        docs=[ordinary_memory('r'+base36(i)) for i in range(1,1001)]
        state=tree.initial('Large deterministic fixture?',['fixture'],context_budget=200000)
        snapshot=build_snapshot('c'*64,docs,[],state,{})
        with patch.object(self.inspector,'snapshot',return_value=snapshot):
            result=[]
            for offset in range(0,1000,200):
                data=self.inspector.inventory('knowledge-fixture',{'offset':str(offset),'limit':'200'})
                self.assertEqual(data['total'],1000);result.extend(r['id'] for r in data['units'])
        self.assertEqual(len(result),1000);self.assertEqual(len(set(result)),1000)
        self.assertEqual(result[9],'ra#f1');self.assertEqual(result[35],'r10#f1')
        self.assertFalse(self.model.requests)

    def test_backend_does_not_render_untrusted_fields_as_html(self):
        m=ordinary_memory();m.units[0].fields['Proposition']='</script><img src=x onerror=alert(1)>'
        snapshot=build_snapshot('f'*64,[m],[],tree.initial('Question?',['fixture']),{})
        with patch.object(self.inspector,'snapshot',return_value=snapshot):
            row=self.inspector.detail('knowledge-fixture','r1#f1')['unit']
        self.assertEqual(row['proposition'],'</script><img src=x onerror=alert(1)>')
        script=Path('src/mira/viewer_assets/knowledge.js').read_text()
        for unsafe in ['innerHTML','eval(','insertAdjacentHTML','document.write(']:self.assertNotIn(unsafe,script)
        self.assertIn('textContent',script);self.assertIn('createElementNS',script)

    def test_active_corpus_identity_flag_for_default_viewer_selection(self):
        from mira.inspection import Inspector
        rows=Inspector(self.home).experiments()
        self.assertTrue(next(r for r in rows if r['name']=='knowledge-fixture')['active'])

    def test_source_payload_missing_or_tampered_remains_explicit(self):
        from mira import sources
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=loads(self.r.store._files()['research/state.json'])
            m=ordinary_memory('r3');m.metadata['source']={'id':'fixture:payload','url':'https://example.org/paper','title':'Original laboratory source'}
            m.metadata['evidence_ref']='research/results/'+'a'*32+'.json'
            m.units[0].label='Claim';m.units[0].fields={k:v for k,v in m.units[0].fields.items() if k in {'Kind','Proposition'}}
            payload=sources.save_payload(self.r.store,'a'*32,[{**m.metadata['source'],'content':'Original full passage.'}])
            docs.append(m);ledger['r']=4;state['nodes']['q1']['memory_ids'].append('r3');tree.refresh(state,docs)
            self.r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state),m.metadata['evidence_ref']:dumps({**payload,'results':[sources.descriptor(m.metadata['source'])]})})
        data=self.row('r3#f1');self.assertTrue(data['original_evidence']['available'])
        self.assertEqual(data['original_evidence']['source'][0]['content'],'Original full passage.')
        (self.root/payload['payload_ref']).write_text('Tampered payload.')
        data=self.row('r3#f1');self.assertFalse(data['original_evidence']['available'])
        self.assertIn('failed hash validation',data['original_evidence']['notice'])
        self.assertEqual(data['fields']['Proposition'],'A measured signal under laboratory conditions.')

    def test_active_writer_returns_unavailable_without_creating_files(self):
        before=file_hashes(self.root)
        with self.r.store.lock():
            status,_,_=self.request('/api/experiments/knowledge-fixture/overview')
        self.assertEqual(status,503);self.assertEqual(before,file_hashes(self.root))

    def test_s2_no_candidate_distinct_from_s3_no_synthesis(self):
        self.r.llm=ScriptedLLM([fixture.plans()]);self.advance('S1','S2')
        row=self.row();self.assertIn('no_candidate',row['participation']);self.assertNotIn('no_synthesis',row['participation'])
        summary=self.snapshot()['synthesis_summary']
        self.assertEqual(summary['groups_no_candidate'],1);self.assertEqual(summary['attempts_completed'],0)
        self.assertEqual(summary['no_synthesis_outcomes'],0)

    def test_blocked_s3_is_not_an_attempt_or_scientific_rejection(self):
        self.advance('S1','S2')
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=loads(self.r.store._files()['research/state.json'])
            objective=next(iter(state['unit_synthesis']['objectives'].values()))
            objective.update(status='blocked_context',reason='blocked_context_budget')
            self.r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
        row=self.row();self.assertIn('blocked',row['participation']);self.assertNotIn('attempted',row['participation'])
        self.assertEqual(row['evidence_status'],'unverified')
        self.assertEqual(self.snapshot()['synthesis_summary']['attempts_started'],0)

    def test_partial_contributors_not_all_selected_units_count_as_used(self):
        # Construct the pure scientific projection from an actual completed
        # fixture, then add a selected but noncontributing unit to its history.
        self.advance('S1','S2','S3');value=self.snapshot();self.assertIn('contributed',self.row()['participation'])
        with self.r.store.lock():_,docs,eqs,_=self.r.store.read();state=loads(self.r.store._files()['research/state.json'])
        extra=ordinary_memory('r3');docs.append(extra)
        current=build_snapshot(value['revision'],docs,eqs,state,{})
        version=next(u for u in current['units'] if u['id']=='r3#f1')['version']
        group=next(iter(state['unit_synthesis']['groups'].values()))
        group['unit_versions'].append({'id':'r3#f1','version':version})
        projected=build_snapshot(value['revision'],docs,eqs,state,{})
        row=next(u for u in projected['units'] if u['id']=='r3#f1')
        self.assertIn('selected',row['participation']);self.assertNotIn('contributed',row['participation'])

    def test_processed_source_inventory_includes_sources_without_units(self):
        state=tree.initial('Question?',['fixture']);state['source_index']={'index-key':{'source':{
            'id':'fixture:no-findings','title':'A source yielding no scientific unit','url':'https://example.org/empty'},
            'evidence_ref':'research/results/fixture.json'}}
        data=build_snapshot('f'*64,[],[],state,{})
        self.assertEqual(data['coverage']['sources_processed'],1)
        self.assertEqual(data['coverage']['sources_yielding_units'],0)
        self.assertEqual(data['sources'][0]['unit_ids'],[])
        self.assertTrue(data['sources'][0]['processed'])
