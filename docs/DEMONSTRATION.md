# End-to-end demonstration

The demonstration connects three repositories. Platform provides a Profile B K3s lab, placement evidence and portal. Workload builds a scanned HTTP API image with two demo entry points. Config records the verified image, private access, approved placement, a scheduled job and a continuously running availability worker.

## Offline rehearsal

1. Use the reviewed local checkpoint refs in [final review](FINAL_REVIEW.md). Do not fetch or push during an offline rehearsal.
2. Run `python -B scripts/terraform_offline.py --provider-mirror infra/terraform/.terraform/providers` from the Platform root. Review the Profile B plan tests and the state/lock policy. Verify the initial two-instance configuration and final three-instance fixture.
3. Run `python -B -m unittest discover -s tests` in the three checkouts, using an existing test environment with Flask, Requests, PuLP/CBC and PyYAML as applicable. Render `helm template workload-api ./apps/workload-api` and run the Config image and deployment checks. Render the demo-jobs fixture from its README.
4. From Platform run `python -B -m benchmarks.compare_algorithms --snapshot optimizer/data/placement_snapshot_v1.json --as-of 2026-11-26T12:01:00Z --repeats 7`. Compare feasible results and replay a stale fixture. The region labels in this run are simulated.
5. Identify the portal tests for unauthorized write, stale base, read-only preview, conflicting retries, accepted proposal and comparison vs synced revision. The test services are mocks. Run the recovery tests to check SQLite and its journal with synthetic data.

## Owner demonstration sequence

| Step | Expected evidence |
| --- | --- |
| Verify the approved identity, state backend and plan. Begin with Profile B server + one agent. Add the second only through a reviewed plan. Set explicit simulated regions for both workers if demonstrating two region selectors. | Reviewed plan, exact state and lock keys, clean authorization evidence, profile and final 3-node count. [AWS-11 to AWS-13](TERRAFORM_STATE_RUNBOOK.md) |
| Configure nodes and capture readiness under AWS-14. | Server + 2 agents, version, workloads scheduled only where approved, private K3s API and SSM. [Ansible](../infra/ansible/README.md) |
| Review a release candidate and pinned rollout at approved hosted gates. Use an independent reviewer; run negative candidate and exact identity checks. | Protected base and review, successful approved scan/artifacts, observed digest and Config revision. [Promotion](PROMOTION_RUNBOOK.md) |
| Approve explicit Argo sync, private dashboards/alerts and demo jobs. | Config revision, status, readiness, image ID, successful probe and job, SLI windows and one redacted test alert/log. [Manual gates](MANUAL_AWS_GATES.md) |
| Preview placement and compare recommendation to real cluster constraints. A separately authorized reviewer approves any change. Revert placement through a reviewed PR and sync the revert. | Snapshot metadata, pending and accepted requests, desired and observed revision, reconciliation and HTTP check. [Portal](../portal/README.md) |
| Restore synthetic evidence offline. The owner performs a separately approved recovery or bounded load drill. Destroy the lab only after a separately approved plan and verify residual billing. | Restoration timeline and health, retained backup/state, residual storage and cost checks. [Recovery](RECOVERY_RUNBOOK.md) · [Cleanup](TERRAFORM_STATE_RUNBOOK.md) |

Record timestamps, source SHAs, sanitized counts and whether each check was mocked or observed. Keep AWS IDs, SSM tokens, Kubernetes access and inventories out of screenshots. Cost attribution is based on observed AWS billing after reporting delay. The demonstration assumes a single AZ and single K3s server.
