# Platform repository

Read the [shared workspace policy](docs/WORKSPACE_POLICY.md) before editing and manually open the matching `.agents/skills/<name>/SKILL.md`. This checkout owns the [shared architecture](docs/ARCHITECTURE.md), docs and nine skill files. For a standalone clone, coordinate external contract changes with their owners.

- Run `python -m flask --app portal.app run`, `python -m optimizer.ilp`, and `python -m benchmarks.compare_algorithms` from this checkout's root with `requirements.txt` installed. Use fixture data and mock GitHub for portal tests.
- Keep `portal/app.py`, `portal/github_client.py`, and `optimizer/ilp.py` separate at the HTTP, GitHub and placement boundaries. Preserve CSRF handling, validate inputs, and treat GitHub writes as authenticated external mutations.
- Preserve the config PR contract in `portal/github_client.py`. Check the config chart and workload requirements before changing region labels, replicas, per-replica requests or values layout.
- Validate optimizer changes with feasible and infeasible fixture cases. Compare benchmark algorithms against exhaustive search when it can run and keep timing claims tied to the run environment.
- Keep authorized Terraform and Ansible work under `infra/`. Preserve pre-existing drafts and keep plans, state, inventories and credentials private. Review infrastructure before any authorized live operation.
