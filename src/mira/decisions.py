"""One-call LLM contracts and scripted transport. IDs/state belong to the harness."""
from .format import dumps, loads, require

from .prompts import PromptTemplates

def prepared_request(model, settings, action, context):
    require(set(settings) <= {"temperature", "max_tokens", "top_p", "seed", "response_format", "chat_template_kwargs"}, "unsupported generation settings")
    messages, provenance = PromptTemplates().render(action, context)
    serialized = dumps({"model": model, **settings, "messages": messages})
    return serialized, provenance


def request(model, settings, action, context):
    return prepared_request(model, settings, action, context)[0]


def fields(value, keys):
    require(isinstance(value, dict) and set(value) == set(keys), "unexpected/missing response fields")


def text(value):
    require(isinstance(value, str) and value.strip(), "nonempty text required")


def keywords(value):
    require(isinstance(value, list) and value, "keywords required")
    for term in value: text(term)


def proposal(raw):
    envelope = loads(raw)
    require(isinstance(envelope, dict) and isinstance(envelope.get("choices"), list) and len(envelope["choices"]) == 1, "one completion required")
    choice = envelope["choices"][0]
    require(choice.get("finish_reason") == "stop", "incomplete model output")
    return loads(choice["message"]["content"]), {"model": envelope.get("model"), "usage": envelope.get("usage")}


def validate(action, value, evidence=None):
    if action == "R0":
        fields(value, ["strategy", "reason"])
        text(value["strategy"]); text(value["reason"])
        from .strategies import select
        select(evidence, value["strategy"])
    elif action == "R1":
        fields(value, ["keywords"]); keywords(value["keywords"])
    elif action == "R4":
        fields(value, ["decision", "reason"])
        require(isinstance(value["decision"], str) and value["decision"] in {"kill", "answered", "retry"}, "invalid node decision")
        text(value["reason"])
    elif action == "R5":
        fields(value, ["questions"])
        require(isinstance(value["questions"], list), "questions list required")
        for question in value["questions"]: text(question)
    elif action == "R3":
        from .r3 import validate
        validate(value, evidence)
    return value


class ScriptedLLM:
    """Queue of proposals, exact raw responses or exceptions; no generated reasoning."""
    model = "scripted-fixture-v1"
    settings = {"temperature": 0, "max_tokens": 2048}
    secrets = ()

    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def complete(self, serialized_request):
        self.requests.append(serialized_request)
        result = next(self.responses)
        if isinstance(result, BaseException): raise result
        if isinstance(result, str): return result
        return dumps({"model": self.model, "choices": [{"finish_reason": "stop", "message": {"content": dumps(result)}}], "usage": None})
