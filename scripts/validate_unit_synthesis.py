#!/usr/bin/env python3
"""Bounded production S1-S3 check on a disposable copy, never the active corpus.

Only the disposable scheduling cadence is advanced, to exercise synthesis without
issuing literature searches or changing scientific questions/statuses. Complete
interaction records and journals stay locally inspectable; outputs are not facts
merely because they pass structural validation.
"""
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import tempfile
import time
from urllib.request import urlopen

from mira.clients import HTTPModel
from mira.embeddings import NomicHTTPEmbedding
from mira.experiments import existing_reader, atomic_text
from mira.format import Memory, Unit, digest, dumps, loads, render, require
from mira.interactions import read_records
from mira.research import Research
from mira import synthesis as sy, research_tree as tree


def get(url):
    with urlopen(url,timeout=10) as response:return json.load(response)


def snapshot(source,destination):
    with existing_reader(source,blocking=False) as store:
        revision,docs,eqs,ledger=store.read()
        files=store._files();state=loads(files['research/state.json'])
        require(state.get('pending_synthesis') is None,'Historical pending synthesis requires review')
        committed={loads(raw).get('interaction_id') for p,raw in files.items() if p.startswith('events/')}
        require(not any('outcome' not in r and r['id'] not in committed for r in read_records(source)),'Uncertain existing model submission')
        destination.mkdir()
        for name in ['memories','equations','events','journal','glossary','interactions','retrieval_calls']:
            path=source/name
            if path.exists():shutil.copytree(path,destination/name,symlinks=True)
        (destination/'research').mkdir()
        for name in ['state.json','question.md']:
            path=source/'research'/name
            if path.exists():shutil.copyfile(path,destination/'research'/name)
        if (source/'research/results').exists():shutil.copytree(source/'research/results',destination/'research/results',symlinks=True)
        shutil.copyfile(source/'identity.json',destination/'identity.json')
    return {'revision':revision,'memories':len(docs),'original_memory_hashes':{m.id:digest(render(m)) for m in docs}}


def due(research):
    with research.store.lock():
        token,docs,eqs,ledger=research.store.read();state=tree.upgrade(loads(research.store._files()['research/state.json']),docs)
        state['research_cycles_since_synthesis']=state['synthesis_interval']
        tree.refresh(state,docs)
        research.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)},operation_type='validation_cadence')


