"""Deterministic, task-specific R1 inputs. Memory excerpts remain untrusted data."""
import re

from . import research_tree as tree
from .format import MD, dumps, loads, require


CONTROL_TERMS = ["summary", "explanation", "findings", "proposition", "provenance",
                 "evidence", "sources", "references", "metadata", "title"]


def normalized(text):
    return " ".join(text.split())


def unique(values):
    result, seen = [], set()
    for value in values:
        key = normalized(value)
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result


def controls(values):
    require(isinstance(values, (list, tuple)) and all(isinstance(v, str) and v.strip()
            and "\n" not in v and "\r" not in v for v in values), "control terms must be a list of nonempty single-line strings")
    return unique([*CONTROL_TERMS, *values])


def filter_terms(components, control_terms):
    result = []
    for component in components:
        for term in control_terms:
            component = re.sub(r"(?<!\w)" + re.escape(normalized(term)) + r"(?!\w)", " ", component, flags=re.I)
        component = re.sub(r"\(\s*\)|\[\s*\]|\{\s*\}", "", component)
        component = normalized(component).strip(" ,;:-")
        if re.search(r"\w", component): result.append(component)
    validate_terms(result, control_terms)
    return deduplicate(result)


def validate_terms(components, control_terms):
    """Literal whole-term/phrase restrictions, never negative provider operators."""
    query = normalized(" ".join(components)).casefold()
    for term in control_terms:
        pattern = r"(?<!\w)" + re.escape(normalized(term).casefold()) + r"(?!\w)"
        require(not re.search(pattern, query), "R1 query contains a supplied control term")


# Recognisable query grammar only; scientific relevance and phrase meaning are
# model responsibilities. Lowercase conjunctions in established phrases are prose.
BOOLEAN = re.compile(r"\b(?:AND|OR|NOT|XOR|NEAR|WITHIN)\b|(?i:\b(?:NEAR|WITHIN|ADJ)\s*/\s*\d+\b|\bADJ\d+\b)")
QUERY_SYNTAX = re.compile(r'[\[\]{}:"*?|&\\=<>~`;]|(?:^|\s)[+-](?=\S)|[\x00-\x1f\x7f]')
PROVIDERS = re.compile(r"\b(?:arxiv|pubmed|crossref|europe[ _-]*pmc|eric|openalex|wikipedia)\b", re.I)


def validate_concepts(components, limit=6):
    """Validate the R1 proposal without revalidating legacy persisted keywords."""
    require(isinstance(components, list) and len(components) <= limit,
            "R1 concept limit exceeded or invalid list")
    for concept in components:
        require(isinstance(concept, str) and concept.strip(), "R1 concepts must be nonempty strings")
        require(len(concept.split()) <= 5, "R1 concepts must contain at most five words")
        require(not BOOLEAN.search(concept), "R1 concepts must not contain Boolean operators")
        require(not QUERY_SYNTAX.search(concept), "R1 concepts must not contain field tags or query syntax")
        require(not PROVIDERS.search(concept), "R1 concepts must not contain provider names")


# Deliberately conservative textual filtering, not a semantic security classifier.
INSTRUCTIONS = re.compile(
    r"\b(ignore|disregard|override)\b.{0,60}\b(instructions?|prompts?|previous|above|rules?)\b|"
    r"\b(system|developer|assistant)\s*(message|prompt|role|:)|"
    r"\b(return|output|respond|print|emit)\b.{0,40}\b(json|keywords|instead|only)\b|"
    r"\b(you must|you are|follow these|execute|run this|do not follow)\b|"
    r"\{\{|\}\}|<\|", re.I)
PATHS = re.compile(r"https?://\S+|(?:[A-Za-z]:[\\/]|(?<!\w)/|\.{1,2}/)\S+|\b[rs][1-9a-z][0-9a-z]*#[fqe][1-9a-z][0-9a-z]*\b")
STOP = set("what which when where why how does do is are can could would should the a an of to in for and or with under about this that these those from remain remains question evidence finding findings".split())


