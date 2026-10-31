"""R4 scientific evidence, exact provenance and bounded-request integrity."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from mira import r4, research_tree as tree
from mira.decisions import ScriptedLLM, validate
from mira.format import Memory, Unit, Relationship, dumps, loads
from mira.interactions import read_records
from mira.research import Research
from mira.prompts import SLOTS, PromptTemplates


def source(identity, order, owner='q1', text='Synthetic sample A had a mean of 4 units.'):
    m = Memory(identity, 'Synthetic source study', 'Measured synthetic samples only; generalization is unknown.',
        metadata={'kind':'research','node_id':owner,'created_order':order,'source_memories':[],
            'synthesized_by':None,'evidence_ref':f'research/results/{identity}.json',
            'source':{'id':'source-'+identity,'url':'https://example.org/'+identity,'title':'Synthetic controlled study',
                'published':'2020-01-01','content_kind':'abstract'}})
    m.units.append(Unit(m.allocate('f'), 'Finding', {'Kind':'finding','Proposition':text,
        'Qualification':'N=10 synthetic samples; same measurement scale; no clinical inference.'}))
    return m


def synthesis(identity, order, inputs, text='The synthetic samples differ by 4 units.', owner='q1'):
    m = Memory(identity, 'Synthetic comparison', 'A scoped comparison; uncertainty remains.',
        metadata={'kind':'synthesis','node_id':owner,'created_order':order,'source_memories':[v.id for v in inputs],
            'synthesized_by':None,'markdown_format':2})
    m.units.append(Unit(m.allocate('f'), 'Comparison', {'Kind':'synthesis','Evidence status':'unverified',
        'Proposition':text,'Explanation':'Compare the supplied source measurements with equal scales.',
        'Provenance':'Interpretation restricted to the supplied synthetic studies.'}))
    m.relationships=[Relationship('f1','SYNTHESIZES',v.id+'#f1','unverified') for v in inputs]
    return m


def scientific_fixture():
    state=tree.initial('How do synthetic samples A and B compare?', ['fixture'], context_budget=50000)
    a=source('r1',1); b=source('r2',2,text='Synthetic sample B had a mean of 8 units.')
    s=synthesis('s1',3,[a,b])
    a.metadata['synthesized_by']=b.metadata['synthesized_by']='s1'
    state['nodes']['q1']['memory_ids']=['r1','r2','s1']
    return state,[a,b,s]


class R4ContextTests(unittest.TestCase):
    def test_supported_synthesis_has_exact_anchors_sources_and_no_duplicate_findings(self):
        state,docs=scientific_fixture(); original=deepcopy(docs)
        context=r4.context(state,docs,[],'q1'); science=context['scientific_evidence']
        self.assertEqual(set(context), {'question','question_scope','scientific_evidence'})
        self.assertEqual(set(context),set(SLOTS['R4']))
        self.assertEqual(context['question'],state['nodes']['q1']['question'])
        self.assertEqual(science['findings'][-1]['supporting_anchors'],['r1#f1','r2#f1'])
        self.assertEqual([f['id'] for f in science['findings']],['r1#f1','r2#f1','s1#f1'])
        self.assertEqual(science['memories'][0]['sources'],[docs[0].metadata['source']])
        self.assertEqual(science['memories'][0]['evidence_ref'],docs[0].metadata['evidence_ref'])
        self.assertEqual(science['findings'][0]['qualification'],docs[0].units[0].fields['Qualification'])
        self.assertTrue(science['coverage']['complete_for_selected_scope'])
        self.assertFalse(science['coverage']['truncated'])
        self.assertEqual(docs,original)
        self.assertEqual(context,r4.context(state,list(reversed(docs)),[],'q1'))
        validate('R4',{'decision':'answered','reason':'The supplied comparison answers the synthetic question.'},context)

    def test_unsupported_synthesis_keeps_the_source_disagreement_visible(self):
        state,docs=scientific_fixture()
        docs[-1].units[0].fields['Proposition']='The synthetic mean is 1000 units in every population.'
        context=r4.context(state,docs,[],'q1')
        findings={v['id']:v for v in context['scientific_evidence']['findings']}
        self.assertIn('1000', findings['s1#f1']['proposition'])
        self.assertIn('4 units',findings['r1#f1']['proposition'])
        self.assertIn('8 units',findings['r2#f1']['proposition'])
        self.assertIn('N=10',findings['r1#f1']['qualification'])
        prompt=PromptTemplates().render('R4',context)[0][0]['content']
        self.assertIn('Check synthesis conclusions against their supporting findings.',prompt)
        validate('R4',{'decision':'unresolved','reason':'The universal 1000-unit conclusion is unsupported by these source measurements.'},context)

    def test_conflicts_limits_and_unresolved_questions_are_preserved(self):
        state,docs=scientific_fixture()
        docs[1].units[0].fields['Proposition']='Synthetic sample A had a mean of 20 units.'
        docs[1].relationships.append(Relationship('f1','CONTRADICTS','r1#f1','unverified'))
        q=Unit(docs[0].allocate('q'),'Open measurement gap',{'Question':'Do other synthetic populations agree?',
            'State':'open','Origin':'derived','Qualification':'No other population has been measured.'})
        docs[0].units.append(q)
        science=r4.context(state,docs,[],'q1')['scientific_evidence']
        self.assertEqual(science['unresolved_questions'][0]['id'],'r1#q1')
        self.assertEqual(science['unresolved_questions'][0]['qualification'],q.fields['Qualification'])
        self.assertIn({'from':'r2#f1','type':'CONTRADICTS','to':'r1#f1','status':'unverified'},science['relationships'])
        self.assertEqual(len(science['findings']),3)

    def test_descendant_synthesis_and_nested_supports_survive_consumption(self):
        state,docs=scientific_fixture()
        state['nodes']['q2']=tree.node('q2','Which synthetic comparisons apply?','q1')
        state['nodes']['q1']['child_ids']=['q2'];state['next_node']=3
        for m in docs:m.metadata['node_id']='q2'
        docs.append(source('r3',4,'q2',text='A second synthetic population had a mean of 7 units.'))
        nested=synthesis('s2',5,[docs[2],docs[3]],owner='q2');docs.append(nested)
        docs[2].metadata['synthesized_by']=docs[3].metadata['synthesized_by']='s2'
        state['nodes']['q1']['memory_ids']=[];state['nodes']['q2']['memory_ids']=[m.id for m in docs]
        science=r4.context(state,docs,[],'q1')['scientific_evidence']
        self.assertEqual({v['id'] for v in science['findings']},{'r1#f1','r2#f1','s1#f1','r3#f1','s2#f1'})
        nested_finding=next(v for v in science['findings'] if v['id']=='s2#f1')
        self.assertEqual(nested_finding['supporting_anchors'],['s1#f1','r3#f1'])

    def test_legacy_synthesis_without_exact_citations_is_explicitly_uncited(self):
        state,docs=scientific_fixture();docs[-1].metadata.pop('markdown_format');docs[-1].relationships=[]
        science=r4.context(state,docs,[],'q1')['scientific_evidence']
        self.assertEqual(science['coverage']['uncited_synthesis_findings'],['s1#f1'])
        self.assertEqual(science['findings'][-1]['supporting_anchors'],[])
        self.assertEqual(len(science['findings']),3)

    def test_incomplete_support_coverage_cannot_be_treated_as_a_complete_answer(self):
        state,docs=scientific_fixture()
        docs[-1].relationships[0]=Relationship('f1','SYNTHESIZES','r1#f2','unverified')
        context=r4.context(state,docs,[],'q1')
        coverage=context['scientific_evidence']['coverage']
        self.assertFalse(coverage['complete_for_selected_scope'])
        self.assertEqual(coverage['missing_support_anchors'],['r1#f2'])
        with self.assertRaisesRegex(ValueError,'missing required scientific evidence'):
            validate('R4',{'decision':'answered','reason':'Complete.'},context)
        validate('R4',{'decision':'unresolved','reason':'The required support is missing.'},context)

    def test_killed_branches_and_their_synthesis_lineage_are_excluded(self):
        state,docs=scientific_fixture()
        state['nodes']['q2']=tree.node('q2','Off-track synthetic study?','q1');state['nodes']['q2']['status']='killed'
        state['nodes']['q1']['child_ids']=['q2'];state['next_node']=3
        docs[1].metadata['node_id']='q2'
        science=r4.context(state,docs,[],'q1')['scientific_evidence']
        self.assertEqual([m['id'] for m in science['memories']],['r1'])
        self.assertEqual(science['coverage']['omitted_memories'],[
            {'id':'r2','reason':'killed_branch_or_lineage'},{'id':'s1','reason':'killed_branch_or_lineage'}])

    def test_only_approved_scientific_inputs_and_scope_objectives(self):
        state,docs=scientific_fixture()
        state['nodes']['q2']=tree.node('q2','Which measurement scale applies?','q1')
        state['nodes']['q1']['child_ids']=['q2'];state['next_node']=3
        state['question_document']={'objectives':['- Compare measurements.','- Preserve uncertainty.']}
        context=r4.context(state,docs,[],'q2')
        self.assertEqual(context['question_scope'], {'parent_question':state['nodes']['q1']['question'],
            'root_question':state['nodes']['q1']['question'],'is_root':False,
            'research_objectives':state['question_document']['objectives']})
        text=dumps(context)
        for unwanted in ('profile_config','search_history','search_concepts','priority','cooldown','research_capacity','next_database_index'):
            self.assertNotIn(unwanted,text)

    def test_complete_scientific_context_blocks_at_budget_without_truncation(self):
        state,docs=scientific_fixture();docs[0].units[0].fields['Proposition']='Unabridged synthetic evidence ' * 3000
        context=r4.context(state,docs,[],'q1'); original=deepcopy(context)
        with tempfile.TemporaryDirectory() as directory:
            model=ScriptedLLM([]);r=Research(directory,model,{})
            state['context_budget']=15000
            with self.assertRaisesRegex(ValueError,'blocked_context_budget'):
                r._model({'action':'R4','cycle':1,'node_id':'q1'},'R4',context,state)
            self.assertEqual(model.requests,[]);self.assertEqual(read_records(directory),[])
        self.assertEqual(context,original)
        self.assertEqual(context['scientific_evidence']['findings'][0]['proposition'],docs[0].units[0].fields['Proposition'])
