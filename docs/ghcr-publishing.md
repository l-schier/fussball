# GHCR image publishing

The `publish-images` workflow publishes `ghcr.io/l-schier/fussball` without deploying or restarting the live stack:

- Add the `build-image` label to a pull request targeting `main` to publish one candidate tagged `pr-<number>-<head-sha>`. A failed publish leaves the label in place. A successful publish removes it; re-add it to request a build for a later commit.
- Candidate publishing is limited to pull requests whose head branch is in this repository. Fork pull requests are intentionally skipped because candidate publishing needs a package-write token and must not build untrusted fork code with that token.
- Merging or closing a same-repository pull request removes its candidate package versions. Cleanup uses trusted base-branch code and refuses to delete a version if it has any non-candidate tags.
- A push to `main` publishes `latest` and the full commit SHA as production tags.

Before requesting a candidate, ensure the repository has a `build-image` label. The package is linked to the repository by its OCI source label, which grants the repository's workflows access to it. GHCR does not inherit package visibility from the repository, and `GITHUB_TOKEN` cannot change visibility. The first publish creates a private package by default, so after that publish open the package settings and set visibility to match the repository. This repository is public; set the package to public. GHCR does not allow a public package to be made private again, so verify the intended visibility before changing it.
