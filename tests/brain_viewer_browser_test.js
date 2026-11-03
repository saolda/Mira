/* Real Chromium/CDP acceptance test. No inference, source requests or canonical writes.
   Usage: node tests/brain_viewer_browser_test.js http://127.0.0.1:18867 19229 /tmp/brain-browser-results
   Chromium must already be running with --remote-debugging-port and this viewer URL. */
'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:8767',port=process.argv[3]||'19229',out=process.argv[4]||'/tmp/mira-brain-browser';
 fs.mkdirSync(out,{recursive:true});
 const targets=await(await fetch(`http://127.0.0.1:${port}/json`)).json(),target=targets.find(t=>t.type==='page'&&t.url.startsWith(base));assert(target,'viewer browser target');
 const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{socket.onopen=r;socket.onerror=j;});let sequence=0;const pending=new Map();
 socket.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result);}};
 const rpc=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 await rpc('Page.navigate',{url:base+'/'});
 const result=await rpc('Runtime.evaluate',{returnByValue:true,awaitPromise:true,expression:`(async()=>{
  const $=id=>document.getElementById(id),check=(v,m)=>{if(!v)throw Error(m);},sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const wait=async(fn,label)=>{const end=Date.now()+20000;while(Date.now()<end){if(fn())return;await sleep(80);}throw Error('Timeout: '+label+'; '+$('brain-error')?.textContent);};
  const change=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('change',{bubbles:true}));};
  const search=async(q,total)=>{$('knowledge-search').value=q;$('knowledge-search').dispatchEvent(new Event('input',{bubbles:true}));await wait(()=>$('knowledge-count').textContent.startsWith(total+' matching')&&(!q.includes('#')||[...document.querySelectorAll('.unit-row')].some(n=>n.dataset.unit===q)),'search '+q);};
  await wait(()=>$('brain-revision')?.textContent.startsWith('Snapshot ')&&document.querySelectorAll('.unit-row').length===46,'active overview');
  check($('brain-experiment').value==='medical-retrieval-repair-20261031','active corpus selected, not alphabetical legacy');
  check($('research-overview').textContent.includes('Does a spiculated pulmonary lesion'),'actual root question');
  check($('research-overview').textContent.includes('Not recorded'),'missing synthesis register honest');
  document.querySelector('[data-workspace=knowledge]').click();await search('r1#f1',1);
  document.querySelector('[data-unit="r1#f1"]').click();await wait(()=>$('knowledge-detail').querySelector('h1')?.textContent.startsWith('r1#f1'),'source finding detail');
  check($('knowledge-detail').textContent.includes('Spiculation is a predictor of cancer'),'complete actual proposition');
  check($('knowledge-detail').textContent.includes('Based on multivariable logistic-regression'),'full scientific qualification');
  check($('knowledge-detail').querySelector('a[href="https://pubmed.ncbi.nlm.nih.gov/24004118/"]'),'scientific source link');
  await search('r1#q1',1);document.querySelector('[data-unit="r1#q1"]').click();await wait(()=>$('knowledge-detail').querySelector('h1')?.textContent.startsWith('r1#q1'),'question detail');
  check($('knowledge-detail').textContent.includes('Question-unit state: open'),'question state recorded independently');
  $('knowledge-clear').click();await wait(()=>document.querySelectorAll('.unit-row').length===46,'clear filters');change('knowledge-type','claim');await wait(()=>document.querySelectorAll('.unit-row').length===5,'claim filter');change('knowledge-origin','source_extracted');await wait(()=>$('knowledge-count').textContent.startsWith('5 matching'),'combined filter');
  $('knowledge-clear').click();await wait(()=>document.querySelectorAll('.unit-row').length===46,'clear again');
  await search('rc#e1',1);document.querySelector('[data-unit="rc#e1"]').click();await wait(()=>$('knowledge-detail').querySelector('h1')?.textContent.startsWith('rc#e1'),'equation detail');
  check($('knowledge-detail').textContent.includes('TVDT = (t * ln(2)) / ln(V2/V1)'),'exact mathematical expression');
  check($('knowledge-detail').textContent.includes('cubic millimeters'),'equation variable units');
  [...$('knowledge-detail').querySelectorAll('button')].find(b=>b.textContent==='Inspect relationships and lineage').click();await wait(()=>document.querySelectorAll('.graph-node').length===2,'focused graph');
  check($('relationship-view').textContent.includes('RELATED_TO'),'recorded relationship');check($('relationship-view').textContent.includes('unverified'),'relationship status');
  const other=[...document.querySelectorAll('.graph-node')].find(n=>n.getAttribute('aria-label')==='Inspect rc#f1');check(other,'related canonical unit');other.dispatchEvent(new MouseEvent('click',{bubbles:true}));await wait(()=>$('relationship-view').querySelector('h2')?.textContent==='rc#f1','graph navigation');
  [...$('relationship-view').querySelectorAll('button')].find(b=>b.textContent==='Inspect selected unit').click();await wait(()=>$('knowledge-detail').querySelector('h1')?.textContent.startsWith('rc#f1'),'related unit detail');
  document.querySelector('[data-workspace=overview]').click();const branch=document.querySelector('details[data-node=q4]');branch.open=true;branch.querySelector('button').click();await wait(()=>$('knowledge-node').value==='q4'&&$('knowledge-count').textContent.startsWith('10 matching'),'branch knowledge navigation');
  $('brain-refresh').click();await wait(()=>!$('brain-error').textContent&&$('knowledge-count').textContent.startsWith('10 matching'),'refresh');await sleep(400);check(new URLSearchParams(location.search).get('unit')==='rc#f1','unit selection preserved');
  document.querySelector('[data-workspace=overview]').click();check(document.querySelector('details[data-node=q4]').open,'expanded question preserved');
  document.querySelector('[data-workspace=decisions]').click();await wait(()=>document.querySelectorAll('#timeline button').length>0,'decision history');const decision=[...document.querySelectorAll('#timeline button')].find(b=>b.textContent.startsWith('R4'));check(decision,'existing R4 decision');decision.click();await wait(()=>$('inspection').textContent.includes('Filled prompt templates actually sent'),'original decision inspector');check($('inspection').textContent.includes('Your local review'),'local review preserved');
  const glossary=await fetch('/glossary');check(glossary.ok,'standard glossary route');const html=await glossary.text();check(html.includes('Previously proposed definition 1'),'updated glossary history preserved');
  const resources=performance.getEntriesByType('resource').map(r=>r.name);check(resources.every(r=>r.startsWith(location.origin)),'offline assets/local API only');
  document.querySelector('[data-workspace=overview]').click();
  return {actual_units:46,active_corpus:true,overview:true,missing_history_honest:true,search:true,combined_filters:true,source_finding:true,question_state:true,equation:true,exact_qualifications:true,source_links:true,focused_graph:true,relationship_navigation:true,branch_navigation:true,stable_refresh:true,decisions:true,reviews:true,glossary:true,offline_assets:true,revision:$('brain-revision').title};
 })()`});
 if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));
 fs.writeFileSync(out+'/browser-results.json',JSON.stringify(result.result.value,null,2));
 let shot=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(out+'/overview.png',Buffer.from(shot.data,'base64'));
 await rpc('Runtime.evaluate',{expression:"document.querySelector('[data-workspace=knowledge]').click()"});
 shot=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(out+'/explorer.png',Buffer.from(shot.data,'base64'));
 console.log(JSON.stringify(result.result.value));socket.close();
})().catch(e=>{console.error(e);process.exit(1);});
