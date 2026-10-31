"""Scientific R4 projections and journaled assessments; no generated interpretation.

Tree scope is deliberately conservative: include all eligible subtree research
and synthesis, plus related ancestor/cross-branch synthesis and its exact support
closure. Relevance never silently trims scientific text. The final model budget
check either accepts the entire projection or blocks before dispatch.
"""
from copy import deepcopy
from dataclasses import asdict

from . import research_tree as tree
from .format import loads, require


FIELDS = {'Kind': 'kind', 'Evidence status': 'evidence_status', 'Proposition': 'proposition',
          'Explanation': 'explanation', 'Provenance': 'provenance', 'Qualification': 'qualification',
          'Question': 'question', 'State': 'state', 'Origin': 'origin', 'Equation': 'equation_id',
          'Description': 'description', 'Expression': 'expression', 'Variables': 'variables',
          'Image': 'image', 'Figure reference': 'figure_reference'}


def eligible(state, node):
    return (not node['pending_results'] and not node.get('deferred_searches') and
            (node.get('search_blocked') or node['keywords'] is not None and
             node['next_database_index'] == len(state['strategies'][state['strategy_index']]['databases'])))


def context(state, memories, equations, identity):
    node = state['nodes'][identity]
    documents = {m.id: m for m in memories}
    units = {m.id + '#' + u.anchor: (m, u) for m in memories for u in m.units}
    scope = set(tree.eligible_subtree(state, identity))
    # Include consumed originals. A synthesis never replaces the scientific
    # support against which R4 must check its conclusions.
    allowed = {}
    def admissible(memory, visiting=frozenset()):
        if memory.id in allowed: return allowed[memory.id]
        require(memory.id not in visiting, 'cyclic scientific lineage')
        owner = memory.metadata['node_id']
        result = (not any(state['nodes'][i]['status'] == 'killed' for i in tree.ancestors(state, owner)) and
            all(admissible(documents[s], visiting | {memory.id}) for s in memory.metadata.get('source_memories', [])))
        allowed[memory.id] = result
        return result
    for memory in memories: admissible(memory)
    selected = {m.id for m in memories if m.metadata['node_id'] in scope and allowed[m.id]}
    seeds = set(selected)
    def lineage(memory, seen=None):
        seen = set() if seen is None else seen
        for source in memory.metadata.get('source_memories', []):
            if source not in seen:
                seen.add(source); lineage(documents[source], seen)
        return seen
    for memory in memories:
        if memory.metadata['kind'] == 'synthesis' and allowed[memory.id] and lineage(memory) & seeds:
            selected.add(memory.id)
    required = {m.id + '#' + u.anchor for m in memories if m.id in selected for u in m.units}
    pending = sorted(required)
    missing, excluded_support, referenced_equations = set(), set(), set()
    edges = {}
    # Follow all scientific relations, in both directions for contradictions and
    # qualifications. Preserve exactly the referenced units, each only once.
    adjacency = {}
    for memory in sorted(memories, key=lambda m: (m.metadata['created_order'], m.id)):
        for edge in memory.relationships:
            source = memory.id + '#' + edge.source
            row = {'from': source, 'type': edge.type, 'to': edge.target, 'status': edge.status}
            adjacency.setdefault(source, []).append(row)
            if edge.type in {'CONTRADICTS', 'QUALIFIES', 'SUPPORTS', 'RELATED_TO'}:
                adjacency.setdefault(edge.target, []).append(row)
    expanded = set(selected)
    while pending:
        reference = pending.pop()
        if reference not in units:
            missing.add(reference); continue
        memory, unit = units[reference]
        selected.add(memory.id)
        if memory.id not in expanded:
            expanded.add(memory.id)
            for supporting in memory.units:
                target = memory.id + '#' + supporting.anchor
                if target not in required:
                    required.add(target); pending.append(target)
        if unit.kind == 'equation': referenced_equations.add(unit.fields['Equation'])
        for edge in adjacency.get(reference, []):
            target = edge['to'] if edge['from'] == reference else edge['from']
            edges[(edge['from'], edge['type'], edge['to'])] = edge
            if target in units:
                if not allowed[units[target][0].id]:
                    excluded_support.add(target); continue
                if target not in required:
                    required.add(target); pending.append(target)
            elif '#' in target and target.split('#', 1)[0] in documents:
                missing.add(target)
        # Legacy synthesis with lineage but no unit-level citations: include all
        # lineage evidence rather than guessing exact supporting anchors.
        if unit.kind == 'finding' and memory.metadata['kind'] == 'synthesis':
            supports = [r for r in adjacency.get(reference, []) if r['from'] == reference and r['type'] == 'SYNTHESIZES']
            if not supports:
                for source in memory.metadata.get('source_memories', []):
                    if not allowed[source]: continue
                    for supporting in documents[source].units:
                        target = source + '#' + supporting.anchor
                        if target not in required:
                            required.add(target); pending.append(target)
    projected_memories, findings, questions, other_units, uncited = [], [], [], [], []
    for memory in sorted((documents[i] for i in selected), key=lambda m: (m.metadata['created_order'], m.id)):
        included = [u for u in memory.units if memory.id + '#' + u.anchor in required]
        projected_memories.append({'id': memory.id, 'kind': memory.metadata['kind'],
            'question': state['nodes'][memory.metadata['node_id']]['question'], 'summary': memory.summary,
            'sources': deepcopy([memory.metadata['source']] if 'source' in memory.metadata else memory.metadata.get('sources', [])),
            'evidence_ref': memory.metadata.get('evidence_ref'),
            'source_memories': list(memory.metadata.get('source_memories', []))})
        for unit in included:
            reference = memory.id + '#' + unit.anchor
            value = {'id': reference, 'memory_id': memory.id, 'label': unit.label,
                **{FIELDS.get(key, key): text for key, text in unit.fields.items()}}
            if unit.kind == 'finding':
                value.setdefault('evidence_status', 'unverified')
                if memory.metadata['kind'] == 'synthesis':
                    value['supporting_anchors'] = [e['to'] for e in adjacency.get(reference, [])
                        if e['from'] == reference and e['type'] == 'SYNTHESIZES']
                    if not value['supporting_anchors']: uncited.append(reference)
                findings.append(value)
            elif unit.kind == 'question': questions.append(value)
            else: other_units.append({'type': unit.kind, **value})
    equation_map = {e.id: e for e in equations}
    missing.update(referenced_equations - equation_map.keys())
    omitted = [{'id': m.id, 'reason': 'killed_branch_or_lineage' if not allowed[m.id] else 'outside_question_scope'}
               for m in sorted(memories, key=lambda m: (m.metadata['created_order'], m.id)) if m.id not in selected]
    return {'question': node['question'], 'question_scope': {
        'parent_question': state['nodes'][node['parent_id']]['question'] if node['parent_id'] else None,
        'root_question': state['nodes'][state['root_id']]['question'],
        'is_root': identity == state['root_id'],
        'research_objectives': list(state.get('question_document', {}).get('objectives', []))},
        'scientific_evidence': {'memories': projected_memories, 'findings': findings,
            'unresolved_questions': [q for q in questions if q['state'] in {'open', 'partially_answered'}],
            'other_questions': [q for q in questions if q['state'] not in {'open', 'partially_answered'}],
            'other_units': other_units,
            'equations': [asdict(equation_map[i]) for i in sorted(referenced_equations) if i in equation_map],
            'relationships': [edges[key] for key in sorted(edges)],
            'coverage': {'policy': 'all eligible subtree evidence, related synthesis and exact scientific support closure',
                'complete_for_selected_scope': not (missing or excluded_support),
                'truncated': False, 'included_memory_ids': [m['id'] for m in projected_memories],
                'omitted_memories': omitted, 'missing_support_anchors': sorted(missing),
                'excluded_support_anchors': sorted(excluded_support), 'uncited_synthesis_findings': uncited,
                'omitted_unit_count_in_included_memories': sum(len(documents[i].units) for i in selected) - len(required),
                'scientific_verification': 'unverified; citation presence does not establish scientific support'}}}


