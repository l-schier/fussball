from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from urllib.error import HTTPError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

API_VERSION = "2026-03-10"
API_ROOT = "https://api.github.com"
PACKAGE_NAME = "fussball"


def candidate_version_ids(versions: Iterable[dict], pull_request: int) -> list[int]:
    """Return only versions tagged exclusively for this PR, protecting production tags."""
    prefix = f"pr-{pull_request}-"
    candidate_ids = []
    for version in versions:
        tags = version.get("metadata", {}).get("container", {}).get("tags", [])
        if not any(tag.startswith(prefix) for tag in tags):
            continue
        if not all(tag.startswith(prefix) for tag in tags):
            raise ValueError(f"Refusing to delete version {version['id']}: non-candidate tags are present: {tags!r}.")
        candidate_ids.append(version["id"])
    return candidate_ids


def _request(url: str, token: str, method: str = "GET"):
    return Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
        },
        method=method,
    )


def _list_versions(endpoint: str, token: str) -> list[dict]:
    versions = []
    while endpoint:
        try:
            with urlopen(_request(endpoint, token), timeout=30) as response:
                versions.extend(json.load(response))
                links = response.headers.get("Link", "")
        except HTTPError as error:
            if error.code == 404 and not versions:
                return []
            raise

        endpoint = next(
            (
                urljoin(endpoint, match.group(1))
                for link in links.split(",")
                if 'rel="next"' in link
                if (match := re.search(r"<([^>]+)>", link))
            ),
            "",
        )
    return versions


def main() -> None:
    owner = quote(os.environ["GH_OWNER"], safe="")
    owner_type = os.environ["GH_OWNER_TYPE"].lower()
    pull_request = int(os.environ["GH_PR_NUMBER"])
    token = os.environ["GH_TOKEN"]
    if owner_type == "organization":
        namespace = f"orgs/{owner}"
    elif owner_type == "user":
        namespace = f"users/{owner}"
    else:
        raise ValueError(f"Unsupported GitHub repository owner type: {owner_type!r}.")

    package_endpoint = f"{API_ROOT}/{namespace}/packages/container/{PACKAGE_NAME}"
    versions = _list_versions(f"{package_endpoint}/versions?per_page=100", token)
    version_ids = candidate_version_ids(versions, pull_request)
    for version_id in version_ids:
        url = f"{package_endpoint}/versions/{version_id}"
        try:
            with urlopen(_request(url, token, method="DELETE"), timeout=30):
                print(f"Deleted candidate package version {version_id}.")
        except HTTPError as error:
            if error.code != 404:
                raise
            print(f"Candidate package version {version_id} was already removed.")

    if not version_ids:
        print(f"No candidate versions found for PR #{pull_request}.")


if __name__ == "__main__":
    main()
