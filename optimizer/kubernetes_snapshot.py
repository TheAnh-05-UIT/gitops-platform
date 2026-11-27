"""Normalize saved Kubernetes API lists without using a cluster client."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import re


REGION_LABEL = "idp.example.com/region"
QUANTITY = re.compile(
    r"(?P<amount>\d+(?:\.\d*)?|\.\d+)(?P<suffix>[eE][+-]?\d+|[numkMGTPE]|[KMGTPE]i)?"
)
DNS_LABEL = re.compile(r"[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?")
FACTORS = {
    **{unit: Decimal(10) ** power for unit, power in zip("numkMGTPE", (-9, -6, -3, 3, 6, 9, 12, 15, 18))},
    **{unit + "i": Decimal(1024) ** index for index, unit in enumerate("KMGTPE", 1)},
}
UNITS = ("cpu_mcpu", "memory_mib", "pod_slots")


@dataclass(frozen=True)
class NodeCapacity:
    placement_region: str | None
    aws_region: str | None
    aws_zone: str | None
    ready: bool
    unschedulable: bool
    blocking_taint: bool
    allocatable: tuple
    requested: tuple


def mapping(value, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def entries(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def identifier(value, field):
    if not isinstance(value, str) or not DNS_LABEL.fullmatch(value):
        raise ValueError(f"{field} must be a DNS-style label")
    return value


def nonnegative_int(value, field):
    if type(value) is not int or not 0 <= value <= 10**12:
        raise ValueError(f"{field} must be a nonnegative bounded integer")
    return value


def _quantity(value):
    if type(value) not in (str, int):
        raise ValueError("Invalid Kubernetes quantity")
    value = str(value)
    match = QUANTITY.fullmatch(value) if len(value) <= 32 else None
    if not match:
        raise ValueError("Invalid Kubernetes quantity")
    amount = Decimal(match["amount"])
    suffix = match["suffix"]
    if suffix and len(suffix) > 1 and suffix[0] in "eE" and suffix not in FACTORS:
        exponent = int(suffix[1:])
        if not -18 <= exponent <= 18:
            raise ValueError("Kubernetes quantity exponent is out of range")
        return amount.scaleb(exponent)
    return amount * FACTORS.get(suffix, 1)


def _pair(resources):
    resources = mapping(resources, "CPU/memory resources")
    return [_quantity(resources.get("cpu", 0)) * 1000,
            _quantity(resources.get("memory", 0)) / (1024**2)]


def _round(value, mode):
    return nonnegative_int(int(value.to_integral_value(rounding=mode)), "resource quantity")


def request_units(resources):
    """Round effective CPU and memory requests up to the model's unit size."""
    return tuple(_round(value, ROUND_CEILING) for value in _pair(resources))


def _requests(container):
    resources = mapping(mapping(container, "container").get("resources", {}), "container resources")
    return _pair(resources.get("requests", {}))


def _pod_request(spec, status):
    if spec.get("resources") or status.get("resize") or any(
        item.get("type") in {"PodResizePending", "PodResizeInProgress"} and item.get("status") == "True"
        for item in map_conditions(status, "pod conditions")
    ):
        raise ValueError("Pod-level resource requests and in-progress resize are outside the snapshot model")
    running = [0, 0]
    for container in entries(spec.get("containers"), "pod containers"):
        running = [a + b for a, b in zip(running, _requests(container))]
    sidecars = [0, 0]
    init_peak = [0, 0]
    for container in entries(spec.get("initContainers", []), "init containers"):
        concurrent = [a + b for a, b in zip(sidecars, _requests(container))]
        init_peak = [max(a, b) for a, b in zip(init_peak, concurrent)]
        if container.get("restartPolicy") == "Always":
            sidecars = concurrent
    overhead = _pair(spec.get("overhead", {}))
    return (
        *(_round(max(steady + sidecar, initial) + extra, ROUND_CEILING)
          for steady, sidecar, initial, extra in zip(running, sidecars, init_peak, overhead)),
        1,
    )