def clean_text(value, limit=360):
    """Extract prose only; drop instruction-like passages before clipping.

    Returns (text, omitted). Suspicious complete sentences/paragraphs are omitted,
    not converted to factual claims. Code, raw HTML and destinations are excluded.
    """
    parts, omitted = [], False
    for token in MD.parse(value):
        if token.type in {"fence", "code_block", "html_block"}:
            omitted = True
        if token.type != "inline":
            continue
        plain = "".join(" " if child.type in {"softbreak", "hardbreak"} else child.content
                        for child in token.children or []
                        if child.type in {"text", "code_inline", "softbreak", "hardbreak"})
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", plain):
            if INSTRUCTIONS.search(sentence) or re.search(r"</?[A-Za-z][^>]*>", sentence):
                omitted = True
                continue
            cleaned = normalized(PATHS.sub("", sentence))
            if cleaned != normalized(sentence): omitted = True
            if cleaned: parts.append(cleaned)
    result = normalized(" ".join(parts))
    clipped = len(result) > limit
    return result[:limit], omitted or clipped


def tokens(text):
    return {t for t in re.findall(r"\w+", text.casefold()) if len(t) > 2 and t not in STOP}


def memory_context(memories, linked_ids, questions):
    relevant = tokens(" ".join(questions))
    findings, gaps, omitted = [], [], False
    for memory in memories:
        if memory.id not in linked_ids:
            continue
        for unit in memory.units:
            if unit.kind in {"equation", "image"}:
                continue
            fields = unit.fields
            text = fields.get("Proposition", fields.get("Question", ""))
            label, label_omitted = clean_text(unit.label, 120)
            proposition, text_omitted = clean_text(text)
            omitted |= label_omitted or text_omitted
            # Linked ownership alone is not sufficient to include unrelated units.
            if not proposition or not (tokens(label + " " + proposition) & relevant):
                continue
            if unit.kind == "question":
                if fields["State"] in {"open", "partially_answered"}:
                    gaps.append({"question": proposition, "state": fields["State"],
                                 **{k.lower(): fields[k] for k in ("Origin", "Qualification") if k in fields},
                                 **({"source": memory.metadata["source"]} if "source" in memory.metadata else {})})
                continue
            limitation, flag = clean_text(fields.get("Qualification", fields.get("Explanation", "")))
            attribution, provenance_flag = clean_text(fields.get("Provenance", memory.metadata.get("source", {}).get("url", "")), 180)
            omitted |= flag or provenance_flag
            findings.append({"terminology": label, "proposition": proposition,
                             "kind": fields["Kind"], "evidence_status": fields.get("Evidence status", "unverified"),
                             "reasoning_and_limits": limitation, "attribution": attribution,
                             "excerpt_incomplete": label_omitted or text_omitted or flag or provenance_flag})
    # Bound the serialized data, including labels and Unicode, without an LLM.
    result = {"untrusted_memory_data": True, "findings": [], "unresolved_questions": [],
              "context_omitted_or_truncated": omitted}
    for key, rows in (("findings", findings), ("unresolved_questions", gaps)):
        for row in rows:
            result[key].append(row)
            if len(dumps(result).encode("utf-8")) > 3200:
                result[key].pop()
                result["context_omitted_or_truncated"] = True
    return result


def question_context(state, node_id):
    question = state["nodes"][node_id]["question"]
    additional = unique([state["nodes"][state["root_id"]]["question"],
                         *[state["nodes"][i]["question"] for i in tree.ancestors(state, node_id)]])
    additional = [q for q in additional if normalized(q) != normalized(question)]
    return additional


