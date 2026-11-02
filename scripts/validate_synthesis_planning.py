#!/usr/bin/env python3
"""Compare production S1 rankings and replay saved S2 groups on disposable copies.

No literature retrieval or S3 publication is performed. Historical prompts and
responses are controls, not newly generated evidence. Full new model receipts
and controller journals remain in the diagnostic output and temporary copies.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
import time

from mira import synthesis as sy, synthesis_discovery as sd
from mira.clients import HTTPModel
from mira.embeddings import NomicHTTPEmbedding
from mira.experiments import atomic_text
from mira.format import dumps, loads, render, digest, require
from mira.interactions import read_records
from mira.research import Research
from validate_unit_synthesis import snapshot, due, get


class ReplayGroup:
    """Select a specified historical group; deliberately not an S1 ranking trial."""
    def __init__(self, group, backend):
        self.group={k:deepcopy(v) for k,v in group.items() if k!='controls'}
        self.backend=backend
    def discover(self, records):
        actual={(r['id'],r['version']) for r in records}
        require(all((v['id'],v['version']) in actual for v in self.group['unit_versions']),
                'Historical scientific unit missing or changed; never repair evidence')
        return [deepcopy(self.group)],{'mode':'historical_group_replay','semantic':False,
            'reason':'Controlled S2 comparison, not a newly ranked S1 selection.'}


def historical(paths):
    groups={}
    for path in paths:
        result=loads(path.read_text())
        for index,interaction in enumerate(result['interactions']):
            if interaction['request']['action']!='S2':continue
            context=interaction['request']['context'];units=context['knowledge_units']
            key=sd.fingerprint(units)
            entry=groups.setdefault(key,{'id':key,'unit_ids':sorted(r['id'] for r in units),
                'unit_versions':sorted([{'id':r['id'],'version':r['version']} for r in units],key=lambda v:v['id']),
                'memory_ids':sorted({r['memory_id'] for r in units}), 'priority':0.,
                'reason':'Controlled replay of a previously selected medical group.',
                'relationships':context['candidate']['relationships'],'controls':[]})
            entry['controls'].append({'path':str(path),'index':index,'interaction':interaction})
    return list(groups.values())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('memory'))
    parser.add_argument('--previous',type=Path,nargs='+',required=True)
    parser.add_argument('--baseline-discovery',type=Path,required=True,help='Unchanged baseline module saved before implementation')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ranked-groups',type=int,default=5)
    args=parser.parse_args();out=args.output.absolute();out.mkdir(parents=True,exist_ok=True)
    require(not (out/'result.json').exists(),'Never overwrite completed validation')
    model=get('http://127.0.0.1:8090/v1/models')['data'][0]['id']
    props=get('http://127.0.0.1:8091/props');artifact=Path(props['model_path']);h=hashlib.sha256()
    with artifact.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    backend=NomicHTTPEmbedding('http://127.0.0.1:8091',str(artifact)+':sha256:'+h.hexdigest())
    llm=HTTPModel('http://127.0.0.1:8090',model,temperature=0,max_tokens=4096,timeout=300,no_thinking=True,json_output=True)
    work=Path(tempfile.mkdtemp(prefix='mira-synthesis-planning-'));base=work/'source'
    original=snapshot(args.source.absolute(),base)
    reader=Research(base,llm,{},embedding_backend=backend)
    with reader.store.lock():
        _,docs,eqs,_=reader.store.read();state=loads(reader.store._files()['research/state.json'])
    require(not sy.pending(state) and not state.get('pending_synthesis'),'Pending synthesis requires review')
    units=sy.records(state,docs,eqs)
    spec=importlib.util.spec_from_file_location('mira._validation_baseline_discovery',args.baseline_discovery)
    baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    started=time.perf_counter()
    with reader.store.lock():
        before,before_capability=baseline.Discovery(reader.store,backend).discover(units)
        after,after_capability=reader.synthesis_discovery.discover(units)
    require({g['id'] for g in before}<={g['id'] for g in after},'Original candidate opportunities were discarded')
    ranking={'previous':before,'revised':after,'previous_capability':before_capability,
             'revised_capability':after_capability,'baseline_sha256':digest(args.baseline_discovery.read_text())}
    groups=historical(args.previous);history=[];ranked=[]
    for index in range(args.ranked_groups):
        candidates=sd.diversify([g for g in after if g['id'] not in {old['id'] for old in history}],history)
        chosen=None
        for group in candidates:
            selected=[r for r in units if r['id'] in group['unit_ids']]
            context=sy.context(state,group,selected,docs)
            estimate=sy.context(state,group,selected,docs,objective={'objective':'S2 objective pending','unit_ids':group['unit_ids']},existing=sy.novelty_context(selected,units))
            if not any(sy.usage(state,llm,action,value)['over_context_budget'] for action,value in [('S2',context),('S3',estimate)]):
                chosen=group;break
        if chosen is None:break
        history.append(chosen);ranked.append(chosen)
        if chosen['id'] not in {g['id'] for g in groups}:groups.append({**chosen,'controls':[]})
    ranking['revised_first_fitting_with_diversity']=ranked
    atomic_text(out/'ranking.json',dumps(ranking))
    trials=[]
    for index,group in enumerate(groups):
        root=work/f'group-{index+1:02}';shutil.copytree(base,root)
        research=Research(root,llm,{},embedding_backend=backend)
        research.synthesis_discovery=ReplayGroup(group,backend)
        initial=len(read_records(root));trial_started=time.perf_counter();actions=[]
        with research.execution(out/f'group-{index+1:02}',command='controlled-s2-planning-validation'):
            due(research)
            for expected in ['S1','S2']:
                action=research.step();actions.append(action)
                if action.get('action')!=expected or action['status']!='committed':break
        with research.store.lock():
            _,current,_,_=research.store.read();saved=loads(research.store._files()['research/state.json'])
        unchanged={m.id:digest(render(m)) for m in current}==original['original_memory_hashes']
        require(unchanged,'Planning must not publish or modify memories')
        trial={'group':group,'copy':str(root),'elapsed_seconds':time.perf_counter()-trial_started,
            'actions':actions,'interactions':read_records(root)[initial:],
            'objectives':saved['unit_synthesis']['objectives'],'memories_preserved':unchanged}
        trials.append(trial);atomic_text(out/'progress.json',dumps({'trials':trials}))
        print(json.dumps({'group':index+1,'historical_controls':len(group['controls']),
            'status':actions[-1]['status'],'objectives':len(trial['objectives'])}),flush=True)
        require(actions[-1].get('action')=='S2' and actions[-1]['status']=='committed','Blocked or rejected planning; inspect preserved receipts, no automatic retry')
    atomic_text(out/'result.json',dumps({'source_snapshot':original,'source':str(args.source.absolute()),
        'work':str(work),'model':model,'settings':llm.settings,'context_window':llm.context_window,
        'embedding_identity':backend.identity,'ranking':ranking,'trials':trials,'elapsed_seconds':time.perf_counter()-started}))
    print('Saved validation:',out/'result.json',flush=True)


if __name__=='__main__':main()
