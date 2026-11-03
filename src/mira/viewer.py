"""Local-only HTTP decision viewer. Only review files can be written by the server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import hmac
import json
import secrets
from urllib.parse import urlsplit, unquote, parse_qs

from .inspection import Inspector
from .knowledge_inspection import KnowledgeInspector, SnapshotChanged
from .live import RecoveryRequired
from .reviews import Reviews
from .store import ConflictError
from .prompts import PromptTemplates


class ViewerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, home=None, *, port=8767):
        self.inspector = Inspector(home)
        self.reviews = Reviews(self.inspector.catalog)
        self.knowledge = KnowledgeInspector(self.inspector.catalog)
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "MiraViewer/1"

    def log_message(self, *args): pass  # Never put research or review text in request logs.

    def _send(self, status, value, kind="application/json; charset=utf-8", *, policy=None):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", policy or "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
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
                      "/style.css": ("style.css", "text/css; charset=utf-8"),
                      "/knowledge.js": ("knowledge.js", "text/javascript; charset=utf-8"),
                      "/knowledge.css": ("knowledge.css", "text/css; charset=utf-8")}
            if path in static:
                name, kind = static[path]
                return self._send(200, files("mira").joinpath("viewer_assets", name).read_bytes(), kind)
            if path == '/glossary':
                from .experiments import existing_reader
                from .format import loads
                from .glossary import metadata
                from .glossary_view import content_policy
                # Serve the standard export, without a second renderer, a new
                # experiment, index writes or changes to canonical state.
                with existing_reader(self.server.inspector.catalog.home, blocking=False) as store:
                    store.read()
                    state = loads(store.path('research/state.json').read_text(encoding='utf-8'))
                    target = store.path('research/glossary.html')
                    if not target.exists(): return self._send(404, {'error': 'Run glossary-view to generate the standard glossary.'})
                    content = target.read_bytes()
                    marker = '<meta name="mira-glossary-commitment" content="' + metadata(state)['commitment'] + '">'
                    if marker.encode() not in content:
                        return self._send(409, {'error': 'Glossary export is stale. Run glossary-view to display the current glossary.'})
                return self._send(200, content, 'text/html; charset=utf-8',
                                  policy=content_policy() + "; frame-ancestors 'none'")
            parts = self._parts()
            if parts == ["api", "session"]: return self._send(200, {"review_token": self.server.token})
            if parts == ["api", "prompt-templates"]: return self._send(200, PromptTemplates().catalog())
            if parts == ["api", "experiments"]: return self._send(200, self.server.inspector.experiments())
            if len(parts) >= 3 and parts[:2] == ["api", "experiments"]:
                name = parts[2]
                if len(parts)>=4 and parts[3] in {'overview','knowledge','relationships','questions','snapshot'}:
                    knowledge=getattr(self.server,'knowledge',None)
                    if knowledge is None:
                        knowledge=KnowledgeInspector(self.server.inspector.catalog)
                        self.server.knowledge=knowledge
                    query=parse_qs(urlsplit(self.path).query,keep_blank_values=True,strict_parsing=True)
                    if any(len(v)!=1 for v in query.values()): raise ValueError('duplicate query parameter')
                    params={k:v[0] for k,v in query.items()}
                    if parts[3]!='knowledge' or len(parts)>4:
                        if set(params)-{'revision'}: raise ValueError('unknown snapshot parameter')
                    expected=params.get('revision')
                    if len(parts)==4 and parts[3]=='overview': return self._send(200,knowledge.overview(name,expected))
                    if len(parts)==4 and parts[3]=='snapshot': return self._send(200,knowledge.snapshot(name,expected))
                    if len(parts)==4 and parts[3]=='knowledge': return self._send(200,knowledge.inventory(name,params))
                    if len(parts)==5 and parts[3]=='knowledge': return self._send(200,knowledge.detail(name,parts[4],expected))
                    if len(parts)==5 and parts[3]=='relationships': return self._send(200,knowledge.relationships(name,parts[4],expected))
                    if len(parts)==5 and parts[3]=='questions':
                        snapshot=knowledge.overview(name,expected)
                        node=next((n for n in snapshot['nodes'] if n['id']==parts[4]),None)
                        if node is None: raise ValueError('unknown research question')
                        return self._send(200,{'schema':snapshot['schema'],'revision':snapshot['revision'],'node':node})
                    return self._send(404,{'error':'unknown knowledge resource'})
                if len(parts) == 3: return self._send(200, self.server.inspector.run(name))
                if len(parts) == 5 and parts[3] == "decisions":
                    data = self.server.inspector.decision(name, parts[4])
                    data["review"] = self.server.reviews.read(name, parts[4])
                    return self._send(200, data)
                if len(parts) == 5 and parts[3] == "actions":
                    return self._send(200, self.server.inspector.action(name, parts[4]))
            return self._send(404, {"error": "unknown viewer resource"})
        except SnapshotChanged as exc:
            return self._send(409, {'error': str(exc)})
        except (RecoveryRequired, BlockingIOError, FileNotFoundError) as exc:
            return self._send(503, {'error': 'Canonical research snapshot unavailable; writer or recovery may be active.'})
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
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
