from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

COMPOSE_FILE = Path(__file__).resolve().parents[1] / "compose.yaml"
LOCAL_COMPOSE_OVERRIDE = Path(__file__).resolve().parents[1] / "compose.override.yaml"


def test_dockge_stack_persists_sqlite_data_and_defaults_to_latest() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text())

    assert compose["services"]["app"]["image"] == "ghcr.io/l-schier/fussball:${IMAGE_TAG:-latest}"
    assert compose["services"]["app"]["volumes"] == ["fussball-data:/app/data"]
    assert compose["volumes"]["fussball-data"]["name"] == "fussball-data"


def test_local_compose_override_builds_a_local_image() -> None:
    compose = yaml.safe_load(LOCAL_COMPOSE_OVERRIDE.read_text())
    app = compose["services"]["app"]

    assert app["image"] == "fussball:local"
    assert app["build"] == {"context": ".", "dockerfile": "Dockerfile"}
    assert app["pull_policy"] == "build"
    assert app["volumes"] == ["fussball-data-dev:/app/data"]
    assert compose["volumes"]["fussball-data-dev"]["name"] == "fussball-data-dev"


def test_compose_renders_selected_image_tag_and_stable_volume_name() -> None:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker Compose is required to render the Dockge stack")

    available = subprocess.run([docker, "compose", "version"], capture_output=True, text=True, check=False)
    if available.returncode:
        pytest.skip("Docker Compose is required to render the Dockge stack")

    environment = os.environ.copy()
    environment["IMAGE_TAG"] = "0123456789abcdef"
    result = subprocess.run(
        [docker, "compose", "--file", str(COMPOSE_FILE), "config", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
        env=environment,
    )
    rendered = json.loads(result.stdout)

    assert rendered["services"]["app"]["image"] == "ghcr.io/l-schier/fussball:0123456789abcdef"
    assert rendered["services"]["app"]["volumes"][0]["target"] == "/app/data"
    assert rendered["services"]["app"]["volumes"][0]["source"] == "fussball-data"
    assert rendered["volumes"]["fussball-data"]["name"] == "fussball-data"
