---
name: optimization-engineering
description: Maintain PuLP placement models, CSV cost and capacity contracts, feasibility checks and reproducible solver benchmarks.
---

# Placement optimization

Take datasets, constraints, objective, scenario and solver version as inputs. Return a model change or review with feasibility, cost and reproducibility evidence.

1. Read `optimizer/ilp.py`, `optimizer/data/` and `benchmarks/compare_algorithms.py`. The portal has a single-service model and the benchmark compares multi-service algorithms. Check Helm resource requests if demand changes.
2. Verify assignment, RTT filtering, capacity accounting, cost units and solver statuses. Use feasible, infeasible and boundary fixtures. Label costs as model estimates.
3. Exercise CLI cases and compare ILP and exhaustive output below the combination limit. Validate reported placements with the scorer. Consider greedy no-solution separately from proven infeasibility.
4. Record fixture, solver, environment and limits. Report skipped or failed cases and keep timing and live-capacity claims tied to observed evidence.
