"""Exercise the AWS-free inventory handoff using Terraform's v1 fixtures."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "infra/terraform/modules/ansible-inventory/tests/fixtures"
SPEC = importlib.util.spec_from_file_location("lab_inventory", ROOT / "infra/ansible/render_inventory.py")
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def fixture(profile):
    return json.loads((FIXTURES / f"{profile}.json").read_text(encoding="utf-8"))


class InventoryTests(unittest.TestCase):
    def convert(self, raw, environment="lab", region="us-east-1"):
        return inventory.render_inventory(raw, environment, region, "example-lab-transfer")

    def test_profiles_use_ssm_without_public_ip_or_secrets(self):
        for profile in ("minimal", "multi-node", "private"):
            with self.subTest(profile=profile):
                source = fixture(profile)
                cluster = self.convert(source)["all"]["children"]["k3s"]
                self.assertEqual(cluster["vars"]["ansible_connection"], "amazon.aws.aws_ssm")
                self.assertEqual(cluster["vars"]["ansible_aws_ssm_region"], "us-east-1")
                self.assertEqual(cluster["vars"]["ansible_aws_ssm_bucket_name"], "example-lab-transfer")
                for group in ("k3s_server", "k3s_agents"):
                    hosts = cluster["children"][group]["hosts"]
                    self.assertEqual(sorted(hosts), sorted(source["groups"][group]))
                    for name, facts in hosts.items():
                        self.assertEqual(facts["ansible_aws_ssm_instance_id"], source["nodes"][name]["instance_id"])
                        self.assertEqual(facts["node_private_ip"], source["nodes"][name]["private_ip"])
                        self.assertNotIn("ansible_host", facts)
                        self.assertNotIn("public_ip", facts)

    def test_wrong_target_fails_closed(self):
        for environment, region in (("prod", "us-east-1"), ("lab", "us-west-2")):
            with self.assertRaises(ValueError):
                self.convert(fixture("multi-node"), environment, region)

    def test_rejects_invalid_topology_and_unsafe_labels(self):
        original = fixture("multi-node")
        for edit in (
            lambda raw: raw["groups"]["k3s_agents"].append("k3s-server"),
            lambda raw: raw["nodes"]["k3s-agent1"].update(instance_id=raw["nodes"]["k3s-server"]["instance_id"]),
            lambda raw: raw["nodes"]["k3s-agent1"].update(private_ip="::1"),
            lambda raw: raw["nodes"]["k3s-agent1"].update(simulated_region="--overwrite"),
            lambda raw: raw["nodes"]["k3s-agent1"].update(unexpected_token="fixture"),
            lambda raw: raw.update(schema_version=True),
        ):
            instance = copy.deepcopy(original)
            edit(instance)
            with self.subTest(raw=instance), self.assertRaises(ValueError):
                self.convert(instance)

    def test_write_is_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            inventory.write_inventory(path, self.convert(fixture("minimal")))
            first = path.read_bytes()
            with self.assertRaises(FileExistsError):
                inventory.write_inventory(path, {})
            self.assertEqual(path.read_bytes(), first)
