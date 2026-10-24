"""Editable on-disk prompt templates with immutable per-call provenance."""
from pathlib import Path
import os
import re
import sys

from .format import digest, dumps, loads, require

ACTIONS = ("R1", "R3", "R4", "S2")
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
        # Indent JSON fragments at their insertion depth, retaining the previous
        # wire representation exactly. Inserted data is never templated again.
        bindings = {"context_json": dumps(context).rstrip("\n").replace("\n", "\n  "),
                    "output_contract_json": dumps(contract).rstrip("\n").replace("\n", "\n  ")}
        def fill(match):
            key = match[1]
            require(key in bindings, "unknown prompt placeholder: " + key)
            return bindings[key]
        user = PLACEHOLDER.sub(fill, sources[1]["source"])
        filled = loads(user)
        require(isinstance(filled, dict) and filled.get("action") == action and
                filled.get("context") == context and filled.get("output_contract") == contract,
                "template must preserve action, complete context and output_contract")
        messages = [{"role": "system", "content": sources[0]["source"]}, {"role": "user", "content": user}]
        return messages, {"version": 1, "action": action, "files": sources,
            "bindings": {"context": context, "output_contract": contract}, "filled_messages": messages}

    def catalog(self):
        return [{"action": action, "files": self.sources(action),
                 "variables": ["context_json", "output_contract_json"]} for action in ACTIONS]