def retrieval_context(state, memories, files, node_id, control_terms=()):
    node = state["nodes"][node_id]
    question = node["question"]
    additional = question_context(state, node_id)
    previous = list(node.get("previous_search_terms", []))
    events = []
    for path, raw in files.items():
        if path.startswith("events/"):
            event = loads(raw)
            if (event.get("node_id") == node_id and event.get("action_committed") == "R1"
                    and event.get("status") == "committed"
                    and normalized(event.get("question", "")) == normalized(question)):
                events.append((event.get("timestamp", ""), path, event))
    for _, _, event in sorted(events):
        # The committed after-state records exact components. Never guess them by
        # splitting a provider's joined query or treating failed queries as bans.
        previous.extend(event.get("tree", {}).get(node_id, {}).get("keywords") or [])
    from .questions import context as brief
    return {"question": question, "question_context": additional, **brief(state, "R1", node_id),
            "previous_search_terms": unique(previous), "control_terms": controls(control_terms),
            "memory_context": memory_context(memories, set(node["memory_ids"]), [question, *additional]),
            "glossary_context": {"entries": [], "untrusted_glossary_data": True},
            "search_outcomes": recent_outcomes(files, node_id)}


def recent_outcomes(files, node_id):
    """Project committed retrieval metadata, independently of glossary budgets.

    LiveStore's read/recovery gate supplies committed canonical files, not pending
    journal payloads or diagnostic search attempts. Keep the actual query intact:
    prose sanitisation would remove or alter provider syntax. The enclosing prompt
    treats these records as data and checks the full rendered request's budget.
    """
    rows = [loads(raw) for path, raw in files.items() if path.startswith("research/results/")]
    rows = sorted((row for row in rows if row.get("node_id") == node_id),
                  key=lambda row: (row.get("timestamp", ""), row.get("reference", "")))[-12:]
    return [{"provider": row.get("provider"), "profile_id": row.get("profile_id"),
             "query": row.get("query", ""),
             # Absent legacy submission metadata is unknown, not a failed search.
             "query_submitted": row.get("query_submitted"), "status": row.get("status"),
             "returned_record_count": row.get("returned_record_count",
                 len(row.get("results", [])) + len(row.get("duplicates", []))),
             "unique_record_count": row.get("unique_record_count", len(row.get("results", [])))}
            for row in rows]


def concept_key(value):
    import unicodedata
    return normalized(unicodedata.normalize('NFKC', value)).casefold()


def deduplicate(values):
    result, seen = [], set()
    for value in values:
        key = concept_key(value)
        if key not in seen:
            seen.add(key); result.append(value)
    return result


def term_limit(state):
    from .retrieval import strategy
    selected = strategy(state)
    if 'query_profiles' in selected:
        return max(p['max_terms'] for p in selected['query_profiles'].values())
    return state.get('legacy_query_policy', {}).get('profile', {}).get('max_terms', 6)


def completed(files, node_id):
    rows = []
    for path, raw in files.items():
        if not path.startswith('research/results/'): continue
        row = loads(raw)
        if (row.get('node_id') == node_id and row.get('status') in {'ok', 'empty'}
                and row.get('query_submitted') is not False):
            rows.append({**row, 'reference': path})
    return sorted(rows, key=lambda r: (r.get('timestamp', ''), r['reference']))


def repeated(entry, history):
    # Compare actual provider semantics, independent of profile labels or versions.
    # Keep syntax/punctuation: different field tags and phrase boundaries matter.
    def parameters(value):
        return {k: concept_key(v) if isinstance(v, str) else v for k, v in value.items()}
    return next((r for r in history if r.get('provider') == entry['provider']
        and concept_key(r.get('query', '')) == concept_key(entry['query'])
        and parameters(r.get('request_parameters', entry['request_parameters'])) == parameters(entry['request_parameters'])), None)


def bounded_projection(rows, *, limit, budget):
    selected = []
    for row in rows:
        if len(selected) == limit: break
        if len(dumps([*selected, row]).encode('utf-8')) <= budget:
            selected.append(row)
    return {'entries': selected, 'omitted_count': len(rows) - len(selected)}


