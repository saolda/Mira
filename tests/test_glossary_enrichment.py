"""Production glossary completion, bounded generation and durable recovery."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from mira import glossary, glossary_definitions as gd, glossary_view, terminology
from mira.decisions import ScriptedLLM
from mira.format import digest, dumps, loads
from mira.glossary_enrichment import Completion, coverage, validate_generated
from mira.interactions import read_records
from mira.live import RecoveryRequired
from mira.research import Research
from test_glossary import evidence, proposal
from test_terminology import responses


class Model(ScriptedLLM):
    def __init__(self, *, mutate=None, window=24000, count=100):
        super().__init__([]); self.mutate = mutate; self.window = window; self.count = count

    def count_tokens(self, request):
        return {'prompt_tokens': self.count * len(loads(loads(request)['messages'][1]['content'])),
                'context_window': self.window}

    def complete(self, request):
        self.requests.append(request)
        entries = loads(loads(request)['messages'][1]['content'])
        result = {'entries': [{'term_id': r['term_id'], 'status': 'defined', 'definitions': [{
            'definition': r['term'] + ' describes a measurable pulmonary imaging characteristic in lung tissue.',
            'scope': 'Pulmonary imaging', 'ambiguity': ''}], 'reason': 'Defined using the supplied pulmonary context.'} for r in entries]}
        if self.mutate: result = self.mutate(result)
        return dumps({'model': self.model, 'choices': [{'finish_reason': 'stop', 'message': {'content': dumps(result)}}],
                      'usage': {'prompt_tokens': 100, 'completion_tokens': 60, 'total_tokens': 160}})


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name); self.root = self.home/'memory'
        self.r = Research(self.root, ScriptedLLM([]), {})
        self.r.initialize('Which pulmonary imaging characteristics describe lung lesions?', ['fixture'], context_budget=24000)
        self.model = Model()

    def add(self, terms, definition=None):
        with self.r.store.lock():
            token, docs, eqs, ledger = self.r.store.read(); state = self.state()
            passage = ' '.join(t + ' is mentioned in the pulmonary imaging report.' for t in terms)
            values = [proposal(t, definition, passage=passage) for t in terms]
            files, _ = self.r.glossary.proposals(state, values, evidence(passage), 'q1')
            self.r.store.publish(docs, eqs, ledger, token, files={**files, 'research/state.json': dumps(state)})

    def state(self): return loads((self.root/'research/state.json').read_text())
    def get(self, identity='g1'): return loads((self.root/'glossary'/f'{identity}.json').read_text())
    def operation(self, **kw):
        return Completion(self.r.store, model_factory=lambda: self.model, prompt_factory=self.fixture_prompt,
                          log_dir=self.home/'log', **kw)

    @staticmethod
    def fixture_prompt(data):
        # Synthetic test data only; never a production model instruction.
        return [{'role': 'system', 'content': 'synthetic fixture'}, {'role': 'user', 'content': dumps(data)}], {
            'files': [{'path': 'synthetic-test-fixture', 'sha256': digest('synthetic fixture')}]}

    def test_complete_backlog_beyond_r1_r3_limits_and_idempotence(self):
        for i in range(0, 19, 5): self.add([f'Pulmonary characteristic {n}' for n in range(i, min(i+5, 19))])
        before = deepcopy(self.state())
        result = self.operation().run(batch_size=4)
        self.assertEqual(result['after']['defined'], 19)
        self.assertEqual(result['processed'], 19); self.assertEqual(result['model_calls'], 5)
        for request in self.model.requests:
            entries = loads(loads(request)['messages'][1]['content'])
            self.assertLessEqual(len(entries), 4)
        canonical = self.r.store._files(); rec = self.get()
        self.assertEqual(rec['definitions'][0]['model_identity']['served_model'], self.model.model)
        self.assertEqual(rec['definitions'][0]['verification'], 'provisional')
        self.assertTrue(rec['definitions'][0]['generated_at'])
        after = self.state(); before.pop('glossary'); after.pop('glossary'); self.assertEqual(before, after)
        repeat = self.operation().run()
        self.assertEqual(repeat['model_calls'], 0); self.assertEqual(repeat['processed'], 0)
        self.assertEqual(canonical, self.r.store._files())
        self.assertEqual(len(self.get()['definitions']), 1)

    def test_bounded_selection_then_resume_and_empty_glossary(self):
        self.assertEqual(self.operation().run()['after']['total'], 0)
        self.add(['Zeta pulmonary sign', 'Alpha pulmonary sign', 'Beta pulmonary sign'])
        first = self.operation().run(limit=1)
        self.assertEqual(first['after']['defined'], 1)
        self.assertFalse(self.get('g1')['definitions']); self.assertTrue(self.get('g2')['definitions'])
        self.assertEqual(self.operation().run()['after']['defined'], 3)

    def test_authority_precedes_generation_and_rebuild_preserves_progress(self):
        self.add(['Organizing pneumonia'])
        transport = Mock(side_effect=responses('Organizing pneumonia', note='An inflammatory process of lung tissue.'))
        authority = terminology.Enricher(self.home/'cache', transport=transport, max_terms=1, sleep=lambda _: None)
        result = self.operation(authority=authority).run()
        self.assertEqual(result['authoritative_api_calls'], 2)
        self.assertEqual(result['after']['authoritative'], 1); self.assertEqual(result['model_calls'], 0)
        row = self.get()['definitions'][0]
        self.assertEqual(row['authority']['provider'], 'mesh'); self.assertEqual(row['authority']['concept_id'], 'M123')
        with self.r.store.lock():
            self.r.glossary.path.unlink(); self.r.glossary.ensure(self.state(), rebuild=True)
        self.assertEqual(self.operation(authority=authority).run()['processed'], 0)

    def test_research_definition_is_extractive_with_original_attribution(self):
        self.add(['Pulmonary sign'])
        with self.r.store.lock():
            token, docs, eqs, ledger = self.r.store.read(); state = self.state(); rec = self.get()
            rec['evidence'].append({**rec['evidence'][0], 'passage': 'Pulmonary sign refers to a radiological feature of lung tissue.'})
            files = {'glossary/g1.json': dumps(rec)}; meta = state['glossary']; meta['revision'] += 1
            meta['commitment'] = glossary.commitment(meta['commitment'], files)
            self.r.store.publish(docs, eqs, ledger, token, files={**files, 'research/state.json': dumps(state)})
        result = self.operation().run()
        self.assertEqual(result['research_definitions'], 1); self.assertEqual(result['model_calls'], 0)
        rec = self.get(); self.assertEqual(rec['definitions'][0]['evidence'], rec['evidence'][1])
        self.assertIn('source-1', glossary_view.markdown([rec]))

    def test_unresolved_abbreviation_is_explicit_not_invented(self):
        self.add(['ABC'])
        result = self.operation().run()
        self.assertEqual(result['after']['requiring_clarification'], 1)
        self.assertEqual(result['after']['without_usable_definitions'], 1)
        self.assertFalse(self.get()['definitions'])
        self.assertIn('source-supported expansion', result['after']['unresolved'][0]['reason'])
        self.assertEqual(self.operation().run()['model_calls'], 0)

    def test_model_abstention_preserves_ambiguity(self):
        self.add(['Ambiguous pulmonary marker'])
        def abstain(result):
            result['entries'][0].update(status='ambiguous', definitions=[], reason='The source does not establish which biomarker is meant.')
            return result
        self.model.mutate = abstain
        result = self.operation().run()
        self.assertEqual(result['after']['requiring_clarification'], 1)
        self.assertIn('biomarker', self.get()['enrichment'][-1]['reason'])

    def test_independently_invalid_definition_does_not_reject_valid_entry(self):
        self.add(['Alpha pulmonary sign', 'Beta pulmonary sign'])
        def reject(result):
            result['entries'][0]['definitions'][0]['definition'] = 'An important scientific concept.'
            return result
        self.model.mutate = reject
        result = self.operation().run()
        self.assertEqual(result['after']['defined'], 1); self.assertTrue(result['errors'])
        self.assertFalse(self.get()['definitions'])
        self.assertEqual(self.get()['enrichment'][-1]['status'], 'failed')
        self.assertEqual(self.operation().run(retry_failed=True)['model_calls'], 0)

    def test_duplicate_id_or_invented_citation_is_rejected(self):
        self.add(['Alpha pulmonary sign'])
        def duplicate(result): result['entries'] *= 2; return result
        self.model.mutate = duplicate
        self.assertEqual(self.operation().run()['after']['defined'], 0)
        rec = self.get()
        row = {'term_id': rec['id'], 'status': 'defined', 'definitions': [{'definition': 'A pulmonary sign according to PMID: 12345.',
            'scope': 'Pulmonary imaging', 'ambiguity': ''}], 'reason': 'Citation supplied.'}
        with self.assertRaisesRegex(ValueError, 'citations'): validate_generated(row, rec)

    def test_missing_service_is_reported_for_entire_backlog_without_retries(self):
        self.add(['Alpha pulmonary sign', 'Beta pulmonary sign'])
        factory = Mock(side_effect=OSError('local service offline'))
        operation = Completion(self.r.store, model_factory=factory, prompt_factory=self.fixture_prompt, log_dir=self.home/'log')
        result = operation.run(batch_size=1)
        self.assertEqual(factory.call_count, 1); self.assertEqual(result['after']['without_usable_definitions'], 2)
        self.assertEqual(len(result['errors']), 2); self.assertEqual(result['model_calls'], 0)

    def test_transient_authority_failure_falls_back_without_losing_reason(self):
        self.add(['Alpha pulmonary sign'])
        authority = terminology.Enricher(self.home/'cache', transport=Mock(side_effect=TimeoutError('offline')), max_terms=1)
        result = self.operation(authority=authority).run()
        self.assertEqual(result['after']['defined'], 1)
        self.assertEqual(self.get()['terminology'][-1]['status'], 'unavailable')

    def test_context_window_is_checked_and_batches_shrink(self):
        self.add(['Alpha pulmonary sign', 'Beta pulmonary sign', 'Gamma pulmonary sign'])
        self.model.count = 100; self.model.window = self.model.settings['max_tokens'] + 150
        result = self.operation().run(batch_size=3)
        self.assertEqual(result['model_calls'], 3)
        self.assertTrue(all(len(loads(loads(r)['messages'][1]['content'])) == 1 for r in self.model.requests))

    def test_single_overlarge_term_never_dispatches(self):
        self.add(['Alpha pulmonary sign']); self.model.window = 100
        result = self.operation().run()
        self.assertEqual(result['model_calls'], 0)
        self.assertIn('context window', result['after']['unresolved'][0]['reason'])

    def test_received_response_is_recovered_without_another_generation(self):
        self.add(['Alpha pulmonary sign', 'Beta pulmonary sign'])
        def fault(stage):
            if stage == 'response_received': raise RuntimeError('simulated interruption')
        with self.assertRaisesRegex(RuntimeError, 'simulated'): self.operation().run(fault=fault)
        self.assertEqual(len(self.model.requests), 1)
        result = self.operation().run()
        self.assertEqual(result['model_calls'], 0); self.assertEqual(result['resumed_responses'], 1)
        self.assertEqual(result['after']['defined'], 2)
        self.assertEqual(len(self.model.requests), 1)

    def test_uncertain_submission_is_never_retried_or_acknowledged(self):
        self.add(['Alpha pulmonary sign'])
        def fault(stage):
            if stage == 'before_model': raise RuntimeError('interrupted before dispatch')
        with self.assertRaises(RuntimeError): self.operation().run(fault=fault)
        with self.assertRaisesRegex(ValueError, 'Uncertain glossary submission'): self.operation().run(retry_failed=True)
        self.assertEqual(len(self.model.requests), 0)
        self.assertNotIn('outcome', read_records(self.root)[0])

    def test_transport_failure_remains_uncertain(self):
        self.add(['Alpha pulmonary sign'])
        self.model.complete = Mock(side_effect=TimeoutError('request timed out'))
        result = self.operation().run()
        self.assertEqual(result['after']['unresolved'][0]['status'], 'uncertain')
        with self.assertRaisesRegex(ValueError, 'Uncertain glossary'): self.operation().run()
        self.assertEqual(self.model.complete.call_count, 1)

    def test_publication_recovery_preserves_definitions_and_no_regeneration(self):
        self.add(['Alpha pulmonary sign'])
        def fault(stage):
            # The prepared model submission is the first journal operation;
            # interrupt after the generated definition has reached its journal.
            if stage == 'before_commit' and self.model.requests: raise RuntimeError('publication interruption')
        with self.assertRaises(RuntimeError): self.operation().run(fault=fault)
        status = self.r.store.recovery_status()
        self.assertTrue(status['operations'])
        with self.assertRaises(RecoveryRequired): self.operation().run()
        self.r.store.repair(status['operations'][0]['id'], apply=True)
        self.assertEqual(self.operation().run()['model_calls'], 0)
        self.assertEqual(len(self.get()['definitions']), 1)

    def test_new_context_reopens_completed_entry_without_duplicate_generation(self):
        self.add(['Alpha pulmonary sign']); self.operation().run()
        self.add(['Alpha pulmonary sign', 'Beta pulmonary sign'])
        result = self.operation().run()
        self.assertEqual(result['after']['defined'], 2)
        self.assertEqual(len(self.get()['definitions']), 1)

    def test_generated_definitions_require_committed_event_provenance(self):
        self.add(['Alpha pulmonary sign']); self.operation().run()
        rec = self.get(); rec['definitions'].append({**rec['definitions'][0], 'text': 'A fabricated pulmonary definition about lung tissue.',
                                                   'event_ref': 'events/' + 'a'*32 + '.json'})
        with self.r.store.lock():
            token, docs, eqs, ledger = self.r.store.read(); state = self.state()
            files = {'glossary/g1.json': dumps(rec)}; meta = state['glossary']; meta['revision'] += 1
            meta['commitment'] = glossary.commitment(meta['commitment'], files)
            with self.assertRaisesRegex(ValueError, 'provenance'):
                self.r.store.publish(docs, eqs, ledger, token, files={**files, 'research/state.json': dumps(state)})

    def test_unicode_views_consistent_coverage_attribution_and_determinism(self):
        self.add(['Δ radiomics', '肺 pulmonary sign']); self.operation().run()
        with self.r.store.lock(): self.r.glossary.export(self.state())
        html = (self.root/'research/glossary.html').read_text(); md = (self.root/'research/glossary.md').read_text()
        for text in ['Δ radiomics', '肺 pulmonary sign', 'Provisional', self.model.model]:
            self.assertIn(text, html); self.assertIn(text, md)
        self.assertIn('Provisional definitions only', html); self.assertIn('Glossary revision', html)
        self.assertNotIn('No source definition recorded.', html)
        self.assertIn('glossary-search', html)
        canonical = self.r.store._files()
        with self.r.store.lock():
            self.r.glossary.path.unlink(); self.r.glossary.export(self.state())
        self.assertEqual(html, (self.root/'research/glossary.html').read_text())
        self.assertEqual(md, (self.root/'research/glossary.md').read_text())
        self.assertEqual(canonical, self.r.store._files())

    def test_standard_cli_reports_without_network_calls(self):
        self.add(['Alpha pulmonary sign'])
        raw = subprocess.check_output([sys.executable, '-m', 'mira', '--root', str(self.root), 'glossary-enrich', '--status'], text=True)
        self.assertEqual(loads(raw)['total'], 1); self.assertIn('Alpha pulmonary sign', raw)

    def test_volume_diameter_conflation_is_rejected(self):
        self.add(['Volume doubling time'])
        row = {'term_id': 'g1', 'status': 'defined', 'definitions': [{
            'definition': 'Volume doubling time is the same as diameter doubling time for a pulmonary lesion.',
            'scope': 'Pulmonary imaging', 'ambiguity': ''}], 'reason': 'Incorrect relationship.'}
        with self.assertRaisesRegex(ValueError, 'distinct quantities'): validate_generated(row, self.get())

    def test_explicitly_disabled_model_never_calls_factory(self):
        self.add(['Alpha pulmonary sign', 'Beta pulmonary sign'])
        factory = Mock(return_value=self.model)
        operation = Completion(self.r.store, model_factory=factory, prompt_factory=None, log_dir=self.home/'log')
        result = operation.run()
        self.assertEqual(result['model_calls'], 0); factory.assert_not_called()
        self.assertEqual(result['after']['defined'], 0)
        self.assertEqual({r['status'] for r in result['after']['unresolved']}, {'failed'})
        self.assertEqual(operation.run()['processed'], 0)

    def test_due_authority_upgrade_supplements_provisional_without_regeneration(self):
        self.add(['Organizing pneumonia']); self.operation().run()
        original = self.get()['definitions'][0]
        transport = Mock(side_effect=responses('Organizing pneumonia', note='An inflammatory process of lung tissue.'))
        authority = terminology.Enricher(self.home/'cache', transport=transport, max_terms=1, sleep=lambda _: None)
        upgraded = self.operation(authority=authority).run(upgrade_provisional=True)
        self.assertEqual(upgraded['model_calls'], 0)
        self.assertEqual(upgraded['after']['authoritative'], 1)
        self.assertEqual(upgraded['after']['provisional_only'], 0)
        rec = self.get(); self.assertIn(original, rec['definitions'])
        self.assertIn('authority', gd.preferred(rec)[0])

    def test_bad_authority_response_preserves_reason_and_cooldown(self):
        self.add(['Alpha pulmonary sign'])
        authority = Mock(); authority.enrich.return_value = ({'g1': {'status': 'matched'}}, {'api_calls': 1})
        result = self.operation(authority=authority).run()
        self.assertEqual(result['after']['defined'], 1)
        self.assertEqual(self.get()['terminology'][-1]['status'], 'error')
        self.assertIn('invalid terminology', self.get()['terminology'][-1]['reason'])
        self.assertFalse(terminology.lookup_due(self.get(), __import__('time').time()))

    def test_failed_definition_can_be_explicitly_retried_only_after_cooldown(self):
        self.add(['Alpha pulmonary sign'])
        def reject(result):
            result['entries'][0]['definitions'][0]['definition'] = 'A scientific concept.'
            return result
        self.model.mutate = reject; self.operation(clock=lambda: 1000).run()
        self.model.mutate = None
        before = self.operation(clock=lambda: 1001).run(retry_failed=True)
        self.assertEqual(before['model_calls'], 0)
        after = self.operation(clock=lambda: 1000 + terminology.FAILURE_COOLDOWN + 1).run(retry_failed=True)
        self.assertEqual(after['model_calls'], 1); self.assertEqual(after['after']['defined'], 1)

    def test_distinct_meanings_are_preserved_with_separate_scopes(self):
        self.add(['Alpha pulmonary sign'])
        def meanings(result):
            result['entries'][0]['definitions'].append({'definition': 'A named pulmonary imaging pattern involving lung tissue morphology.',
                'scope': 'Pulmonary morphology', 'ambiguity': 'A distinct usage recorded provisionally.'})
            return result
        self.model.mutate = meanings
        result = self.operation().run()
        self.assertEqual(result['after']['defined'], 1); self.assertEqual(len(self.get()['definitions']), 2)
        self.assertEqual(self.operation().run()['model_calls'], 0)

    def test_default_g1_uses_exact_approved_template_and_records_provenance(self):
        self.add(['Alpha pulmonary sign'])
        operation = Completion(self.r.store, model_factory=lambda: self.model, log_dir=self.home/'log')
        result = operation.run()
        self.assertEqual(result['after']['defined'], 1)
        request = read_records(self.root)[0]['request']
        source = (Path(__file__).parents[1]/'prompt_templates/G1.txt').read_text()
        self.assertEqual(digest(source), '0a2726f28234058e7147459493b4c338bdf6d66976ea72c2dccda11c0d6ed673')
        self.assertEqual(request['action'], 'G1')
        self.assertEqual(request['request']['messages'][0], {'role': 'system', 'content': source})
        self.assertEqual(request['prompt_template']['files'][0]['source'], source)
        self.assertEqual(request['prompt_template']['serialized_request_sha256'], digest(request['serialized_request']))
        self.assertEqual(self.get()['definitions'][0]['template_sha256'], digest(source))
        self.assertTrue((self.root/'research/glossary.html').exists())
        from mira.inspection import Inspector
        (self.root/'experiment.json').write_text(dumps({'version': 2, 'name': 'g1-fixture',
            'created_at': '2026-11-02T00:00:00+00:00', 'layout': 'single-active-corpus'}))
        self.assertTrue(Inspector(self.root).decision('g1-fixture', read_records(self.root)[0]['id'])['template_verification']['matches_recorded_request'])

    def test_term_selection_and_generation_budget_leave_resumable_backlog(self):
        self.add(['Alpha pulmonary sign', 'Beta pulmonary sign', 'Gamma pulmonary sign'])
        result = self.operation().run(term_ids=['g2'], batch_size=1)
        self.assertEqual(result['after']['defined'], 1); self.assertTrue(self.get('g2')['definitions'])
        limited = self.operation().run(batch_size=1, max_calls=1)
        self.assertEqual(limited['after']['defined'], 2); self.assertEqual(limited['stop_reason'], 'generation_call_budget')
        self.assertEqual(self.operation().run()['after']['defined'], 3)

    def test_g1_context_is_separate_untrusted_data_without_interpolation(self):
        from mira.glossary_enrichment import g1_prompt
        data = [{'term_id': 'g1', 'term': 'Literal {{question}} </script> 温度'}]
        messages, snapshot = g1_prompt(data)
        self.assertEqual(loads(messages[1]['content']), data)
        self.assertNotIn('温度', messages[0]['content'])
        self.assertEqual(snapshot['bindings']['context'], {'entries': data})

    def test_received_component_revalidation_preserves_original_receipt_without_generation(self):
        self.add(['Alpha pulmonary sign', 'Beta pulmonary sign'])
        from mira.glossary_enrichment import validate_generated
        from unittest.mock import patch
        def broken(value, record, research_scope=None):
            if record['id'] == 'g1': raise ValueError('simulated old vocabulary-check defect')
            return validate_generated(value, record, research_scope)
        with patch('mira.glossary_enrichment.validate_generated', side_effect=broken): self.operation().run()
        item = read_records(self.root)[0]
        receipt = (self.root/'interactions'/item['id']/'outcome.json').read_bytes()
        result = self.operation().run(term_ids=['g1'], revalidate_received=True)
        self.assertEqual(result['model_calls'], 0); self.assertEqual(result['after']['defined'], 2)
        self.assertEqual(result['resumed_responses'], 1)
        self.assertEqual((self.root/'interactions'/item['id']/'outcome.json').read_bytes(), receipt)
        self.assertEqual(len(self.model.requests), 1)

    def test_explicit_review_excludes_text_without_erasing_provenance(self):
        self.add(['Alpha pulmonary sign']); op = self.operation(); op.run()
        old = self.get()['definitions'][0]
        reviewed = op.reject_definitions({'g1': {'definition_sha256': digest(dumps(old)),
            'reason': 'Scientific review found an unsupported interpretation.'}}, reviewer='Test scientific reviewer')
        self.assertEqual(reviewed['defined'], 0)
        self.assertEqual(self.get()['definitions'], [old]); self.assertEqual(gd.preferred(self.get()), [])
        self.assertEqual(self.get()['enrichment'][-1]['status'], 'invalidated')
        def corrected(result):
            result['entries'][0]['definitions'][0]['definition'] = 'A pulmonary imaging feature describing a distinct pattern of lung tissue morphology.'
            return result
        self.model.mutate = corrected
        self.assertEqual(op.run()['after']['defined'], 1)
        self.assertIn(old, self.get()['definitions'])
        self.assertEqual(len(self.get()['definition_reviews']), 1)

    def test_vocabulary_check_uses_research_question_not_just_occurrence_passage(self):
        self.add(['Relapse']); rec = self.get()
        rec['evidence'][0]['passage'] = 'Relapse occurred in 56 patients.'
        value = {'term_id': 'g1', 'status': 'defined', 'reason': 'Clinical recurrence.', 'definitions': [{
            'definition': 'Recurrence of disease after an interval of improvement or remission.',
            'scope': 'Pulmonary clinical outcomes', 'ambiguity': ''}]}
        with self.assertRaisesRegex(ValueError, 'vocabulary'): validate_generated(value, rec)
        self.assertEqual(validate_generated(value, rec, {'question': 'Which pulmonary lesions recur?'}), value)

    def test_scientific_review_can_preserve_unresolved_meaning_without_regeneration(self):
        self.add(['Alpha pulmonary sign']);op=self.operation();op.run()
        old=self.get()['definitions'][0]
        result=op.reject_definitions({'g1':{'definition_sha256':digest(dumps(old)),
            'reason':'Source defines only the generic sign; the specific modifier is unresolved.'}},
            reviewer='Test source reviewer',requires_clarification=True)
        self.assertEqual(result['requiring_clarification'],1)
        self.assertEqual(result['without_usable_definitions'],1)
        self.assertEqual(self.get()['definitions'],[old])
        token=self.r.store.read()[0];again=op.run()
        self.assertEqual(again['model_calls'],0);self.assertEqual(again['processed'],0)
        self.assertEqual(token,self.r.store.read()[0]);self.assertEqual(len(self.model.requests),1)
        self.assertFalse(gd.eligible(self.get(),gd.context('Which pulmonary features are relevant?','q1')))
        from mira import r1
        with self.r.store.lock():
            state=self.state();ctx=r1.retrieval_context(state,[],self.r.store._files(),'q1')
            entry=self.r.glossary.retrieve(state,ctx,'q1')['entries'][0]
        self.assertFalse(entry['definition_eligible']);self.assertTrue(entry['requires_clarification'])

    def test_source_window_uses_admitted_passage_when_canonical_label_is_absent(self):
        from mira.glossary_sources import admit
        from mira.interactions import now
        self.add(['Alpha pulmonary sign'])
        passage='A late source heading describes pulmonary air-filled structures.'
        source=dict(id='fixture:headed-source',title='Synthetic source',url='https://example.org/headed',
            retrieved_at=now(),document_sha256=digest('synthetic original'),
            content=('Unrelated front matter. '*200)+passage+' Pulmonary morphology follows.')
        admit(self.r.store,'g1',source,passage=passage,qualification='Pulmonary morphology.',
            reviewer='Test reviewer',mapping_reason='The source heading maps to the existing sign.',log_dir=self.home/'log')
        record=self.get();op=self.operation();state=self.state()
        request,data,_,_=op._request([record],state,{'g1':record})
        window=data[0]['retained_source_context'][0]['verbatim_excerpt']
        self.assertIn(passage,window);self.assertLessEqual(len(window),1800)
        self.assertEqual(self.model.requests,[])  # Tokenization only, no generation.

    def test_cohort_measurements_are_not_generated_definitions(self):
        self.add(['Alpha pulmonary sign'])
        row = {'term_id': 'g1', 'status': 'defined', 'reason': 'Cohort observation.', 'definitions': [{
            'definition': 'A pulmonary sign significantly more frequent in 24% of patients in a study cohort.',
            'scope': 'Pulmonary imaging', 'ambiguity': ''}]}
        with self.assertRaisesRegex(ValueError, 'empirical findings'): validate_generated(row, self.get())

    def test_context_hydrates_hash_validated_source_text_and_rejects_corruption(self):
        self.add(['Alpha pulmonary sign'])
        from mira import sources
        source = {'id': 'source-1', 'title': 'Retained pulmonary source', 'url': 'https://example.org/paper',
            'content': 'Alpha pulmonary sign is discussed with the morphology of lung tissue.',
            'content_kind': 'abstract', 'truncated': False}
        with self.r.store.lock():
            token, docs, eqs, ledger = self.r.store.read()
            payload = sources.save_payload(self.r.store, 'a'*32, [source])
            evidence_row = {'status': 'ok', 'reference': 'research/results/fixture.json',
                            'results': [sources.descriptor(source)], **payload}
            self.r.store.publish(docs, eqs, ledger, token, files={'research/results/fixture.json': dumps(evidence_row)})
        self.operation().run()
        req = read_records(self.root)[0]['request']
        self.assertEqual(req['context']['entries'][0]['retained_source_context'][0]['verbatim_excerpt'], source['content'])
        # Corrupt disposable content must fail before another submission.
        path = self.root/payload['payload_ref']; path.write_text(path.read_text()+' ')
        op = self.operation()
        with self.r.store.lock():
            state = self.state(); rec = self.get()
            with self.assertRaisesRegex(ValueError, 'digest mismatch'): op._request([rec], state, {'g1': rec})
        self.assertEqual(len(self.model.requests), 1)

