"""Immutable question documents and bounded, action-specific prompt projections."""
from pathlib import Path
import re

from .format import MD, digest, require

PATH = "research/question.md"
CONTEXT_BYTES = {"R0": 2048, "R1": 2048, "R3": 1536, "R4": 4096,
                 "R5": 4096, "S1": 3072, "S2": 4096}


def parse(markdown):
    """Keep question text and objective Markdown verbatim, excluding blank separators."""
    require(isinstance(markdown, str) and markdown.strip() and "\x00" not in markdown,
            "nonempty UTF-8 question Markdown required")
    tokens = MD.parse(markdown)
    headings = [(i, token) for i, token in enumerate(tokens) if token.type == "heading_open"]
    require(headings and headings[0][0] == 0, "question document must start with # Research question")
    names = []
    for i, token in headings:
        name = tokens[i + 1].content
        expected = "h1" if not names else "h2"
        require(token.level == 0 and token.tag == expected and name in
                ({"Research question"} if not names else {"Context", "Research objectives"}) and name not in names,
                "invalid or duplicate question document heading")
        names.append(name)
    lines = markdown.splitlines(keepends=True)
    sections = {}
    for position, (i, heading) in enumerate(headings):
        end_token, end_line = (headings[position + 1][0], headings[position + 1][1].map[0]) \
            if position + 1 < len(headings) else (len(tokens), len(lines))
        body = "".join(lines[heading.map[1]:end_line]).strip("\r\n")
        require(body.strip(), "empty question document section: " + names[position])
        sections[names[position]] = (body, tokens[i + 3:end_token])
    question, body_tokens = sections["Research question"]
    require(body_tokens and all(t.type in {"paragraph_open", "inline", "paragraph_close"} for t in body_tokens)
            and any(c.isalnum() for t in body_tokens if t.type == "inline" for c in t.content),
            "main research question must contain prose")
    objectives = []
    if "Research objectives" in sections:
        body, items = sections["Research objectives"]
        require(items and items[0].type in {"bullet_list_open", "ordered_list_open"} and
                all(t.level > 0 or t.type in {"bullet_list_open", "bullet_list_close",
                                            "ordered_list_open", "ordered_list_close"} for t in items),
                "research objectives must be a Markdown list")
        body_lines = body.splitlines(keepends=True)
        # Reparse the section so source line maps start at zero.
        for token in MD.parse(body):
            if token.type == "list_item_open" and token.level == 1:
                item = "".join(body_lines[token.map[0]:token.map[1]]).strip("\r\n")
                prose = re.sub(r"^\s*(?:[-+*]|\d+[.)])\s*", "", item)
                require(any(c.isalnum() for c in prose), "empty research objective")
                objectives.append(item)
        require(objectives, "at least one research objective required")
    return {"path": PATH, "sha256": digest(markdown), "question": question,
            "context": sections.get("Context", ("", []))[0], "objectives": objectives}


def read(path):
    markdown = Path(path).read_bytes().decode("utf-8")
    return markdown, parse(markdown)


def validate(state, files):
    require(isinstance(state, dict), "invalid research state")
    document = state.get("question_document")
    if document is None:
        require(PATH not in files, "question Markdown requires persisted parsed fields")
        return
    require(isinstance(document, dict) and PATH in files, "missing immutable question Markdown")
    require(document == parse(files[PATH]), "question document hash or parsed fields mismatch")
    require(document["question"] == state["nodes"][state["root_id"]]["question"],
            "root question differs from question document")


def context(state, action, node_id=None):
    """All objectives survive; only supplementary background may be excerpted.

    Complete main questions already occupy the existing question/ancestor slots.
    Legacy experiments and saved S2 selections need no document or migration.
    """
    document = state.get("question_document")
    if document is None: return {"research_brief": None}
    question = state["nodes"][node_id or state["root_id"]]["question"]
    terms = set(re.findall(r"\w{3,}", question.casefold()))
    background = document["context"]
    limit = CONTEXT_BYTES[action]
    paragraphs = re.split(r"\r?\n\s*\r?\n", background) if background else []
    ranked = sorted(enumerate(paragraphs), key=lambda p:
                    (-len(terms & set(re.findall(r"\w{3,}", p[1].casefold()))), p[0]))
    selected, remaining = [], limit
    for index, paragraph in ranked:
        cost = len(paragraph.encode("utf-8")) + (2 if selected else 0)
        if cost <= remaining:
            selected.append((index, paragraph)); remaining -= cost
        elif not selected:
            selected.append((index, paragraph.encode("utf-8")[:remaining].decode("utf-8", errors="ignore")))
            remaining = 0
    excerpt = "\n\n".join(p for _, p in sorted(selected))
    return {"research_brief": {"document_sha256": document["sha256"],
            "context": excerpt, "context_excerpted": excerpt != background,
            "context_original_bytes": len(background.encode("utf-8")),
            "objectives": list(document["objectives"])}}
