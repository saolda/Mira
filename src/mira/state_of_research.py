"""Evidence-constrained State of Research generation; canonical corpus stays read-only."""
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import fcntl
import json
from pathlib import Path
import time
import uuid

from . import decisions, glossary_definitions as definitions
from .budget import measure
from .experiments import existing_reader, confined, atomic_text
from .format import digest, dumps, loads, require
from .glossary import Directory
from .glossary_enrichment import model_identity
from .interactions import now, configured_secrets, scrub
from .knowledge_inspection import KnowledgeInspector
from .sor_contracts import SECTIONS, contract, validate_draft, validate_review, validate_revision, scientific_checks, cited_units

ARTIFACTS = ('research/state_of_research.md','research/state_of_research.html','research/state_of_research.audit.json')


def project(snapshot, glossary=(), *, experiment=None):
    """Complete scientific units and qualifications; no inference or text shortening."""
    units={}
    for row in snapshot['units']:
        units[row['id']]={k:deepcopy(row.get(k)) for k in ('id','version','memory_id','node_id','structural_type',
            'scientific_type','label','fields','origin','evidence_status','question_state','sources','source_ids',
            'contributing_units','leaf_units','scientific_validation','evidence_ref')}
        if 'equation' in row: units[row['id']]['equation']=deepcopy(row['equation'])
    glossary_rows={}
    nodes={n['id']:n for n in snapshot['nodes']}
    for record in glossary:
        node=record['node_ids'][0];scope=definitions.context(nodes[node]['question'],node,record['node_ids']) if node in nodes else None
        preferred=definitions.preferred(record,scope)
        glossary_rows[record['id']]={'id':record['id'],'term':record['term'],'aliases':record['aliases'],
            'definition':deepcopy(preferred[0]) if preferred else None,
            'status':record['status'],'enrichment':deepcopy((record.get('enrichment') or [{}])[-1]),
            'evidence':deepcopy(record['evidence'])}
    result={'schema':'mira.sor.evidence/1','source_schema':snapshot['schema'],'revision':snapshot['revision'],
        'experiment':experiment,'identity':deepcopy(snapshot['identity']),'inventory':deepcopy(snapshot['inventory']),
        'coverage':deepcopy(snapshot['coverage']),'node_statuses':deepcopy(snapshot['node_statuses']),
        'research_questions':{n['id']:{k:n.get(k) for k in ('question','parent_id','child_ids','status')} for n in snapshot['nodes']},
        'synthesis_summary':deepcopy(snapshot['synthesis_summary']),
        'units':units,'sources':{r['source']['id']:deepcopy(r['source']) for r in snapshot['sources']},
        'relationships':deepcopy(snapshot['relationships']),'glossary':glossary_rows,
        'limitations':deepcopy(snapshot['limitations'])}
    return result


def capture(catalog,name=None):
    name=name or catalog.active_name();require(name,'No active research corpus')
    snapshot=KnowledgeInspector(catalog).snapshot(name)
    with existing_reader(catalog.select(name),blocking=False,exclusive=True) as store:
        revision,*_=store.read();require(revision==snapshot['revision'],'Snapshot changed while collecting glossary')
        state=loads(store.path('research/state.json').read_text())
        records=Directory(store).all(state)
        return snapshot,project(snapshot,records,experiment=name)


def subset(evidence,ids):
    result={k:deepcopy(evidence[k]) for k in ('schema','revision','identity','inventory','coverage','node_statuses','synthesis_summary','limitations')}
    result['identity']={k:v for k,v in result['identity'].items() if k not in {'active_node_id','active_node_status','active_question'}}
    result['context_coverage']={'scope':'partial_corpus' if len(ids)<len(evidence['units']) else 'complete_corpus',
        'supplied_unit_ids':list(ids),'supplied_unit_count':len(ids),'corpus_unit_count':len(evidence['units']),
        'omitted_unit_ids':[i for i in evidence['units'] if i not in ids],
        'global_absence_established':False}
    result['research_questions']={i:deepcopy(r) for i,r in evidence['research_questions'].items() if i in {evidence['units'][u]['node_id'] for u in ids}}
    result['units']={i:deepcopy(evidence['units'][i]) for i in ids}
    sources={s for u in result['units'].values() for s in u['source_ids']}
    result['sources']={i:deepcopy(evidence['sources'][i]) for i in sorted(sources) if i in evidence['sources']}
    result['glossary']={}
    return result


