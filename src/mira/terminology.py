"""Optional deterministic vocabulary lookup. Never scientific evidence or an LLM.

MeSH concepts (M IDs), not whole descriptors, establish synonym identity.
MedGen is deliberately not enabled: its aggregated definitions have source-specific
reuse conditions; an adapter must establish those before admitting descriptions.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import fcntl
import json
import re
import time
import unicodedata
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from .clients import NoRedirect
from .format import digest, dumps, loads, require

BASE = 'https://id.nlm.nih.gov/mesh/'
URI = re.compile(r'https?://id\.nlm\.nih\.gov/mesh/([MTD][0-9]+)\Z')
STATUSES = {'matched', 'not_found', 'ambiguous', 'unavailable', 'error', 'not_attempted'}
FAILURE_COOLDOWN = 900
RESULT_TTL = 86400


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def timestamp(now=None):
    return (datetime.now(timezone.utc) if now is None else
            datetime.fromtimestamp(now, timezone.utc)).isoformat()


def lookup_due(record, now):
    """Canonical lookup history controls retries, even after cache/index loss."""
    history = record.get('terminology', [])
    if not history or history[-1]['status'] == 'not_attempted': return True
    last = history[-1]
    delay = FAILURE_COOLDOWN if last['status'] in {'unavailable', 'error'} else RESULT_TTL
    return datetime.fromisoformat(last['retrieved_at']).timestamp() + delay <= now


def failure_reason(exc):
    message = type(exc).__name__ + ': ' + str(exc)
    return ''.join(c if ord(c) >= 32 or c in '\n\r\t' else '?' for c in message)[:500]


def text(value, limit=16000):
    require(isinstance(value, str) and value.strip() and len(value) <= limit and
            not any(ord(c) < 32 and c not in '\n\r\t' for c in value), 'invalid terminology text')
    require(not any(0xD800 <= ord(c) <= 0xDFFF for c in value), 'invalid Unicode in terminology text')


def validate_concept(value):
    require(isinstance(value, dict) and set(value) == {'provider', 'concept_id', 'url',
        'preferred_name', 'aliases', 'matched_name', 'matched_term_ids', 'descriptor_ids',
        'match_type', 'retrieved_at', 'descriptions'}, 'invalid terminology concept')
    require(value['provider'] == 'mesh' and re.fullmatch(r'M[0-9]+', value['concept_id']),
            'unsupported terminology authority or concept ID')
    require(value['url'] == BASE + value['concept_id'], 'invalid terminology citation URL')
    for k in ('preferred_name', 'matched_name'): text(value[k], 500)
    require(isinstance(value['aliases'], list) and len(value['aliases']) <= 128, 'invalid terminology aliases')
    for alias in value['aliases']: text(alias, 500)
    require(normalize(value['matched_name']) in {normalize(n) for n in
        [value['preferred_name'], *value['aliases']]}, 'matched name absent from concept synonyms')
    require(value['match_type'] in {'exact', 'entry_term'}, 'invalid terminology match type')
    for field, prefix in (('matched_term_ids', 'T'), ('descriptor_ids', 'D')):
        require(isinstance(value[field], list) and len(value[field]) <= 128 and
            all(isinstance(i, str) and re.fullmatch(prefix + '[0-9]+', i) for i in value[field]),
            'invalid terminology identity links')
    require(value['matched_term_ids'], 'missing verified term identity')
    require(isinstance(value['retrieved_at'], str) and
        datetime.fromisoformat(value['retrieved_at']).tzinfo is not None, 'invalid terminology timestamp')
    require(isinstance(value['descriptions'], list) and len(value['descriptions']) <= 16,
            'invalid terminology descriptions')
    for row in value['descriptions']:
        require(isinstance(row, dict) and set(row) == {'type', 'text', 'scope', 'qualification'} and
                row['type'] in {'definition', 'scope_note', 'description'}, 'invalid terminology description type')
        text(row['text']); text(row['scope']); text(row['qualification'])
    return value


def validate_result(value, term):
    require(isinstance(value, dict) and set(value) == {'provider', 'term', 'status', 'reason',
        'retrieved_at', 'concepts'}, 'invalid terminology outcome')
    require(value['provider'] == 'mesh' and value['term'] == term and value['status'] in STATUSES,
            'invalid terminology outcome identity/status')
    text(value['reason']); text(value['retrieved_at'])
    require(datetime.fromisoformat(value['retrieved_at']).tzinfo is not None, 'invalid lookup timestamp')
    require(isinstance(value['concepts'], list) and len(value['concepts']) <= 32, 'invalid lookup concepts')
    for concept in value['concepts']:
        validate_concept(concept)
        require(normalize(concept['matched_name']) == normalize(term), 'unrelated terminology match')
    require((value['status'] == 'matched' and len(value['concepts']) == 1) or
            (value['status'] != 'matched' and not value['concepts']), 'invalid matched terminology outcome')
    return value


class BudgetExceeded(TimeoutError):
    pass


class MeSH:
    """Official exact entry-term lookup, followed by explicit RDF concept links."""
    name = 'mesh'
    interval = 1.0

    def lookup(self, term, get):
        rows = get(BASE + 'lookup/term?' + urlencode({'label': term, 'match': 'exact', 'limit': 32}))
        require(isinstance(rows, list) and len(rows) <= 32, 'malformed MeSH lookup response')
        ids = set()
        for row in rows:
            require(isinstance(row, dict) and isinstance(row.get('label'), str), 'invalid MeSH lookup row')
            match = URI.fullmatch(row.get('resource', ''))
            require(match and match[1].startswith('T'), 'invalid MeSH term URI')
            require(normalize(row['label']) == normalize(term), 'MeSH returned a nonexact label')
            ids.add(match[1])
        if not ids: return 'not_found', 'No exact MeSH canonical or entry-term match.', []
        if len(rows) == 32: return 'ambiguous', 'MeSH lookup reached its result limit.', []
        query = '''PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?concept ?preferred ?matched ?alias ?name ?scope ?descriptor WHERE {
VALUES ?matched { %s }
{ ?concept meshv:term ?matched } UNION { ?concept meshv:preferredTerm ?matched }
?concept a meshv:Concept; rdfs:label ?preferred.
?concept meshv:active true.
?concept (meshv:term|meshv:preferredTerm) ?alias. ?alias meshv:prefLabel ?name.
OPTIONAL { ?concept meshv:scopeNote ?scope }
OPTIONAL { ?descriptor meshv:preferredConcept ?concept }
} LIMIT 257''' % ' '.join('<http://id.nlm.nih.gov/mesh/' + i + '>' for i in sorted(ids))
        data = get(BASE + 'sparql?' + urlencode({'query': query, 'format': 'JSON'}))
        require(isinstance(data, dict) and isinstance(data.get('results'), dict) and
                isinstance(data['results'].get('bindings'), list), 'malformed MeSH RDF response')
        bindings = data['results']['bindings']
        require(len(bindings) < 257, 'MeSH concept response truncated')
        concepts = {}
        def literal(row, key):
            item = row.get(key)
            require(isinstance(item, dict) and item.get('type') in {'literal', 'typed-literal'} and
                    item.get('xml:lang', 'en') == 'en', 'invalid MeSH literal: ' + key)
            text(item.get('value')); return item['value']
        def identifier(row, key, prefix):
            item = row.get(key)
            require(isinstance(item, dict) and item.get('type') == 'uri', 'invalid MeSH identity binding')
            match = URI.fullmatch(item.get('value', ''))
            require(match and match[1].startswith(prefix), 'invalid MeSH concept link')
            return match[1]
        for row in bindings:
            require(isinstance(row, dict), 'invalid MeSH RDF row')
            identity = identifier(row, 'concept', 'M')
            matched = identifier(row, 'matched', 'T')
            require(matched in ids, 'MeSH concept linked to an unrequested term')
            identifier(row, 'alias', 'T')
            preferred, name = literal(row, 'preferred'), literal(row, 'name')
            c = concepts.setdefault(identity, {'provider': 'mesh', 'concept_id': identity,
                'url': BASE + identity, 'preferred_name': preferred, 'aliases': [], 'matched_name': term,
                'matched_term_ids': [], 'descriptor_ids': [], 'match_type': 'exact' if
                    normalize(preferred) == normalize(term) else 'entry_term',
                'retrieved_at': timestamp(), 'descriptions': []})
            require(c['preferred_name'] == preferred, 'inconsistent preferred name')
            if name not in c['aliases']: c['aliases'].append(name)
            if matched not in c['matched_term_ids']: c['matched_term_ids'].append(matched)
            if 'descriptor' in row:
                d = identifier(row, 'descriptor', 'D')
                if d not in c['descriptor_ids']: c['descriptor_ids'].append(d)
            if 'scope' in row:
                description = {'type': 'scope_note', 'text': literal(row, 'scope'), 'scope': 'MeSH concept',
                    'qualification': 'NLM MeSH scope note; terminology information, not independent scientific evidence.'}
                if description not in c['descriptions']: c['descriptions'].append(description)
        require(concepts, 'MeSH lookup term has no verifiable concept link')
        if len(concepts) != 1:
            return 'ambiguous', 'Exact entry term maps to multiple MeSH concepts: ' + ', '.join(sorted(concepts)) + '.', []
        c = next(iter(concepts.values()))
        c['aliases'].sort(key=lambda n: (normalize(n), n))
        c['matched_term_ids'].sort(); c['descriptor_ids'].sort()
        c['descriptions'].sort(key=lambda d: (d['type'], d['text']))
        validate_concept(c)
        if re.fullmatch('[A-Z][A-Z0-9-]{1,11}', term) and c['match_type'] != 'exact':
            return 'ambiguous', 'Abbreviation requires additional concept scope; no equivalence assumed.', []
        return 'matched', 'Exact preferred name or explicitly linked MeSH entry term.', [c]


def http_json(url, timeout):
    """Fixed-authority requests, no redirects, bounded body and read deadline."""
    require(url.startswith(BASE), 'unapproved terminology endpoint')
    end = time.monotonic() + timeout
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Mira terminology lookup'})
    with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        chunks, size = [], 0
        connection = response.fp.raw._sock
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0: raise TimeoutError('terminology response deadline exceeded')
            connection.settimeout(remaining)
            chunk = response.read1(min(65536, 1048577-size))
            if not chunk: break
            chunks.append(chunk); size += len(chunk)
            require(size <= 1048576, 'terminology response too large')
    return loads(b''.join(chunks).decode('utf-8'))


class Enricher:
    """Disposable response cache; authoritative after-images live in the glossary.

    The provider protocol is lookup(term, get) -> (status, reason, concepts).
    No adapter may execute extra model calls. Cache failures are optional failures.
    """
    def __init__(self, cache_dir, *, provider=None, transport=http_json, max_terms=2,
                 request_timeout=3, action_timeout=8, max_requests=6, clock=time.time,
                 monotonic=time.monotonic, sleep=time.sleep):
        require(type(max_terms) is int and 0 <= max_terms <= 5 and type(max_requests) is int and
                0 <= max_requests <= 20 and request_timeout > 0 and action_timeout > 0,
                'invalid terminology lookup budget')
        self.cache_dir, self.provider, self.transport = cache_dir, provider or MeSH(), transport
        self.max_terms, self.request_timeout, self.action_timeout, self.max_requests = max_terms, request_timeout, action_timeout, max_requests
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep

    @staticmethod
    def enabled(state):
        return state['strategies'][state['strategy_index']]['id'] in {'medical', 'biomedical'}

    def enrich(self, records):
        report = {'provider': self.provider.name, 'api_calls': 0, 'cache_hits': 0, 'concept_cache_hits': 0, 'outcomes': [],
                  'budget': {'max_terms': self.max_terms, 'max_requests': self.max_requests,
                             'request_timeout': self.request_timeout, 'action_timeout': self.action_timeout}}
        results = {}
        start = self.monotonic()
        end = start + self.action_timeout
        used = 0
        seen = {}
        for record in records:
            term = record['term']; key = normalize(term)
            outcome = {'provider': self.provider.name, 'term': term, 'status': 'not_attempted',
                       'reason': 'Per-R3 lookup budget exhausted.', 'retrieved_at': timestamp(self.clock()), 'concepts': []}
            if key in seen:
                outcome = {**deepcopy(seen[key]), 'term': term}
                report['cache_hits'] += 1
            elif used < self.max_terms and self.monotonic() < end:
                used += 1
                try:
                    outcome = self._lookup(term, end, report)
                    validate_result(outcome, term)
                except Exception as exc:
                    outcome.update(status='error', reason=failure_reason(exc),
                                   retrieved_at=timestamp(self.clock()), concepts=[])
                seen[key] = outcome
            results[record['id']] = outcome
            report['outcomes'].append({'id': record['id'], **outcome})
        report['elapsed_seconds'] = self.monotonic() - start
        return results, report

    def _lookup(self, term, end, report):
        from .experiments import atomic_text, confined
        directory = confined(self.cache_dir); directory.mkdir(parents=True, exist_ok=True)
        cache = directory / (digest(self.provider.name + ':' + normalize(term)) + '.json')
        require(not cache.is_symlink(), 'symlink terminology cache')
        def cached():
            require(not cache.is_symlink(), 'symlink terminology cache')
            try:
                data = loads(cache.read_text())
                result = {**data['result'], 'term': term}
                validate_result(result, term)
                expires = data['expires_at']
                if result['status'] in {'unavailable', 'error'}:
                    # Honour the cooldown for caches written before it increased
                    # from one minute, without changing the original attribution.
                    expires = max(expires, datetime.fromisoformat(result['retrieved_at']).timestamp() + FAILURE_COOLDOWN)
                if expires > self.clock():
                    report['cache_hits'] += 1
                    return result
            except (OSError, ValueError, TypeError, KeyError): pass
        hit = cached()
        if hit is not None: return hit
        result = {'provider': self.provider.name, 'term': term, 'status': 'unavailable',
                  'reason': 'Terminology provider is busy.', 'retrieved_at': timestamp(self.clock()), 'concepts': []}
        lock_path = directory / (self.provider.name + '.lock')
        require(not lock_path.is_symlink() and not cache.is_symlink(), 'symlink terminology cache')
        with lock_path.open('a') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: return result
            # Another process may have filled the cache between the fast read
            # and acquisition of the provider lease.
            hit = cached()
            if hit is not None: return hit
            pacing = directory / (self.provider.name + '-pacing.json')
            require(not pacing.is_symlink(), 'symlink terminology pacing file')
            try: next_at = loads(pacing.read_text())['next_at']
            except FileNotFoundError: next_at = 0
            def get(url):
                nonlocal next_at
                if report['api_calls'] >= self.max_requests: raise BudgetExceeded('Per-R3 request budget exhausted.')
                delay = max(0, next_at-self.clock())
                if delay >= end-self.monotonic(): raise BudgetExceeded('Provider pacing/cooldown exceeds R3 deadline.')
                if delay: self.sleep(delay)
                remaining = end-self.monotonic()
                if remaining <= 0: raise BudgetExceeded('Per-R3 lookup deadline reached.')
                next_at = self.clock() + self.provider.interval
                atomic_text(pacing, dumps({'next_at': next_at}))
                report['api_calls'] += 1
                return self.transport(url, min(remaining, self.request_timeout))
            try:
                status, reason, concepts = self.provider.lookup(term, get)
                result.update(status=status, reason=reason, concepts=concepts)
                validate_result(result, term)
                for concept in concepts:
                    # Concept cache retains the validated identity/provenance, not
                    # a fuzzy alias shortcut. Different names still resolve identity.
                    concept_path = directory / (self.provider.name + '-' + concept['concept_id'] + '.json')
                    require(not concept_path.is_symlink(), 'symlink terminology concept cache')
                    try:
                        previous = validate_concept(loads(concept_path.read_text()))
                        contextual = {'matched_name', 'matched_term_ids', 'match_type', 'retrieved_at'}
                        if {k:v for k,v in previous.items() if k not in contextual} == {
                                k:v for k,v in concept.items() if k not in contextual}:
                            # Preserve the original retrieval attribution of an
                            # unchanged description; current outcome records when
                            # its identity was checked again for this exact name.
                            concept['retrieved_at'] = previous['retrieved_at']
                            report['concept_cache_hits'] += 1
                    except (OSError, ValueError, TypeError, KeyError): pass
                    atomic_text(concept_path, dumps(concept))
            except HTTPError as exc:
                with exc:
                    retry = exc.headers.get('Retry-After') if exc.headers else None
                delay = 60
                try: delay = max(1, int(retry))
                except (ValueError, TypeError):
                    try: delay = max(1, parsedate_to_datetime(retry).timestamp()-self.clock())
                    except (ValueError, TypeError, AttributeError): pass
                next_at = max(next_at, self.clock()+delay)
                atomic_text(pacing, dumps({'next_at': next_at}))
                result.update(status='unavailable', reason='HTTP ' + str(exc.code) + '; retry after provider cooldown.')
            except (TimeoutError, OSError) as exc:
                result.update(status='unavailable', reason=failure_reason(exc), concepts=[])
            except Exception as exc:
                result.update(status='error', reason=failure_reason(exc), concepts=[])
            result['retrieved_at'] = timestamp(self.clock())
            expires = self.clock() + (FAILURE_COOLDOWN if result['status'] in {'unavailable', 'error'} else RESULT_TTL)
            if result['status'] == 'unavailable': expires = max(expires, next_at)
            atomic_text(cache, dumps({'expires_at': expires, 'result': result}))
        return result
