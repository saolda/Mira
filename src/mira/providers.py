"""Small public API adapters adapted from autonomous_ai/actions.py, without routing/fallbacks."""
import html
import json
import os
import re
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from .format import require
from .search import ArxivSearch, validate_search

USER_AGENT = 'Mira/0.3 (local research; https://github.com/saolda/Mira)'
_PACE_LOCK = threading.Lock()
_LAST = {}


def plain(value):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', str(value or ''))).split())


def row(identity, title, url, abstract='', *, authors=(), published='', identifiers=None, details='', max_chars=2500):
    abstract = plain(abstract)
    metadata = plain(details) or f'Title: {plain(title)}. Authors: {", ".join(authors)}. Published: {published or "not supplied"}.'
    content = abstract or metadata
    return {'id': str(identity), 'title': plain(title), 'url': url, 'authors': [plain(a) for a in authors if plain(a)],
            'published': str(published), 'identifiers': {k: str(v) for k, v in (identifiers or {}).items() if v},
            'content': content[:max_chars], 'content_kind': 'abstract' if abstract else 'bibliographic_metadata',
            'truncated': len(content) > max_chars}


class PublicAPI:
    interval = 1.0  # Conservative local policy where no numeric minimum is published.

    def __init__(self, *, limit=2, timeout=25, max_abstract_chars=2500, opener=None, api_key=None, contact=None):
        require(type(limit) is int and 1 <= limit <= 10 and timeout > 0 and max_abstract_chars > 0, 'invalid provider limits')
        self.limit, self.timeout, self.max_chars = limit, timeout, max_abstract_chars
        self.opener, self.api_key = opener or urlopen, api_key
        self.contact = contact or os.environ.get('MIRA_CONTACT_EMAIL')
        self.secrets = (api_key,) if api_key else ()

    def get(self, endpoint, params, *, key=False):
        params = dict(params)
        if key and self.api_key: params['api_key'] = self.api_key
        request = Request(endpoint + '?' + urlencode(params), headers={'User-Agent': USER_AGENT,
            'Accept': 'application/json, application/xml', 'Api-User-Agent': USER_AGENT})
        host = urlsplit(endpoint).netloc
        # Per-host, process-wide serialization also paces PubMed's two requests.
        with _PACE_LOCK:
            delay = max(0, self.interval - (time.monotonic() - _LAST.get(host, float('-inf'))))
            if delay: time.sleep(delay)
            _LAST[host] = time.monotonic()
            with self.opener(request, timeout=self.timeout) as response:
                return response.read().decode('utf-8')

    def search(self, query):
        try:
            rows = self.retrieve(query)
            require(isinstance(rows, list) and len(rows) <= self.limit, 'provider exceeded result bound')
            return validate_search({'status': 'ok' if rows else 'empty', 'results': rows})
        except HTTPError as exc:
            outcome = {'status': 'rate_limited' if exc.code == 429 else 'failed', 'results': [],
                       'http_status': exc.code, 'retry_after': exc.headers.get('Retry-After') if exc.headers else None,
                       'error': 'provider HTTP request failed'}
            exc.close()
            return outcome
        except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError) as exc:
            return {'status': 'failed', 'results': [], 'error': type(exc).__name__ + ': invalid response or unavailable provider'}

    def result(self, *args, **kwargs):
        return row(*args, max_chars=self.max_chars, **kwargs)


class WikipediaSearch(PublicAPI):
    def retrieve(self, query):
        data = json.loads(self.get('https://en.wikipedia.org/w/api.php', {'action':'query', 'generator':'search',
            'gsrsearch':query, 'gsrlimit':self.limit, 'prop':'extracts|info', 'exintro':1, 'explaintext':1,
            'inprop':'url', 'format':'json', 'formatversion':2, 'maxlag':5}))
        require('error' not in data and ('query' in data or 'batchcomplete' in data), 'Wikipedia API error')
        pages = data.get('query', {}).get('pages', [])
        rows = []
        for p in sorted(pages, key=lambda p: p.get('index', 0)):
            r = self.result(f'wikipedia:en:{p["pageid"]}', p['title'],
                            p.get('fullurl') or f'https://en.wikipedia.org/?curid={p["pageid"]}', p.get('extract',''),
                            identifiers={'wikipedia':f'en:{p["pageid"]}'})
            r['content_kind'] = 'encyclopedia_excerpt' if p.get('extract') else 'bibliographic_metadata'
            rows.append(r)
        return rows


