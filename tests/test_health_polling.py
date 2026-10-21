from __future__ import annotations

import urllib.error
from unittest.mock import Mock

from tests.health_polling import poll_health_endpoint


def test_poll_health_endpoint_retries_transient_connection_errors(monkeypatch) -> None:
    times = iter((0, 0, 0.2))
    attempts = 0
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    response.status = 200
    response.read.return_value = b'{"status":"ok"}'

    def open_url(url: str, *, timeout: float):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise urllib.error.URLError("server starting")
        return response

    monkeypatch.setattr("tests.health_polling.monotonic", lambda: next(times))
    monkeypatch.setattr("tests.health_polling.sleep", Mock())
    monkeypatch.setattr("tests.health_polling.urlopen", open_url)

    body = poll_health_endpoint("http://127.0.0.1:8000/health", timeout=1, interval=0.1)

    assert body == b'{"status":"ok"}'
    assert attempts == 2