def context(state, memories, files, node_id, control_terms=(), glossary_context=None):
    old = retrieval_context(state, memories, files, node_id, control_terms)
    node = state['nodes'][node_id]
    relevant = tokens(' '.join([old['question'], *old['question_context'], dumps(old['memory_context'])]))
    def rank(row):
        return (-len(relevant & tokens(row['term'])), row.get('last_considered_round', 0), row['order'])
    candidates = sorted((r for r in node.get('concept_candidates', []) if not r['submitted_queries']), key=rank)
    unused = bounded_projection([{'term': clean_text(r['term'], 180)[0], 'order': r['order'],
        'status': 'unverified', 'selection_count': len(r['selected_rounds'])} for r in candidates], limit=10, budget=2200)
    prior = deduplicate(old['previous_search_terms'])
    prior = sorted(enumerate(prior), key=lambda pair: (-len(relevant & tokens(pair[1])),
        (pair[0] - node.get('search_round', 0) * 10) % max(1, len(prior))))
    previous = bounded_projection([{'term': clean_text(t, 180)[0]} for _, t in prior], limit=10, budget=1600)
    history = completed(files, node_id)
    # Relevance, then recency; independent of the glossary budget. A projection is
    # guidance only: duplicate checks always read the entire committed history.
    history = [r for _, r in sorted(enumerate(history), key=lambda pair:
        (-len(relevant & tokens(pair[1].get('query', ''))), -pair[0]))]
    queries = bounded_projection([{k: r.get(k) for k in ('provider', 'profile_id', 'query', 'status', 'reference')}
        for r in history], limit=12, budget=4000)
    return {'question': old['question'],
        'question_scope': {'ancestor_questions': old['question_context'], 'research_brief': old['research_brief']},
        'research_context': old['memory_context'],
        'term_context': {'unused_candidates': unused, 'prior_terms': previous,
            'glossary': glossary_context or old['glossary_context'],
            'selection_policy': 'relevance, least recently considered, discovery order; prior-term rotation',
            'untrusted_term_data': True},
        'completed_queries': queries, 'term_limit': term_limit(state), 'control_terms': old['control_terms']}


def components(value, control_terms):
    """Reject individual concepts without rewriting the model's selections."""
    accepted = {'reason': value['reason']}
    rejected = []
    for field in ('new_concepts', 'search_concepts'):
        accepted[field] = []
        seen = set()
        for index, term in enumerate(value[field]):
            try:
                validate_concepts([term])
                validate_terms([*accepted[field], term], control_terms)
                require(concept_key(term) not in seen, 'duplicate concept')
            except ValueError as exc:
                rejected.append({'field': field, 'index': index, 'text': term, 'error': str(exc)})
                continue
            seen.add(concept_key(term)); accepted[field].append(term)
    return accepted, rejected


