"""Derived report publication, safe reading/rendering and canonical preservation."""
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mira.decisions import ScriptedLLM
from mira.experiments import Experiments,file_hashes
from mira.format import dumps,loads,digest
from mira.knowledge_inspection import KnowledgeInspector
from mira.research import Research
from mira.state_of_research import capture,project,Generator,publish,load,compose,ARTIFACTS
from mira.sor_contracts import SECTIONS,scientific_checks
from mira.sor_view import markdown,html
import sor_fixtures as fixtures
from test_state_of_research import draft,review,revision
from test_gardener import seed


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name);self.catalog=Experiments(self.home/'memory');self.root=self.catalog.create('sor-fixture')
        self.r=Research(self.root,ScriptedLLM([]),{});self.r.initialize('Controlled research question?',['fixture'],context_budget=30000)
        seed(self.r,own=2,child=0,leaf=0)
        self.snapshot,self.evidence=capture(self.catalog)
        self.model=ScriptedLLM([]);self.model.context_window=30000
        self.model.count_tokens=lambda wire:{'prompt_tokens':100,'context_window':30000}
        self.g=Generator(self.model,self.home/'log')
        self.audit=self.make_audit()

    def make_audit(self):
        sections=[s for s,_ in SECTIONS]
        d=draft(self.evidence,sections=sections,ids=['r1#f1'],kind='source_finding')
        paper={'schema':'mira.sor.paper/1','id':self.g.identity,'title':'State of controlled research',
            'generated_at':'2026-11-03T00:00:00+00:00','source_revision':self.evidence['revision'],
            'source_snapshot_sha256':digest(dumps(self.evidence)),'experiment':'sor-fixture','model_identity':{'served_model':'synthetic-fixture'},
            'adversarial_review':True,'sections':d['sections'],'scientifically_verified':False,
            'coverage_ledger':{i:{'id':i,'version':u['version'],'batch':'fixture','considered':True,'initially_cited':i=='r1#f1','finally_cited':i=='r1#f1'} for i,u in self.evidence['units'].items()}}
        checks=scientific_checks(d,self.evidence)
        r=review(d)
        manifest={**self.g.manifest,'status':'completed','validation':checks,'source_revision':self.evidence['revision'],
                  'source_snapshot_sha256':digest(dumps(self.evidence)),'experiment':'sor-fixture','model_identity':paper['model_identity']}
        trial={'label':'fixture','unit_ids':list(self.evidence['units']),'draft':d,'valid_review':r,'review':r,'rejected_objections':[],
            'revision':revision(d,r),'initial_validation':checks,'final_validation':checks}
        paper['sections'],initial,withheld=compose([trial],self.evidence)
        checks=scientific_checks({'schema':'mira.sor.draft/1','title':paper['title'],'sections':paper['sections']},self.evidence)
        manifest['validation']=checks
        return {'schema':'mira.sor.audit/1','paper':paper,'evidence':self.evidence,'trials':[trial],
            'initial_sections':initial,'withheld_paragraphs':withheld,'manifest':manifest,'validation':checks}

    def canonical(self):return {p:h for p,h in file_hashes(self.root).items() if p not in ARTIFACTS}

    def test_three_outputs_are_derived_and_do_not_change_canonical_snapshot(self):
        before=self.canonical();token=self.r.store.read()[0]
        result=publish(self.catalog,self.audit)
        self.assertEqual(self.canonical(),before);self.assertEqual(self.r.store.read()[0],token)
        self.assertEqual(result['units_considered'],2)
        self.assertTrue(all((self.root/p).is_file() for p in ARTIFACTS))
        self.assertEqual(KnowledgeInspector(self.catalog).snapshot('sor-fixture')['revision'],token)

    def test_invalid_candidate_and_failed_render_leave_previous_triple_intact(self):
        publish(self.catalog,self.audit);previous={p:(self.root/p).read_bytes() for p in ARTIFACTS}
        invalid=deepcopy(self.audit);invalid['paper']['sections'][0]['paragraphs'][0]['unit_ids']=['r99#f1']
        with self.assertRaises(ValueError):publish(self.catalog,invalid)
        with patch('mira.sor_view.html',side_effect=RuntimeError('render failed')),self.assertRaises(RuntimeError):publish(self.catalog,self.audit)
        self.assertEqual(previous,{p:(self.root/p).read_bytes() for p in ARTIFACTS})

    def test_atomic_replace_failure_rolls_back_all_three_outputs(self):
        publish(self.catalog,self.audit);previous={p:(self.root/p).read_bytes() for p in ARTIFACTS}
        from mira import glossary_view
        original=glossary_view.os.replace
        def fail_audit(source,dest):
            if str(dest).endswith('state_of_research.audit.json'):raise OSError('simulated final replace failure')
            return original(source,dest)
        with patch('mira.glossary_view.os.replace',side_effect=fail_audit),self.assertRaises(OSError):publish(self.catalog,self.audit)
        self.assertEqual(previous,{p:(self.root/p).read_bytes() for p in ARTIFACTS})

    def test_view_never_calls_model_and_freshness_is_explicit(self):
        publish(self.catalog,self.audit);before=self.canonical()
        with patch('mira.clients.HTTPModel.complete',side_effect=AssertionError('viewing cannot infer')):
            result=load(self.catalog);self.assertFalse(result['stale'])
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read()
            self.r.store.publish(docs,eqs,ledger,token,files={'events/read-only-test.json':dumps({'recorded':True})})
        result=load(self.catalog);self.assertTrue(result['stale'])
        output=html(result['audit'],stale=result['stale']);self.assertIn('Research has changed since this report was generated.',output)
        self.assertEqual(result['audit']['paper']['source_revision'],self.evidence['revision'])

    def test_old_snapshot_publication_never_silently_changes_its_revision(self):
        with self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read()
            self.r.store.publish(docs,eqs,ledger,token,files={'events/intervening.json':dumps({'recorded':True})})
        publish(self.catalog,self.audit);self.assertTrue(load(self.catalog)['stale'])

    def test_full_sections_equations_glossary_and_knowledge_citations(self):
        e=fixtures.quantitative();a=deepcopy(self.audit);a['evidence']=e
        a['paper']['coverage_ledger']={i:{'id':i,'considered':True,'finally_cited':True} for i in e['units']}
        for s in a['paper']['sections']:
            for p in s['paragraphs']:p['unit_ids']=['r1#f1']
        a['evidence']['glossary']={'g1':{'id':'g1','term':'Synthetic term','definition':{'origin':'llm_generated','text':'A provisional fixture meaning.'},'enrichment':{}}}
        output=html(a);md=markdown(a)
        for _,title in SECTIONS:self.assertIn(title,output);self.assertIn(title,md)
        self.assertIn('V = (pi / 6) * D^3',output);self.assertIn('Consistent length units',md)
        self.assertIn('Provisional, model-generated; not independently verified',output)
        self.assertIn('href="/glossary#g1"',output);self.assertIn('unit=r1%23f1',output)

    def test_untrusted_scientific_content_cannot_execute_html_or_javascript(self):
        a=deepcopy(self.audit);a['paper']['title']='</title><script>alert(1)</script>'
        a['paper']['sections'][0]['paragraphs'][0]['text']='<img src=x onerror=alert(2)> & unsafe'
        output=html(a)
        class Parser(HTMLParser):
            def __init__(self):super().__init__();self.tags=[]
            def handle_starttag(self,tag,attrs):self.tags.append((tag,dict(attrs)))
        p=Parser();p.feed(output)
        self.assertFalse(any(t=='img' for t,_ in p.tags));self.assertEqual(sum(t=='script' for t,_ in p.tags),1)
        self.assertFalse(any(k.startswith('on') for _,attrs in p.tags for k in attrs))
        self.assertIn('&lt;img',output);self.assertNotIn('<script>alert(1)</script>',markdown(a))

    @unittest.skipUnless(shutil.which('node'),'Node executes the production browser search asset')
    def test_production_search_navigation_normalization_and_safe_results(self):
        asset=Path('src/mira/sor_assets/search.js')
        run=subprocess.run(['node',str(Path(__file__).with_name('sor_search_test.js')),str(asset)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_corrupt_evidence_hash_is_not_presented_as_valid_report(self):
        publish(self.catalog,self.audit);path=self.root/ARTIFACTS[2]
        a=loads(path.read_text());a['evidence']['inventory']['total_units']=999;path.write_text(dumps(a))
        with self.assertRaisesRegex(ValueError,'hash mismatch'):load(self.catalog)

    def test_saved_verdict_cannot_hide_invalid_content_or_coverage(self):
        for change in ('citation','count','ledger','snapshot','review'):
            with self.subTest(change=change):
                a=deepcopy(self.audit)
                if change=='citation':a['paper']['sections'][0]['paragraphs'][0]['unit_ids']=['r99#f1']
                if change=='count':a['paper']['sections'][0]['paragraphs'][0]['text']='There are 999 research memories.'
                if change=='ledger':a['paper']['coverage_ledger']['r1#f1']['finally_cited']=False
                if change=='snapshot':a['paper']['source_revision']='another revision'
                if change=='review':a['trials']=[]
                with self.assertRaises(ValueError):publish(self.catalog,a)

    def test_read_only_cli_and_http_report_routes_never_infer(self):
        from argparse import Namespace
        from types import SimpleNamespace
        from mira.sor_cli import execute
        from mira.inspection import Inspector
        from test_viewer import ViewerTests
        publish(self.catalog,self.audit);before=self.canonical()
        args=Namespace(root=None,memory_dir=str(self.root),experiment=None,command='state-of-research-view',format='html',open=False)
        inspector=SimpleNamespace(inspector=Inspector(self.root),reviews=None)
        with patch('mira.clients.HTTPModel.complete',side_effect=AssertionError('viewing cannot infer')):
            self.assertIn('State of controlled research',execute(args))
            for route in ('/state-of-research','/state-of-research?experiment=sor-fixture','/api/experiments/sor-fixture/state-of-research'):
                status,body,headers=ViewerTests.request(inspector,'GET',route)
                self.assertEqual(status,200);self.assertIn(b'State of controlled research',body)
            self.assertEqual(ViewerTests.request(inspector,'GET','/state-of-research?experiment=sor-fixture&experiment=sor-fixture')[0],400)
        self.assertEqual(self.canonical(),before)

    def test_report_view_and_publication_refuse_active_writer_and_pending_recovery(self):
        from types import SimpleNamespace
        from mira.inspection import Inspector
        from test_viewer import ViewerTests
        publish(self.catalog,self.audit)
        inspector=SimpleNamespace(inspector=Inspector(self.root),reviews=None)
        with self.r.store.lock():
            self.assertEqual(ViewerTests.request(inspector,'GET','/state-of-research')[0],503)
            with self.assertRaises(BlockingIOError):publish(self.catalog,self.audit)
        def fault(point):
            if point=='prepared':raise RuntimeError('simulated interrupted journal commit')
        with self.assertRaises(RuntimeError),self.r.store.lock():
            token,docs,eqs,ledger=self.r.store.read()
            self.r.store.publish(docs,eqs,ledger,token,files={'events/fixture.json':dumps({'fixture':True})},fault=fault)
        before=file_hashes(self.root)
        self.assertEqual(ViewerTests.request(inspector,'GET','/state-of-research')[0],503)
        with self.assertRaises(RuntimeError):publish(self.catalog,self.audit)
        self.assertEqual(before,file_hashes(self.root))

    def test_explicit_source_reference_has_a_real_bibliography_anchor(self):
        a=deepcopy(self.audit)
        a['evidence']['sources']['fixture:extra']={'id':'fixture:extra','title':'Additional recorded source','url':'https://example.invalid/extra'}
        a['paper']['sections'][0]['paragraphs'][0]['text']='Recorded attribution [SRC:fixture:extra].'
        output=html(a)
        index=list(a['evidence']['sources']).index('fixture:extra')
        self.assertIn('href="#source-'+str(index)+'"',output)
        self.assertIn('id="source-'+str(index)+'"',output)
        self.assertIn('Additional recorded source',markdown(a))
        self.assertEqual(output,html(a));self.assertEqual(markdown(a),markdown(a))

    def test_explicit_new_experiment_removes_only_derived_report_with_old_corpus(self):
        publish(self.catalog,self.audit);private=self.root/'questions';private.mkdir();(private/'keep.md').write_text('Private input')
        self.catalog.create('replacement',reset=True)
        self.assertTrue((private/'keep.md').exists());self.assertFalse(any((self.root/p).exists() for p in ARTIFACTS))

    def test_symlink_report_destination_cannot_modify_an_outside_file(self):
        outside=self.home/'outside';outside.write_text('Keep this')
        (self.root/ARTIFACTS[0]).symlink_to(outside)
        with self.assertRaises(ValueError):publish(self.catalog,self.audit)
        self.assertEqual(outside.read_text(),'Keep this')
