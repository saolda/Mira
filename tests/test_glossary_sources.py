"""Independent reviewed source attribution, admission and recovery safeguards."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from mira import glossary, glossary_sources as sources, glossary_view, r1
from mira.decisions import ScriptedLLM
from mira.format import digest, dumps, loads
from mira.interactions import Interactions, now
from mira.live import RecoveryRequired
from mira.research import Research
from test_glossary import proposal, evidence


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name); self.root = self.home / 'memory'
        self.r = Research(self.root, ScriptedLLM([]), {})
        self.r.initialize('Which pulmonary lesions have volume changes?', ['fixture'])
        with self.r.store.lock():
            token, docs, eqs, ledger = self.r.store.read(); state = self.state()
            files, _ = self.r.glossary.proposals(state, [proposal('Pulmonary nodules', None,
                passage='Pulmonary nodules occur in clinical imaging.')],
                evidence('Pulmonary nodules occur in clinical imaging.'), 'q1')
            self.r.store.publish(docs, eqs, ledger, token, files={**files, 'research/state.json': dumps(state)})
        self.source = dict(id='doi:synthetic-1', title='Synthetic source glossary',
            url='https://example.org/paper?x=1&y=2#definition', retrieved_at=now(),
            document_sha256=digest('original synthetic document'),
            content='Nodule\nA circumscribed opacity in lung tissue.\nMore text.')

    def state(self): return loads((self.root/'research/state.json').read_text())
    def get(self): return loads((self.root/'glossary/g1.json').read_text())
    def admit(self, **changes):
        kw = dict(passage='Nodule\nA circumscribed opacity in lung tissue.',
            definition='A circumscribed opacity in lung tissue.',
            qualification='Synthetic pulmonary morphology; not a diagnosis.', reviewer='test reviewer',
            mapping_reason='Source heading is the singular of this existing pulmonary concept.',
            log_dir=self.home/'log')
        kw.update(changes)
        return sources.admit(self.r.store, 'g1', self.source, **kw)

    def test_headed_extract_identity_provenance_idempotence_and_preservation(self):
        before = deepcopy(self.state()); old = self.r.store._files()
        result = self.admit(); self.assertTrue(result['changed'])
        record = self.get(); definition = record['definitions'][0]
        glossary.validate_record(record)
        self.assertEqual(definition['text'], 'A circumscribed opacity in lung tissue.')
        self.assertNotIn('origin', definition); self.assertNotIn('authority', definition)
        self.assertEqual(self.state()['glossary']['next_id'], 2)
        state = self.state(); state['glossary'] = before['glossary']; self.assertEqual(state, before)
        self.assertEqual({p:t for p,t in self.r.store._files().items() if p.startswith(('memories/', 'equations/'))},
                         {p:t for p,t in old.items() if p.startswith(('memories/', 'equations/'))})
        retained = loads((self.root/result['source_ref']).read_text())
        self.assertFalse(retained['query_submitted']); self.assertNotIn('node_id', retained)
        self.assertEqual(retained['results'][0]['content_sha256'], digest(self.source['content']))
        event = loads((self.root/'events'/f"{result['event_id']}.json").read_text())
        self.assertEqual(event['classification'], 'exact_source_extract'); self.assertTrue(event['mapping_reason'])
        token = self.r.store.read()[0]
        self.assertFalse(self.admit()['changed']); self.assertEqual(token, self.r.store.read()[0])
        self.assertEqual(r1.completed({result['source_ref']:dumps(retained)}, 'q1'), [])

    def test_paraphrase_missing_text_or_unreviewed_mapping_rejected_without_changes(self):
        before = self.r.store.read()[0]
        for changes in [dict(definition='Paraphrased scientific text.'),dict(passage='Not in source.'),
                        dict(mapping_reason=''),dict(reviewer=''),dict(aliases=['Invented alias']),
                        dict(relationships=[{'target':'g1','type':'SYNONYM_OF'}])]:
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.admit(**changes)
            self.assertEqual(before, self.r.store.read()[0])

    def test_source_identity_changes_rejected_and_no_duplicate_source_files(self):
        first = self.admit(); before = self.r.store.read()[0]
        for field in ['url','content','document_sha256']:
            original = deepcopy(self.source)
            self.source[field] = {'url':'https://other.example/paper','content':original['content']+' Changed.',
                'document_sha256':digest('different original document')}[field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'different content or URL'): self.admit()
            self.source = original
        self.assertEqual(before, self.r.store.read()[0])
        self.assertEqual(len(list((self.root/'research/results').glob('glossary_source_*.json'))), 1)
        self.assertEqual(first['source_ref'], self.admit()['source_ref'])

    def test_uncertain_submission_blocks_admission(self):
        trace = Interactions(self.r.store)
        identity = '20261103-' + 'a'*32
        (self.root/'interactions'/identity).mkdir()
        trace.write(identity, 'request', {'action':'G1','timestamp':now()})
        with self.assertRaisesRegex(ValueError, 'Unresolved submission'): self.admit()
        self.assertEqual(self.get()['definitions'], [])

    def test_runner_lease_and_pending_recovery_are_respected(self):
        trace = Interactions(self.r.store)
        with trace.execution(self.home/'log'):
            with self.assertRaises(BlockingIOError): self.admit()
        def fault(stage):
            if stage == 'prepared': raise RuntimeError('interrupted source review')
        with self.assertRaisesRegex(RuntimeError, 'interrupted'): self.admit(fault=fault)
        with self.assertRaises(RecoveryRequired): self.admit()
        status = self.r.store.recovery_status()
        self.assertTrue(status['operations'])
        self.r.store.repair(status['operations'][0]['id'], apply=True)
        self.assertEqual(len(self.get()['definitions']), 1)
        self.assertFalse(self.admit()['changed'])

    def test_source_urls_and_html_links_are_safe(self):
        for url in ['javascript:alert(1)','data:text/html,bad','//evil.example/x','https://user:pw@example.org/',
                    'https://example.org\\@evil.example','https://example.org/\nscript','https://example.org:bad/']:
            self.assertEqual(sources.source_url(url), '')
        self.admit()
        with self.r.store.lock(): self.r.glossary.export(self.state())
        html = (self.root/'research/glossary.html').read_text()
        self.assertIn('href="https://example.org/paper?x=1&amp;y=2#definition"', html)
        self.assertIn('rel="noreferrer noopener"', html)
        meta={'generated_at':now(),'revision':1,'commitment':digest('fixture'),
             'source_references':{(self.get()['evidence'][-1]['evidence_ref'],self.source['id']):
             {'url':'javascript:alert(1)','title':'<img src=x onerror=alert(1)>'}}}
        html=glossary_view.html([self.get()], metadata=meta)
        self.assertNotIn('href="javascript:',html); self.assertNotIn('<img src=x',html)

    def test_source_projection_keeps_attribution_and_reports_truncation(self):
        long=' '.join(['Pulmonary nodules are circumscribed lung opacities.']*18)
        self.source['content']=long
        self.admit(passage=long,definition=long)
        with self.r.store.lock():
            state=self.state(); ctx=r1.retrieval_context(state,[],self.r.store._files(),'q1')
            rows=self.r.glossary.retrieve(state,ctx,'q1')['entries']
        self.assertEqual(len(rows),1)
        row=rows[0]; self.assertTrue(row['definition_omitted_or_truncated']); self.assertTrue(row['terminology_only'])
        self.assertEqual(row['definition_sources'][0]['source_id'],self.source['id'])
        self.assertTrue(row['definition_sources'][0]['evidence_ref'].startswith('research/results/'))
        self.assertNotIn('authority',row['definition_sources'][0]); self.assertLessEqual(len(row['definition']),600)

    def test_definition_projection_preserves_late_scientific_conditions(self):
        text=('Pulmonary nodules are focal opacities of the lung parenchyma. '+
              'The source describes their morphology, attenuation and measurements across imaging examinations. '*2+
              'A spiculated margin is nonspecific and does not itself establish malignancy.')
        self.assertGreater(len(text),240);self.assertLess(len(text),600)
        self.source['content']=text;self.admit(passage=text,definition=text)
        with self.r.store.lock():
            state=self.state();ctx=r1.retrieval_context(state,[],self.r.store._files(),'q1')
            result=self.r.glossary.retrieve(state,ctx,'q1')
        self.assertEqual(result['entries'][0]['definition'],text)
        self.assertNotIn('definition_omitted_or_truncated',result['entries'][0])
        self.assertLessEqual(len(dumps(result).encode()),state['glossary']['token_budget'])

    def test_published_parenthetical_synonym_list_is_not_mere_cooccurrence(self):
        text='Reversed halo sign (also known as the atoll sign, reverse halo sign, and the fairy ring sign)'
        self.assertTrue(glossary.relationship_supported('Reverse halo sign','Reversed halo sign','SYNONYM_OF',text))
        self.assertFalse(glossary.alias_supported('Reverse halo sign','consolidation',text+' consolidation'))
        self.assertFalse(glossary.alias_supported('Reverse halo sign','halo sign',text))

    def test_source_qualification_preserves_applicability_and_wrong_scope_is_omitted(self):
        self.admit(qualification='Clinical diagnosis and prognosis risk assessment.')
        from mira import glossary_definitions as definitions
        record=self.get(); row=record['definitions'][0]
        self.assertTrue(definitions.applicable(row,record,definitions.context('How does diagnosis affect prognosis?','q2')))
        self.assertFalse(definitions.applicable(row,record,definitions.context('How do plant chloroplasts photosynthesize?','q2')))

    def test_compound_name_abbreviation_requires_complete_source_naming(self):
        term='Transforming growth factor (TGF)-beta'
        text=term+' is a synthetic source naming example.'
        self.assertTrue(glossary.alias_supported(term,'TGF-beta',text))
        self.assertTrue(glossary.alias_supported('TGF-beta',term,text))
        self.assertFalse(glossary.alias_supported(term,'TGF-beta','TGF and beta are mentioned together.'))
        self.assertFalse(glossary.alias_supported(term,'TGF-alpha',text))
        self.assertFalse(glossary.alias_supported(term,'beta',text))

    def seed_mismatched_reference(self, rows):
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read();state=self.state();record=self.get()
            ref='research/results/mismatched_source.json'
            record['evidence'].append({**record['evidence'][0], 'source_id':self.source['id'],'evidence_ref':ref})
            files={'glossary/g1.json':dumps(record)}
            state['glossary']['revision']+=1
            state['glossary']['commitment']=glossary.commitment(state['glossary']['commitment'],files)
            files.update({ref:dumps({'results':rows}),'research/state.json':dumps(state)})
            self.r.store.publish(docs,eqs,ledger,token,files=files)

    def test_retained_reference_must_contain_the_declared_identity(self):
        self.seed_mismatched_reference([dict(self.source,id='different-source')])
        before=self.r.store.read()[0]
        with self.assertRaisesRegex(ValueError,'missing or duplicate source identity'):self.admit()
        self.assertEqual(before,self.r.store.read()[0])

    def test_duplicate_identity_in_retained_source_is_ambiguous(self):
        self.seed_mismatched_reference([self.source,self.source])
        before=self.r.store.read()[0]
        with self.assertRaisesRegex(ValueError,'missing or duplicate source identity'):self.admit()
        self.assertEqual(before,self.r.store.read()[0])


if __name__ == '__main__': unittest.main()
