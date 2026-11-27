import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from math import ceil, isclose, isfinite, prod
from pathlib import Path
from statistics import median
from time import perf_counter

import pulp

from optimizer.ilp import read_csv
from optimizer.placement import PlacementModel, score, solve_exhaustive, solve_greedy, solve_ilp
from optimizer.snapshot import StaleSnapshot, build_snapshot_model, explain, timestamp


def build_model(copies, scenario):
    regions = read_csv("regions.csv", "region")
    latency = read_csv("latency.csv", "region")
    services = read_csv("benchmark_services.csv", "service")

    if set(regions) != set(latency):
        raise ValueError("regions.csv and latency.csv must contain the same regions.")

    capacities = {
        region: (
            int(row["cpu_mcpu"]) * copies,
            int(row["memory_mib"]) * copies,
        )
        for region, row in regions.items()
    }
    prices = {
        region: float(row["price_usd_per_hour"]) * copies
        for region, row in regions.items()
    }

    demands = {}
    candidates = {}
    costs = {}

    for index in range(copies):
        for name, row in services.items():
            service = name if copies == 1 else f"{name}-{index + 1:03d}"
            replicas = int(row["replicas"])
            if scenario == "infeasible" and name == "api-b":
                replicas *= 2

            cpu = int(row["cpu_mcpu_per_replica"]) * replicas
            memory = int(row["memory_mib_per_replica"]) * replicas
            max_rtt = int(row["max_rtt_ms"])
            demands[service] = (cpu, memory)
            candidates[service] = []

            for region, (total_cpu, total_memory) in capacities.items():
                rtt = int(latency[region]["rtt_ms"])

                if rtt <= max_rtt and cpu <= total_cpu and memory <= total_memory:
                    candidates[service].append(region)
                    costs[service, region] = prices[region] * max(
                        cpu / total_cpu, memory / total_memory
                    )

    return PlacementModel(demands, capacities, candidates, costs)


def benchmark(model, solver, repeats, snapshot=None):
    samples = []
    statuses = Counter()
    for _ in range(repeats):
        start = perf_counter()
        status, placement = solver()
        samples.append((perf_counter() - start) * 1000)
        statuses[status] += 1
        objective = score(model, placement) if placement is not None else None
        if placement is not None and objective is None:
            raise RuntimeError("Solver returned an invalid placement.")

    skipped = status.startswith("Skipped")
    result = {
        "status": status,
        "placement": placement,
        "statuses": statuses,
        "median_ms": None if skipped else median(samples),
        "p95_ms": None if skipped else sorted(samples)[ceil(0.95 * len(samples)) - 1],
    }
    if snapshot is None:
        result["estimated_cost_usd_per_hour"] = objective
    else:
        result["objective"] = objective
        result["explanation"] = explain(snapshot, placement)
    return result


def compare(results, objective_field):
    ilp = results["ilp"]
    exact = results["exhaustive"]
    greedy = results["greedy"]
    if exact["status"] == "Infeasible" and any(
        result["placement"] is not None for result in (ilp, greedy)
    ):
        raise RuntimeError("A solver returned a placement for an infeasible model.")
    if exact["status"] == "Optimal" and ilp["status"] == "Infeasible":
        raise RuntimeError("ILP and exhaustive search disagree on feasibility.")
    if exact["status"] == ilp["status"] == "Optimal" and not isclose(
        ilp[objective_field], exact[objective_field], abs_tol=1e-9,
    ):
        raise RuntimeError("ILP and exhaustive search disagree on the optimal objective.")
    optimum = next((result[objective_field] for result in (exact, ilp)
                    if result["status"] == "Optimal"), None)
    if optimum is None:
        return
    for name, result in (("ilp", ilp), ("greedy", greedy)):
        objective = result[objective_field]
        if objective is None:
            continue
        if objective < optimum and not isclose(objective, optimum, abs_tol=1e-9):
            raise RuntimeError(f"{name} reports a better score than the proven optimum.")
        if optimum > 0:
            result["gap_percent"] = round(100 * (objective - optimum) / optimum, 4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("baseline", "infeasible"), default="baseline")
    parser.add_argument("--copies", type=int, default=1)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--as-of", help="ISO 8601 evaluation time. Defaults to the current UTC time.")
    parser.add_argument("--max-age-seconds", type=int, default=300)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--max-combinations", type=int, default=100_000)
    parser.add_argument("--time-limit-seconds", type=float, default=30)
    args = parser.parse_args()

    if min(args.copies, args.repeats, args.max_combinations, args.max_age_seconds) < 1:
        parser.error("Copies, repeats, maximum combinations and freshness limit must be positive.")
    if not isfinite(args.time_limit_seconds) or args.time_limit_seconds <= 0:
        parser.error("The ILP time limit must be positive and finite.")
    if args.snapshot and (args.copies != 1 or args.case != "baseline"):
        parser.error("CSV cases and copies cannot be combined with a snapshot.")
    if args.as_of and not args.snapshot:
        parser.error("An evaluation time requires a snapshot.")

    snapshot = None
    if args.snapshot:
        try:
            snapshot = build_snapshot_model(
                json.loads(args.snapshot.read_text(encoding="utf-8")),
                timestamp(args.as_of) if args.as_of else datetime.now(timezone.utc),
                args.max_age_seconds,
            )
        except StaleSnapshot as error:
            print(json.dumps({"case": "snapshot", "status": "StaleSnapshot", "reason": str(error)}))
            return 2
        except (ValueError, OSError) as error:
            parser.error(str(error))
    model = snapshot.model if snapshot is not None else build_model(args.copies, args.case)
    results = {
        "ilp": benchmark(
            model, lambda: solve_ilp(model, args.time_limit_seconds), args.repeats, snapshot,
        ),
        "greedy": benchmark(model, lambda: solve_greedy(model), args.repeats, snapshot),
        "exhaustive": benchmark(
            model, lambda: solve_exhaustive(model, args.max_combinations), args.repeats, snapshot,
        ),
    }
    compare(results, "objective" if snapshot is not None else "estimated_cost_usd_per_hour")
    print(json.dumps({
        "case": "snapshot" if snapshot is not None else args.case,
        "services": len(set(model.groups.values())) if model.groups else len(model.demands),
        "placement_units": len(model.demands),
        "candidate_assignments": prod(len(options) for options in model.candidates.values()),
        "repeats": args.repeats,
        "solver": {"pulp_version": pulp.__version__, "cbc_threads": 1, "cbc_seed": 1,
                   "cbc_time_limit_seconds": args.time_limit_seconds,
                   "exhaustive_max_combinations": args.max_combinations},
        "results": results,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
