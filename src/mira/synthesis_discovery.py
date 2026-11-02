"""Bounded deterministic unit discovery, adapted from the diagnostic experiment.

Embeddings and neighbour lists are disposable caches, never scientific evidence.
Exact scanning uses O(N D + N k) memory, not a stored similarity matrix.
"""
from contextlib import closing
from collections import Counter
from dataclasses import asdict
import heapq
import html
import math
import re
import sqlite3
import unicodedata

from .embeddings import cosine, validate_vectors
from .format import digest, dumps, loads, require

REPRESENTATION = 'qualified-scientific-unit-v1'
RANKING = 'relatedness-opportunity-diversity-v1'
STOP = set('a an and are as at be been being both by can could did do does each for from had has have how if in into is it its may more most of on or other our reported research result results scientific significantly study studies such than that the their these they this those to using was were what when where whether which while who why will with would patient patients finding findings based'.split())


def normal(text):
    # Preserve inequalities, signs, units, decimal points and negation.
    return ' '.join(unicodedata.normalize('NFKC', html.unescape(text)).casefold().split())


def tokens(text):
    return {w for w in re.findall(r'[^\W_]+', normal(text)) if len(w)>2 and w not in STOP}


def fingerprint(records):
    require(len({r['id'] for r in records})==len(records), 'duplicate synthesis unit')
    return digest(dumps(sorted((r['id'],r['version']) for r in records)))


def representation(record):
    return '\n'.join([record['type'], record['label'], *[k+': '+v for k,v in record['fields'].items()
        if k not in {'Provenance','Evidence status','Origin','Equation'}]])


def project(memories, equations=(), eligible_nodes=None):
    """Full scientific units; versions exclude mutable memory-level bookkeeping."""
    docs={m.id:m for m in memories};eqs={e.id:asdict(e) for e in equations}
    units={m.id+'#'+u.anchor:(m,u) for m in memories for u in m.units}
    def leaves(identity, seen=()):
        require(identity not in seen, 'cyclic knowledge-unit ancestry')
        m,u=units[identity]
        parents=[e.target for e in m.relationships if e.source==u.anchor and e.type=='SYNTHESIZES']
        return sorted({leaf for p in parents for leaf in leaves(p,(*seen,identity))}) if parents else [identity]
    result=[]
    for identity,(m,u) in sorted(units.items()):
        if eligible_nodes is not None and (m.metadata.get('node_id') not in eligible_nodes or
                any(docs[p.split('#')[0]].metadata.get('node_id') not in eligible_nodes for p in leaves(identity))):continue
        if u.kind not in {'finding','question','equation','image'}:continue
        leaf_ids=leaves(identity)
        sources=[]
        for leaf in leaf_ids:
            meta=docs[leaf.split('#')[0]].metadata
            for source in ([meta['source']] if 'source' in meta else meta.get('sources',[])):
                if source not in sources:sources.append(source)
        relationships=[e.payload() for e in m.relationships if e.source==u.anchor]
        scientific={'label':u.label,'fields':dict(u.fields),'sources':sources,
                    'relationships':relationships,'leaf_units':leaf_ids}
        equation=eqs.get(u.fields.get('Equation'))
        if equation:scientific['equation']=equation
        result.append({'id':identity,'memory_id':m.id,'node_id':m.metadata.get('node_id'),
            'type':u.fields.get('Kind',u.kind),'structural_type':u.kind,'label':u.label,
            'fields':dict(u.fields),'version':digest(dumps(scientific)),
            'sources':sources,'source_ids':sorted({s['id'] for s in sources if 'id' in s}),
            'leaf_units':leaf_ids,'relationships':relationships,
            **({'equation':equation} if equation else {})})
    return result


def distinctions(a,b):
    def markers(r):
        text=normal(representation(r));words=set(re.findall(r'[^\W_]+',text))
        return {'numbers_and_comparators':re.findall(r'[<>≤≥=±]*\s*\d+(?:\.\d+)?\s*%?',text),
            'polarity':sorted(words & set('not no without neither absent cannot increase decreased higher lower'.split())),
            'conditions':sorted(words & set('human mice mouse adult pediatric children solid subsolid nonsolid screening retrospective prospective randomized malignant benign infection cancer'.split())),
            'units':sorted(words & set('mm cm days weeks months years kg mg mmol auc'.split())),
            'type':r['type'],'qualification':normal(r['fields'].get('Qualification',''))}
    left,right=markers(a),markers(b)
    return [k for k in left if left[k]!=right[k]]


