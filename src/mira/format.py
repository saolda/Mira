"""Versioned Markdown contract and whole-corpus structural validation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
from urllib.parse import urlsplit

from markdown_it import MarkdownIt


class ValidationError(ValueError):
    pass


DOC_ID = re.compile(r"[rs][1-9a-z][0-9a-z]*\Z")
ANCHOR = re.compile(r"[fqei][1-9a-z][0-9a-z]*\Z")
EQ_ID = re.compile(r"e_[rs][1-9a-z][0-9a-z]*_[1-9][0-9]*\Z")
KINDS = {"finding", "observation", "claim", "inference", "hypothesis", "synthesis"}
EVIDENCE = {"unverified", "supported", "disputed", "inconclusive"}
QUESTION_STATES = {"open", "partially_answered", "answered", "superseded"}
STATUSES = {"unverified", "proposed", "reviewed", "rejected"}
TYPES = {"CITES", "SUPPORTS", "CONTRADICTS", "QUALIFIES", "DEPENDS_ON",
         "BUILDS_ON", "SYNTHESIZES", "RELATED_TO", "INFLUENCED_BY"}
MD = MarkdownIt("commonmark", {"html": False})


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def loads(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=unique,
                          parse_constant=lambda value: require(False, "nonfinite JSON"))
    except (ValueError, TypeError) as exc:
        raise ValidationError("invalid JSON: " + str(exc)) from exc


def base36(value):
    result = ""
    while value:
        value, digit = divmod(value, 36)
        result = "0123456789abcdefghijklmnopqrstuvwxyz"[digit] + result
    return result or "0"


@dataclass
class Unit:
    anchor: str
    label: str
    fields: dict[str, str]

    @property
    def kind(self):
        return {"f": "finding", "q": "question", "e": "equation", "i": "image"}[self.anchor[0]]

    @property
    def revision(self):
        return digest(dumps(asdict(self)))


@dataclass
class Relationship:
    source: str
    type: str
    target: str
    status: str = "proposed"

    def payload(self):
        return {"from": self.source, "type": self.type, "to": self.target, "status": self.status}


@dataclass
class Equation:
    id: str
    origin: str
    label: str
    expression: str
    variables: dict[str, str]
    assumptions: list[str]
    provenance: str
    revision: int = 1
    units: dict[str, str] = field(default_factory=dict)

    def validate(self):
        require(isinstance(self.id, str) and EQ_ID.fullmatch(self.id), "invalid equation ID")
        require(isinstance(self.origin, str) and DOC_ID.fullmatch(self.origin), "invalid equation origin")
        require(self.id.startswith("e_" + self.origin + "_"), "equation ID/origin mismatch")
        for value in (self.label, self.expression, self.provenance):
            require(isinstance(value, str) and value.strip(), "equation text required")
        require(type(self.revision) is int and self.revision == 1, "equation revision changes unsupported")
        require(isinstance(self.variables, dict) and self.variables, "equation variables required")
        require(all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
                    for k, v in self.variables.items()), "invalid variables")
        require(isinstance(self.units, dict) and set(self.units) <= set(self.variables), "invalid equation units")
        require(all(isinstance(v, str) and v.strip() for v in self.units.values()), "invalid unit description")
        require(isinstance(self.assumptions, list) and all(isinstance(v, str) and v.strip()
                    for v in self.assumptions), "invalid assumptions")


@dataclass
class Memory:
    id: str
    title: str
    summary: str
    revision: int = 1
    metadata: dict = field(default_factory=dict)
    next_ids: dict = field(default_factory=lambda: {"f": 1, "q": 1, "e": 1})
    units: list[Unit] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    def allocate(self, prefix):
        if prefix == "i": self.next_ids.setdefault("i", 1)
        value = self.next_ids[prefix]
        self.next_ids[prefix] += 1
        return prefix + base36(value)


def structural_lines(text):
    """Only top-level paragraph and heading lines may carry reserved syntax.

    Code, quotes, lists and inline-code spans cannot introduce anchors/sections.
    Adapted conceptually from the local Phase 1C parser, without runtime imports.
    """
    lines = text.splitlines(keepends=True)
    visible = {}
    tokens = MD.parse(text)
    for i, token in enumerate(tokens):
        if token.type == "inline" and token.level == 1 and token.map:
            start, end = token.map
            raw = "".join(lines[start:end])
            # Mask complete CommonMark code spans, including multiline spans.
            masked = list(raw)
            cursor = 0
            for match in re.finditer(r"`+", raw):
                if match.start() < cursor:
                    continue
                before = raw[:match.start()]
                if (len(before) - len(before.rstrip("\\"))) % 2:
                    continue
                closing = re.search(r"(?<!`)`{" + str(len(match[0])) + r"}(?!`)", raw[match.end():])
                if closing:
                    cursor = match.end() + closing.end()
                    masked[match.start():cursor] = ["\n" if c == "\n" else " " for c in raw[match.start():cursor]]
            for number, line in enumerate("".join(masked).splitlines(keepends=True), start):
                visible[number] = line
    return visible


def render(memory):
    header = {"version": 1, "id": memory.id, "revision": memory.revision,
              "summary": memory.summary, "metadata": memory.metadata, "next": memory.next_ids}
    parts = ["# " + memory.title, "", "```json", dumps(header).rstrip(), "```", "", "## Memory", ""]
    for unit in memory.units:
        parts += [f"[#{unit.anchor}] {unit.label}", ""]
        for key, value in unit.fields.items():
            parts += [f"**{key}:**" + ("\n\n" if key in {"Expression", "Variables"} else " ") + value, ""]
    parts += ["## Relationships", "", "```json",
              dumps({"version": 1, "relationships": [r.payload() for r in memory.relationships]}).rstrip(), "```", ""]
    text = "\n".join(parts)
    # Reject field text that would render as additional structure or be lossy.
    require(parse(text) == memory, "memory is not losslessly representable")
    return text


def parse(text):
    tokens = MD.parse(text)
    lines = text.splitlines(keepends=True)
    headings = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.level == 0:
            headings.append((token.tag, tokens[i + 1].content, token.map[0], token.map[1]))
    require(len(headings) >= 3 and headings[0][0] == "h1", "document title required")
    require([(h[0], h[1]) for h in headings[1:]] == [("h2", "Memory"), ("h2", "Relationships")],
            "expected Memory then terminal Relationships sections; other headings unsupported")
    title = headings[0][1]
    require(headings[0][2] == 0 and title.strip(), "title must be first")

    def json_fence(start, end):
        tail = "".join(lines[start:end])
        ts = MD.parse(tail)
        require(len(ts) == 1 and ts[0].type == "fence" and ts[0].info == "json", "one JSON fence required")
        return loads(ts[0].content)

    header = json_fence(headings[0][3], headings[1][2])
    require(isinstance(header, dict) and set(header) == {"version", "id", "revision", "summary", "metadata", "next"}, "header fields")
    require(type(header["version"]) is int and header["version"] == 1, "unsupported format version")
    relationships = json_fence(headings[2][3], len(lines))
    require(isinstance(relationships, dict) and set(relationships) == {"version", "relationships"}
            and type(relationships["version"]) is int and relationships["version"] == 1
            and isinstance(relationships["relationships"], list), "relationship envelope")
    body = "".join(lines[headings[1][3]:headings[2][2]])
    body_lines = body.splitlines(keepends=True)
    visible = structural_lines(body)
    markers = []
    for i, line in visible.items():
        if re.search(r"(?<!\\)(?:\\\\)*\[#", line):
            match = re.fullmatch(r"\[#([fqei][1-9a-z][0-9a-z]*)\] ([^\n]+)\n?", body_lines[i])
            require(match is not None and len(re.findall(r"(?<!\\)(?:\\\\)*\[#", line)) == 1, "malformed reserved anchor")
            markers.append((i, match[1], match[2]))
    require(not body[:sum(len(s) for s in body_lines[:markers[0][0]])].strip() if markers else not body.strip(),
            "unanchored memory content")
    units = []
    for n, (line, anchor, label) in enumerate(markers):
        stop = markers[n + 1][0] if n + 1 < len(markers) else len(body_lines)
        field_lines = structural_lines("".join(body_lines[line + 1:stop]))
        raw_lines = body_lines[line + 1:stop]
        starts = []
        for pos, value in field_lines.items():
            match = re.match(r"^\*\*([^*\n]+):\*\*(?: (.*)|$)", raw_lines[pos])
            if match:
                starts.append((pos, match[1], match[2] or ""))
        require(starts and not "".join(raw_lines[:starts[0][0]]).strip(), "unit fields required")
        fields = {}
        for j, (pos, key, first) in enumerate(starts):
            stop_field = starts[j + 1][0] if j + 1 < len(starts) else len(raw_lines)
            require(key not in fields, "duplicate unit field")
            fields[key] = (first + "\n" + "".join(raw_lines[pos + 1:stop_field])).strip()
        units.append(Unit(anchor, label, fields))
    edges = []
    for row in relationships["relationships"]:
        require(isinstance(row, dict) and set(row) == {"from", "type", "to", "status"}, "relationship fields")
        edges.append(Relationship(row["from"], row["type"], row["to"], row["status"]))
    memory = Memory(header["id"], title, header["summary"], header["revision"], header["metadata"], header["next"], units, edges)
    validate_memory(memory)
    return memory


def validate_memory(memory):
    require(isinstance(memory.id, str) and DOC_ID.fullmatch(memory.id), "invalid memory ID")
    for value in (memory.title, memory.summary):
        require(isinstance(value, str) and value.strip(), "title/summary required")
    require("\n" not in memory.title, "multiline title")
    require(type(memory.revision) is int and memory.revision > 0, "positive revision required")
    require(isinstance(memory.metadata, dict), "metadata object required")
    require(isinstance(memory.next_ids, dict) and set(memory.next_ids) in ({"f", "q", "e"}, {"f", "q", "e", "i"}), "allocator fields")
    require(all(type(v) is int and v > 0 for v in memory.next_ids.values()), "invalid allocator")
    seen = set()
    for unit in memory.units:
        require(isinstance(unit.anchor, str) and ANCHOR.fullmatch(unit.anchor), "invalid anchor")
        require(unit.anchor not in seen, "duplicate anchor")
        seen.add(unit.anchor)
        require(int(unit.anchor[1:], 36) < memory.next_ids[unit.anchor[0]], "allocator would reuse ID")
        require(isinstance(unit.label, str) and unit.label.strip() and "\n" not in unit.label, "invalid unit label")
        require(isinstance(unit.fields, dict) and all(isinstance(v, str) and v.strip() for v in unit.fields.values()), "empty unit field")
        if unit.kind == "finding":
            require(set(unit.fields) == {"Kind", "Evidence status", "Proposition", "Explanation", "Provenance"}, "finding fields")
            require(unit.fields["Kind"] in KINDS and unit.fields["Evidence status"] in EVIDENCE, "finding vocabulary")
        elif unit.kind == "question":
            require(set(unit.fields) == {"Question", "State"} and unit.fields["State"] in QUESTION_STATES, "question fields/state")
        elif unit.kind == "equation":
            require(set(unit.fields) in ({"Equation"}, {"Equation", "Description", "Expression", "Variables", "Provenance"}) and EQ_ID.fullmatch(unit.fields["Equation"]), "equation reference")
        else:
            require(set(unit.fields) == {"Image", "Figure reference", "Provenance"}, "image fields")


def external(ref):
    if not isinstance(ref, str) or any(c.isspace() for c in ref):
        return False
    parts = urlsplit(ref)
    return (parts.scheme in {"http", "https"} and bool(parts.hostname)) or bool(re.fullmatch(r"doi:10\.\d{4,9}/\S+", ref))


def validate_corpus(memories, equations):
    docs, units, edges = {}, {}, []
    for memory in memories:
        validate_memory(memory)
        require(memory.id not in docs, "duplicate document ID")
        docs[memory.id] = memory
        units[memory.id] = (memory, None)
        for unit in memory.units:
            units[memory.id + "#" + unit.anchor] = (memory, unit)
    eqs = {}
    for eq in equations:
        eq.validate()
        require(eq.id not in eqs, "duplicate equation ID")
        require(eq.origin in docs, "missing equation origin")
        eqs[eq.id] = eq
    referenced = set()
    for memory in memories:
        for unit in memory.units:
            if unit.kind == "equation":
                target = unit.fields["Equation"]
                require(target in eqs, "missing equation: " + target)
                referenced.add(target)
                if "Expression" in unit.fields:
                    require(unit.fields == equation_fields(eqs[target]), "equation presentation differs from definition")
    require(referenced == set(eqs), "orphan equation definition")
    seen = set()
    for memory in memories:
        for edge in memory.relationships:
            require(all(isinstance(v, str) for v in (edge.source, edge.type, edge.target, edge.status)), "relationship strings required")
            require(edge.type in TYPES and edge.status in STATUSES, "relationship type/status")
            source = memory.id + "#" + edge.source
            require(source in units, "invalid source unit: " + source)
            require(edge.target in units or edge.target in eqs or external(edge.target), "missing target: " + edge.target)
            require(edge.target != source, "self relationship unsupported")
            source_unit = units[source][1]
            target_unit = units.get(edge.target, (None, None))[1]
            if edge.type != "CITES":
                require(not external(edge.target), "external targets require CITES")
                require(target_unit is not None or edge.target in eqs, "conceptual target must be a unit")
            if edge.type in {"SUPPORTS", "CONTRADICTS", "QUALIFIES", "BUILDS_ON", "INFLUENCED_BY"}:
                require(source_unit.kind == "finding" and target_unit is not None and target_unit.kind == "finding", "relationship requires finding endpoints")
            if edge.type == "SYNTHESIZES":
                require(source_unit.kind == "finding" and source_unit.fields["Kind"] == "synthesis", "SYNTHESIZES source must be a synthesis finding")
                require(target_unit is not None and target_unit.kind in {"finding", "equation", "image"}, "invalid synthesis result target")
            ends = tuple(sorted((source, edge.target))) if edge.type == "RELATED_TO" else (source, edge.target)
            key = (edge.type, ends)
            require(key not in seen, "duplicate relationship")
            seen.add(key)
            edges.append({**edge.payload(), "from": source, "owner": memory.id})
    return docs, eqs, units, edges


def equation_fields(equation):
    def escape(value):
        return re.sub(r"([\\`*{}_\[\]#!])", r"\\\1", value.replace("<", "&lt;").replace(">", "&gt;"))
    variables = "\n".join("- " + escape(symbol) + ": " + escape(description) + " (units: " + escape(equation.units.get(symbol, "not supplied")) + ")"
                          for symbol, description in sorted(equation.variables.items()))
    return {"Equation": equation.id, "Description": escape(equation.label),
            "Expression": "$$\n" + equation.expression + "\n$$", "Variables": variables,
            "Provenance": escape(equation.provenance)}