def apply(state, identity, value, event):
    node = state['nodes'][identity]
    require(eligible(state, node), 'R4 requires completed evidence and deferred searches')
    require(value['decision'] != 'kill' or identity != state['root_id'], 'R4 cannot kill the root question')
    receipt = {'decision': deepcopy(value), 'event_ref': 'events/' + event['event_id'] + '.json',
               'interaction_id': event['interaction_id'], 'search_blocked': node.get('search_blocked', False)}
    node['last_r4_assessment'] = receipt
    event['decision'] = deepcopy(value)
    if value['decision'] in {'answered', 'kill'}:
        node['status'] = 'answered' if value['decision'] == 'answered' else 'killed'
    elif node.get('search_blocked'):
        node.update(status='exhausted', exhaustion_reason='search_blocked', exhaustion_assessment=deepcopy(receipt))
        event['exhaustion'].append({'node_id': identity, 'reason': 'search_blocked', 'assessment': deepcopy(receipt)})
    else:
        from .r1 import unique
        node['previous_search_terms'] = unique(node['previous_search_terms'] + (node['keywords'] or []))
        node.update(keywords=None, next_database_index=0, round_outcomes=[], provider_outcomes={},
                    deferred_searches=[], legacy_completed_provider_indices=[])


def search_exhausted(node):
    receipt = node.get('exhaustion_assessment', {})
    return (node.get('exhaustion_reason') == 'search_blocked' and node.get('search_blocked') is True
            and receipt.get('search_blocked') is True and receipt.get('decision', {}).get('decision') == 'unresolved')


def validate_state(node, files):
    receipt = node.get('last_r4_assessment')
    if receipt is not None:
        require(isinstance(receipt, dict) and set(receipt) == {'decision', 'event_ref', 'interaction_id', 'search_blocked'}, 'invalid R4 assessment')
        from .decisions import validate
        validate('R4', receipt['decision'])
        require(receipt['decision']['decision'] != 'kill' or node['parent_id'] is not None, 'R4 cannot kill the root question')
        require(type(receipt['search_blocked']) is bool and isinstance(receipt['interaction_id'], str), 'invalid R4 provenance')
        require(receipt['event_ref'] in files and receipt['event_ref'].startswith('events/'), 'missing R4 assessment event')
        event = loads(files[receipt['event_ref']])
        require(event.get('node_id') == node['id'] and event.get('status') == 'committed'
                and event.get('action_committed') == 'R4' and event.get('decision') == receipt['decision']
                and event.get('interaction_id') == receipt['interaction_id'], 'R4 assessment differs from committed event')
    if node.get('exhaustion_reason') == 'search_blocked':
        require(search_exhausted(node) and node['status'] in {'exhausted', 'split'}
            and node.get('exhaustion_assessment') == receipt, 'invalid search exhaustion cause')
        committed = loads(files[receipt['event_ref']]).get('tree', {}).get(node['id'], {})
        require(committed.get('status') == 'exhausted' and committed.get('search_blocked') is True
                and committed.get('exhaustion_reason') == 'search_blocked'
                and committed.get('exhaustion_assessment') == receipt, 'search exhaustion is not proved by its R4 event')
