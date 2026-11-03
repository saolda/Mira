"""Safe academic HTML/Markdown views of validated, snapshot-bound SOR papers."""
from base64 import b64encode
from hashlib import sha256
from html import escape, unescape
from pathlib import Path
import re
from urllib.parse import urlencode,quote

from .format import dumps
from .glossary_sources import source_url
from .glossary import r3_prose
from .sor_contracts import SECTIONS,cited_units

ASSETS=Path(__file__).with_name('sor_assets')


def knowledge_url(identity,experiment):
    return '/?'+urlencode({'view':'knowledge','experiment':experiment or '', 'unit':identity})


def current_concerns(audit):
    result=list(audit['validation']['scientific_concerns'])
    result.extend(audit.get('evaluation_concerns',[]))
    for trial in audit['trials']:
        by_id={r['id']:r for r in trial['valid_review']['objections']}
        for row in trial['revision']['dispositions']:
            if row['disposition']=='unresolved':result.append({'claim_id':trial['label']+'.'+by_id[row['objection_id']]['claim_id'],
                'category':'unresolved_model_objection','reason':row['explanation'],'unit_ids':row['unit_ids']})
    return result


def stats(evidence):
    inventory=evidence['inventory'];coverage=evidence['coverage']
    return [('Research memories',inventory['research_memories']),('Synthesis memories',inventory['synthesis_memories']),
        ('Knowledge units',inventory['total_units']),('Processed sources',coverage['sources_processed']),
        ('Sources yielding units',coverage['sources_yielding_units']),('Open question units',coverage['open_question_units'])]


def md_text(value):return r3_prose(unescape(str(value)))


def used_sources(paper,evidence):
    result={source for section in paper['sections'] for p in section['paragraphs']
            for unit in cited_units(p) for source in evidence['units'][unit]['source_ids']}
    result.update(source for section in paper['sections'] for p in section['paragraphs']
                  for source in re.findall(r'\[SRC:([^\]]+)\]',p['text']))
    return result


def markdown(audit):
    paper=audit['paper'];evidence=audit['evidence'];lines=['# '+md_text(paper['title']),'',
        'Generated: '+paper['generated_at'],'Snapshot: '+paper['source_revision'],
        'Corpus: '+md_text(paper['experiment'] or 'Fixture'),
        'Model: '+md_text(paper['model_identity']['served_model']),'',
        '**Source-extracted findings and model interpretations remain distinct. Adversarial review is model-generated and is not independent scientific verification.**','']
    by_id={s['id']:s for s in paper['sections']}
    for identity,title in SECTIONS:
        lines += ['## '+title,'']
        for row in audit.get('withheld_paragraphs',[]):
            if row['section_id']==identity:lines += ['Model-authored inventory bookkeeping was withheld after count validation. Canonical counts are shown directly; the original paragraph remains in the audit.','']
        if identity=='coverage':
            lines += [f'- {label}: {value if value is not None else "Not recorded"}' for label,value in stats(evidence)]
            lines += ['',md_text(evidence['inventory']['counting_rules']),'']
            lines += ['Root question: '+md_text(evidence['identity']['root_question']),'',
                'Structural types: '+md_text(dumps(evidence['inventory']['structural_types'])),
                'Scientific types (same units): '+md_text(dumps(evidence['inventory']['scientific_types'])),
                'Research-node statuses: '+md_text(dumps(evidence['node_statuses'])),'']
        if identity=='methodology':
            lines += ['Recorded Mira research cycles: '+str(evidence['identity']['research_cycles'])+
                '; recorded synthesis cycles: '+str(evidence['identity']['synthesis_cycles'])+
                '. Activity counters do not establish successful scientific synthesis.','']
        if identity=='synthesis':
            lines += ['Published synthesis memories: '+str(evidence['inventory']['synthesis_memories'])+'.',
                'Recorded activity: '+md_text(dumps(evidence['synthesis_summary'])),'']
        for p in by_id[identity]['paragraphs']:
            lines += [md_text(p['text'])+' '+ ' '.join('['+'KU:'+u+']('+knowledge_url(u,paper['experiment'])+')' for u in cited_units(p)),
                '*Recorded role: '+p['kind'].replace('_',' ')+'.*','']
            for concern in current_concerns(audit):
                if concern['claim_id']==p['id']:lines += ['**Unresolved review concern:** '+md_text(concern['reason']),'']
        if identity=='mathematics':
            for u in evidence['units'].values():
                if 'equation' not in u:continue
                e=u['equation'];lines += ['### '+md_text(e['label']),'', '    '+e['expression'].replace('\n','\n    '),'',
                    'Unit: [KU:'+u['id']+']('+knowledge_url(u['id'],paper['experiment'])+')','',
                    'Variables: '+md_text(dumps(e['variables'])),'Units: '+md_text(dumps(e['units'])),
                    'Recorded assumptions: '+md_text(dumps(e['assumptions'])),'Attribution: '+md_text(e['provenance']),'']
        if identity=='questions':
            for u in evidence['units'].values():
                if u['structural_type']=='question':lines += ['- '+md_text(u['fields']['Question'])+' [KU:'+u['id']+']('+knowledge_url(u['id'],paper['experiment'])+') · state: '+str(u['question_state'])]
            lines += ['']
    lines += ['## Glossary of Scientific Terms','']
    for term in evidence.get('glossary',{}).values():
        d=term['definition'];lines += ['### '+md_text(term['term'])+' ('+term['id']+')','']
        if d:
            lines += [md_text(d['text']),'', 'Provenance: '+md_text(dumps({k:v for k,v in d.items() if k!='text'})),'']
        else:lines += ['No accepted definition. '+md_text(term['enrichment'].get('reason','Meaning remains unverified.')),'']
        lines += ['[Canonical glossary entry](/glossary#'+term['id']+')','']
    used=sorted(used_sources(paper,evidence))
    lines += ['## References','']
    for identity in used:
        s=evidence['sources'][identity];lines += ['- '+md_text(s.get('title',identity))+' · '+md_text(identity)+' · '+md_text(s.get('url',''))]
    lines += ['', '## Appendix: Knowledge Inventory','',
        'Considered: '+str(len(paper['coverage_ledger']))+'; cited in model narrative: '+str(sum(r['finally_cited'] for r in paper['coverage_ledger'].values()))+'.','']
    for row in paper['coverage_ledger'].values():
        u=evidence['units'][row['id']];lines += ['- [KU:'+row['id']+']('+knowledge_url(row['id'],paper['experiment'])+') · '+md_text(u['label'])+' · '+('Cited' if row['finally_cited'] else 'Considered; not cited in model narrative')]
    lines += ['', '## Review limitations and unresolved concerns','']
    for concern in current_concerns(audit):lines += ['- '+md_text(concern['claim_id']+': '+concern['reason'])]
    lines += [md_text(audit['validation']['limitations']),'']
    return '\n'.join(lines)


