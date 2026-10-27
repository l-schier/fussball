# GHCR image publishing

The `publish-images` workflow publishes `ghcr.io/l-schier/fussball` without deploying or restarting the live stack:

- A push to `main` runs Python Semantic Release against the Conventional Commit messages since the last version tag. No-release changes do not build or publish a container image.
- When a release is created, the workflow builds the version-stamped commit and publishes the exact `X.Y.Z`, `X.Y`, `X`, and `latest` tags. It does not publish commit-SHA or pull-request candidate tags.
- Git tags use `vX.Y.Z`. The image's short aliases and `latest` advance only with a release.
- The cleanup workflow remains to remove candidate package versions from before candidate publishing was retired. It only deletes versions tagged exclusively for the closed PR.
- Image publication does not deploy or restart the live stack; operators choose when to pull and deploy an image in Dockge.

Before enabling the release workflow, complete the historical backfill in [issue #44](https://github.com/l-schier/fussball/issues/44), including the `v3.4.1` tag. The workflow verifies that this tag points to PR #38's merge commit (`94c8403275e2e8f34314d30e83d6d5b40b8f99c6`) and is an ancestor of the main commit before calculating a release.

The release workflow must be able to push the version-stamp commit and Git tag to protected `main`. If repository rules do not allow `GITHUB_TOKEN` to do that, configure the `RELEASE_TOKEN` Actions secret with a token authorized by the existing branch protection policy; do not bypass protections. This workflow publishes only the container image and GitHub Release, not a Python package.

The package is linked to the repository by its OCI source label, which grants the repository's workflows access to it. GHCR does not inherit package visibility from the repository, and `GITHUB_TOKEN` cannot change visibility. The first publish creates a private package by default, so after that publish open the package settings and set visibility to match the repository. This repository is public; set the package to public. GHCR does not allow a public package to be made private again, so verify the intended visibility before changing it.
