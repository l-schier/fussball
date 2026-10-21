from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
CLEANUP_SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "cleanup_candidate_images.py"


def test_production_image_publishes_latest_and_commit_tags_on_main() -> None:
    workflow = yaml.load((WORKFLOWS / "publish-images.yml").read_text(), Loader=yaml.BaseLoader)

    assert workflow["on"]["push"]["branches"] == ["main"]
    publish = workflow["jobs"]["publish-production"]
    assert publish["permissions"] == {"contents": "read", "packages": "write"}
    build = next(step for step in publish["steps"] if step.get("id") == "build")
    assert "latest" in build["with"]["tags"]
    assert "github.sha" in build["with"]["tags"]
    assert "Production image" in build["with"]["labels"]


def test_candidate_image_is_one_shot_and_limited_to_same_repository_pull_requests() -> None:
    workflow = yaml.load((WORKFLOWS / "publish-images.yml").read_text(), Loader=yaml.BaseLoader)

    assert workflow["on"]["pull_request"]["types"] == ["labeled"]
    assert "pull_request_target" not in workflow["on"]
    candidate = workflow["jobs"]["publish-candidate"]
    assert "build-image" in candidate["if"]
    assert "head.repo.full_name == github.repository" in candidate["if"]
    assert candidate["permissions"] == {"contents": "read", "packages": "write"}
    checkout = next(step for step in candidate["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert "pull_request.head.sha" in checkout["with"]["ref"]
    build = next(step for step in candidate["steps"] if step.get("id") == "build")
    assert "pull_request.number" in build["with"]["tags"]
    assert "pull_request.head.sha" in build["with"]["tags"]
    assert "Candidate image for PR" in build["with"]["labels"]

    remove_label = workflow["jobs"]["remove-build-label"]
    assert remove_label["needs"] == "publish-candidate"
    assert "needs.publish-candidate.result == 'success'" in remove_label["if"]
    assert remove_label["permissions"] == {"issues": "write"}


def test_closed_pull_request_cleanup_deletes_only_its_candidate_versions() -> None:
    workflow = yaml.load((WORKFLOWS / "cleanup-candidates.yml").read_text(), Loader=yaml.BaseLoader)

    assert workflow["on"]["pull_request_target"]["types"] == ["closed"]
    cleanup = workflow["jobs"]["delete-candidate-images"]
    assert "head.repo.full_name == github.repository" in cleanup["if"]
    assert cleanup["permissions"] == {"contents": "read", "packages": "write"}
    checkout = next(step for step in cleanup["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.base.ref }}"
    assert checkout["with"]["persist-credentials"] == "false"
    assert any("cleanup_candidate_images.py" in step.get("run", "") for step in cleanup["steps"])
    compile(CLEANUP_SCRIPT.read_text(), str(CLEANUP_SCRIPT), "exec")


def test_candidate_cleanup_selects_only_candidate_versions_for_the_closed_pull_request() -> None:
    spec = importlib.util.spec_from_file_location("cleanup_candidate_images", CLEANUP_SCRIPT)
    assert spec is not None and spec.loader is not None
    cleanup_script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cleanup_script)

    versions = [
        {"id": 101, "metadata": {"container": {"tags": ["pr-42-abcdef"]}}},
        {"id": 102, "metadata": {"container": {"tags": ["pr-43-abcdef"]}}},
        {"id": 103, "metadata": {"container": {"tags": ["latest", "0123456789abcdef"]}}},
    ]

    assert cleanup_script.candidate_version_ids(versions, 42) == [101]
    with pytest.raises(ValueError, match="non-candidate tags"):
        cleanup_script.candidate_version_ids(
            [{"id": 104, "metadata": {"container": {"tags": ["pr-42-abcdef", "latest"]}}}],
            42,
        )


def test_workflow_actions_are_pinned_and_visibility_constraint_is_explicit() -> None:
    workflows = [yaml.load(path.read_text(), Loader=yaml.BaseLoader) for path in WORKFLOWS.glob("*.yml")]

    for workflow in workflows:
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    assert re.fullmatch(r"[^@]+@[0-9a-f]{40}(?:\s+# v\d+)?", step["uses"])

    publishing = (WORKFLOWS / "publish-images.yml").read_text()
    assert "GHCR package visibility is separate" in publishing
    assert "Set package visibility to match the repository" in publishing
