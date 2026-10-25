'use strict';
const $=id=>document.getElementById(id);
const initialLink=new URLSearchParams(location.search);
let sessionToken='', experiment=initialLink.get('experiment')||'', run=null, timeline=[], selected=-1, requestNumber=0;
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
async function api(path,options={}){const r=await fetch(path,options);const data=await r.json();if(!r.ok)throw Error(data.error||r.statusText);return data;}
function absent(parent,label='Not supplied to the model.'){parent.append(el('p',label,'absent'));}
function jsonView(value,label='JSON',open=false,depth=0){
 const d=el('details');d.open=open;d.append(el('summary',label));
 if(value===null||value===undefined){d.append(el('p','Not recorded.','absent'));return d;}
 if(typeof value==='object'&&depth<3){const entries=Object.entries(value);if(!entries.length)d.append(el('pre',JSON.stringify(value)));else for(const [k,v]of entries){
  if(v!==null&&typeof v==='object')d.append(jsonView(v,`${k} · ${Array.isArray(v)?v.length+' items':Object.keys(v).length+' fields'}`,false,depth+1));
  else{const line=el('div',undefined,'json-entry');line.append(el('strong',`${k}: `));line.append(el('pre',typeof v==='string'?v:JSON.stringify(v)));d.append(line);}
 }}else d.append(el('pre',typeof value==='string'?value:JSON.stringify(value,null,2)));return d;
}
function section(title,subtitle){const s=el('section',undefined,'section');s.append(el('h2',title));if(subtitle)s.append(el('p',subtitle,'hint'));$('inspection').append(s);return s;}
function showJSON(title,value,note){const s=section(title,note);if(value===null||value===undefined)absent(s);else s.append(jsonView(value,'Expand recorded content',true));return s;}
function rawSection(title,value,note,expanded=true){const s=section(title,note);if(value===null||value===undefined)absent(s,'Not recorded.');else{const d=el('details');d.open=expanded;d.append(el('summary','Exact recorded text'),el('pre',value));s.append(d);}return s;}
function messages(title,items){const s=section(title,'Actual recorded messages, in order; no current-state reconstruction.');if(!items){absent(s);return;}for(const m of items){s.append(el('h3',m.role));if(typeof m.content==='string')s.append(el('pre',m.content));else s.append(jsonView(m.content,'Recorded content',true));}}
function renderTree(nodes,label){$('tree').replaceChildren();$('tree-label').textContent=label;if(!nodes){absent($('tree'),'Historical tree not recorded.');return;}
 const seen=new Set();function visit(id,parent){if(seen.has(id))return;seen.add(id);const n=nodes[id];if(!n)return;const d=el('div',undefined,'tree-node');const b=el('button',`${id} · ${n.status||'unknown'} · ${n.question||''}`);b.onclick=()=>{const i=timeline.findIndex(t=>t.node_id===id&&t.kind==='decision');if(i>=0)select(i);};d.append(b);parent.append(d);for(const child of n.child_ids||[])visit(child,d);}
 for(const [id,n]of Object.entries(nodes))if(!n.parent_id)visit(id,$('tree'));for(const id of Object.keys(nodes))if(!seen.has(id))visit(id,$('tree'));
}
function renderTimeline(){const f=$('filter').value;timeline=(run?.timeline||[]).filter(t=>f==='all'||(f==='decision'?t.kind==='decision':t.action===f));$('timeline').replaceChildren();timeline.forEach((t,i)=>{const b=el('button',undefined,i===selected?'active':'');b.append(el('strong',`${t.action||'unknown'} · ${t.node_id||'run'}`),el('span',t.status,'badge '+t.status),el('span',`Cycle ${t.cycle??'?'} · ${t.timestamp||'timestamp absent'}`,'hint'));b.onclick=()=>select(i);$('timeline').append(b);});}
async function loadExperiments(){const data=await api('/api/experiments');$('experiments').replaceChildren();if(!data.length){$('experiments').append(new Option('No persistent experiments',''));$('inspection').replaceChildren(el('h1','No experiments yet'),el('p','Use research-init or research-import. Data lives in the local memory/ directory.'));return;}
 for(const item of data)$('experiments').append(new Option(`${item.name} — ${item.question||'not initialized'}`,item.name));if(data.some(d=>d.name===experiment))$('experiments').value=experiment;await loadRun();}
