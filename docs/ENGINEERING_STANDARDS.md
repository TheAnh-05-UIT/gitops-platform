# Engineering standards

## Changes

- Identify the root cause and use the owning repository. Preserve behavior and cross-repository contracts unless the task authorizes a change. For breaking changes, review migration order and a rollback before editing.
- Prefer existing interfaces and simple designs. Obtain approval before adding or changing dependencies. Keep unrelated refactors out of the diff. Complete production behavior without placeholders.
- Update architecture and contract documentation alongside material changes. Use an ADR for meaningful decisions about ownership, interfaces, infrastructure or operating policy. State status, context, decision and consequences.

## Python and optimization

- Follow PEP 8 and the repository's module boundaries. Use clear names and type hints on new interfaces where useful. Separate business logic, HTTP handlers and external integration code.
- Validate external input, handle expected errors explicitly and use application logging suitable for structured collection. Keep sensitive request data out of logs.
- Add a regression test for each bug fix. Record datasets, units, solver versions and settings when reporting benchmark results. Check feasibility independently of cost and keep measured timings separate from algorithm guarantees.

## Delivery and infrastructure

- Validate before publication and promotion. Keep GitHub Actions permissions minimal, separate publication from validation responsibilities, and review concurrency, duplicate PRs and recovery after partial failures.
- Keep managed desired state in Git and use reviewed PRs. Use explicit image tags or immutable digests, retain a rollback reference, and validate the rendered manifest and Argo CD reconciliation behavior.
- Set workload-specific resource requests and limits, non-root execution, least-privilege security contexts, and probes appropriate to the workload. Maintain labels and selectors, and check actual placement capacity before promising rollout readiness.
- Keep declarative Terraform and Ansible under the platform repository. Separate environments, protect state and plan files, review the authorized plan before applying, and account for cost, security, reliability and operational complexity. Require explicit authorization for provisioning, destruction and live changes.
- Establish observability from workload behavior and deployment objectives before choosing telemetry components. Specify reliable signals, owners and response paths when adding alerts or SLOs.
