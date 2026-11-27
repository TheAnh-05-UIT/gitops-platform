# Offline workload placement

The snapshot benchmark compares the PuLP/CBC model, a deterministic greedy heuristic, and bounded exhaustive search against the same forecast and hard constraints. It emits JSON recommendations with the evidence needed for review before creating any GitOps change.

Run from the Platform repository with its existing Python environment.

```powershell
python -B -m benchmarks.compare_algorithms --snapshot optimizer/data/placement_snapshot_v1.json --as-of 2026-11-26T12:01:00Z
python -B -m benchmarks.compare_algorithms --case infeasible
python -B -m unittest discover -s tests -p test_placement_snapshots.py -v
```

`--as-of` enables replay. Omit it when evaluating current evidence. The default freshness limit is 300 seconds. The program emits `StaleSnapshot` and exits with code 2 when any supplied evidence predates the limit or has a timestamp after the evaluation time. CBC uses one thread, seed 1, and a 30-second limit per run. An incumbent can be `FeasibleNotProven` or yield `Timeout` without one. Only exhaustive search and a proven CBC result establish optimality. The benchmark reports median and nearest-rank p95 wall time in milliseconds and solver statuses across repetitions. Runtime includes the local CBC launch overhead. The legacy CSV single-service portal and CLI still use their existing simulation contract.

## Snapshot contract

| Field | Required evidence |
| --- | --- |
| `schema_version` and `mode` | Integer `1` and `simulation` or `observed`. |
| `capacity` | `observed_at`, `pod_coverage: all-namespaces`, completed core v1 node and pod list exports. Optional `reserve_by_node` records additional reserved mCPU, MiB, and pod slots. |
| `latency` | `observed_at` and `rtt_ms_by_region` keyed by the placement label. Each workload specifies its maximum RTT. |
| `metrics` | Optional `observed_at` and `usage_by_node` with caller-normalized mCPU and MiB. Without a measurement for a node, predicted pressure uses booked requests. |
| `pricing` | Optional `observed_at` and `incremental_usd_per_replica_hour_by_region`. A positive cost weight requires price evidence for each candidate region. These inputs represent modeled incremental estimates. |
| `workloads` | Unique name, replica count, effective mCPU and MiB per replica, and maximum RTT. Optionally restrict placement regions and declare the current region and replica count for the movement penalty. |
| `weights` | Nonnegative weights for incremental cost, peak pressure, and moved replicas. Defaults are 0, 1, and 0.05 respectively. |

Observe node and pod exports within the same capacity window. For production-inspired review, owners should provide sanitized, complete lists acquired under the cluster read-only evidence gate. The normalizer rejects paginated lists, unbound pods, unsupported resize or pod-level resource requests, and unknown workload fields. Preserve Node names, placement labels, taints, conditions and allocatable. Preserve pod UIDs, namespaces, node binding, phase, init/regular container requests and pod overhead. Remove unrelated annotations, client config and other sensitive material before sharing. Keep observed exports and recommendations outside Git. The included fixture declares `simulation`.

The model accounts for existing nonterminal pod requests and explicit headroom per node, including init containers, restartable init sidecars, and pod overhead. Current workload pods remain booked, so a proposed move is sized conservatively for overlap. Allocatable supplies CPU, memory, and pod slots. Readiness, cordon and blocking taints determine candidate nodes. Each workload's replicas share one `idp.example.com/region` value for the GitOps chart selector. AWS region and AZ remain independent metadata.

After placement, forecast pressure is based on the greater of booked/reserved capacity and measured use, plus the proposed requests, divided by allocatable. Metrics are independent of hard capacity. The explanation reports the weighted objective components, regional replica counts, proposed per-node packing, capacity remaining, and candidate rejection reasons. The planned packing is a feasibility check for a region selector. Actual node selection belongs to Kubernetes.

The model omits storage bindings, resource quotas, topology spread, tolerations, custom affinity, admission changes, disruption, retry after concurrent scheduling, and multi-container demand estimation. Check those constraints against the target environment before promotion. The tool consumes saved inputs and produces recommendations only. Actual-cluster placement and performance evidence belong to [AWS-15-PLACEMENT](../docs/MANUAL_AWS_GATES.md#aws-15-placement-read-only-evidence-gate).
