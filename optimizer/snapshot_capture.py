"""Assemble an observed snapshot from offline Kubernetes exports."""

import argparse
import json
from pathlib import Path
import re

from optimizer.kubernetes_snapshot import UNITS, entries, mapping, request_units
from optimizer.snapshot import build_snapshot_model, timestamp

TOPOLOGY = ("topology.kubernetes.io/region", "topology.kubernetes.io/zone")
SELECTOR = "idp.example.com/region"


def _only(data, fields):
    return {field: data[field] for field in fields if field in data}


def _export(document, normalize):
    document = mapping(document, "Kubernetes export")
    return {**_only(document, ("kind", "apiVersion")), "metadata": _only(document.get("metadata", {}), ("continue",)),
            "items": [{**_only(item, ("kind", "apiVersion")), **normalize(item)} for item in entries(document.get("items"), "items")]}


def _node(item, locations):
    metadata = item.get("metadata", {})
    name = metadata.get("name")
    labels = _only(metadata.get("labels", {}), (SELECTOR, *TOPOLOGY))
    if name in locations:
        for key, value in zip(TOPOLOGY, locations[name]):
            if key in labels and labels[key] != value:
                raise ValueError("Inventory and Node topology disagree")
            labels[key] = value
    status = item.get("status", {})
    return {
        "metadata": {"name": name, "labels": labels},
        "spec": {**_only(item.get("spec", {}), ("unschedulable",)),
                 "taints": [_only(row, ("effect",)) for row in item.get("spec", {}).get("taints", [])]},
        "status": {**_only(status, ("allocatable",)),
                   "conditions": [_only(row, ("type", "status")) for row in status.get("conditions", [])]},
    }


def _pod(item):
    source = item.get("spec", {})
    spec = _only(source, ("nodeName", "resources", "overhead"))
    for group in ("containers", "initContainers"):
        if group in source:
            spec[group] = [
                {**_only(container, ("restartPolicy",)),
                 "resources": _only(container.get("resources", {}), ("requests",))}
                for container in entries(source[group], group)
            ]
    status = item.get("status", {})
    return {"metadata": _only(item.get("metadata", {}), ("namespace", "uid")), "spec": spec,
            "status": {**_only(status, ("phase", "resize")),
                       "conditions": [_only(row, ("type", "status")) for row in status.get("conditions", [])]}}


def _locations(inventory):
    if inventory is None:
        return {}
    data = mapping(inventory, "Terraform inventory")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("Expected Terraform inventory v1")
    region = data.get("aws_region")
    if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(-[a-z]+)+-[1-9][0-9]*", region):
        raise ValueError("Unexpected physical AWS Region")
    result = {}
    for name, node in mapping(data.get("nodes"), "Terraform nodes").items():
        zone = node.get("availability_zone")
        if not isinstance(zone, str) or not re.fullmatch(re.escape(region) + "[a-z]", zone):
            raise ValueError("Unexpected physical AWS Availability Zone")
        result[name] = (region, zone)
    return result


def _metrics(document, captured):
    document = mapping(document, "Node metrics export")
    if (document.get("kind") != "NodeMetricsList" or document.get("apiVersion") != "metrics.k8s.io/v1beta1"
            or document.get("metadata", {}).get("continue")):
        raise ValueError("Use a complete metrics.k8s.io/v1beta1 NodeMetricsList")
    observed = []
    by_node = {}
    for item in entries(document.get("items"), "node metrics"):
        name = item["metadata"]["name"]
        if name in by_node:
            raise ValueError("Duplicate node metrics")
        when = timestamp(item["timestamp"])
        if when > captured:
            raise ValueError("Metrics are newer than the capture")
        observed.append(when)
        usage = mapping(item["usage"], "node usage")
        if not {"cpu", "memory"} <= usage.keys():
            raise ValueError("Expected measured CPU and memory")
        by_node[name] = dict(zip(UNITS[:2], request_units(usage)))
    if not observed:
        raise ValueError("Empty metrics capture")
    return {"observed_at": min(observed).isoformat(), "usage_by_node": by_node}


def assemble_snapshot(inputs, nodes, pods, *, observed_at, revision, metrics=None, inventory=None, max_age=300):
    inputs = mapping(inputs, "Reviewed placement inputs")
    if inputs.get("mode") != "observed":
        raise ValueError("Use explicitly reviewed observed inputs for RTT, demand and pricing")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected the reviewed Config commit SHA")
    captured = timestamp(observed_at)
    locations = _locations(inventory)
    capacity = {
        "observed_at": captured.isoformat(), "pod_coverage": "all-namespaces",
        "nodes": _export(nodes, lambda row: _node(row, locations)),
        "pods": _export(pods, _pod),
        **_only(inputs.get("capacity", {}), ("reserve_by_node",)),
    }
    if locations and set(locations) != {row["metadata"]["name"] for row in capacity["nodes"]["items"]}:
        raise ValueError("Terraform inventory and Kubernetes export contain different nodes")
    snapshot = {
        **_only(inputs, ("schema_version", "mode", "latency", "pricing", "workloads", "weights")),
        "config_revision": revision, "capacity": capacity,
    }
    if metrics is not None:
        snapshot["metrics"] = _metrics(metrics, captured)
    build_snapshot_model(snapshot, captured, max_age)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("inputs", "nodes", "pods", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--observed-at", required=True)
    args = parser.parse_args()

    def load(path):
        return json.loads(path.read_text(encoding="utf-8-sig")) if path else None

    try:
        snapshot = assemble_snapshot(load(args.inputs), load(args.nodes), load(args.pods),
                                     observed_at=args.observed_at, revision=args.revision,
                                     metrics=load(args.metrics), inventory=load(args.inventory))
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(snapshot, out, indent=2, sort_keys=True)
            out.write("\n")
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        parser.exit(1, "Snapshot assembly failed. Check the reviewed inputs, capture window and output path.\n")


if __name__ == "__main__":
    main()
