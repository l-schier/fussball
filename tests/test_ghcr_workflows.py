from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from tomllib import loads

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = PROJECT_ROOT / ".github" / "workflows"
CLEANUP_SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "cleanup_candidate_images.py"
RELEASE_NOTES_SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "prepare_release_notes.py"


def test_production_image_is_published_only_after_a_semantic_release() -> None:
    workflow = yaml.load((WORKFLOWS / "publish-images.yml").read_text(), Loader=yaml.BaseLoader)

    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "pull_request" not in workflow["on"]
    assert "publish-candidate" not in workflow["jobs"]

    release = workflow["jobs"]["release"]
    assert release["permissions"] == {"contents": "read", "id-token": "write"}
    app_token = next(step for step in release["steps"] if step.get("id") == "release-token")
    assert app_token["uses"] == "actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510"
    assert app_token["with"] == {
        "client-id": "${{ vars.RELEASE_APP_CLIENT_ID }}",
        "private-key": "${{ secrets.RELEASE_APP_PRIVATE_KEY }}",
        "permission-contents": "write",
    }
    preview = next(step for step in release["steps"] if step.get("id") == "preview")
    assert preview["with"]["github_token"] == "${{ steps.release-token.outputs.token }}"
    assert preview["with"]["no_operation_mode"] == "true"
    assert preview["with"]["changelog"] == "false"
    baseline_check = next(step for step in release["steps"] if "historical release baseline" in step.get("name", ""))["run"]
    assert "v3.4.1" in baseline_check
    assert "94c8403275e2e8f34314d30e83d6d5b40b8f99c6" in baseline_check
    release_action = next(step for step in release["steps"] if step.get("id") == "release")
    assert release_action["with"]["github_token"] == "${{ steps.release-token.outputs.token }}"
    assert release_action["if"] == "steps.preview.outputs.released == 'true'"
    release_notes = next(step for step in release["steps"] if step.get("name") == "Publish major release Upgrade notes")
    assert release_notes["env"]["GH_TOKEN"] == "${{ steps.release-token.outputs.token }}"

    publish = workflow["jobs"]["publish-production"]
    assert publish["needs"] == "release"
    assert publish["if"] == "needs.release.outputs.released == 'true'"
    assert publish["permissions"] == {"contents": "read", "packages": "write"}
    registry_login = next(step for step in publish["steps"] if step.get("name") == "Log in to GitHub Container Registry")
    assert registry_login["with"]["password"] == "${{ secrets.GITHUB_TOKEN }}"
    checkout = next(step for step in publish["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "${{ needs.release.outputs.commit_sha }}"
    assert checkout["with"]["persist-credentials"] == "false"

    metadata = next(step for step in publish["steps"] if step.get("id") == "metadata")
    tags = metadata["with"]["tags"]
    assert "pattern={{version}}" in tags
    assert "pattern={{major}}.{{minor}}" in tags
    assert "pattern={{major}}" in tags
    assert "type=raw,value=latest" in tags
    assert "type=sha" not in tags

    build = next(step for step in publish["steps"] if step.get("id") == "build")
    assert "github.sha" not in build["with"]["tags"]
    assert "Production release image" in build["with"]["labels"]


def test_semantic_release_config_matches_the_backfilled_version_and_bump_policy() -> None:
    project = loads((PROJECT_ROOT / "pyproject.toml").read_text())
    release = project["tool"]["semantic_release"]
    commit_rules = release["commit_parser_options"]

    assert project["project"]["version"] == "3.5.0"
    assert release["tag_format"] == "v{version}"
    assert release["version_toml"] == ["pyproject.toml:project.version"]
    build_commands = [line.strip() for line in release["build_command"].splitlines() if line.strip()]
    assert build_commands == [
        "python -m pip install uv",
        'uv lock --upgrade-package "$PACKAGE_NAME"',
        "git add uv.lock",
    ]
    assert commit_rules["minor_tags"] == ["feat"]
    assert commit_rules["patch_tags"] == ["fix", "perf"]
    assert commit_rules["default_bump_level"] == 0

    lock = loads((PROJECT_ROOT / "uv.lock").read_text())
    app_package = next(package for package in lock["package"] if package["name"] == "fussball")
    assert app_package["version"] == project["project"]["version"]


def test_major_release_notes_require_manual_breaking_change_details() -> None:
    spec = importlib.util.spec_from_file_location("prepare_release_notes", RELEASE_NOTES_SCRIPT)
    assert spec is not None and spec.loader is not None
    release_notes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release_notes)

    notes = "## v3.0.0\n\n### Breaking Changes\n\n- Move the database to the new persistent volume.\n"
    is_major, updated = release_notes.prepare_release_notes("3.0.0", "2.4.0", notes)
    assert is_major is True
    assert "### Upgrade notes" in updated
    assert "### Breaking Changes" not in updated

    with pytest.raises(ValueError, match="BREAKING CHANGE footer"):
        release_notes.prepare_release_notes("3.0.0", "2.4.0", "## v3.0.0\n\n### Features\n")

    is_major, unchanged = release_notes.prepare_release_notes("3.4.2", "3.4.1", notes)
    assert is_major is False
    assert unchanged == notes


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
