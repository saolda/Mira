"""Read-only, revisioned scientific-unit projections for the existing local viewer.

No research scheduling, embeddings, model requests or canonical writes occur here.
"""
from collections import Counter
from copy import deepcopy
import re
import threading
import unicodedata

from .experiments import existing_reader
from .format import digest, dumps, loads, render, require, validate_corpus
from . import research_tree as tree, sources
from .synthesis_discovery import project

SCHEMA = 'mira.research-state/1'
UNIT_ID = re.compile(r'[rs][1-9a-z][0-9a-z]*#[fqei][1-9a-z][0-9a-z]*\Z')
COUNTING = ('Every current canonical unit is counted once by stable ID. Structural counts (finding, question, equation, image) '
    'and scientific-type counts are separate views of the same units; do not add them together. '
    'An inference in a synthesis memory remains structurally a finding. Historical versions are activity records, not extra current units.')
CAUTION = ('Source citations identify attribution, not independent verification. S1 selection and S2 planning are not synthesis. '
    'S3 completion may mean no synthesis. Structural validation does not scientifically verify generated conclusions. '
    'Controller-answered nodes and answered question units are separate records. Participation is nonconsumptive.')


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).casefold().split())


def unit_order(identity):
    memory, anchor = identity.split('#')
    return memory[0], int(memory[1:], 36), anchor[0], int(anchor[1:], 36)


