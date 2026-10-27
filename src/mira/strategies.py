"""Load and validate predefined database sequences; selection is experiment-wide."""
import os
from pathlib import Path
import re

from .format import loads, require

PROVIDERS = ('wikipedia', 'arxiv', 'pubmed', 'crossref', 'europe_pmc', 'eric', 'openalex')


def registry(path=None):
    path = path or os.environ.get('MIRA_RESEARCH_STRATEGIES') or Path(__file__).with_name('strategies.json')
    values = loads(Path(path).read_text())
    require(isinstance(values, list) and values, 'nonempty strategy registry required')
    seen = set()
    for s in values:
        require(isinstance(s, dict) and set(s) == {'id','name','description','databases'}, 'invalid strategy fields')
        require(isinstance(s['id'], str) and re.fullmatch(r'[a-z][a-z0-9_-]*', s['id']) and s['id'] not in seen, 'invalid/duplicate strategy ID')
        seen.add(s['id'])
        require(all(isinstance(s[k], str) and s[k].strip() for k in ('name','description')), 'strategy name/description required')
        dbs = s['databases']
        require(isinstance(dbs, list) and dbs and all(isinstance(d, str) and d in PROVIDERS for d in dbs) and len(set(dbs)) == len(dbs), 'unknown/duplicate strategy databases')
    return values


def select(values, identity):
    require(isinstance(identity, str), 'strategy ID must be text')
    chosen = next((s for s in values if s['id'] == identity), None)
    require(chosen is not None, 'unknown strategy: ' + identity)
    return chosen
