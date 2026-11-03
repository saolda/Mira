"""Versioned SOR data contracts and deterministic checks; no model instructions."""
import re
from .format import dumps, require

SECTIONS = [('abstract','Abstract'),('introduction','1. Introduction'),('methodology','2. Research Methodology'),
    ('coverage','3. Research Corpus and Evidence Coverage'),('findings','4. Principal Findings'),
    ('mathematics','5. Mathematical Relationships'),('synthesis','6. Scientific Synthesis'),
    ('conflicts','7. Conflicting Evidence and Alternative Interpretations'),('limitations','8. Research Limitations'),
    ('questions','9. Open Research Questions'),('progress','10. Research Progress'),('conclusions','11. Conclusions'),
    ('directions','12. Recommended Research Directions')]
KINDS = ['source_finding','interpretation','hypothesis','recorded_question','recommendation','process','limitation']
CATEGORIES = ['demonstrated_error','unsupported_claim','scientific_disagreement','verification_concern','omitted_evidence']
DISPOSITIONS = ['accepted','rejected','partially_accepted','unresolved']


def contract(stage, section_ids):
    claim={'type':'object','additionalProperties':False,'required':['id','kind','text','unit_ids'],
        'properties':{'id':{'type':'string'},'kind':{'enum':KINDS},'text':{'type':'string'},
                      'unit_ids':{'type':'array','items':{'type':'string'}}}}
    from copy import deepcopy
    scientific=deepcopy(claim);scientific['properties']['kind']={'enum':['source_finding','interpretation','hypothesis','recorded_question']}
    scientific['properties']['unit_ids']['minItems']=1
    contextual=deepcopy(claim);contextual['properties']['kind']={'enum':['recommendation','process','limitation']}
    claim={'oneOf':[scientific,contextual]}
    draft={'type':'object','additionalProperties':False,'required':['schema','title','sections'],
        'properties':{'schema':{'const':'mira.sor.draft/1'},'title':{'type':'string'},
            'sections':{'type':'array','minItems':len(section_ids),'maxItems':len(section_ids),'items':{'type':'object','required':['id','paragraphs'],'additionalProperties':False,
                'properties':{'id':{'enum':section_ids},'paragraphs':{'type':'array','items':claim}}}}}}
    objection={'type':'object','additionalProperties':False,
        'required':['id','claim_id','assertion','category','severity','unit_ids','explanation','correction'],
        'properties':{'id':{'type':'string'},'claim_id':{'type':'string'},'assertion':{'type':'string'},
            'category':{'enum':CATEGORIES},'severity':{'enum':['major','minor']},
            'unit_ids':{'type':'array','minItems':1,'items':{'type':'string'}},'explanation':{'type':'string'},'correction':{'type':'string'}}}
    if stage=='SOR1': return draft
    if stage=='SOR2': return {'type':'object','additionalProperties':False,'required':['schema','objections','summary'],
        'properties':{'schema':{'const':'mira.sor.review/1'},'objections':{'type':'array','items':objection},'summary':{'type':'string'}}}
    return {'type':'object','additionalProperties':False,'required':['schema','draft','dispositions'],
        'properties':{'schema':{'const':'mira.sor.revision/1'},'draft':draft,
            'dispositions':{'type':'array','items':{'type':'object','additionalProperties':False,
                'required':['objection_id','disposition','explanation','unit_ids'],
                'properties':{'objection_id':{'type':'string'},'disposition':{'enum':DISPOSITIONS},
                    'explanation':{'type':'string'},'unit_ids':{'type':'array','items':{'type':'string'}}}}}}}


def fields(value,keys):require(isinstance(value,dict) and set(value)==set(keys),'unexpected/missing SOR fields')
def text(value,limit=12000):require(isinstance(value,str) and value.strip() and len(value)<=limit and '\x00' not in value,'invalid SOR text')

def references(values,evidence):
    require(isinstance(values,list) and len(values)==len(set(values)) and all(isinstance(v,str) and v in evidence['units'] for v in values),'invalid knowledge-unit references')


def cited_units(paragraph):
    return list(dict.fromkeys([*paragraph['unit_ids'],*re.findall(r'\b[rs][1-9a-z][0-9a-z]*#[fqei][1-9a-z][0-9a-z]*\b',paragraph['text'])]))


