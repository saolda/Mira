"""Medical catalogue, provider metadata, scheduling and publication identity."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from mira import providers, sources, strategies
from mira.decisions import ScriptedLLM
from mira.format import loads
from mira.interactions import read_records
from mira.providers import PubMedSearch, EuropePMCSearch, OpenAlexSearch
from mira.research import Research


QUESTION = ('What conditions cause rapidly enlarging spiculated pulmonary masses in older adults, '
            'and which clinical, imaging, microbiological and pathological findings distinguish '
            'infectious, inflammatory and malignant causes?')
MEDICAL = ['pubmed', 'europe_pmc', 'openalex', 'crossref', 'wikipedia']
DESCRIPTION = ('Biomedical and clinical research, including diseases, diagnosis, treatment, '
               'pathology, epidemiology and medical evidence.')


def pubmed_xml(date='<Year>2024</Year><Month>Feb</Month><Day>12</Day>', *, identifiers=True):
    ids = ('<ArticleId IdType="doi">10.1234/medical</ArticleId>'
           '<ArticleId IdType="pmc">PMC1234</ArticleId>') if identifiers else ''
    return (f'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1234</PMID><Article>'
            '<ArticleTitle>Controlled study of pulmonary mass diagnostic methods</ArticleTitle>'
            '<Abstract><AbstractText Label="RESULTS">Authors report a diagnostic comparison; '
            'independent validation remains unavailable.</AbstractText></Abstract>'
            '<AuthorList><Author><ForeName>Jane</ForeName><LastName>Smith</LastName></Author></AuthorList>'
            f'<Journal><JournalIssue><PubDate>\n {date}\n </PubDate></JournalIssue></Journal>'
            '</Article></MedlineCitation><PubmedData><ArticleIdList>'
            f'{ids}</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>').encode()


def europe_result(*, identifiers=True):
    item = {'id':'1234', 'source':'MED', 'title':'Controlled study of pulmonary mass diagnostic methods',
            'abstractText':'Authors report a diagnostic comparison; independent validation remains unavailable.',
            'authorList':{'author':[{'fullName':'Smith J'}]}, 'firstPublicationDate':'2024-02-12'}
    # MED's source-qualified ID is supplied even if the redundant pmid is omitted.
    if identifiers: item.update(doi='https://doi.org/10.1234/MEDICAL', pmcid='PMC1234')
    return {'resultList':{'result':[item]}}


def wire_adapters(data):
    adapters = providers.adapters()
    calls = {name:[] for name in MEDICAL}
    for name in MEDICAL:
        responses = iter(data[name])
        def open_(request, timeout, *, name=name, responses=responses):
            calls[name].append(request)
            value = next(responses)
            return BytesIO(value if isinstance(value,bytes) else json.dumps(value).encode())
        adapters[name].opener = open_
    return adapters, calls


class MedicalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'run'
        providers._LAST.clear()

    def state(self): return loads((self.root/'research/state.json').read_text())

    def test_medical_registry_description_and_registered_provider_order(self):
        medical = strategies.select(strategies.registry(), 'medical')
        self.assertEqual(medical, {'id':'medical', 'name':'Medical', 'description':DESCRIPTION, 'databases':MEDICAL})
        adapters = providers.adapters()
        expected = [PubMedSearch, EuropePMCSearch, OpenAlexSearch, providers.CrossrefSearch, providers.WikipediaSearch]
        self.assertEqual([type(adapters[p]) for p in medical['databases']], expected)
        self.assertTrue(set(MEDICAL) <= set(strategies.PROVIDERS))
        self.assertTrue(all(callable(adapters[p].search) for p in MEDICAL))
        self.assertNotIn('arxiv', medical['databases']); self.assertNotIn('eric', medical['databases'])

    def test_existing_strategy_sequences_and_descriptions_are_preserved(self):
        expected = {
            'general':('Broad orientation and multidisciplinary scholarly research.', ['wikipedia','openalex','crossref','arxiv']),
            'engineering':('Engineering, computing, mathematics and technical methods.', ['arxiv','crossref','openalex','wikipedia']),
            'humanities':('History, philosophy, arts and cultural scholarship.', ['crossref','openalex','wikipedia']),
            'biomedical':('Clinical, biomedical and life-science evidence.', ['pubmed','europe_pmc','crossref','openalex','wikipedia']),
            'education':('Education, teaching, learning and educational research.', ['eric','crossref','openalex','wikipedia'])}
        current = {s['id']:(s['description'],s['databases']) for s in strategies.registry() if s['id']!='medical'}
        self.assertEqual(current, expected)

    def test_explicit_medical_selection_skips_r0_and_survives_restart(self):
        llm=ScriptedLLM([]); r=Research(self.root,llm,providers.adapters())
        state=r.initialize(QUESTION,strategy='medical',context_budget=24000)
        self.assertEqual(state['strategy_selection']['method'],'explicit')
        self.assertEqual(state['strategies'][0]['databases'],MEDICAL)
        self.assertFalse(llm.requests); self.assertFalse(read_records(self.root))
        resumed=Research(self.root,ScriptedLLM([]),providers.adapters())
        self.assertEqual(resumed.inspect()['strategy']['id'],'medical')
        self.assertEqual(resumed.inspect()['strategy']['databases'],MEDICAL)

    def test_r0_can_select_medical_from_the_actual_catalogue(self):
        llm=ScriptedLLM([{'strategy':'medical','reason':'Differential diagnoses require biomedical and clinical evidence.'}])
        r=Research(self.root,llm,providers.adapters()); state=r.initialize(QUESTION,context_budget=24000)
        self.assertEqual(state['strategy_selection']['method'],'r0')
        self.assertEqual(state['strategies'][0]['databases'],MEDICAL)
        records=read_records(self.root); self.assertEqual(len(records),1)
        record=records[0]; self.assertEqual(record['request']['action'],'R0')
        catalogue=record['request']['context']['strategies']
        self.assertEqual(strategies.select(catalogue,'medical')['description'],DESCRIPTION)
        self.assertIn(DESCRIPTION,record['request']['serialized_request'])
        self.assertTrue(record['validation']['accepted'])

    def test_r1_r2_use_all_five_real_adapters_in_order_without_query_rewriting(self):
        data={'pubmed':[{'esearchresult':{'idlist':[]}}], 'europe_pmc':[{'resultList':{'result':[]}}],
              'openalex':[{'results':[]}], 'crossref':[{'status':'ok','message':{'items':[]}}],
              'wikipedia':[{'batchcomplete':True}]}
        adapters,calls=wire_adapters(data)
        llm=ScriptedLLM([{'keywords':['spiculated pulmonary mass', 'volume doubling time']}])
        r=Research(self.root,llm,adapters); r.initialize(QUESTION,strategy='medical',context_budget=24000)
        with patch('mira.providers.time.sleep'): events=[r.step() for _ in range(6)]
        self.assertEqual([e['action'] for e in events],['R1']+['R2']*5)
        self.assertEqual([e['provider'] for e in events[1:]],MEDICAL)
        self.assertTrue(all(e['status']=='committed' for e in events))
        query_parameters=['term','query','search','query.bibliographic','gsrsearch']
        for name,key in zip(MEDICAL,query_parameters):
            self.assertEqual(len(calls[name]),1)
            self.assertEqual(parse_qs(urlsplit(calls[name][0].full_url).query)[key],['spiculated pulmonary mass volume doubling time'])
        self.assertEqual(self.state()['nodes']['q1']['next_database_index'],5)
        self.assertEqual(len(llm.requests),1)

    def test_pubmed_europe_pmc_dedup_metadata_and_provenance_through_r3_restart(self):
        for identifiers in (True,False):
            with self.subTest(all_identifiers=identifiers),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                data={'pubmed':[{'esearchresult':{'idlist':['1234']}},pubmed_xml(identifiers=identifiers)],
                      'europe_pmc':[europe_result(identifiers=identifiers)],'openalex':[], 'crossref':[], 'wikipedia':[]}
                adapters,calls=wire_adapters(data)
                result={'type':'claim','text':'The fixture authors report a diagnostic comparison.',
                        'qualification':'Fixture only; no clinical inference or independent validation.',
                        'source_ids':['pmid:1234'],'related_to':None}
                llm=ScriptedLLM([{'keywords':['pulmonary mass', 'volume doubling time']},{'summary':'Attributed fixture comparison with limitations.','results':[result]}])
                r=Research(root,llm,adapters);r.initialize(QUESTION,strategy='medical',context_budget=24000)
                with patch('mira.providers.time.sleep'):
                    self.assertEqual(r.step()['action'],'R1'); e=r.step(); self.assertEqual(e['provider'],'pubmed')
                    self.assertEqual(r.step()['memory_ids'],['r1'])
                    duplicate=Research(root,llm,adapters).step()
                self.assertEqual(duplicate['provider'],'europe_pmc')
                self.assertEqual(duplicate['duplicate_count'],1); self.assertEqual(duplicate['unique_source_count'],0)
                state=loads((root/'research/state.json').read_text())
                self.assertIsNone(state['nodes']['q1']['pending_results'])
                self.assertEqual(state['nodes']['q1']['next_database_index'],2)
                self.assertEqual(len(llm.requests),2); self.assertEqual(len(state['source_index']),1)
                memory=r.knowledge.document('r1'); ref=memory.metadata['evidence_ref']
                evidence=sources.hydrate(r.store,loads((root/ref).read_text()))
                self.assertEqual(evidence['provider'],'pubmed')
                row=evidence['results'][0]
                self.assertEqual(row['title'],'Controlled study of pulmonary mass diagnostic methods')
                self.assertEqual(row['authors'],['Jane Smith']); self.assertEqual(row['published'],'2024 Feb 12')
                self.assertEqual(row['url'],'https://pubmed.ncbi.nlm.nih.gov/1234/')
                self.assertIn('diagnostic comparison',row['content']); self.assertEqual(row['content_kind'],'abstract')
                expected={'pmid':'1234',**({'doi':'10.1234/medical','pmcid':'PMC1234'} if identifiers else {})}
                self.assertEqual(row['identifiers'],expected)
                citation=r.knowledge.provenance('r1#f1')[0]
                self.assertEqual(citation['source']['identifiers'],expected)
                self.assertEqual(citation['source']['published'],'2024 Feb 12')
                self.assertEqual(citation['source']['url'],row['url'])
                indexed=next(iter(state['source_index'].values()))
                self.assertEqual(indexed['source']['authors'],['Jane Smith'])
                self.assertIn('source:europe_pmc:MED:1234',indexed['aliases'])
                self.assertEqual(r.knowledge.validate()['documents'],1)
                self.assertFalse(r.store.recovery_status()['blocked'])

    def test_pubmed_preserves_available_dates_without_inventing_precision(self):
        dates=[('<Year>2024</Year>','2024'), ('<Year>2024</Year><Month>02</Month><Day>12</Day>','2024 02 12'),
               ('<MedlineDate>2023 Dec-2024 Jan</MedlineDate>','2023 Dec-2024 Jan'),
               ('<Year>2024</Year><Season>Winter</Season>','2024 Winter'), ('','')]
        for supplied,expected in dates:
            with self.subTest(supplied=supplied):
                adapters,_=wire_adapters({'pubmed':[{'esearchresult':{'idlist':['1234']}},pubmed_xml(supplied)],
                    'europe_pmc':[],'openalex':[],'crossref':[],'wikipedia':[]})
                with patch('mira.providers.time.sleep'): result=adapters['pubmed'].search('pulmonary mass')
                self.assertEqual(result['results'][0]['published'],expected)

    def test_europe_source_identifiers_do_not_treat_other_databases_as_pubmed(self):
        for source,identity,expected in [('MED','1234',{'pmid':'1234'}),('PMC','PMC1234',{'pmcid':'PMC1234'}),
                                          ('PPR','1234',{}),('PAT','1234',{})]:
            with self.subTest(source=source):
                item={'source':source,'id':identity,'title':'Article without further metadata'}
                adapters,_=wire_adapters({'pubmed':[],'europe_pmc':[{'resultList':{'result':[item]}}],
                    'openalex':[],'crossref':[],'wikipedia':[]})
                with patch('mira.providers.time.sleep'):row=adapters['europe_pmc'].search('mass')['results'][0]
                self.assertEqual(row['identifiers'],expected); self.assertEqual(row['authors'],[])
                self.assertEqual(row['published'],''); self.assertEqual(row['content_kind'],'bibliographic_metadata')

    def test_openalex_retains_supplied_pmcid_and_doi_and_deduplicates_by_pmcid(self):
        item={'id':'https://openalex.org/W1234','display_name':'A differently formatted title',
              'ids':{'pmcid':'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234/','doi':'https://doi.org/10.1234/medical'}}
        adapters,_=wire_adapters({'pubmed':[],'europe_pmc':[],'openalex':[{'results':[item]}],'crossref':[],'wikipedia':[]})
        row=adapters['openalex'].search('pulmonary mass')['results'][0]
        self.assertEqual(row['identifiers']['pmcid'],'PMC1234')
        self.assertEqual(row['identifiers']['doi'],'https://doi.org/10.1234/medical')
        first={**deepcopy(row),'id':'pmid:1234','identifiers':{'pmid':'1234','pmcid':'PMC1234'}}
        index={};sources.processed(index,[first],'fixture')
        accepted,duplicates=sources.unique([row],index)
        self.assertFalse(accepted);self.assertEqual(len(duplicates),1)


if __name__=='__main__':unittest.main()
