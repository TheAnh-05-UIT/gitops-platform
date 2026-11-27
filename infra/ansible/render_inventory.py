"""Render Terraform inventory v1 as an SSH-free Ansible inventory, offline."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re

WORKERS = ("k3s-agent1", "k3s-agent2")
SERVER = "k3s-server"
REGION = r"[a-z]{2}(-[a-z]+)+-[1-9][0-9]*"
NAME = r"[a-z][a-z0-9]*(-[a-z0-9]+)*"
NODE_FIELDS = {
    "logical_id", "role", "instance_id", "private_ip", "public_ip",
    "availability_zone", "simulated_region",
}


def matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def ipv4(value):
    if not isinstance(value, str):
        raise ValueError("Expected an IPv4 address.")
    address = ipaddress.IPv4Address(value)
    if address.is_unspecified or address.is_loopback or address.is_multicast or address.is_link_local:
        raise ValueError("Invalid node IPv4 address.")
    return str(address)


def render_inventory(raw, environment, region, bucket):
    if not matches(NAME, environment) or len(environment) > 16 or not matches(REGION, region):
        raise ValueError("Invalid approved environment or Region.")
    if not matches(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Supply the approved private SSM transfer bucket name.")
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version", "environment", "aws_region", "lab_profile", "connection_strategy", "nodes", "groups",
    }:
        raise ValueError("Expected the Terraform inventory v1 envelope.")
    if (
        type(raw["schema_version"]) is not int or raw["schema_version"] != 1
        or raw["environment"] != environment or raw["aws_region"] != region
        or raw["connection_strategy"] != "ssm"
    ):
        raise ValueError("Inventory metadata does not match the approved SSM target.")

    nodes = raw["nodes"]
    profile = raw["lab_profile"]
    if not isinstance(nodes, dict) or not isinstance(profile, str):
        raise ValueError("Invalid lab node map.")
    allowed = {"minimal": (1,), "multi-node": (2, 3), "private": (2, 3)}
    if len(nodes) not in allowed.get(profile, ()):
        raise ValueError("Node count is incompatible with the lab profile.")
    workers = list(WORKERS[:len(nodes) - 1])
    groups = {"k3s": sorted([SERVER, *workers]), "k3s_server": [SERVER], "k3s_agents": workers}
    if set(nodes) != set(groups["k3s"]) or raw["groups"] != groups:
        raise ValueError("Inventory groups do not match the stable node IDs.")

    hosts = {}
    identities, addresses, public_ips, zones = set(), set(), set(), set()
    for name, node in sorted(nodes.items()):
        if not isinstance(node, dict) or set(node) != NODE_FIELDS:
            raise ValueError("Unexpected inventory node fields.")
        server = name == SERVER
        if (
            node["logical_id"] != name or node["role"] != ("server" if server else "worker")
            or not matches(r"i-([0-9a-f]{8}|[0-9a-f]{17})", node["instance_id"])
            or not matches(re.escape(region) + "[a-z]", node["availability_zone"])
        ):
            raise ValueError("Invalid node identity, AWS instance ID or Availability Zone.")
        labels = node["simulated_region"]
        if labels is not None and (not matches(REGION, labels) or len(labels) > 63):
            raise ValueError("Invalid simulated placement region.")
        if (labels is None) != (server and profile != "minimal"):
            raise ValueError("Unexpected placement eligibility in the inventory.")
        private_ip = ipv4(node["private_ip"])
        if profile == "private":
            if node["public_ip"] is not None:
                raise ValueError("Private nodes cannot have a public IP.")
        else:
            public_ips.add(ipv4(node["public_ip"]))
        identities.add(node["instance_id"])
        addresses.add(private_ip)
        zones.add(node["availability_zone"])
        hosts[name] = {
            "ansible_aws_ssm_instance_id": node["instance_id"],
            "node_private_ip": private_ip,
            "simulated_region": labels,
        }
    if len(identities) != len(nodes) or len(addresses) != len(nodes) or len(zones) != 1:
        raise ValueError("Duplicate node identity/address or inconsistent Availability Zone.")
    if profile != "private" and len(public_ips) != len(nodes):
        raise ValueError("Duplicate node public address.")

    return {"all": {"children": {"k3s": {
        "vars": {
            "ansible_connection": "amazon.aws.aws_ssm",
            "ansible_aws_ssm_region": region,
            "ansible_aws_ssm_bucket_name": bucket,
            "ansible_aws_ssm_bucket_sse_mode": "AES256",
            "lab_environment": environment,
        },
        "children": {
            group: {"hosts": {name: hosts[name] for name in groups[group]}}
            for group in ("k3s_server", "k3s_agents")
        },
    }}}}


def write_inventory(path, inventory):
    payload = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terraform-output", type=Path, required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--transfer-bucket", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        with args.terraform_output.open(encoding="utf-8-sig") as stream:
            raw = json.load(stream)
        output = render_inventory(raw, args.environment, args.region, args.transfer_bucket)
        write_inventory(args.output, output)
    except (OSError, ValueError) as exc:
        # Parse/address errors can include input values. Do not emit them to shared logs.
        parser.exit(1, f"Inventory handoff failed ({type(exc).__name__}). Verify the approved inputs and use a new protected output file.\n")


if __name__ == "__main__":
    main()
