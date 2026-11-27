import json
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pulp

from optimizer.placement import score, solve_exhaustive, solve_greedy, solve_ilp
from optimizer.snapshot import StaleSnapshot, build_snapshot_model, explain


FIXTURE = Path(__file__).resolve().parents[1] / "optimizer/data/placement_snapshot_v1.json"
REFERENCE_TIME = datetime(2026, 11, 26, 12, 1, tzinfo=timezone.utc)


class PlacementSnapshotsTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def compile(self):
        return build_snapshot_model(self.snapshot, REFERENCE_TIME, max_age_seconds=300)

    def test_optimal_snapshot_agrees_with_exhaustive_and_reports_capacity(self):
        compiled = self.compile()
        model = compiled.model
        ilp_status, placement = solve_ilp(model)
        exhaustive_status, exhaustive = solve_exhaustive(model, 100_000)
        greedy_status, greedy = solve_greedy(model)
        self.assertEqual((ilp_status, exhaustive_status, greedy_status), ("Optimal", "Optimal", "Feasible"))
        self.assertAlmostEqual(score(model, placement), score(model, exhaustive))
        self.assertGreaterEqual(score(model, greedy) + 1e-9, score(model, exhaustive))
        evidence = explain(compiled, placement)
        self.assertEqual(evidence["source_mode"], "simulation")
        self.assertEqual(evidence["workloads"]["workload-api"]["replicas"], 2)
        self.assertIn("placement_region", evidence["workloads"]["workload-api"])
        for node in evidence["nodes"].values():
            self.assertGreaterEqual(node["remaining"]["cpu_mcpu"], 0)
            self.assertGreaterEqual(node["remaining"]["memory_mib"], 0)
        self.assertNotEqual(
            evidence["nodes"]["worker-a"]["placement_region"],
            evidence["nodes"]["worker-a"]["aws_region"],
        )
        self.assertEqual(evidence["nodes"]["worker-a"]["already_requested"]["cpu_mcpu"], 410)
        self.assertEqual(evidence["nodes"]["worker-a"]["already_requested"]["memory_mib"], 173)
        weights = evidence["objective_weights"]
        self.assertAlmostEqual(evidence["objective"], (
            weights["incremental_cost"] * evidence["estimated_incremental_usd_per_hour"]
            + weights["peak_pressure"] * evidence["projected_peak_pressure"]
            + weights["moved_replicas"] * evidence["moved_replicas"]
        ))

    def test_fragmented_nodes_and_one_selector_are_not_aggregated(self):
        workload = self.snapshot["workloads"][0]
        workload.update(cpu_mcpu_per_replica=900, memory_mib_per_replica=64)
        self.snapshot["workloads"] = [workload]
        self.snapshot["capacity"]["pods"]["items"] = []
        compiled = self.compile()
        self.assertEqual(solve_ilp(compiled.model), ("Infeasible", None))
        self.assertEqual(solve_exhaustive(compiled.model, 100), ("Infeasible", None))

    def test_cordoned_and_tainted_nodes_are_rejected(self):
        nodes = self.snapshot["capacity"]["nodes"]["items"]
        nodes[0]["spec"]["unschedulable"] = True
        nodes[1]["spec"]["taints"] = [{"key": "dedicated", "value": "system", "effect": "NoSchedule"}]
        compiled = self.compile()
        self.assertIn("unschedulable", compiled.rejections["workload-api"]["worker-a"])
        self.assertIn("blocking_taint", compiled.rejections["workload-api"]["worker-b"])
        self.assertNotIn("insufficient_node_capacity", compiled.rejections["workload-api"]["worker-a"])
        self.assertEqual(solve_ilp(compiled.model), ("Infeasible", None))

    def test_stale_capacity_and_optional_metric_sources_hold_recommendation(self):
        for source in ("capacity", "latency", "metrics", "pricing"):
            with self.subTest(source=source):
                original = deepcopy(self.snapshot)
                self.snapshot[source]["observed_at"] = "2026-11-26T11:50:00Z"
                with self.assertRaisesRegex(StaleSnapshot, source):
                    self.compile()
                self.snapshot = original

    def test_metrics_guide_ranking_without_subtracting_usage_again(self):
        actual = self.compile()
        del self.snapshot["metrics"]
        requests_only = self.compile()
        self.assertEqual(actual.model.capacities, requests_only.model.capacities)
        self.assertNotEqual(actual.model.pressure, requests_only.model.pressure)

    def test_missing_price_is_not_treated_as_cheap_when_weighted(self):
        self.snapshot["pricing"]["incremental_usd_per_replica_hour_by_region"].pop("eu-west-1")
        compiled = self.compile()
        self.assertIn("missing_incremental_price", compiled.rejections["workload-api"]["worker-b"])
        self.assertEqual(solve_ilp(compiled.model)[0], "Optimal")

    def test_invalid_and_conflicting_inventory_is_rejected(self):
        self.snapshot["capacity"]["nodes"]["metadata"]["continue"] = "unfinished"
        with self.assertRaisesRegex(ValueError, "paginated"):
            self.compile()
        self.snapshot["capacity"]["nodes"]["metadata"].clear()
        pod = deepcopy(self.snapshot["capacity"]["pods"]["items"][0])
        pod["spec"].pop("nodeName")
        self.snapshot["capacity"]["pods"]["items"][0] = pod
        with self.assertRaisesRegex(ValueError, "unbound"):
            self.compile()

    def test_timeout_is_not_mislabeled_as_optimal(self):
        compiled = self.compile()

        def stopped(problem, solver):
            problem.assignStatus(pulp.LpStatusNotSolved, pulp.LpSolutionNoSolutionFound)
            return pulp.LpStatusNotSolved

        with patch.object(pulp.LpProblem, "solve", stopped):
            self.assertEqual(solve_ilp(compiled.model, time_limit=1), ("Timeout", None))

    def test_incumbent_is_validated_without_claiming_optimality(self):
        compiled = self.compile()
        real_solve = pulp.LpProblem.solve

        def stopped_with_incumbent(problem, solver):
            real_solve(problem, solver)
            problem.assignStatus(pulp.LpStatusOptimal, pulp.LpSolutionIntegerFeasible)
            return pulp.LpStatusOptimal

        with patch.object(pulp.LpProblem, "solve", stopped_with_incumbent):
            status, placement = solve_ilp(compiled.model, time_limit=1)
        self.assertEqual(status, "FeasibleNotProven")
        self.assertIsNotNone(score(compiled.model, placement))

    def test_generic_kubectl_list_exports_are_typed(self):
        baseline = self.compile()
        for name, kind in (("nodes", "Node"), ("pods", "Pod")):
            source = self.snapshot["capacity"][name]
            source["kind"] = "List"
            for item in source["items"]:
                item.update(kind=kind, apiVersion="v1")
        self.assertEqual(self.compile().model, baseline.model)
        self.snapshot["capacity"]["nodes"]["items"][0]["kind"] = "Pod"
        with self.assertRaisesRegex(ValueError, "only Node objects"):
            self.compile()

    def test_workload_requirements_outside_model_are_rejected(self):
        self.snapshot["workloads"][0]["affinity"] = {"nodeAffinity": {}}
        with self.assertRaisesRegex(ValueError, "outside the snapshot placement model"):
            self.compile()

if __name__ == "__main__":
    unittest.main()
