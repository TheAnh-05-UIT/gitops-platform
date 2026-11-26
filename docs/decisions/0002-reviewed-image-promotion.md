# ADR 0002. Reviewed image promotion with a dedicated GitHub App

**Status** Proposed for P0.3 approval.

## Context

Workload CI publishes to GHCR and config `main` controls Argo CD. The v2 promotion and revert are recorded in Git, and the live rollout outcome and reason for the revert are unknown. A publication is artifact evidence. Deployment requires separate intent and review. See [project state](../PROJECT_STATE.md).

## Options

| Option | Security and operations |
| --- | --- |
| Dedicated GitHub App installation | Short-lived, repository- and permission-scoped token, distinct bot identity and owner-managed lifecycle. Requires a maintained signing key, installation, rotation, a protected workflow and verified rules. |
| Fine-grained personal access token | Can limit permissions and selected repos and has lower setup overhead. Ties production automation to a user and the user's access and expiration lifecycle. Use only as an explicitly approved, time-bounded fallback with equivalent review gates and a rotation owner. |
| Argo CD Image Updater | Can observe a registry and supports Git write-back and PR mode. Adds a controller plus registry and repository credentials. The project would still need to integrate build provenance, explicit approval generations and rollback tombstones to prevent a registry-discovered image from undoing a rollback. |

The options are based on [GitHub App installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app), [GitHub token types](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) and [Argo CD Image Updater write-back](https://argocd-image-updater.readthedocs.io/en/stable/basics/update-methods/).

## Decision

Recommend a dedicated GitHub App installed on the config repo, invoked by a protected, explicitly dispatched workload workflow after successful publication and reviewed config admission. Its authority is to propose an image-only PR. Strict config checks and independent human review govern the merge. Config tracks the active request generation and blocked candidates, including the historical v2 source SHA. Review the [promotion contract](../IMAGE_PROMOTION.md) for exact checks and exception handling.

Preserve the full-SHA tag Helm contract for the first implementation and verify its digest at publication, proposal and merge. Plan digest-pinned desired state as a subsequent chart migration.

## Consequences

The release has two distinct human decisions: authorize the artifact and merge the tested desired state. Maintainers must operate the App key, evidence retention and rollback records. Protected config checks are a dependency for enabling bot writes. Tag-based deployment retains registry reassignability at pull time until digest pinning. Missing access, evidence or owner approval keeps P0.3 in design or read-only testing.
