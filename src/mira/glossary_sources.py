"""Reviewed extractive source admission, using the ordinary canonical journal.

The reviewer establishes concept identity and scientific applicability. These
checks establish traceability, not scientific certification. R3's independent
proposal validation is deliberately unchanged.
"""
from copy import deepcopy
from urllib.parse import urlsplit
import re
import uuid

from . import glossary, glossary_definitions as definitions
from .format import digest, dumps, loads, require
from .interactions import Interactions, now, read_records


def source_url(value):
    """A navigable HTTP(S) citation, never executable or credential-bearing."""
    if not isinstance(value, str) or re.search(r'[\s\\\x00-\x1f\x7f]', value): return ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            return ''
        parsed.port  # Reject malformed ports before emitting a browser link.
    except ValueError:
        return ''
    return value


def admit(store, term_id, source, *, passage, definition=None, qualification,
          reviewer, mapping_reason, aliases=(), relationships=(), node_id=None, log_dir=None, fault=None):
    """Add a reviewed literal definition fragment, including headed definitions.

    A source may define a concept under a heading, singular label or abbreviation
    rather than repeat the corpus's exact preferred plural label. Explicit review
    records that mapping without manufacturing a sentence or altering its words.
    Sources require their original document hash, retrieval time and full retained
    extracted text. Repeated admission is a no-op; changed source identities fail.
    """
    from datetime import datetime
    glossary.string(reviewer, 200); glossary.string(mapping_reason, 2000)
    glossary.string(passage, 1000); glossary.string(qualification, 500)
    require(isinstance(source, dict), 'invalid reviewed source')
    source = deepcopy(source)
    for key in ('id', 'title', 'url', 'retrieved_at', 'document_sha256', 'content'):
        require(isinstance(source.get(key), str) and source[key].strip(), 'missing source ' + key)
    require(bool(source_url(source['url'])), 'invalid source URL')
    require(re.fullmatch('[0-9a-f]{64}', source['document_sha256']), 'invalid original document hash')
    require(datetime.fromisoformat(source['retrieved_at']).tzinfo is not None, 'source retrieval time must have timezone')
    require(passage in source['content'], 'reviewed passage absent from retained source')
    if definition is not None:
        glossary.string(definition)
        require(definition in passage, 'reviewed definition must be an exact source extract')
    require(isinstance(aliases, (list, tuple)) and len(aliases) <= 8, 'invalid reviewed aliases')
    require(isinstance(relationships, (list, tuple)) and len(relationships) <= 8, 'invalid reviewed relationships')
    source['content_sha256'] = digest(source['content'])
    trace = Interactions(store)
    with trace.execution(log_dir, command='glossary-source-review'), store.lock():
        token, docs, eqs, ledger = store.read()
        require(not any('outcome' not in row for row in read_records(store.root)),
                'Unresolved submission; inspect transcript before source review.')
        state = loads(store.path('research/state.json').read_text(encoding='utf-8'))
        directory = glossary.Directory(store)
        records = directory.all(state)
        by_id = {r['id']: r for r in records}
        require(term_id in by_id, 'unknown reviewed glossary identity')
        record = by_id[term_id]
        node_id = node_id or record['node_ids'][0]
        require(node_id in state['nodes'], 'unknown source scope node')
        # A source identifier cannot silently acquire a different URL or text.
        references = {e['evidence_ref'] for r in records for e in r['evidence'] if e['source_id'] == source['id']}
        reference = None
        for ref in sorted(references):
            require(re.fullmatch(r'research/results/[A-Za-z0-9_-]+\.json', ref), 'unsafe retained source reference')
            retained = loads(store.path(ref).read_text(encoding='utf-8'))
            matches = [old for old in retained.get('results', []) if old.get('id') == source['id']]
            require(len(matches) == 1, 'retained reference has missing or duplicate source identity')
            for old in matches:
                require(all(old.get(k) == source[k] for k in ('url', 'content_sha256', 'document_sha256')),
                        'source identifier already has different content or URL; use an explicit source version')
                reference = ref
        reference = reference or 'research/results/glossary_source_' + uuid.uuid4().hex + '.json'
        support = dict(source_id=source['id'], passage=passage, evidence_ref=reference,
                       node_id=node_id, qualification=qualification)
        previous = dumps(record)
        for alias in aliases:
            glossary.string(alias, 160)
            require(glossary.alias_supported(record['term'], alias, passage), 'alias lacks explicit naming evidence')
            if not any(glossary.normalize(alias) == glossary.normalize(n) for n in [record['term'], *record['aliases']]):
                record['aliases'].append(alias)
        for relation in relationships:
            require(isinstance(relation, dict) and set(relation) == {'target', 'type'}, 'invalid reviewed relationship')
            target = by_id.get(relation['target'])
            require(target is not None and target['id'] != term_id and relation['type'] in glossary.RELATIONS,
                    'invalid reviewed relationship target/type')
            require(glossary.relationship_supported(record['term'], target['term'], relation['type'], passage),
                    'relationship lacks explicit source support')
            link = {**relation, 'evidence': support}
            if link not in record['relationships']: record['relationships'].append(link)
        if support not in record['evidence']: record['evidence'].append(support)
        if node_id not in record['node_ids']: record['node_ids'].append(node_id)
        if definition is not None:
            row = dict(text=definition, qualification=qualification, evidence=support)
            if row not in record['definitions']: record['definitions'].append(row)
        record['status'] = definitions.status(record['definitions'], record.get('definition_reviews', []))
        glossary.validate_record(record)
        if dumps(record) == previous:
            return {'changed': False, 'term_id': term_id, 'source_ref': reference}
        if definition is not None:
            from .glossary_enrichment import input_hash
            record.setdefault('enrichment', []).append(dict(status='complete', updated_at=now(),
                input_sha256=input_hash(record, state, by_id),
                reason='Reviewed exact source definition admitted; no model generation or scientific certification.',
                retry_after=None, interaction_id=None))
            glossary.validate_record(record)
        files = {'glossary/' + term_id + '.json': dumps(record)}
        meta = deepcopy(glossary.metadata(state)); meta['revision'] += 1
        meta['commitment'] = glossary.commitment(meta['commitment'], files); state['glossary'] = meta
        event = dict(event_id=uuid.uuid4().hex, timestamp=now(), status='committed',
                     action_committed='glossary-source-review', term_id=term_id,
                     source_ref=reference, source_id=source['id'], reviewer=reviewer,
                     mapping_reason=mapping_reason, definition=definition,
                     classification='exact_source_extract' if definition is not None else 'context_only')
        files.update({'research/state.json': dumps(state), 'events/' + event['event_id'] + '.json': dumps(event)})
        if not references:
            files[reference] = dumps(dict(status='ok', reference=reference, timestamp=now(),
                query_submitted=False, purpose='glossary_definition_source', results=[source]))
        store.publish(docs, eqs, ledger, token, files=files, operation_type='glossary-source-review',
                      context={'timestamp': event['timestamp'], 'term_id': term_id}, fault=fault)
        trace.record('glossary_source_review', event)
        return {'changed': True, 'term_id': term_id, 'source_ref': reference, 'event_id': event['event_id']}
