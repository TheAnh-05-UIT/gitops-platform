import argparse
import csv
import json
from pathlib import Path

import pulp

DATA_DIR = Path(__file__).resolve().parent / "data"


def read_csv(filename, key):
    with (DATA_DIR / filename).open(encoding="utf-8-sig", newline="") as file:
        rows = {}
        for row in csv.DictReader(file):
            name = row[key]
            if name in rows:
                raise ValueError(f"{filename}: duplicate {key} {name!r}")
            rows[name] = row
    return rows


def solve_placement(regions, latency, cpu_mcpu, memory_mib, max_rtt_ms):
    if not regions or set(regions) != set(latency):
        raise ValueError("regions.csv and latency.csv must contain the same regions.")

    problem = pulp.LpProblem("workload_placement", pulp.LpMinimize)
    selected = {
        region: pulp.LpVariable(f"select_{index}", cat="Binary")
        for index, region in enumerate(regions)
    }
    problem += pulp.lpSum(selected.values()) == 1

    costs = {}
    rejected = {}

    for region, row in regions.items():
        cpu_capacity = int(row["cpu_mcpu"])
        memory_capacity = int(row["memory_mib"])
        price = float(row["price_usd_per_hour"])
        rtt = int(latency[region]["rtt_ms"])

        if cpu_capacity <= 0 or memory_capacity <= 0 or price < 0 or rtt < 0:
            raise ValueError(f"{region}: invalid capacity, price or RTT.")

        costs[region] = price * max(
            cpu_mcpu / cpu_capacity,
            memory_mib / memory_capacity,
        )

        reasons = []
        if cpu_mcpu > cpu_capacity:
            reasons.append("insufficient CPU")
        if memory_mib > memory_capacity:
            reasons.append("insufficient memory")
        if rtt > max_rtt_ms:
            reasons.append(f"RTT {rtt} ms exceeds {max_rtt_ms} ms")

        if reasons:
            problem += selected[region] == 0
            rejected[region] = reasons

    problem += pulp.lpSum(
        costs[region] * variable for region, variable in selected.items()
    )

    status = pulp.LpStatus[problem.solve(pulp.PULP_CBC_CMD(msg=False))]

    if status != "Optimal":
        return {"status": status, "region": None, "rejected": rejected}

    region = next(
        region for region, variable in selected.items()
        if pulp.value(variable) > 0.5
    )
    return {
        "status": status,
        "region": region,
        "estimated_cost_usd_per_hour": round(costs[region], 6),
        "rtt_ms": int(latency[region]["rtt_ms"]),
        "rejected": rejected,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", default="workload-api")
    parser.add_argument("--replicas", type=int)
    parser.add_argument("--max-rtt-ms", type=int)
    args = parser.parse_args()

    try:
        regions = read_csv("regions.csv", "region")
        latency = read_csv("latency.csv", "region")
        service = read_csv("services.csv", "service")[args.service]

        replicas = (
            args.replicas if args.replicas is not None else int(service["replicas"])
        )
        max_rtt_ms = (
            args.max_rtt_ms
            if args.max_rtt_ms is not None
            else int(service["max_rtt_ms"])
        )
        cpu_per_replica = int(service["cpu_mcpu_per_replica"])
        memory_per_replica = int(service["memory_mib_per_replica"])

        if min(replicas, cpu_per_replica, memory_per_replica) <= 0 or max_rtt_ms < 0:
            raise ValueError("Replicas and resource requests must be positive; RTT must be non-negative.")

        result = solve_placement(
            regions,
            latency,
            cpu_per_replica * replicas,
            memory_per_replica * replicas,
            max_rtt_ms,
        )
    except (OSError, KeyError, ValueError, pulp.PulpSolverError) as error:
        parser.error(str(error))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()