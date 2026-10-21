from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


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
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if server.poll() is not None:
                _, error = server.communicate()
                raise AssertionError(f"Production server exited before becoming healthy:\n{error}")

            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    assert response.status == 200
                    assert response.read() == b'{"status":"ok"}'
                    return
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(0.1)

        raise AssertionError("Production server did not respond at /health")
    finally:
        if server.poll() is None:
            server.terminate()
        server.communicate(timeout=5)
