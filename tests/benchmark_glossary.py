"""Reproduce glossary scaling: PYTHONPATH=src:tests python3 tests/benchmark_glossary.py."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import statistics,time
from mira.decisions import ScriptedLLM
from mira.research import Research
from mira.format import dumps,loads
from mira import r1
from test_glossary import seed_benchmark
with TemporaryDirectory(prefix='mira-glossary-benchmark-') as directory:
 r=Research(directory,ScriptedLLM([{'keywords':['pulmonary granuloma 1', 'inflammation']}]),{})
 r.initialize('Which pulmonary masses involve granuloma or infection?',['fixture'],context_budget=24000)
 start=time.perf_counter();state=seed_benchmark(r);setup=time.perf_counter()-start
 with r.store.lock():context=r1.context(state,[],r.store._files(),'q1')
 timings=[];reads=[]
 for i in range(30):
  before=r.glossary.records_read;start=time.perf_counter()
  with r.store.lock():result=r.glossary.retrieve(state,context,'q1')
  timings.append((time.perf_counter()-start)*1000);reads.append(r.glossary.records_read-before)
 original=Path.read_text; actual=[]
 def tracked(path,*args,**kwargs):
  if path.parent.name=='glossary':actual.append(path.name)
  return original(path,*args,**kwargs)
 with patch.object(Path,'read_text',tracked):
  start=time.perf_counter();event=r.step();elapsed=time.perf_counter()-start
 summary={'entries':10000,'setup_and_explicit_rebuild_seconds':round(setup,3),'retrieval_runs':len(timings),'retrieval_mean_ms':round(statistics.mean(timings),3),'retrieval_median_ms':round(statistics.median(timings),3),'retrieval_max_ms':round(max(timings),3),'selected_entries':len(result['entries']),'glossary_context_bytes':len(dumps(result).encode()),'configured_token_upper_bound':state['glossary']['token_budget'],'canonical_records_read_per_retrieval':sorted(set(reads)),'full_R1_cycle_seconds':round(elapsed,3),'full_R1_canonical_term_file_reads':len(actual),'full_R1_distinct_term_records':len(set(actual)),'full_R1_status':event['status'],'full_R1_context_tokens_upper_bound':event.get('context_usage',{}).get('prompt_tokens')}
 print(dumps(summary))
