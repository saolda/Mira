"""Durable provider rounds, host pacing and deferred submission scheduling.

Canonical state and outcomes commit through Research's existing journal. Independent
submission receipts precede network I/O, so a crash before publication cannot
silently repeat an uncertain request.
"""
from copy import deepcopy
from email.utils import parsedate_to_datetime
import inspect
from urllib.parse import urlsplit
import uuid

from . import query_profiles as profiles
from .format import dumps, loads, require
from .search import validate_search
from .store import sync_dir


class SubmissionPersistenceError(RuntimeError):
    """Never turn a failed durable preflight into an ordinary provider outcome."""


def strategy(state):
    return state['strategies'][state['strategy_index']]


def enabled(state):
    return 'query_profiles' in strategy(state) or 'legacy_query_policy' in state


def upgrade(state):
    if 'query_profiles' not in strategy(state) and 'legacy_query_policy' not in state:
        data = profiles.registry()
        state['legacy_query_policy'] = {'profile':deepcopy(profiles.select(data, 'default')),
                                       'host_min_intervals':deepcopy(data['host_min_intervals'])}
        state['provider_availability'] = {p:{'next_request_at':t, 'consecutive_rate_limits':0}
            for p,t in state.get('provider_cooldowns', {}).items()}
        # The legacy cursor proves visits, not outcomes. Do not invent failed or
        # empty results for that already completed prefix of an older round.
        for node in state['nodes'].values():
            node['legacy_completed_provider_indices'] = list(range(node['next_database_index']))


def compile_entry(state, provider, concepts):
    selected = strategy(state)
    legacy = 'query_profiles' not in selected
    profile = state['legacy_query_policy']['profile'] if legacy else selected['query_profiles'][provider]
    return profiles.compile(provider, concepts, profile, legacy=legacy)


def host_intervals(state):
    return (state['legacy_query_policy'] if 'query_profiles' not in strategy(state) else strategy(state))['host_min_intervals']


def host(provider, adapter=None):
    return getattr(adapter, 'host', profiles.HOSTS.get(provider, provider))


def eligible_at(state, entry, adapter=None):
    provider = entry['provider']
    return max(entry.get('retry_at', 0),
        state.get('provider_availability', {}).get(provider, {}).get('next_request_at', 0),
        state.get('host_availability', {}).get(host(provider, adapter), 0))


def next_entry(state, node, adapters, timestamp):
    selected = strategy(state)
    index = node['next_database_index']
    if index < len(selected['databases']):
        provider = selected['databases'][index]
        return {**compile_entry(state, provider, node['keywords']),
                'provider_index': index, 'attempts': 0, 'retry_at': 0}, True
    queue = sorted(node.get('deferred_searches', []), key=lambda e:e['provider_index'])
    return next(((deepcopy(e), False) for e in queue if eligible_at(state, e, adapters.get(e['provider'])) <= timestamp), (None, False))


def ready(state, node, adapters, timestamp):
    if node['pending_results'] or node['keywords'] is None: return True
    if node['next_database_index'] < len(strategy(state)['databases']): return True
    return not node.get('deferred_searches') or next_entry(state, node, adapters, timestamp)[0] is not None


def retry_time(value, timestamp, failures, profile):
    # A valid server delay is authoritative, even beyond the local backoff cap.
    try:
        if isinstance(value, str) and value.strip().isdigit(): return timestamp + int(value.strip())
        if type(value) in (int, float) and profiles.number(value): return timestamp + value
        if isinstance(value, str):
            date = parsedate_to_datetime(value)
            if date.tzinfo is not None: return max(timestamp, date.timestamp())
    except (TypeError, ValueError, OverflowError): pass
    # Avoid exponent overflow for a long-lived provider under repeated rate limits.
    delay = profile['retry_initial_seconds']
    for _ in range(min(failures - 1, 1024)):
        delay = min(profile['retry_max_seconds'], delay * 2)
        if delay == profile['retry_max_seconds']: break
    return timestamp + delay


def receipt(research, identity, phase, value):
    directory = research.store.path('retrieval_calls/' + identity)
    directory.mkdir(parents=True, exist_ok=True)
    sync_dir(directory.parent)
    research.store._replace('retrieval_calls/' + identity + '/' + phase + '.json', research.trace.clean(dumps(value)))
    research.trace.record('provider_' + phase, {'submission_id':identity, **value})