def mathematical_fixture(root,llm,backend,matched=False):
    research=Research(root,llm,{},embedding_backend=backend)
    question=('What change and ratio follow from the two defined matched energy measurements, without treating them as independent replications?' if matched else 'Under the defined spherical constant-shape exponential growth model, what diameter doubling interval follows from a volume doubling interval of 28 days?')
    research.initialize(question,
        ['fixture'],context_budget=llm.context_window,output_reserve=4096)
    premises=[('Geometry identity','For a sphere of diameter D, volume V = (pi/6) * D^3; the exponent is 3.',
        'An exact mathematical identity for spheres; constant shape is assumed, not measured in patients.'),
        ('Specified exponential model','In this defined hypothetical model, volume grows exponentially at a constant rate and doubles every 28 days.',
        'A defined mathematical example, not an empirical observation, study or claim about any pulmonary lesion.')]
    if matched:
        premises=[('Defined initial energy','In this hypothetical matched measurement fixture, initial energy is 4 joules.',
            'A defined artificial numeric premise under the same conditions and units as the final measurement; not a real study.'),
            ('Defined final energy','In this hypothetical matched measurement fixture, final energy is 8 joules.',
            'A second defined artificial numeric premise from the same fixture; not independent replication or a real study.')]
    with research.store.lock():
        token,docs,eqs,ledger=research.store.read();state=loads(research.store._files()['research/state.json'])
        for index,(title,text,qualification) in enumerate(premises,1):
            m=Memory('r'+str(index),title,'Independently checkable mathematical premise; no empirical study.',
                metadata={'node_id':'q1','kind':'research','source_memories':[],'synthesized_by':None,'created_order':index,
                    'source':{'id':'defined-mathematical-fixture-'+str(index),'url':'https://example.org/mira-defined-mathematical-fixture-'+str(index)}})
            m.units.append(Unit(m.allocate('f'),'Claim',{'Kind':'claim','Proposition':text,'Qualification':qualification}))
            docs.append(m);state['nodes']['q1']['memory_ids'].append(m.id)
        ledger['r']=3;tree.refresh(state,docs)
        fixture_revision=research.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)},operation_type='defined_fixture')
    return {'revision':fixture_revision,'memories':2,'original_memory_hashes':{m.id:digest(render(m)) for m in docs},
        'qualification':'Defined mathematical premises, independently checkable by algebra; no new medical evidence or independent empirical studies.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('memory'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-actions',type=int,default=10)
    parser.add_argument('--mathematical-fixture',action='store_true',help='Use explicitly defined algebraic premises; never fabricate medical findings')
    parser.add_argument('--matched-measurements',action='store_true',help='Use defined matched 4-J and 8-J premises instead of power-law geometry')
    args=parser.parse_args();out=args.output.absolute();out.mkdir(parents=True,exist_ok=True)
    require(not (out/'result.json').exists(),'Never overwrite completed validation')
    model=get('http://127.0.0.1:8090/v1/models')['data'][0]['id']
    embedding_props=get('http://127.0.0.1:8091/props');artifact=Path(embedding_props['model_path'])
    h=hashlib.sha256()
    with artifact.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    backend=NomicHTTPEmbedding('http://127.0.0.1:8091',str(artifact)+':sha256:'+h.hexdigest())
    llm=HTTPModel('http://127.0.0.1:8090',model,temperature=0,max_tokens=4096,timeout=300,no_thinking=True,json_output=True)
    root=Path(tempfile.mkdtemp(prefix='mira-production-synthesis-'))/('mathematical-fixture' if args.mathematical_fixture else 'medical')
    original=mathematical_fixture(root,llm,backend,matched=args.matched_measurements) if args.mathematical_fixture else snapshot(args.source.absolute(),root)
    actions=[];started=time.perf_counter();initial_interactions=len(read_records(root))
    research=Research(root,llm,{},embedding_backend=backend)
    with research.execution(out,command='validate-production-unit-synthesis'):
        for index in range(args.max_actions):
            due(research)
            # Restart the actual controller while preserving the execution logger.
            restarted=Research(root,llm,{},embedding_backend=backend);restarted.trace=research.trace;research=restarted
            event=research.step();actions.append(event)
            atomic_text(out/'progress.json',dumps({'root':str(root),'actions':actions}))
            print(json.dumps({'action':event.get('action'),'status':event['status'],'disposition':event.get('disposition'),
                'reason':event.get('reason'),'error':event.get('error'),'group':event.get('group_id'),
                'objective':event.get('objective_id')}),flush=True)
            if event.get('action') not in {'S1','S2','S3'} or event['status']!='committed':break
            with research.store.lock():
                _,docs,eqs,ledger=research.store.read();state=loads(research.store._files()['research/state.json'])
            if any(e.get('action')=='S3' for e in actions) and not sy.pending(state):break
    with research.store.lock():
        revision,docs,eqs,ledger=research.store.read();state=loads(research.store._files()['research/state.json'])
    interactions=read_records(root)[initial_interactions:]
    before_calls=len(read_records(root));before_groups=set(state['unit_synthesis']['groups'])
    # Exact register checks are read-only. Discovery itself does not consume work.
    units=sy.records(state,docs,eqs)
    with research.store.lock():groups,capability=research.synthesis_discovery.discover(units)
    evaluated={k for k,v in state['unit_synthesis']['groups'].items() if v['status']=='evaluated'}
    replay_suppressed=[g['id'] for g in groups if g['id'] in evaluated]
    research._recover_outcomes()
    require(len(read_records(root))==before_calls,'Outcome recovery must not dispatch')
    preserved={m.id:digest(render(m)) for m in docs if m.id in original['original_memory_hashes']}==original['original_memory_hashes']
    result={'root':str(root),'source':'defined-mathematical-fixture' if args.mathematical_fixture else str(args.source.absolute()),'source_snapshot':original,
        'settings':llm.settings,'model':llm.model,'context_window':llm.context_window,
        'embedding_identity':backend.identity,'embedding_props':embedding_props,
        'elapsed_seconds':time.perf_counter()-started,'actions':actions,'interactions':interactions,
        'state':state,'outputs':[render(m) for m in docs if m.id not in original['original_memory_hashes']],
        'source_memories_preserved':preserved,'replay_suppressed_group_ids':replay_suppressed,
        'postcheck_capability':capability,'recovery_dispatched_calls':0,'canonical_validation':research.knowledge.validate()}
    atomic_text(out/'result.json',dumps(result))
    print('Saved validation:',out/'result.json',flush=True)


if __name__=='__main__':main()
