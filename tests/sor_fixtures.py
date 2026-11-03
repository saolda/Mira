"""Explicit synthetic scientific evidence; never installed into the active corpus."""
from mira.format import Memory,Unit,Equation,equation_fields
from mira.knowledge_inspection import build_snapshot
from mira.research_tree import initial
from mira.state_of_research import project


def memory(identity,source,title,findings):
    m=Memory(identity,title,'Controlled test evidence; not a real scientific publication.',metadata={
        'node_id':'q1','kind':'research','source_memories':[],'synthesized_by':None,'created_order':int(identity[1:],36),
        'source':{'id':source,'title':title,'url':'https://example.invalid/'+identity,'content_kind':'controlled_fixture'}})
    for text,qualification in findings:
        anchor=m.allocate('f');m.units.append(Unit(anchor,'Finding',{'Kind':'finding','Proposition':text,'Qualification':qualification}))
    return m


def quantitative():
    m=memory('r1','fixture:geometry','Controlled fixture: fixed-shape exponential growth',[
        ('For a sphere of fixed shape, volume V is proportional to the cube of diameter D.',
         'Synthetic mathematical fixture. Fixed shape is required; this is not patient evidence.'),
        ('A synthetic object doubles in volume over 28 days while its volume follows a constant exponential growth rate.',
         'The 28-day interval is an invented controlled test value, not an observed pulmonary-lesion cohort.'),
        ('Under fixed shape and constant exponential growth, diameter doubling takes three times the volume doubling time: 84 days for a 28-day volume doubling time.',
         'This conditional calculation does not establish empirical growth kinetics, infection, malignancy or patient-specific diagnostic probability.')])
    m.units.append(Unit(m.allocate('e'),'Equation',{'Equation':'e_r1_1'}))
    e=Equation('e_r1_1','r1','Sphere volume','V = (pi / 6) * D^3',{'V':'volume','D':'diameter'},['Spherical fixed shape','Consistent length units'],
        'Controlled mathematical fixture, not clinical evidence.',units={'V':'length cubed','D':'length'})
    m.units[-1].fields=equation_fields(e)
    state=initial('How do volume and diameter doubling times differ under fixed-shape exponential growth?',['fixture'])
    return project(build_snapshot('b'*64,[m],[e],state,{}),experiment='controlled-quantitative-fixture')


def incompatible():
    a=memory('r1','fixture:adult-screening','Controlled fixture: adult screening CT',[
        ('In a synthetic adult screening CT cohort, spiculation has an odds ratio of 1.8 for malignancy.',
         'Invented test estimate, not a real study. Endpoint: histological malignancy. Adults at screening; no lesion-growth interval measured.')])
    b=memory('r2','fixture:child-infection','Controlled fixture: febrile childhood infection',[
        ('In a synthetic febrile-childhood cohort, an imaging feature has an odds ratio of 0.4 for persistence of fever after treatment.',
         'Invented test estimate, not a real study. Endpoint: fever persistence; chest radiographs, not volumetric CT. No malignancy comparison and no four-week volume-doubling measurement.')])
    state=initial('Can incompatible populations and endpoints establish a diagnostic preference for infection over malignancy?',['fixture'])
    return project(build_snapshot('c'*64,[a,b],[],state,{}),experiment='controlled-incompatible-fixture')


def candidate(evidence,kind='quantitative'):
    if kind=='quantitative':
        text='The volume doubling time of 28 days is identical to the diameter doubling time of 28 days. This proves that a rapidly growing pulmonary lesion is infectious.'
        ids=['r1#f1','r1#f2','r1#f3'];section='mathematics'
    else:
        text='Dividing the adult screening odds ratio of 1.8 by the childhood fever odds ratio of 0.4 establishes a 4.5-fold diagnostic advantage for infection over malignancy in rapidly doubling adult nodules.'
        ids=['r1#f1','r2#f1'];section='findings'
    return {'schema':'mira.sor.draft/1','title':'Explicitly labelled erroneous draft candidate for controlled adversarial evaluation',
        'sections':[{'id':section,'paragraphs':[{'id':'seeded-error','kind':'interpretation','text':text,'unit_ids':ids}]},
            {'id':'limitations','paragraphs':[{'id':'scope','kind':'limitation','text':'This is a deliberately erroneous controlled test candidate, not a research finding or a patient assessment.','unit_ids':[]}]}]}
