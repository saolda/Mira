"""Wire-level public API contracts; no internet in deterministic tests."""
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from mira import providers
from mira.providers import (WikipediaSearch, PubMedSearch, CrossrefSearch,
                            EuropePMCSearch, ERICSearch, OpenAlexSearch)


class ProviderTests(unittest.TestCase):
    def setUp(self): providers._LAST.clear()

    def adapter(self, cls, responses, **kwargs):
        queue=iter(responses);self.calls=[]
        def open_(request,timeout):
            self.calls.append(request)
            value=next(queue)
            if isinstance(value,Exception): raise value
            return BytesIO(value if isinstance(value,bytes) else json.dumps(value).encode())
        return cls(opener=open_,**kwargs)

    def test_scientific_comparisons_entities_and_markup_preserved(self):
        cases = [
            ('P < 0.05 and tumour volume > 10 cm³', 'P < 0.05 and tumour volume > 10 cm³'),
            ('P &lt; 0.05 and confidence interval &gt; 1.0', 'P < 0.05 and confidence interval > 1.0'),
            ('<p>Volume doubling time was <b>43 days</b>, P &lt; 0.001.</p>',
             'Volume doubling time was 43 days, P < 0.001.'),
            ('<div class="x > y"><p>α <b>1.2e−3 <i>± 0.4</i></b></p><p>β ≥ 2 &amp; γ ≤ 4.</p></div>',
             'α 1.2e−3 ± 0.4 β ≥ 2 & γ ≤ 4.'),
            ('<p>First</p><p>second<br>third</p>', 'First second third'),
            ('<jats:p>Nested <jats:italic>scientific</jats:italic> text.</jats:p>', 'Nested scientific text.'),
            ('P<0.05; n>10; 1.2e-5 mol/L; 95% CI (1.1, 2.2).', 'P<0.05; n>10; 1.2e-5 mol/L; 95% CI (1.1, 2.2).'),
            ('A <b>malformed <i>nested abstract', 'A malformed nested abstract'),
            ('Ordinary abstract text. No changes; n = 23.', 'Ordinary abstract text. No changes; n = 23.'),
            ('&lt;b&gt;literal encoded markup&lt;/b&gt;', '<b>literal encoded markup</b>'),
        ]
        for source, expected in cases:
            with self.subTest(source=source): self.assertEqual(providers.plain(source), expected)

    def test_scientific_cleaning_bounds_and_metadata(self):
        text = '<p>P < 0.05 and tumour volume > 10 cm³; ' + 'α ' * 30 + '</p>'
        expected = providers.plain(text)
        row = providers.row('source:1', '<i>Study</i>', 'https://example.org/1', text,
            authors=['Author α'], published='2026', identifiers={'doi':'10.1234/a'}, max_chars=50)
        self.assertEqual(row['content'], expected[:50])
        self.assertTrue(row['truncated'])
        self.assertEqual(row['id'], 'source:1')
        self.assertEqual(row['url'], 'https://example.org/1')
        self.assertEqual(row['identifiers'], {'doi':'10.1234/a'})
        self.assertEqual(row['authors'], ['Author α'])
        self.assertEqual(row['published'], '2026')
        short = providers.row('s', 'Title', 'https://example.org', 'P < 0.05 and n > 10')
        self.assertFalse(short['truncated'])
        self.assertEqual(short['content'], 'P < 0.05 and n > 10')

    def test_wikipedia_extract_metadata_and_no_hidden_fallback(self):
        data={'query':{'pages':[{'pageid':123,'title':'Artificial intelligence','fullurl':'https://en.wikipedia.org/wiki/Artificial_intelligence','extract':'A useful introductory description.'}]}}
        adapter=self.adapter(WikipediaSearch,[data,{'batchcomplete':True}])
        with patch('mira.providers.time.sleep'):
            result=adapter.search('artificial intelligence');empty=adapter.search('missing topic')
        row=result['results'][0]
        self.assertEqual(row['id'],'wikipedia:en:123');self.assertEqual(row['authors'],[])
        self.assertEqual(row['content_kind'],'encyclopedia_excerpt')
        self.assertEqual(empty['status'],'empty');self.assertEqual(len(self.calls),2)
        params=parse_qs(urlsplit(self.calls[0].full_url).query)
        self.assertEqual(params['gsrsearch'],['artificial intelligence']);self.assertEqual(params['maxlag'],['5'])
        self.assertIn('Mira/',self.calls[0].headers['User-agent'])

    def test_pubmed_batched_fetch_nested_text_and_identifiers(self):
        xml=b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1234</PMID><Article>
        <ArticleTitle>A <i>controlled</i> trial</ArticleTitle><Abstract><AbstractText Label="METHODS">A useful <b>abstract</b>.</AbstractText></Abstract>
        <AuthorList><Author><ForeName>Jane</ForeName><LastName>Smith</LastName></Author></AuthorList>
        <Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation>
        <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1234/trial</ArticleId><ArticleId IdType="pmc">PMC1234</ArticleId></ArticleIdList></PubmedData>
        </PubmedArticle></PubmedArticleSet>'''
        a=self.adapter(PubMedSearch,[{'esearchresult':{'idlist':['1234']}},xml],api_key='fake-secret',contact='test@example.org')
        with patch('mira.providers.time.sleep') as sleep:result=a.search('asthma biologics')
        row=result['results'][0]
        self.assertEqual(row['title'],'A controlled trial');self.assertEqual(row['authors'],['Jane Smith'])
        self.assertEqual(row['content'],'METHODS: A useful abstract.')
        self.assertEqual(row['identifiers'],{'pmid':'1234','doi':'10.1234/trial','pmcid':'PMC1234'})
        self.assertEqual(len(self.calls),2);sleep.assert_called_once()
        for call in self.calls:
            params=parse_qs(urlsplit(call.full_url).query)
            self.assertEqual(params['api_key'],['fake-secret']);self.assertEqual(params['email'],['test@example.org'])
        self.assertNotIn('fake-secret',json.dumps(result))
        self.assertEqual(self.adapter(PubMedSearch,[{'esearchresult':{'idlist':[]}}]).search('none')['status'],'empty')

    def test_crossref_jats_no_abstract_metadata_and_contact(self):
        item={'DOI':'10.1234/paper','title':['A controlled paper'],'abstract':'<jats:p>Some <jats:italic>useful</jats:italic> research.</jats:p>',
              'author':[{'given':'Jane','family':'Smith'}],'published':{'date-parts':[[2024,2,1]]}}
        a=self.adapter(CrossrefSearch,[{'status':'ok','message':{'items':[item]}},
            {'status':'ok','message':{'items':[{k:v for k,v in item.items() if k!='abstract'}]}}],contact='test@example.org')
        with patch('mira.providers.time.sleep'):
            result=a.search('research');metadata=a.search('research')
        self.assertEqual(result['results'][0]['content'],'Some useful research.')
        self.assertEqual(result['results'][0]['identifiers'],{'doi':'10.1234/paper'})
        self.assertEqual(metadata['results'][0]['content_kind'],'bibliographic_metadata')
        self.assertIn('Title:',metadata['results'][0]['content'])
        self.assertEqual(parse_qs(urlsplit(self.calls[0].full_url).query)['mailto'],['test@example.org'])

    def test_europe_pmc_core_identifiers_and_correct_source_url(self):
        data={'resultList':{'result':[{'id':'1234','source':'MED','pmid':'1234','pmcid':'PMC1','doi':'10.1234/a','title':'A trial',
            'abstractText':'<p>Results of a trial.</p>','authorList':{'author':[{'fullName':'Smith J'}]},'firstPublicationDate':'2024-01-01'}]}}
        a=self.adapter(EuropePMCSearch,[data]);result=a.search('trial')
        row=result['results'][0]
        self.assertEqual(row['url'],'https://europepmc.org/article/MED/1234')
        self.assertEqual(row['identifiers']['pmid'],'1234');self.assertEqual(row['authors'],['Smith J'])
        self.assertEqual(row['content'],'Results of a trial.')
        self.assertEqual(parse_qs(urlsplit(self.calls[0].full_url).query)['resultType'],['core'])

    def test_eric_normalization(self):
        a=self.adapter(ERICSearch,[{'response':{'docs':[{'id':'EJ1234','title':'Classroom research','author':['Jane Smith'],
            'description':'A controlled classroom study.','publicationdateyear':2024}]}}])
        result=a.search('teaching');row=result['results'][0]
        self.assertEqual(row['id'],'eric:EJ1234');self.assertEqual(row['url'],'https://eric.ed.gov/?id=EJ1234')
        self.assertEqual(row['authors'],['Jane Smith']);self.assertEqual(row['published'],'2024')
        self.assertEqual(parse_qs(urlsplit(self.calls[0].full_url).query)['rows'],['2'])

    def test_openalex_inverted_abstract_optional_key_and_missing_metadata(self):
        item={'id':'https://openalex.org/W1234','display_name':'An example work','doi':'https://doi.org/10.1234/work',
            'abstract_inverted_index':{'useful':[1],'A':[0],'abstract':[2]},'authorships':[{'author':{'display_name':'Jane Smith'}}],
            'ids':{'pmid':'https://pubmed.ncbi.nlm.nih.gov/1234/'},'publication_year':2024}
        a=self.adapter(OpenAlexSearch,[{'results':[item]}],api_key='fake-key')
        result=a.search('research');row=result['results'][0]
        self.assertEqual(row['content'],'A useful abstract');self.assertEqual(row['identifiers']['pmid'],'1234')
        self.assertEqual(parse_qs(urlsplit(self.calls[0].full_url).query)['api_key'],['fake-key'])
        item.update(abstract_inverted_index=None,doi=None,primary_location=None,authorships=[])
        result=self.adapter(OpenAlexSearch,[{'results':[item]}]).search('research')
        self.assertEqual(result['results'][0]['content_kind'],'bibliographic_metadata')
        self.assertNotIn('api_key',parse_qs(urlsplit(self.calls[0].full_url).query))

    def test_provider_empty_failed_rate_limited_and_malformed_are_distinct(self):
        fixtures=[(WikipediaSearch,{'batchcomplete':True}),(PubMedSearch,{'esearchresult':{'idlist':[]}}),
                  (CrossrefSearch,{'status':'ok','message':{'items':[]}}),(EuropePMCSearch,{'resultList':{'result':[]}}),
                  (ERICSearch,{'response':{'docs':[]}}),(OpenAlexSearch,{'results':[]})]
        for cls,empty in fixtures:
            with self.subTest(provider=cls.__name__):
                self.assertEqual(self.adapter(cls,[empty]).search('test')['status'],'empty')
                self.assertEqual(self.adapter(cls,[b'not JSON/XML']).search('test')['status'],'failed')
                self.assertEqual(self.adapter(cls,[URLError('offline')]).search('test')['status'],'failed')
                error=HTTPError('https://example.org',429,'limited',{'Retry-After':'10'},BytesIO(b'limited'))
                with patch('mira.providers.time.sleep'):
                    result=self.adapter(cls,[error]).search('test')
                self.assertEqual(result['status'],'rate_limited');self.assertEqual(result['retry_after'],'10')
                self.assertNotIn('error',result)

    def test_explicit_content_truncation_and_shared_host_pacing(self):
        item={'id':'EJ1','title':'Study','description':'long '*100}
        a=self.adapter(ERICSearch,[{'response':{'docs':[item]}},{'response':{'docs':[item]}}],max_abstract_chars=30)
        with patch('mira.providers.time.sleep') as sleep:
            self.assertEqual(a.search('test')['status'],'ok');second=a.search('test')
        self.assertTrue(second['results'][0]['truncated']);self.assertEqual(len(second['results'][0]['content']),30)
        sleep.assert_called_once()
