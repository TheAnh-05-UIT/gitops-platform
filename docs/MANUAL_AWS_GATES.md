# Manual AWS execution gates

All real AWS operations are owner-run under the [Platform AGENTS policy](../AGENTS.md#manual-cloud-execution-policy). No AWS credentials are needed for offline implementation or reviewed fixtures.

| Gate | Operation | Authoritative instructions and status |
| --- | --- | --- |
| AWS-11/S0 | Confirm account, Region, role, quotas, cost and approvals | [Terraform state runbook](TERRAFORM_STATE_RUNBOOK.md). BLOCKED pending owner execution. |
| AWS-12/13 | Bootstrap and lab plan/init/apply, S3 locking, migration and incident recovery | [Terraform state runbook](TERRAFORM_STATE_RUNBOOK.md). BLOCKED pending owner execution. |
| AWS-14 | SSM, OS baseline and K3s deployment | [Ansible automation and owner commands](../infra/ansible/README.md). Requires approved pins, SSM and transfer-bucket verification. |
| AWS-15 | Argo CD bootstrap, reviewed sync and workload readiness | [Config Argo CD runbook](../../gitops-platform-config/argocd/README.md). Requires trusted image and reviewed cluster access. |
| AWS-16 | Review and reconcile lab and backend cleanup and residual cost | [Terraform state runbook](TERRAFORM_STATE_RUNBOOK.md). BLOCKED pending owner execution. |
| AWS-15-OBS1/2 | Private monitoring, logs and bounded SRE exercise | [Config observability runbook](../../gitops-platform-config/observability/README.md). Requires privately reachable targets and reviewed chart packages. |
| AWS-15-DEMO | Install and verify the private background worker and CronJob | [Config demo jobs](../../gitops-platform-config/apps/demo-jobs/README.md). Requires a scanned pinned image with the job entry points and a scoped manual-sync Application. |
| AWS-15-PLACEMENT | Capture owner-approved read-only capacity and compare a recommendation | Run the evidence gate below after workload readiness. |
| AWS-14-R0/R1/R2, AWS-15-R3 | Private preflight, off-host backup, staged same-server restore and recovery smoke | [Recovery runbook](RECOVERY_RUNBOOK.md). Requires separately approved outage window, owner-only SSM and protected backup custody. |

Each live gate requires an exact source revision, working directory, inputs, commands, expected result, costs, risks, rollback or cleanup, and redacted evidence. A gate for one mutation does not authorize another.

### AWS-15-PLACEMENT read-only evidence gate

Run from `<workspace>/gitops-platform` with the previously approved private `LAB_KUBE_CONTEXT`, owner-approved `AWS_PROFILE` and `AWS_REGION` for the SSM access path, and a secure off-repository `LAB_EVIDENCE_DIR`. Use the approved lab identity restricted to listing nodes and pods. Wait for a stable capacity window with no in-flight rollout. Run the following only after verifying the target identity.

```bash
umask 077
kubectl --context "$LAB_KUBE_CONTEXT" get nodes --request-timeout=10s -o json > "$LAB_EVIDENCE_DIR/nodes.json"
kubectl --context "$LAB_KUBE_CONTEXT" get pods -A --request-timeout=10s -o json > "$LAB_EVIDENCE_DIR/pods.json"
```

Require complete lists in the same timestamp window. Review and sanitize the exports, then create an observed snapshot under the [snapshot contract](../optimizer/README.md). Use reviewed measurements for RTT and optional telemetry and price estimates. Run `python -B -m benchmarks.compare_algorithms --snapshot "$LAB_EVIDENCE_DIR/snapshot.json"` and compare proposed counts and labels to scheduling, quota, topology and rollout headroom. Stop on stale data, partial exports, unfamiliar workload constraints or missing access. Keep local outputs private, remove or retain them under the owner's evidence policy and review exports before sharing. The gate writes only local evidence and adds no AWS resources. Existing SSM, monitoring and cluster operating costs apply. Return timestamp, node and workload counts, selected labels, missing constraints and simulated versus observed input mode.
