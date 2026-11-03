"""R1 consumes terminology; only G1 generates new model definitions.

Historical model definitions retain their original records and attribution.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from mira import glossary, glossary_definitions as gd, glossary_view, r1, research_tree as tree
from mira.decisions import ScriptedLLM, validate as validate_response
from mira.format import digest, dumps, loads
from mira.glossary_enrichment import Completion
from mira.interactions import read_records
from mira.research import Research
from mira.search import FixtureSearch
from test_glossary import proposal as term_proposal, evidence
import test_glossary_enrichment as enrichment_fixture
from test_terminology import responses as mesh_responses
from mira.terminology import Enricher

QUESTION='How does medical imaging use pulmonary volume doubling time?'


def plan(**changes):
    return {'new_concepts':['CT volumetry'],'search_concepts':['volume doubling time','pulmonary nodule'],
            'reason':'Use scientific terms.',**changes}


def generated(**changes):
    return {'origin':'llm_generated','verification':'provisional','term_id':'g1',
        'text':'The time required for a measured volume to double.', 'scope':'Medical imaging','ambiguity':'',
        'model':'historical-model','interaction_ref':'interactions/00000001-'+'a'*32+'/request.json',
        'event_ref':'events/'+'b'*32+'.json','template_sha256':'c'*64,'request_sha256':'d'*64,
        'context':{'question':QUESTION,'node_id':'q1'},**changes}


class ProvisionalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'memory'
        self.r=Research(self.root,ScriptedLLM([]),{'fixture':FixtureSearch([{'status':'empty','results':[]}])})
        self.r.initialize(QUESTION,['fixture'],context_budget=50000,output_reserve=4096)
        self.add_terms(['Volume doubling time'])

    def state(self):return loads((self.root/'research/state.json').read_text())
    def record(self, identity='g1'):return loads((self.root/'glossary'/f'{identity}.json').read_text())

    def add_terms(self, terms, definition=None):
        passage=definition or ' '.join(t+' appears in a controlled terminology fixture without a definition.' for t in terms)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=self.state()
            files,audit=self.r.glossary.proposals(state,[term_proposal(t,definition,passage=passage) for t in terms],evidence(passage),'q1')
            self.assertEqual(audit['rejected'],[])
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(state)})

    def step(self,value):
        self.r.llm=ScriptedLLM([value]);return self.r.step()

    def projection(self):
        with self.r.store.lock():
            s=self.state();ctx=r1.retrieval_context(s,[],self.r.store._files(),'q1')
            return self.r.glossary.retrieve(s,ctx,'q1')

    def generate(self, **changes):
        value=generated(**changes)
        def mutate(response):
            response['entries'][0]['definitions']=[{'definition':value['text'],'scope':value['scope'],'ambiguity':value['ambiguity']}]
            return response
        model=enrichment_fixture.Model(mutate=mutate)
        result=Completion(self.r.store,model_factory=lambda:model,prompt_factory=enrichment_fixture.EnrichmentTests.fixture_prompt,
                          log_dir=Path(self.tmp.name)/'log').run()
        self.assertEqual(result['model_calls'],1);self.assertEqual(result['after']['provisional_only'],1)
        return self.record()['definitions'][0]

    def test_exact_three_fields_optional_definition_field_is_rejected(self):
        validate_response('R1',plan(),6)
        for extra in ({'provisional_definitions':[]},{'provisional_definitions':None},{'definitions':[]},{'unknown':True}):
            with self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'response fields'):
                validate_response('R1',plan(**extra),6)
        for key in plan():
            value=plan();del value[key]
            with self.assertRaises(ValueError):validate_response('R1',value,6)

    def test_new_r1_definition_response_is_rejected_without_admission(self):
        before=(self.root/'glossary/g1.json').read_bytes()
        event=self.step(plan(provisional_definitions=[{'term_id':'g1','definition':'Invented'}]))
        self.assertEqual(event['status'],'rejected');self.assertIsNone(event['action_committed'])
        self.assertEqual(before,(self.root/'glossary/g1.json').read_bytes())
        self.assertEqual(len(self.r.llm.requests),1)

    def test_r1_searches_undefined_terms_without_creating_definitions(self):
        self.assertNotIn('definition_eligible',self.projection()['entries'][0])
        event=self.step(plan());self.assertEqual(event['status'],'committed')
        self.assertEqual(self.record()['definitions'],[])
        self.assertEqual(event['search_plan']['search_concepts'],plan()['search_concepts'])
        self.assertEqual(len(self.state()['nodes']['q1']['concept_candidates']),1)
        self.assertEqual(set(read_records(self.root)[0]['validation']['normalized_response']),set(plan()))

    def test_g1_is_independent_then_r1_uses_existing_definition(self):
        definition=self.generate()
        self.assertEqual(self.projection()['entries'][0]['definition'],definition['text'])
        before=(self.root/'glossary/g1.json').read_bytes();event=self.step(plan())
        self.assertEqual(event['status'],'committed')
        self.assertEqual(before,(self.root/'glossary/g1.json').read_bytes())
        request=loads(self.r.llm.requests[0])
        self.assertIn(definition['text'],request['messages'][0]['content'])
        self.assertNotIn('provisional_definitions',event)

    def test_new_r1_provenance_cannot_admit_model_definitions_at_transaction_boundary(self):
        row=generated();rec=self.record();rec['definitions']=[row];rec['status']='provisional'
        event={'action_committed':'R1','status':'committed','interaction_id':'00000001-'+'a'*32,
            'node_id':'q1','question':QUESTION,'provisional_definitions':{'accepted':[{
                'term_id':'g1','definition':row['text'],'scope':row['scope'],'ambiguity':''}]}}
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            files={'glossary/g1.json':dumps(rec),row['event_ref']:dumps(event)}
            s['glossary']['revision']+=1;s['glossary']['commitment']=glossary.commitment(s['glossary']['commitment'],{'glossary/g1.json':dumps(rec)})
            with self.assertRaisesRegex(ValueError,'enrichment provenance'):
                self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})

    def test_historical_r1_records_read_and_export_without_rewriting(self):
        # Simulate a corpus committed by the old release. New publications may
        # retain these rows, but cannot newly admit an R1-generated definition.
        row=generated();rec=self.record();rec['definitions']=[row];rec['status']='provisional'
        with self.r.store.lock(),patch('mira.live.validate_glossary_transaction'):
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            files={'glossary/g1.json':dumps(rec),row['event_ref']:dumps({'action_committed':'R1','status':'committed'})}
            s['glossary']['revision']+=1;s['glossary']['commitment']=glossary.commitment(s['glossary']['commitment'],{'glossary/g1.json':dumps(rec)})
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})
        before={p:self.r.store.path(p).read_bytes() for p in files}
        self.assertEqual(self.step(plan())['status'],'committed')
        self.add_terms(['Pulmonary nodule'])
        with self.r.store.lock():self.r.glossary.export(self.state())
        self.assertEqual(before,{p:self.r.store.path(p).read_bytes() for p in files})
        self.assertIn(row['text'],(self.root/'research/glossary.html').read_text())
        self.assertIn('historical-model',(self.root/'research/glossary.md').read_text())

    def test_source_definition_preference_retains_provisional_and_status(self):
        previous=self.generate()
        source='Volume doubling time is the elapsed time in which a measured volume doubles.'
        self.add_terms(['Volume doubling time'],source)
        rec=self.record();self.assertIn(previous,rec['definitions']);self.assertEqual(rec['status'],'source_defined')
        self.assertEqual(gd.preferred(rec,gd.context(QUESTION,'q1'))[0]['text'],source)

    def test_context_change_and_wrong_ancestor_meaning(self):
        row=generated(context={'node_id':'q2','question':'How does software networking measure packet volume doubling time?'},scope='Computer networking')
        rec=self.record();rec['definitions']=[row]
        source={'text':'Volume doubling time is a medical imaging measurement.', 'qualification':'Different meaning in ancestor question.',
            'evidence':{**rec['evidence'][0],'passage':'Volume doubling time is a medical imaging measurement.','node_id':'q1'}}
        rec['definitions'].append(source)
        scope=gd.context('How does software networking measure packet volume doubling time?','q2',['q1','q2'])
        self.assertEqual(gd.preferred(rec,scope),[row])
        self.assertEqual(gd.preferred({'term':rec['term'],'aliases':[],'definitions':[row]},gd.context(QUESTION,'q1')),[])

    def test_authority_precedence_wrong_meaning_and_no_description(self):
        self.generate()
        e=Enricher(Path(self.tmp.name)/'cache',transport=Mock(side_effect=mesh_responses('Volume doubling time',preferred='Volume doubling time',note='Time for measured volume doubling in medical imaging.')),sleep=lambda _:None)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            files,_=self.r.glossary.proposals(s,[],evidence(),'q1',enricher=e)
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})
        rec=self.record();self.assertIn('authority',gd.preferred(rec,gd.context(QUESTION,'q1'))[0])
        wrong=deepcopy(rec);a=next(d for d in wrong['definitions'] if 'authority' in d)
        a['text']='Time required for a software network packet transmission.';a['scope']='Computer networking'
        self.assertTrue(gd.provisional(gd.preferred(wrong,gd.context(QUESTION,'q1'))[0]))

    def test_mesh_backlog_without_description_does_not_block_g1_or_r1(self):
        enricher=Enricher(Path(self.tmp.name)/'cache',transport=Mock(side_effect=mesh_responses('Volume doubling time',preferred='Volume doubling time',note=None)),sleep=lambda _:None)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            files,audit=self.r.glossary.proposals(s,[],evidence(),'q1',enricher=enricher)
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})
        self.assertEqual(audit['enrichment']['api_calls'],2)
        self.assertFalse(self.record()['definitions']);self.generate()
        self.assertEqual(self.step(plan())['status'],'committed')
        with self.r.store.lock():_,again=self.r.glossary.proposals(self.state(),[],evidence(),'q1',enricher=enricher)
        self.assertEqual(again['enrichment']['api_calls'],0)

    def test_rejected_search_does_not_admit_definitions(self):
        event=self.step(plan(search_concepts=['one two three four five six']))
        self.assertEqual(event['status'],'rejected');self.assertFalse(self.record()['definitions'])
        self.assertEqual(len(self.r.llm.requests),1)

    def test_malformed_json_preserves_existing_failure_behavior(self):
        event=self.step('not JSON')
        self.assertEqual(event['status'],'rejected');self.assertFalse(self.record()['definitions'])
        self.assertEqual(len(self.r.llm.requests),1)

    def test_exports_escape_provisional_text_and_preserve_attribution(self):
        self.generate(text='Volume doubles <script>alert(1)</script> & remains measured.',ambiguity='Meaning <b>depends</b> on segmentation.')
        rec=self.record();md=glossary_view.markdown([rec]);html=glossary_view.html([rec])
        for label in ['LLM-generated','Provisional, not independently verified','Scientific scope','Ambiguity','Request SHA256']:
            self.assertIn(label,md);self.assertIn(label,html)
        self.assertNotIn('<script>alert(1)</script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertIn('definition-provisional',html);self.assertNotIn('href="interactions/',html)
        with self.r.store.lock():
            before=self.r.store.read()[0];self.r.glossary.export(self.state());self.assertEqual(before,self.r.store.read()[0])

    def test_canonical_provenance_schema_strict_and_append_only(self):
        self.generate();rec=self.record()
        for key,value in [('authority',{}),('confidence',.9),('evidence',{})]:
            bad=deepcopy(rec);bad['definitions'][0][key]=value
            with self.assertRaises(ValueError):glossary.validate_record(bad)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            rec['definitions']=[];rec['status']='candidate';files={'glossary/g1.json':dumps(rec)}
            s['glossary']['revision']+=1;s['glossary']['commitment']=glossary.commitment(s['glossary']['commitment'],files)
            with self.assertRaisesRegex(ValueError,'cannot be removed'):
                self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})