async function loadRun(){const ticket=++requestNumber;experiment=$('experiments').value;if(!experiment)return;const snapshot=await api('/api/experiments/'+encodeURIComponent(experiment));if(ticket!==requestNumber)return;run=snapshot;$('run-question').textContent=run.current_state?.nodes?.[run.current_state.root_id]?.question||'Research question unavailable';$('alert').textContent=run.warnings.join('\n');renderTree(run.current_state?.nodes,'Current recorded state — not historical model input');selected=-1;renderTimeline();if(timeline.length){const requested=new URLSearchParams(location.search).get('decision');const index=timeline.findIndex(t=>t.id===requested);await select(index>=0?index:0);}}
function memoryList(title,items,note){const s=section(title,note);if(!items||!items.length){absent(s);return;}for(const item of items){const d=el('details');d.append(el('summary',`${item.id||'memory'}${item.included_in_request===false?' · available but NOT supplied':item.included_in_request===true?' · supplied':''}`));d.append(el('pre',item.markdown??'Contents unavailable.'));s.append(d);}}
async function select(i){if(i<0||i>=timeline.length)return;selected=i;const seq=++requestNumber,t=timeline[i],selectedExperiment=experiment;$('previous').disabled=i===0;$('next').disabled=i===timeline.length-1;$('position').textContent=`${i+1} / ${timeline.length}`;renderTimeline();
 try{const path=`/api/experiments/${encodeURIComponent(experiment)}/${t.kind==='decision'?'decisions':'actions'}/${encodeURIComponent(t.id)}`;const data=await api(path);if(seq!==requestNumber)return;history.replaceState(null,'','?'+new URLSearchParams({experiment:selectedExperiment,decision:t.id}));$('inspection').replaceChildren();$('alert').textContent=(data.warnings||[]).join('\n');$('inspection').append(el('h1',`${t.action} · ${t.node_id||'run'} · ${data.status||t.status}`));
 if(t.kind!=='decision'){if(data.event.tree)renderTree(data.event.tree,'Recorded tree AFTER selected action');showJSON('Recorded action',data.event,data.notice);showJSON('Retrieved from external sources',data.retrieved_evidence,'Available external evidence is not automatically included in later model requests.');return;}
 const input=data.inputs;
 $('inspection').append(el('p',data.input_source,'notice'));
 showJSON('Research objective and selected node',{question:input.question,question_context:input.question_context,root_question:input.root_question,node:input.node,ancestor_questions:input.ancestor_questions},'These fields come from verified saved template bindings or historical request JSON. Missing means absent.');
 const templateSection=section('Filled prompt templates actually sent',data.template_verification.notice);
 if(data.prompt_template){
  templateSection.append(jsonView({action:data.prompt_template.action,request_sha256:data.prompt_template.serialized_request_sha256,redaction_applied:data.prompt_template.redaction_applied,verification:data.template_verification},'Recorded template identity',true));
  for(const file of data.prompt_template.files||[]){const d=el('details');d.append(el('summary',file.path+' · '+file.sha256),el('pre',file.source));templateSection.append(d);}
  templateSection.append(jsonView(data.prompt_template.bindings,'Values inserted into the templates',false));
 }else absent(templateSection,'This historical call predates template snapshots. Its actual filled messages remain available below. Current template files are not substituted.');
 if(data.plain_text_prompt!==null&&data.plain_text_prompt!==undefined)rawSection('Filled task instructions — exact sent text',data.plain_text_prompt,'One plain-text user message; no shared system prompt.');
 else showJSON('State task and exact output instructions',data.task_instructions,'Historical structured instructions, extracted only from the saved user message.');
 const slots=section('Filled information slots','Values from the verified recorded template bindings or historical JSON request. Explicit null and empty collections are distinct; missing values are not filled in.');
 if(data.prompt_slots===null||!data.prompt_slots?.length)absent(slots,'No structured context slots were recorded.');
 else for(const slot of data.prompt_slots)slots.append(jsonView(slot.value,slot.name+' · '+slot.status));
 if(input.system_messages)messages('Historical system message — exact sent text',input.system_messages);if(input.developer_messages)messages('Historical developer message — exact sent text',input.developer_messages);messages('User message — exact sent text',input.user_messages);
 showJSON('Structured context actually supplied',data.structured_context);
 memoryList('Existing memories actually supplied',input.existing_memories,'Complete recorded contents. No additional corpus memories are inserted here.');
 showJSON('Search evidence actually supplied',input.search_evidence,'Recorded research or search_evidence values only. Prior retrieval is shown separately below.');
 if(input.output_contract)showJSON('Historical output contract',input.output_contract);
 showJSON('Model and generation settings',{requested_model:data.model,reported_model:data.reported_model,settings:data.generation_settings});
 showJSON('Token usage and context estimate',{reported_token_usage:data.usage,context_utilisation:data.context_estimate.fraction===null?'Not recorded':(100*data.context_estimate.fraction).toFixed(1)+'%',estimate:data.context_estimate},'Usage is server-reported when available. UTF-8 byte estimates are conservative and are not measured token counts.');
 rawSection('Exact serialized HTTP request body',data.serialized_request,'Original recorded body; not reserialized from current state.',false);
 rawSection('Complete raw LLM response',data.raw_response,'Preserves the completion envelope, including malformed/rejected output.');
 showJSON('Readable generated response content',data.completion_messages,'Generated by the model, not additional input evidence.');
 showJSON('Validation results',data.validation);
 showJSON('Actual committed action',data.committed_event,'Only linked events backed by a committed journal marker and matching event hash appear here.');
 showJSON('Recorded outcome',data.outcome,'May be absent after interruption; a verified committed event above can resolve it without another model call.');
 showJSON('Historical tree before decision',data.tree_before,'Recovered from retained pre-operation journal history, not used to fill in missing model inputs.');
 showJSON('Resulting committed tree',data.tree_after);
 if(data.tree_before)renderTree(data.tree_before,'Historical tree BEFORE selected decision (journal history)');else renderTree(null,'Historical tree unavailable');
 memoryList('Corpus available at this decision',data.historical_corpus,'Historical journal after-images. Availability does not mean inclusion in the model request.');
 showJSON('Previously retrieved external evidence',data.retrieved_before_decision,'Prior committed retrievals. This material may NOT have been sent to this decision. See the actual-input section above.');
 showJSON('New canonical memories committed by this decision',data.generated_memories,'Generated output, not part of the original model input.');
 memoryList('Current corpus — separate reference',run.current_corpus,'Latest files only. These are NOT historical model inputs and may have changed since the selected decision.');
 addReview(data,selectedExperiment);
 }catch(e){$('alert').textContent=e.message;}}
