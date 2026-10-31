"""Complete canonical exports, untrusted rendering and offline term navigation."""
from copy import deepcopy
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mira import glossary, glossary_view
from mira.decisions import ScriptedLLM
from mira.experiments import Experiments, file_hashes
from mira.format import digest, dumps, loads
from mira.live import RecoveryRequired
from mira.research import Research
from test_glossary import record


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements=[];self.text=[];self.feed(html)
    def handle_starttag(self, tag, attributes):self.elements.append((tag,dict(attributes)))
    def handle_data(self, data):self.text.append(data)


class GlossaryViewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)/'memory';self.catalog=Experiments(self.home)
        root=self.catalog.create('glossary-fixture')
        self.research=Research(root,ScriptedLLM([]),{})
        self.research.initialize('Synthetic glossary fixture?',['fixture'],context_budget=30000)
        self.directory=self.research.glossary;self.store=self.research.store
        self.md=self.home/'research/glossary.md';self.html=self.home/'research/glossary.html'

    def state(self):return loads((self.home/'research/state.json').read_text())

    def seed(self, records):
        with self.store.lock():
            token,docs,eqs,ledger=self.store.read();state=self.state()
            changed={'glossary/'+r['id']+'.json':dumps(r) for r in records}
            state['glossary'].update(next_id=len(records)+1,revision=1,
                commitment=glossary.commitment(state['glossary']['commitment'],changed))
            self.store.publish(docs,eqs,ledger,token,files={**changed,'research/state.json':dumps(state)})

    def export(self):
        with self.store.lock():return self.directory.export(self.state())

    def canonical(self):
        return {p:h for p,h in file_hashes(self.home).items() if p not in
            {'glossary.sqlite3','glossary.sqlite3-wal','glossary.sqlite3-shm','research/glossary.md','research/glossary.html'}}

    def test_markdown_compatibility_and_unicode_alphabetical_order(self):
        first=record(1,'Zeta');second=record(2,'alpha')
        second['aliases']=['First alias'];second['relationships']=[{'type':'RELATED_TO','target':'g1','evidence':second['evidence'][0]}]
        self.seed([first,second]);self.export()
        expected='''# Research glossary

Source-derived terminology; definitions are not independently verified.

## alpha (g2)

Status: source_defined

Aliases: First alias

- alpha is a synthetic benchmark term. — Synthetic.

> alpha is a synthetic benchmark term.

Source: synthetic; evidence: research/results/synthetic.json; node: q1

Qualification: Synthetic fixture.

RELATED_TO: g1

## Zeta (g1)

Status: source_defined

- Zeta is a synthetic benchmark term. — Synthetic.

> Zeta is a synthetic benchmark term.

Source: synthetic; evidence: research/results/synthetic.json; node: q1

Qualification: Synthetic fixture.
'''
        self.assertEqual(self.md.read_text(),expected)
        html=self.html.read_text();self.assertLess(html.index('id="g2"'),html.index('id="g1"'))
        self.assertIn('href="#g1">Zeta (g1)</a>',html)
        self.assertIn('href="#g2-e1">Evidence 1</a>',html)

    def test_all_canonical_definitions_aliases_evidence_qualifications_and_relationships(self):
        first=record(1,'Alpha');first['aliases']=[f'Alias {i}' for i in range(12)]
        first['evidence']=[];first['definitions']=[]
        for i in range(3):
            text='Alpha is '+str(i)+' '+('a complete synthetic definition with qualification ' * 14)
            support={'source_id':'source-'+str(i),'passage':text+' PASSAGE-END-'+str(i),
                'evidence_ref':f'research/results/source-{i}.json','node_id':'q1','qualification':'Evidence qualification '+str(i)}
            first['evidence'].append(support)
            first['definitions'].append({'text':text,'qualification':'Definition qualification '+str(i),'evidence':support})
        first['status']='multiple_definitions'
        first['relationships']=[{'type':'BROADER_THAN','target':'g2','evidence':first['evidence'][2]}]
        self.seed([first,record(2,'Beta')]);original=self.canonical()
        result=self.export();html=self.html.read_text();md=self.md.read_text()
        self.assertEqual(result,{'path':str(self.md),'html_path':str(self.html),'entries':2})
        self.assertEqual(self.canonical(),original)
        text=''.join(Document(html).text)
        for value in [*first['aliases'], *[d['text'] for d in first['definitions']],
            *[d['qualification'] for d in first['definitions']], *[e['passage'] for e in first['evidence']],
            *[e['qualification'] for e in first['evidence']], *[e['source_id'] for e in first['evidence']],
            *[e['evidence_ref'] for e in first['evidence']]]:
            self.assertIn(value,text);self.assertIn(value,md)
        self.assertIn('BROADER_THAN: <a href="#g2">Beta (g2)</a> · <a href="#g1-e3">Evidence 3</a>',html)
        with sqlite3.connect(self.directory.path) as db:
            self.assertLess(len(db.execute('SELECT definition FROM terms WHERE id="g1"').fetchone()[0]),len(first['definitions'][2]['text']))

    def test_empty_glossary_and_export_alias_use_the_same_implementation(self):
        original=self.canonical()
        command=[sys.executable,'-m','mira','--memory-dir',str(self.home)]
        a=loads(subprocess.check_output([*command,'glossary-export'],text=True))
        contents=(self.md.read_bytes(),self.html.read_bytes())
        b=loads(subprocess.check_output([*command,'glossary-view'],text=True))
        self.assertEqual(a,b);self.assertEqual(a['entries'],0)
        self.assertEqual(contents,(self.md.read_bytes(),self.html.read_bytes()))
        self.assertIn('No glossary entries have been recorded.',self.html.read_text())
        self.assertEqual(self.canonical(),original)
        with self.store.lock():self.store.read()

    def test_html_and_script_injection_are_literal_text_and_search_data_contains_names_only(self):
        term='</script><img src=x onerror=alert(1)>'
        value=record(1,term);value['aliases']=['" autofocus onfocus="alert(2)', '<svg onload=alert(3)>']
        value['evidence'][0].update(evidence_ref='javascript:alert(4) <iframe src=x>',node_id='q1 <script>alert(5)</script>')
        value['definitions'][0]['qualification']='</style><script>alert(6)</script>'
        self.seed([value]);self.export();html=self.html.read_text();parsed=Document(html)
        self.assertFalse(any(tag in {'img','svg','iframe'} for tag,_ in parsed.elements))
        self.assertEqual(len([tag for tag,_ in parsed.elements if tag=='script']),2)
        for tag,attrs in parsed.elements:
            self.assertFalse(any(k.startswith('on') for k in attrs))
            self.assertNotIn('src',attrs)
            if 'href' in attrs:self.assertTrue(attrs['href'].startswith('#'))
        data=re.search(r'<script id="glossary-search-data" type="application/json">(.*?)</script>',html,re.S)[1]
        self.assertNotIn('<',data)
        self.assertEqual(json.loads(data),[{'id':'g1','term':term,'aliases':value['aliases']}])
        self.assertNotIn('<script>',self.md.read_text());self.assertNotIn('<iframe',self.md.read_text())
        self.assertIn(term,''.join(parsed.text))

    def test_standalone_inline_assets_csp_responsive_and_sticky_search(self):
        self.seed([record(1,'Alpha')]);self.export();html=self.html.read_text();document=Document(html)
        self.assertTrue(html.startswith('<!doctype html>'))
        attrs=next(attrs for tag,attrs in document.elements if tag=='input')
        self.assertEqual(attrs['aria-controls'],'glossary-results')
        self.assertIn('Search glossary terms',html)
        self.assertIn('position: sticky',html);self.assertIn('@media (max-width:',html)
        self.assertIn('name="viewport"',html)
        policy=next(attrs['content'] for tag,attrs in document.elements if attrs.get('http-equiv')=='Content-Security-Policy')
        from base64 import b64encode
        for pattern in ('<style>(.*?)</style>', '<script>(.*?)</script>'):
            content=re.search(pattern,html,re.S)[1]
            self.assertIn('sha256-'+b64encode(sha256(content.encode()).digest()).decode(),policy)
        script=re.search('<script>(.*?)</script>',html,re.S)[1]
        for unsafe in ('innerHTML','eval(', 'fetch(', 'XMLHttpRequest','import(', 'http://', 'https://'):
            self.assertNotIn(unsafe,script)
        self.assertNotIn('@import',html)
        self.assertFalse(any(tag in {'link','img','iframe','form','font'} for tag,_ in document.elements))

    def test_index_rebuild_ordering_and_export_determinism_without_canonical_changes(self):
        records=[record(1,'zeta'),record(2,'Straße'),record(3,'STRASSE'),record(4,'Äther')]
        records[2]['key'] += '|source-scope'  # Distinct scoped entries with equal casefold ordering.
        self.seed(records);before=self.canonical();self.export();expected=(self.md.read_bytes(),self.html.read_bytes())
        self.assertLess(self.md.read_text().index('(g2)'),self.md.read_text().index('(g3)'))
        self.directory.path.unlink();self.export()
        self.assertEqual(expected,(self.md.read_bytes(),self.html.read_bytes()))
        self.directory.path.write_bytes(b'corrupt SQLite');self.export()
        self.assertEqual(expected,(self.md.read_bytes(),self.html.read_bytes()))
        # Even a cache with a matching commitment cannot change enumeration/order.
        with sqlite3.connect(self.directory.path) as db:
            db.execute('DELETE FROM terms WHERE id="g4"')
            db.execute('UPDATE terms SET term="aaaa",sha=? WHERE id="g1"',('0'*64,))
        self.export();self.assertEqual(expected,(self.md.read_bytes(),self.html.read_bytes()))
        with sqlite3.connect(self.directory.path) as db:
            db.execute('UPDATE terms SET term="wrong cached ordering" WHERE id="g1"')
        self.export();self.assertEqual(expected,(self.md.read_bytes(),self.html.read_bytes()))
        self.assertEqual(before,self.canonical())
        self.assertFalse(self.store.recovery_status()['blocked'])

    def test_changed_canonical_record_or_incomplete_journal_blocks_both_exports(self):
        self.seed([record(1,'Alpha')]);self.export();before=(self.md.read_bytes(),self.html.read_bytes())
        path=self.home/'glossary/g1.json';original=path.read_bytes();path.write_bytes(original+b' ')
        with self.assertRaisesRegex(ValueError,'committed hash'):self.export()
        self.assertEqual(before,(self.md.read_bytes(),self.html.read_bytes()))
        path.write_bytes(original)
        def fault(point):
            if point=='prepared':raise RuntimeError('interrupted action')
        with self.assertRaises(RuntimeError),self.store.lock():
            token,docs,eqs,ledger=self.store.read()
            self.store.publish(docs,eqs,ledger,token,files={'events/export-fixture.json':dumps({'fixture':True})},fault=fault)
        with self.assertRaises(RecoveryRequired):self.export()
        self.assertEqual(before,(self.md.read_bytes(),self.html.read_bytes()))

    def test_staging_failure_and_symlink_targets_preserve_outputs_and_external_files(self):
        self.seed([record(1,'Alpha')]);self.export();before=(self.md.read_bytes(),self.html.read_bytes())
        original=glossary_view.durable_write
        def fail_html(path,text):
            if '.html.tmp-' in path.name:raise OSError('simulated staging failure')
            original(path,text)
        with patch('mira.glossary_view.durable_write',side_effect=fail_html),self.assertRaises(OSError):self.export()
        self.assertEqual(before,(self.md.read_bytes(),self.html.read_bytes()))
        self.assertEqual(list((self.home/'research').glob('*.tmp-*')),[])
        outside=Path(self.temp.name)/'outside';outside.write_text('Keep outside data')
        self.html.unlink();self.html.symlink_to(outside)
        with self.assertRaises(ValueError):self.export()
        self.assertEqual(outside.read_text(),'Keep outside data')
        self.assertEqual(self.md.read_bytes(),before[0])

    @unittest.skipUnless(shutil.which('node'),'Node is required to execute exported JavaScript tests')
    def test_exported_script_search_ranking_unicode_navigation_and_highlight(self):
        names=['Alpha','Alpha beta','Betalpha','Café','Straße protein','ΟΣ','Spacing term','T-cell response',
               'Many aliases','</script><img src=x onerror=alert(1)>']
        records=[record(i,name) for i,name in enumerate(names,1)]
        records[0]['aliases']=['First alias'];records[6]['aliases']=['multiple words']
        records[8]['aliases']=[f'alias-{i}' for i in range(8)]+['ninth-alias']
        records[0]['evidence'][0]['passage']+=' passage-only'
        records[0]['evidence'][0]['source_id']='citation-only'
        records[0]['definitions'][0]['qualification']='only-in-definition'
        self.seed(records);self.export()
        run=subprocess.run(['node',str(Path(__file__).with_name('glossary_search_test.js')),str(self.html)],text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertIn('keyboard navigation, highlighting',run.stdout)

    def test_new_experiment_reset_removes_both_derived_views(self):
        self.seed([record(1,'Alpha')]);self.export()
        self.catalog.create('replacement',reset=True)
        self.assertFalse(self.md.exists());self.assertFalse(self.html.exists())

    def test_publication_error_restores_the_previous_complete_export_pair(self):
        self.seed([record(1,'Alpha')]);self.export();before=(self.md.read_bytes(),self.html.read_bytes())
        original=glossary_view.os.replace
        def fail_second(source,target):
            if Path(target)==self.html:raise OSError('simulated replace failure')
            return original(source,target)
        with patch('mira.glossary_view.os.replace',side_effect=fail_second),self.assertRaises(OSError):
            glossary_view.publish(self.store,{'research/glossary.md':'changed Markdown','research/glossary.html':'changed HTML'})
        self.assertEqual(before,(self.md.read_bytes(),self.html.read_bytes()))
        self.assertEqual(list((self.home/'research').glob('*.tmp-*')),[])