def unresolved(research, files):
    committed = {loads(raw).get('submission_id') for p, raw in files.items() if p.startswith('research/results/')}
    result = []
    for directory in sorted(research.store.path('retrieval_calls').glob('*')):
        research.store.path('retrieval_calls/' + directory.name)
        acknowledged = research.store.path('retrieval_calls/' + directory.name + '/acknowledged.json')
        intent = research.store.path('retrieval_calls/' + directory.name + '/intent.json')
        if directory.name in committed or acknowledged.exists(): continue
        if intent.exists(): result.append(directory.name)
    return result


def restore_spacing(research, state):
    """Recover request times even after an operator acknowledges an unknown call."""
    for path in research.store.path('retrieval_calls').glob('*/network-*.json'):
        research.store.path(path.relative_to(research.store.root).as_posix())
        row = loads(path.read_text())
        hosts = state.setdefault('host_availability', {})
        hosts[row['host']] = max(hosts.get(row['host'], 0), row['next_request_at'])
        providers = state.setdefault('provider_availability', {})
        available = providers.setdefault(row['provider'], {'next_request_at': 0, 'consecutive_rate_limits': 0})
        available['next_request_at'] = max(available['next_request_at'], row['next_request_at'])


def perform(research, state, node, event):
    timestamp = research.clock()
    entry, initial = next_entry(state, node, research.adapters, timestamp)
    require(entry is not None, 'provider is waiting')
    provider, profile = entry['provider'], entry['profile_config']
    adapter = research.adapters.get(provider)
    until = eligible_at(state, entry, adapter)
    queue = node.setdefault('deferred_searches', [])
    if until > timestamp:
        result = {'status':'deferred', 'results':[], 'skipped':'provider_availability', 'retry_at':until}
        entry['retry_at'] = until
        submitted = False
    elif adapter is None:
        result = {'status':'failed', 'results':[], 'error':'provider adapter unavailable'}
        submitted = False
    else:
        identity = uuid.uuid4().hex
        entry['submission_id'] = identity
        entry['attempts'] += 1
        intent = {'node_id': event['node_id'], 'cycle': event['cycle'], 'round': node.get('search_round', 0),
                  'timestamp':timestamp, **entry}
        receipt(research, identity, 'intent', intent)
        fault = getattr(research, '_retrieval_fault', None)
        if fault: fault('retrieval_intent')
        network = []
        def gate(endpoint, parameters):
            current_host = urlsplit(endpoint).netloc if endpoint else host(provider, adapter)
            hosts = state.setdefault('host_availability', {})
            delay = max(0, hosts.get(current_host, 0) - research.clock())
            if delay: research.sleep(delay)
            started = research.clock()
            interval = max(profile['min_interval_seconds'], host_intervals(state).get(current_host, 0))
            hosts[current_host] = started + interval
            row = {'provider':provider, 'host':current_host, 'endpoint':endpoint, 'parameters':parameters,
                   'started_at':started, 'next_request_at':started + interval,
                   'logical_submission':endpoint is None}
            network.append(row)
            try:
                receipt(research, identity, 'network-' + str(len(network)), row)
            except Exception as exc:
                raise SubmissionPersistenceError('could not persist provider request intent') from exc
            if fault: fault('retrieval_network')
        try:
            parameters = inspect.signature(adapter.search).parameters
            if 'before_request' in parameters:
                result = validate_search(adapter.search(entry['query'], before_request=gate))
            else:
                # Custom/fixture adapters expose one logical submission.
                gate(None, entry['request_parameters'])
                result = validate_search(adapter.search(entry['query']))
        except Exception as exc:
            if isinstance(exc, SubmissionPersistenceError): raise
            result = {'status':'failed', 'results':[], 'error':research.trace.clean(str(exc)), 'error_type':type(exc).__name__}
        result = loads(research.trace.clean(dumps(result)))
        result['requests'] = [{k:r[k] for k in ('endpoint','parameters','started_at','logical_submission')} for r in network]
        receipt(research, identity, 'response', result)
        if fault: fault('retrieval_response')
        submitted = bool(network)
        available = state.setdefault('provider_availability', {}).setdefault(provider, {'next_request_at':0, 'consecutive_rate_limits':0})
        available['next_request_at'] = max(available['next_request_at'], research.clock() + profile['min_interval_seconds'])
        if result['status'] == 'rate_limited':
            available['consecutive_rate_limits'] += 1
            until = retry_time(result.get('retry_after'), research.clock(), available['consecutive_rate_limits'], profile)
            available['next_request_at'] = max(available['next_request_at'], until)
            entry['retry_at'] = available['next_request_at']
            result['retry_at'] = entry['retry_at']
            if entry['attempts'] >= profile['max_attempts']:
                result.update(status='unavailable', last_retrieval_status='rate_limited')
        elif result['status'] in {'ok', 'empty'}:
            available['consecutive_rate_limits'] = 0
    queue[:] = [e for e in queue if e['provider_index'] != entry['provider_index']]
    if result['status'] in {'deferred', 'rate_limited'}:
        queue.append(deepcopy({k:v for k,v in entry.items() if k!='submission_id'}))
        queue.sort(key=lambda e:e['provider_index'])
    else:
        node.setdefault('provider_outcomes', {})[str(entry['provider_index'])] = result['status']
    before = node['next_database_index']
    if initial: node['next_database_index'] += 1
    node.setdefault('round_outcomes', []).append(result['status'])
    event.update(database_index_before=before, database_index_after=node['next_database_index'],
        deferred_retry=not initial, query_submitted=submitted, attempts=entry['attempts'])
    return entry, result, submitted


