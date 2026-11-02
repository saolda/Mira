"""Definition provenance, contextual preference and bounded R1 fallback admission.

These deterministic scope checks are conservative lexical heuristics, not a
scientific meaning classifier. Every generated definition remains provisional.
"""
import re
import unicodedata

from .format import digest, dumps, require

PROVISIONAL_FIELDS = {'origin', 'verification', 'term_id', 'text', 'scope', 'ambiguity',
    'model', 'interaction_ref', 'event_ref', 'template_sha256', 'request_sha256', 'context'}
GENERIC_SCOPE = {'mesh concept', 'general', 'unspecified', 'terminology'}
STOP = set('what which when where why how does do is are can could would should the a an of to in for and or with under about this that these those from scientific research question definition meaning term relevant context use used using'.split())


def normalize(text):
    value=unicodedata.normalize('NFKC',text).casefold()
    return ' '.join(re.sub(r'[-‐‑–—]', ' ', value).split())


def words(text):
    return {w for w in re.findall(r'[^\W_]+', normalize(text)) if len(w)>2 and w not in STOP}


def provisional(row):
    return row.get('origin') == 'llm_generated'


def status(definitions):
    sourced = [d for d in definitions if not provisional(d)]
    if not sourced: return 'provisional' if definitions else 'candidate'
    return 'source_defined' if len({normalize(d['text']) for d in sourced}) == 1 else 'multiple_definitions'


def text(value, limit, *, empty=False):
    require(isinstance(value, str) and len(value)<=limit and (empty or value.strip()) and
        not any(ord(c)<32 and c not in '\n\r\t' or 0xD800<=ord(c)<=0xDFFF for c in value),
        'invalid provisional definition text')


def validate(row, term_id):
    require(isinstance(row,dict) and set(row)==PROVISIONAL_FIELDS, 'invalid provisional definition fields')
    require(row['origin']=='llm_generated' and row['verification']=='provisional' and row['term_id']==term_id,
        'invalid provisional definition identity/status')
    text(row['text'],600);text(row['scope'],160);text(row['ambiguity'],400,empty=True);text(row['model'],1000)
    require(isinstance(row['context'],dict) and set(row['context'])=={'node_id','question'}, 'invalid definition context')
    require(isinstance(row['context']['node_id'],str) and re.fullmatch(r'q[1-9][0-9]*',row['context']['node_id']), 'invalid definition node')
    text(row['context']['question'],20000)
    require(isinstance(row['interaction_ref'],str) and re.fullmatch(r'interactions/[0-9]{8,}-[0-9a-f]{32}/request\.json',row['interaction_ref']), 'invalid definition interaction')
    require(isinstance(row['event_ref'],str) and re.fullmatch(r'events/[0-9a-f]{32}\.json',row['event_ref']), 'invalid definition event')
    for k in ['template_sha256','request_sha256']:
        require(isinstance(row[k],str) and re.fullmatch(r'[0-9a-f]{64}',row[k]), 'invalid definition prompt hash')


def context(question, node_id, node_ids=()):
    return {'question':question,'node_id':node_id,'node_ids':list(node_ids) or [node_id]}


def same_scope(row, record, current):
    old=row['context']
    if normalize(old['question'])==normalize(current['question']): return True
    names=words(' '.join([record['term'],*record['aliases']]))
    a,b=words(old['question'])-names,words(current['question'])-names
    # Shared contextual vocabulary conservatively retains a definition. A new
    # cycle, punctuation, word order or stop words never create a new meaning.
    if a & b: return True
    if len(a)>=3 and len(b)>=3: return False
    return old['node_id']==current['node_id']


def applicable(row, record, current):
    if current is None: return True
    if provisional(row): return same_scope(row,record,current)
    names=words(' '.join([record['term'],*record['aliases']]))
    query=words(current['question'])-names
    if 'authority' not in row:
        return row['evidence']['node_id']==current['node_id'] or bool((words(row['text'])-names) & query)
    scope=normalize(row.get('scope',''))
    if scope and scope not in GENERIC_SCOPE:
        return bool((words(scope+' '+row['text'])-names) & query)
    # MeSH's generic scope label is not evidence of contextual applicability.
    # Compare its actual description with the question and locally grounded term
    # passages. A bare acronym alone never establishes scientific equivalence.
    grounding=' '.join(e['passage'] for e in record['evidence'] if e['node_id']==current['node_id'] or
        e['node_id'] in current.get('node_ids',[]) and (words(e['passage'])-names) & query)
    return bool((words(row['text'])-names) & (query | (words(grounding)-names)))


def preferred(record, current=None):
    rows=[d for d in record['definitions'] if applicable(d,record,current)]
    def rank(d): return (0 if 'authority' in d else 2 if provisional(d) else 1, normalize(d['text']), dumps(d))
    return sorted(rows,key=rank)


def eligible(record, current):
    return not preferred(record,current)


def proposals(values, supplied, current):
    """Reject optional entries independently; never change search components."""
    accepted=[];rejected=[]
    if not isinstance(values,list):
        return [],[{'field':'provisional_definitions','error':'provisional_definitions must be an array'}]
    by_id={e['id']:e for e in supplied};seen=set()
    for index,value in enumerate(values):
        try:
            require(index<3,'at most three provisional definitions per R1')
            require(isinstance(value,dict) and set(value)=={'term_id','definition','scope','ambiguity'}, 'invalid provisional definition proposal fields')
            identity=value['term_id']
            require(isinstance(identity,str) and re.fullmatch(r'g[1-9][0-9]*',identity) and identity in by_id,
                'definition term must be in the supplied glossary')
            require(identity not in seen,'duplicate provisional definition proposal')
            seen.add(identity)
            require(by_id[identity].get('definition_eligible') is True,'term already has an applicable definition')
            text(value['definition'],600);text(value['scope'],160);text(value['ambiguity'],400,empty=True)
            require(not re.search(r'https?://|\b(?:PMID|doi)\s*:|\b10\.\d{4,9}/',value['definition'],re.I),
                'provisional definitions must not invent citations')
            unresolved=r'\b(?:specific meaning|term.s meaning|meaning of (?:this|the) (?:term|abbreviation))\b.{0,60}\b(?:cannot|can.t|indeterminate)\b|\bsemantically indeterminate\b'
            require(not re.search(unresolved,value['definition']+' '+value['ambiguity'],re.I),
                'unresolved term meaning requires abstention')
            accepted.append(value)
        except (ValueError,TypeError,KeyError) as exc:
            rejected.append({'field':'provisional_definitions','index':index,'error':str(exc)})
    return accepted,rejected