def annotate(a,b,lexical,semantic):
    same_source=bool(set(a['leaf_units']) & set(b['leaf_units']) or set(a['source_ids']) & set(b['source_ids']))
    scientific=lambda r:{k:normal(v) for k,v in r['fields'].items() if k not in {'Provenance','Origin'}}
    exact=scientific(a)==scientific(b) and a['type']==b['type']
    different=distinctions(a,b)
    explicit=[e['type'] for r,target in [(a,b['id']),(b,a['id'])] for e in r['relationships'] if e['to']==target]
    if exact and same_source:category='exact_duplicate'
    elif exact:category='potential_corroboration'
    elif 'CONTRADICTS' in explicit:category='apparent_contradiction'
    elif any(t in explicit for t in ['QUALIFIES','BUILDS_ON']):category='complementary_findings'
    elif 'SUPPORTS' in explicit:category='potential_corroboration'
    elif semantic is not None and semantic>=.8 and not different:category='potential_semantic_duplicate'
    elif semantic is not None and semantic>=.8:category='informational_redundancy_or_complementarity'
    else:category='relationship_requires_review'
    return {'unit_ids':sorted([a['id'],b['id']]),'category':category,
        'lexical':round(lexical,8),'semantic':round(semantic,8) if semantic is not None else None,
        'distinctions':different,'explicit_relationships':explicit,
        'source_dependence':'shared_evidence' if same_source else 'independence_unverified',
        'automatic_equivalence':category=='exact_duplicate',
        'reason':'Content and provenance require review; no deletion, merging or exclusion from similarity.'}


def opportunity(a, b, row):
    """Bounded retrieval hints, not findings about scientific compatibility.

    Generic role words detect a possible method/measurement/outcome bridge.
    Distinct source IDs measure catalogue variety, never study independence.
    Shared-paper origin alone has no redundancy penalty.
    """
    role_words = [set('method methods protocol assay algorithm model calibrated calibration resolution estimation'.split()),
                  set('measurement measurements measured observed count counts concentration duration volume diameter'.split()),
                  set('outcome outcomes endpoint endpoints association correlation predicts prediction accuracy sensitivity specificity effect response'.split())]
    def roles(r):
        words=tokens(representation(r))
        return {i for i,terms in enumerate(role_words) if words & terms}
    left,right=roles(a),roles(b)
    bridge=bool(left and right and left!=right and len(left|right)>1)
    explicit=bool(set(row['explicit_relationships']) & {'CONTRADICTS','QUALIFIES','BUILDS_ON','SUPPORTS'})
    difference=min(1.,len(set(row['distinctions']) & {'numbers_and_comparators','polarity','units','type'})/2)
    exact={k:normal(v) for k,v in a['fields'].items() if k not in {'Provenance','Origin'}}=={k:normal(v) for k,v in b['fields'].items() if k not in {'Provenance','Origin'}} and a['type']==b['type']
    overlap=len(set(a['leaf_units']) & set(b['leaf_units']))/max(1,len(set(a['leaf_units']) | set(b['leaf_units'])))
    redundancy=1. if exact else max(overlap,.5 if row['category']=='potential_semantic_duplicate' else 0.)
    distinct_sources=bool(a['source_ids'] and b['source_ids'] and set(a['source_ids'])!=set(b['source_ids']))
    relatedness=(row['lexical'] if row['semantic'] is None else .5*row['lexical']+.5*max(0,row['semantic']))
    if row['explicit_relationships']:relatedness=max(relatedness,.95)
    return {'relatedness':round(relatedness,8),
            'complementarity_hint':float(not exact)*max(float(explicit),.75*bridge,.35*(a['structural_type']!=b['structural_type'])),
            'qualified_difference':difference if not exact else 0.,
            'evidence_variety':float(distinct_sources), 'redundancy_hint':redundancy}


def priority_score(dimensions):
    # Positive terms sum to one; redundancy is a bounded, soft penalty.
    return round(max(0.,min(1.,.55*dimensions['relatedness']+.25*dimensions['complementarity_hint']+
        .10*dimensions['qualified_difference']+.10*dimensions['evidence_variety']-.20*dimensions['redundancy_hint'])),8)


def diversify(groups, history=()):
    """Soft exact-version overlap penalty against at most eight recent selections.

    Every candidate remains eligible. This orders opportunities, never changes
    the exact-version register or treats a subset as already evaluated.
    """
    recent=list(history)[-8:]
    result=[]
    for group in groups:
        versions={(v['id'],v['version']) for v in group['unit_versions']}
        overlaps=[]
        for old in recent:
            previous={(v['id'],v['version']) for v in old['unit_versions']}
            overlaps.append(len(versions & previous)/len(versions | previous))
        penalty=round(.18*max(overlaps,default=0.),8)
        result.append({**group,'priority':round(max(0.,group['priority']-penalty),8),
                       'selection_diversity':{'recent_groups':len(recent),'overlap_penalty':penalty,'base_priority':group['priority']}})
    return sorted(result,key=lambda g:(-g['priority'],g['id']))