def validate_state(state):
    if not enabled(state): return
    selected = strategy(state)
    if 'query_profiles' in selected:
        require(isinstance(selected.get('profiles'), dict) and set(selected['profiles']) == set(selected['databases'])
            and isinstance(selected['query_profiles'], dict) and set(selected['query_profiles']) == set(selected['databases']), 'invalid profile snapshot')
        for provider, profile in selected['query_profiles'].items():
            profiles.validate(profile)
            require(selected['profiles'][provider] == profile['id'] and
                (provider in profile['providers'] or provider not in profiles.PROVIDERS and profile['id']=='default'), 'incompatible snapshotted profile')
    else:
        require(isinstance(state['legacy_query_policy'], dict), 'invalid legacy query policy')
        profiles.validate(state['legacy_query_policy']['profile'])
        require(state['legacy_query_policy']['profile']['compiler']=='legacy', 'changed legacy compiler')
    require(isinstance(host_intervals(state), dict) and all(profiles.number(t) for t in host_intervals(state).values()), 'invalid host intervals')
    require(isinstance(state.get('provider_availability', {}), dict), 'invalid provider availability')
    for value in state.get('provider_availability', {}).values():
        require(isinstance(value, dict) and profiles.number(value.get('next_request_at')) and
            type(value.get('consecutive_rate_limits')) is int and value['consecutive_rate_limits'] >= 0, 'invalid provider availability')
    require(isinstance(state.get('host_availability', {}), dict) and
        all(profiles.number(v) for v in state.get('host_availability', {}).values()), 'invalid host availability')
    for n in state['nodes'].values():
        queue = n.get('deferred_searches', [])
        require(isinstance(queue, list), 'invalid deferred queue')
        seen = set()
        for e in queue:
            require(isinstance(e, dict) and type(e.get('provider_index')) is int and 0 <= e['provider_index'] < n['next_database_index']
                and e['provider_index'] not in seen, 'invalid deferred provider index')
            seen.add(e['provider_index'])
            provider = selected['databases'][e['provider_index']]
            compiled = compile_entry(state, provider, n['keywords'])
            require(e.get('provider') == provider and e.get('profile_config') == compiled['profile_config'], 'changed deferred profile')
            require(all(e.get(k) == v for k,v in compiled.items()), 'changed deferred query')
            require(type(e.get('attempts')) is int and 0 <= e['attempts'] < e['profile_config']['max_attempts']
                and profiles.number(e.get('retry_at')), 'invalid deferred attempts/time')
        require(not queue or n['status']=='living' and n['keywords'] is not None, 'deferred work requires a living research round')
        if 'provider_outcomes' in n:
            terminal = n['provider_outcomes']
            legacy = n.get('legacy_completed_provider_indices', [])
            require(isinstance(legacy, list) and (not legacy or 'legacy_query_policy' in state) and
                all(type(i) is int and 0 <= i < n['next_database_index'] for i in legacy)
                and len(legacy)==len(set(legacy)), 'invalid legacy provider prefix')
            require(isinstance(terminal, dict) and all(isinstance(k, str) and k.isdigit() and
                0 <= int(k) < n['next_database_index'] and v in {'ok','empty','failed','unavailable'}
                for k,v in terminal.items()), 'invalid terminal provider outcomes')
            groups = [seen, {int(k) for k in terminal}, set(legacy)]
            require(sum(map(len, groups)) == len(set.union(*groups)) and
                set.union(*groups) == set(range(n['next_database_index'])), 'incomplete provider progression')
