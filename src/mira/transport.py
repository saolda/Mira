"""Central request spacing for standalone adapters; research supplies durable pacing."""
import threading
import time
from .query_profiles import registry, select

_LOCK = threading.Lock()
_LAST = {}


def standalone(endpoint, parameters):
    from urllib.parse import urlsplit
    host = urlsplit(endpoint).netloc
    configuration = registry()
    interval = max(select(configuration, 'default')['min_interval_seconds'], configuration['host_min_intervals'].get(host, 0))
    with _LOCK:
        delay = max(0, _LAST.get(host, 0) - time.monotonic())
        if delay: time.sleep(delay)
        _LAST[host] = time.monotonic() + interval
