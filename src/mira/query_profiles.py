"""Versioned query compilers and immutable experiment configuration snapshots."""
from copy import deepcopy
import math
import os
from pathlib import Path
import re

from .format import loads, require

PROVIDERS = ('wikipedia', 'arxiv', 'pubmed', 'crossref', 'europe_pmc', 'eric', 'openalex')
HOSTS = dict(zip(PROVIDERS, ('en.wikipedia.org', 'export.arxiv.org', 'eutils.ncbi.nlm.nih.gov',
    'api.crossref.org', 'www.ebi.ac.uk', 'api.ies.ed.gov', 'api.openalex.org')))
QUERY_PARAMETERS = dict(zip(PROVIDERS, ('gsrsearch', 'search_query', 'term', 'query.bibliographic', 'query', 'search', 'search')))
RULES = {
    'legacy': ('provider_legacy', 'provider_legacy', 'provider_legacy'),
    'pubmed': ('AND', 'unquoted_atm', 'literal_words'),
    'pubmed_or': ('OR', 'unquoted_atm', 'literal_words'),
    'phrase_and': ('AND', 'phrase', 'backslash'),
    'phrase_or': ('OR', 'phrase', 'backslash'),
    'text': ('spaces', 'none', 'literal_words'),
    'arxiv': ('AND', 'all_field_phrase', 'backslash'),
}
# OR compilers are available only through explicitly supplied profiles; the
# shipped registry continues to select the existing production compilers.
COMPATIBLE = {'legacy': set(PROVIDERS), 'pubmed': {'pubmed'}, 'pubmed_or': {'pubmed'},
    'phrase_and': {'europe_pmc', 'eric'}, 'phrase_or': {'europe_pmc', 'eric'},
    'text': {'wikipedia', 'crossref', 'openalex'}, 'arxiv': {'arxiv'}}


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate(profile):
    require(isinstance(profile, dict) and set(profile) == {'id', 'version', 'providers', 'compiler',
        'combination', 'quoting', 'escaping', 'max_terms', 'min_interval_seconds', 'retry_initial_seconds',
        'retry_max_seconds', 'max_attempts'}, 'invalid query-profile fields')
    require(isinstance(profile['id'], str) and re.fullmatch(r'[a-z][a-z0-9_-]*', profile['id']), 'invalid profile ID')
    require(type(profile['version']) is int and profile['version'] > 0, 'invalid profile version')
    require(isinstance(profile['compiler'], str) and profile['compiler'] in RULES, 'unknown query compiler')
    require(tuple(profile[k] for k in ('combination', 'quoting', 'escaping')) == RULES[profile['compiler']], 'invalid compiler rules')
    providers = profile['providers']
    require(isinstance(providers, list) and providers and all(isinstance(p, str) and p in COMPATIBLE[profile['compiler']] for p in providers)
        and len(providers) == len(set(providers)), 'incompatible/duplicate profile providers')
    require(type(profile['max_terms']) is int and 1 <= profile['max_terms'] <= 6, 'invalid max_terms')
    require(type(profile['max_attempts']) is int and profile['max_attempts'] > 0, 'invalid max_attempts')
    require(all(number(profile[k]) for k in ('min_interval_seconds', 'retry_initial_seconds', 'retry_max_seconds'))
        and 0 < profile['retry_initial_seconds'] <= profile['retry_max_seconds'], 'invalid profile timing')
    return profile


def registry(path=None):
    path = path or os.environ.get('MIRA_QUERY_PROFILES') or Path(__file__).with_name('query_profiles.json')
    data = loads(Path(path).read_text())
    require(isinstance(data, dict) and set(data) == {'profiles', 'host_min_intervals'}, 'invalid profile registry')
    require(isinstance(data['profiles'], list) and data['profiles'], 'nonempty profiles required')
    seen = set()
    for profile in data['profiles']:
        validate(profile)
        require(profile['id'] not in seen, 'duplicate profile ID')
        seen.add(profile['id'])
    require('default' in seen, 'default profile required')
    hosts = data['host_min_intervals']
    require(isinstance(hosts, dict) and all(isinstance(h, str) and h and '/' not in h and number(v) for h, v in hosts.items()), 'invalid host request intervals')
    default = select(data, 'default')
    require(set(default['providers']) == set(PROVIDERS) and default['compiler'] == 'legacy', 'default must support all providers with legacy semantics')
    return data


def select(data, identity, provider=None):
    profile = next((p for p in data['profiles'] if p['id'] == identity), None)
    require(profile is not None, 'unknown query profile: ' + str(identity))
    if provider is not None:
        # Explicit custom adapters retain the existing public initialization API.
        require(provider in profile['providers'] or provider not in PROVIDERS and identity == 'default', 'profile incompatible with provider: ' + provider)
    return profile


def snapshot(strategy, data):
    result = deepcopy(strategy)
    require(set(result['profiles']) == set(result['databases']), 'every strategy provider requires a profile')
    result['query_profiles'] = {p: deepcopy(select(data, result['profiles'][p], p)) for p in result['databases']}
    result['host_min_intervals'] = deepcopy(data['host_min_intervals'])
    return result


def legacy_query(provider, concepts):
    require(isinstance(concepts, list) and concepts and all(isinstance(c, str) and c.strip() for c in concepts), 'search concepts required')
    if provider != 'arxiv': return ' '.join(concepts)
    if len(concepts) == 1 and re.fullmatch(r'id:(?:[a-zA-Z.-]+/)?[0-9]+(?:\.[0-9]+)?(?:v[0-9]+)?', concepts[0]):
        return concepts[0]
    words = list(dict.fromkeys(w for c in concepts for w in re.findall(r'[\w-]+', c)))
    require(words, 'arXiv query has no searchable words')
    return ' AND '.join('all:"' + w + '"' for w in words)


def compile(provider, concepts, profile, *, legacy=False):
    validate(profile)
    require(provider in profile['providers'] or provider not in PROVIDERS and profile['id'] == 'default', 'incompatible profile')
    require(isinstance(concepts, list) and concepts and all(isinstance(c, str) and c.strip() for c in concepts), 'search concepts required')
    retained = concepts if legacy else concepts[:profile['max_terms']]
    def phrase(c): return '"' + c.replace('\\', '\\\\').replace('"', '\\"') + '"'
    def words(c): return ' '.join(re.findall(r'[\w+.,/−-]+', c))
    compiler = profile['compiler']
    if compiler == 'legacy': query = legacy_query(provider, retained)
    elif compiler in {'pubmed', 'pubmed_or'}:
        query = (' ' + profile['combination'] + ' ').join('(' + words(c) + ')' for c in retained)
    elif compiler in {'phrase_and', 'phrase_or'}:
        query = (' ' + profile['combination'] + ' ').join(phrase(c) for c in retained)
    elif compiler == 'arxiv': query = ' AND '.join('all:' + phrase(c) for c in retained)
    else: query = ' '.join(words(c) for c in retained)
    require(query.strip(), 'empty compiled query')
    return {'original_concepts': list(concepts), 'retained_concepts': list(retained),
        'discarded_concepts': [] if legacy else concepts[profile['max_terms']:], 'provider': provider,
        'profile_id': None if legacy else profile['id'], 'profile_version': None if legacy else profile['version'],
        'profile_config': deepcopy(profile), 'legacy_query_semantics': legacy,
        'query': query, 'request_parameters': {QUERY_PARAMETERS.get(provider, 'query'): query}}
