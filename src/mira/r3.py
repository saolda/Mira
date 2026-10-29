"""Ordered extraction contract. Models propose results; Python owns memories."""
import re

from .format import (Equation, Memory, Unit, Relationship, base36, require,
                     external, equation_fields)
from .r1 import question_context
from .sources import descriptor

TEXT_TYPES = {"finding", "observation", "claim", "inference", "hypothesis"}


class OutputError(ValueError):
    """A received R3 response could not be decoded as a complete proposal."""


def context(state, node_id, research):
    # Preserve the provider's structured fields, including explicit truncation and
    # content kind. The raw feed is retained on disk, not duplicated in the prompt.
    return {"question": state["nodes"][node_id]["question"],
            "question_context": question_context(state, node_id),
            "research": {"status": research["status"], "results": research["results"]}}


def text(value, allow_empty=False):
    require(isinstance(value, str) and (allow_empty or value.strip()), "R3 text required")
    require(not any(ord(c) < 32 and c not in "\n\t\r" for c in value), "invalid control character in R3 text")


def strings(value):
    if isinstance(value, str): yield value
    elif isinstance(value, dict):
        for v in value.values(): yield from strings(v)
    elif isinstance(value, list):
        for v in value: yield from strings(v)


def validate(value, evidence):
    """Validate extraction, discarding unused summary text for empty results."""
    require(isinstance(value, dict) and set(value) == {"summary", "results"} and isinstance(value["results"], list), "R3 requires summary and an ordered results array")
    if not value["results"] and isinstance(value["summary"], str):
        value = {**value, "summary": ""}
    text(value["summary"], allow_empty=not value["results"])
    require(len(evidence["results"]) <= 1, "R3 extracts one source at a time")
    sources = {row["id"]: row for row in evidence["results"]}
    results = value["results"]
    for result in results:
        require(isinstance(result, dict) and isinstance(result.get("type"), str), "R3 result type required")
        kind = result["type"]
        common = {"type", "text", "source_ids", "related_to"}
        optional = set()
        if kind in TEXT_TYPES: fields = common | {"qualification"}
        elif kind == "question": fields = common | {"qualification", "origin"}
        elif kind == "equation":
            fields = common | {"latex", "variables"}
            optional = {"origin"}
        elif kind == "image": fields = common | {"url", "reference"}
        else: raise ValueError("unsupported R3 result type")
        require(fields <= set(result) <= fields | optional, "unexpected/missing R3 result fields")
        text(result["text"])
        ids = result["source_ids"]
        require(isinstance(ids, list) and ids and all(isinstance(i, str) and i in sources for i in ids), "invalid R3 source reference")
        require(len(ids) == len(set(ids)), "duplicate R3 source reference")
        ref = result["related_to"]
        require(ref is None or type(ref) is int and 0 <= ref < len(results), "invalid related_to index")
        if kind in TEXT_TYPES: text(result["qualification"], allow_empty=True)
        elif kind == "question":
            text(result["qualification"], allow_empty=True)
            require(isinstance(result["origin"], str) and result["origin"] in {"source", "derived"}, "question origin must be source or derived")
        elif kind == "equation":
            text(result["latex"])
            require(not any(c in result["latex"] for c in ("$$", "```", "[#")), "unsafe equation delimiters")
            require("origin" not in result or isinstance(result["origin"], str) and result["origin"] in {"source", "derived"}, "equation origin must be source or derived")
            variables = result["variables"]
            require(isinstance(variables, list) and variables, "equation symbol descriptions required")
            seen = set()
            for variable in variables:
                require(isinstance(variable, dict) and set(variable) == {"symbol", "description", "units"}, "equation variable fields")
                text(variable["symbol"]); text(variable["description"])
                require(variable["symbol"] not in seen, "duplicate equation symbol")
                seen.add(variable["symbol"])
                if variable["units"] is not None: text(variable["units"])
        else:
            if result["reference"] is not None: text(result["reference"])
            url = result["url"]
            supplied = [s for i in ids for s in strings(sources[i])]
            if result["reference"] is not None:
                reference = " ".join(result["reference"].split()).casefold()
                require(any(reference in " ".join(s.split()).casefold() for s in supplied), "figure reference not present in cited research")
            require(url is not None or result["reference"] is not None, "image URL or figure reference required")
            if url is not None:
                text(url)
                require(url.startswith(("https://", "http://")) and external(url) and not any(c in url for c in '<>"\\'), "invalid image URL")
                # Match a complete supplied URL, not a fabricated suffix of one.
                require(any(url == s or url in [candidate.rstrip(".,;!?)") for candidate in re.findall(r'https?://[^\s<>"\x27]+', s)] for s in supplied), "image URL not present in cited research")
    for start in range(len(results)):
        seen, current = set(), start
        while current is not None:
            require(current not in seen, "self-reference or cycle in R3 results")
            seen.add(current)
            current = results[current]["related_to"]
    return value