def accept(node, value, context, event, history, plans, known_terms=(), *, invalid_selection=False):
    """Update candidates and plan in the same journal operation as the R1 event."""
    accepted = {key: list(value[key]) for key in ('new_concepts', 'search_concepts')}
    accepted['reason'] = value['reason']
    round_id = node.get('search_round', 0) + 1
    records = node.setdefault('concept_candidates', [])
    known = {concept_key(r['term']) for r in records}
    known.update(concept_key(t) for t in known_terms)
    known.update(concept_key(t) for t in node.get('previous_search_terms', []))
    for projection in ('prior_terms',):
        known.update(concept_key(r['term']) for r in context['term_context'][projection]['entries'])
    for row in context['term_context']['glossary'].get('entries', []):
        known.update(concept_key(t) for t in [row.get('term', row.get('canonical', '')), *row.get('aliases', [])])
    discoveries = []
    for original in value['new_concepts']:
        if concept_key(original) in known: continue
        term = original; known.add(concept_key(term)); discoveries.append(term)
        records.append({'term': term, 'original': original, 'normalized': concept_key(term),
            'node_id': node['id'], 'discovery_round': round_id, 'discovery_event': event['event_id'],
            'interaction_id': event['interaction_id'], 'order': len(records) + 1, 'status': 'unverified',
            'considered_rounds': [], 'selected_rounds': [], 'submitted_queries': [], 'last_considered_round': 0})
    accepted['new_concepts'] = discoveries
    considered = {r['order'] for r in context['term_context']['unused_candidates']['entries']}
    selected = {concept_key(t) for t in accepted['search_concepts']}
    for row in records:
        if row['order'] in considered:
            row['considered_rounds'].append(round_id); row['last_considered_round'] = round_id
        if row['normalized'] in selected: row['selected_rounds'].append(round_id)
    repeats = [dict(provider=p['provider'], query=p['query'], original_reference=match['reference'])
        for p in plans if (match := repeated(p, history))]
    blocked = not invalid_selection and (not accepted['search_concepts'] or len(repeats) == len(plans))
    node.update(keywords=accepted['search_concepts'] or None, search_round=round_id,
        next_database_index=0, round_outcomes=[], provider_outcomes={}, deferred_searches=[],
        legacy_completed_provider_indices=[], search_blocked=blocked,
        search_blocked_reason=('empty_selection' if not accepted['search_concepts'] else 'completed_queries_only') if blocked else None)
    event.update(search_plan=accepted, repeated_queries=repeats, search_blocked=blocked,
        search_blocked_reason=node['search_blocked_reason'], r1_projection=context)
    if invalid_selection:
        node['r1_validation_blocked'] = {'event_ref': 'events/' + event['event_id'] + '.json',
            'interaction_id': event['interaction_id'], 'reason': 'all_selected_concepts_invalid'}
    return accepted


def mark_submitted(node, plan, reference):
    used = {concept_key(t) for t in plan['retained_concepts']}
    for row in node.get('concept_candidates', []):
        if row['normalized'] in used:
            row['submitted_queries'].append({'provider': plan['provider'], 'query': plan['query'],
                'round': node['search_round'], 'evidence_ref': reference})


def validate_state(node):
    records = node.get('concept_candidates', [])
    require(isinstance(records, list), 'invalid R1 candidates')
    seen = set()
    for index, row in enumerate(records, 1):
        require(isinstance(row, dict) and row.get('order') == index and row.get('node_id') == node['id']
            and row.get('status') == 'unverified' and isinstance(row.get('term'), str)
            and row.get('normalized') == concept_key(row['term']) and row['normalized'] not in seen,
            'invalid R1 candidate identity')
        seen.add(row['normalized'])
        require(isinstance(row.get('original'), str) and isinstance(row.get('discovery_event'), str)
            and isinstance(row.get('interaction_id'), str) and type(row.get('discovery_round')) is int
            and 0 < row['discovery_round'] <= node.get('search_round', 0), 'invalid candidate provenance')
        require(all(isinstance(row.get(k), list) for k in ('considered_rounds', 'selected_rounds', 'submitted_queries')),
            'invalid candidate usage')
    require(type(node.get('search_blocked', False)) is bool, 'invalid search block')
    if node.get('r1_validation_blocked'):
        receipt = node['r1_validation_blocked']
        require(isinstance(receipt, dict) and set(receipt) == {'event_ref', 'interaction_id', 'reason'}
            and receipt['reason'] == 'all_selected_concepts_invalid' and not node.get('search_blocked')
            and node['keywords'] is None, 'invalid R1 validation block')
    if node.get('search_blocked'):
        require(node.get('search_blocked_reason') in {'empty_selection', 'completed_queries_only'}
            and not node['pending_results'] and not node.get('deferred_searches')
            and node['next_database_index'] == 0, 'invalid blocked handoff')
