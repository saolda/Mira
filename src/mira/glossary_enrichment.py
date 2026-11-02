"""Resumable glossary maintenance, independent of research scheduling.

Canonical records and immutable events are the progress authority. Received
responses can be replayed without generation; uncertain submissions cannot.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path
import re
import time
import uuid

from . import glossary, glossary_definitions as definitions, terminology
from .decisions import proposal
from .format import digest, dumps, loads, require
from .interactions import Interactions, now, read_records



PROGRESS_FIELDS = {'status', 'updated_at', 'input_sha256', 'reason', 'retry_after', 'interaction_id'}
STATUSES = {'complete', 'clarification', 'failed', 'pending', 'uncertain', 'approval_required', 'invalidated'}


def g1_prompt(data):
    from .prompts import PromptTemplates
    return PromptTemplates().render('G1', {'entries': data})


def validate_progress(rows):
    require(isinstance(rows, list), 'invalid enrichment history')
    for row in rows:
        require(isinstance(row, dict) and set(row) == PROGRESS_FIELDS and row['status'] in STATUSES,
                'invalid enrichment progress')
        for field in ('updated_at', 'retry_after'):
            require(field == 'retry_after' and row[field] is None or
                    isinstance(row[field], str) and datetime.fromisoformat(row[field]).tzinfo is not None,
                    'invalid enrichment timestamp')
        require(isinstance(row['input_sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['input_sha256']),
                'invalid enrichment input hash')
        definitions.text(row['reason'], 2000)
        require(row['interaction_id'] is None or isinstance(row['interaction_id'], str) and
                re.fullmatch(r'[0-9]{8,}-[0-9a-f]{32}', row['interaction_id']), 'invalid enrichment interaction')


def scope(record, state):
    # A currently selected child question must not obscure another term's scope.
    node_id = record['node_ids'][0]
    return definitions.context(state['nodes'][node_id]['question'], node_id, record['node_ids'])


def context(record, state, by_id):
    return {'term_id': record['id'], 'term': record['term'], 'aliases': record['aliases'][:16],
        'research_context': scope(record, state),
        'passages': record['evidence'][:3],
        'related_terms': [{'term': by_id[r['target']]['term'], 'relationship': r['type']}
                          for r in record['relationships'][:8]],
        'context_is_bounded': True}


def input_hash(record, state, by_id):
    # Detect new research context even beyond the bounded model projection.
    return digest(dumps({'term': record['term'], 'aliases': record['aliases'],
        'evidence': record['evidence'], 'relationships': record['relationships'],
        'definition_reviews': record.get('definition_reviews', []),
        'questions': [state['nodes'][i]['question'] for i in record['node_ids']],
        'related_terms': [by_id[r['target']]['term'] for r in record['relationships']]}))


def coverage(records, state=None):
    counts = dict(total=len(records), authoritative=0, research_source=0, provisional_only=0,
                  requiring_clarification=0, without_usable_definitions=0, defined=0)
    unresolved = []
    for record in records:
        rows = definitions.preferred(record, scope(record, state) if state else None)
        authority = any('authority' in d for d in rows)
        research = any(not definitions.provisional(d) and 'authority' not in d for d in rows)
        counts['authoritative'] += authority
        counts['research_source'] += research
        counts['provisional_only'] += bool(rows) and not (authority or research)
        last = record.get('enrichment', [{}])[-1]
        clarification = last.get('status') == 'clarification' and not rows
        counts['requiring_clarification'] += clarification
        counts['without_usable_definitions'] += not bool(rows)
        counts['defined'] += bool(rows)
        if not rows:
            unresolved.append({'id': record['id'], 'term': record['term'],
                'status': last.get('status', 'outstanding'),
                'reason': last.get('reason', 'No applicable attributed definition.'),
                'retry_after': last.get('retry_after')})
    return {**counts, 'category_note': 'Authoritative and research-source counts may overlap; provisional-only is exclusive. Clarification is a subset of without usable definitions.',
            'unresolved': unresolved}


def validate_generated(value, record, research_scope=None):
    require(isinstance(value, dict) and set(value) == {'term_id', 'status', 'definitions', 'reason'} and
            value['term_id'] == record['id'] and value['status'] in {'defined', 'ambiguous'},
            'invalid definition entry identity/status')
    definitions.text(value['reason'], 1000)
    rows = value['definitions']
    require(isinstance(rows, list) and len(rows) <= 3, 'invalid definition batch')
    require(bool(rows) == (value['status'] == 'defined'), 'inconsistent definition/ambiguity status')
    # An unexpanded bare abbreviation cannot acquire an invented expansion from
    # general model knowledge. Expanded canonical labels are not affected.
    if rows and re.fullmatch(r'[A-Z][A-Z0-9-]{1,11}', record['term']) and not record['aliases']:
        require(False, 'Bare abbreviation lacks a source-supported expansion; clarification required.')
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'definition', 'scope', 'ambiguity'}, 'invalid definition fields')
        definitions.text(row['definition'], 600); definitions.text(row['scope'], 160)
        definitions.text(row['ambiguity'], 400, empty=True)
        text = row['definition']; normalized = definitions.normalize(text)
        require(not re.search(r'https?://|\b(?:PMID|doi)\s*:|\b10\.\d{4,9}/', text, re.I),
                'Generated definitions must not invent citations.')
        meaningful = definitions.words(text) - definitions.words(record['term'])
        require(len(meaningful) >= 3 and len(text.split()) >= 6, 'Definition is circular or lacks scientific content.')
        require(not re.search(r'\b(?:important (?:scientific )?(?:term|concept)|refers to itself|various scientific contexts)\b', text, re.I),
                'Generic filler is not a definition.')
        require(normalized not in seen, 'Duplicate generated meanings.')
        seen.add(normalized)
        # Contextual plausibility is deliberately conservative, not verification.
        grounding = ' '.join([record['term'], *record['aliases'], *[e['passage'] for e in record['evidence']]])
        if research_scope: grounding += ' ' + research_scope['question']
        require(bool(definitions.words(text + ' ' + row['scope']) & definitions.words(grounding)),
                'Definition has no scientific vocabulary in common with the supplied context.')
        require(not (re.search(r'\d+(?:\.\d+)?\s*%', text) and
                     re.search(r'\b(?:more frequent|less frequent|patients|cohort)\b', text, re.I)),
                'Cohort frequencies are empirical findings, not a terminology definition.')
        names = definitions.normalize(' '.join([record['term'], *record['aliases']]))
        if 'doubling' in names and ('volume' in names or 'diameter' in names):
            require(not re.search(r'(?:volume.{0,25}(?:equals|equal to|same as|equivalent to).{0,25}diameter|diameter.{0,25}(?:equals|equal to|same as|equivalent to).{0,25}volume)', text, re.I),
                    'Volume and diameter doubling are distinct quantities.')
    return value


def model_identity(model):
    props = getattr(model, 'properties', {})
    path = props.get('model_path', model.model)
    result = {'served_model': model.model, 'server_model_path': path,
              'properties_sha256': digest(dumps(props))}
    # Hash a locally served artifact when it is accessible; never assert that a
    # same-named local file proves the identity of an arbitrary remote service.
    from urllib.parse import urlsplit
    if urlsplit(getattr(model, 'server', '')).hostname in {'localhost', '127.0.0.1', '::1'} and Path(path).is_file():
        with Path(path).open('rb') as stream: result['artifact_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return result


class Completion:
    def __init__(self, store, *, model_factory=None, prompt_factory=g1_prompt, authority=None, log_dir=None, clock=time.time):
        self.store, self.directory = store, glossary.Directory(store)
        self.model_factory, self.authority, self.log_dir, self.clock = model_factory, authority, log_dir, clock
        # All production instruction text comes from the approved G1 file.
        self.prompt_factory = prompt_factory
        self.trace = Interactions(store)
        self.model = self.identity = None
        self.model_error = None

    def _state(self):
        return loads(self.store.path('research/state.json').read_text(encoding='utf-8'))

    def inspect(self):
        with self.store.lock():
            self.store.read(); state = self._state()
            records = self.directory.all(state)
            return {'root': str(self.store.root), 'revision': glossary.metadata(state)['revision'],
                    **coverage(records, state)}

    def reject_definitions(self, rejections, *, reviewer):
        """Explicit scientific review; preserve original generated text/receipt."""
        with self.trace.execution(self.log_dir, command='glossary-definition-review'), self.store.lock():
            self.store.read(); state = self._state(); records = self.directory.all(state)
            by_id = {r['id']: r for r in records}; changed = []
            for identity, rejection in rejections.items():
                require(identity in by_id, 'Unknown reviewed term')
                record = by_id[identity]; sha = rejection['definition_sha256']
                require(any(digest(dumps(d)) == sha for d in record['definitions']), 'Unknown reviewed definition')
                if any(r['definition_sha256'] == sha for r in record.get('definition_reviews', [])): continue
                record.setdefault('definition_reviews', []).append({'definition_sha256': sha,
                    'reason': rejection['reason'], 'reviewer': reviewer, 'reviewed_at': now()})
                self._progress(record, state, by_id, 'invalidated', rejection['reason'])
                changed.append(record)
            self._save(changed, {'event_id': uuid.uuid4().hex, 'action_committed': 'glossary-definition-review'})
            return coverage(records, state)

    def _save(self, records, event, *, fault=None):
        token, docs, eqs, ledger = self.store.read(); state = self._state()
        files = {}
        for record in records:
            record['status'] = definitions.status(record['definitions'], record.get('definition_reviews', []))
            glossary.validate_record(record)
            path = 'glossary/' + record['id'] + '.json'; raw = dumps(record)
            if self.store.path(path).read_text(encoding='utf-8') != raw: files[path] = raw
        if not files: return
        meta = deepcopy(glossary.metadata(state)); meta['revision'] += 1
        meta['commitment'] = glossary.commitment(meta['commitment'], files); state['glossary'] = meta
        event = {'timestamp': now(), 'status': 'committed', **event}
        files.update({'research/state.json': dumps(state), 'events/' + event['event_id'] + '.json': dumps(event)})
        self.store.publish(docs, eqs, ledger, token, files=files, operation_type='glossary-enrich',
                           context={'timestamp': event['timestamp'], 'term_ids': [r['id'] for r in records]}, fault=fault)
        self.trace.record('glossary_enrichment_commit', event)

    def _progress(self, record, state, by_id, status, reason, interaction=None):
        record.setdefault('enrichment', []).append({'status': status, 'updated_at': now(),
            'input_sha256': input_hash(record, state, by_id), 'reason': reason[:2000],
            'retry_after': terminology.timestamp(self.clock() + terminology.FAILURE_COOLDOWN) if status == 'failed' else None,
            'interaction_id': interaction})

    def _prepare_term(self, record, state, by_id, stats, upgrade):
        current = scope(record, state)
        if self.authority is not None and (not definitions.preferred(record, current) or upgrade) and terminology.lookup_due(record, self.clock()):
            try:
                outcomes, report = self.authority.enrich([record])
                stats['authoritative_api_calls'] += report.get('api_calls', 0)
                stats['authoritative_lookups'] += len(outcomes)
                outcome = outcomes.get(record['id'])
                if outcome:
                    terminology.validate_result(outcome, record['term'])
                    if outcome not in record.setdefault('terminology', []): record['terminology'].append(outcome)
                    if outcome['status'] == 'matched':
                        authority = outcome['concepts'][0]
                        for description in authority['descriptions']:
                            row = {**description, 'authority': authority}
                            if definitions.applicable(row, record, current) and not any(
                                d.get('authority', {}).get('concept_id') == authority['concept_id'] and
                                d['text'] == row['text'] for d in record['definitions']):
                                record['definitions'].append(row); stats['authoritative_definitions'] += 1
                        if any(d.get('authority', {}).get('concept_id') == authority['concept_id'] for d in record['definitions']):
                            for alias in [authority['preferred_name'], *authority['aliases']]:
                                if len(alias) <= 160 and not any(glossary.normalize(alias) == glossary.normalize(n)
                                        for n in [record['term'], *record['aliases']]): record['aliases'].append(alias)
            except Exception as exc:
                reason = terminology.failure_reason(exc)
                stats['errors'].append({'id': record['id'], 'phase': 'authority', 'reason': reason})
                record.setdefault('terminology', []).append({'provider': 'mesh', 'term': record['term'],
                    'status': 'error', 'reason': reason, 'retrieved_at': terminology.timestamp(self.clock()), 'concepts': []})
        # Only explicit source naming/definition statements are harvested. Mere
        # occurrence, diagnostic association and research results are not definitions.
        if not definitions.preferred(record, current):
            cue = r'(?<!\w)' + re.escape(record['term']) + r'\s+(?:is defined as|are defined as|refers to|means|denotes)\s+'
            for evidence in record['evidence']:
                for sentence in re.split(r'(?<=[.!?])\s+', evidence['passage']):
                    if re.search(cue, sentence, re.I) and len(sentence) <= 1000:
                        row = {'text': sentence, 'qualification': evidence['qualification'], 'evidence': evidence}
                        if row not in record['definitions']:
                            record['definitions'].append(row); stats['research_definitions'] += 1
        return bool(definitions.preferred(record, current))

    def _get_model(self):
        if self.model_error: raise RuntimeError(self.model_error)
        if self.model is None:
            try:
                require(self.model_factory is not None, 'Local model is disabled or unavailable.')
                self.model = self.model_factory()
                self.identity = model_identity(self.model)
            except Exception as exc:
                self.model_error = terminology.failure_reason(exc)
                raise
        return self.model

    def _request(self, batch, state, by_id):
        if self.prompt_factory is None:
            raise ValueError('Glossary model generation is explicitly disabled.')
        model = self._get_model()
        data = [context(r, state, by_id) for r in batch]
        # Original occurrence excerpts can contain only cohort statistics. Add a
        # bounded, verbatim window from the retained source and its title so a
        # definition is grounded in the document's actual scientific subject.
        for entry, record in zip(data, batch):
            source_context = []
            for evidence in record['evidence'][:3]:
                ref = evidence['evidence_ref']
                if not re.fullmatch(r'research/results/[A-Za-z0-9_-]+\.json', ref): continue
                path = self.store.path(ref)
                if not path.is_file(): continue
                retained = loads(path.read_text(encoding='utf-8'))
                if retained.get('payload_ref'):
                    # Payloads carry source text; canonical result rows are only
                    # descriptors. Use the existing hash/metadata-validated path.
                    payload = self.store.path(retained['payload_ref'])
                    if payload.exists():
                        from .sources import hydrate
                        retained = hydrate(self.store, retained)
                for source in retained.get('results', []):
                    if source.get('id') != evidence['source_id']: continue
                    content = source.get('content', '')
                    if not isinstance(content, str): continue
                    at = content.casefold().find(record['term'].casefold())
                    start = max(0, at-300) if at >= 0 else 0
                    source_context.append({'source_id': source['id'], 'reference': ref,
                        'title': source.get('title', '')[:300], 'verbatim_excerpt': content[start:start+1800]})
            if source_context: entry['retained_source_context'] = source_context
        messages, template = self.prompt_factory(data)
        unredacted = dumps({'model': model.model, **model.settings, 'messages': messages})
        request = self.trace.clean(unredacted)
        template = deepcopy(template)
        template.update(serialized_request_sha256=digest(request), redaction_applied=request != unredacted,
                        filled_messages=loads(request)['messages'])
        if hasattr(model, 'count_tokens'):
            usage = model.count_tokens(request)
        else:
            usage = {'prompt_tokens': len(request.encode('utf-8')), 'context_window': 24000,
                     'estimator': 'conservative UTF-8 byte bound'}
        require(usage['prompt_tokens'] + model.settings['max_tokens'] <= usage['context_window'],
                'Glossary definition batch exceeds the model context window.')
        return request, data, usage, template

    def _finish(self, batch, state, by_id, interaction, request_record, response, stats, fault=None, *, write_outcome=True):
        event_id = uuid.uuid4().hex
        generated = {}; errors = []; values = {}
        try:
            result, info = proposal(response['raw'])
            require(info['model'] == request_record['request']['model'], 'Response model identity changed.')
            require(isinstance(result, dict) and set(result) == {'entries'} and isinstance(result['entries'], list), 'Invalid glossary completion envelope.')
            ids = [v.get('term_id') if isinstance(v, dict) else None for v in result['entries']]
            expected = {r['term_id'] for r in request_record['context']['entries']}
            require(len(ids) == len(set(ids)) and set(ids) == expected, 'Missing, extra or duplicate definition identities.')
            values = {v['term_id']: v for v in result['entries']}
            stats['usage'].append(info.get('usage'))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append({'phase': 'response', 'reason': str(exc)})
        contexts = request_record['context']['scopes']
        for record in batch:
            try:
                require(record['id'] in values, errors[0]['reason'] if errors else 'Missing definition response.')
                value = validate_generated(values[record['id']], record, scope(record, state))
                if value['status'] == 'ambiguous':
                    self._progress(record, state, by_id, 'clarification', value['reason'], interaction)
                    continue
                added = []
                for row in value['definitions']:
                    definition = {'origin': 'llm_generated', 'verification': 'provisional', 'term_id': record['id'],
                        'text': row['definition'], 'scope': row['scope'], 'ambiguity': row['ambiguity'],
                        'model': request_record['request']['model'],
                        'model_identity': request_record['context']['model_identity'], 'generated_at': response['timestamp'],
                        'interaction_ref': 'interactions/' + interaction + '/request.json', 'event_ref': 'events/' + event_id + '.json',
                        'template_sha256': request_record['prompt_template']['files'][0]['sha256'],
                        'request_sha256': digest(request_record['serialized_request']),
                        'context': contexts[record['id']]}
                    definitions.validate(definition, record['id'])
                    if not any(definitions.normalize(d['text']) == definitions.normalize(definition['text']) and
                               d.get('scope', '') == definition['scope'] for d in record['definitions']):
                        record['definitions'].append(definition); added.append(definition)
                generated[record['id']] = added
                stats['model_generated_definitions'] += len(added)
                require(definitions.preferred(record, scope(record, state)), 'Generated definition is not applicable to its research context.')
                self._progress(record, state, by_id, 'complete', value['reason'], interaction)
            except (ValueError, TypeError, KeyError) as exc:
                # Per-entry structural failures never corrupt independently valid entries.
                message = str(exc); errors.append({'id': record['id'], 'phase': 'quality', 'reason': message})
                status = 'clarification' if 'abbreviation' in message.lower() else 'failed'
                self._progress(record, state, by_id, status, message, interaction)
        stats['errors'].extend(errors)
        event = {'event_id': event_id, 'action_committed': 'glossary-enrich', 'interaction_id': interaction,
                 'contexts': contexts, 'definitions': generated, 'errors': errors,
                 'usage': stats['usage'][-1] if values and stats['usage'] else None}
        self._save(batch, event, fault=fault)
        if write_outcome:
            self.trace.write(interaction, 'outcome', {'timestamp': now(), 'status': 'committed',
                             'action_committed': 'glossary-enrich', 'event_ref': 'events/' + event_id + '.json'})

    def run(self, *, limit=None, term_ids=(), batch_size=4, max_calls=60, retry_failed=False, revalidate_received=False, upgrade_provisional=False, progress=None, fault=None):
        require(limit is None or type(limit) is int and limit >= 0, 'Invalid glossary limit.')
        require(type(batch_size) is int and 1 <= batch_size <= 12, 'Glossary batch size must be 1..12.')
        require(type(max_calls) is int and 0 <= max_calls <= 60, 'Glossary generation call limit must be 0..60.')
        require(isinstance(term_ids, (list, tuple)) and all(isinstance(i, str) and glossary.TERM_ID.fullmatch(i)
                for i in term_ids), 'Invalid glossary term selection.')
        start = time.monotonic()
        stats = dict(processed=0, model_calls=0, resumed_responses=0, authoritative_lookups=0,
                     authoritative_api_calls=0, authoritative_definitions=0, research_definitions=0,
                     model_generated_definitions=0, usage=[], errors=[])
        with self.trace.execution(self.log_dir, command='glossary-enrich'), self.store.lock():
            self.store.read(); state = self._state(); records = self.directory.all(state)
            by_id = {r['id']: r for r in records}
            require(set(term_ids) <= set(by_id), 'Unknown glossary term ID.')
            stats['before'] = coverage(records, state)
            files = self.store._files()
            events = {loads(t).get('interaction_id'): loads(t) for p, t in files.items() if p.startswith('events/')}
            interactions = read_records(self.store.root)
            for item in interactions:
                if 'outcome' in item: continue
                if item['id'] in events:
                    self.trace.write(item['id'], 'outcome', {'timestamp': now(), 'status': 'committed',
                        'action_committed': events[item['id']].get('action_committed')})
                    continue
                require(item.get('request', {}).get('action') == 'G1',
                        'Unresolved research submission; inspect transcript before glossary maintenance.')
                pending = [r for r in records if r.get('enrichment') and
                           r['enrichment'][-1]['interaction_id'] == item['id'] and
                           r['enrichment'][-1]['status'] in {'pending', 'uncertain'}]
                require(pending and item.get('response', {}).get('status') == 'received',
                        'Uncertain glossary submission; inspect transcript and explicitly acknowledge before retry.')
                self._finish(pending, state, by_id, item['id'], item['request'], item['response'], stats, fault)
                stats['resumed_responses'] += 1
            if revalidate_received:
                require(term_ids, 'Explicit term IDs are required to revalidate received definitions.')
                for identity in term_ids:
                    record = by_id[identity]
                    if definitions.preferred(record, scope(record, state)): continue
                    last = record.get('enrichment', [{}])[-1]
                    item = next((i for i in interactions if i['id'] == last.get('interaction_id')), None)
                    require(item and item.get('response', {}).get('status') == 'received' and
                            item.get('outcome', {}).get('status') == 'committed', 'No safely received committed response to revalidate.')
                    self._finish([record], state, by_id, item['id'], item['request'], item['response'], stats,
                                 fault, write_outcome=False)
                    stats['resumed_responses'] += 1
            from .retrieval import unresolved
            from types import SimpleNamespace
            require(not unresolved(SimpleNamespace(store=self.store), files), 'Uncertain provider submission; glossary maintenance blocked.')
            selected = []
            for record in records:
                if term_ids and record['id'] not in term_ids: continue
                last = record.get('enrichment', [{}])[-1]
                unchanged = last.get('input_sha256') == input_hash(record, state, by_id)
                rows = definitions.preferred(record, scope(record, state))
                upgrade = upgrade_provisional and rows and all(definitions.provisional(d) for d in rows) and terminology.lookup_due(record, self.clock())
                if unchanged and last.get('status') in {'complete', 'clarification'} and not upgrade: continue
                if unchanged and last.get('status') == 'approval_required' and self.prompt_factory is None and not retry_failed:
                    continue
                if unchanged and last.get('status') in {'pending', 'uncertain'}:
                    # An explicit transcript acknowledgement is required even if
                    # another tool has supplied an outcome receipt.
                    require(any(i['id'] == last['interaction_id'] and i.get('outcome', {}).get('status') == 'interrupted_acknowledged'
                                for i in interactions), 'Uncertain glossary submission requires explicit acknowledgement.')
                    if not retry_failed: continue
                if unchanged and last.get('status') == 'failed':
                    if not retry_failed or datetime.fromisoformat(last['retry_after']).timestamp() > self.clock(): continue
                selected.append(record)
            if limit is not None: selected = selected[:limit]
            waiting = []
            for record in selected:
                done = self._prepare_term(record, state, by_id, stats, upgrade_provisional)
                if done:
                    self._progress(record, state, by_id, 'complete', 'Applicable attributed definition retained.')
                self._save([record], {'event_id': uuid.uuid4().hex, 'action_committed': 'glossary-enrich-authority',
                    'terminology': record.get('terminology', [])[-1:]})
                if done:
                    stats['processed'] += 1
                else: waiting.append(record)
            while waiting:
                if stats['model_calls'] >= max_calls:
                    stats['stop_reason'] = 'generation_call_budget'
                    break
                batch = waiting[:batch_size]
                try:
                    while True:
                        try: request, data, usage, template = self._request(batch, state, by_id); break
                        except ValueError as exc:
                            if 'context window' not in str(exc) or len(batch) == 1: raise
                            batch = batch[:max(1, len(batch)//2)]
                except Exception as exc:
                    for record in batch:
                        self._progress(record, state, by_id, 'failed', terminology.failure_reason(exc))
                        stats['errors'].append({'id': record['id'], 'phase': 'model_setup', 'reason': str(exc)})
                    self._save(batch, {'event_id': uuid.uuid4().hex, 'action_committed': 'glossary-enrich-unavailable'})
                    waiting = waiting[len(batch):]; stats['processed'] += len(batch)
                    continue
                scopes = {r['id']: {k: v for k, v in scope(r, state).items() if k in {'question', 'node_id'}} for r in batch}
                interaction = self.trace.start({'action': 'G1'}, request,
                    {'entries': data, 'scopes': scopes, 'model_identity': self.identity, 'token_usage': usage},
                    template=template)
                for record in batch: self._progress(record, state, by_id, 'pending', 'Model request durably prepared; submission may be in flight.', interaction)
                self._save(batch, {'event_id': uuid.uuid4().hex, 'action_committed': 'glossary-enrich-start'}, fault=fault)
                if fault: fault('before_model')
                stats['model_calls'] += 1
                try:
                    raw = self.trace.clean(self.model.complete(request))
                except Exception as exc:
                    self.trace.write(interaction, 'response', {'timestamp': now(), 'status': 'call_failed',
                        'error': terminology.failure_reason(exc), 'raw': getattr(exc, 'raw', None)})
                    for record in batch: self._progress(record, state, by_id, 'uncertain', 'Transport failed; model execution is uncertain. Inspect transcript before retry.', interaction)
                    self._save(batch, {'event_id': uuid.uuid4().hex, 'action_committed': 'glossary-enrich-uncertain'})
                    stats['errors'].append({'phase': 'model_submission', 'reason': str(exc)})
                    break
                response = {'timestamp': now(), 'status': 'received', 'raw': raw}
                self.trace.write(interaction, 'response', response)
                if fault: fault('response_received')
                saved = loads(self.store.path('interactions/' + interaction + '/request.json').read_text())
                self._finish(batch, state, by_id, interaction, saved, response, stats, fault)
                stats['processed'] += len(batch); waiting = waiting[len(batch):]
                if progress: progress({'processed': stats['processed'], 'selected': len(selected), **coverage(records, state)})
            state = self._state()
            stats.update(after=coverage(records, state), elapsed_seconds=time.monotonic()-start,
                         revision=glossary.metadata(state)['revision'], root=str(self.store.root))
            stats['exports'] = self.directory.export(state)
            self.trace.record('glossary_enrichment_summary', stats)
        return stats
