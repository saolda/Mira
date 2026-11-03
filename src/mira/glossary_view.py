"""Deterministic, escaped glossary views from complete canonical term records."""
from base64 import b64encode
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import os
import uuid

from .store import durable_write, sync_dir
from .format import digest, dumps
from . import glossary_definitions as definitions
from .glossary_sources import source_url


ASSETS = Path(__file__).with_name('glossary_assets')
NLM_NOTICE = ('Courtesy of the U.S. National Library of Medicine. Retrieved terminology may not reflect '
              'the most current NLM data. NLM does not endorse Mira.')


def lookup_status(record):
    last = record.get('terminology', [])
    if not last: return 'Lookup not yet attempted.'
    row = last[-1]
    labels = {'matched': 'Authoritative match', 'not_found': 'No authoritative match',
        'ambiguous': 'Ambiguous match; no definition attached', 'unavailable': 'Lookup unavailable',
        'error': 'Lookup error', 'not_attempted': 'Lookup not yet attempted'}
    if row['status'] == 'matched' and not any(c['descriptions'] for c in row['concepts']):
        return 'Authoritative name match; no descriptive definition supplied: ' + row['reason']
    return labels[row['status']] + ': ' + row['reason']


def authority_label(definition):
    a = definition['authority']
    return ('NLM MeSH · ' + a['concept_id'] + ' · ' + definition['type'].replace('_', ' ') +
            ' · preferred name: ' + a['preferred_name'])


def citation_url(value):
    # Used only for validated terminology citations, never arbitrary source prose.
    import re
    return value if re.fullmatch(r'https://id\.nlm\.nih\.gov/mesh/M[0-9]+', value) else ''


def content_policy():
    def integrity(path):
        return b64encode(sha256(path.read_bytes()).digest()).decode('ascii')
    return ("default-src 'none'; script-src 'sha256-" + integrity(ASSETS / 'search.js') +
            "'; style-src 'sha256-" + integrity(ASSETS / 'style.css') + "'; base-uri 'none'; form-action 'none'")


def view_coverage(records, metadata):
    from .glossary_enrichment import coverage
    return metadata.get('coverage') or coverage(records)


def coverage_lines(records, metadata):
    c = view_coverage(records, metadata)
    return [('Total glossary terms', c['total']), ('Authoritative definitions', c['authoritative']),
            ('Research-source definitions', c['research_source']), ('Provisional definitions only', c['provisional_only']),
            ('Requiring clarification', c['requiring_clarification']), ('Without usable definitions', c['without_usable_definitions'])]


def unresolved_reason(record):
    progress = record.get('enrichment', [])
    return progress[-1]['reason'] if progress else 'No applicable definition yet; run glossary-enrich to complete this entry.'


def presentation(record, current_scope=None):
    """One scientific presentation shared by both exports; never edit the record.

    Exclusions affect acceptance, not visibility. The current issue is split
    from its full review reason so history can link back without repeating it.
    """
    accepted = definitions.preferred(record, current_scope)
    preferred = accepted[0] if accepted else None
    reviews = {}
    for review in record.get('definition_reviews', []):
        reviews.setdefault(review['definition_sha256'], []).append(review)
    last = (record.get('enrichment') or [{}])[-1]
    reason = unresolved_reason(record) if not preferred else ''
    # A first sentence is an extract, not a generated scientific reinterpretation.
    import re
    issue = re.split(r'(?<=[.!?])\s+(?=[A-Z])', reason, maxsplit=1)[0]
    history = []
    alternatives = []
    for definition in record['definitions']:
        matching = reviews.get(digest(dumps(definition)), [])
        if matching:
            history.append({'definition': definition, 'reviews': matching})
        elif definition != preferred:
            alternatives.append({'definition': definition, 'applicable': definition in accepted})
    verification = ('No accepted definition in the current scope.' if preferred is None else
        'Provisional, not independently verified.' if definitions.provisional(preferred) else
        'Authoritative terminology description.' if 'authority' in preferred else
        'Source-supported research definition.')
    return {'preferred': preferred, 'verification': verification, 'issue': issue,
            'reason': reason, 'history': history, 'alternatives': alternatives, 'progress': last}


