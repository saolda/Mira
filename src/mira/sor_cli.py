"""Explicit SOR generation and read-only viewing commands."""
import os
from pathlib import Path
from urllib.parse import urlsplit,urlencode
from urllib.request import Request,urlopen

from .format import loads,require
from .experiments import Experiments
from .clients import HTTPModel
from .state_of_research import Generator,capture,generation_lock,publish,load


def register(sub):
    generate=sub.add_parser('state-of-research-generate',help='explicitly generate, challenge and revise a snapshot-bound scientific report')
    generate.add_argument('--experiment')
    generate.add_argument('--resume',help='resume only safely received exact requests from an existing generation ID')
    generate.add_argument('--llm-url',help='existing local model endpoint (default localhost:8090)')
    generate.add_argument('--model',help='served model identity; otherwise discover a single local model')
    generate.add_argument('--max-tokens',type=int,default=4096)
    generate.add_argument('--timeout',type=float,default=240)
    generate.add_argument('--max-calls',type=int,default=40)
    generate.add_argument('--log-dir',help='private diagnostic directory outside the canonical corpus')
    view=sub.add_parser('state-of-research-view',help='inspect an existing completed report without model calls')
    view.add_argument('--experiment')
    view.add_argument('--open',action='store_true',help='open the existing local Mira viewer report route')
    view.add_argument('--format',choices=['markdown','html','json'],help='print the saved report or audit')


def execute(args):
    require(not args.root,'SOR commands select --memory-dir/--experiment, not a Phase 1 --root')
    catalog=Experiments(args.memory_dir);name=args.experiment or catalog.active_name()
    if args.command=='state-of-research-view':
        result=load(catalog,name)
        if args.format:
            if args.format=='json':return result
            if args.format=='html':
                from .sor_view import html
                return html(result['audit'],stale=result['stale'])
            from .sor_view import markdown
            return ('Research has changed since this report was generated.\n\n' if result['stale'] else '')+markdown(result['audit'])
        url='http://127.0.0.1:8767/state-of-research?'+urlencode({'experiment':name})
        if args.open:
            import webbrowser
            webbrowser.open(url)
        return {'url':url,'html_path':str(catalog.select(name)/'research/state_of_research.html'),
                'revision':result['audit']['paper']['source_revision'],'current_revision':result['current_revision'],'stale':result['stale']}
    require(3<=args.max_calls<=40,'SOR call limit must be between 3 and 40')
    require(args.max_tokens>0 and args.timeout>0,'SOR output tokens and timeout must be positive')
    endpoint=args.llm_url or os.environ.get('MIRA_LLM_URL','http://127.0.0.1:8090')
    require(urlsplit(endpoint).hostname in {'127.0.0.1','localhost','::1'},'SOR generation requires the configured local model; external model service is not authorized')
    model=args.model or os.environ.get('MIRA_LLM_MODEL');key=os.environ.get('MIRA_LLM_API_KEY')
    if not model:
        route=endpoint.rstrip('/')+('/models' if endpoint.rstrip('/').endswith('/v1') else '/v1/models')
        with urlopen(Request(route,headers={'Authorization':'Bearer '+key} if key else {}),timeout=args.timeout) as response:
            served=loads(response.read().decode())['data']
        require(len(served)==1,'Specify --model when multiple local models are served');model=served[0]['id']
    llm=HTTPModel(endpoint,model,api_key=key,temperature=0,max_tokens=args.max_tokens,timeout=args.timeout,json_output=True,no_thinking=True)
    directory=Path(os.path.abspath(args.log_dir)) if args.log_dir else catalog.home.parent/'log'/'state-of-research'
    require(not directory.is_relative_to(Path(os.path.abspath(catalog.home))),'SOR diagnostics must be outside the research corpus')
    with generation_lock(directory,catalog.select(name)):
        snapshot,evidence=capture(catalog,name)
        generator=Generator(llm,directory,max_calls=args.max_calls,resume_id=args.resume)
        audit=generator.run(evidence);result=publish(catalog,audit)
        result['diagnostic_directory']=str(generator.directory)
        return result
