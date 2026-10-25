"""Small plain-text renderer with immutable per-call source and binding snapshots."""
from pathlib import Path
import os
import re
import sys

from .format import digest, dumps, require

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
        name = action + ".txt"
        source = (self.directory / name).read_bytes().decode("utf-8")
        return [{"path": "prompt_templates/" + name, "sha256": digest(source), "source": source}]

    def render(self, action, context):
        sources = self.sources(action)
        declared = set(SLOTS[action])
        require(not (set(context) - declared), "context has no declared prompt slot: " + str(set(context) - declared))
        source = sources[0]["source"]
        placeholders = {match[1] for match in PLACEHOLDER.finditer(source)}
        require(not (placeholders - declared), "unknown prompt placeholder: " + str(placeholders - declared))
        # Check all double-braced expressions, including misspellings outside the
        # supported variable grammar. Substitution examines source only, once.
        remainder = PLACEHOLDER.sub("", source)
        require("{{" not in remainder and "}}" not in remainder, "malformed prompt placeholder")
        require(placeholders == declared, "template has missing slot: " + str(declared - placeholders))
        require(not (declared - set(context)), "missing prompt values: " + str(declared - set(context)))
        values = {key: context[key] for key in SLOTS[action]}
        filled = PLACEHOLDER.sub(lambda match: dumps(values[match[1]]).rstrip("\n"), source)
        messages = [{"role": "user", "content": filled}]
        return messages, {"version": 2, "format": "text", "action": action, "files": sources,
                          "bindings": {"context": values}, "filled_messages": messages}

    def catalog(self):
        return [{"action": action, "files": self.sources(action), "variables": list(SLOTS[action])} for action in ACTIONS]