def content_policy():
    h=lambda p:b64encode(sha256(p.read_bytes()).digest()).decode()
    return "default-src 'none'; script-src 'sha256-"+h(ASSETS/'search.js')+"'; style-src 'sha256-"+h(ASSETS/'style.css')+"'; base-uri 'none'; form-action 'none'"


def html(audit,*,stale=False):
    paper=audit['paper'];evidence=audit['evidence'];experiment=paper['experiment'];by_id={s['id']:s for s in paper['sections']}
    def ku(identity):return '<a class="ku-citation" target="_top" href="'+escape(knowledge_url(identity,experiment),quote=True)+'">[KU:'+escape(identity)+']</a>'
    def prose(value):
        value=unescape(value)
        pattern=r'\[(KU|TERM|SRC):([^\]]+)\]'
        result=[];cursor=0
        for match in re.finditer(pattern,value):
            result.append(escape(value[cursor:match.start()]));kind,identity=match.group(1,2)
            if kind=='KU' and identity in evidence['units']:result.append(ku(identity))
            elif kind=='TERM' and identity in evidence.get('glossary',{}):result.append('<a target="_top" href="/glossary#'+escape(quote(identity),quote=True)+'">'+escape(evidence['glossary'][identity]['term'])+'</a>')
            elif kind=='SRC' and identity in evidence['sources']:result.append('<a href="#source-'+str(list(evidence['sources']).index(identity))+'">'+escape(identity)+'</a>')
            else:result.append(escape(match[0]))
            cursor=match.end()
        result.append(escape(value[cursor:]));return ''.join(result)
    parts=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="'+escape(content_policy(),quote=True)+'">',
        '<meta name="mira-sor-revision" content="'+escape(paper['source_revision'],quote=True)+'">',
        '<title>'+escape(paper['title'])+' · Mira</title><style>'+(ASSETS/'style.css').read_text()+'</style></head><body>',
        '<header><a target="_top" href="/?view=overview">Mira Brain Viewer</a><a target="_top" href="/glossary">Glossary</a><a target="_top" href="/?view=state-of-research">State of Research workspace</a></header>',
        '<div class="paper-layout"><nav aria-label="Paper sections"><strong>State of Research</strong><label for="paper-search">Search report</label>',
        '<input id="paper-search" type="search" autocomplete="off"><p id="paper-match-count" role="status" aria-live="polite"></p><ul id="paper-results"></ul>',
        '<ol>'+''.join('<li><a href="#'+i+'">'+escape(t)+'</a></li>' for i,t in SECTIONS)+
        '<li><a href="#glossary">Glossary</a></li><li><a href="#references">References</a></li><li><a href="#inventory">Knowledge inventory</a></li></ol></nav><main>',
        *(['<p class="stale" role="alert">Research has changed since this report was generated.</p>'] if stale else []),
        '<h1>'+escape(paper['title'])+'</h1>',
        '<p class="byline">Generated '+escape(paper['generated_at'])+'<br>Research snapshot '+escape(paper['source_revision'])+'<br>Corpus '+escape(experiment or 'Controlled fixture')+
        '<br>Model '+escape(paper['model_identity']['served_model'])+'<br>Adversarial review performed; scientific verification not established.</p>',
        '<p class="caution">Adversarial review performed by the same configured model. This report and its review are not independent scientific verification or patient-specific advice.</p>']
    for identity,title in SECTIONS:
        parts += ['<section id="'+identity+'" tabindex="-1"><h2>'+escape(title)+'</h2>']
        for row in audit.get('withheld_paragraphs',[]):
            if row['section_id']==identity:parts += ['<p class="note">Model-authored inventory bookkeeping was withheld after count validation. Canonical counts are shown directly; the original paragraph remains in the audit.</p>']
        if identity=='coverage':
            parts += ['<dl class="inventory-stats">'+''.join('<div><dt>'+escape(label)+'</dt><dd>'+str(value if value is not None else 'Not recorded')+'</dd></div>' for label,value in stats(evidence))+'</dl>',
                '<p class="note">'+escape(evidence['inventory']['counting_rules'])+'</p>']
            parts += ['<p><strong>Root research question:</strong> '+escape(evidence['identity']['root_question'])+'</p>',
                '<details><summary>Canonical type counts and research-tree status</summary><pre>'+escape(dumps({
                    'structural_types':evidence['inventory']['structural_types'],'scientific_types':evidence['inventory']['scientific_types'],
                    'research_node_statuses':evidence['node_statuses'],'research_questions':evidence['research_questions']}))+'</pre></details>']
        if identity=='methodology':
            parts += ['<p class="recorded">Recorded Mira research cycles: '+str(evidence['identity']['research_cycles'])+
                '; synthesis cycles: '+str(evidence['identity']['synthesis_cycles'])+
                '. These are activity counters, not a count of successful scientific syntheses.</p>']
        if identity=='synthesis':
            parts += ['<p class="recorded">Canonical published synthesis memories: <strong>'+str(evidence['inventory']['synthesis_memories'])+'</strong>.</p>',
                '<details><summary>Recorded synthesis activity</summary><pre>'+escape(dumps(evidence['synthesis_summary']))+'</pre></details>']
        previous_node=None
        for p in by_id[identity]['paragraphs']:
            label=p['id'].split('.',1)[0]
            node=next((t.get('node_id') for t in audit['trials'] if t['label']==label),None)
            if node and node!=previous_node and identity in {'findings','conflicts','limitations','questions'}:
                previous_node=node
                parts += ['<h3>Research question '+escape(node)+'</h3><p class="note">'+escape(evidence['research_questions'][node]['question'])+'</p>']
            parts += ['<div class="claim" id="'+escape(p['id'],quote=True)+'"><p>'+prose(p['text'])+' <span class="citations">'+' '.join(ku(u) for u in cited_units(p))+'</span></p>',
                '<small>'+escape(p['kind'].replace('_',' '))+'</small></div>']
            for concern in current_concerns(audit):
                if concern['claim_id']==p['id']:parts += ['<p class="caution">Unresolved review concern: '+escape(concern['reason'])+'</p>']
        if identity=='mathematics':
            for u in evidence['units'].values():
                if 'equation' not in u:continue
                e=u['equation'];parts += ['<article class="equation"><h3>'+escape(e['label'])+'</h3><pre class="expression">'+escape(e['expression'])+'</pre><p>'+ku(u['id'])+'</p>',
                    '<dl>'+''.join('<dt>'+escape(k)+'</dt><dd>'+escape(v)+' · '+escape(e['units'].get(k,'Units not recorded'))+'</dd>' for k,v in e['variables'].items())+'</dl>',
                    '<p>Recorded assumptions: '+escape('; '.join(e['assumptions']) or 'No explicit assumptions recorded; this does not establish universal applicability.')+'</p>',
                    '<p class="note">'+escape(e['provenance'])+'</p></article>']
        if identity=='questions':
            parts += ['<details open><summary>Complete recorded question-unit inventory</summary><ul>']
            for u in evidence['units'].values():
                if u['structural_type']=='question':parts += ['<li>'+prose(u['fields']['Question'])+' '+ku(u['id'])+' · state: '+escape(str(u['question_state']))+'</li>']
            parts += ['</ul></details>']
        parts += ['</section>']
    parts += ['<section id="glossary"><h2>Glossary of Scientific Terms</h2>']
    for term in evidence.get('glossary',{}).values():
        d=term['definition'];parts += ['<article class="term"><h3><a target="_top" href="/glossary#'+escape(quote(term['id']),quote=True)+'">'+escape(term['term'])+'</a> <small>'+escape(term['id'])+'</small></h3>']
        if d:
            label='Provisional, model-generated; not independently verified' if d.get('origin')=='llm_generated' else 'Authoritative terminology' if 'authority'in d else 'Source-supported terminology'
            parts += ['<p>'+prose(d['text'])+'</p><p class="note">'+label+'</p><details><summary>Definition provenance and qualifications</summary><pre>'+escape(dumps({k:v for k,v in d.items() if k!='text'}))+'</pre></details>']
        else:parts += ['<p>No accepted definition. '+prose(term['enrichment'].get('reason','Unresolved terminology.'))+'</p>']
        parts += ['</article>']
    parts += ['</section><section id="references"><h2>References</h2><ol>']
    used=used_sources(paper,evidence)
    for index,(identity,s) in enumerate(evidence['sources'].items()):
        if identity not in used:continue
        url=source_url(s.get('url',''));parts += ['<li id="source-'+str(index)+'">'+prose(s.get('title',identity))+' · '+escape(identity)+
            (' · <a href="'+escape(url,quote=True)+'" rel="noopener noreferrer">Source</a>' if url else '')+'</li>']
    parts += ['</ol></section><section id="inventory"><h2>Appendix: Knowledge Inventory</h2>',
        '<p>All '+str(len(paper['coverage_ledger']))+' units were considered. '+str(sum(r['finally_cited'] for r in paper['coverage_ledger'].values()))+' are cited in model narrative; canonical equations and open questions are also reproduced directly.</p><ul>']
    for row in paper['coverage_ledger'].values():parts += ['<li>'+ku(row['id'])+' · '+escape(evidence['units'][row['id']]['label'])+' · '+('Cited' if row['finally_cited'] else 'Considered; not cited in model narrative')+'</li>']
    parts += ['</ul></section><section id="review-concerns"><h2>Unresolved review concerns</h2>']
    concerns=current_concerns(audit)
    if not concerns:parts += ['<p>No unresolved objections recorded by this pipeline. This is not a scientific clearance.</p>']
    for row in concerns:parts += ['<p>'+escape(row['claim_id']+': '+row['reason'])+'</p>']
    parts += ['<p class="note">'+escape(audit['validation']['limitations'])+'</p></section>',
        '<details id="adversarial-history"><summary>Original drafts, adversarial reviews and revision dispositions</summary>',
        '<p>Admitted objections passed quotation and reference checks. This is structural validation, not scientific adjudication.</p>']
    for trial in audit['trials']:
        parts += ['<details><summary>'+escape(trial['label'])+' · original draft</summary><pre>'+escape(dumps(trial['draft']))+'</pre></details>',
            '<details><summary>'+escape(trial['label'])+' · challenger and revision history</summary><pre>'+escape(dumps({k:trial[k] for k in ('review','valid_review','rejected_objections','revision','initial_validation','final_validation')}))+'</pre></details>']
        if trial.get('previous_trial'):
            parts += ['<details><summary>'+escape(trial['label'])+' · earlier retained evaluation before implementation correction</summary><pre>'+escape(dumps(trial['previous_trial']))+'</pre></details>']
    parts += ['</details><details id="generation-provenance"><summary>Generation provenance and structural validation</summary><pre>'+escape(dumps(audit['manifest']))+'</pre></details>',
        '<details id="withheld-bookkeeping"><summary>Withheld model inventory bookkeeping</summary><pre>'+escape(dumps(audit.get('withheld_paragraphs',[])))+'</pre></details>',
        '</main></div><script>'+(ASSETS/'search.js').read_text()+'</script></body></html>']
    return '\n'.join(parts)
