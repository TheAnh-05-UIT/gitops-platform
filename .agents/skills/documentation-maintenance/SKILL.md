---
name: documentation-maintenance
description: Reconcile architecture notes, project state, roadmap, ADRs and runbooks against source changes and verified delivery evidence.
---

# Documentation maintenance

Take the change, documentation and source or runtime evidence as inputs. Return updated references and remaining evidence gaps.

1. Use [architecture](../../../docs/ARCHITECTURE.md) for contracts, [project state](../../../docs/PROJECT_STATE.md) for evidence, [testing](../../../docs/TESTING.md) for commands and [roadmap](../../../docs/ROADMAP.md) for planned work.
2. Check the relevant source before updating claims. Start with `portal/github_client.py` for placement, `gitops-platform-config/argocd/applications/workload-api.yaml` for desired state, or `gitops-platform-workload-api/.github/workflows/ci.yml` for publication. Record material decisions and consequences under `docs/decisions/`.
3. Check commands from their stated root and verify relative links. Describe conflicts by revision and scope, and keep runtime and remote unknowns explicit.
