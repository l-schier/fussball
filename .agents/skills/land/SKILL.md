---
name: land
description: >-
  Land changes in the Fussball repository only when the user explicitly requests
  that they be landed. Do not invoke for review, preparation, testing, or skill
  installation alone.
disable-model-invocation: true
metadata:
  delta-action: land
---

# Land changes

## Applicability

Use this procedure only for an explicit request to land changes, such as a request to merge the current work into `main`. Invocation for that purpose is authorization to complete the landing; do not ask again whether the user wants the PR merged. Do not use administrator bypasses to evade repository protections.

This procedure targets `l-schier/fussball` on `origin/main`. The configured `upstream` remote is `Declow/fussball`; never publish this work to that remote unless the user explicitly changes the destination. Confirm the configured remotes before acting. The repository's issue-tracker guidance uses GitHub CLI and derives the repository from its remotes (`docs/agents/issue-tracker.md`).

## Prepare the change

1. Check the working tree, current branch, recent commits, remotes, and the diff against the intended base. Confirm that the requested changes—not unrelated work—are what will be landed.
2. Preserve all existing changes. Do not reset, discard, or stage the whole working tree. If there are uncommitted changes, separate task-scoped changes from unrelated edits and commit only the intended changes. If that cannot be done safely, stop and ask. If the work is on `main`, create an `integration/<short-topic>` branch before committing; otherwise keep the existing feature/integration branch.
3. Fetch the current `main` from `origin` and merge it into the work branch without rewriting published history:

   ```sh
   git fetch origin main
   git merge --no-edit origin/main
   ```

   Source: `docs/agents/issue-tracker.md` identifies the repository from its remotes; `.github/workflows/publish-images.yml` uses `main` as the PR target. Do not rebase or force-push an already-published branch.
4. Resolve merge conflicts automatically only when the correct combined result is clear and preserves unrelated changes. If the intended result is ambiguous, stop and ask rather than guessing. After resolving conflicts, complete the merge non-interactively, then inspect the complete resulting diff.

## Validate and review

Run the project test suite before publishing the branch:

```sh
uv run --group dev pytest -q
```

Source: `pyproject.toml` declares `pytest` in the `dev` dependency group; tests live under `tests/`.

For Docker or Compose changes, also validate and build the application service:

```sh
docker compose config --format json
docker compose build app
```

Source: `compose.yaml` defines the `app` service; `compose.override.yaml` selects the local image build; `Dockerfile` defines the image; `tests/test_dockge_compose.py` exercises Compose configuration. If Docker is unavailable for a Docker-related change, stop and report the verification blocker. Do not claim a check passed if it was skipped or could not run.

The production persistent volume is `fussball-data`, as specified by `docs/deployment.md` and `tests/test_dockge_compose.py`; keep `compose.yaml` aligned with that contract. The local override must use a distinct `fussball-data-dev` volume so local containers cannot attach to production data (`compose.override.yaml`). If these files diverge, re-evaluate against the user's confirmed production-volume choice and fix only related, clearly scoped mismatches. Never skip, weaken, or silently waive a failing test.

Review the exact final diff against both the requested behavior/specification and the repository's standards. Address in-scope findings and repeat the review until there are no unresolved findings. This review must be fresh after syncing `main`; any conflict resolution or subsequent code change invalidates it and requires a complete review restart. Record the reviewed commit SHA and verify it remains the PR head before merging.

## Pull request and repository checks

`main` is protected and requires a PR; use the GitHub pull-request workflow rather than pushing to `main`. Recent PRs #16, #30, and #31 were merged with merge commits, so use the merge-commit strategy. GitHub currently deletes remote head branches after merge. Check live branch protection and repository settings each time; current settings are not a permanent guarantee. The present configuration enforces protection for administrators, has no required status-check contexts, requires zero approvals, has no `CODEOWNERS` file, and does not require signed commits. If any rule changes, obey the current rule and wait for required human reviews; never use `--admin` to bypass it. The PR target is `main` (`.github/workflows/publish-images.yml`); the GitHub CLI is the repository's configured issue-tracker tool (`docs/agents/issue-tracker.md`).

Require every individual commit introduced by a PR to use a Conventional Commit subject; keep merge commits and do not rely on the generated merge-commit message for release classification. Use `feat` for additive user-facing functionality, `fix` or `perf` for compatible corrections and performance improvements, and `docs`, `chore`, `test`, `ci`, or non-user-visible `refactor` for changes that should not release. Classify user-visible refactors as `feat` or `fix`. Mark breaking changes with `!` and/or a `BREAKING CHANGE:` footer. For any breaking release, include a `BREAKING CHANGE:` paragraph with manually written upgrade notes covering data/configuration risks, migration steps, and behavior changes; explicitly state when no special upgrade steps are required. The release workflow uses that text for the major release's **Upgrade notes** section and blocks a major release if it is missing.

Publish only the work branch to `origin`, then create or update a PR targeting `main`. For a new PR, use a command of this form:

```sh
gh pr create --base main --head "$branch" --title "$title" --body "$body"
```

There is no PR template or contribution guide; include a concise summary, relevant issue/spec references when applicable, and the verification actually completed. Do not change issue state unless the user or the issue workflow requires it. Check live branch protection with `gh api repos/l-schier/fussball/branches/main/protection`, then verify that:

- The PR head SHA is exactly the reviewed and tested commit.
- Every required check for that SHA has completed successfully. Use `gh pr checks "$pr" --required` to inspect required checks and `gh pr checks "$pr" --watch` to wait for reported checks. Pending, failing, missing, or unverifiable required checks block the merge. If no checks are required, confirm that from the live settings rather than treating absent checks as a pass.
- Any required review approvals and conversation resolutions are satisfied.
- `main` has not advanced since the final sync. If it has, merge the new `origin/main` tip into the work branch and restart the tests and review.

The repository has no general test workflow. `publish-images` only builds an image after Python Semantic Release creates a release; PRs and ordinary non-release merges do not publish images (`.github/workflows/publish-images.yml`, `docs/ghcr-publishing.md`). Do not add candidate-image labels to manufacture a check; candidate publishing has been retired.

A release-worthy merge to `main` automatically creates a GitHub Release and publishes GHCR SemVer aliases (`X.Y.Z`, `X.Y`, `X`, and `latest`); it does not deploy the live stack (`.github/workflows/publish-images.yml`, `docs/ghcr-publishing.md`, `docs/deployment.md`). Before the merge, disclose this side effect and obtain explicit authorization for release and package publication if the user's landing request does not already authorize it. Do not perform a live deployment or change package visibility. The release workflow also needs permission to push the version-stamp commit to protected `main`; confirm the token/branch-protection configuration without bypassing repository protections.

## Merge and confirm

Once the PR is current, the final review is clean, all required checks and reviews pass, and any separate publication authorization is satisfied, merge it using the merge-commit strategy:

```sh
gh pr merge "$pr" --merge
```

Source: recent merged PRs #16, #30, and #31 use merge commits; the repository currently permits merge commits. Do not push directly to `main` or use the admin bypass.

Afterward, verify the PR is merged and its merge commit is an ancestor of the latest `origin/main`. Confirm the main-branch image-publishing workflow for that merge commit completed successfully; if it failed, report that the code landed but publication failed, and do not attempt deployment or rollback without authorization. If any required condition blocks the merge, leave the changes unlanded and explain the blocker rather than claiming success.
