---
name: cicd-engineering
description: Change or review GitHub Actions validation, container builds, Trivy scans, GHCR publication and cross-repository image promotion.
---

# CI and image promotion

Take triggers, source and target refs, intended image and permission requirements as inputs. Return workflow verification, publication and promotion gates, and a retry or recovery path.

1. Read `gitops-platform-workload-api/.github/workflows/ci.yml` and `gitops-platform-config/.github/workflows/validate-config.yml`. Review `portal/github_client.py` when promotion may race with placement.
2. Check triggers and minimum permissions. Require HTTP smoke and the security scan before publication and verify the published image before promotion. Preserve the full SHA contract or coordinate migration.
3. Check retry behavior around one source revision and one intended promotion. Verify duplicate requests and concurrent placement edits. Keep credentials out of logs and untrusted data out of shell interpolation.
4. Validate workflow behavior with local build, smoke, scanning and config checks as available. Report unavailable runner or registry checks. Run remote publication or open a PR only with explicit authorization.
