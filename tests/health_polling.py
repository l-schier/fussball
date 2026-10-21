from __future__ import annotations

import urllib.error
from collections.abc import Callable
from time import monotonic, sleep
from urllib.request import urlopen


def poll_health_endpoint(
    url: str,
    *,
    timeout: float,
    interval: float,
    request_timeout: float = 2,
    before_request: Callable[[], None] | None = None,
) -> bytes | None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if before_request is not None:
            before_request()
        try:
            with urlopen(url, timeout=request_timeout) as response:
                assert response.status == 200
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            sleep(interval)
    return None
