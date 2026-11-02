"""Production S1 discovery, S2 objectives and S3 unit-level participation.

All mutable scientific bookkeeping is an after-image of research/state.json.
Independent interaction receipts retain dispatch uncertainty outside the journal.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, localcontext
import re

from . import decisions, questions
from .budget import measure
from .format import Memory, Unit, Relationship, base36, digest, dumps, loads, render, require
from .synthesis_discovery import Discovery, diversify, project, fingerprint, normal, tokens, representation


def initial():
    return {'version':1,'groups':{},'objectives':{},'selected_group':None,'scanned':None,
            'capability':None,'burst':0}


def records(state, memories, equations=()):
    from . import research_tree as tree
    return project(memories,equations,set(tree.eligible_subtree(state,state['root_id'])))


def catalogue(state, memories):
    from . import research_tree as tree
    return digest(dumps({'units':fingerprint(records(state,memories)),
        'questions':[(i,state['nodes'][i]['question']) for i in tree.eligible_subtree(state,state['root_id'])],
        'budget':[state['context_budget'],state.get('synthesis_output_reserve',state['output_reserve'])]}))


def pending(state):
    register=state.get('unit_synthesis',{})
    return bool(register.get('selected_group') or any(o['status']=='pending' for o in register.get('objectives',{}).values()))


def blocked(state):
    register=state.get('unit_synthesis',{})
    return bool(register.get('legacy_pending') or register.get('deferred_groups') or any(g['status']=='failed' for g in register.get('groups',{}).values()) or
        any(o['status'] in {'failed','blocked_context'} for o in register.get('objectives',{}).values()))


def available(state, memories):
    register=state['unit_synthesis']
    return pending(state) or (len({r['memory_id'] for r in records(state,memories)})>=2 and register['scanned']!=catalogue(state,memories))


def upgrade(state):
    if 'unit_synthesis' not in state:
        state['unit_synthesis']=initial()
        # Never discard or reinterpret an in-flight legacy execution selection.
        # It remains durable and requires operator review instead of silent replay.
        if state.get('pending_synthesis') is not None:
            state['unit_synthesis']['legacy_pending']=deepcopy(state['pending_synthesis'])


def owner(state, selected):
    from . import research_tree as tree
    paths=[tree.ancestors(state,r['node_id']) for r in selected]
    return next(i for i in reversed(paths[0]) if all(i in path for path in paths))


def context(state, group, selected, memories, *, objective=None, existing=()):
    """Complete selected units; bounded parent metadata, never a global catalogue."""
    identity=owner(state,selected)
    parents={m.id:m for m in memories}
    supplied={'root_question':state['nodes'][state['root_id']]['question'],
        'question':state['nodes'][identity]['question'],
        **questions.context(state,'S3' if objective else 'S2',identity),
        'candidate':{'id':group['id'],'reason':group['reason'],'relationships':group['relationships']},
        'knowledge_units':deepcopy(selected),
        'parent_memories':[{'id':i,'title':parents[i].title,'summary':parents[i].summary,
            'node_id':parents[i].metadata['node_id'],'question':state['nodes'][parents[i].metadata['node_id']]['question'],
            'guidance_questions':[{'id':i+'#'+u.anchor,'fields':dict(u.fields)} for u in parents[i].units if u.kind=='question'][:2]}
            for i in sorted({r['memory_id'] for r in selected})],
        'objective':deepcopy(objective), 'existing_knowledge':[
            {'id':r['id'],'reference':'Complete scientific content is already supplied in knowledge_units.'}
            if r['id'] in {u['id'] for u in selected} else r for r in existing]}
    return supplied if objective is not None else planning_context(supplied)


def planning_context(supplied):
    """Project current or saved pending S2 inputs without rewriting receipts.

    Only repeated tree-question metadata becomes a reference. Scientific units,
    source records, qualifications and the immutable research brief stay whole.
    S3 continues to receive its existing, separate execution contract.
    """
    result=deepcopy(supplied);result.pop('objective',None)
    seen={}
    def question(value, path):
        if not isinstance(value,str):return value
        key=normal(value)
        if key in seen:return {'same_as':seen[key]}
        seen[key]=path
        return value
    for key in ['root_question','question']:result[key]=question(result[key],key)
    for index,parent in enumerate(result['parent_memories']):
        parent['question']=question(parent['question'],f'parent_memories[{index}].question')
    return result


def usage(state, llm, action, supplied):
    return measure(decisions.request(llm.model,llm.settings,action,supplied),
        state.get('synthesis_output_reserve',state['output_reserve']),state['context_budget'],getattr(llm,'count_tokens',None))


def novelty_context(selected, all_records, limit=6):
    query=set().union(*(tokens(representation(r)) for r in selected))
    ranked=sorted(all_records,key=lambda r:(-len(query & tokens(representation(r))),r['id']))
    # Complete units, no shortened qualifications. Actual request is checked later.
    selected_ids={r['id'] for r in selected}
    # Compare with input conclusions too, without duplicating their prompt text.
    return list(selected)+[r for r in ranked if r['id'] not in selected_ids and query & tokens(representation(r))][:max(0,limit-len(selected))]


def select(state, memories, equations, llm, discovery, event):
    register=state['unit_synthesis'];all_records=records(state,memories,equations)
    groups,capability=discovery.discover(all_records)
    history=sorted(register['groups'].values(),key=lambda g:(g.get('selected_cycle',-1),g['id']))
    groups=diversify(groups,history)
    register['deferred_groups']=[]
    register['capability']=capability;event['embedding_capability']=capability
    lookup={r['id']:r for r in all_records};blocked=[]
    for group in groups:
        # No subset/superset/overlap exclusion and no completed-set rewording.
        if group['id'] in register['groups']:continue
        selected=[lookup[i] for i in group['unit_ids']]
        supplied=context(state,group,selected,memories)
        cost=usage(state,llm,'S2',supplied)
        estimate=context(state,group,selected,memories,objective={'objective':'S2 objective pending', 'unit_ids':group['unit_ids']},
            existing=novelty_context(selected,all_records))
        s3cost=usage(state,llm,'S3',estimate)
        group['context_requirements']={'s2':cost,'s3_estimate':s3cost,'s3_exact':'Measured again with the accepted objective before dispatch.'}
        if cost['over_context_budget'] or s3cost['over_context_budget']:
            blocked.append({'group_id':group['id'],'reason':'blocked_context_budget','usage':cost});continue
        group.update(status='selected',node_id=owner(state,selected),selected_event=event['event_id'],selected_cycle=event['cycle'],
            s2_interaction_id=None,objectives=[],reason_outcome=None,context=supplied)
        register['groups'][group['id']]=group;register['selected_group']=group['id']
        event.update(selection=deepcopy(group),unit_ids=group['unit_ids'],node_id=group['node_id'],reason='selected')
        return
    register['scanned']=catalogue(state,memories)
    register['deferred_groups']=blocked
    event.update(reason='no_fitting_candidate' if blocked else 'no_candidate',deferred_groups=blocked)


def bounded_text(value, limit=4000):
    require(isinstance(value,str) and value.strip() and len(value)<=limit and '\x00' not in value,'invalid synthesis text')


def references(ids, lookup):
    require(isinstance(ids,list) and len(ids)>=2 and all(isinstance(i,str) and i in lookup for i in ids)
        and len(set(ids))==len(ids),'invalid/unsupplied synthesis unit references')
    require(len({lookup[i]['memory_id'] for i in ids})>=2,'synthesis requires two distinct input memories')


def objective_id(idea, selected):
    return digest(dumps([fingerprint(selected),normal(idea['objective'])]))


def validate_s2(value, selected):
    decisions.fields(value,['disposition','ideas','reason']);bounded_text(value['reason'])
    require(value['disposition'] in {'ideas','no_candidate'} and isinstance(value['ideas'],list), 'invalid S2 disposition/ideas')
    require(bool(value['ideas'])==(value['disposition']=='ideas'),'S2 disposition/ideas mismatch')
    accepted=[];rejected=[];seen=set();lookup={r['id']:r for r in selected}
    for index,idea in enumerate(value['ideas']):
        try:
            require(index<3,'at most three S2 objectives')
            decisions.fields(idea,['category','objective','unit_ids','potential_new_understanding','limitations','novelty'])
            require(idea['category'] in {'comparison','integration','reconciliation','hypothesis','quantitative','methodological'},'invalid S2 category')
            for key in ['objective','potential_new_understanding','novelty']:bounded_text(idea[key],1600)
            references(idea['unit_ids'],lookup)
            require(isinstance(idea['limitations'],list) and 1<=len(idea['limitations'])<=8,'S2 limitations required')
            for limitation in idea['limitations']:bounded_text(limitation,1000)
            key=objective_id(idea,[lookup[i] for i in idea['unit_ids']])
            require(key not in seen,'duplicate S2 objective');seen.add(key)
            accepted.append((key,idea))
        except (ValueError,TypeError,KeyError) as exc:rejected.append({'index':index,'error':str(exc)})
    return accepted,rejected


def plan(state, memories, equations, llm, event, model):
    register=state['unit_synthesis'];group=register['groups'][register['selected_group']]
    event.update(action='S2',node_id=group['node_id'],question=state['nodes'][group['node_id']]['question'],group_id=group['id'],unit_ids=group['unit_ids'])
    current={r['id']:r for r in records(state,memories,equations)}
    require(all(v['id'] in current and current[v['id']]['version']==v['version'] for v in group['unit_versions']), 'selected S2 unit versions changed or ineligible')
    selected=[current[i] for i in group['unit_ids']]
    value=model(event,'S2',planning_context(group['context']),state)
    accepted,rejected=validate_s2(value,selected)
    event['rejected_components']=rejected
    require(not value['ideas'] or accepted,'all S2 proposals failed validation')
    group.update(status='evaluated',s2_interaction_id=event['interaction_id'],reason_outcome=value['reason'],
        disposition=value['disposition'],rejected_proposals=rejected)
    for key,idea in accepted:
        if key in register['objectives']:continue
        objective={'id':key,'group_id':group['id'],'proposal':deepcopy(idea),'status':'pending',
            'unit_versions':[{'id':i,'version':current[i]['version']} for i in sorted(idea['unit_ids'])],
            's3_interaction_id':None,'result_memory_id':None,'contributing_unit_ids':[],
            's2_interaction_id':event['interaction_id']}
        register['objectives'][key]=objective;group['objectives'].append(key)
    register['selected_group']=None
    event.update(disposition=value['disposition'],accepted_objectives=group['objectives'],rejected_components=rejected,
                 reason='no_valid_objectives' if value['ideas'] and not accepted else value['reason'])


def numeric_checks(checks, lookup):
    require(isinstance(checks,list) and len(checks)<=8,'invalid quantitative checks')
    for check in checks:
        decisions.fields(check,['operation','operands','result','assumptions'])
        bounded_text(check['assumptions'],1000)
        require(isinstance(check['operands'],list) and 2<=len(check['operands'])<=8,'invalid numeric operands')
        numbers=[]
        for operand in check['operands']:
            decisions.fields(operand,['unit_id','value','quote'])
            require(isinstance(operand['unit_id'],str) and operand['unit_id'] in lookup,'invalid numeric evidence reference')
            bounded_text(operand['quote'],2000);bounded_text(operand['value'],80)
            require(operand['quote'] in '\n'.join(lookup[operand['unit_id']]['fields'].values()),'numeric quote not in attributed unit')
            require(re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?',operand['value']), 'invalid numeric operand')
            number=Decimal(operand['value']);require(number.is_finite(),'nonfinite operand')
            quoted=re.findall(r'(?<![\w.])[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?!\w|\.\d)',operand['quote'].replace('−','-'))
            require(number in [Decimal(v) for v in quoted],'numeric operand not in quote')
            numbers.append(number)
        op=check['operation'];require(op in {'sum','difference','ratio','product','less_than','greater_than'},'unsupported arithmetic operation')
        with localcontext() as ctx:
            ctx.prec=50
            a,b=numbers[:2]
            if op=='sum':expected=sum(numbers)
            elif op=='product':
                expected=Decimal(1)
                for n in numbers:expected*=n
            else:
                require(len(numbers)==2,'binary numeric operation required')
                if op=='ratio':require(b!=0,'division by zero');expected=a/b
                elif op=='difference':expected=a-b
                elif op=='less_than':expected=a<b
                else:expected=a>b
            if isinstance(expected,bool):require(type(check['result']) is bool and check['result']==expected,'incorrect numerical inequality')
            else:
                require(isinstance(check['result'],str),'numeric result must be text')
                try:actual=Decimal(check['result'])
                except InvalidOperation:raise ValueError('invalid numeric result')
                require(actual.is_finite() and abs(actual-expected)<=abs(expected)*Decimal('1e-8'), 'incorrect numerical relationship')


def validate_s3(value, selected, existing):
    if value.get('disposition')=='no_synthesis':
        decisions.fields(value,['disposition','reason']);bounded_text(value['reason']);return []
    decisions.fields(value,['disposition','title','summary','findings'])
    require(value['disposition']=='synthesis','invalid S3 disposition')
    bounded_text(value['title'],300);bounded_text(value['summary'],2000)
    require(isinstance(value['findings'],list) and 1<=len(value['findings'])<=4,'one to four synthesis findings required')
    lookup={r['id']:r for r in selected};novelty_ids={r['id'] for r in existing}
    for finding in value['findings']:
        decisions.fields(finding,['label','proposition','explanation','qualification','epistemic_type','source_findings',
            'evidence_checks','quantitative_checks','novelty','novelty_comparisons'])
        for k in ['label','proposition','explanation','qualification','novelty']:bounded_text(finding[k],3000)
        require(finding['epistemic_type'] in {'inference','hypothesis'},'synthesis conclusions must be labelled inference or hypothesis')
        references(finding['source_findings'],lookup)
        require(any(lookup[i]['structural_type']=='finding' for i in finding['source_findings']), 'questions alone cannot establish synthesis evidence')
        checks=finding['evidence_checks'];require(isinstance(checks,list) and len(checks)==len(finding['source_findings']),'one attributed evidence check per contributing unit required')
        seen=set()
        for check in checks:
            decisions.fields(check,['unit_id','quote','use'])
            identity=check['unit_id'];require(isinstance(identity,str) and identity in finding['source_findings'] and identity not in seen,'invalid/duplicate evidence check')
            seen.add(identity);bounded_text(check['quote'],3000);bounded_text(check['use'],1000)
            require(check['quote'] in '\n'.join(lookup[identity]['fields'].values()),'misattributed evidence quotation')
        numeric_checks(finding['quantitative_checks'],{i:lookup[i] for i in finding['source_findings']})
        require(isinstance(finding['novelty_comparisons'],list),'novelty comparisons required')
        reviewed=set()
        for check in finding['novelty_comparisons']:
            decisions.fields(check,['unit_id','assessment','reason'])
            require(isinstance(check['unit_id'],str) and check['unit_id'] in novelty_ids and check['unit_id'] not in reviewed,'invalid novelty comparison reference')
            reviewed.add(check['unit_id'])
            require(check['assessment'] in {'distinct','equivalent','uncertain'},'invalid novelty assessment')
            bounded_text(check['reason'],1200)
        require(reviewed==novelty_ids,'review every supplied novelty candidate')
    return value['findings']


def novelty(findings, selected, all_records):
    lookup={r['id']:r for r in selected};accepted=[];audit=[]
    for finding in findings:
        leaves={leaf for i in finding['source_findings'] for leaf in lookup[i]['leaf_units']}
        redundant=[]
        for record in all_records:
            same=normal(finding['proposition'])==normal(record['fields'].get('Proposition','')) and normal(finding['qualification'])==normal(record['fields'].get('Qualification',''))
            reviewed=any(c['unit_id']==record['id'] and c['assessment']=='equivalent' for c in finding['novelty_comparisons'])
            if (same or reviewed) and leaves<=set(record['leaf_units']):redundant.append(record['id'])
        if redundant:audit.append({'label':finding['label'],'disposition':'redundant','existing_unit_ids':redundant})
        elif any(normal(finding['proposition'])==normal(f['proposition']) and normal(finding['qualification'])==normal(f['qualification']) and
                 leaves=={l for i in f['source_findings'] for l in lookup[i]['leaf_units']} for f in accepted):
            audit.append({'label':finding['label'],'disposition':'duplicate_within_output'})
        else:accepted.append(finding)
    return accepted,audit


def apply(state, memories, ledger, selected, findings, value, objective):
    lookup={r['id']:r for r in selected};contributors=sorted({i for f in findings for i in f['source_findings']})
    identity=owner(state,[lookup[i] for i in contributors])
    output_id='s'+base36(ledger['s']);ledger['s']+=1
    sources=[]
    for i in contributors:
        for source in lookup[i]['sources']:
            if source not in sources:sources.append(source)
    output=Memory(output_id,value['title'],value['summary'],metadata={'node_id':identity,'kind':'synthesis',
        'source_memories':sorted({lookup[i]['memory_id'] for i in contributors}),'synthesized_by':None,
        'lineage_mode':'knowledge_units','sources':sources,'created_order':len(memories)+1,'markdown_format':2,
        'synthesis_objective':objective['id'],
        'synthesis_unit_versions':[{'id':i,'version':lookup[i]['version']} for i in contributors],
        'scientific_validation':{'status':'unverified','checks':'Exact references/quotations, declared arithmetic and conservative novelty; not scientific proof.'}})
    for finding in findings:
        anchor=output.allocate('f')
        output.units.append(Unit(anchor,finding['label'],{'Kind':'synthesis','Evidence status':'unverified',
            'Proposition':finding['proposition'],'Explanation':finding['explanation'],'Qualification':finding['qualification'],
            'Epistemic type':finding['epistemic_type'],'Provenance':'S3 objective '+objective['id']+'; '+finding['novelty']}))
        for target in finding['source_findings']:output.relationships.append(Relationship(anchor,'SYNTHESIZES',target,'unverified'))
    memories.append(output);state['nodes'][identity]['memory_ids'].append(output.id)
    return output


def execute(state, memories, equations, ledger, llm, event, model):
    register=state['unit_synthesis'];objective=next(o for o in register['objectives'].values() if o['status']=='pending')
    group=register['groups'][objective['group_id']];all_records=records(state,memories,equations);lookup={r['id']:r for r in all_records}
    event.update(action='S3',objective_id=objective['id'],group_id=group['id'],node_id=group['node_id'],question=state['nodes'][group['node_id']]['question'])
    require(all(v['id'] in lookup and lookup[v['id']]['version']==v['version'] for v in objective['unit_versions']), 'S3 evidence versions changed or ineligible')
    selected=[lookup[v['id']] for v in objective['unit_versions']]
    existing=novelty_context(selected,all_records)
    supplied=context(state,group,selected,memories,objective=objective['proposal'],existing=existing)
    cost=usage(state,llm,'S3',supplied);event['context_requirements']=cost
    if cost['over_context_budget']:
        # Whole selected units are preserved; never silently drop evidence to fit.
        objective.update(status='blocked_context',reason='blocked_context_budget')
        event.update(reason='blocked_context_budget',disposition='deferred');return
    value=model(event,'S3',supplied,state)
    findings=validate_s3(value,selected,existing)
    accepted,audit=novelty(findings,selected,all_records)
    output=apply(state,memories,ledger,selected,accepted,value,objective) if accepted else None
    contributors=sorted({i for f in accepted for i in f['source_findings']})
    objective.update(status='completed',disposition='synthesis' if output else 'no_synthesis',
        reason=value.get('reason',value.get('summary','')),s3_interaction_id=event['interaction_id'],
        contributing_unit_ids=contributors,result_memory_id=output.id if output else None,novelty_audit=audit)
    event.update(disposition=objective['disposition'],novelty_audit=audit,contributing_unit_ids=contributors,
        memory_ids=[output.id] if output else [],generated_memories=[] if output is None else [render(output)])


def fail(state, event):
    """Durable failures never count as scientific rejections or auto retry."""
    register=state.get('unit_synthesis')
    if register is None:return
    if event.get('action')=='S2' and register['selected_group']:
        group=register['groups'][register['selected_group']]
        group.update(status='failed',s2_interaction_id=event.get('interaction_id'),reason_outcome=event['error'])
        register['selected_group']=None
    elif event.get('action')=='S3' and event.get('objective_id') in register['objectives']:
        register['objectives'][event['objective_id']].update(status='failed',reason=event['error'],s3_interaction_id=event.get('interaction_id'))


def validate_register(state, memories, files):
    register=state['unit_synthesis'];require(register.get('version')==1,'invalid unit synthesis version')
    require(isinstance(register['groups'],dict) and isinstance(register['objectives'],dict),'invalid synthesis registers')
    require(type(register['burst']) is int and 0<=register['burst']<=3,'invalid synthesis burst')
    selected=register['selected_group'];require(selected is None or selected in register['groups'],'invalid pending S2 group')
    docs={m.id:m for m in memories}
    events={p[7:-5]:loads(raw) for p,raw in files.items() if p.startswith('events/')}
    interactions={e['interaction_id']:e for e in events.values() if e.get('interaction_id')}
    for key,g in register['groups'].items():
        require(g['id']==key and g['status'] in {'selected','evaluated','failed'},'invalid synthesis group')
        require(g['node_id'] in state['nodes'] and set(g['memory_ids'])<=set(docs),'missing synthesis parent')
        require(key==digest(dumps(sorted((v['id'],v['version']) for v in g['unit_versions']))),'invalid synthesis group fingerprint')
        require(g['unit_ids']==[v['id'] for v in g['unit_versions']] and len(set(g['unit_ids']))==len(g['unit_ids']),'invalid synthesis group versions')
        require((g['status']=='selected')==(selected==key),'inconsistent pending S2')
        require(g['status']=='selected' or g.get('s2_interaction_id') is not None or g['status']=='failed','missing S2 interaction')
        selection=events.get(g['selected_event'],{})
        require(selection.get('action_committed')=='S1' and selection.get('selection',{}).get('unit_versions')==g['unit_versions'],
            'synthesis group lacks committed S1 selection')
        if g.get('s2_interaction_id'):
            e=interactions.get(g['s2_interaction_id'],{})
            require(e.get('action')=='S2' and e.get('group_id')==key,'missing S2 interaction event')
    for key,o in register['objectives'].items():
        require(o['id']==key and o['group_id'] in register['groups'] and o['status'] in {'pending','completed','failed','blocked_context'},'invalid S3 objective')
        g=register['groups'][o['group_id']]
        require(g['status']=='evaluated' and key in g['objectives'] and o['s2_interaction_id']==g['s2_interaction_id'],'objective lacks S2 evaluation')
        require(set((v['id'],v['version']) for v in o['unit_versions'])<=set((v['id'],v['version']) for v in g['unit_versions']),'S3 evidence not selected by S2')
        require(key==digest(dumps([digest(dumps(sorted((v['id'],v['version']) for v in o['unit_versions']))),normal(o['proposal']['objective'])])),'invalid S3 objective fingerprint')
        if o['status']=='completed':
            require(o['s3_interaction_id'] and o['disposition'] in {'synthesis','no_synthesis'},'invalid S3 completion')
            if o['disposition']=='synthesis':
                output=docs.get(o['result_memory_id'])
                require(output is not None and output.metadata.get('synthesis_objective')==key,'S3 result mismatch')
                actual=sorted({e.target for e in output.relationships if e.type=='SYNTHESIZES'})
                require(actual==o['contributing_unit_ids'] and set(actual)<=set(o['proposal']['unit_ids']),'S3 contributor mismatch')
            else:require(o['result_memory_id'] is None and not o['contributing_unit_ids'],'no_synthesis published evidence')
            e=interactions.get(o['s3_interaction_id'],{})
            require(e.get('action_committed')=='S3' and e.get('objective_id')==key
                and e.get('memory_ids',[])==([o['result_memory_id']] if o['result_memory_id'] else []),'missing committed S3 publication')