function addReview(data,selectedExperiment){const s=section('Your local review','Human annotation only. Reviews never modify canonical memories, transcripts, prompts or research behaviour.');s.classList.add('review');const status=el('select');for(const [value,label]of [['approved','Approved'],['questionable','Questionable'],['incorrect','Incorrect'],['needs_investigation','Needs investigation']])status.append(new Option(label,value));if(data.review)status.value=data.review.status;else status.value='needs_investigation';
 const label=el('label','Comments');const comments=el('textarea');comments.maxLength=20000;comments.value=data.review?.comments||'';const save=el('button','Save review');const result=el('span');result.id='review-result';s.append(status,label,comments,save,result);if(data.review)s.append(jsonView(data.review.history,'Review history',false));
 save.onclick=async()=>{save.disabled=true;try{const review=await api(`/api/experiments/${encodeURIComponent(selectedExperiment)}/reviews/${encodeURIComponent(data.id)}`,{method:'POST',headers:{'Content-Type':'application/json','X-Mira-Token':sessionToken},body:JSON.stringify({status:status.value,comments:comments.value,expected_revision:data.review?.revision||0})});data.review=review;result.textContent=`Saved locally · revision ${review.revision}`;}catch(e){result.textContent=e.message;}finally{save.disabled=false;}};
}
$('experiments').onchange=()=>loadRun().catch(e=>$('alert').textContent=e.message);$('filter').onchange=()=>{selected=-1;renderTimeline();if(timeline.length)select(0);};$('previous').onclick=()=>select(selected-1);$('next').onclick=()=>select(selected+1);$('refresh').onclick=()=>loadExperiments().catch(e=>$('alert').textContent=e.message);
(async()=>{try{sessionToken=(await api('/api/session')).review_token;await loadExperiments();}catch(e){$('alert').textContent=e.message;}})();

$('templates').onclick=async()=>{const ticket=++requestNumber;try{const catalog=await api('/api/prompt-templates');if(ticket!==requestNumber)return;$('inspection').replaceChildren(el('h1','Current prompt templates'),el('p','These are current files on disk, not proof of what an older call used. Select a decision to inspect its saved, filled templates.','notice'));$('alert').textContent='';for(const action of catalog){const s=section(action.action+' prompt templates','Edit these files in prompt_templates/. New calls save their own immutable source snapshot and filled text.');for(const file of action.files){const d=el('details');d.open=file.path.endsWith('.txt');d.append(el('summary',file.path),el('pre',file.source));s.append(d);}s.append(el('p','Variables: '+action.variables.join(', '),'hint'));}}catch(e){$('alert').textContent=e.message;}};
