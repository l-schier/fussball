from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator

import pytest

from tests.health_polling import poll_health_endpoint

DOCKER = shutil.which("docker")
IMAGE = f"fussball-container-test:{uuid.uuid4().hex}"


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    assert DOCKER is not None
    return subprocess.run(
        [DOCKER, *args],
        check=check,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _wait_for_health(container: str, timeout: float = 60) -> str:
    port = docker("port", container, "8000/tcp").stdout.strip().rsplit(":", 1)[-1]
    url = f"http://127.0.0.1:{port}/health"
    body = poll_health_endpoint(url, timeout=timeout, interval=0.25)
    if body is not None:
        return body.decode()
    logs = docker("logs", container, check=False).stdout
    raise AssertionError(f"Container did not become healthy. Logs:\n{logs}")


@pytest.fixture(scope="session", autouse=True)
def production_image() -> Iterator[None]:
    if DOCKER is None:
        pytest.skip("Docker CLI is required for production-container tests")
    info = docker("info", check=False)
    if info.returncode:
        pytest.skip("A running Docker daemon is required for production-container tests")

    docker("build", "--tag", IMAGE, ".")
    yield
    docker("image", "rm", IMAGE, check=False)


@pytest.fixture
def data_volume() -> Iterator[str]:
    name = f"fussball-test-{uuid.uuid4().hex}"
    docker("volume", "create", name)
    try:
        yield name
    finally:
        docker("volume", "rm", "--force", name, check=False)


def _start(container: str, volume: str) -> None:
    docker(
        "run",
        "--detach",
        "--name",
        container,
        "--publish",
        "127.0.0.1::8000",
        "--mount",
        f"type=volume,source={volume},target=/app/data",
        IMAGE,
    )


def _remove(container: str) -> None:
    docker("rm", "--force", container, check=False)


def test_health_endpoint_responds_from_production_container(data_volume: str) -> None:
    container = f"fussball-health-{uuid.uuid4().hex}"
    try:
        _start(container, data_volume)
        assert json.loads(_wait_for_health(container)) == {"status": "ok"}
    finally:
        _remove(container)


def test_startup_applies_current_migration_head(data_volume: str) -> None:
    container = f"fussball-migrations-{uuid.uuid4().hex}"
    try:
        _start(container, data_volume)
        _wait_for_health(container)
        result = docker(
            "exec",
            container,
            "python",
            "-c",
            "import sqlite3; db=sqlite3.connect('/app/data/database.db'); "
            "print(db.execute('select version_num from alembic_version').fetchone()[0]); "
            "print(db.execute(\"select name from sqlite_master where type='table' and name='player'\").fetchone()[0])",
        )
        assert result.stdout.splitlines() == ["8cb434f843c9", "player"]
    finally:
        _remove(container)


def test_database_contents_survive_container_replacement(data_volume: str) -> None:
    first_container = f"fussball-persistence-a-{uuid.uuid4().hex}"
    replacement = f"fussball-persistence-b-{uuid.uuid4().hex}"
    player_id = "00000000-0000-0000-0000-000000000013"
    try:
        _start(first_container, data_volume)
        _wait_for_health(first_container)
        docker(
            "exec",
            first_container,
            "python",
            "-c",
            "import sqlite3; db=sqlite3.connect('/app/data/database.db'); "
            f"db.execute(\"insert into player (id, name, active, created_at) values ('{player_id}', 'saved-player', 1, '2026-10-21')\"); db.commit()",
        )
        _remove(first_container)

        _start(replacement, data_volume)
        _wait_for_health(replacement)
        result = docker(
            "exec",
            replacement,
            "python",
            "-c",
            f"import sqlite3; print(sqlite3.connect('/app/data/database.db').execute(\"select name from player where id='{player_id}'\").fetchone()[0])",
        )
        assert result.stdout.strip() == "saved-player"
    finally:
        _remove(first_container)
        _remove(replacement)


def test_failed_migration_prevents_application_start(data_volume: str) -> None:
    container = f"fussball-migration-failure-{uuid.uuid4().hex}"
    # A directory at the database file path makes SQLite fail during Alembic's
    # startup migration without changing the image or its migration scripts.
    docker(
        "run",
        "--rm",
        "--user",
        "0",
        "--mount",
        f"type=volume,source={data_volume},target=/app/data",
        "--entrypoint",
        "python",
        IMAGE,
        "-c",
        "import os; os.mkdir('/app/data/database.db'); os.chmod('/app/data/database.db', 0o777)",
    )
    try:
        docker(
            "run",
            "--detach",
            "--name",
            container,
            "--mount",
            f"type=volume,source={data_volume},target=/app/data",
            IMAGE,
            check=False,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = docker("inspect", "--format", "{{.State.Status}}", container, check=False)
            if state.stdout.strip() == "exited":
                break
            time.sleep(0.25)
        else:
            raise AssertionError("Container kept running despite the failed startup migration")

        logs = docker("logs", container, check=False).stdout + docker("logs", container, check=False).stderr
        assert "unable to open database file" in logs.lower()
        assert docker("inspect", "--format", "{{.State.ExitCode}}", container).stdout.strip() != "0"
    finally:
        _remove(container)