def batches(evidence,*,max_units=12,max_bytes=12500):
    grouped=defaultdict(list)
    for row in evidence['units'].values():grouped[row['node_id']].append(row['id'])
    result=[]
    for node,ids in grouped.items():
        selected=[]
        for identity in ids:
            row=evidence['units'][identity]
            size=len(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode())
            require(size<=max_bytes,'A complete scientific unit exceeds the evidence batch budget; nothing was truncated.')
            if selected and (len(selected)>=max_units or len(json.dumps([evidence['units'][i] for i in selected],ensure_ascii=False).encode())+size>max_bytes):
                result.append((node,selected));selected=[]
            selected.append(identity)
        if selected:result.append((node,selected))
    return result


def bookkeeping_failures(draft,checks):
    """Only model process/count prose can yield to canonical inventory rendering."""
    paragraphs={p['id']:p for s in draft['sections'] for p in s['paragraphs']}
    failures=defaultdict(list)
    for error in checks['publication_errors']:failures[error['claim_id']].append(error)
    return {identity:errors for identity,errors in failures.items()
            if paragraphs[identity]['kind']=='process' and all(e['category']=='inventory_mismatch' for e in errors)}


def compose(trials,evidence):
    """Combine complete model sections; canonical code owns inventory bookkeeping.

    An invalid model process/count paragraph is withheld, never rewritten.
    Its exact text and checks remain inspectable; scientific errors still block.
    """
    sections=[];initial_sections=[];withheld=[]
    for section_id,_ in SECTIONS:
        final=[];initial=[]
        for trial in trials:
            checks=scientific_checks(trial['revision']['draft'],evidence)
            ignored=bookkeeping_failures(trial['revision']['draft'],checks)
            for target,source in [(final,trial['revision']['draft']),(initial,trial['draft'])]:
                for section in source['sections']:
                    if section['id']!=section_id:continue
                    for paragraph in section['paragraphs']:
                        row={**paragraph,'id':trial['label']+'.'+paragraph['id']}
                        if target is final and paragraph['id'] in ignored:
                            withheld.append({'section_id':section_id,'paragraph':row,'checks':ignored[paragraph['id']],
                                'reason':'Model inventory bookkeeping failed deterministic validation; canonical inventory is rendered directly.'})
                        else:target.append(row)
        sections.append({'id':section_id,'paragraphs':final});initial_sections.append({'id':section_id,'paragraphs':initial})
    return sections,initial_sections,withheld


class GenerationFailure(RuntimeError): pass


