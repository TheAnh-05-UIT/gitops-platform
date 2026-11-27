# Quality gates

Use **PASS** for observed success, **FAIL** for an executed failure, **BLOCKED** for a named missing prerequisite and **NOT RUN** for checks with no execution evidence. Cite the command, checkout or source scope, result and remaining limitation.

| Boundary | Acceptance |
| --- | --- |
| Terraform | Reviewed provider lock, backend-disabled init, approved local mirror, plan-only AWS mocks, no ambient credentials, accurate resource graph and policy scope. |
| Ansible | Fixture schemas and groups, secret-free rendering and validation, task syntax when available, documented version pins, bounded readiness and safe repeated runs. AWS apply requires owner evidence. |
| Config and Workload | Render/lint and positive/negative policy tests, workload smoke, consistent port and probes, exact image/placement contract, reviewed default and rollback. |
| Placement and Portal | Positive and negative correctness, stale input and denied authorizations, CSRF and dry-run behavior, regression coverage, explainable resource and objective claims. |
| Security and release | Scoped diff, no credential artifacts, reviewed dependency and lifecycle changes, observed check provenance, independent approval, explicit publication gate. |
| Evidence | Distinguish mock from live, local source from hosted checks, and intended topology from deployed runtime. Preserve recovery and cleanup procedures. |

Set `PLATFORM_CONFIG_CHECKOUT` and `PLATFORM_WORKLOAD_CHECKOUT` to the isolated candidate paths printed by `git worktree list` in each sibling. Run `python -B -m unittest discover -s tests` in all three checkouts with the approved existing dependencies. Platform checks both Workload hard stops, the Config freeze and pinned action references from those candidates. Run the [isolated Terraform runner](../scripts/README.md) with the approved provider mirror. [Recorded checkpoint evidence](FINAL_REVIEW.md)