def map_conditions(status, field):
    return [mapping(item, field) for item in entries(status.get("conditions", []), field)]


def _api_items(document, kind):
    document = mapping(document, kind)
    if document.get("kind") not in (kind, "List") or document.get("apiVersion") != "v1":
        raise ValueError(f"Expected a Kubernetes {kind} export")
    if mapping(document.get("metadata", {}), "list metadata").get("continue"):
        raise ValueError("A paginated Kubernetes export cannot be used as capacity evidence")
    items = [mapping(item, kind) for item in entries(document.get("items"), kind)]
    if document["kind"] == "List" and any(
        item.get("kind") != kind.removesuffix("List") or item.get("apiVersion") != "v1"
        for item in items
    ):
        raise ValueError(f"The Kubernetes List must contain only {kind.removesuffix('List')} objects")
    return items


def normalize_inventory(node_list, pod_list):
    nodes = {}
    for item in _api_items(node_list, "NodeList"):
        metadata = mapping(item.get("metadata"), "node metadata")
        name = metadata.get("name")
        if not isinstance(name, str) or len(name) > 253 or not all(
            DNS_LABEL.fullmatch(part) for part in name.split(".")
        ):
            raise ValueError("Invalid Kubernetes node name")
        if name in nodes:
            raise ValueError("Duplicate Kubernetes nodes")
        nodes[name] = item
    if not nodes:
        raise ValueError("The Kubernetes export has no nodes")

    booked = {name: [0, 0, 0] for name in nodes}
    pods_seen = set()
    for pod in _api_items(pod_list, "PodList"):
        metadata = mapping(pod.get("metadata"), "pod metadata")
        identifier(metadata.get("namespace"), "pod namespace")
        key = metadata.get("uid")
        if not isinstance(key, str) or not key or key in pods_seen:
            raise ValueError("Missing or duplicate Kubernetes pod UID")
        pods_seen.add(key)
        status = mapping(pod.get("status", {}), "pod status")
        if status.get("phase") in ("Succeeded", "Failed"):
            continue
        spec = mapping(pod.get("spec"), "pod specification")
        node = spec.get("nodeName")
        if not isinstance(node, str) or node not in booked:
            raise ValueError("The export contains an unbound pod or a pod outside the node inventory")
        booked[node] = [a + b for a, b in zip(booked[node], _pod_request(spec, status))]

    normalized = {}
    for name, item in sorted(nodes.items()):
        status = mapping(item.get("status"), "node status")
        spec = mapping(item.get("spec", {}), "node spec")
        labels = mapping(item["metadata"].get("labels", {}), "node labels")
        locations = [labels.get(label) for label in (
            REGION_LABEL, "topology.kubernetes.io/region", "topology.kubernetes.io/zone",
        )]
        for location in locations:
            if location is not None:
                identifier(location, "node topology")
        ready = any(
            condition.get("type") == "Ready" and condition.get("status") == "True"
            for condition in map_conditions(status, "node conditions")
        )
        blocking_taint = any(
            mapping(taint, "node taint").get("effect") in ("NoSchedule", "NoExecute")
            for taint in entries(spec.get("taints", []), "node taints")
        )
        allocatable = mapping(status.get("allocatable"), "node allocatable")
        if not {"cpu", "memory", "pods"} <= allocatable.keys():
            raise ValueError("Every node needs CPU, memory and pods allocatable")
        free = (
            *(_round(value, ROUND_FLOOR) for value in _pair(allocatable)),
            _round(_quantity(allocatable["pods"]), ROUND_FLOOR),
        )
        unschedulable = spec.get("unschedulable", False)
        if type(unschedulable) is not bool:
            raise ValueError("A node's unschedulable flag must be a boolean")
        normalized[name] = NodeCapacity(
            *locations, ready, unschedulable, blocking_taint, free, tuple(booked[name]),
        )
    return normalized
