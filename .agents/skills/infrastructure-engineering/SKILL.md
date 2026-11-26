---
name: infrastructure-engineering
description: Review or develop authorized Terraform, AWS, Ansible, Linux and k3s provisioning using the platform lab draft and environment contracts.
---

# Infrastructure engineering

Take the environment, IaC revision, inventory and access scope as inputs. Return a declarative proposal or diff with validation, cost and reliability implications.

1. Read [project state](../../../docs/PROJECT_STATE.md) and `infra/terraform/` and `infra/ansible/` when available. The baseline has an untracked single-AZ lab draft. Reproducible provisioning and its live state remain unverified.
2. Review Region/AZ compatibility, network boundaries, inventory mapping, instance cost, bootstrap version and idempotency. Keep inventory, plans, state and credentials private. Verify the config chart's label contract.
3. Run format and available provider or playbook syntax checks. Review any authorized plan privately. Identify missing tooling and evidence.
4. Require explicit authorization for provisioning, destruction and remote changes. For authorized lab operations capture readiness, labels, recovery and cost controls with sensitive details redacted.