def validate_draft(value,evidence,section_ids):
    fields(value,['schema','title','sections']);require(value['schema']=='mira.sor.draft/1','invalid draft schema');text(value['title'],500)
    require(isinstance(value['sections'],list),'sections must be an array')
    ids=[];claims=set()
    for section in value['sections']:
        fields(section,['id','paragraphs']);require(section['id'] in section_ids and section['id'] not in ids,'invalid/duplicate section');ids.append(section['id'])
        require(isinstance(section['paragraphs'],list) and len(section['paragraphs'])<=30,'invalid paragraph list')
        for claim in section['paragraphs']:
            fields(claim,['id','kind','text','unit_ids']);text(claim['id'],80);text(claim['text']);references(claim['unit_ids'],evidence)
            require(claim['id'] not in claims,'duplicate claim ID');claims.add(claim['id'])
            require(claim['kind'] in KINDS,'invalid epistemic claim type')
            if claim['kind'] in {'source_finding','interpretation','hypothesis','recorded_question'}:
                require(claim['unit_ids'],'scientific claim lacks citations')
            for identity in re.findall(r'\[KU:([^\]]+)\]',claim['text']):require(identity in evidence['units'],'inline citation does not resolve to supplied evidence')
            # Catch malformed anchors too (for example r6#2), rather than
            # silently treating an obvious broken citation as ordinary prose.
            for identity in re.findall(r'\b[rs][1-9a-z][0-9a-z]*#[0-9a-z]+\b',claim['text']):require(identity in evidence['units'],'raw knowledge citation does not resolve to supplied evidence: '+identity)
            for identity in re.findall(r'\[TERM:([^\]]+)\]',claim['text']):require(identity in evidence.get('glossary',{}),'invalid glossary reference')
            for identity in re.findall(r'\[SRC:([^\]]+)\]',claim['text']):require(identity in evidence['sources'],'invalid source reference')
            for doi in re.findall(r'\b10\.\d{4,9}/[^\s\]\)]+',claim['text']):
                require(any(doi.rstrip('.,;').casefold() in dumps(s).casefold() for s in evidence['sources'].values()),'unrecorded DOI')
            for pmid in re.findall(r'\bpmid\s*:?\s*(\d+)\b',claim['text'],flags=re.I):
                require(any(re.search(r'(?<!\d)'+re.escape(pmid)+r'(?!\d)',dumps(s)) for s in evidence['sources'].values()),'unrecorded PMID')
    require(set(ids)==set(section_ids),'required sections missing')
    require(claims,'No model-authored report paragraphs supplied')
    return value


def validate_review(value,draft,evidence):
    fields(value,['schema','objections','summary']);require(value['schema']=='mira.sor.review/1','invalid review schema');text(value['summary'])
    require(isinstance(value['objections'],list) and len(value['objections'])<=24,'invalid objection list')
    claims={p['id']:p for s in draft['sections'] for p in s['paragraphs']};ids=set()
    for row in value['objections']:
        fields(row,['id','claim_id','assertion','category','severity','unit_ids','explanation','correction'])
        for key in ['id','claim_id','assertion','explanation','correction']:text(row[key])
        require(row['id'] not in ids,'duplicate objection');ids.add(row['id'])
        require(row['claim_id'] in claims,'review points to unknown claim')
        require(row['assertion'] in claims[row['claim_id']]['text'],'criticised assertion is not an exact draft quotation')
        require(row['category'] in CATEGORIES and row['severity'] in {'major','minor'},'invalid review classification')
        references(row['unit_ids'],evidence);require(row['unit_ids'],'objection lacks evidence references')
    return value


def validate_revision(value,draft,review,evidence,section_ids):
    fields(value,['schema','draft','dispositions']);require(value['schema']=='mira.sor.revision/1','invalid revision schema')
    validate_draft(value['draft'],evidence,section_ids)
    require(isinstance(value['dispositions'],list),'invalid review dispositions')
    ids=[]
    for row in value['dispositions']:
        fields(row,['objection_id','disposition','explanation','unit_ids']);text(row['explanation']);references(row['unit_ids'],evidence)
        require(row['disposition'] in DISPOSITIONS,'invalid objection disposition');ids.append(row['objection_id'])
    require(len(ids)==len(set(ids)) and set(ids)=={r['id'] for r in review['objections']},'each objection needs exactly one disposition')
    return value


