"""Focused standalone experiment tests; never open or mutate active research."""
from copy import deepcopy
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('ku_experiment',Path(__file__).resolve().parents[1]/'scripts/synthesis_discovery_experiment.py')
e=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(e)


def unit(identity, text='Instrument A increases signal by 10 percent.', source='fixture:1', qualification='Laboratory fixture, not medical evidence.'):
    return {'id':identity,'memory_id':identity.split('#')[0], 'proposition':text, 'qualification':qualification,
        'explanation':'','type':'finding','structural_type':'finding','evidence_status':'unverified',
        'source_ids':[source],'label':'Fixture observation','sources':[{'id':source}],
        'scientific_fields':{'Proposition':text,'Qualification':qualification},
        'content_version':e.digest(text+qualification+source)}


class DiscoveryTests(unittest.TestCase):
    def test_conservative_normalization_preserves_polarity_numbers_and_comparators(self):
        self.assertEqual(e.normal(' A  &gt; 10 '),'a > 10')
        self.assertNotEqual(e.normal('A > 10'),e.normal('A < 10'))
        a=unit('r1#f1');b=unit('r2#f1','Instrument A decreases signal by 10 percent.')
        result=e.annotate(a,b,.9,.99)
        self.assertNotEqual(result['category'],'exact_duplicate')
        self.assertIn('direction',result['safeguard_differences'])

    def test_exact_content_and_source_independence(self):
        a=unit('r1#f1'); b=unit('r1#f2')
        self.assertEqual(e.annotate(a,b,1,1)['category'],'exact_duplicate')
        b=unit('r2#f1',source='fixture:2')
        self.assertEqual(e.annotate(a,b,1,1)['category'],'independent_corroboration_requires_review')
        self.assertFalse(e.annotate(a,b,1,1)['automatic_merge_or_delete'])

    def test_numerical_timeframe_species_status_qualifications_block_duplicates(self):
        a=unit('r1#f1')
        for text in ['Instrument A increases signal by 20 percent.','Instrument A does not increase signal by 10 percent.']:
            b=unit('r2#f1',text)
            self.assertNotEqual(e.annotate(a,b,.99,.99)['category'],'exact_duplicate')
        for qualification in ['Mice at 4 weeks.','Humans at 4 days.','Different uncertainty interval.']:
            b=unit('r2#f1',qualification=qualification)
            self.assertNotEqual(e.content_key(a),e.content_key(b))
        b=deepcopy(a); b['evidence_status']='supported'
        self.assertNotEqual(e.content_key(a),e.content_key(b))

    def test_representation_excludes_administrative_metadata(self):
        a=unit('r1#f1');b=deepcopy(a);b['id']='other';b['source_ids']=['secret'];b['sources']=[{'id':'secret'}]
        for mode in ['A','B']:
            self.assertEqual(e.representation(a,mode),e.representation(b,mode))
            self.assertIn(a['qualification'],e.representation(a,mode))
        self.assertNotEqual(e.representation(a,'A'),e.representation(a,'B'))

    def test_set_order_version_superset_and_discovery(self):
        a,b,c=unit('r1#f1'),unit('r2#f1'),unit('r3#f1')
        self.assertEqual(e.set_fingerprint([a,b]),e.set_fingerprint([b,a]))
        with self.assertRaises(ValueError):e.set_fingerprint([a,a])
        register=e.AttemptRegister()
        self.assertEqual(register.status([a,b]),'available')
        row=register.start([a,b],'G1');register.finish(row,'completed',result={'ideas':[]})
        self.assertEqual(register.status([b,a]),'completed')
        self.assertEqual(register.status([a,b,c]),'available')
        changed=deepcopy(a);changed['content_version']='new_version'
        self.assertEqual(register.status([changed,b]),'available')

    def test_register_persistence_and_uncertain_transport(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'register.json';r=e.AttemptRegister(path);a,b=unit('r1#f1'),unit('r2#f1')
            row=r.start([a,b],'G1')
            self.assertEqual(e.AttemptRegister(path).status([a,b]),'uncertain_do_not_retry')
            r.finish(row,'uncertain',reason='Request interrupted.')
            self.assertEqual(e.AttemptRegister(path).status([a,b]),'uncertain_do_not_retry')
            with self.assertRaises(ValueError):r.start([b,a],'G2')
            r.finish(row,'validation_failed',reason='No accepted evaluation.')
            self.assertEqual(r.status([a,b]),'available')

    def test_reviewed_equivalence_preserves_sources_and_versions(self):
        a,b,c=unit('r1#f1'),unit('r2#f1','An increase of 10 percent in signal is measured with instrument A.'),unit('r3#f1','Complementary calibration.')
        reviewed={x['id']:{'class':'same-proposition','version':x['content_version']} for x in [a,b]}
        self.assertEqual(e.equivalence_fingerprint([a,c],reviewed),e.equivalence_fingerprint([b,c],reviewed))
        b['source_ids']=['independent:2']
        self.assertNotEqual(e.equivalence_fingerprint([a,c],reviewed),e.equivalence_fingerprint([b,c],reviewed))
        b['source_ids']=a['source_ids'];b['content_version']='changed'
        self.assertNotEqual(e.equivalence_fingerprint([a,c],reviewed),e.equivalence_fingerprint([b,c],reviewed))

    def test_groups_stable_bounded_and_no_fill_for_unrelated(self):
        records=[unit('r'+str(i)+'#f1') for i in range(1,9)]
        vectors={'B':[[1.,0.] for _ in records]}
        pairs,_=e.pairwise(records,vectors)
        groups,stats=e.group_candidates(records,pairs,k=4)
        self.assertTrue(groups)
        self.assertTrue(all(2<=len(g['unit_ids'])<=5 for g in groups))
        self.assertEqual(groups,e.group_candidates(records,list(reversed(pairs)),k=4)[0])
        self.assertGreaterEqual(stats['redundant_exact_sets_avoided'],0)
        isolated=[{'ids':['r1#f1','r2#f1'],'hybrid':{'B':.1},'lexical':0,'semantic':{'B':.2},'duplicate':{}}]
        self.assertEqual(e.group_candidates(records[:2],isolated)[0],[])

    def test_incremental_topk_handles_ties(self):
        records=[unit('r'+str(i)+'#f1') for i in range(1,7)]
        vectors=[[1.,0.] for _ in records];pairs,_=e.pairwise(records,{'B':vectors})
        self.assertTrue(e.compute_costs(records,vectors,pairs,k=2)['incremental_equals_full'])
        self.assertTrue(e.compute_costs(list(reversed(records)),vectors,pairs,k=2)['incremental_equals_full'])
        reversed_pairs,_=e.pairwise(list(reversed(records)),{'B':vectors})
        self.assertEqual(pairs,reversed_pairs)

    def test_validation_rejects_unsupplied_and_duplicate_references(self):
        a,b=unit('r1#f1'),unit('r2#f1')
        value={'disposition':'ideas','reason':'Fixture','ideas':[{'category':'comparison','objective':'Compare calibration',
            'unit_ids':[a['id'],b['id']],'potential_new_understanding':'Unknown','limitations':['Fixture only'],'novelty':'Uncertain'}]}
        self.assertEqual(e.validate_s2(value,[a,b]),value)
        for ids in [['r1#f1','unknown'],['r1#f1','r1#f1'],['r1#f1']]:
            bad=deepcopy(value);bad['ideas'][0]['unit_ids']=ids
            with self.assertRaises(ValueError):e.validate_s2(bad,[a,b])
        self.assertEqual(e.validate_s2({'disposition':'no_candidate','ideas':[],'reason':'No integration.'},[a,b])['ideas'],[])

    def test_novelty_review_is_not_publication(self):
        a=unit('r1#f1');b=unit('s1#f1')
        result=e.novelty_check(b,[a])
        self.assertEqual(result['action'],'review_required');self.assertEqual(result['matches'],['r1#f1'])
        self.assertEqual(e.novelty_check(unit('s2#f1','Different assumptions'),[a])['matches'],[])

    def test_output_cannot_be_inside_read_only_corpus(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'memory';root.mkdir()
            with self.assertRaisesRegex(ValueError,'outside the corpus'):
                e.prepare(root,root/'experimental','http://127.0.0.1:8091')
            self.assertFalse((root/'experimental').exists())

    def test_request_retains_complete_propositions_roles_and_no_s3(self):
        class LLM:model='fixture';settings={'temperature':0,'max_tokens':4096}
        a,b=unit('r1#f1'),unit('r2#f1')
        payload=e.loads(e.make_request([a,b],{'id':'G1','reason':'Fixture'},'Question',LLM()))
        self.assertEqual([m['role'] for m in payload['messages']],['system','user'])
        self.assertEqual(payload['max_tokens'],4096)
        context=e.loads(payload['messages'][1]['content'])
        self.assertEqual(context['knowledge_units'][0]['proposition'],a['proposition'])
        self.assertIn('not production S1/S2',payload['messages'][0]['content'])
