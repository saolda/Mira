"""External research search contracts, separate from the internal SQLite index."""
from copy import deepcopy

from .format import require


def validate_search(result):
    require(isinstance(result, dict) and result.get("status") in {"ok", "empty", "failed", "rate_limited"}, "invalid search outcome")
    require(isinstance(result.get("results"), list), "search results required")
    require(bool(result["results"]) == (result["status"] == "ok"), "inconsistent search outcome")
    ids = set()
    for row in result["results"]:
        for key in ("id", "url", "title", "content", "content_kind"):
            require(isinstance(row.get(key), str) and row[key].strip(), "incomplete search evidence: " + key)
        require(row["url"].startswith(("https://", "http://")), "invalid evidence URL")
        require(row["id"] not in ids, "duplicate result ID"); ids.add(row["id"])
    return result


class FixtureSearch:
    def __init__(self, results):
        self.results = iter(results)
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        result = next(self.results)
        if isinstance(result, Exception): raise result
        return deepcopy(result)
