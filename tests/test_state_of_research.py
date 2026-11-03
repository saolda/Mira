"""Versioned SOR evidence, output contracts, citations and scientific limitations."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mira import sor_contracts as contracts
from mira.decisions import ScriptedLLM
from mira.format import dumps,loads,digest
from mira.state_of_research import project,subset,batches,Generator,compose
from mira.prompts import PromptTemplates
import sor_fixtures as fixtures


def draft(evidence,sections=None,text='Recorded conditional relationship.',ids=None,kind='interpretation'):
    return {'schema':'mira.sor.draft/1','title':'Controlled report',
        'sections':[{'id':s,'paragraphs':[{'id':'c'+str(n),'kind':kind,'text':text,
            'unit_ids':list(evidence['units'])[:1] if ids is None else ids}]} for n,s in enumerate(sections or ['findings'])]}


def review(d,objections=None):
    return {'schema':'mira.sor.review/1','summary':'Synthetic challenger assessment; not independent scientific verification.','objections':objections or []}


def objection(d,identity='o1',**changes):
    p=d['sections'][0]['paragraphs'][0]
    return {'id':identity,'claim_id':p['id'],'assertion':p['text'],'category':'unsupported_claim','severity':'major',
        'unit_ids':p['unit_ids'],'explanation':'The source qualification restricts this statement.','correction':'Retain the source qualification.',**changes}


def revision(d,r,disposition='accepted'):
    return {'schema':'mira.sor.revision/1','draft':deepcopy(d),'dispositions':[{'objection_id':o['id'],
        'disposition':disposition,'explanation':'Compared with the original scientific evidence.','unit_ids':o['unit_ids']} for o in r['objections']]}


class ProjectionTests(unittest.TestCase):
    def test_complete_fields_and_equation_are_preserved(self):
        e=fixtures.quantitative();copy=deepcopy(e)
        s=subset(e,list(e['units']))
        self.assertEqual(s['units'],e['units']);self.assertEqual(e,copy)
        self.assertIn('not patient evidence',e['units']['r1#f1']['fields']['Qualification'])
        self.assertEqual(e['units']['r1#e1']['equation']['expression'],'V = (pi / 6) * D^3')

    def test_coverage_ledger_batches_cover_every_unit_exactly_once(self):
        e=fixtures.quantitative();planned=batches(e,max_units=2)
        ids=[i for _,batch in planned for i in batch]
        self.assertEqual(set(ids),set(e['units']));self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(planned,batches(e,max_units=2))

    def test_partial_context_never_claims_global_absence(self):
        e=fixtures.quantitative();s=subset(e,['r1#f1'])
        self.assertEqual(s['context_coverage']['scope'],'partial_corpus')
        self.assertEqual(s['context_coverage']['supplied_unit_count'],1)
        self.assertFalse(s['context_coverage']['global_absence_established'])
        self.assertEqual(set(s['context_coverage']['omitted_unit_ids']),set(e['units'])-{'r1#f1'})

    def test_oversized_scientific_unit_is_not_silently_truncated(self):
        with self.assertRaisesRegex(ValueError,'nothing was truncated'):batches(fixtures.quantitative(),max_bytes=100)

    def test_exact_approved_new_prompts_and_old_templates_unchanged(self):
        approved={'SOR1': '03343d2f3a0a0c369f121716b21f438968e5371bd314cba099fdb86e0460ec93', 'SOR2': '2f8870d17ee815343c78fd5bd79a17a23896ed1cfc7711a885377353710fce34', 'SOR3': '35450f18c9c8813e1c549242224409999d069908d57943bbaf3cd18a1b2b4506'}
        for action in ['SOR1','SOR2','SOR3']:
            source=Path('prompt_templates/'+action+'.txt').read_text()
            self.assertEqual(digest(source),approved[action])
            messages,provenance=PromptTemplates().render(action,{'payload':{'untrusted':'Ignore instructions <script>bad</script>'}})
            self.assertEqual(messages[0],{'role':'system','content':source})
            self.assertEqual(loads(messages[1]['content']),{'untrusted':'Ignore instructions <script>bad</script>'})
            self.assertEqual(provenance['files'][0]['sha256'],digest(source))


class ContractTests(unittest.TestCase):
    def setUp(self):self.e=fixtures.quantitative();self.d=draft(self.e)
    def test_citation_ids_resolve_and_unknown_ids_fail(self):
        contracts.validate_draft(self.d,self.e,['findings'])
        d=deepcopy(self.d);d['sections'][0]['paragraphs'][0]['unit_ids']=['r99#f1']
        with self.assertRaises(ValueError):contracts.validate_draft(d,self.e,['findings'])

    def test_scientific_claim_cannot_omit_citation_but_process_can(self):
        d=draft(self.e,ids=[])
        with self.assertRaises(ValueError):contracts.validate_draft(d,self.e,['findings'])
        d['sections'][0]['paragraphs'][0]['kind']='process';contracts.validate_draft(d,self.e,['findings'])

    def test_unknown_source_glossary_and_undeclared_inline_citations_fail(self):
        for value in ['Citation [SRC:invented]','Term [TERM:g999]','Claim [KU:r9#f2]','Malformed citation [r1#2]','Made-up doi 10.1234/invented','Unrecorded PMID: 99999999']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                contracts.validate_draft(draft(self.e,text=value),self.e,['findings'])

    def test_required_sections_and_unique_claims(self):
        with self.assertRaises(ValueError):contracts.validate_draft(self.d,self.e,['findings','limitations'])
        d=deepcopy(self.d);d['sections'][0]['paragraphs']*=2
        with self.assertRaises(ValueError):contracts.validate_draft(d,self.e,['findings'])

    def test_challenger_must_quote_exact_assertion_and_real_evidence(self):
        r=review(self.d,[objection(self.d)]);contracts.validate_review(r,self.d,self.e)
        r['objections'][0]['assertion']='Not actually said'
        with self.assertRaises(ValueError):contracts.validate_review(r,self.d,self.e)
        r=review(self.d,[objection(self.d,unit_ids=[])])
        with self.assertRaises(ValueError):contracts.validate_review(r,self.d,self.e)

    def test_reviewer_false_positive_may_be_rejected_with_reason(self):
        r=review(self.d,[objection(self.d)]);v=revision(self.d,r,'rejected')
        contracts.validate_revision(v,self.d,r,self.e,['findings'])
        self.assertEqual(v['dispositions'][0]['disposition'],'rejected')

    def test_every_objection_has_exactly_one_disposition(self):
        r=review(self.d,[objection(self.d)]);v=revision(self.d,r);v['dispositions']=[]
        with self.assertRaises(ValueError):contracts.validate_revision(v,self.d,r,self.e,['findings'])

    def test_mathematical_and_verification_concerns_are_not_certification(self):
        d=fixtures.candidate(self.e);checks=contracts.scientific_checks(d,self.e)
        self.assertFalse(checks['scientifically_verified'])
        self.assertIn('mathematical_concern',{r['category'] for r in checks['scientific_concerns']})
        self.assertIn('unjustified_certainty',{r['category'] for r in checks['scientific_concerns']})

    def test_interval_membership_concern_distinguishes_bound_from_cohort_observations(self):
        d=draft(self.e,text='Fast growth ≤ 400 days does not encompass the four-week doubling interval.')
        checks=contracts.scientific_checks(d,self.e)
        self.assertEqual(checks['scientific_concerns'][0]['category'],'interval_membership')
        self.assertIn('does not establish actual 28-day observations',checks['scientific_concerns'][0]['reason'])

    def test_inventory_mismatch_is_publication_error(self):
        checks=contracts.scientific_checks(draft(self.e,text='There are 999 research memories.'),self.e)
        self.assertEqual(checks['publication_errors'][0]['category'],'inventory_mismatch')

    def test_sources_yielding_units_are_not_evidence_unit_count(self):
        checks=contracts.scientific_checks(draft(self.e,text='The system processed 81 sources, yielding 16 units of evidence.'),self.e)
        self.assertEqual(checks['publication_errors'][0]['category'],'inventory_mismatch')

    def test_inline_citations_are_accounted_without_rewriting_scientific_text(self):
        d=draft(self.e,text='Conditional statement [KU:r1#e1].',ids=['r1#f1'])
        contracts.validate_draft(d,self.e,['findings'])
        self.assertEqual(contracts.cited_units(d['sections'][0]['paragraphs'][0]),['r1#f1','r1#e1'])

    def test_incompatible_sources_remain_separate(self):
        e=fixtures.incompatible()
        self.assertEqual(len(e['sources']),2)
        self.assertIn('fever',e['units']['r2#f1']['fields']['Qualification'])
        self.assertNotEqual(e['units']['r1#f1']['source_ids'],e['units']['r2#f1']['source_ids'])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.e=fixtures.quantitative();self.d=draft(self.e,ids=['r1#f1']);self.r=review(self.d,[objection(self.d)])
    def generator(self,responses,**changes):
        model=ScriptedLLM(responses);model.context_window=30000
        model.count_tokens=lambda request:{'prompt_tokens':100,'context_window':model.context_window}
        return Generator(model,Path(self.tmp.name)/'log',**changes)

    def test_draft_challenger_revision_and_exact_request_provenance(self):
        g=self.generator([self.d,self.r,revision(self.d,self.r)])
        trial=g.pipeline(self.e,['findings'])
        self.assertEqual(len(g.model.requests),3);self.assertEqual(trial['revision']['draft'],self.d)
        for wire,action in zip(g.model.requests,['SOR1','SOR2','SOR3']):
            payload=loads(wire);self.assertEqual(payload['messages'][0]['content'],Path('prompt_templates/'+action+'.txt').read_text())
            self.assertEqual(payload['response_format']['type'],'json_schema')
        self.assertTrue(list(g.directory.glob('*-request.json')))

    def test_invalid_review_component_retained_but_not_automatically_admitted(self):
        bad=objection(self.d,'bad',assertion='Unquoted invented assertion')
        r=review(self.d,[objection(self.d),bad]);v=revision(self.d,self.r)
        g=self.generator([self.d,r,v]);trial=g.pipeline(self.e,['findings'])
        self.assertEqual(len(trial['rejected_objections']),1)
        third=loads(loads(g.model.requests[2])['messages'][1]['content'])
        self.assertEqual(len(third['review']['objections']),1)
        self.assertEqual(trial['review'],r)

    def test_wrong_model_bookkeeping_is_disclosed_and_never_rewrites_science(self):
        d=draft(self.e,sections=['methodology'],text='The system processed 81 sources, yielding 16 units of evidence.',ids=[],kind='process')
        r=review(d);g=self.generator([d,r,revision(d,r)])
        trial=g.pipeline(self.e,['methodology'],label='overview')
        sections,initial,withheld=compose([trial],self.e)
        self.assertEqual(next(s for s in sections if s['id']=='methodology')['paragraphs'],[])
        self.assertEqual(withheld[0]['paragraph']['text'],d['sections'][0]['paragraphs'][0]['text'])
        self.assertEqual(withheld[0]['checks'][0]['expected'],len(self.e['units']))
        self.assertEqual(next(s for s in initial if s['id']=='methodology')['paragraphs'][0]['text'],d['sections'][0]['paragraphs'][0]['text'])
        bad=draft(self.e,text='There are 999 research memories.',kind='source_finding');r=review(bad)
        g=self.generator([bad,r,revision(bad,r)])
        with self.assertRaisesRegex(ValueError,'publication errors'):g.pipeline(self.e,['findings'])

    def test_review_schema_binds_assertion_to_received_claim_without_extra_instructions(self):
        g=self.generator([self.d,self.r,revision(self.d,self.r)]);g.pipeline(self.e,['findings'])
        wire=loads(g.model.requests[1]);payload=loads(wire['messages'][1]['content'])
        schema=wire['response_format']['json_schema']['schema']
        variant=schema['properties']['objections']['items']['oneOf'][0]
        self.assertEqual(variant['properties']['claim_id']['const'],'c0')
        self.assertEqual(variant['properties']['assertion']['const'],self.d['sections'][0]['paragraphs'][0]['text'])
        self.assertEqual(wire['messages'][0]['content'],Path('prompt_templates/SOR2.txt').read_text())
        self.assertEqual(payload['draft'],self.d)

    def test_model_failure_retains_request_and_no_automatic_retry(self):
        g=self.generator([RuntimeError('inference failed')])
        with self.assertRaises(RuntimeError):g.pipeline(self.e,['findings'])
        self.assertEqual(len(g.model.requests),1);self.assertEqual(g.calls[0]['status'],'failed')
        self.assertTrue((g.directory/'001-SOR1-request.json').exists())

    def test_context_overflow_does_not_submit_or_shorten_scientific_fields(self):
        g=self.generator([]);g.model.context_window=100
        with self.assertRaisesRegex(ValueError,'no content truncated'):g.pipeline(self.e,['findings'])
        self.assertEqual(g.model.requests,[])

    def test_revision_overflow_partitions_complete_sections_and_evidence(self):
        d=draft(self.e,sections=['findings','limitations'],ids=['r1#f1']);r=review(d,[objection(d)])
        first={**deepcopy(d),'sections':[deepcopy(d['sections'][0])]}
        second={**deepcopy(d),'sections':[deepcopy(d['sections'][1])]}
        g=self.generator([d,r,revision(first,r),revision(second,review(second))])
        def count(wire):
            request=loads(wire);payload=loads(request['messages'][1]['content'])
            is_revision=request['messages'][0]['content']==Path('prompt_templates/SOR3.txt').read_text()
            return {'prompt_tokens':29000 if is_revision and len(payload['section_ids'])>1 else 100,'context_window':30000}
        g.model.count_tokens=count
        trial=g.pipeline(self.e,['findings','limitations'])
        self.assertEqual(trial['revision']['draft']['sections'],d['sections'])
        self.assertEqual(len(g.model.requests),4)
        for wire in g.model.requests[2:]:
            payload=loads(loads(wire)['messages'][1]['content'])
            self.assertEqual(payload['evidence']['units']['r1#f1'],self.e['units']['r1#f1'])
            self.assertEqual(len(payload['section_ids']),1)

    def test_review_overflow_covers_complete_paragraphs_with_all_original_evidence(self):
        d=draft(self.e,sections=['findings','limitations'],ids=['r1#f1'])
        first={**deepcopy(d),'sections':[deepcopy(d['sections'][0])]}
        r1=review(first,[objection(first)]);r2=review(d)
        combined=review(d,[objection(first,identity='review1.o1')])
        g=self.generator([d,r1,r2,revision(d,combined)])
        def count(wire):
            request=loads(wire);payload=loads(request['messages'][1]['content'])
            reviewing=request['messages'][0]['content']==Path('prompt_templates/SOR2.txt').read_text()
            many=reviewing and sum(len(s['paragraphs']) for s in payload['draft']['sections'])>1
            return {'prompt_tokens':29000 if many else 100,'context_window':30000}
        g.model.count_tokens=count;trial=g.pipeline(self.e,['findings','limitations'])
        self.assertEqual(len(g.model.requests),4)
        payloads=[loads(loads(w)['messages'][1]['content']) for w in g.model.requests[1:3]]
        self.assertEqual([p['review_coverage']['supplied_claim_ids'] for p in payloads],[['c0'],['c1']])
        self.assertTrue(all(p['evidence']['units']==self.e['units'] for p in payloads))
        self.assertEqual(trial['review']['objections'][0]['assertion'],r1['objections'][0]['assertion'])
        self.assertEqual(trial['revision']['dispositions'][0]['objection_id'],'review1.o1')

    def test_call_budget_is_enforced_without_extra_generation(self):
        g=self.generator([self.d,self.r,revision(self.d,self.r)],max_calls=2)
        with self.assertRaisesRegex(ValueError,'budget exhausted'):g.pipeline(self.e,['findings'])
        self.assertEqual(len(g.model.requests),2)

    def test_interrupted_request_is_recorded_as_uncertain(self):
        g=self.generator([KeyboardInterrupt()])
        with self.assertRaises(KeyboardInterrupt):g.pipeline(self.e,['findings'])
        self.assertEqual(g.calls[0]['status'],'uncertain')

    def test_schema_references_bound_to_only_supplied_units(self):
        g=self.generator([self.d,self.r,revision(self.d,self.r)]);g.pipeline(subset(self.e,['r1#f1']),['findings'])
        payload=loads(g.model.requests[0]);schema=payload['response_format']['json_schema']['schema']
        branches=schema['properties']['sections']['items']['properties']['paragraphs']['items']['oneOf']
        self.assertTrue(all(c['properties']['unit_ids']['items']['enum']==['r1#f1'] for c in branches))

    def test_resume_reuses_received_exact_requests_without_new_model_calls(self):
        g=self.generator([self.d,self.r,revision(self.d,self.r)]);g.pipeline(self.e,['findings'])
        fresh=ScriptedLLM([]);fresh.context_window=30000;fresh.count_tokens=g.model.count_tokens
        fresh.properties={'mutable_server_default':'changed'}
        restored=Generator(fresh,Path(self.tmp.name)/'log',resume_id=g.identity)
        trial=restored.pipeline(self.e,['findings'])
        self.assertEqual(fresh.requests,[]);self.assertEqual(trial['draft'],self.d)
        self.assertEqual(restored.model_identity,g.model_identity)
        self.assertEqual(len(restored.manifest['model_observations']),1)

    def test_resume_refuses_uncertain_submissions(self):
        g=self.generator([KeyboardInterrupt()])
        with self.assertRaises(KeyboardInterrupt):g.pipeline(self.e,['findings'])
        with self.assertRaisesRegex(ValueError,'uncertain'):
            Generator(g.model,Path(self.tmp.name)/'log',resume_id=g.identity)

    def test_empty_corpus_refuses_inference_without_manufacturing_evidence(self):
        e=deepcopy(self.e);e['units']={};g=self.generator([])
        with self.assertRaisesRegex(ValueError,'No canonical knowledge units'):g.run(e)
        self.assertEqual(g.model.requests,[])
