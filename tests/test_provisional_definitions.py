"""Optional R1 definitions, independent validation, contextual preference and recovery."""
from copy import deepcopy
from pathlib import Path
import multiprocessing
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from mira import glossary, glossary_definitions as gd, glossary_view, r1, research_tree as tree
from mira.decisions import ScriptedLLM, validate as validate_response
from mira.format import digest, dumps, loads
from mira.interactions import read_records
from mira.live import RecoveryRequired
from mira.research import Research
from mira.search import FixtureSearch
from test_glossary import proposal as term_proposal, evidence
from test_terminology import responses as mesh_responses
from mira.terminology import Enricher

QUESTION='How does medical imaging use pulmonary volume doubling time?'


def definition(identity='g1', **changes):
    return {'term_id':identity,'definition':'The time required for a measured volume to double.',
        'scope':'Medical imaging','ambiguity':'',**changes}


def plan(definitions=None, **changes):
    value={'new_concepts':['CT volumetry'],'search_concepts':['volume doubling time','pulmonary nodule'],'reason':'Use scientific terms.'}
    if definitions is not None:value['provisional_definitions']=definitions
    return {**value,**changes}


def crash_definition(root, stage):
    def fault(point):
        if point==stage:os._exit(74)
    Research(root,ScriptedLLM([plan([definition()])]),{}).step(fault=fault)


class ProvisionalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'memory'
        self.r=Research(self.root,ScriptedLLM([]),{'fixture':FixtureSearch([{'status':'empty','results':[]}])})
        self.r.initialize(QUESTION,['fixture'],context_budget=50000,output_reserve=4096)
        self.add_terms(['Volume doubling time'])

    def state(self):return loads((self.root/'research/state.json').read_text())
    def record(self, identity='g1'):return loads((self.root/'glossary'/f'{identity}.json').read_text())

    def add_terms(self, terms):
        passage=' '.join(t+' appears in a controlled terminology fixture without a definition.' for t in terms)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=self.state()
            files,audit=self.r.glossary.proposals(state,[term_proposal(t,None,passage=passage) for t in terms],evidence(passage),'q1')
            self.assertEqual(audit['rejected'],[])
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(state)})

    def step(self,value):
        self.r.llm=ScriptedLLM([value]);return self.r.step()

    def reset_round(self, question=None):
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            s['nodes']['q1'].update(keywords=None,pending_results=None,next_database_index=0)
            if question:s['nodes']['q1']['question']=question
            tree.refresh(s,docs)
            self.r.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(s)})

    def projection(self):
        with self.r.store.lock():
            s=self.state();ctx=r1.retrieval_context(s,[],self.r.store._files(),'q1')
            return self.r.glossary.retrieve(s,ctx,'q1')

    def test_undefined_generation_single_call_and_actual_provenance(self):
        self.assertTrue(self.projection()['entries'][0]['definition_eligible'])
        e=self.step(plan([definition()]));self.assertEqual(e['status'],'committed')
        self.assertEqual(len(self.r.llm.requests),1)
        rec=self.record();glossary.validate_record(rec);d=rec['definitions'][0]
        self.assertEqual(rec['status'],'provisional');self.assertEqual(d['origin'],'llm_generated')
        self.assertEqual(d['verification'],'provisional');self.assertEqual(d['model'],self.r.llm.model)
        self.assertEqual(d['event_ref'],'events/'+e['event_id']+'.json')
        request=loads((self.root/d['interaction_ref']).read_text())
        self.assertEqual(d['template_sha256'],request['prompt_template']['files'][0]['sha256'])
        self.assertEqual(d['request_sha256'],digest(self.r.llm.requests[0]))
        self.assertNotIn('authority',d);self.assertNotIn('evidence',d)
        self.assertEqual(rec['evidence'][0]['source_id'],'source-1')
        self.assertEqual(self.state()['glossary']['next_id'],2)
        self.assertEqual(len(self.state()['nodes']['q1']['concept_candidates']),1)
        self.assertEqual(len(list((self.root/'glossary').glob('*.json'))),1)
        request_record=read_records(self.root)[0]
        self.assertEqual(request_record['validation']['normalized_response']['provisional_definitions'],[definition()])

    def test_zero_definitions_and_legacy_responses(self):
        for value in [plan(),plan([])]:
            self.reset_round();e=self.step(value)
            self.assertEqual(e['status'],'committed');self.assertEqual(self.record()['definitions'],[])
            self.assertEqual(len(self.r.llm.requests),1)
            validate_response('R1',value,6)

    def test_invalid_definitions_preserve_valid_plan_and_components(self):
        invalid=[definition('g999'),definition('r1'),definition(definition=''),definition(definition='a'*601),
            definition(scope=''),definition(scope='a'*161),definition(ambiguity='a'*401),definition(definition=True),
            definition(definition='Bad\x00text'),definition(definition='Citation https://invented.example'),
            {**definition(),'confidence':.99},{**definition(),'authority':'Invented'},['not an object']]
        for proposed in invalid:
            with self.subTest(proposed=proposed):
                self.reset_round();e=self.step(plan([proposed],new_concepts=['CT volumetry','bad AND query']))
                self.assertEqual(e['status'],'committed',e)
                self.assertEqual(e['search_plan']['search_concepts'],['volume doubling time','pulmonary nodule'])
                self.assertEqual(self.record()['definitions'],[])
                self.assertTrue(any(r['field']=='provisional_definitions' for r in e['rejected_components']))
                self.assertEqual(len(self.r.llm.requests),1)
        self.reset_round();e=self.step(plan({'not':'an array'}))
        self.assertEqual(e['status'],'committed');self.assertTrue(e['provisional_definitions']['rejected'])

    def test_existing_but_not_supplied_identity_is_rejected(self):
        self.add_terms(['Orchid pollination'])
        self.assertNotIn('g2',[r['id'] for r in self.projection()['entries']])
        event=self.step(plan([definition('g2')]))
        self.assertEqual(event['status'],'committed')
        self.assertEqual(self.record('g2')['definitions'],[])
        self.assertTrue(event['provisional_definitions']['rejected'])

    def test_explicitly_indeterminate_meaning_is_not_admitted(self):
        self.add_terms(['APC']);self.reset_round('What does APC mean without a scientific domain or expanded name?')
        event=self.step(plan([definition('g2',definition='APC has multiple possible expansions.',
            ambiguity='The specific meaning cannot be determined without domain context.')]))
        self.assertEqual(event['status'],'committed');self.assertEqual(self.record('g2')['definitions'],[])
        self.assertIn('abstention',event['provisional_definitions']['rejected'][0]['error'])

    def test_duplicate_proposals_and_limit_are_independent(self):
        self.add_terms(['Pulmonary spiculation','Pulmonary SUVmax','Pulmonary APC'])
        proposals=[definition('g1'),definition('g1'),definition('g2'),definition('g3')]
        e=self.step(plan(proposals))
        self.assertEqual(e['status'],'committed')
        self.assertEqual([r['term_id'] for r in e['provisional_definitions']['accepted']],['g1','g2'])
        self.assertEqual(len(e['provisional_definitions']['rejected']),2)
        self.assertEqual(self.record('g3')['definitions'],[])

    def test_uncertain_abbreviation_omission_and_qualified_scope(self):
        self.add_terms(['APC']);e=self.step(plan([]))
        self.assertEqual(self.record('g2')['definitions'],[])
        self.reset_round('How does APC relate to antigen presenting cells in immunology?')
        e=self.step(plan([definition('g2',definition='A cell that presents antigen to lymphocytes.',scope='Immunology',
            ambiguity='APC has other meanings; this interpretation is restricted to antigen-presenting cells.')]))
        self.assertEqual(e['status'],'committed');self.assertIn('other meanings',self.record('g2')['definitions'][0]['ambiguity'])

    def test_no_repeat_same_scope_trivial_wording_and_changed_scope(self):
        self.step(plan([definition()]))
        first=deepcopy(self.record()['definitions'])
        self.reset_round('  HOW does medical imaging use pulmonary volume doubling time! ')
        self.assertFalse(self.projection()['entries'][0]['definition_eligible'])
        e=self.step(plan([definition()]));self.assertEqual(e['status'],'committed')
        self.assertEqual(self.record()['definitions'],first);self.assertTrue(e['provisional_definitions']['rejected'])
        record=self.record();different=gd.context('How do atmospheric chemical reaction kinetics determine aerosol volume doubling time?', 'q2')
        self.assertTrue(gd.eligible(record,different))

    def test_source_definition_preference_retains_provisional_and_status_semantics(self):
        self.step(plan([definition()]))
        previous=deepcopy(self.record()['definitions'][0])
        text='Volume doubling time is the elapsed time in which a measured volume doubles.'
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            files,_=self.r.glossary.proposals(s,[term_proposal('Volume doubling time',text,passage=text)],evidence(text),'q1')
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})
        rec=self.record();self.assertIn(previous,rec['definitions']);self.assertEqual(rec['status'],'source_defined')
        preferred=gd.preferred(rec,gd.context(QUESTION,'q1'))
        self.assertEqual(preferred[0]['text'],text);self.assertFalse(gd.provisional(preferred[0]))
        self.reset_round();e=self.step(plan([definition()]))
        self.assertTrue(e['provisional_definitions']['rejected']);self.assertEqual(len(self.record()['definitions']),2)

    def test_authority_precedence_wrong_meaning_and_no_description_fallback(self):
        self.step(plan([definition()]))
        e=Enricher(Path(self.tmp.name)/'cache',transport=Mock(side_effect=mesh_responses('Volume doubling time',preferred='Volume doubling time',note='Time for measured volume doubling in medical imaging.')),
            sleep=lambda _:None)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            files,audit=self.r.glossary.proposals(s,[],evidence(),'q1',enricher=e)
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})
        rec=self.record();self.assertEqual(len(rec['definitions']),2)
        self.assertIn('authority',gd.preferred(rec,gd.context(QUESTION,'q1'))[0])
        wrong=deepcopy(rec);a=next(d for d in wrong['definitions'] if 'authority' in d)
        a['text']='Time required for a software network packet transmission.';a['scope']='Computer networking'
        self.assertTrue(gd.provisional(gd.preferred(wrong,gd.context(QUESTION,'q1'))[0]))
        empty=deepcopy(rec);empty['definitions']=[];empty['status']='candidate'
        self.assertTrue(gd.eligible(empty,gd.context(QUESTION,'q1')))

    def test_mesh_match_without_description_allows_initial_fallback(self):
        enricher=Enricher(Path(self.tmp.name)/'cache',transport=Mock(
            side_effect=mesh_responses('Volume doubling time',preferred='Volume doubling time',note=None)),sleep=lambda _:None)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=self.state()
            files,_=self.r.glossary.proposals(state,[],evidence(),'q1',enricher=enricher)
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(state)})
        self.assertEqual(self.record()['terminology'][-1]['status'],'matched')
        self.assertTrue(self.projection()['entries'][0]['definition_eligible'])
        self.assertEqual(self.step(plan([definition()]))['status'],'committed')
        self.assertEqual(self.record()['status'],'provisional')

    def test_definition_text_not_subject_to_search_concept_restrictions(self):
        value=definition(definition='The elapsed interval required for V2 = 2 * V1, with measurement conditions unchanged.')
        self.assertEqual(self.step(plan([value]))['status'],'committed')
        self.assertEqual(self.record()['definitions'][0]['text'],value['definition'])

    def test_wrong_ancestor_meaning_does_not_override_contextual_provisional(self):
        self.step(plan([definition()]))
        rec=self.record();d=rec['definitions'][0]
        d['context']={'node_id':'q2','question':'How does software networking measure packet volume doubling time?'}
        d['scope']='Computer networking'
        source={'text':'Volume doubling time is a medical imaging measurement.',
            'qualification':'Different meaning in ancestor question.',
            'evidence':{**rec['evidence'][0],'passage':'Volume doubling time is a medical imaging measurement.','node_id':'q1'}}
        rec['definitions'].append(source)
        scope=gd.context('How does software networking measure packet volume doubling time?','q2',['q1','q2'])
        self.assertTrue(gd.provisional(gd.preferred(rec,scope)[0]))

    def test_provisional_does_not_suppress_mesh_backlog_or_cooldown(self):
        self.step(plan([definition()]))
        enricher=Enricher(Path(self.tmp.name)/'cache',transport=Mock(side_effect=mesh_responses('Volume doubling time',preferred='Volume doubling time',note=None)),sleep=lambda _:None)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            files,audit=self.r.glossary.proposals(s,[],evidence(),'q1',enricher=enricher)
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})
        self.assertEqual(audit['enrichment']['api_calls'],2)
        self.assertEqual(self.record()['terminology'][-1]['status'],'matched')
        self.assertEqual(len(self.record()['definitions']),1)
        self.assertEqual(self.record()['status'],'provisional')
        with self.r.store.lock():
            files,again=self.r.glossary.proposals(self.state(),[],evidence(),'q1',enricher=enricher)
        self.assertEqual(again['enrichment']['api_calls'],0)

    def test_source_added_after_provisional_keeps_first_authority_lookup_eligible(self):
        self.step(plan([definition()]))
        source='Volume doubling time is the elapsed interval until a volume doubles.'
        enricher=Enricher(Path(self.tmp.name)/'cache',transport=Mock(
            side_effect=mesh_responses('Volume doubling time',preferred='Volume doubling time',note=None)),sleep=lambda _:None)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=self.state()
            files,audit=self.r.glossary.proposals(state,[term_proposal('Volume doubling time',source,passage=source)],
                evidence(source),'q1',enricher=enricher)
            self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(state)})
        self.assertEqual(audit['enrichment']['api_calls'],2)
        self.assertEqual(self.record()['status'],'source_defined')
        self.assertEqual(len(self.record()['definitions']),2)

    def test_all_invalid_search_no_orphan_definitions(self):
        e=self.step(plan([definition()],search_concepts=['one two three four five six']))
        self.assertEqual(e['status'],'rejected');self.assertEqual(self.record()['definitions'],[])
        self.assertTrue(self.state()['nodes']['q1']['r1_validation_blocked'])
        self.assertEqual(e['action_committed'],None)

    def test_later_action_failure_rolls_back_definition_afterimages(self):
        with patch('mira.research.branching.assess',side_effect=[[],RuntimeError('late failure')]):
            e=self.step(plan([definition()]))
        self.assertEqual(e['status'],'rejected');self.assertEqual(self.record()['definitions'],[])
        self.assertEqual(self.state()['glossary']['revision'],1)

    def test_malformed_json_retains_existing_failure_behavior(self):
        self.r.llm=ScriptedLLM(['not JSON']);e=self.r.step()
        self.assertEqual(e['status'],'rejected');self.assertEqual(self.record()['definitions'],[])
        self.assertEqual(len(self.r.llm.requests),1)

    def test_exports_escaped_provisional_labels_and_preference(self):
        self.step(plan([definition(definition='Volume doubles <script>alert(1)</script> & remains measured.',
            ambiguity='Meaning <b>depends</b> on segmentation.')]))
        rec=self.record();md=glossary_view.markdown([rec]);html=glossary_view.html([rec])
        for s in ['LLM-generated','Provisional, not independently verified','Scientific scope','Ambiguity']:
            self.assertIn(s,md);self.assertIn(s,html)
        self.assertNotIn('<script>alert(1)</script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertIn('definition-provisional',html)
        self.assertNotIn('href="interactions/',html)
        self.assertEqual(md,glossary_view.markdown([rec]))
        with self.r.store.lock():
            before=self.r.store.read()[0];out=self.r.glossary.export(self.state());after=self.r.store.read()[0]
            self.assertEqual(before,after);self.assertTrue(Path(out['html_path']).exists())

    def test_canonical_provenance_schema_is_strict_and_append_only(self):
        self.step(plan([definition()]))
        rec=self.record();legacy=deepcopy(rec);legacy['definitions']=[];legacy['status']='candidate';glossary.validate_record(legacy)
        for key,value in [('authority',{}),('confidence',.9),('evidence',{})]:
            bad=deepcopy(rec);bad['definitions'][0][key]=value
            with self.assertRaises(ValueError):glossary.validate_record(bad)
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();s=self.state()
            rec['definitions']=[];rec['status']='candidate';files={'glossary/g1.json':dumps(rec)}
            s['glossary']['revision']+=1;s['glossary']['commitment']=glossary.commitment(s['glossary']['commitment'],files)
            with self.assertRaisesRegex(ValueError,'cannot be removed'):
                self.r.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})

    def test_recovery_commits_glossary_and_plan_together_without_second_call(self):
        for stage in ['prepared','replaced:glossary/g1.json','replaced:research/state.json','before_commit']:
            with self.subTest(stage=stage):
                # Every boundary gets an independent fixture; active research is never opened.
                with tempfile.TemporaryDirectory() as d:
                    clone=Path(d)/'memory'
                    import shutil
                    shutil.copytree(self.root,clone)
                    proc=multiprocessing.get_context('fork').Process(target=crash_definition,args=(clone,stage));proc.start();proc.join(15)
                    self.assertEqual(proc.exitcode,74)
                    restarted=Research(clone,ScriptedLLM([]),{})
                    with self.assertRaises(RecoveryRequired),restarted.store.lock():restarted.store.read()
                    pending=restarted.store.recovery_status()['operations'][0]
                    restarted.store.repair(pending['id'],apply=True)
                    with restarted.store.lock():restarted.store.read();state=loads((clone/'research/state.json').read_text())
                    self.assertEqual(loads((clone/'glossary/g1.json').read_text())['status'],'provisional')
                    self.assertEqual(state['nodes']['q1']['keywords'],['volume doubling time','pulmonary nodule'])
                    self.assertEqual(len(restarted.llm.requests),0)