class Discovery:
    def __init__(self, store, backend=None):
        self.store,self.backend=store,backend

    def _db(self):
        # Safe, disposable root-level index, serialized by the existing writer lock.
        path=self.store.path('synthesis.sqlite3')
        for suffix in ['-wal','-shm','-journal']:self.store.path('synthesis.sqlite3'+suffix)
        db=sqlite3.connect(path)
        db.execute('CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector TEXT NOT NULL)')
        return db

    def vectors(self, records):
        backend=self.backend
        status={'mode':'lexical_only','semantic':False,'backend':getattr(backend,'identity',None),
                'reason':'No semantic embedding backend configured.','generated':0,'cache_hits':0}
        if backend is None or backend.identity.startswith('test-double:'):
            if backend is not None:status['reason']='Token-hashing test double is not semantic retrieval.'
            return None,status
        result=[]
        try:
            with closing(self._db()) as db:
                for record in records:
                    key=digest(dumps([REPRESENTATION,backend.identity,record['version']]))
                    row=db.execute('SELECT vector FROM vectors WHERE key=?',(key,)).fetchone()
                    vector=loads(row[0]) if row else backend.embed([representation(record)],query=False)[0]
                    validate_vectors([vector],1)
                    require(any(vector),'zero synthesis embedding')
                    if not row:
                        db.execute('INSERT INTO vectors VALUES (?,?)',(key,dumps(vector)));db.commit();status['generated']+=1
                    else:status['cache_hits']+=1
                    result.append(vector)
            dimensions=validate_vectors(result,len(records))
            status.update(mode='lexical_semantic',semantic=True,dimensions=dimensions,reason='Real configured semantic embeddings plus lexical retrieval.')
            return result,status
        except Exception as exc:
            status['reason']='Semantic service/cache unavailable: '+str(exc)
            return None,status

    def discover(self, records, *, k=4):
        # Findings/equations/images form the scientific evidence neighbourhood.
        # Open questions remain in parent context; repeated question wording
        # must not dominate semantic discovery or substitute for premises.
        records=sorted((r for r in records if r['structural_type']!='question'),key=lambda r:r['id'])
        vectors,status=self.vectors(records)
        sets=[tokens(representation(r)) for r in records]
        # Sparse lexical vectors; no pair matrix is allocated or persisted.
        counts=Counter(t for words in sets for t in words)
        lexical=[]
        for words in sets:
            v={t:1+math.log((1+len(sets))/(1+counts[t])) for t in sorted(words)}
            norm=math.sqrt(sum(w*w for w in v.values())) or 1
            lexical.append({t:w/norm for t,w in v.items()})
        heaps=[[] for _ in records];opportunities=[[] for _ in records]
        for i,a in enumerate(records):
            for j in range(i):
                b=records[j];lex=sum(w*lexical[j].get(t,0) for t,w in lexical[i].items())
                sem=cosine(vectors[i],vectors[j]) if vectors else None
                explicit=any(e['to']==b['id'] for e in a['relationships']) or any(e['to']==a['id'] for e in b['relationships'])
                score=(.5*lex+.5*max(0,sem) if sem is not None else lex)
                if explicit:score=max(score,.95)
                if score<(.42 if vectors else .15):continue
                potential=priority_score(opportunity(a,b,annotate(a,b,lex,sem)))
                for left,right in [(i,j),(j,i)]:
                    # Negative position preserves ascending stable-ID ties.
                    heapq.heappush(heaps[left],(score,-right,right,lex,sem))
                    if len(heaps[left])>k:heapq.heappop(heaps[left])
                    heapq.heappush(opportunities[left],(potential,-right,right,lex,sem))
                    if len(opportunities[left])>k:heapq.heappop(opportunities[left])
        groups={}
        candidates=[]
        for neighbours in [heaps,opportunities]:
            for i,edges in enumerate(neighbours):
                candidates.append((i,edges,sorted({i,*(e[2] for e in edges)})))
                # Retain original related pairs and full neighbourhoods too.
                candidates.extend((i,[edge],sorted([i,edge[2]])) for edge in edges)
        for i,edges,selected in candidates:
            # A second parent is required; same-paper duplicates stay annotated.
            if len({records[j]['memory_id'] for j in selected})<2:continue
            # Open questions can guide groups but cannot alone support the S3
            # finding contract; don't spend S2 calls on question-only sets.
            if not any(records[j]['structural_type']=='finding' for j in selected):continue
            group=[records[j] for j in selected];key=fingerprint(group)
            if key in groups:continue
            annotations=[];dimensions=[]
            for x,left in enumerate(selected):
                for right in selected[:x]:
                    lex=sum(w*lexical[right].get(t,0) for t,w in lexical[left].items())
                    sem=cosine(vectors[left],vectors[right]) if vectors else None
                    row=annotate(records[left],records[right],lex,sem)
                    annotations.append(row);dimensions.append(opportunity(records[left],records[right],row))
            mean={key:round(sum(d[key] for d in dimensions)/len(dimensions),8) for key in dimensions[0]}
            groups[key]={'id':key,'unit_ids':[r['id'] for r in group],
                'unit_versions':[{'id':r['id'],'version':r['version']} for r in group],
                'memory_ids':sorted({r['memory_id'] for r in group}),
                'priority':priority_score(mean),'ranking':{'policy':RANKING,'dimensions':mean},
                'relationships':annotations,'reason':f'Bounded top-{k} relatedness and opportunity neighbourhoods; ranked by relatedness, role/explicit relationship hints, qualified differences, source variety and soft redundancy. These are review hints, not proof of complementarity or independence.'}
        return sorted(groups.values(),key=lambda g:(-g['priority'],g['id'])),status
