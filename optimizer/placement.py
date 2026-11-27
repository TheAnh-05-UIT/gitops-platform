"""Shared feasibility and objective model for the placement benchmarks."""

from dataclasses import dataclass, field
from itertools import product
from math import isclose, prod

import pulp


@dataclass
class PlacementModel:
    demands: dict
    capacities: dict
    candidates: dict
    costs: dict
    groups: dict = field(default_factory=dict)
    target_regions: dict = field(default_factory=dict)
    pressure: dict = field(default_factory=dict)
    headroom_weight: float = 0


def projected_pressure(model, target, used):
    baseline_cpu, baseline_memory, cpu, memory = model.pressure[target]
    return max((baseline_cpu + used[0]) / cpu, (baseline_memory + used[1]) / memory)


def score(model, placement):
    """Validate complete placement against the discrete model and score it."""
    if placement.keys() != model.demands.keys():
        return None

    usage = {target: [0] * len(capacity) for target, capacity in model.capacities.items()}
    group_regions = {}
    total = 0.0
    for item in sorted(placement):
        target = placement[item]
        if target not in model.candidates[item]:
            return None
        if item in model.groups:
            region = model.target_regions[target]
            if group_regions.setdefault(model.groups[item], region) != region:
                return None
        for index, request in enumerate(model.demands[item]):
            usage[target][index] += request
            if usage[target][index] > model.capacities[target][index]:
                return None
        total += model.costs[item, target]
    return total + model.headroom_weight * max(
        (projected_pressure(model, target, usage[target]) for target in model.pressure),
        default=0,
    )


def solve_greedy(model):
    used = {target: [0] * len(capacity) for target, capacity in model.capacities.items()}
    placement = {}
    group_regions = {}
    for item in sorted(model.demands, key=lambda name: (len(model.candidates[name]), name)):
        group = model.groups.get(item)
        request = model.demands[item]
        trials = []
        peaks = sorted(
            ((projected_pressure(model, target, used[target]), target) for target in model.pressure),
            reverse=True,
        )[:2]
        for target in model.candidates[item]:
            region = model.target_regions.get(target)
            if group in group_regions and group_regions[group] != region:
                continue
            projected = [current + extra for current, extra in zip(used[target], request)]
            if any(total > limit for total, limit in zip(projected, model.capacities[target])):
                continue
            peak = next((current for current, name in peaks if name != target), 0)
            if target in model.pressure:
                peak = max(peak, projected_pressure(model, target, projected))
            trials.append((model.costs[item, target] + model.headroom_weight * peak, target, projected))
        if not trials:
            return "NoSolutionFound", None
        _, target, projected = min(trials)
        used[target] = projected
        placement[item] = target
        if group is not None:
            group_regions[group] = model.target_regions[target]
    return "Feasible", placement


def solve_exhaustive(model, max_combinations):
    items = sorted(model.demands)
    options = [model.candidates[item] for item in items]
    if prod(map(len, options)) > max_combinations:
        return "SkippedCombinationLimit", None
    best_placement = None
    best = float("inf")
    for targets in product(*options):
        placement = dict(zip(items, targets))
        objective = score(model, placement)
        if objective is not None and objective < best:
            best_placement, best = placement, objective
    return ("Optimal", best_placement) if best_placement is not None else ("Infeasible", None)


def solve_ilp(model, time_limit=None):
    if any(not options for options in model.candidates.values()):
        return "Infeasible", None

    problem = pulp.LpProblem("multi_service_placement", pulp.LpMinimize)
    selected = {
        pair: pulp.LpVariable(f"select_{index}", cat="Binary")
        for index, pair in enumerate(sorted(model.costs))
    }
    for item, targets in model.candidates.items():
        problem += pulp.lpSum(selected[item, target] for target in targets) == 1

    group_items = {}
    for item, group in model.groups.items():
        group_items.setdefault(group, []).append(item)
    for index, items in enumerate(group_items.values()):
        regions = sorted({model.target_regions[target] for item in items for target in model.candidates[item]})
        for region_index, region in enumerate(regions):
            group_choice = pulp.LpVariable(f"cohort_{index}_{region_index}", cat="Binary")
            for item in items:
                problem += pulp.lpSum(
                    selected[item, target] for target in model.candidates[item]
                    if model.target_regions[target] == region
                ) == group_choice

    peak = pulp.LpVariable("peak_pressure", lowBound=0) if model.pressure else 0
    terms_by_target = {target: [] for target in model.capacities}
    for (item, target), variable in selected.items():
        terms_by_target[target].append((model.demands[item], variable))
    for target, capacity in model.capacities.items():
        terms = terms_by_target[target]
        used = [pulp.lpSum(request[index] * var for request, var in terms)
                for index in range(len(capacity))]
        for total, limit in zip(used, capacity):
            problem += total <= limit
        if target in model.pressure:
            baseline_cpu, baseline_memory, cpu, memory = model.pressure[target]
            problem += used[0] + baseline_cpu <= peak * cpu
            problem += used[1] + baseline_memory <= peak * memory

    problem += pulp.lpSum(model.costs[pair] * var for pair, var in selected.items()) + model.headroom_weight * peak
    status = pulp.LpStatus[problem.solve(pulp.PULP_CBC_CMD(
        msg=False, threads=1, options=["randomSeed 1"], timeLimit=time_limit,
    ))]
    incumbent = problem.sol_status == pulp.LpSolutionIntegerFeasible
    optimal = status == "Optimal" and problem.sol_status == pulp.LpSolutionOptimal
    if not (optimal or incumbent):
        return ("Timeout" if status == "Not Solved" and time_limit is not None else status), None

    assignments = []
    for pair, variable in selected.items():
        value = pulp.value(variable)
        if value is None or not (isclose(value, 0, abs_tol=1e-6) or isclose(value, 1, abs_tol=1e-6)):
            return "InvalidIncumbent", None
        if value > 0.5:
            assignments.append(pair)
    placement = dict(assignments)
    if len(assignments) != len(placement) or score(model, placement) is None:
        return "InvalidIncumbent", None
    return ("Optimal" if optimal else "FeasibleNotProven"), placement