def scientific_checks(draft,evidence):
    """Transparent warning rules, not an automated scientific truth judgement."""
    concerns=[];errors=[]
    for section in draft['sections']:
        for claim in section['paragraphs']:
            body=claim['text'];lower=body.casefold();units=[evidence['units'][i] for i in cited_units(claim) if i in evidence['units']]
            def add(kind,reason,hard=False):
                (errors if hard else concerns).append({'claim_id':claim['id'],'category':kind,'reason':reason,'unit_ids':claim['unit_ids']})
            unknown=sorted({i for i in [*claim['unit_ids'],*re.findall(r'\b[rs][1-9a-z][0-9a-z]*#[0-9a-z]+\b',body)] if i not in evidence['units']})
            if unknown:
                add('unresolved_reference','Knowledge-unit citations do not resolve in the supplied source snapshot.',True)
                errors[-1].update(observed=unknown,available_unit_ids=list(evidence['units']))
            if claim['kind'] in {'source_finding','interpretation'} and units and all(u['structural_type']=='question' for u in units):
                add('question_as_evidence','Only question units are cited for an empirical interpretation.')
            for match in re.finditer(r'\b(?:independently scientifically verified|scientifically verified|proves?.{0,100}(?:infection|infectious|malignancy)|definitively establishes)\b',lower):
                prefix=lower[max(0,match.start()-65):match.start()]
                if not re.search(r'\b(?:not|no|never|without|cannot|unverified)\b',prefix):add('unjustified_certainty','Scientific verification or definitive diagnostic language requires external adjudication.')
            if re.search(r'\b(?:volume|volumetric).{0,65}doubling.{0,65}(?:equals?|identical|same as).{0,45}diameter',lower):
                add('mathematical_concern','Volume and diameter doubling times are distinct under constant-shape exponential growth.')
            bound=re.search(r'(?:≤|<=)\s*(\d+(?:\.\d+)?)\s*days',lower)
            four_weeks=re.search(r'(?:four|4)[ -]week',lower)
            if bound and four_weeks and float(bound[1])>=28 and re.search(r'does not encompass|does not include|significantly slower',lower):
                add('interval_membership','28 days satisfies the recorded ≤ '+bound[1]+' day threshold. Category membership does not establish actual 28-day observations or an etiology-specific subgroup analysis.')
            if claim['kind']!='recorded_question' and re.search(r'(?:four|4)[ -]week.{0,55}(?:typical|typically suggestive|timeframe typical).{0,12}(?:of |for )?infection',lower):
                add('unverified_question_premise','The recorded question contains an infection-kinetics premise; repeating it does not establish independent evidence for that premise.')
            for pattern,key in [(r'\b(\d+) research memories\b','research_memories'),(r'\b(\d+) synthesis memories\b','synthesis_memories'),(r'\b(\d+) knowledge units\b','total_units')]:
                for match in re.finditer(pattern,lower):
                    if int(match[1])!=evidence['inventory'][key]:
                        add('inventory_mismatch','Generated inventory count differs from the canonical inventory.',True)
                        errors[-1].update(inventory_key=key,observed=int(match[1]),expected=evidence['inventory'][key])
            for match in re.finditer(r'\b(?:yield(?:ed|ing|s)?|contains?|comprises?|total(?: of)?)\s+(\d+)\s+(?:units of evidence|evidence units|scientific units)\b',lower):
                if int(match[1])!=evidence['inventory']['total_units']:
                    add('inventory_mismatch','Sources yielding evidence and the number of knowledge units are different inventories.',True)
                    errors[-1].update(inventory_key='total_units',observed=int(match[1]),expected=evidence['inventory']['total_units'])
            if evidence['inventory']['synthesis_memories']==0 and re.search(r'\b(?:successful|published|completed) synthes(?:is|ized) (?:discoveries|findings|memories)\b',lower) and not re.search(r'\b(?:no|not|zero|without)\b',lower):
                add('synthesis_status','No published synthesis exists in this source snapshot.',True)
    return {'schema':'mira.sor.validation/1','structural_valid':True,'publication_errors':errors,
        'scientific_concerns':concerns,'scientifically_verified':False,
        'limitations':'Deterministic reference/count rules and lexical warnings cannot establish scientific entailment, diagnose patients, or replace source review.'}