def attribution(definition):
    """Plain data pairs only; each renderer escapes them at its own boundary."""
    if definitions.provisional(definition):
        return [('Source', 'LLM-generated.'), ('Verification', 'Provisional, not independently verified.'),
            ('Scientific scope', definition['scope']), ('Ambiguity', definition['ambiguity'] or 'None recorded.'),
            ('Model', definition['model']),
            ('Generation timestamp', definition.get('generated_at', 'See interaction timestamp.')),
            ('Model identity', json.dumps(definition.get('model_identity', {'served_model': definition['model']}), ensure_ascii=False, sort_keys=True)),
            ('Generating interaction', definition['interaction_ref']), ('Generating event', definition['event_ref']),
            ('Prompt template SHA256', definition['template_sha256']), ('Request SHA256', definition['request_sha256'])]
    if 'authority' in definition:
        a = definition['authority']
        return [('Source', authority_label(definition)), ('Retrieved', a['retrieved_at']),
                ('Scientific scope', definition['scope']), ('Qualification', definition['qualification'])]
    return [('Source', 'Source-supported research passage · ' + definition['evidence']['source_id'] +
             ' · ' + definition['evidence']['evidence_ref']), ('Qualification', definition['qualification'])]


def review_reason(review, view):
    """Return the unrepeated remainder and whether to reference the main issue."""
    reason = review['reason']
    references_issue = bool(view['issue'] and reason.startswith(view['issue']))
    return (reason[len(view['issue']):].lstrip() if references_issue else reason), references_issue


def source_label(evidence, metadata):
    source = metadata.get('source_references', {}).get((evidence['evidence_ref'], evidence['source_id']), {})
    return source.get('title', ''), source.get('url', '')


def markdown(records, current_scope=None, metadata=None):
    from .glossary import r3_prose as prose
    metadata = metadata or {}
    lines = ['# Research glossary', '', 'Scientific terminology with attributed definitions; provisional definitions are not independently verified.', '']
    lines += [f'{label}: {count}' for label, count in coverage_lines(records, metadata)]
    lines += ['', view_coverage(records, metadata)['category_note'], '']
    if metadata:
        lines += ['Generated: ' + prose(metadata['generated_at']) + '; glossary revision: ' + str(metadata['revision']),
                  'Glossary commitment: ' + metadata['commitment'], '']
    if any(r.get('terminology') for r in records): lines += [NLM_NOTICE, '']
    for record in records:
        view = presentation(record, metadata.get('scopes', {}).get(record['id'], current_scope))
        preferred = view['preferred']
        lines += ['## ' + prose(record['term']) + ' (' + record['id'] + ')', '']
        if preferred: lines += ['Preferred definition: ' + prose(preferred['text']), '']
        lines += ['Scientific verification: ' + prose(view['verification']), '', 'Status: ' + record['status'], '']
        if view['issue']: lines += ['Scientific issue: ' + prose(view['issue']), '']
        if record['aliases']: lines += ['Aliases: ' + ', '.join(map(prose, record['aliases'])), '']
        if view['alternatives']: lines += ['### Alternative definitions', '']
        for row in view['alternatives']:
            d = row['definition']
            lines += ['- Definition: ' + prose(d['text']), '  Applicability: ' + ('Current scope.' if row['applicable'] else 'Other recorded scope; not preferred here.')]
            lines += ['  ' + label + ': ' + prose(value) for label, value in attribution(d)]
        if view['history']: lines += ['### Previously proposed definitions', '']
        for index, row in enumerate(view['history'], 1):
            lines += ['Previously proposed definition ' + str(index) + ': ' + prose(row['definition']['text']),
                      '', 'Status: Excluded from accepted terminology.', '']
            for review in row['reviews']:
                reason, references_issue = review_reason(review, view)
                lines += ['Reason: ' + ('See scientific issue above. ' if references_issue else '') + prose(reason),
                    'Reviewed by: ' + prose(review['reviewer']) + ' · ' + prose(review['reviewed_at']),
                    'Definition SHA256: ' + prose(review['definition_sha256']), '']
            lines += [label + ': ' + prose(value) for label, value in attribution(row['definition'])]
            lines += ['']
        lines += ['### Attribution and supporting evidence', '']
        if preferred:
            lines += [label + ': ' + prose(value) for label, value in attribution(preferred)]
            if 'authority' in preferred and citation_url(preferred['authority']['url']):
                lines += ['[Source](' + citation_url(preferred['authority']['url']) + ')']
        for row in view['alternatives'] + view['history']:
            d = row['definition']
            if 'authority' in d and citation_url(d['authority']['url']):
                lines += ['[Source](' + citation_url(d['authority']['url']) + ')']
        if any(definitions.provisional(d) for d in record['definitions']):
            lines += ['', 'Supporting passages document term occurrence; they do not verify model-generated definitions.']
        for evidence in record['evidence']:
            lines += ['', '> ' + prose(evidence['passage']).replace('\n', '\n> '), '',
                'Source: ' + prose(evidence['source_id']) + '; evidence: ' + prose(evidence['evidence_ref']) + '; node: ' + prose(evidence['node_id'])]
            title, url = source_label(evidence, metadata)
            if title: lines += ['Source title: ' + prose(title)]
            if url: lines += ['Source reference: ' + prose(url)]
            if evidence['qualification']: lines += ['', 'Qualification: ' + prose(evidence['qualification'])]
        for link in record['relationships']: lines += ['', link['type'] + ': ' + link['target']]
        lines += ['', '### Technical provenance', '']
        if record.get('terminology') or not record['definitions']: lines += [prose(lookup_status(record)), '']
        if view['progress']:
            last = view['progress']
            lines += ['Enrichment: ' + prose(last['status']) + ' · ' + prose(last['updated_at']), '']
            # Clarification repeats a review reason in canonical progress. Keep
            # that record's status/time, with the scientific reason shown once.
            reviewed = any(r['reason'] == last['reason'] for r in record.get('definition_reviews', []))
            if not reviewed:
                rest = last['reason'][len(view['issue']):].lstrip() if view['issue'] else last['reason']
                if rest: lines += ['Enrichment details: ' + prose(rest), '']
    return '\n'.join(lines)


