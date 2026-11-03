"""Accepted terminology and verbatim, attributed excluded proposals in both views."""
from copy import deepcopy
from html import escape
from pathlib import Path
import re
import unittest

from mira import glossary, glossary_definitions as definitions, glossary_view
from mira.format import digest, dumps
from mira.glossary_enrichment import coverage
from test_glossary import record
from test_glossary_view import Document
from test_provisional_definitions import generated

# The original g30 text is a rejected model proposal, not verified science.
ORIGINAL = ('A radiological sign on CT imaging where air-filled bronchi are visible within a pulmonary nodule or consolidation. '
    'In the context of differentiating malignant solid nodules from ground-glass opacities (GGOs), its presence is '
    'significantly more frequent in GGOs (24%) than in malignant solid nodules (0%).')
ISSUE = 'The study-specific modifier natural has not been independently established.'
REASON = ISSUE + ' A general air bronchogram does not establish this exact modified meaning.'


def clarification_fixture():
    row=record(1,'natural air bronchograms');row['status']='candidate';row['aliases']=['Natural bronchogram sign']
    rows=[generated(text=ORIGINAL,model='original-model'),
          generated(text='A later model proposal comparing air-filled bronchi in two malignant cohorts.',model='second-model',interaction_ref='interactions/00000002-'+'b'*32+'/request.json'),
          generated(text='A general description of air-filled airways within airless lung.',model='third-model',interaction_ref='interactions/00000003-'+'c'*32+'/request.json')]
    row['definitions']=rows
    row['definition_reviews']=[{'definition_sha256':digest(dumps(d)),
        'reason':('The definition embeds cohort-specific 24% versus 0% frequencies.' if i==0 else
                  'The later proposal confuses morphology with a cohort comparison.' if i==1 else REASON),
        'reviewer':'Scientific reviewer '+str(i+1),'reviewed_at':'2026-11-03T00:00:00+00:00'} for i,d in enumerate(rows)]
    row['enrichment']=[{'status':'clarification','reason':REASON,'updated_at':'2026-11-03T00:00:00+00:00',
        'input_sha256':'e'*64,'interaction_id':None,'retry_after':None}]
    row['evidence']=[{**row['evidence'][0], 'passage': 'Two malignant cohorts had natural air bronchograms at different frequencies.',
                     'qualification':'Occurrence evidence does not verify the modified meaning.'}]
    return row