def prose(value):
    """Store model prose as text, not executable HTML or canonical markup."""
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # A model's prose may contain text resembling a compact field label.
    value = re.sub(r"(?m)^([A-Z][A-Za-z ]*):", r"\1\\:", value)
    return re.sub(r"([\\`*{}_\[\]#!])", r"\\\1", value).strip()


def label(value):
    return prose(" ".join(value.split())[:110])


def create_memory(state, memories, equations, ledger, node_id, results, evidence, summary):
    validate({"summary": summary, "results": results}, evidence)
    if not results: return None
    identity = "r" + base36(ledger["r"]); ledger["r"] += 1
    question = state["nodes"][node_id]["question"]
    memory = Memory(identity, "Research: " + label(question), prose(summary), metadata={
        "node_id": node_id, "kind": "research", "source_memories": [], "synthesized_by": None,
        "created_order": len(memories) + 1, "evidence_ref": evidence["reference"],
        "source": {k: v for k, v in descriptor(evidence["results"][0]).items() if k != "authors"}})
    anchors = []
    for result in results:
        kind = result["type"]
        anchor = memory.allocate("e" if kind == "equation" else "i" if kind == "image" else "q" if kind == "question" else "f")
        anchors.append(anchor)
        provenance = "Equation origin: " + (result.get("origin") or "unspecified")
        if kind in TEXT_TYPES:
            unit = Unit(anchor, kind.title(), {"Kind": kind, "Proposition": prose(result["text"]),
                **({"Qualification": prose(result["qualification"])} if result["qualification"].strip() else {})})
        elif kind == "question":
            unit = Unit(anchor, "Question", {"Question": prose(result["text"]), "State": "open",
                "Origin": result["origin"],
                **({"Qualification": prose(result["qualification"])} if result["qualification"].strip() else {})})
        elif kind == "equation":
            origin = result.get("origin") or "unspecified"
            equation = Equation(f"e_{identity}_{int(anchor[1:], 36)}", identity, result["text"].strip(), result["latex"],
                {v["symbol"]: v["description"] for v in result["variables"]}, [],
                provenance + (" (model-derived, not asserted to appear in source)." if origin == "derived" else " (model-reported, unverified)."),
                units={v["symbol"]: v["units"] for v in result["variables"] if v["units"] is not None})
            equations.append(equation)
            unit = Unit(anchor, "Equation", {**equation_fields(equation), **({"Origin": origin} if origin != "unspecified" else {})})
        else:
            image = f'![{prose(result["text"])}](<{result["url"]}>)' if result["url"] else prose(result["text"])
            unit = Unit(anchor, "Image", {"Image": image,
                **({"Figure reference": prose(result["reference"])} if result["reference"] else {})})
        memory.units.append(unit)
    for index, result in enumerate(results):
        if result["related_to"] is not None:
            memory.relationships.append(Relationship(anchors[index], "RELATED_TO", identity + "#" + anchors[result["related_to"]], "unverified"))
    memories.append(memory)
    state["nodes"][node_id]["memory_ids"].append(identity)
    return memory
