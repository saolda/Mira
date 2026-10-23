"""Replaceable embedding interface; no lifecycle control of external services."""
from __future__ import annotations
import hashlib
import json
import math
import re
from typing import Protocol
from urllib.request import Request, urlopen

from .format import require


class EmbeddingBackend(Protocol):
    identity: str
    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


class TestEmbedding:
    """Deterministic token hashing TEST DOUBLE. Not a semantic model."""
    identity = "test-double:sha256-token-hash-v1:128"

    def embed(self, texts, *, query=False):
        result = []
        for text in texts:
            vector = [0.0] * 128
            for word in re.findall(r"\w+", text.lower()):
                value = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big")
                vector[value % 128] += 1.0
            result.append(vector)
        return result


class NomicHTTPEmbedding:
    """Client for an independently managed llama.cpp nomic endpoint.

    identity must include a model artifact digest; the caller owns server setup.
    """
    def __init__(self, endpoint, model_identity):
        require(model_identity and not model_identity.startswith("test-double:"), "real model identity required")
        self.endpoint = endpoint.rstrip("/") + "/v1/embeddings"
        self.identity = "nomic-http:" + model_identity + ":prefix-v1"

    def embed(self, texts, *, query=False):
        prefix = "search_query: " if query else "search_document: "
        result = []
        for text in texts:
            payload = {"model": "nomic-embed-text-v1.5", "input": [prefix + text]}
            req = Request(self.endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=60) as response:
                rows = json.load(response)["data"]
            require(len(rows) == 1 and rows[0]["index"] == 0, "embedding response cardinality/order")
            result.append(rows[0]["embedding"])
        return result


def validate_vectors(vectors, count):
    require(isinstance(vectors, list) and len(vectors) == count, "embedding count mismatch")
    dimensions = {len(v) for v in vectors if isinstance(v, list)}
    require(not count or (len(dimensions) == 1 and next(iter(dimensions)) > 0), "embedding dimensions")
    require(all(isinstance(v, list) and all(type(x) in (int, float) and math.isfinite(x) for x in v)
                for v in vectors), "nonfinite/invalid embedding")
    return next(iter(dimensions)) if dimensions else 0


def cosine(a, b):
    require(len(a) == len(b), "embedding dimension mismatch")
    norm = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / norm if norm else 0.0
