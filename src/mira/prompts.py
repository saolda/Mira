"""Editable on-disk prompt templates with immutable per-call provenance."""
import json
from pathlib import Path
import os
import re
import sys

from .format import digest, dumps, loads, require

ACTIONS = ("R1", "R3", "R4", "S2")
COMMON_SLOTS = ("root_question", "question", "node", "ancestor_questions", "linked_memories",
                "children", "strategy", "next_database", "search_history", "equations")
SLOTS = {"R1": COMMON_SLOTS, "R3": COMMON_SLOTS + ("search_evidence",),
         "R4": COMMON_SLOTS + ("search_evidence",),
         "S2": ("root_question", "question", "node", "ancestor_questions", "input_memories", "equations")}
PLACEHOLDER = re.compile(r"{{\s*([a-z_]+)\s*}}")


def template_directory():
    configured = os.environ.get("MIRA_PROMPT_TEMPLATES")
    if configured: return Path(configured).absolute()
    source = Path(__file__).resolve().parents[2] / "prompt_templates"
    return source if source.is_dir() else Path(sys.prefix) / "share/mira/prompt_templates"


class PromptTemplates:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else template_directory()

    def sources(self, action):
        require(action in ACTIONS, "unknown LLM action")
        result = []
        for name in ("system.txt", action + ".user.json", action + ".contract.json"):
            source = (self.directory / name).read_bytes().decode("utf-8")
            result.append({"path": "prompt_templates/" + name, "sha256": digest(source), "source": source})
        return result

    def render(self, action, context):
        sources = self.sources(action)
        contract = loads(sources[2]["source"])
        require(isinstance(contract, dict), "prompt contract must be an object")
        require(not (set(context) - set(SLOTS[action])), "context has no declared prompt slot: " + str(set(context) - set(SLOTS[action])))
        # Every named slot is explicit; missing values become null, never inferred.
        bound_context = {key: context.get(key) for key in SLOTS[action]}
        values = {key + "_json": value for key, value in bound_context.items()}
        values["output_contract_json"] = contract
        source = sources[1]["source"]
        placeholders = {match[1] for match in PLACEHOLDER.finditer(source)}
        require(placeholders == set(values), "template must include every declared slot exactly by name; unknown prompt placeholder or missing slot")
        def fill(match):
            key = match[1]
            # Compact schema avoids spending the input budget on schema indentation;
            # source schema files stay readable. Context indentation follows its slot.
            if key == "output_contract_json":
                return json.dumps(values[key], ensure_ascii=False, separators=(",", ":"))
            line_start = source.rfind("\n", 0, match.start()) + 1
            indent = re.match(r"[ \t]*", source[line_start:]).group()
            return dumps(values[key]).rstrip("\n").replace("\n", "\n" + indent)
        user = PLACEHOLDER.sub(fill, source)
        filled = loads(user)
        require(isinstance(filled, dict) and filled.get("action") == action and
                filled.get("context") == bound_context and filled.get("output_contract") == contract and
                isinstance(filled.get("task"), str) and filled["task"].strip() and
                isinstance(filled.get("instructions"), list) and filled["instructions"] and
                all(isinstance(item, str) and item.strip() for item in filled["instructions"]) and
                isinstance(filled.get("output_requirements"), str) and filled["output_requirements"].strip(),
                "template must preserve task, instructions, complete context and output_contract")
        messages = [{"role": "system", "content": sources[0]["source"]}, {"role": "user", "content": user}]
        return messages, {"version": 1, "action": action, "files": sources,
            "bindings": {"context": bound_context, "output_contract": contract, "slots": bound_context}, "filled_messages": messages}

    def catalog(self):
        return [{"action": action, "files": self.sources(action),
                 "variables": [key + "_json" for key in SLOTS[action]] + ["output_contract_json"]} for action in ACTIONS]
