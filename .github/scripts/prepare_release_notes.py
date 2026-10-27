from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+].*)?$")
BREAKING_CHANGES_HEADING = "### Breaking Changes"
UPGRADE_NOTES_HEADING = "### Upgrade notes"


def _major(version: str) -> int:
    match = SEMVER.fullmatch(version)
    if match is None:
        raise ValueError(f"Expected a SemVer version, got {version!r}.")
    return int(match.group(1))


def prepare_release_notes(
    version: str,
    previous_version: str,
    release_notes: str,
) -> tuple[bool, str]:
    """Rename detailed breaking-change notes for a major release, failing if absent."""
    is_major = _major(version) > _major(previous_version)
    if not is_major:
        return False, release_notes

    if BREAKING_CHANGES_HEADING not in release_notes:
        raise ValueError(
            "A major release must include a BREAKING CHANGE footer with manually written "
            "upgrade notes before the release can be created."
        )

    breaking_notes = release_notes.split(BREAKING_CHANGES_HEADING, maxsplit=1)[1]
    breaking_notes = breaking_notes.split("\n### ", maxsplit=1)[0].strip()
    if not breaking_notes:
        raise ValueError("The major release Upgrade notes section cannot be empty.")

    return True, release_notes.replace(
        BREAKING_CHANGES_HEADING,
        UPGRADE_NOTES_HEADING,
        1,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--preflight",
        action="store_true",
        help="validate previewed notes and write the major-release result to GITHUB_OUTPUT",
    )
    mode.add_argument(
        "--output",
        type=Path,
        help="write normalized release notes to this path after the release is created",
    )
    args = parser.parse_args()

    is_major, notes = prepare_release_notes(
        os.environ["VERSION"],
        os.environ["PREVIOUS_VERSION"],
        os.environ["RELEASE_NOTES"],
    )
    if args.preflight:
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"is_major={str(is_major).lower()}\n")
    else:
        args.output.write_text(notes, encoding="utf-8")


if __name__ == "__main__":
    main()
