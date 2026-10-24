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


class ArxivSearch:
    """Single-provider Atom adapter adapted from historical actions._arxiv.

    Query is passed unchanged: no hidden keyword rewriting or fallback provider.
    Rate spacing is process-wide. Full raw Atom is retained as evidence but is
    excluded from the bounded LLM context, which explicitly carries abstracts.
    """
    import threading
    _lock = threading.Lock()
    _last_request = None

    def __init__(self, *, limit=2, timeout=30, max_abstract_chars=2500, opener=None):
        from urllib.request import urlopen
        require(type(limit) is int and 1 <= limit <= 10 and timeout > 0 and max_abstract_chars > 0, "invalid search limits")
        self.limit, self.timeout, self.max_abstract_chars = limit, timeout, max_abstract_chars
        self.opener = opener or urlopen

    def search(self, query):
        import re
        import time
        from urllib.request import Request
        from urllib.parse import urlencode
        from urllib.error import HTTPError
        from xml.etree import ElementTree
        url = "https://export.arxiv.org/api/query?" + urlencode({"search_query": query, "start": 0,
            "max_results": self.limit, "sortBy": "relevance", "sortOrder": "descending"})
        req = Request(url, headers={"User-Agent": "Mira/0.2 (bounded local research; https://github.com/saolda/Mira)", "Accept": "application/atom+xml"})
        with ArxivSearch._lock:
            if ArxivSearch._last_request is not None:
                time.sleep(max(0, 3 - (time.monotonic() - ArxivSearch._last_request)))
            ArxivSearch._last_request = time.monotonic()
            try:
                with self.opener(req, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
            except HTTPError as exc:
                result = {"status": "rate_limited" if exc.code == 429 else "failed", "results": [],
                        "http_status": exc.code, "retry_after": exc.headers.get("Retry-After"),
                        "request_url": url, "error": "arXiv HTTP request failed"}
                exc.close()
                return result
            except (OSError, TimeoutError) as exc:
                return {"status": "failed", "results": [], "request_url": url, "error": type(exc).__name__}
        try:
            root = ElementTree.fromstring(raw)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            require(root.tag == "{http://www.w3.org/2005/Atom}feed", "expected Atom feed")
            results = []
            for entry in root.findall("a:entry", ns):
                def field(name): return re.sub(r"\s+", " ", entry.findtext("a:" + name, default="", namespaces=ns)).strip()
                identity, summary = field("id"), field("summary")
                require("/api/errors" not in identity, "arXiv returned an API error entry")
                results.append({"id": identity, "url": identity, "title": field("title"),
                    "content": summary[:self.max_abstract_chars], "content_kind": "abstract",
                    "truncated": len(summary) > self.max_abstract_chars, "published": field("published"),
                    "authors": [author.findtext("a:name", default="", namespaces=ns) for author in entry.findall("a:author", ns)]})
            require(len(results) <= self.limit, "provider exceeded requested result bound")
            return validate_search({"status": "ok" if results else "empty", "results": results,
                                    "request_url": url, "raw_api_response": raw})
        except (ValueError, ElementTree.ParseError) as exc:
            return {"status": "failed", "results": [], "request_url": url, "raw_api_response": raw,
                    "error": "invalid arXiv response: " + str(exc)}
