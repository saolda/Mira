"""Deterministic, escaped glossary views from complete canonical term records."""
from base64 import b64encode
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import os
import uuid

from .store import durable_write, sync_dir
from . import glossary_definitions as definitions


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


def source_label(evidence, metadata):
    source = metadata.get('source_references', {}).get((evidence['evidence_ref'], evidence['source_id']), {})
    return source.get('title', ''), source.get('url', '')


def markdown(records, current_scope=None, metadata=None):
    # Preserve the established Markdown layout and ordering. Every untrusted
    # field is prose, including legacy source/evidence/node reference strings.
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
        lines += ['## ' + prose(record['term']) + ' (' + record['id'] + ')', '', 'Status: ' + record['status'], '']
        if record['aliases']: lines += ['Aliases: ' + ', '.join(map(prose, record['aliases'])), '']
        if record.get('terminology') or not record['definitions']:
            lines += [prose(lookup_status(record)), '']
        preferred = definitions.preferred(record, metadata.get('scopes', {}).get(record['id'], current_scope))
        ordered=list(preferred)
        ordered += [d for d in definitions.preferred(record) if d not in ordered]
        lines += ['Preferred definition: ' + prose(preferred[0]['text']) if preferred else prose(unresolved_reason(record)), '']
        if any(definitions.provisional(d) for d in ordered):
            lines += ['Supporting passages document term occurrence; they do not verify model-generated definitions.', '']
        if record.get('enrichment'):
            last = record['enrichment'][-1]
            lines += ['Enrichment: ' + prose(last['status']) + ' · ' + prose(last['updated_at']) + ' · ' + prose(last['reason']), '']
        for review in record.get('definition_reviews', []):
            lines += ['Excluded earlier definition: ' + prose(review['reason']) + ' · reviewed by ' + prose(review['reviewer']), '']
        for definition in ordered:
            if definitions.provisional(definition):
                lines += ['- Definition: ' + prose(definition['text']),
                    '  Source: LLM-generated.', '  Verification: Provisional, not independently verified.',
                    '  Scientific scope: ' + prose(definition['scope']),
                    '  Ambiguity: ' + prose(definition['ambiguity'] or 'None recorded.'),
                    '  Model: ' + prose(definition['model']),
                    '  Generation timestamp: ' + prose(definition.get('generated_at', 'See interaction timestamp.')),
                    '  Model identity: ' + prose(json.dumps(definition.get('model_identity', {'served_model': definition['model']}), ensure_ascii=False, sort_keys=True)),
                    '  Generating interaction: ' + prose(definition['interaction_ref']),
                    '  Generating event: ' + prose(definition['event_ref']),
                    '  Prompt template SHA256: ' + prose(definition['template_sha256'])]
                continue
            lines += ['- ' + prose(definition['text']) + ' — ' + prose(definition['qualification'])]
            if 'authority' not in definition:
                lines += ['  Source: Source-supported research passage · ' + prose(definition['evidence']['source_id']) +
                    ' · ' + prose(definition['evidence']['evidence_ref'])]
            if 'authority' in definition:
                a = definition['authority']; url = citation_url(a['url'])
                lines += ['  ' + prose(authority_label(definition)) +
                    (' · [Source](' + url + ')' if url else '') + ' · retrieved: ' + prose(a['retrieved_at']),
                    '  Scope: ' + prose(definition['scope'])]
        for evidence in record['evidence']:
            lines += ['', '> ' + prose(evidence['passage']).replace('\n', '\n> '), '',
                'Source: ' + prose(evidence['source_id']) + '; evidence: ' + prose(evidence['evidence_ref']) + '; node: ' + prose(evidence['node_id'])]
            title, url = source_label(evidence, metadata)
            if title: lines += ['Source title: ' + prose(title)]
            if url: lines += ['Source reference: ' + prose(url)]
            if evidence['qualification']: lines += ['', 'Qualification: ' + prose(evidence['qualification'])]
        for link in record['relationships']: lines += ['', link['type'] + ': ' + link['target']]
        lines += ['']
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
        identity = record['id']  # IDs and relationship targets were canonically validated.
        def support_link(evidence):
            index = record['evidence'].index(evidence) + 1
            return '<a href="#' + identity + '-e' + str(index) + '">Evidence ' + str(index) + '</a>'
        parts += ['<article class="entry" id="' + identity + '" tabindex="-1" aria-labelledby="heading-' + identity + '">',
            '<h2 id="heading-' + identity + '"><a href="#' + identity + '">' + escape(record['term']) +
            '</a><small>' + identity + '</small></h2>',
            '<p class="status">Status: ' + escape(record['status']) + '</p>']
        if record['aliases']:
            parts += ['<p class="aliases prose"><strong>Aliases:</strong> ' + escape(', '.join(record['aliases'])) + '</p>']
        if record.get('terminology') or not record['definitions']:
            parts += ['<p class="qualification prose">' + escape(lookup_status(record)) + '</p>']
        parts += ['<h3>Definitions</h3>']
        preferred=definitions.preferred(record, metadata.get('scopes', {}).get(record['id'], current_scope))
        parts += ['<p class="preferred-definition prose"><strong>Preferred definition:</strong> ' +
            escape(preferred[0]['text'] if preferred else unresolved_reason(record)) + '</p>']
        if record.get('enrichment'):
            last=record['enrichment'][-1]
            parts += ['<p class="reference prose">Enrichment: ' + escape(last['status']) + ' · ' + escape(last['updated_at']) +
                '<br>' + escape(last['reason']) + '</p>']
        for review in record.get('definition_reviews', []):
            parts += ['<p class="qualification prose"><strong>Excluded earlier definition:</strong> ' +
                escape(review['reason']) + '<br>Reviewed by ' + escape(review['reviewer']) + '</p>']
        if any(definitions.provisional(d) for d in record['definitions']):
            parts += ['<p class="qualification prose">Supporting passages document term occurrence; they do not verify model-generated definitions.</p>']
        if record['definitions']:
            parts += ['<ol class="definitions">']
            ordered=list(preferred)
            ordered += [d for d in definitions.preferred(record) if d not in ordered]
            for definition in ordered:
                if definitions.provisional(definition):
                    parts += ['<li class="definition-provisional"><p class="prose"><strong>Definition:</strong> ' + escape(definition['text']) + '</p>',
                        '<p class="reference prose"><strong>Source:</strong> LLM-generated.<br>'
                        '<strong>Verification:</strong> Provisional, not independently verified.<br>'
                        '<strong>Scientific scope:</strong> ' + escape(definition['scope']) + '<br>'
                        '<strong>Ambiguity:</strong> ' + escape(definition['ambiguity'] or 'None recorded.') + '<br>'
                        '<strong>Model:</strong> ' + escape(definition['model']) + '<br>'
                        '<strong>Generated:</strong> ' + escape(definition.get('generated_at', 'See interaction timestamp.')) + '<br>'
                        '<strong>Model identity:</strong> ' + escape(json.dumps(definition.get('model_identity', {'served_model': definition['model']}), ensure_ascii=False, sort_keys=True)) + '<br>'
                        '<strong>Generating interaction:</strong> ' + escape(definition['interaction_ref']) + '<br>'
                        '<strong>Generating event:</strong> ' + escape(definition['event_ref']) + '<br>'
                        '<strong>Prompt template SHA256:</strong> ' + escape(definition['template_sha256']) + '</p></li>']
                    continue
                parts += ['<li><p class="prose">' + escape(definition['text']) + '</p>']
                if definition['qualification']:
                    parts += ['<p class="qualification prose"><strong>Qualification:</strong> ' + escape(definition['qualification']) + '</p>']
                if 'authority' in definition:
                    a = definition['authority']; url = citation_url(a['url'])
                    parts += ['<p class="reference prose">' + escape(authority_label(definition)) +
                        (' · <a href="' + escape(url, quote=True) + '" rel="noreferrer">Source</a>' if url else '') +
                        '<br>Retrieved: ' + escape(a['retrieved_at']) + '<br>Scope: ' + escape(definition['scope']) + '</p></li>']
                else:
                    label='Source-supported research passage · ' + escape(definition['evidence']['source_id']) + ' · '
                    parts += ['<p class="reference">' + label + support_link(definition['evidence']) + '</p></li>']
            parts += ['</ol>']
        else: parts += ['<p>' + escape(unresolved_reason(record)) + '</p>']
        parts += ['<h3>Supporting evidence</h3>']
        for index, evidence in enumerate(record['evidence'], 1):
            parts += ['<section class="evidence" id="' + identity + '-e' + str(index) + '">',
                '<blockquote class="prose">' + escape(evidence['passage']) + '</blockquote>',
                '<p class="reference prose"><strong>Source:</strong> ' + escape(evidence['source_id']) +
                '<br><strong>Evidence:</strong> <code>' + escape(evidence['evidence_ref']) + '</code>' +
                '<br><strong>Node:</strong> ' + escape(evidence['node_id']) + '</p>']
            title, url = source_label(evidence, metadata)
            if title: parts += ['<p class="reference prose"><strong>Source title:</strong> ' + escape(title) + '</p>']
            if url: parts += ['<p class="reference prose"><strong>Source reference:</strong> ' + escape(url) + '</p>']
            if evidence['qualification']:
                parts += ['<p class="qualification prose"><strong>Qualification:</strong> ' + escape(evidence['qualification']) + '</p>']
            parts += ['</section>']
        if record['relationships']:
            parts += ['<h3>Relationships</h3>', '<ul class="relationships">']
            for link in record['relationships']:
                target = by_id[link['target']]
                parts += ['<li>' + escape(link['type']) + ': <a href="#' + target['id'] + '">' +
                    escape(target['term']) + ' (' + target['id'] + ')</a> · ' + support_link(link['evidence']) + '</li>']
            parts += ['</ul>']
        parts += ['</article>']
    # Embed only names and aliases in the search index. Escape raw-text script
    # delimiters independently of HTML escaping; scientific text never becomes JS.
    data = json.dumps([{'id': r['id'], 'term': r['term'], 'aliases': r['aliases']} for r in records],
                      ensure_ascii=False, separators=(',', ':'))
    for character in '<>&\u2028\u2029':
        data = data.replace(character, '\\u' + format(ord(character), '04x'))
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
