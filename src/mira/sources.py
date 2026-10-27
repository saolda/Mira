"""Conservative publication identity and disposable, hash-checked retrieval inputs."""
from copy import deepcopy
import re
import unicodedata
from urllib.parse import unquote

from .format import digest, dumps, loads, require
from .store import durable_write, sync_dir


def normalized(value):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', str(value)).casefold()))


def descriptor(row):
    return {k: deepcopy(row[k]) for k in ('id','title','authors','url','doi','pmid','pmcid','arxiv_id','identifiers','published','year','content_kind','truncated') if k in row}


def identity(row):
    ids = dict(row.get('identifiers') or {})
    for k in ('doi','pmid','pmcid','arxiv_id'):
        if row.get(k): ids[k] = row[k]
    values = [str(row.get(k, '')) for k in ('id','url')]
    for value in values:
        if value.lower().startswith('doi:'): ids.setdefault('doi', value[4:])
        if value.lower().startswith('pmid:'): ids.setdefault('pmid', value[5:])
        if value.lower().startswith('arxiv:'): ids.setdefault('arxiv_id', value[6:])
        if re.search(r'(?:dx\.)?doi\.org/', value, re.I): ids.setdefault('doi', re.split(r'doi\.org/', value, flags=re.I)[-1])
        match = re.search(r'(?:arxiv\.org/(?:abs|pdf)/)([^?#]+)', value, re.I)
        if match: ids.setdefault('arxiv_id', match[1].removesuffix('.pdf'))
        match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', value)
        if match: ids.setdefault('pmid', match[1])
    clean = {}
    for key, value in ids.items():
        if not isinstance(value, (str, int)) or not str(value).strip(): continue
        value = unquote(str(value)).strip()
        if key == 'doi':
            value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value, flags=re.I).lower()
            if not re.fullmatch(r'10\.\d{4,9}/\S+', value): continue
        if key == 'pmid':
            value = value.rstrip('/').split('/')[-1]
            if not value.isdigit(): continue
        if key == 'pmcid': value = value.upper()
        if key == 'arxiv_id': value = value.lower()  # Keep explicit versions distinct.
        clean[key] = value
    # Exact normalized source URLs also cover nonscholarly sources, e.g. Wikipedia.
    clean['source'] = str(row['id']).rstrip('/')
    title = normalized(row.get('title', ''))
    authors = sorted(normalized(a) for a in row.get('authors', []) if normalized(a))
    fingerprint = digest(dumps([title, authors])) if len(title) >= 35 and len(title.split()) >= 5 and authors else None
    year = str(row.get('year') or row.get('published') or '')[:4]
    return {'identifiers': clean, 'aliases': [k+':'+v for k,v in clean.items()], 'fingerprint': fingerprint, 'year': year, 'source': descriptor(row)}


def same(a, b):
    left, right = a['identifiers'], b['identifiers']
    # Conflicting identifiers (including explicitly different arXiv versions) are
    # retained even when titles/authors match. No fuzzy title/initial matching.
    for key in ('doi','pmid','pmcid','arxiv_id'):
        if key in left and key in right and left[key] != right[key]: return False
    if any(key in right and right[key] == value for key, value in left.items()): return True
    if set(a.get('aliases', [])) & set(b.get('aliases', [])): return True
    if a['year'] and b['year'] and a['year'] != b['year']: return False
    return bool(a['fingerprint'] and a['fingerprint'] == b['fingerprint'])


def unique(rows, index):
    accepted, duplicates, seen = [], [], list(index.values())
    for row in rows:
        current = identity(row)
        prior = next((item for item in seen if same(current, item)), None)
        if prior is None:
            accepted.append(row); seen.append(current)
        else:
            duplicates.append(descriptor(row))
    return accepted, duplicates


def processed(index, rows, evidence_ref):
    for row in rows:
        current = identity(row)
        prior = next((item for item in index.values() if same(current, item)), None)
        if prior is None:
            current['evidence_ref'] = evidence_ref
            index[digest(dumps(current['identifiers']))] = current
        else:
            prior['identifiers'].update({k:v for k,v in current['identifiers'].items() if k != 'source'})
            prior['aliases'] = list(dict.fromkeys(prior.get('aliases', []) + current['aliases']))


def reconcile(index, rows):
    """Add defensible aliases to known records, without marking new works processed."""
    for row in rows:
        current = identity(row)
        if any(same(current, prior) for prior in index.values()):
            processed(index, [row], "")


def save_payload(store, identity, rows):
    relative = 'retrieved/' + identity + '.json'
    directory = store.path('retrieved'); directory.mkdir(exist_ok=True); sync_dir(directory.parent)
    text = dumps({'results': rows})
    durable_write(store.path(relative), text); sync_dir(directory)
    return {'payload_ref': relative, 'payload_sha256': digest(text)}


def hydrate(store, evidence):
    if 'payload_ref' not in evidence: return deepcopy(evidence)  # Existing canonical evidence.
    relative = evidence['payload_ref']
    require(isinstance(relative, str) and re.fullmatch(r'retrieved/[0-9a-f]{32}\.json', relative), 'invalid retrieved payload path')
    path = store.path(relative)
    require(path.is_file(), 'pending retrieval payload missing: ' + relative)
    raw = path.read_text()
    require(digest(raw) == evidence['payload_sha256'], 'retrieved payload digest mismatch')
    rows = loads(raw)['results']
    require([descriptor(row) for row in rows] == evidence['results'], 'retrieval metadata mismatch')
    return {**evidence, 'results': rows}


def prune(store, *, apply=False):
    """Only known completed payloads; pending work and ambiguous orphans survive."""
    with store.lock():
        store.read()  # Recovery gate must pass before touching any cache.
        files = store._files()
        state = loads(files['research/state.json'])
        protected = {ref for n in state['nodes'].values() for ref in
                     (n.get('pending_results'), n.get('legacy_pending_results')) if ref}
        candidates, retained = [], []
        for path, raw in files.items():
            if not path.startswith('research/results/'): continue
            evidence = loads(raw)
            if 'payload_ref' not in evidence: continue
            relative = evidence['payload_ref']
            require(re.fullmatch(r'retrieved/[0-9a-f]{32}\.json', relative), 'invalid payload path')
            if path in protected:
                retained.append(relative); continue
            payload = store.path(relative)
            if payload.is_file():
                require(digest(payload.read_text()) == evidence['payload_sha256'], 'changed retrieval cache; refusing prune')
                candidates.append(relative)
        if apply:
            for relative in candidates: store.path(relative).unlink()
            if candidates: sync_dir(store.path('retrieved'))
        return {'apply': apply, 'discardable': candidates, 'protected': retained, 'removed': candidates if apply else []}
