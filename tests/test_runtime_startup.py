from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

from tests.health_polling import poll_health_endpoint


def test_production_server_serves_the_health_endpoint() -> None:
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(project_root), str(project_root / "fussball")))

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=project_root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    def ensure_server_is_running() -> None:
        if server.poll() is not None:
            _, error = server.communicate()
            raise AssertionError(f"Production server exited before becoming healthy:\n{error}")

    try:
        body = poll_health_endpoint(
            f"http://127.0.0.1:{port}/health",
            timeout=15,
            interval=0.1,
            request_timeout=1,
            before_request=ensure_server_is_running,
        )
        if body is None:
            raise AssertionError("Production server did not respond at /health")
        assert body == b'{"status":"ok"}'
    finally:
        if server.poll() is None:
            server.terminate()
        server.communicate(timeout=5)
