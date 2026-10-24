"""Local-only HTTP decision viewer. Only review files can be written by the server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import hmac
import json
import secrets
from urllib.parse import urlsplit, unquote

from .inspection import Inspector
from .reviews import Reviews
from .store import ConflictError


class ViewerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, home=None, *, port=8767):
        self.inspector = Inspector(home)
        self.reviews = Reviews(self.inspector.catalog)
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "MiraViewer/1"

    def log_message(self, *args): pass  # Never put research or review text in request logs.

    def _send(self, status, value, kind="application/json; charset=utf-8"):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError): pass

    def _allowed(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def _parts(self):
        return [unquote(part) for part in urlsplit(self.path).path.split("/") if part]

    def do_GET(self):
        if not self._allowed(): return self._send(403, {"error": "local viewer host required"})
        try:
            path = urlsplit(self.path).path
            static = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in static:
                name, kind = static[path]
                return self._send(200, files("mira").joinpath("viewer_assets", name).read_bytes(), kind)
            parts = self._parts()
            if parts == ["api", "session"]: return self._send(200, {"review_token": self.server.token})
            if parts == ["api", "experiments"]: return self._send(200, self.server.inspector.experiments())
            if len(parts) >= 3 and parts[:2] == ["api", "experiments"]:
                name = parts[2]
                if len(parts) == 3: return self._send(200, self.server.inspector.run(name))
                if len(parts) == 5 and parts[3] == "decisions":
                    data = self.server.inspector.decision(name, parts[4])
                    data["review"] = self.server.reviews.read(name, parts[4])
                    return self._send(200, data)
                if len(parts) == 5 and parts[3] == "actions":
                    return self._send(200, self.server.inspector.action(name, parts[4]))
            return self._send(404, {"error": "unknown viewer resource"})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            return self._send(400, {"error": str(exc)})

    def do_POST(self):
        if not self._allowed(): return self._send(403, {"error": "local viewer host required"})
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
            return self._send(403, {"error": "same-origin review required"})
        if not hmac.compare_digest(self.headers.get("X-Mira-Token", ""), self.server.token):
            return self._send(403, {"error": "review token required"})
        if self.headers.get("Content-Type") != "application/json": return self._send(415, {"error": "JSON required"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 100000: return self._send(413, {"error": "review body too large or missing"})
            parts = self._parts()
            if len(parts) != 5 or parts[:2] != ["api", "experiments"] or parts[3] != "reviews":
                return self._send(404, {"error": "only local review writes are supported"})
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or set(payload) != {"status", "comments", "expected_revision"}:
                return self._send(400, {"error": "review fields required"})
            self.server.inspector.decision(parts[2], parts[4])  # Existence and isolation check.
            result = self.server.reviews.save(parts[2], parts[4], **payload)
            return self._send(200, result)
        except ConflictError as exc: return self._send(409, {"error": str(exc)})
        except (ValueError, OSError, KeyError, TypeError) as exc: return self._send(400, {"error": str(exc)})


def serve(home=None, *, port=8767):
    with ViewerServer(home, port=port) as server:
        print(f"Mira decision viewer: http://127.0.0.1:{server.server_port}", flush=True)
        print(f"Local experiments: {server.inspector.catalog.home / 'research'}", flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
