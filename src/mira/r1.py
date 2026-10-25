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
    require(result, "R1 query contains only prohibited control terms")
    validate_terms(result, control_terms)
    return result


def validate_terms(components, control_terms):
    """Literal whole-term/phrase restrictions, never negative provider operators."""
    query = normalized(" ".join(components)).casefold()
    for term in control_terms:
        pattern = r"(?<!\w)" + re.escape(normalized(term).casefold()) + r"(?!\w)"
        require(not re.search(pattern, query), "R1 query contains a supplied control term")


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
                    gaps.append({"question": proposition, "state": fields["State"]})
                continue
            limitation, flag = clean_text(fields["Explanation"])
            attribution, provenance_flag = clean_text(fields["Provenance"], 180)
            omitted |= flag or provenance_flag
            findings.append({"terminology": label, "proposition": proposition,
                             "kind": fields["Kind"], "evidence_status": fields["Evidence status"],
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


def context(state, memories, files, node_id, control_terms=()):
    node = state["nodes"][node_id]
    question = node["question"]
    additional = question_context(state, node_id)
    previous = []
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
    return {"question": question, "question_context": additional,
            "previous_search_terms": unique(previous), "control_terms": controls(control_terms),
            "memory_context": memory_context(memories, set(node["memory_ids"]), [question, *additional])}