def build_snapshot(revision, memories, equations, state, files, evidence=None):
    """Pure structured projection, independent of the browser and its layout."""
    state = state or {}
    _, _, _, edges = validate_corpus(memories, equations)
    explicit={(m.id+'#'+e.source,e.type,e.target) for m in memories for e in m.relationships}
    edges=[{**e,'provenance':{'memory_id':e['owner'],
        'basis':'recorded_relationship' if (e['from'],e['type'],e['to']) in explicit else 'inherited_source_attribution'}} for e in edges]
    rows = project(memories, equations)  # Deliberately all branches and origins.
    docs = {m.id: m for m in memories}
    nodes = state.get('nodes', {})
    eligible = set(tree.eligible_subtree(state, state['root_id'])) if nodes else set()
    groups = state.get('unit_synthesis', {}).get('groups', {})
    objectives = state.get('unit_synthesis', {}).get('objectives', {})
    units = {}
    source_inventory = {}
    for row in rows:
        m = docs[row['memory_id']]
        fields = row['fields']
        scientific = fields.get('Epistemic type') or fields.get('Kind') or row['structural_type']
        unit = {**row, 'scientific_type': scientific, 'memory_revision': m.revision,
            'unit_revision': next(u.revision for u in m.units if m.id+'#'+u.anchor == row['id']),
            'memory_title': m.title, 'memory_summary': m.summary,
            'origin': 'synthesized' if m.metadata.get('kind') == 'synthesis' or m.id.startswith('s') else 'source_extracted',
            'evidence_status': fields.get('Evidence status'), 'question_state': fields.get('State') if row['structural_type']=='question' else None,
            'scientific_validation': deepcopy(m.metadata.get('scientific_validation')),
            'proposition': fields.get('Proposition') or fields.get('Question') or fields.get('Description') or fields.get('Expression') or fields.get('Caption') or '',
            'node_status': nodes.get(row['node_id'], {}).get('status'),
            'research_question': nodes.get(row['node_id'], {}).get('question'),
            'eligible_subtree': row['node_id'] in eligible,
            'created_order': m.metadata.get('created_order'),
            'synthesis_history': [], 'participation': [], 'contributing_units': [],
            'evidence_ref': m.metadata.get('evidence_ref'),
            
            'synthesis_objective_id': m.metadata.get('synthesis_objective')}
        units[row['id']] = unit
        for source in row['sources']:
            key = source.get('id') or digest(dumps(source))
            source_inventory.setdefault(key, {'source': sources.descriptor(source), 'unit_ids': []})['unit_ids'].append(row['id'])

    for record in state.get('source_index', {}).values():
        source=record.get('source',{})
        if source.get('id'):
            item=source_inventory.setdefault(source['id'],{'source':sources.descriptor(source),'unit_ids':[]})
            item.update(processed=True,evidence_ref=record.get('evidence_ref'))

    def activity(identity, kind, reference, status, version=None, provenance=None):
        if identity not in units: return
        current = version == units[identity]['version'] if version is not None else None
        units[identity]['synthesis_history'].append({'kind': kind, 'reference': reference, 'status': status,
            'unit_version': version, 'matches_current_version': current, 'provenance': provenance})
        if current is not False and kind not in units[identity]['participation']: units[identity]['participation'].append(kind)

    for g in groups.values():
        for v in g['unit_versions']:
            activity(v['id'], 'selected', g['id'], g['status'], v['version'], 'events/'+g['selected_event']+'.json')
            if g['status']=='evaluated': activity(v['id'], 'evaluated', g['id'], g['status'], v['version'], g.get('s2_interaction_id'))
            if g['status']=='failed': activity(v['id'], 'failed', g['id'], g['status'], v['version'], g.get('s2_interaction_id'))
            if g.get('disposition')=='no_candidate': activity(v['id'], 'no_candidate', g['id'], 'no_candidate', v['version'], g.get('s2_interaction_id'))
    for o in objectives.values():
        for v in o['unit_versions']:
            activity(v['id'], 'objective', o['id'], o['status'], v['version'], o.get('s2_interaction_id'))
            if o.get('s3_interaction_id'): activity(v['id'], 'attempted', o['id'], o['status'], v['version'], o['s3_interaction_id'])
            if o['status']=='completed' and o.get('disposition')=='no_synthesis':
                activity(v['id'], 'no_synthesis', o['id'], 'no_synthesis', v['version'], o.get('s3_interaction_id'))
            if o['status'] in {'failed','blocked_context'}:
                activity(v['id'], 'failed' if o['status']=='failed' else 'blocked', o['id'], o['status'], v['version'], o.get('s3_interaction_id'))
    for blocked in state.get('unit_synthesis', {}).get('deferred_groups', []):
        # Deferred discovery may retain only a fingerprint, not its unit list.
        # Do not guess which individual units were blocked.
        for identity in blocked.get('unit_ids', []): activity(identity, 'blocked', blocked['group_id'], blocked['reason'])
    for edge in edges:
        if edge['type'] != 'SYNTHESIZES' or edge['from'] not in units: continue
        out = units[edge['from']]
        out['contributing_units'].append(edge['to'])
        m = docs[out['memory_id']]
        version = next((v['version'] for v in m.metadata.get('synthesis_unit_versions', []) if v['id']==edge['to']), None)
        activity(edge['to'], 'contributed', out['id'], edge['status'], version, 'memories/'+m.id+'.md')
    for u in units.values():
        if not u['synthesis_history']: u['participation'] = ['never_selected'] if 'unit_synthesis' in state else ['not_recorded']
        u['relationships'] = [deepcopy(e) for e in edges if u['id'] in (e['from'], e['to'])]
        # A declared scientific relationship is not a proof of its content.
        u['contributing_units'].sort(key=unit_order)

    node_rows = []
    for n in nodes.values():
        subtree = set(tree.descendants(state, n['id']))
        direct = [u['id'] for u in units.values() if u['node_id']==n['id']]
        whole = [u['id'] for u in units.values() if u['node_id'] in subtree]
        node_rows.append({k:deepcopy(n.get(k)) for k in ('id','parent_id','child_ids','question','status','priority')})
        node_rows[-1].update(direct_unit_ids=direct, subtree_unit_ids=whole,
            memory_ids=list(n.get('memory_ids', [])),
            synthesis_memory_ids=[m.id for m in memories if m.metadata.get('node_id') in subtree and m.metadata.get('kind')=='synthesis'],
            pending_research={'pending_results':n.get('pending_results'),'deferred_searches':deepcopy(n.get('deferred_searches', [])),
                'search_blocked':n.get('search_blocked',False),'validation_blocked':n.get('r1_validation_blocked',False)},
            pending_objective_ids=[o['id'] for o in objectives.values() if o['status']=='pending' and groups[o['group_id']]['node_id'] in subtree])
    status_counts = dict(Counter(n['status'] for n in nodes.values()))
    types = dict(Counter(u['scientific_type'] for u in units.values()))
    structural = dict(Counter(u['structural_type'] for u in units.values()))
    modern = 'unit_synthesis' in state
    synthesis = {'recording':'knowledge_units' if modern else 'legacy_or_not_recorded',
        'groups_selected':len(groups) if modern else None,
        'groups_evaluated':sum(g['status']=='evaluated' for g in groups.values()) if modern else None,
        'groups_no_candidate':sum(g.get('disposition')=='no_candidate' for g in groups.values()) if modern else None,
        'objectives_proposed':len(objectives) if modern else None,
        'objectives_pending':sum(o['status']=='pending' for o in objectives.values()) if modern else None,
        'attempts_started':sum(bool(o.get('s3_interaction_id')) for o in objectives.values()) if modern else None,
        'attempts_completed':sum(o['status']=='completed' for o in objectives.values()) if modern else None,
        'no_synthesis_outcomes':sum(o.get('disposition')=='no_synthesis' for o in objectives.values()) if modern else None,
        'failed_or_blocked':sum(g['status']=='failed' for g in groups.values()) + sum(o['status'] in {'failed','blocked_context'} for o in objectives.values()) + len(state.get('unit_synthesis',{}).get('deferred_groups', [])) if modern else None,
        'memories_created':sum(m.id.startswith('s') for m in memories)}
    inventory = {'research_memories':sum(m.id.startswith('r') for m in memories), 'synthesis_memories':synthesis['memories_created'],
        'total_units':len(units), 'structural_types':structural, 'scientific_types':types,
        'synthesized_units':sum(u['origin']=='synthesized' for u in units.values()), 'counting_rules':COUNTING}
    coverage = {'sources_processed':len(state['source_index']) if 'source_index' in state else None,
        'sources_yielding_units':len({m.metadata['source']['id'] for m in memories if m.units and m.metadata.get('source')}),
        'units_selected':sum('selected' in u['participation'] for u in units.values()) if modern else None,
        'units_contributing_to_published_synthesis':sum('contributed' in u['participation'] for u in units.values()),
        'units_not_used_in_published_synthesis':sum('contributed' not in u['participation'] for u in units.values()),
        'open_question_units':sum(u['question_state'] in {'open','partially_answered'} for u in units.values()),
        'outstanding_branches':status_counts.get('living',0),
        'not_recorded':'Legacy synthesis registers do not establish unit-level selection, evaluation or attempt history.' if not modern else None}
    root = nodes.get(state.get('root_id'), {})
    identity = {'root_id':state.get('root_id'),'root_question':root.get('question'),
        'active_node_id':state.get('active_node_id'), 'active_node_status':nodes.get(state.get('active_node_id'),{}).get('status'), 'active_question':nodes.get(state.get('active_node_id'),{}).get('question'),
        'objectives':deepcopy(state.get('question_document',{}).get('objectives')),
        'brief':state.get('question_document',{}).get('context'),
        'strategy':sources.descriptor({'id':state.get('strategies',[{}])[state.get('strategy_index',0)].get('id','Not recorded')}) if state.get('strategies') else None,
        'root_status':root.get('status'), 'terminal_event':deepcopy(state.get('terminal_event')),
        'research_cycles':state.get('research_cycles'), 'synthesis_cycles':state.get('synthesis_cycles'),
        'state_revision':state.get('revision'), 'run_id':state.get('run_id')}
    limitations = [CAUTION, COUNTING]
    if not modern: limitations.append(coverage['not_recorded'])
    return {'schema':SCHEMA,'revision':revision,'identity':identity,'inventory':inventory,'node_statuses':status_counts,
        'synthesis_summary':synthesis,'coverage':coverage,'nodes':node_rows,
        'units':sorted(units.values(),key=lambda u:unit_order(u['id'])),
        'original_evidence_by_memory':deepcopy(evidence or {}),
        'memories':[{'id':m.id,'title':m.title,'summary':m.summary,'revision':m.revision,
            'node_id':m.metadata.get('node_id'),'kind':m.metadata.get('kind'),
            'markdown':files.get('memories/'+m.id+'.md',render(m))} for m in memories],
        'sources':list(source_inventory.values()),'relationships':edges,
        'synthesis':{'groups':deepcopy(groups),'objectives':deepcopy(objectives),
            'deferred_groups':deepcopy(state.get('unit_synthesis',{}).get('deferred_groups',[])),
            'legacy_attempts':deepcopy(state.get('synthesis_attempts',[])),
            'legacy_pending':deepcopy(state.get('pending_synthesis'))},
        'limitations':limitations}


