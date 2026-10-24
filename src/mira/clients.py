"""Small configurable HTTP generation transport; no service lifecycle control."""
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError
from urllib.parse import urlsplit

from .format import require


def wire_text(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        import base64
        return "base64:" + base64.b64encode(data).decode("ascii")


class CallError(RuntimeError):
    def __init__(self, message, raw=None):
        super().__init__(message)
        self.raw = raw


class NoRedirect(HTTPRedirectHandler):
    # Never forward an authentication header to an unexpected redirect target.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPModel:
    def __init__(self, endpoint, model, *, api_key=None, temperature=0, max_tokens=2048,
                 timeout=120, json_output=True, no_thinking=False):
        parsed = urlsplit(endpoint)
        require(parsed.scheme in {"http", "https"} and parsed.hostname and
                not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
                "endpoint must be an HTTP(S) base URL without credentials or query parameters")
        require(isinstance(model, str) and model.strip(), "model identifier required")
        require(type(max_tokens) is int and max_tokens > 0 and timeout > 0, "invalid generation limits")
        require(type(temperature) in {int, float} and 0 <= temperature <= 2, "invalid temperature")
        self.endpoint = endpoint.rstrip("/") + ("/chat/completions" if parsed.path.rstrip("/").endswith("/v1") else "/v1/chat/completions")
        self.model, self.timeout, self.api_key = model, timeout, api_key
        self.settings = {"temperature": temperature, "max_tokens": max_tokens}
        if json_output: self.settings["response_format"] = {"type": "json_object"}
        if no_thinking: self.settings["chat_template_kwargs"] = {"enable_thinking": False}
        self.secrets = (api_key,) if api_key else ()

    def complete(self, serialized_request):
        headers = {"Content-Type": "application/json"}
        if self.api_key: headers["Authorization"] = "Bearer " + self.api_key
        request = Request(self.endpoint, data=serialized_request.encode("utf-8"), headers=headers, method="POST")
        try:
            with build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                body = response.read()
                raw = wire_text(body)
                if raw.startswith("base64:"):
                    raise CallError("non-UTF8 model response (raw is base64 encoded)", raw)
                return raw
        except HTTPError as exc:
            with exc:
                raw = wire_text(exc.read())
            raise CallError("model HTTP status " + str(exc.code), raw) from None
