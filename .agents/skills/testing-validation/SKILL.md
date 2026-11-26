---
name: testing-validation
description: Select and execute local regression, smoke, optimizer, Helm policy and cross-repository contract validation before reporting a change.
---

# Testing and validation

Take requested behavior, affected files and available tooling as inputs. Return executed commands, outcomes and uncovered acceptance criteria.

1. Map tests to behavior using [testing](../../../docs/TESTING.md). Use `portal/app.py` and `optimizer/ilp.py` for portal and solver cases, `gitops-platform-config/scripts/check_deployment_policies.py` for manifests and `gitops-platform-workload-api/.github/workflows/ci.yml` for container smoke.
2. Reproduce bugs before implementation. Cover expected and failed outcomes. Use fixtures or mocks for external GitHub writes. Verify the chart values, image, health route, labels and resource units across checkouts when affected.
3. Run the commands, inspect exit codes and review the final diff. If a tool or authorized environment is unavailable, run independent checks and record the exact uncovered behavior.