class Generator:
    def __init__(self,model,log_dir,*,max_calls=40,clock=time.monotonic,resume_id=None):
        self.model=model;self.base=Path(log_dir).absolute();confined(self.base)
        self.base.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.identity=resume_id or uuid.uuid4().hex
        require(len(self.identity)==32 and all(c in '0123456789abcdef' for c in self.identity),'invalid generation ID')
        self.directory=confined(self.base/self.identity)
        if not resume_id:self.directory.mkdir(mode=0o700)
        self.clock=clock;self.started=clock();self.max_calls=max_calls;self.calls=[]
        self.secrets=configured_secrets(getattr(model,'secrets',()))
        self.model_identity=model_identity(model)
        self.manifest={'schema':'mira.sor.manifest/1','id':self.identity,'started_at':now(),'status':'prepared',
            'model_identity':self.model_identity,'settings':dict(model.settings),'calls':self.calls,'scientifically_verified':False}
        if resume_id:
            previous=loads(confined(self.directory/'manifest.json').read_text())
            require(previous['model_identity'].get('served_model')==self.model_identity['served_model'] and
                previous['model_identity'].get('artifact_sha256')==self.model_identity.get('artifact_sha256'),'generating model identity changed')
            require(not any(c['status'] in {'prepared','uncertain'} for c in previous['calls']),'uncertain SOR submission requires explicit human review')
            self.manifest=previous;self.calls=previous['calls']
            if previous['model_identity']!=self.model_identity:
                self.manifest.setdefault('model_observations',[]).append({'observed_at':now(),'identity':self.model_identity})
                # Server properties can include mutable defaults. Preserve the
                # original model identity; record changed observations alongside
                # it after checking the served name and artifact hash above.
                self.model_identity=previous['model_identity']
            if 'error' in self.manifest:
                self.manifest.setdefault('recovered_errors',[]).append({'error':self.manifest.pop('error'),'finished_at':self.manifest.get('finished_at')})
        self.save('manifest.json',self.manifest)

    def save(self,name,value):
        require(Path(name).name==name and not name.startswith('.'),'invalid diagnostic filename')
        path=confined(self.directory/name)
        atomic_text(path,dumps(scrub(value,self.secrets)))

    def request(self,action,payload):
        payload=deepcopy(payload)
        output=payload['output_contract']
        def bind(schema):
            if not isinstance(schema,dict):return
            for key,value in schema.items():
                if key=='unit_ids' and isinstance(value,dict) and value.get('type')=='array':
                    value['items']={'enum':list(payload['evidence']['units'])}
                elif key=='claim_id' and isinstance(value,dict) and 'draft' in payload:
                    value.clear();value['enum']=[p['id'] for s in payload['draft']['sections'] for p in s['paragraphs']]
                elif key=='objection_id' and isinstance(value,dict) and 'review' in payload:
                    value.clear();value['enum']=[o['id'] for o in payload['review']['objections']]
                if isinstance(value,dict):bind(value)
                elif isinstance(value,list):
                    for child in value:bind(child)
        bind(output)
        if action=='SOR2':
            paragraphs=[p for s in payload['draft']['sections'] for p in s['paragraphs']]
            generic=output['properties']['objections']['items']
            if paragraphs:
                variants=[]
                for paragraph in paragraphs:
                    row=deepcopy(generic)
                    row['properties']['claim_id']={'const':paragraph['id']}
                    row['properties']['assertion']={'const':paragraph['text']}
                    variants.append(row)
                output['properties']['objections']['items']={'oneOf':variants}
            else:
                output['properties']['objections'].update(maxItems=0,items={'type':'object'})
        if action=='SOR3':
            total=len(payload['review']['objections'])
            output['properties']['dispositions'].update(minItems=total,maxItems=total)
            if not total:output['properties']['dispositions']['items']={'type':'object'}
        settings=deepcopy(self.model.settings)
        settings['response_format']={'type':'json_schema','json_schema':{'name':action.lower(),'strict':True,'schema':payload['output_contract']}}
        wire,template=decisions.prepared_request(self.model.model,settings,action,{'payload':payload})
        usage=measure(wire,self.model.settings['max_tokens'],getattr(self.model,'context_window',16384),getattr(self.model,'count_tokens',None))
        require(not usage['over_context_budget'],'Complete SOR context exceeds the active model window; no content truncated')
        return wire,template,usage

    def call(self,action,payload):
        # Reuse immutable received results when the scientific inputs and exact
        # approved template match. A tighter output grammar does not warrant
        # resubmitting completed inference; current validators still apply.
        from .prompts import PromptTemplates
        current_template=PromptTemplates().sources(action)[0]['sha256']
        scientific={k:v for k,v in payload.items() if k!='output_contract'}
        for previous in self.calls:
            if previous['action']!=action or previous['template_sha256']!=current_template:continue
            path=self.directory/f"{previous['number']:03d}-{action}-request.json"
            saved=loads(confined(path).read_text());old_wire=loads(saved['serialized_request'])
            old_payload=loads(old_wire['messages'][1]['content'])
            if {k:v for k,v in old_payload.items() if k!='output_contract'}!=scientific:continue
            if previous['status']=='failed':raise GenerationFailure('Received failed output is retained; resume does not repeat it.')
            if previous['status']=='received':return loads(confined(self.directory/f"{previous['number']:03d}-{action}-parsed.json").read_text())
        wire,template,budget=self.request(action,payload)
        for previous in self.calls:
            if previous['request_sha256']==digest(wire) and previous['status']=='failed':
                raise GenerationFailure('Previously failed exact request is retained; resume does not resubmit failed model output.')
            if previous['request_sha256']==digest(wire) and previous['status']=='received':
                return loads(confined(self.directory/f"{previous['number']:03d}-{action}-parsed.json").read_text())
        require(len(self.calls)<self.max_calls,'SOR model-call budget exhausted')
        number=len(self.calls)+1;prefix=f'{number:03d}-{action}'
        row={'number':number,'action':action,'status':'prepared','timestamp':now(),
            'request_sha256':digest(wire),'template_sha256':template['files'][0]['sha256'],'budget':budget}
        self.save(prefix+'-request.json',{'serialized_request':wire,'prompt_template':template,'budget':budget})
        self.calls.append(row);self.manifest['status']='running';self.save('manifest.json',self.manifest)
        start=self.clock()
        try:
            raw=self.model.complete(wire)
            self.save(prefix+'-response.json',{'raw':raw,'received_at':now()})
            row.update(status='received',elapsed_seconds=self.clock()-start)
            value,info=decisions.proposal(raw);row.update(model=info['model'],usage=info['usage'])
            self.save(prefix+'-parsed.json',value);self.save('manifest.json',self.manifest)
            return value
        except BaseException as exc:
            row.update(status='failed' if isinstance(exc,Exception) else 'uncertain',error_type=type(exc).__name__,error=str(exc),elapsed_seconds=self.clock()-start)
            self.save('manifest.json',self.manifest);raise

    def pipeline(self,evidence,sections,*,candidate=None,label='batch'):
        base={'evidence':evidence,'section_ids':sections}
        draft=candidate if candidate is not None else self.call('SOR1',{**base,'output_contract':contract('SOR1',sections)})
        validate_draft(draft,evidence,sections)
        initial_checks=scientific_checks(draft,evidence)
        review=self.challenge(evidence,sections,draft,initial_checks)
        # Invalid individual objections are retained but cannot become evidence
        # for revision. This changes no scientific text or interpretation.
        valid=[];rejected=[]
        require(isinstance(review,dict) and set(review)=={'schema','summary','objections'} and isinstance(review['objections'],list),'invalid review envelope')
        validate_review({**review,'objections':[]},draft,evidence)
        for objection in review['objections']:
            try:
                if isinstance(objection,dict) and isinstance(objection.get('id'),str) and objection['id'] in self.review_context:
                    require(objection.get('claim_id') in self.review_context[objection['id']],'Objection refers outside its bounded review context')
                validate_review({**review,'objections':valid+[objection]},draft,evidence);valid.append(objection)
            except (ValueError,TypeError,KeyError) as exc:rejected.append({'objection':objection,'error':str(exc)})
        accepted_review={**review,'objections':valid}
        revised=self.revise(evidence,sections,draft,accepted_review,initial_checks)

        validate_revision(revised,draft,accepted_review,evidence,sections)
        checks=scientific_checks(revised['draft'],evidence)
        result={'schema':'mira.sor.trial/1','label':label,'unit_ids':list(evidence['units']),'draft':draft,
            'review':review,'valid_review':accepted_review,'rejected_objections':rejected,'revision':revised,
            'initial_validation':initial_checks,'final_validation':checks}
        self.save(label+'.json',result)
        ignored=bookkeeping_failures(revised['draft'],checks)
        require(all(e['claim_id'] in ignored for e in checks['publication_errors']),'Revised draft has deterministic publication errors')
        return result

    def review_plan(self,evidence,sections,draft,checks):
        """Fit complete draft paragraphs while retaining all supplied evidence."""
        all_claims=[p['id'] for s in draft['sections'] for p in s['paragraphs']]
        pending=[draft];prepared=[]
        while pending:
            local=pending.pop(0);ids=[s['id'] for s in local['sections']]
            payload={'evidence':evidence,'section_ids':ids,'draft':local,
                'deterministic_checks':checks if local==draft else scientific_checks(local,evidence),'output_contract':contract('SOR2',ids)}
            claims=[p['id'] for s in local['sections'] for p in s['paragraphs']]
            if local!=draft:
                payload['review_coverage']={'scope':'partial_draft','supplied_claim_ids':claims,
                    'omitted_claim_ids':[i for i in all_claims if i not in claims]}
            try:self.request('SOR2',payload)
            except ValueError as exc:
                if 'context exceeds' not in str(exc):raise
                rows=[(s['id'],p) for s in local['sections'] for p in s['paragraphs']]
                require(len(rows)>1,'A complete review paragraph and its evidence exceed the model context; nothing was truncated.')
                middle=(len(rows)+1)//2;parts=[]
                for selected in (rows[:middle],rows[middle:]):
                    grouped={}
                    for section,paragraph in selected:grouped.setdefault(section,[]).append(paragraph)
                    parts.append({**draft,'sections':[{'id':section,'paragraphs':paragraphs} for section,paragraphs in grouped.items()]})
                pending[0:0]=parts;continue
            prepared.append(payload)
        return prepared

    def challenge(self,evidence,sections,draft,checks):
        self.review_context={}
        payload={'evidence':evidence,'section_ids':sections,'draft':draft,
            'deterministic_checks':checks,'output_contract':contract('SOR2',sections)}
        try:return self.call('SOR2',payload)
        except ValueError as exc:
            if 'context exceeds' not in str(exc):raise
        prepared=self.review_plan(evidence,sections,draft,checks)
        require(len(self.calls)+len(prepared)<=self.max_calls,'Complete scientific review exceeds the remaining call budget')
        summaries=[];objections=[]
        for number,part in enumerate(prepared,1):
            review=self.call('SOR2',part)
            require(isinstance(review,dict) and set(review)=={'schema','summary','objections'} and review['schema']=='mira.sor.review/1'
                    and isinstance(review['summary'],str) and isinstance(review['objections'],list),'invalid bounded review envelope')
            summaries.append(review['summary'])
            for row in review['objections']:
                # Stable local IDs are namespaced; assertions and reasoning are
                # unchanged. Raw per-group responses remain in the receipts.
                if isinstance(row,dict) and isinstance(row.get('id'),str):
                    identity=f'review{number}.'+row['id'];self.review_context[identity]={p['id'] for s in part['draft']['sections'] for p in s['paragraphs']}
                    objections.append({**row,'id':identity})
                else:objections.append(row)
        return {'schema':'mira.sor.review/1','summary':'\n\n'.join(summaries),'objections':objections}

    def revise(self,evidence,sections,draft,accepted_review,initial_checks):
        """Revise a received draft/review without repeating earlier model stages."""
        revision_payload={'evidence':evidence,'section_ids':sections,'draft':draft,'review':accepted_review,'deterministic_checks':initial_checks,
            'output_contract':contract('SOR3',sections)}
        try:
            revised=self.call('SOR3',revision_payload)
        except ValueError as exc:
            if 'context exceeds' not in str(exc):raise
            # Partition the revision by complete sections, preserving each
            # criticised claim and every supporting unit in its own context.
            revised_sections=[];dispositions=[];pending=[draft['sections']];prepared=[]
            while pending:
                selected_sections=pending.pop(0)
                claim_ids={p['id'] for section in selected_sections for p in section['paragraphs']}
                local_review={**accepted_review,'objections':[o for o in accepted_review['objections'] if o['claim_id'] in claim_ids]}
                ids=list(dict.fromkeys([u for section in selected_sections for p in section['paragraphs'] for u in cited_units(p)]+[u for o in local_review['objections'] for u in o['unit_ids']]))
                local_evidence=subset(evidence,ids);local_ids=[s['id'] for s in selected_sections]
                local_draft={**draft,'sections':selected_sections}
                local_payload={'evidence':local_evidence,'section_ids':local_ids, 'draft':local_draft,'review':local_review,
                    'deterministic_checks':scientific_checks(local_draft,local_evidence),'output_contract':contract('SOR3',local_ids)}
                try:self.request('SOR3',local_payload)
                except ValueError as failure:
                    if 'context exceeds' not in str(failure) or len(selected_sections)==1:raise
                    middle=(len(selected_sections)+1)//2
                    pending[0:0]=[selected_sections[:middle],selected_sections[middle:]]
                    continue
                prepared.append((local_payload,local_evidence,local_draft,local_review,local_ids))
            require(len(self.calls)+len(prepared)<=self.max_calls,'Complete section revision exceeds the remaining call budget')
            for local_payload,local_evidence,local_draft,local_review,local_ids in prepared:
                part=self.call('SOR3',local_payload)
                validate_revision(part,local_draft,local_review,local_evidence,local_ids)
                revised_sections.extend(part['draft']['sections']);dispositions.extend(part['dispositions'])
            revised={'schema':'mira.sor.revision/1','draft':{**draft,'sections':revised_sections},'dispositions':dispositions}

        validate_revision(revised,draft,accepted_review,evidence,sections)
        return revised

    def run(self,evidence):
        require(evidence['units'],'No canonical knowledge units are available; no paper can be generated.')
        plan=batches(evidence);require((len(plan)+1)*3<=self.max_calls,'Complete corpus needs more calls than this generation budget')
        require(not self.manifest.get('source_snapshot_sha256') or self.manifest['source_snapshot_sha256']==digest(dumps(evidence)), 'Resume evidence differs from the original source snapshot')
        self.manifest.update(source_revision=evidence['revision'],source_snapshot_sha256=digest(dumps(evidence)),experiment=evidence.get('experiment'))
        self.save('evidence.json',evidence);self.save('manifest.json',self.manifest)
        trials=[]
        ledger={i:{'id':i,'version':u['version'],'batch':None,'considered':False,'initially_cited':False,'finally_cited':False} for i,u in evidence['units'].items()}
        try:
            for number,(node,ids) in enumerate(plan,1):
                selected=subset(evidence,ids);sections=['findings','conflicts','limitations','questions']
                if any('equation' in u for u in selected['units'].values()):sections.append('mathematics')
                trial=self.pipeline(selected,sections,label=f'group-{number:02d}');trial['node_id']=node;trials.append(trial)
                for i in ids:ledger[i].update(batch=trial['label'],considered=True)
                self.save('coverage.json',ledger)
            representatives=[]
            for _,ids in plan:
                for kind in ('finding','question','equation'):
                    match=next((i for i in ids if evidence['units'][i]['structural_type']==kind),None)
                    if match and match not in representatives:representatives.append(match)
            summary=subset(evidence,representatives)
            global_sections=['abstract','introduction','methodology','synthesis','progress','conclusions','directions']
            trials.append(self.pipeline(summary,global_sections,label='overview'))
            sections,initial_sections,withheld=compose(trials,evidence)
            for target,key in [(initial_sections,'initially_cited'),(sections,'finally_cited')]:
                for section in target:
                    for paragraph in section['paragraphs']:
                        for identity in cited_units(paragraph):ledger[identity][key]=True
            final={'schema':'mira.sor.paper/1','id':self.identity,'title':trials[-1]['revision']['draft']['title'],
                'generated_at':now(),'source_revision':evidence['revision'],'source_snapshot_sha256':digest(dumps(evidence)),
                'experiment':evidence.get('experiment'),'model_identity':self.model_identity,'adversarial_review':True,
                'sections':sections,'coverage_ledger':ledger,'scientifically_verified':False}
            final_draft={'schema':'mira.sor.draft/1','title':final['title'],'sections':sections}
            validate_draft(final_draft,evidence,[i for i,_ in SECTIONS]);checks=scientific_checks(final_draft,evidence)
            require(not checks['publication_errors'],'Final paper failed deterministic validation')
            require(all(r['considered'] for r in ledger.values()),'Incomplete scientific coverage ledger')
            self.manifest.update(status='completed',finished_at=now(),elapsed_seconds=self.clock()-self.started,
                prompt_template_hashes={r['action']:r['template_sha256'] for r in self.calls},validation=checks)
            self.manifest['invocation_elapsed_seconds']=self.manifest['elapsed_seconds']
            self.manifest['elapsed_seconds']=(datetime.fromisoformat(self.manifest['finished_at'])-datetime.fromisoformat(self.manifest['started_at'])).total_seconds()
            self.manifest['model_elapsed_seconds']=sum(row.get('elapsed_seconds',0) for row in self.calls)
            self.save('manifest.json',self.manifest);self.save('paper.json',final)
            audit={'schema':'mira.sor.audit/1','paper':final,'evidence':evidence,'trials':trials,
                'initial_sections':initial_sections,'withheld_paragraphs':withheld,'manifest':self.manifest,'validation':checks}
            return audit
        except BaseException as exc:
            self.manifest.update(status='failed' if isinstance(exc,Exception) else 'interrupted',error=str(exc),finished_at=now(),elapsed_seconds=self.clock()-self.started)
            self.save('manifest.json',self.manifest);raise


