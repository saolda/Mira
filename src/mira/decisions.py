"""One-call LLM contracts and scripted transport. IDs/state belong to the harness."""
from .format import dumps, loads, require

from .prompts import PromptTemplates

FINDING = {"label": "nonempty string", "kind": "observation|claim|inference|hypothesis",
           "proposition": "nonempty string", "explanation": "nonempty string", "provenance": "nonempty string",
           "evidence_ids": ["IDs from supplied search results"]}
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
    if action == "R1":
        fields(value, ["keywords"]); keywords(value["keywords"])
    elif action == "R4":
        fields(value, ["decision", "keywords", "children", "rationale"])
        decision = value["decision"]
        require(decision in {"kill", "exhaust", "retry", "retry_split", "exhaust_split"}, "invalid node decision")
        text(value["rationale"])
        if decision in {"retry", "retry_split"}: keywords(value["keywords"])
        else: require(value["keywords"] is None, "keywords only allowed for retries")
        require(isinstance(value["children"], list), "children list required")
        require(bool(value["children"]) == decision.endswith("split"), "split requires child questions")
        for question in value["children"]: text(question)
        require(len(value["children"]) == len(set(value["children"])), "duplicate child question")
    elif action == "R3":
        fields(value, ["memories", "no_finding_reason"])
        require(isinstance(value["memories"], list), "memories list required")
        if not value["memories"]: text(value["no_finding_reason"])
        else: require(value["no_finding_reason"] is None, "unexpected no-finding reason")
        ids = {r["id"] for r in evidence["results"]}
        for draft in value["memories"]:
            fields(draft, ["title", "summary", "findings"])
            text(draft["title"]); text(draft["summary"])
            require(isinstance(draft["findings"], list) and draft["findings"], "findings required")
            for finding in draft["findings"]:
                fields(finding, FINDING)
                for key in ("label", "proposition", "explanation", "provenance"): text(finding[key])
                require(finding["kind"] in {"observation", "claim", "inference", "hypothesis"}, "invalid finding kind")
                require(isinstance(finding["evidence_ids"], list) and finding["evidence_ids"] and
                        all(isinstance(i, str) and i in ids for i in finding["evidence_ids"]), "unsupported evidence reference")
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
