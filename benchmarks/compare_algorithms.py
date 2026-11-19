import argparse
import json
from dataclasses import dataclass
from itertools import product
from math import isclose, prod
from statistics import median
from time import perf_counter

import pulp

from optimizer.ilp import read_csv


@dataclass
class PlacementModel:
    demands: dict
    capacities: dict
    candidates: dict
    costs: dict


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


def score(model, placement):
    """Return the cost of a complete, valid placement."""
    if placement.keys() != model.demands.keys():
        return None

    usage = {region: [0, 0] for region in model.capacities}
    total_cost = 0.0

    for service, region in placement.items():
        if region not in model.candidates[service]:
            return None

        cpu, memory = model.demands[service]
        used = usage[region]
        used[0] += cpu
        used[1] += memory

        total_cpu, total_memory = model.capacities[region]
        if used[0] > total_cpu or used[1] > total_memory:
            return None

        total_cost += model.costs[service, region]

    return total_cost


def solve_greedy(model):
    remaining = {
        region: list(capacity) for region, capacity in model.capacities.items()
    }
    placement = {}
    services = sorted(
        model.demands,
        key=lambda service: (len(model.candidates[service]), service),
    )

    for service in services:
        cpu, memory = model.demands[service]
        regions = sorted(
            model.candidates[service],
            key=lambda region: (model.costs[service, region], region),
        )

        for region in regions:
            available = remaining[region]
            if cpu <= available[0] and memory <= available[1]:
                placement[service] = region
                available[0] -= cpu
                available[1] -= memory
                break
        else:
            return "NoSolutionFound", None

    return "Feasible", placement


def solve_exhaustive(model, max_combinations):
    services = list(model.demands)
    options = [model.candidates[service] for service in services]

    if prod(len(regions) for regions in options) > max_combinations:
        return "SkippedCombinationLimit", None

    best_placement = None
    best_cost = float("inf")

    for regions in product(*options):
        placement = dict(zip(services, regions))
        cost = score(model, placement)
        if cost is not None and cost < best_cost:
            best_placement = placement
            best_cost = cost

    if best_placement is None:
        return "Infeasible", None

    return "Optimal", best_placement


def solve_ilp(model):
    if any(not options for options in model.candidates.values()):
        return "Infeasible", None

    problem = pulp.LpProblem("multi_service_placement", pulp.LpMinimize)
    selected = {
        pair: pulp.LpVariable(f"select_{index}", cat="Binary")
        for index, pair in enumerate(model.costs)
    }

    for service, regions in model.candidates.items():
        problem += pulp.lpSum(selected[service, region] for region in regions) == 1

    for region, (total_cpu, total_memory) in model.capacities.items():
        terms = [
            (model.demands[service], variable)
            for (service, target), variable in selected.items()
            if target == region
        ]
        problem += pulp.lpSum(cpu * var for (cpu, _), var in terms) <= total_cpu
        problem += pulp.lpSum(memory * var for (_, memory), var in terms) <= total_memory

    problem += pulp.lpSum(
        model.costs[pair] * variable for pair, variable in selected.items()
    )

    status = pulp.LpStatus[problem.solve(pulp.PULP_CBC_CMD(msg=False))]
    if status != "Optimal":
        return status, None

    placement = {
        service: region
        for (service, region), variable in selected.items()
        if pulp.value(variable) > 0.5
    }
    return status, placement


def benchmark(model, solver, repeats):
    samples = []

    for _ in range(repeats):
        start = perf_counter()
        status, placement = solver()
        samples.append((perf_counter() - start) * 1000)

    cost = score(model, placement) if placement is not None else None
    if placement is not None and cost is None:
        raise RuntimeError("Solver returned an invalid placement.")

    return {
        "status": status,
        "placement": placement,
        "estimated_cost_usd_per_hour": cost,
        "median_ms": None if status.startswith("Skipped") else median(samples),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("baseline", "infeasible"), default="baseline")
    parser.add_argument("--copies", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--max-combinations", type=int, default=100_000)
    args = parser.parse_args()

    if min(args.copies, args.repeats, args.max_combinations) < 1:
        parser.error("Copies, repeats and max combinations must be positive.")

    model = build_model(args.copies, args.case)
    results = {
        "ilp": benchmark(model, lambda: solve_ilp(model), args.repeats),
        "greedy": benchmark(model, lambda: solve_greedy(model), args.repeats),
        "exhaustive": benchmark(
            model,
            lambda: solve_exhaustive(model, args.max_combinations),
            args.repeats,
        ),
    }

    ilp = results["ilp"]
    exhaustive = results["exhaustive"]
    if exhaustive["status"] in ("Optimal", "Infeasible"):
        if ilp["status"] != exhaustive["status"]:
            raise RuntimeError("ILP and Exhaustive Search disagree on the status.")
        if ilp["status"] == "Optimal" and not isclose(
            ilp["estimated_cost_usd_per_hour"],
            exhaustive["estimated_cost_usd_per_hour"],
            abs_tol=1e-9,
        ):
            raise RuntimeError("ILP and Exhaustive Search disagree on optimal cost.")

    optimal_cost = ilp["estimated_cost_usd_per_hour"]
    greedy_cost = results["greedy"]["estimated_cost_usd_per_hour"]
    if optimal_cost is not None and optimal_cost > 0 and greedy_cost is not None:
        results["greedy"]["gap_percent"] = round(
            100 * (greedy_cost - optimal_cost) / optimal_cost, 4
        )

    print(json.dumps({
        "case": args.case,
        "services": len(model.demands),
        "candidate_assignments": prod(
            len(options) for options in model.candidates.values()
        ),
        "repeats": args.repeats,
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()