#!/usr/bin/env python3
"""Bounded local-Qwen R1 comparison using disposable terminology-only fixtures.

No production corpus or providers are opened. The pre-change R1 template must be
supplied explicitly; all complete interactions use Mira's existing log facilities.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import os
import shutil
import tempfile
import time
from urllib.request import urlopen

from mira.clients import HTTPModel
from mira.experiments import atomic_text
from mira.format import digest, dumps, loads
from mira.interactions import read_records
from mira.research import Research
from mira import research_tree as tree

QUESTION='What scientific terminology is useful for assessing volume doubling time, spiculation, and SUVmax in pulmonary nodule imaging?'
AMBIGUOUS='What does APC mean in a scientific report when its abbreviation is not expanded and the specialty and experimental method are unspecified?'


class CountedModel(HTTPModel):
    calls=0
    def complete(self,serialized):
        self.calls+=1
        return super().complete(serialized)


@contextmanager
def template_override(directory):
    previous=os.environ.get('MIRA_PROMPT_TEMPLATES')
    if directory is None:os.environ.pop('MIRA_PROMPT_TEMPLATES',None)
    else:os.environ['MIRA_PROMPT_TEMPLATES']=str(directory)
    try:yield
    finally:
        if previous is None:os.environ.pop('MIRA_PROMPT_TEMPLATES',None)
        else:os.environ['MIRA_PROMPT_TEMPLATES']=previous


def seed(research,terms):
    passage=' '.join(t+' is mentioned in this synthetic terminology fixture without defining its meaning.' for t in terms)
    evidence={'reference':'research/results/synthetic-terminology.json','results':[{'id':'synthetic-terminology',
        'content':passage,'title':'Controlled terminology mentions, not scientific findings'}]}
    values=[{'term':t,'definition':None,'aliases':[],'relationships':[],
        'source_id':'synthetic-terminology','passage':passage,'qualification':'Synthetic test mention; not scientific evidence.'} for t in terms]
    with research.store.lock():
        token,docs,eqs,ledger=research.store.read();s=loads(research.store._files()['research/state.json'])
        files,audit=research.glossary.proposals(s,values,evidence,'q1')
        assert not audit['rejected']
        research.store.publish(docs,eqs,ledger,token,files={**files,'research/state.json':dumps(s)})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-template',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.absolute()
    assert not (out/'controlled-results.json').exists(),'Never overwrite completed validation'
    out.mkdir(parents=True,exist_ok=True)
    with urlopen('http://127.0.0.1:8090/v1/models',timeout=10) as response:model=loads(response.read().decode())['data'][0]['id']
    llm=CountedModel('http://127.0.0.1:8090',model,temperature=0,max_tokens=4096,no_thinking=True,json_output=True)
    assert llm.context_window==16384
    base=Path(tempfile.mkdtemp(prefix='mira-r1-definitions-'))
    templates=base/'old-templates';shutil.copytree(Path(__file__).resolve().parents[1]/'prompt_templates',templates)
    (templates/'R1.txt').write_bytes(args.before_template.read_bytes())
    rows=[];contexts={}
    for label,question,terms,override in [('before',QUESTION,['Volume doubling time','Spiculation','SUVmax'],templates),
            ('after',QUESTION,['Volume doubling time','Spiculation','SUVmax'],None),
            ('ambiguous',AMBIGUOUS,['APC'],None)]:
        root=base/label;research=Research(root,llm,{})
        with template_override(override),research.execution(out,command='controlled-r1-'+label):
            research.initialize(question,['fixture'],context_budget=16384,output_reserve=4096)
            seed(research,terms)
            count=llm.calls;started=time.perf_counter();event=research.step()
            assert llm.calls-count==1,'one model call per R1'
            record=read_records(root)[0];contexts[label]=record['request']['context']
            row={'label':label,'root':str(root),'seconds':time.perf_counter()-started,
                'event':event,'interaction':record,'llm_calls':1,
                'glossary':[loads(p.read_text()) for p in sorted((root/'glossary').glob('g*.json'))]}
            rows.append(row)
            if label=='after' and event['status']=='committed':
                # Explicitly reset only this disposable fixture's search cursor
                # to inspect a subsequent R1. No provider action is performed.
                with research.store.lock():
                    token,docs,eqs,ledger=research.store.read();state=loads(research.store._files()['research/state.json'])
                    state['nodes']['q1'].update(keywords=None,next_database_index=0)
                    tree.refresh(state,docs)
                    research.store.publish(docs,eqs,ledger,token,files={'research/state.json':dumps(state)})
                count=llm.calls;started=time.perf_counter();followup=research.step()
                assert llm.calls-count==1
                rows.append({'label':'followup','root':str(root),'seconds':time.perf_counter()-started,
                    'event':followup,'interaction':read_records(root)[-1],'llm_calls':1,
                    'glossary':[loads(p.read_text()) for p in sorted((root/'glossary').glob('g*.json'))]})
            if label=='after':
                with research.store.lock():research.glossary.export(loads(research.store._files()['research/state.json']))
    result={'temporary_base':str(base),'model':model,'settings':llm.settings,
        'before_after_context_equal':contexts['before']==contexts['after'],'actions':rows,'total_llm_calls':llm.calls}
    atomic_text(out/'controlled-results.json',dumps(result))
    for row in rows:
        event=row['event'];proposal=row['interaction'].get('validation',{}).get('proposed_response')
        print(dumps({'label':row['label'],'action':event.get('action'),'status':event['status'],
            'seconds':row['seconds'],'context_usage':event.get('context_usage'),'response':proposal,
            'definition_admission':event.get('provisional_definitions')}))
    print('Equivalent starting contexts:',result['before_after_context_equal'])


if __name__=='__main__':main()
