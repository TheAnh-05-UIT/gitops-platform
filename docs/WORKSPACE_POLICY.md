# Workspace engineering policy

Build a production-like internal developer platform for cost-aware workload placement. This directory coordinates three independent Git repositories. Keep it outside Git and preserve the repository boundaries.

| Repository | Owns |
| --- | --- |
| `gitops-platform/` | Shared engineering documentation and skills, Flask Developer Portal, placement models and datasets, benchmarks, future infrastructure automation |
| `gitops-platform-config/` | Workload desired state, Helm chart, deployment policy checks, and Argo CD Application |
| `gitops-platform-workload-api/` | Flask workload, Gunicorn container, HTTP smoke checks, and GHCR publication |

The shared contract is the config repository's `main:apps/workload-api/values.yaml`. The portal proposes `replicaCount` and `nodeSelector.idp.example.com/region` through a PR. The workload workflow publishes a full-commit-SHA GHCR tag. Image promotion updates the config image reference through review. The chart consumes workload port `8080` and `GET /healthz`. Read the [architecture and contracts](ARCHITECTURE.md) before changing these interfaces.

## Required workflow

1. Read this file and the owning repository's `AGENTS.md`. Check Git status in each affected checkout and identify existing edits. Explicitly open only the relevant `.agents/skills/*/SKILL.md` files from the Platform repository. Automatic discovery remains unverified.
2. Identify the root cause, owner, and potential impact on both sibling repositories. Check the affected API, image, configuration, and deployment contracts. Record a short plan. Resolve material uncertainty using source and tests. Ask the user when unresolved choices change scope, compatibility, authorization, or risk.
3. Make the smallest complete change consistent with existing conventions. Preserve compatibility and user changes. Review migration order and rollback before breaking changes. Obtain authorization before changing dependencies or materially changing behavior outside the task.
4. Run the relevant [validation](TESTING.md), review diffs across affected repositories, and update documentation for material changes to architecture, interfaces, procedures, or project state.

## Engineering rules

- Apply the [engineering standards](ENGINEERING_STANDARDS.md) and [security policy](SECURITY.md). Validate external inputs and permissions. Keep credentials, state, plans and sensitive logs private.
- Route changes to managed deployments through reviewed Git configuration. Preserve rollback and verify chart rendering, image compatibility and scheduling. Provisioning, destructive operations and live deployment require explicit authorization.
- Preserve unrelated edits. Avoid destructive Git operations, including force push, hard reset and clean. Commit, push, open a remote PR, approve, merge or deploy only with explicit authorization. Use the [development workflow](DEVELOPMENT_WORKFLOW.md) and suggest Conventional Commit messages.
- A task is done when its requirements are met, intended behavior and contracts are checked, the final diff is scoped, security and sibling impacts are reviewed, and documentation is current. Report executed commands and outcomes, remaining risks and exact blockers. Support claims with evidence.

Use [project state](PROJECT_STATE.md) for the verified baseline and [roadmap](ROADMAP.md) for sequencing. Platform owns this policy and the canonical copies of shared docs and skills. Preserve the non-Git workspace parent and the three independent repositories.