def html(records, current_scope=None, metadata=None):
    metadata = metadata or {}
    by_id = {r['id']: r for r in records}
    css = (ASSETS / 'style.css').read_text(encoding='utf-8')
    script = (ASSETS / 'search.js').read_text(encoding='utf-8')
    policy = content_policy()
    parts = ['<!doctype html>', '<html lang="en">', '<head>', '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="' + escape(policy, quote=True) + '">',
        '<title>Research glossary · Mira</title>', '<style>' + css + '</style>', '</head>', '<body>',
        '<header class="page-header"><h1>Research glossary</h1>',
        '<p>Scientific terminology with attributed definitions. Provisional definitions are not independently verified.</p>',
        '<dl class="coverage">' + ''.join('<div><dt>' + escape(label) + '</dt><dd>' + str(count) + '</dd></div>'
            for label, count in coverage_lines(records, metadata)) + '</dl>',
        '<p class="reference">' + escape(view_coverage(records, metadata)['category_note']) + '</p>',
        *(['<p class="reference">Generated: ' + escape(metadata['generated_at']) + ' · Glossary revision: ' + str(metadata['revision']) +
            '<br>Commitment: <code>' + escape(metadata['commitment']) + '</code></p>'] if metadata else []),
        '</header>',
        '<section class="search-panel" aria-label="Glossary term search"><div class="search-content">',
        '<label for="glossary-search">Search glossary terms</label>',
        '<input id="glossary-search" type="search" autocomplete="off" role="combobox" aria-autocomplete="list" '
        'aria-controls="glossary-results" aria-expanded="false" aria-describedby="glossary-search-help glossary-match-count">',
        '<div class="search-meta"><span id="glossary-match-count" role="status" aria-live="polite">' + str(len(records)) +
        ' glossary entries</span><span id="glossary-search-help">Names and aliases only. Use Ctrl+F for full text.</span></div>',
        '<ul id="glossary-results" role="listbox" aria-label="Matching glossary terms" hidden></ul>',
        '<p id="glossary-no-matches" role="status" hidden>No matching terms</p>',
        '<noscript><p>Enable JavaScript for term search, or use your browser’s Ctrl+F.</p></noscript>',
        '</div></section>', '<main aria-label="Glossary entries">']
    if not records: parts += ['<p>No glossary entries have been recorded.</p>']
    if any(r.get('terminology') for r in records): parts += ['<p>' + escape(NLM_NOTICE) + '</p>']
    for record in records:
        identity = record['id']
        view = presentation(record, metadata.get('scopes', {}).get(identity, current_scope))
        preferred = view['preferred']
        def support_link(evidence):
            index = record['evidence'].index(evidence) + 1
            return '<a href="#' + identity + '-e' + str(index) + '">Evidence ' + str(index) + '</a>'
        def attributed(d):
            result = ['<p class="reference prose">' + '<br>'.join('<strong>' + label + ':</strong> ' + escape(value)
                for label, value in attribution(d)) + '</p>']
            if 'authority' in d:
                url = citation_url(d['authority']['url'])
                if url: result += ['<a href="' + escape(url, quote=True) + '" rel="noreferrer">Source</a>']
            elif not definitions.provisional(d): result += [support_link(d['evidence'])]
            return result
        parts += ['<article class="entry" id="' + identity + '" tabindex="-1" aria-labelledby="heading-' + identity + '">',
            '<h2 id="heading-' + identity + '"><a href="#' + identity + '">' + escape(record['term']) +
            '</a><small>' + identity + '</small></h2>']
        if preferred:
            parts += ['<p class="preferred-definition prose"><strong>Preferred definition:</strong> ' + escape(preferred['text']) + '</p>']
        parts += ['<p class="verification prose"><strong>Scientific verification:</strong> ' + escape(view['verification']) + '</p>',
                  '<p class="status">Status: ' + escape(record['status']) + '</p>']
        if view['issue']:
            parts += ['<p class="scientific-issue prose" id="' + identity + '-issue"><strong>Scientific issue:</strong> ' + escape(view['issue']) + '</p>']
        if record['aliases']:
            parts += ['<p class="aliases prose"><strong>Aliases:</strong> ' + escape(', '.join(record['aliases'])) + '</p>']
        if view['alternatives']:
            parts += ['<h3>Alternative definitions</h3>', '<ol class="definitions">']
            for row in view['alternatives']:
                d = row['definition']
                parts += ['<li' + (' class="definition-provisional"' if definitions.provisional(d) else '') + '><p class="prose">' + escape(d['text']) + '</p>',
                    '<p class="qualification">' + ('Current scope.' if row['applicable'] else 'Other recorded scope; not preferred here.') + '</p>', *attributed(d), '</li>']
            parts += ['</ol>']
        if view['history']:
            # Native disclosure works without JavaScript. Undefined terms show
            # their original proposals by default, regardless of search support.
            parts += ['<details class="definition-history"' + ('' if preferred else ' open') + '>',
                      '<summary>Previously proposed definitions (' + str(len(view['history'])) + ')</summary>']
            for index, row in enumerate(view['history'], 1):
                d = row['definition']
                parts += ['<section class="excluded-definition"><h3>Previously proposed definition ' + str(index) + '</h3>',
                    '<p class="historical-text prose">' + escape(d['text']) + '</p>',
                    '<p class="excluded-status"><strong>Status:</strong> Excluded from accepted terminology.</p>']
                for review in row['reviews']:
                    reason, references_issue = review_reason(review, view)
                    parts += ['<p class="qualification prose"><strong>Reason:</strong> ' +
                        ('<a href="#' + identity + '-issue">See current scientific issue.</a> ' if references_issue else '') + escape(reason) + '</p>',
                        '<p class="reference prose"><strong>Reviewed by:</strong> ' + escape(review['reviewer']) + ' · ' + escape(review['reviewed_at']) +
                        '<br><strong>Definition SHA256:</strong> ' + escape(review['definition_sha256']) + '</p>']
                parts += [*attributed(d), '</section>']
            parts += ['</details>']
        parts += ['<h3>Attribution and supporting evidence</h3>']
        if preferred:
            parts += ['<div class="preferred-attribution' + (' definition-provisional' if definitions.provisional(preferred) else '') + '">', *attributed(preferred), '</div>']
        if any(definitions.provisional(d) for d in record['definitions']):
            parts += ['<p class="qualification prose">Supporting passages document term occurrence; they do not verify model-generated definitions.</p>']
        for index, evidence in enumerate(record['evidence'], 1):
            parts += ['<section class="evidence" id="' + identity + '-e' + str(index) + '">',
                '<blockquote class="prose">' + escape(evidence['passage']) + '</blockquote>',
                '<p class="reference prose"><strong>Source:</strong> ' + escape(evidence['source_id']) +
                '<br><strong>Evidence:</strong> <code>' + escape(evidence['evidence_ref']) + '</code>' +
                '<br><strong>Node:</strong> ' + escape(evidence['node_id']) + '</p>']
            title, url = source_label(evidence, metadata)
            if title: parts += ['<p class="reference prose"><strong>Source title:</strong> ' + escape(title) + '</p>']
            if url:
                safe = source_url(url)
                reference = ('<a href="' + escape(safe, quote=True) + '" rel="noreferrer noopener">' + escape(url) + '</a>') if safe else escape(url)
                parts += ['<p class="reference prose"><strong>Source reference:</strong> ' + reference + '</p>']
            if evidence['qualification']: parts += ['<p class="qualification prose"><strong>Qualification:</strong> ' + escape(evidence['qualification']) + '</p>']
            parts += ['</section>']
        if record['relationships']:
            parts += ['<h3>Relationships</h3>', '<ul class="relationships">']
            for link in record['relationships']:
                target = by_id[link['target']]
                parts += ['<li>' + escape(link['type']) + ': <a href="#' + target['id'] + '">' +
                    escape(target['term']) + ' (' + target['id'] + ')</a> · ' + support_link(link['evidence']) + '</li>']
            parts += ['</ul>']
        parts += ['<details class="technical-provenance"><summary>Technical provenance</summary>']
        if record.get('terminology') or not record['definitions']: parts += ['<p class="reference prose">' + escape(lookup_status(record)) + '</p>']
        if view['progress']:
            last = view['progress']
            parts += ['<p class="reference prose">Enrichment: ' + escape(last['status']) + ' · ' + escape(last['updated_at']) + '</p>']
            reviewed = any(r['reason'] == last['reason'] for r in record.get('definition_reviews', []))
            if not reviewed:
                rest = last['reason'][len(view['issue']):].lstrip() if view['issue'] else last['reason']
                if rest: parts += ['<p class="reference prose">' + escape(rest) + '</p>']
        parts += ['</details>', '</article>']
    data = json.dumps([{'id': r['id'], 'term': r['term'], 'aliases': r['aliases']} for r in records],
                      ensure_ascii=False, separators=(',', ':'))
    for character in '<>&\u2028\u2029': data = data.replace(character, '\\u' + format(ord(character), '04x'))
    parts += ['</main>', '<script id="glossary-search-data" type="application/json">' + data + '</script>',
              '<script>' + script + '</script>', '</body>', '</html>', '']
    if metadata:
        parts.insert(5, '<meta name="mira-glossary-commitment" content="' + escape(metadata['commitment'], quote=True) + '">')
        parts.insert(5, '<meta name="mira-glossary-generated-at" content="' + escape(metadata['generated_at'], quote=True) + '">')
    return '\n'.join(parts)