class DefinitionHistoryTests(unittest.TestCase):
    def views(self, row):
        before=deepcopy(row)
        html=glossary_view.html([row]);md=glossary_view.markdown([row])
        self.assertEqual(row,before)
        return html,md

    def test_g30_original_and_each_distinct_version_visible_by_default(self):
        row=clarification_fixture();glossary.validate_record(row)
        html,md=self.views(row)
        self.assertIn('<details class="definition-history" open>',html)
        for d in row['definitions']:
            self.assertIn('<p class="historical-text prose">'+escape(d['text'])+'</p>',html)
            self.assertIn(d['text'],md)
        self.assertEqual(html.count('class="excluded-definition"'),3)
        self.assertEqual(md.count('Status: Excluded from accepted terminology.'),3)
        self.assertNotIn('class="preferred-definition',html)
        self.assertNotIn('Preferred definition:',md)

    def test_scientific_issue_is_shown_once_with_review_remainder(self):
        html,md=self.views(clarification_fixture())
        for text in (html,md):
            self.assertEqual(text.count(ISSUE),1)
            self.assertEqual(text.count('A general air bronchogram does not establish this exact modified meaning.'),1)
        self.assertIn('href="#g1-issue">See current scientific issue.</a>',html)
        self.assertIn('Reason: See scientific issue above.',md)
        self.assertEqual(html.count('class="scientific-issue'),1)
        self.assertIn('Enrichment: clarification',html)

    def test_versions_retain_distinct_attributions_and_exact_exclusions(self):
        row=clarification_fixture();html,md=self.views(row)
        sections=re.findall(r'<section class="excluded-definition">(.*?)</section>',html,re.S)
        for section,d,review in zip(sections,row['definitions'],row['definition_reviews']):
            self.assertIn(d['model'],section);self.assertIn(d['interaction_ref'],section)
            self.assertIn(review['reviewer'],section);self.assertIn(review['definition_sha256'],section)
            self.assertIn(d['request_sha256'],section)
            for value in (d['model'],d['interaction_ref'],review['reviewer'],review['definition_sha256']):
                self.assertIn(value,md)

    def test_excluded_history_does_not_increase_accepted_coverage_or_r1_preference(self):
        row=clarification_fixture()
        self.assertEqual(definitions.preferred(row),[])
        counts=coverage([row]);self.assertEqual(counts['defined'],0)
        self.assertEqual(counts['provisional_only'],0);self.assertEqual(counts['requiring_clarification'],1)
        self.assertEqual(counts['without_usable_definitions'],1)
        html,md=self.views(row)
        self.assertIn('Without usable definitions: 1',md)
        self.assertIn('<dt>Without usable definitions</dt><dd>1</dd>',html)

    def test_accepted_preferred_comes_before_status_and_collapses_history(self):
        row=clarification_fixture();source=record(1,row['term'])
        row['definitions'].append(source['definitions'][0]);row['evidence']+=source['evidence']
        row['status']='source_defined'
        html,md=self.views(row)
        self.assertIn('<details class="definition-history">',html)
        self.assertNotIn('<details class="definition-history" open>',html)
        self.assertNotIn('class="scientific-issue',html)
        self.assertIn(ORIGINAL,html);self.assertIn(ORIGINAL,md)
        self.assertLess(html.index('class="preferred-definition'),html.index('class="verification'))
        self.assertLess(md.index('Preferred definition:'),md.index('Scientific verification:'))
        self.assertEqual(coverage([row])['research_source'],1)
        self.assertEqual(coverage([row])['provisional_only'],0)

    def test_undefined_without_history_has_one_actionable_reason(self):
        row=record(1,'Unknown term');row.update(definitions=[],status='candidate')
        html,md=self.views(row)
        self.assertNotIn('class="definition-history',html)
        self.assertEqual(html.count('No applicable definition yet; run glossary-enrich'),1)
        self.assertEqual(md.count('No applicable definition yet; run glossary-enrich'),1)
        self.assertIn('No accepted definition in the current scope.',html)
        self.assertIn('No accepted definition in the current scope.',md)

    def test_preferred_text_not_duplicated_in_attribution_and_alternatives_complete(self):
        row=record(1,'Alpha')
        other=deepcopy(row['definitions'][0]);other.update(text='Another meaning of Alpha.',qualification='Different scientific scope.')
        other['evidence']={**other['evidence'],'passage':other['text']}
        row['evidence'].append(other['evidence']);row['definitions'].append(other);row['status']='multiple_definitions'
        html,md=self.views(row)
        self.assertIn('Alternative definitions',html);self.assertIn('Alternative definitions',md)
        for d in row['definitions']:
            # Once in the definition and once in the verbatim supporting passage.
            self.assertEqual(html.count(escape(d['text'])),2)
            self.assertEqual(md.count(d['text']),2)
        self.assertIn(other['qualification'],html);self.assertIn(other['qualification'],md)

    def test_excluded_authority_description_keeps_source_identity_and_link(self):
        row=clarification_fixture();d={'text':'A previously supplied authority description.', 'qualification':'Wrong scientific meaning.',
            'scope':'MeSH concept','type':'scope_note','authority':{'provider':'mesh','concept_id':'M123','preferred_name':'Example',
                'url':'https://id.nlm.nih.gov/mesh/M123','retrieved_at':'2026-11-03T00:00:00+00:00'}}
        row['definitions']=[d];row['definition_reviews']=[{**row['definition_reviews'][0],'definition_sha256':digest(dumps(d))}]
        html,md=self.views(row)
        self.assertIn(d['text'],html);self.assertIn(d['text'],md)
        self.assertIn('NLM MeSH',html);self.assertIn('NLM MeSH',md)
        self.assertIn('href="https://id.nlm.nih.gov/mesh/M123"',html)
        self.assertIn('[Source](https://id.nlm.nih.gov/mesh/M123)',md)
        self.assertEqual(coverage([row])['authoritative'],0)

    def test_history_text_review_and_attribution_cannot_inject_html_or_scripts(self):
        row=clarification_fixture();d=row['definitions'][0]
        d['text']='</script><img src=x onerror=alert(1)>'
        d['model']='</summary><svg onload=alert(2)>'
        row['definition_reviews'][0].update(definition_sha256=digest(dumps(d)),reason='<script>alert(3)</script>',reviewer='<iframe src=x>')
        html,md=self.views(row);parsed=Document(html)
        self.assertFalse(any(tag in {'img','svg','iframe'} for tag,_ in parsed.elements))
        self.assertIn(d['text'],''.join(parsed.text))
        self.assertNotIn('<script>alert(3)</script>',html);self.assertNotIn('<iframe src=x>',md)
        self.assertEqual(sum(tag=='script' for tag,_ in parsed.elements),2)
        self.assertFalse(any(k.startswith('on') for _,attrs in parsed.elements for k in attrs))

    def test_native_history_disclosure_requires_no_javascript_and_has_semantic_labels(self):
        html,_=self.views(clarification_fixture());parsed=Document(html)
        self.assertTrue(any(tag=='details' and attrs.get('class')=='definition-history' and 'open' in attrs for tag,attrs in parsed.elements))
        self.assertTrue(any(tag=='summary' for tag,_ in parsed.elements))
        self.assertIn('Previously proposed definition',html)
        self.assertIn('<strong>Status:</strong> Excluded from accepted terminology.',html)
        self.assertIn('<strong>Reason:</strong>',html)
        self.assertIn('Model:',html)

    def test_nonexcluded_definition_in_another_scope_is_not_mislabeled_excluded(self):
        row=clarification_fixture();row.pop('definition_reviews');row.pop('enrichment');row['status']='provisional'
        scope=definitions.context('How does botany regulate orchid petal coloration?','q9')
        view=glossary_view.presentation(row,scope)
        self.assertIsNone(view['preferred']);self.assertFalse(view['history'])
        self.assertEqual(len(view['alternatives']),3)
        self.assertFalse(any(r['applicable'] for r in view['alternatives']))
        html=glossary_view.html([row],scope)
        self.assertNotIn('Excluded from accepted terminology',html)
        self.assertIn('Other recorded scope; not preferred here.',html)

    def test_shared_presentation_is_deterministic_and_original_record_unchanged(self):
        row=clarification_fixture();before=dumps(row)
        view=glossary_view.presentation(row)
        self.assertEqual(view,glossary_view.presentation(row))
        self.assertEqual(view['history'][0]['definition']['text'],ORIGINAL)
        self.assertEqual(self.views(row),self.views(row));self.assertEqual(before,dumps(row))