def publish(catalog,audit,*,fault=None):
    """Publish only a validated completed triple; rollback leaves previous paper intact."""
    from .sor_view import markdown,html
    from .glossary_view import publish as publish_views
    validate_audit(audit)
    evidence=audit['evidence'];paper=audit['paper']
    with existing_reader(catalog.select(evidence['experiment']),blocking=False,exclusive=True) as store:
        store.read();state=loads(store.path('research/state.json').read_text())
        require(state.get('run_id')==evidence['identity'].get('run_id'),'Experiment replaced during generation')
        outputs={ARTIFACTS[0]:markdown(audit),ARTIFACTS[1]:html(audit),ARTIFACTS[2]:dumps(audit)}
        if fault:fault('before_publication')
        publish_views(store,outputs)
    return {'id':paper['id'],'revision':paper['source_revision'],'paths':[str(catalog.select(evidence['experiment'])/p) for p in ARTIFACTS],
        'model_calls':len(audit['manifest']['calls'])+sum(len(m['calls']) for m in audit['manifest'].get('supplemental_generations',[])),
        'units_considered':len(paper['coverage_ledger']),
        'units_cited':sum(r['finally_cited'] for r in paper['coverage_ledger'].values())}


def load(catalog,name=None):
    name=name or catalog.active_name();root=catalog.select(name)
    with existing_reader(root,blocking=False) as store:
        revision,*_=store.read();target=store.path(ARTIFACTS[2])
        require(target.exists(),'No completed State of Research report; run state-of-research-generate')
        audit=loads(target.read_text());validate_audit(audit)
        require(audit['paper']['experiment']==name,'Report belongs to another experiment')
        return {'audit':audit,'current_revision':revision,'stale':revision!=audit['paper']['source_revision']}


