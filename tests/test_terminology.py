"""Deterministic authoritative matching and optional, atomic R3 enrichment."""
from copy import deepcopy
from contextlib import closing
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from mira import glossary, glossary_view, r1, terminology
from mira.decisions import ScriptedLLM
from mira.format import dumps, loads
from mira.interactions import read_records
from mira.live import RecoveryRequired
from mira.research import Research
from mira.search import FixtureSearch
from test_glossary import evidence, proposal

TERM = 'Organizing pneumonia'
TEXT = TERM + ' is an inflammatory lung process.'
NOTE = 'An inflammatory tissue process, with qualifications <script>alert(1)</script>.'


def rdf(term=TERM, preferred='Organizing Pneumonia', identity='M123', note=NOTE):
    def uri(value): return {'type': 'uri', 'value': 'http://id.nlm.nih.gov/mesh/' + value}
    def literal(value): return {'type': 'literal', 'xml:lang': 'en', 'value': value}
    rows = []
    for i, name in enumerate(dict.fromkeys([term, preferred])):
        row = {'concept': uri(identity), 'preferred': literal(preferred), 'matched': uri('T123'),
               'alias': uri('T' + str(123+i)), 'name': literal(name), 'descriptor': uri('D123')}
        if note is not None: row['scope'] = literal(note)
        rows.append(row)
    return {'results': {'bindings': rows}}


def responses(term=TERM, **kw):
    return [[{'resource': 'http://id.nlm.nih.gov/mesh/T123', 'label': term}], rdf(term, **kw)]


def plan(selected=(TERM,), new=()):
    return {'new_concepts': list(new), 'search_concepts': list(selected), 'reason': 'Fixture scientific terms.'}


class FakeClock:
    def __init__(self): self.now = 1000
    def time(self): return self.now
    def sleep(self, delay): self.now += delay


class TerminologyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'memory'
        self.cache = Path(self.temp.name)/'cache'
        self.clock = FakeClock()

    def enricher(self, rows=None, **kwargs):
        self.transport = Mock(side_effect=responses() if rows is None else rows)
        return terminology.Enricher(self.cache, transport=self.transport, clock=self.clock.time,
            monotonic=self.clock.time, sleep=self.clock.sleep, **kwargs)

    def lookup(self, term=TERM, rows=None, **kw):
        e = self.enricher(rows, **kw)
        outcomes, report = e.enrich([{'id': 'g1', 'term': term}])
        return outcomes['g1'], report, e

    def test_exact_match_scope_note_and_identity_cache(self):
        outcome, report, enricher = self.lookup()
        self.assertEqual(outcome['status'], 'matched')
        concept = outcome['concepts'][0]
        self.assertEqual(concept['concept_id'], 'M123')
        self.assertEqual(concept['descriptions'][0]['type'], 'scope_note')
        self.assertEqual(concept['descriptions'][0]['text'], NOTE)
        self.assertNotIn(TERM, NOTE)
        self.assertEqual(report['api_calls'], 2)
        self.assertTrue((self.cache/'mesh-M123.json').exists())
        repeat, audit = enricher.enrich([{'id':'g1', 'term': TERM.upper()}])
        self.assertEqual(repeat['g1']['status'], 'matched')
        self.assertEqual(audit['api_calls'], 0)
        self.assertEqual(audit['cache_hits'], 1)
        self.assertEqual(self.transport.call_count, 2)
        self.clock.now += 86401
        self.transport.side_effect = responses()
        refreshed, audit = enricher.enrich([{'id':'g1', 'term':TERM}])
        self.assertEqual(audit['concept_cache_hits'], 1)
        self.assertEqual(refreshed['g1']['concepts'][0]['retrieved_at'], concept['retrieved_at'])

    def test_historical_entry_term_uses_its_concept_not_related_descriptor(self):
        term = 'Bronchiolitis obliterans organizing pneumonia'
        result, _, _ = self.lookup(term, responses(term, preferred='Cryptogenic Organizing Pneumonia'))
        self.assertEqual(result['concepts'][0]['match_type'], 'entry_term')
        self.assertEqual(result['concepts'][0]['matched_name'], term)
        self.assertIn(term, result['concepts'][0]['aliases'])
        self.assertEqual(result['concepts'][0]['descriptor_ids'], ['D123'])

    def test_cache_is_rechecked_after_acquiring_provider_lease(self):
        result, _, e = self.lookup()
        actual_read = Path.read_text
        misses = []
        def race(path, *args, **kwargs):
            if path.parent == self.cache and len(path.stem) == 64 and not misses:
                misses.append(True)
                raise FileNotFoundError('simulated concurrent cache fill')
            return actual_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', race):
            outcomes, report = e.enrich([{'id':'g1','term':TERM}])
        self.assertEqual(outcomes['g1']['status'],'matched')
        self.assertEqual(report['api_calls'],0)
        self.assertEqual(self.transport.call_count,2)

    def test_ambiguity_lookalikes_abbreviations_and_no_scope_note(self):
        rows = responses(); rows[1]['results']['bindings'] += rdf(identity='M456')['results']['bindings']
        self.assertEqual(self.lookup(rows=rows)[0]['status'], 'ambiguous')
        with tempfile.TemporaryDirectory() as tmp:
            self.cache = Path(tmp)/'cache'
            self.assertEqual(self.lookup('Organising pneumonia', responses())[0]['status'], 'error')
        with tempfile.TemporaryDirectory() as tmp:
            self.cache = Path(tmp)/'cache'
            self.assertEqual(self.lookup('OP', responses('OP'))[0]['status'], 'ambiguous')
        with tempfile.TemporaryDirectory() as tmp:
            self.cache = Path(tmp)/'cache'
            result, _, _ = self.lookup(rows=responses(note=None))
            self.assertEqual(result['status'], 'matched')
            self.assertEqual(result['concepts'][0]['descriptions'], [])

    def test_not_found_is_distinct_from_timeout_malformed_and_rate_limit(self):
        cases = [([], 'not_found'), ([TimeoutError('slow API')], 'unavailable'),
                 ([{'bogus': []}], 'error'),
                 ([HTTPError(terminology.BASE, 429, 'limited', {'Retry-After':'120'}, BytesIO())], 'unavailable')]
        for rows, status in cases:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                self.cache = Path(tmp)/'cache'
                result, report, e = self.lookup(rows=[rows] if rows == [] else rows)
                self.assertEqual(result['status'], status)
                self.assertEqual(result['concepts'], [])
                self.assertEqual(report['api_calls'], 1)
                repeat, audit = e.enrich([{'id':'g1','term':TERM}])
                self.assertEqual(repeat['g1']['status'], status)
                self.assertEqual(audit['api_calls'], 0)
                if status == 'unavailable' and 'HTTP' in result['reason']:
                    self.clock.now += 61
                    other, audit = e.enrich([{'id':'g2','term':'Another term'}])
                    self.assertEqual(other['g2']['status'], 'unavailable')
                    self.assertEqual(audit['api_calls'], 0)

    def test_lookup_budget_duplicate_prevention_and_pacing(self):
        e = self.enricher(max_terms=1)
        result, report = e.enrich([{'id':'g1','term':TERM}, {'id':'g2','term':TERM}, {'id':'g3','term':'Different'}])
        self.assertEqual(report['api_calls'], 2)
        self.assertEqual(result['g2']['status'], 'matched')
        self.assertEqual(result['g3']['status'], 'not_attempted')
        self.assertGreaterEqual(self.clock.now, 1001)
        self.assertTrue(all(call.args[1] <= 3 for call in self.transport.call_args_list))
        with tempfile.TemporaryDirectory() as tmp:
            self.cache = Path(tmp)/'cache'
            result, report, _ = self.lookup(max_requests=1)
            self.assertEqual(report['api_calls'], 1)
            self.assertEqual(result['status'], 'unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            self.cache = Path(tmp)/'cache'
            result, report, _ = self.lookup(action_timeout=.1)
            self.assertEqual(report['api_calls'], 1)
            self.assertEqual(result['status'], 'unavailable')

    def make_research(self, enricher, *, source_text=TEXT, terms=True, strategy='medical'):
        supplied = evidence(source_text)['results'][0]
        if not source_text:
            supplied.pop('content'); supplied['content_kind']='bibliographic_metadata'
        extraction = {'summary': 'A source-grounded fixture finding.', 'results': [{
            'type':'finding', 'text':TEXT, 'qualification':'Fixture source.', 'source_ids':['source-1'], 'related_to':None}],
            'terms':[proposal(TERM, None, passage=source_text)] if terms else []}
        llm = ScriptedLLM([plan(), extraction, {'decision':'unresolved','reason':'Evidence remains incomplete.'}, plan()])
        adapters = {name:FixtureSearch([{'status':'ok','results':[supplied]}] if name=='pubmed' else
            [{'status':'empty','results':[]}]) for name in ['pubmed','europe_pmc','crossref','wikipedia']}
        research = Research(self.root, llm, adapters, terminology=enricher)
        research.initialize('What is organizing pneumonia?', strategy=strategy, context_budget=40000)
        research.step(); research.step()
        return research

    def state(self): return loads((self.root/'research/state.json').read_text())
    def record(self): return loads((self.root/'glossary/g1.json').read_text())

    def test_r3_atomic_enrichment_r1_context_exports_and_rebuild(self):
        research = self.make_research(self.enricher())
        event = research.step()
        self.assertEqual(event['action'], 'R3'); self.assertEqual(event['memory_ids'], ['r1'])
        self.assertEqual(len(research.llm.requests), 2)
        record = self.record(); self.assertEqual(record['term'], TERM)
        self.assertEqual(record['definitions'][0]['text'], NOTE)
        self.assertEqual(record['definitions'][0]['type'], 'scope_note')
        self.assertEqual(record['evidence'][0]['source_id'], 'source-1')
        self.assertEqual(self.state()['glossary']['revision'], 1)
        with research.store.lock():
            glossary.verify(research.store, self.state())
            research.glossary.ensure(self.state(), rebuild=True)
        for _ in range(5): research.step()  # Three other providers, R4, then R1.
        prompt = loads(research.llm.requests[-1])['messages'][0]['content']
        self.assertIn('M123', prompt); self.assertIn('scope_note', prompt)
        self.assertIn('terminology_only', prompt)
        self.assertNotIn('<script>', prompt)
        html = glossary_view.html([record]); md = glossary_view.markdown([record])
        self.assertIn('scope note', html); self.assertIn('M123', md)
        self.assertIn('href="https://id.nlm.nih.gov/mesh/M123"', html)
        self.assertIn('[Source](https://id.nlm.nih.gov/mesh/M123)', md)
        self.assertIn('&lt;script&gt;', html); self.assertNotIn('<script>alert(1)</script>', html)
        self.assertEqual(html, glossary_view.html([record]))
        self.assertIn('Courtesy of the U.S. National Library of Medicine', html)
        indexed = html.split('<script id="glossary-search-data" type="application/json">')[1].split('</script>')[0]
        self.assertNotIn('An inflammatory tissue process', indexed)

    def test_api_failure_does_not_lose_science_and_is_presented(self):
        research = self.make_research(self.enricher([TimeoutError('API down')]))
        event = research.step()
        self.assertEqual(event['status'], 'committed'); self.assertEqual(event['memory_ids'], ['r1'])
        record = self.record()
        self.assertEqual(record['status'], 'candidate'); self.assertEqual(record['definitions'], [])
        self.assertEqual(record['terminology'][-1]['status'], 'unavailable')
        self.assertIn('Lookup unavailable', glossary_view.html([record]))
        self.assertTrue((self.root/'memories/r1.md').exists())

    def test_optional_enricher_exception_preserves_science_and_error_state(self):
        e=self.enricher()
        research=self.make_research(e)
        with patch.object(e,'enrich',side_effect=RuntimeError('optional failure\x00')):
            event=research.step()
        self.assertEqual(event['memory_ids'],['r1'])
        self.assertEqual(event['status'],'committed')
        self.assertEqual(self.record()['terminology'][-1]['status'],'error')
        self.assertEqual(self.transport.call_count,0)

    def test_unsupported_empty_or_metadata_source_is_not_admitted(self):
        for content in ['', 'Unrelated metadata only.']:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)/'memory'; e = self.enricher()
                if not content:
                    with self.assertRaises(ValueError):
                        glossary.validate_proposal(proposal(TERM, None, passage=TERM), evidence(''))
                    self.assertEqual(self.transport.call_count, 0)
                    continue
                research = self.make_research(e, source_text=content)
                event = research.step()
                self.assertEqual(event['memory_ids'], ['r1'])
                self.assertEqual(event['glossary']['accepted'], 0)
                self.assertTrue(event['glossary']['rejected'])
                self.assertEqual(self.transport.call_count, 0)
                self.assertFalse((self.root/'glossary/g1.json').exists())

    def test_crash_recovery_preserves_final_commitment_without_network_or_llm(self):
        for point in ['prepared', 'before_commit']:
            with self.subTest(point=point), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)/'memory'; self.cache=Path(tmp)/'cache'
                research = self.make_research(self.enricher())
                def crash(stage):
                    if stage == point: raise RuntimeError('simulated crash')
                with self.assertRaises(RuntimeError): research.step(fault=crash)
                status = research.store.recovery_status()
                with self.assertRaises(RecoveryRequired):
                    with research.store.lock(): research.store.read()
                calls = self.transport.call_count
                research.store.repair(status['operations'][0]['id'], apply=True)
                self.assertEqual(self.transport.call_count, calls)
                self.assertEqual(self.state()['glossary']['revision'], 1)
                self.assertEqual(self.record()['id'], 'g1')
                self.assertEqual(len(self.record()['definitions']), 1)
                self.assertTrue((self.root/'memories/r1.md').exists())
                with research.store.lock(): glossary.verify(research.store, self.state())
                restarted = Research(self.root, ScriptedLLM([]), {}, terminology=self.enricher([]))
                restarted._recover_outcomes()
                self.assertEqual(read_records(self.root)[-1]['outcome']['action_committed'], 'R3')

    def test_existing_candidate_enriched_no_duplicate_ids_or_definitions(self):
        research = self.make_research(self.enricher([TimeoutError('offline')]))
        research.step()
        self.clock.now += 61  # A failed lookup's cooldown is not bypassed.
        good = self.enricher()
        with research.store.lock():
            token, docs, eqs, ledger = research.store.read(); state = self.state()
            files, audit = research.glossary.proposals(state, [], evidence(TEXT), 'q1', enricher=good)
            research.store.publish(docs, eqs, ledger, token, files={**files, 'research/state.json':dumps(state)})
            token, docs, eqs, ledger = research.store.read(); state=self.state()
            files, audit = research.glossary.proposals(state, [proposal(TERM, None, passage=TEXT)], evidence(TEXT), 'q1', enricher=good)
            research.store.publish(docs, eqs, ledger, token, files={**files, 'research/state.json':dumps(state)})
        self.assertEqual(self.state()['glossary']['next_id'], 2)
        self.assertEqual(len(self.record()['definitions']), 1)
        self.assertEqual(self.transport.call_count, 2)

    def test_paper_definition_preserved_with_authority_and_validation_not_weakened(self):
        research=self.make_research(self.enricher())
        with research.store.lock():
            token, docs, eqs, ledger=research.store.read(); state=self.state()
            files, audit=research.glossary.proposals(state, [proposal(TERM, TEXT, passage=TEXT)], evidence(TEXT), 'q1', enricher=research.terminology)
            research.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(state)})
        record=self.record();self.assertEqual(len(record['definitions']),2)
        self.assertEqual(record['definitions'][0]['text'],TEXT)
        self.assertEqual(record['status'],'multiple_definitions')
        invalid=deepcopy(record);invalid['definitions'][0]['text']='Invented definition.'
        with self.assertRaises(ValueError):glossary.validate_record(invalid)
        invalid=deepcopy(record);invalid['definitions'][1]['authority']['matched_name']='Another condition'
        with self.assertRaises(ValueError):glossary.validate_record(invalid)

    def test_index_schema_upgrade_and_context_byte_budget(self):
        import sqlite3
        research=self.make_research(self.enricher());research.step()
        with research.store.lock():
            state=self.state(); research.glossary.ensure(state)
            with closing(sqlite3.connect(research.glossary.path)) as db, db:
                db.execute("UPDATE metadata SET value='1' WHERE key='schema'")
                db.execute('DROP TABLE lookups')
            research.glossary.ensure(state)
            with closing(sqlite3.connect(research.glossary.path)) as db:
                self.assertEqual(db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0],'2')
            _,memories,_,_=research.store.read();files=research.store._files()
            context=r1.retrieval_context(state,memories,files,'q1')
            state['glossary']['token_budget']=450
            bounded=research.glossary.retrieve(state,context,'q1')
            self.assertLessEqual(len(dumps(bounded).encode()),450)
            glossary.verify(research.store,self.state())

    def test_candidate_backlog_does_not_starve_after_negative_matches(self):
        research=self.make_research(self.enricher([[]],max_terms=1));research.step()
        passage='Other medical term and Third medical term are recorded here.'
        e=self.enricher([[]],max_terms=1)
        with research.store.lock():
            token,docs,eqs,ledger=research.store.read();state=self.state()
            values=[proposal(term,None,passage=passage) for term in ['Other medical term','Third medical term']]
            files,_=research.glossary.proposals(state,values,evidence(passage),'q1',enricher=e)
            research.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(state)})
            pending=loads((self.root/'glossary/g3.json').read_text())
            self.assertEqual(pending['terminology'][-1]['status'],'not_attempted')
            token,docs,eqs,ledger=research.store.read();state=self.state()
            e=self.enricher([[]],max_terms=1)
            files,audit=research.glossary.proposals(state,[],evidence(passage),'q1',enricher=e)
            self.assertEqual(audit['enrichment']['api_calls'],1)
            self.assertEqual(audit['enrichment']['outcomes'][0]['id'],'g3')
            research.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(state)})

    def test_external_invalid_identity_does_not_admit_a_definition(self):
        rows=responses();rows[1]['results']['bindings'][0]['concept']['value']='https://attacker.example/M123'
        research=self.make_research(self.enricher(rows))
        event=research.step()
        self.assertEqual(event['memory_ids'],['r1'])
        self.assertEqual(self.record()['definitions'],[])
        self.assertEqual(self.record()['terminology'][-1]['status'],'error')

    def test_verified_authority_alias_reuses_existing_id_and_original_spelling(self):
        preferred='Established Preferred Pneumonia'
        research=self.make_research(self.enricher(responses(preferred=preferred)));research.step()
        passage=preferred+' occurs in this additional source.'
        with research.store.lock():
            token,docs,eqs,ledger=research.store.read();state=self.state()
            files,audit=research.glossary.proposals(state,[proposal(preferred,None,passage=passage)],evidence(passage),'q1')
            research.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(state)})
        self.assertEqual(self.record()['term'],TERM)
        self.assertEqual(self.state()['glossary']['next_id'],2)
        self.assertEqual(len(self.record()['evidence']),2)
        self.assertEqual(audit['merged'],1)

    def test_export_distinguishes_lookup_states_and_cites_without_script_injection(self):
        from test_glossary import record
        for status,label in [('not_found','No authoritative match'),('ambiguous','Ambiguous match'),
            ('unavailable','Lookup unavailable'),('error','Lookup error'),('not_attempted','Lookup not yet attempted')]:
            candidate=record(1,TERM);candidate['definitions']=[];candidate['status']='candidate'
            candidate['terminology']=[{'provider':'mesh','term':TERM,'status':status,
                'reason':'Untrusted <script>text</script>.','retrieved_at':'2026-10-31T00:00:00+00:00','concepts':[]}]
            glossary.validate_record(candidate)
            self.assertIn(label,glossary_view.markdown([candidate]))
            self.assertIn(label,glossary_view.html([candidate]))
            self.assertNotIn('<script>text</script>',glossary_view.html([candidate]))

    def test_nonmedical_strategy_does_not_contact_vocabulary(self):
        e=self.enricher()
        state={'strategies':[{'id':'engineering'}],'strategy_index':0}
        self.assertFalse(e.enabled(state))
        research=Research(self.root,ScriptedLLM([plan(),{'summary':'','results':[],
            'terms':[proposal(TERM,None,passage=TEXT)]}]),{'fixture':FixtureSearch([{'status':'ok','results':evidence(TEXT)['results']}])},terminology=e)
        research.initialize('Engineering terminology?', ['fixture'], context_budget=40000)
        research.step();research.step();research.step()
        self.assertEqual(self.transport.call_count,0)
        self.assertNotIn('terminology',self.record())


if __name__ == '__main__': unittest.main()
