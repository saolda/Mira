"""Shared decision budgeting; tokenizer calls never perform inference."""
from .format import require


def measure(serialized, reserve, limit, counter=None):
    usage = counter(serialized) if counter else {
        "prompt_tokens": len(serialized.encode("utf-8")),
        "estimator": "UTF-8 request bytes (fallback; no model tokenizer)",
    }
    require(type(usage.get("prompt_tokens")) is int and usage["prompt_tokens"] >= 0,
            "invalid model token count")
    window = usage.get("context_window", limit)
    require(type(window) is int and window > 0, "invalid model context window")
    return {**usage, "request_bytes": len(serialized.encode("utf-8")),
            "output_reserve": reserve, "context_budget": min(limit, window),
            "estimated_tokens": usage["prompt_tokens"] + reserve,
            "over_context_budget": usage["prompt_tokens"] + reserve > min(limit, window)}
