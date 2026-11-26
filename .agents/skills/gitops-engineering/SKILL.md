---
name: gitops-engineering
description: Review or change GitOps desired state, Helm rendering, Kubernetes workload settings, Argo CD promotion, reconciliation and rollback.
---

# GitOps and Kubernetes engineering

Take config revision, chart values, image and environment as inputs. Return a reviewed manifest diff, render and policy results, scheduling implications and rollback path.

1. Read `apps/workload-api/`, `argocd/applications/workload-api.yaml` and `scripts/check_deployment_policies.py` in the config checkout. Inspect the image producer and portal values updater if their contracts are affected.
2. Confirm the image reference, port, readiness, resources and least-privilege settings. Keep selectors, labels and namespace consistent. Compare region selectors with node labels and capacity when authorized. Distinguish simulated labels from physical topology.
3. Lint and render affected values and run the policy check. Review rendered security, networking and rollout properties outside policy coverage. Confirm the previous desired state and rollback image are available.
4. Route changes through reviewed Git configuration. For an authorized rollout, observe the Argo CD revision and health, scheduling and endpoints. Report unavailable live checks.
