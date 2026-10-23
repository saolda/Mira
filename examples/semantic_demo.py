"""Run a bounded real-model demonstration against a separately managed server.

Does not launch, stop or import the reference application. No downloads.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from mira import Knowledge
from mira.demo import populate
from mira.embeddings import NomicHTTPEmbedding


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:18091")
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    model_hash = hashlib.file_digest(args.model.open("rb"), "sha256").hexdigest()
    backend = NomicHTTPEmbedding(args.endpoint, args.model.name + ":sha256:" + model_hash)
    queries = [
        ("How can a jacket slow the escape of warmth?", "r2#f1"),
        ("What makes a hot item cool down?", "r1#f1"),
        ("When is treating an entire object as one temperature inaccurate?", "r2#f2"),
    ]
    with tempfile.TemporaryDirectory(prefix="mira-real-semantic-") as root:
        knowledge = Knowledge(root, backend)
        populate(knowledge)
        counts = knowledge.rebuild()
        results = []
        for query, expected in queries:
            hits = knowledge.search(query, mode="vector", type="finding", limit=6)
            results.append({"query": query, "authored_expected": expected,
                            "expected_rank": next((i + 1 for i, h in enumerate(hits) if h["id"] == expected), None),
                            "literal_phrase_hits": [h["id"] for h in knowledge.search(query, type="finding")],
                            "ranked_findings": [{k: h[k] for k in ("id", "label", "score")} for h in hits[:3]]})
        print(json.dumps({"model": backend.identity, "index": counts,
                          "evaluation": "Three authored queries over synthetic fixtures; not a held-out or human-adjudicated benchmark.",
                          "results": results}, indent=2))


if __name__ == "__main__":
    main()