class PubMedSearch(PublicAPI):
    interval = 0.35  # NCBI: no more than 3 requests/s without a key; stay below even with one.

    def retrieve(self, query):
        common = {'db':'pubmed', 'tool':'Mira'}
        if self.contact: common['email'] = self.contact
        data = json.loads(self.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
            {**common,'term':query,'retmode':'json','retmax':self.limit,'sort':'relevance'}, key=True))
        require('error' not in data and 'errorlist' not in data.get('esearchresult',{}), 'PubMed query error')
        ids = data['esearchresult']['idlist']
        if not ids: return []
        root = ET.fromstring(self.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
            {**common,'id':','.join(ids),'retmode':'xml'}, key=True))
        require(root.tag == 'PubmedArticleSet' and root.find('.//ERROR') is None, 'invalid PubMed fetch')
        rows = []
        for a in root.findall('PubmedArticle'):
            pmid = a.findtext('MedlineCitation/PMID')
            title = a.find('.//ArticleTitle')
            authors = [' '.join(filter(None,[author.findtext('ForeName') or author.findtext('Initials'),
                                             author.findtext('LastName') or author.findtext('CollectiveName')]))
                       for author in a.findall('.//AuthorList/Author')]
            abstract = ' '.join((n.get('Label','') + ': ' if n.get('Label') else '') + ''.join(n.itertext())
                                for n in a.findall('.//Abstract/AbstractText'))
            identifiers = {'pmid':pmid}
            identifiers.update({n.get('IdType'): n.text for n in a.findall('PubmedData/ArticleIdList/ArticleId') if n.get('IdType') in {'doi','pmc'}})
            if 'pmc' in identifiers: identifiers['pmcid'] = identifiers.pop('pmc')
            rows.append(self.result('pmid:'+str(pmid), ''.join(title.itertext()) if title is not None else '',
                f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/', abstract, authors=authors,
                published=a.findtext('.//JournalIssue/PubDate/Year') or a.findtext('.//PubDate/MedlineDate') or '',
                identifiers=identifiers))
        require(len(rows) == len(ids), 'incomplete PubMed batch')
        return rows


class CrossrefSearch(PublicAPI):
    def retrieve(self, query):
        params = {'query.bibliographic':query,'rows':self.limit,
                  'select':'DOI,title,abstract,author,published,URL,type'}
        if self.contact: params['mailto'] = self.contact
        data = json.loads(self.get('https://api.crossref.org/works',params))
        require(data.get('status') == 'ok', 'Crossref API error')
        rows = []
        for item in data['message']['items']:
            doi = item['DOI']
            date = '-'.join(map(str,((item.get('published') or {}).get('date-parts') or [[]])[0]))
            authors = [' '.join(filter(None,[a.get('given'),a.get('family') or a.get('name')])) for a in item.get('author',[])]
            rows.append(self.result('doi:'+doi.lower(), ' '.join(item['title']), item.get('URL') or 'https://doi.org/'+doi,
                                    item.get('abstract',''), authors=authors, published=date, identifiers={'doi':doi}))
        return rows


class EuropePMCSearch(PublicAPI):
    def retrieve(self, query):
        data = json.loads(self.get('https://www.ebi.ac.uk/europepmc/webservices/rest/search',
                         {'query':query,'format':'json','pageSize':self.limit,'resultType':'core'}))
        rows = []
        for item in data['resultList']['result']:
            source, identity = item['source'], item['id']
            authors = [a.get('fullName') or ' '.join(filter(None,[a.get('firstName'),a.get('lastName')]))
                       for a in (item.get('authorList') or {}).get('author',[])]
            if not authors and item.get('authorString'): authors = [item['authorString']]
            rows.append(self.result(f'europe_pmc:{source}:{identity}', item['title'],
                f'https://europepmc.org/article/{source}/{identity}', item.get('abstractText',''), authors=authors,
                published=item.get('firstPublicationDate') or item.get('pubYear',''),
                identifiers={k:item[k] for k in ('doi','pmid','pmcid') if item.get(k)}))
        return rows


class ERICSearch(PublicAPI):
    def retrieve(self, query):
        data = json.loads(self.get('https://api.ies.ed.gov/eric/', {'search':query,'rows':self.limit,'format':'json','start':0,
            'fields':'id,title,author,source,publicationdateyear,description,subject,peerreviewed,url'}))
        rows = []
        for item in data['response']['docs']:
            authors = item.get('author') or []
            if isinstance(authors,str): authors = [authors]
            identity = item['id']
            rows.append(self.result('eric:'+identity, item['title'], 'https://eric.ed.gov/?id='+identity,
                item.get('description',''), authors=authors, published=item.get('publicationdateyear',''), identifiers={'eric':identity}))
        return rows


class OpenAlexSearch(PublicAPI):
    def retrieve(self, query):
        data = json.loads(self.get('https://api.openalex.org/works', {'search':query,'per_page':self.limit}, key=True))
        rows = []
        for item in data['results']:
            inverted = item.get('abstract_inverted_index') or {}
            abstract = ' '.join(word for _, word in sorted((position,word) for word, positions in inverted.items() for position in positions))
            identifiers = {'openalex':item['id']}
            if item.get('doi'): identifiers['doi'] = item['doi']
            pmid = (item.get('ids') or {}).get('pmid')
            if pmid: identifiers['pmid'] = pmid.rstrip('/').split('/')[-1]
            authors = [(a.get('author') or {}).get('display_name','') for a in item.get('authorships',[])]
            location = item.get('primary_location') or {}
            rows.append(self.result(item['id'], item['display_name'], item.get('doi') or location.get('landing_page_url') or item['id'],
                abstract, authors=authors, published=item.get('publication_date') or item.get('publication_year',''), identifiers=identifiers))
        return rows


def adapters(*, limit=2, timeout=25):
    common = {'limit':limit,'timeout':timeout}
    return {'arxiv':ArxivSearch(**common), 'wikipedia':WikipediaSearch(**common),
            'pubmed':PubMedSearch(**common,api_key=os.environ.get('MIRA_NCBI_API_KEY')),
            'crossref':CrossrefSearch(**common), 'europe_pmc':EuropePMCSearch(**common), 'eric':ERICSearch(**common),
            'openalex':OpenAlexSearch(**common,api_key=os.environ.get('MIRA_OPENALEX_API_KEY') or os.environ.get('OPENALEX_API_KEY'))}
