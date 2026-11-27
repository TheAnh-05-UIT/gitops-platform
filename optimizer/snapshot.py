"""Compile a versioned, operator-exported snapshot into a recommendation model."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from optimizer.kubernetes_snapshot import (
    UNITS, entries, identifier, mapping, nonnegative_int, normalize_inventory,
)
from optimizer.placement import PlacementModel, projected_pressure, score


class StaleSnapshot(ValueError):
    """The snapshot cannot support a current recommendation."""


@dataclass
class SnapshotModel:
    model: PlacementModel
    mode: str
    source_times: dict
    resources: dict
    reserves: dict
    latency: dict
    prices: dict
    rejections: dict
    current_regions: dict
    moved_units: set
    weights: dict


def timestamp(value):
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError("Use an ISO 8601 timestamp with a timezone") from error


def _nonnegative_number(value, field):
    if type(value) not in (int, float) or not 0 <= value <= 10**12 or not isfinite(value):
        raise ValueError(f"{field} must be a finite nonnegative number")
    return float(value)


def _by_region(value, field):
    return {
        identifier(region, "placement region"): _nonnegative_number(observed, field)
        for region, observed in mapping(value, field).items()
    }


def _resources(value, fields):
    row = mapping(value, "resource evidence")
    if set(row) != set(fields):
        raise ValueError("Resource evidence must specify its units")
    return tuple(nonnegative_int(row[field], field) for field in fields)


def _by_node(value, nodes, fields):
    rows = mapping(value, "per-node evidence")
    if not rows.keys() <= nodes.keys():
        raise ValueError("Per-node evidence must refer to nodes in the inventory")
    return {node: _resources(row, fields) for node, row in rows.items()}


def build_snapshot_model(snapshot, as_of, max_age_seconds):
    snapshot = mapping(snapshot, "snapshot")
    if type(snapshot.get("schema_version")) is not int or snapshot["schema_version"] != 1:
        raise ValueError("Unsupported placement snapshot schema version")
    mode = snapshot.get("mode")
    if mode not in ("simulation", "observed"):
        raise ValueError("Snapshot mode must be simulation or observed")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or (
        nonnegative_int(max_age_seconds, "max_age_seconds") == 0
    ):
        raise ValueError("Use an aware reference time and a positive freshness limit")

    source_times = {}
    for name in ("capacity", "latency", "metrics", "pricing"):
        if name not in snapshot and name in ("metrics", "pricing"):
            continue
        observed = timestamp(mapping(snapshot.get(name), name).get("observed_at"))
        age = (as_of - observed).total_seconds()
        if age < 0 or age > max_age_seconds:
            raise StaleSnapshot(f"{name} evidence is outside the freshness window")
        source_times[name] = observed.isoformat()

    inventory = snapshot["capacity"]
    if inventory.get("pod_coverage") != "all-namespaces":
        raise ValueError("Use a pod export covering all namespaces")
    nodes = normalize_inventory(inventory.get("nodes"), inventory.get("pods"))
    reserves = _by_node(inventory.get("reserve_by_node", {}), nodes, UNITS)
    latency = _by_region(snapshot["latency"].get("rtt_ms_by_region"), "RTT")
    metrics = _by_node(snapshot["metrics"].get("usage_by_node"), nodes, UNITS[:2]) if "metrics" in snapshot else {}
    prices = _by_region(snapshot["pricing"].get("incremental_usd_per_replica_hour_by_region"),
                        "incremental USD/hour per replica") if "pricing" in snapshot else {}
    weights = mapping(snapshot.get("weights", {}), "weights")
    cost_weight = _nonnegative_number(weights.get("incremental_cost", 0), "incremental cost weight")
    headroom_weight = _nonnegative_number(weights.get("peak_pressure", 1), "pressure weight")
    move_weight = _nonnegative_number(weights.get("moved_replicas", 0.05), "movement weight")
    if cost_weight and not prices:
        raise ValueError("A positive cost weight requires incremental price estimates")

    free = {}
    remaining_by_node = {}
    pressure = {}
    regions = {}
    for name, node in nodes.items():
        booked = tuple(request + reserve for request, reserve in
                       zip(node.requested, reserves.get(name, (0, 0, 0))))
        remaining = tuple(max(0, total - used) for total, used in zip(node.allocatable, booked))
        remaining_by_node[name] = remaining
        if all(remaining) and node.ready and not (
            node.unschedulable or node.blocking_taint or not node.placement_region
        ):
            free[name] = remaining
            measured = metrics.get(name, (0, 0))
            pressure[name] = (*map(max, zip(booked, measured)), *node.allocatable[:2])
            regions[name] = node.placement_region

    demands, candidates, costs, groups = {}, {}, {}, {}
    rejections, current_regions, moved_units = {}, {}, set()
    for request in entries(snapshot.get("workloads"), "workloads"):
        request = mapping(request, "workload request")
        if request.keys() - {
            "name", "replicas", "cpu_mcpu_per_replica", "memory_mib_per_replica",
            "max_rtt_ms", "allowed_regions", "current_region", "current_replicas",
        }:
            raise ValueError("The workload specifies fields outside the snapshot placement model")
        name = identifier(request.get("name"), "workload name")
        replicas = nonnegative_int(request.get("replicas"), "replicas")
        cpu = nonnegative_int(request.get("cpu_mcpu_per_replica"), "CPU per replica")
        memory = nonnegative_int(request.get("memory_mib_per_replica"), "memory per replica")
        rtt_limit = _nonnegative_number(request.get("max_rtt_ms"), "maximum RTT")
        if not all((replicas, cpu, memory)) or name in rejections:
            raise ValueError("Each workload needs a unique name and positive replicas, CPU and memory")
        if len(demands) + replicas > 1000:
            raise ValueError("The snapshot exceeds the 1000-replica offline model limit")
        allowed = request.get("allowed_regions")
        if allowed is not None:
            allowed = {identifier(region, "allowed placement region")
                       for region in entries(allowed, "allowed regions")}
        current = request.get("current_region")
        current_count = nonnegative_int(request.get("current_replicas", 0), "current replica count")
        if current is not None:
            identifier(current, "current placement region")
        elif current_count:
            raise ValueError("Existing replicas need a current placement region")
        current_regions[name] = current
        rejected = rejections[name] = {}
        targets = []
        for target, node in nodes.items():
            region = node.placement_region
            reasons = []
            if not node.ready:
                reasons.append("not_ready")
            if node.unschedulable:
                reasons.append("unschedulable")
            if node.blocking_taint:
                reasons.append("blocking_taint")
            if not region:
                reasons.append("missing_placement_region")
            elif allowed is not None and region not in allowed:
                reasons.append("region_not_allowed")
            if region not in latency:
                reasons.append("missing_rtt")
            elif latency[region] > rtt_limit:
                reasons.append("rtt_limit")
            if cost_weight and region not in prices:
                reasons.append("missing_incremental_price")
            if any(need > available for need, available in
                   zip((cpu, memory, 1), remaining_by_node[target])):
                reasons.append("insufficient_node_capacity")
            if reasons:
                rejected[target] = reasons
            else:
                targets.append(target)
        if len(costs) + replicas * len(targets) > 100_000:
            raise ValueError("The snapshot exceeds the 100000-edge offline model limit")
        for ordinal in range(1, replicas + 1):
            unit = f"{name}/{ordinal}"
            groups[unit] = name
            demands[unit] = (cpu, memory, 1)
            candidates[unit] = targets
            if ordinal <= current_count:
                moved_units.add(unit)
            for target in targets:
                region = regions[target]
                costs[unit, target] = cost_weight * prices.get(region, 0)
                if unit in moved_units and region != current:
                    costs[unit, target] += move_weight
    if not demands:
        raise ValueError("The snapshot needs at least one workload")

    eligible = {target for targets in candidates.values() for target in targets}
    model = PlacementModel(
        demands, free, candidates, costs, groups, regions,
        {name: row for name, row in pressure.items() if name in eligible},
        headroom_weight,
    )
    return SnapshotModel(
        model, mode, source_times, nodes, reserves, latency, prices, rejections, current_regions, moved_units,
        {"incremental_cost": cost_weight, "peak_pressure": headroom_weight, "moved_replicas": move_weight},
    )


def explain(compiled, placement):
    model = compiled.model
    objective = score(model, placement) if placement is not None else None
    if placement is not None and objective is None:
        raise ValueError("The placement is incompatible with this snapshot")
    usage = {node: [0, 0, 0] for node in model.capacities}
    workloads = {}
    moved = 0
    price_terms = []
    for unit, target in (placement or {}).items():
        name = model.groups[unit]
        region = model.target_regions[target]
        result = workloads.setdefault(name, {
            "placement_region": region, "rtt_ms": compiled.latency[region],
            "replicas": 0, "node_replica_counts": Counter(),
        })
        result["replicas"] += 1
        result["node_replica_counts"][target] += 1
        if unit in compiled.moved_units and region != compiled.current_regions[name]:
            moved += 1
        usage[target] = [a + b for a, b in zip(usage[target], model.demands[unit])]
        price_terms.append(compiled.prices.get(region))
    nodes = {}
    for name, available in model.capacities.items():
        node = compiled.resources[name]
        nodes[name] = {
            "placement_region": node.placement_region,
            "aws_region": node.aws_region,
            "aws_zone": node.aws_zone,
            "allocatable": dict(zip(UNITS, node.allocatable)),
            "already_requested": dict(zip(UNITS, node.requested)),
            "explicit_reserve": dict(zip(UNITS, compiled.reserves.get(name, (0, 0, 0)))),
            "proposed": dict(zip(UNITS, usage[name])),
            "remaining": dict(zip(UNITS, (total - used for total, used in zip(available, usage[name])))),
            "projected_peak_pressure": projected_pressure(model, name, usage[name]) if name in model.pressure else None,
        }
    return {
        "schema_version": 1,
        "source_mode": compiled.mode,
        "source_times": compiled.source_times,
        "objective": objective,
        "objective_weights": compiled.weights,
        "projected_peak_pressure": (
            max(projected_pressure(model, name, usage[name]) for name in model.pressure)
            if placement else None
        ),
        "moved_replicas": moved if placement is not None else None,
        "estimated_incremental_usd_per_hour": sum(price_terms) if price_terms and None not in price_terms else None,
        "workloads": workloads,
        "nodes": nodes,
        "rejections": compiled.rejections,
    }