def validate_audit(audit):
    """Recheck saved content; a saved validation verdict is not a trust boundary."""
    require(audit.get('schema')=='mira.sor.audit/1','Unsupported report audit')
    evidence=audit['evidence'];paper=audit['paper'];manifest=audit['manifest']
    require(evidence.get('schema')=='mira.sor.evidence/1' and paper.get('schema')=='mira.sor.paper/1','Unsupported report evidence/paper')
    require(manifest['status']=='completed','Incomplete State of Research artifact')
    require(digest(dumps(evidence))==paper['source_snapshot_sha256'],'Report evidence hash mismatch')
    require(paper['source_revision']==evidence['revision'] and paper['experiment']==evidence['experiment'],'Report snapshot identity mismatch')
    require(manifest['source_revision']==paper['source_revision'] and manifest['source_snapshot_sha256']==paper['source_snapshot_sha256']
            and manifest['experiment']==paper['experiment'],'Generation manifest snapshot mismatch')
    require(manifest['model_identity']==paper['model_identity'],'Report model provenance mismatch')
    require(paper['id']==manifest['id'] and not paper['scientifically_verified'],'Invalid report generation identity or verification claim')
    draft={'schema':'mira.sor.draft/1','title':paper['title'],'sections':paper['sections']}
    validate_draft(draft,evidence,[i for i,_ in SECTIONS])
    validate_draft({**draft,'sections':audit['initial_sections']},evidence,[i for i,_ in SECTIONS])
    checks=scientific_checks(draft,evidence)
    require(not checks['publication_errors'],'Incomplete/invalid paper cannot be published')
    require(audit['validation']==checks,'Saved report validation differs from its content')
    ledger=paper['coverage_ledger'];cited={u for s in paper['sections'] for p in s['paragraphs'] for u in cited_units(p)}
    require(set(ledger)==set(evidence['units']),'Incomplete scientific coverage ledger')
    for identity,row in ledger.items():
        require(row['id']==identity and row['version']==evidence['units'][identity]['version'] and row['considered'] is True,'Invalid scientific coverage record')
        require(row['finally_cited']==(identity in cited),'Citation coverage differs from the final narrative')
    require(paper['adversarial_review'] is True and audit['trials'],'Report has no adversarial review history')
    for trial in audit['trials']:
        selected=subset(evidence,trial['unit_ids'])
        sections=[s['id'] for s in trial['draft']['sections']]
        validate_draft(trial['draft'],selected,sections)
        validate_review(trial['valid_review'],trial['draft'],selected)
        validate_revision(trial['revision'],trial['draft'],trial['valid_review'],selected,sections)
    expected,initial,withheld=compose(audit['trials'],evidence)
    require(paper['sections']==expected and audit['initial_sections']==initial,'Report differs from received draft/revision assembly')
    require(audit.get('withheld_paragraphs',[])==withheld,'Withheld model bookkeeping is not fully disclosed')
    return audit


@contextmanager
def generation_lock(log_dir,root):
    directory=Path(log_dir)/'locks';confined(directory);directory.mkdir(parents=True,exist_ok=True)
    target=confined(directory/(digest(str(Path(root).absolute()))+'.lock'))
    with target.open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)