def publish(store, outputs):
    """Stage/fsync both derived views before atomic per-file publication.

    The caller holds the existing writer lock. No canonical or recovery record
    changes; failed rendering/staging cannot publish only half of a new export.
    """
    staged, backups, installed = [], {}, []
    try:
        for relative, content in outputs.items():
            destination = store.path(relative)
            backups[relative] = None
            if destination.exists():
                backup = store.path(relative + '.tmp-' + uuid.uuid4().hex)
                backups[relative] = backup
                durable_write(backup, destination.read_bytes().decode('utf-8'))
            temporary = store.path(relative + '.tmp-' + uuid.uuid4().hex)
            staged.append((temporary, relative))
            durable_write(temporary, content)
        sync_dir(store.path('research'))
        try:
            for temporary, relative in staged:
                os.replace(temporary, store.path(relative))  # Recheck destination symlinks.
                installed.append(relative)
            sync_dir(store.path('research'))
        except BaseException:
            # Preserve the previous pair on a publication error while the writer
            # lock still excludes cooperating readers. Exports are disposable.
            for relative in reversed(installed):
                destination = store.path(relative)
                if backups[relative] is None: destination.unlink(missing_ok=True)
                else: os.replace(backups[relative], destination)
            sync_dir(store.path('research'))
            raise
    finally:
        for temporary, _ in staged: temporary.unlink(missing_ok=True)
        for backup in backups.values():
            if backup is not None: backup.unlink(missing_ok=True)