class SnapshotChanged(ValueError):
    pass


class KnowledgeInspector:
    def __init__(self, catalog):
        self.catalog=catalog; self._cache={}; self._mutex=threading.RLock()

    @staticmethod
    def _signature(store):
        # Recheck cooperating writer/recovery locks on every request. Metadata
        # detects changes before reusing an immutable, fully validated revision.
        rows=[]
        for base in ('memories','equations','research','events','journal','retrieved'):
            for p in store.path(base).rglob('*'):
                relative=p.relative_to(store.root).as_posix()
                # Legacy stores and disposable glossary exports are not current state.
                if base=='research' and len(p.relative_to(store.root).parts)>2 and p.relative_to(store.root).parts[1]!='results': continue
                if relative in {'research/glossary.md','research/glossary.html','research/state_of_research.md','research/state_of_research.html','research/state_of_research.audit.json'}: continue
                store.path(relative)
                stat=p.stat();rows.append((relative,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns))
        for relative in ('identity.json','.reset.json','.transition.json'):
            p=store.path(relative)
            if p.exists():
                stat=p.stat();rows.append((relative,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns))
        return tuple(sorted(rows))

    def snapshot(self, name, expected=None):
        root=self.catalog.select(name)
        with self._mutex,existing_reader(root,blocking=False) as store:
            signature=self._signature(store)
            cached=self._cache.get(str(root))
            if cached and cached[0]==signature: result=cached[1]
            else:
                revision,memories,equations,_=store.read()
                files=store._files()
                state=loads(files['research/state.json']) if 'research/state.json' in files else {}
                evidence={}
                for m in memories:
                    ref=m.metadata.get('evidence_ref')
                    if not ref or ref not in files: continue
                    saved=loads(files[ref]); source_id=m.metadata.get('source',{}).get('id')
                    try:
                        hydrated=sources.hydrate(store,saved)
                        rows=[r for r in hydrated.get('results',[]) if r.get('id')==source_id]
                        evidence[m.id]={'reference':ref,'available':bool(rows),
                            'source':[{**sources.descriptor(r), **{k:r[k] for k in ('content','abstract','passage') if isinstance(r.get(k),str)}} for r in rows],
                            'notice':'Recorded retrieved source text, not an independently verified quotation supporting every unit.'}
                    except (ValueError,OSError,KeyError,TypeError):
                        evidence[m.id]={'reference':ref,'available':False,'notice':'Retained source payload unavailable or failed hash validation.'}
                result=build_snapshot(revision,memories,equations,state,files,evidence)
                self._cache={str(root):(signature,result)}
            if expected and expected!=result['revision']: raise SnapshotChanged('Scientific snapshot changed; refresh the current view.')
            return deepcopy(result)

    def overview(self,name,expected=None):
        value=self.snapshot(name,expected)
        return {k:v for k,v in value.items() if k not in {'units','memories','sources','relationships','synthesis','original_evidence_by_memory'}}

    def inventory(self,name,params):
        allowed={'q','type','origin','evidence','participation','node','descendants','memory','sort','offset','limit','revision'}
        require(set(params)<=allowed,'unknown knowledge filter')
        snapshot=self.snapshot(name,params.get('revision'));rows=snapshot['units']
        selected_node=params.get('node')
        require(not selected_node or selected_node in {n['id'] for n in snapshot['nodes']},'unknown research question')
        if selected_node:
            node=next(n for n in snapshot['nodes'] if n['id']==selected_node)
            ids=set(node['subtree_unit_ids'] if params.get('descendants')=='true' else node['direct_unit_ids'])
            rows=[r for r in rows if r['id'] in ids]
        for param,key in [('origin','origin'),('memory','memory_id')]:
            if params.get(param): rows=[r for r in rows if r[key]==params[param]]
        if params.get('type'): rows=[r for r in rows if params['type'] in {r['scientific_type'],r['structural_type']}]
        if params.get('evidence'): rows=[r for r in rows if (r['evidence_status'] or 'not_recorded')==params['evidence']]
        if params.get('participation'): rows=[r for r in rows if params['participation'] in r['participation']]
        if params.get('q'):
            words=normalize(params['q']).split()
            rows=[r for r in rows if all(w in normalize(' '.join([r['id'],r['label'],r['proposition'],r['memory_id'],r['research_question'] or '',
                *r['fields'].values(),dumps(r['sources'])])) for w in words)]
        sorting=params.get('sort','id');require(sorting in {'id','memory','node','type','evidence','participation'},'invalid knowledge sort')
        def key(r):
            value={'memory':r['memory_id'],'node':r['node_id'] or '', 'type':r['scientific_type'],
                'evidence':r['evidence_status'] or '', 'participation':','.join(r['participation'])}.get(sorting,'')
            return value,unit_order(r['id'])
        rows=sorted(rows,key=key)
        offset=int(params.get('offset',0));limit=int(params.get('limit',50))
        require(0<=offset and 1<=limit<=200,'invalid knowledge pagination')
        summaries=[{k:v for k,v in r.items() if k not in {'original_evidence','fields','scientific_validation','synthesis_history','equation'}} for r in rows[offset:offset+limit]]
        return {'schema':SCHEMA,'revision':snapshot['revision'],'total':len(rows),'corpus_total':len(snapshot['units']),
            'offset':offset,'limit':limit,'units':summaries,
            'facets':{'evidence':sorted({r['evidence_status'] or 'not_recorded' for r in snapshot['units']}),
                'memories':sorted({r['memory_id'] for r in snapshot['units']})}}

    def detail(self,name,identity,expected=None):
        require(UNIT_ID.fullmatch(identity),'invalid knowledge-unit ID')
        snapshot=self.snapshot(name,expected)
        row=next((r for r in snapshot['units'] if r['id']==identity),None)
        require(row is not None,'unknown knowledge unit')
        row['original_evidence']=snapshot['original_evidence_by_memory'].get(row['memory_id'])
        objective=snapshot['synthesis']['objectives'].get(row['synthesis_objective_id'])
        return {'schema':SCHEMA,'revision':snapshot['revision'],'unit':row,'objective':objective,
            'memory':next(m for m in snapshot['memories'] if m['id']==row['memory_id']),'notice':CAUTION}

    def relationships(self,name,identity,expected=None):
        detail=self.detail(name,identity,expected);row=detail['unit']
        related={e['from'] for e in row['relationships']}|{e['to'] for e in row['relationships']}
        snapshot=self.snapshot(name,detail['revision'])
        neighbours=[{k:r[k] for k in ('id','label','scientific_type','origin','evidence_status')} for r in snapshot['units'] if r['id'] in related]
        return {'schema':SCHEMA,'revision':snapshot['revision'],'selected':identity,'edges':row['relationships'],
            'nodes':neighbours,'leaf_units':row['leaf_units'],'notice':'Recorded directed relationships only; status is not a scientific endorsement.'}
