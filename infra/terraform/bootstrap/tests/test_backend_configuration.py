import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

BOOTSTRAP = Path(__file__).resolve().parents[1]
LAB = BOOTSTRAP.parent / "lab"
sys.path.insert(0, str(BOOTSTRAP))
from render_backend_config import render_backend


def manifest(environment="lab", project="gitops-platform"):
    prefix = f"terraform-state/{project}/{environment}"
    return {
        "account_id": "000000000000",
        "project_name": project,
        "environment": environment,
        "bucket": "example-platform-lab-tfstate-a1b2",
        "region": "us-east-1",
        "key": f"{prefix}/terraform.tfstate",
        "lock_key": f"{prefix}/terraform.tfstate.tflock",
        "workspace_key_prefix": f"{prefix}/workspaces",
        "encrypt": True,
        "use_lockfile": True,
    }


class BackendConfigurationTest(unittest.TestCase):
    def test_lab_declares_partial_backend_with_mandatory_controls(self):
        backend = (LAB / "backend.tf").read_text(encoding="utf-8")
        self.assertRegex(
            backend,
            r'(?s)^\s*terraform\s*{\s*backend "s3"\s*{\s*encrypt\s*=\s*true\s*use_lockfile\s*=\s*true\s*}\s*}\s*$',
        )
        bootstrap_source = "\n".join(path.read_text(encoding="utf-8") for path in BOOTSTRAP.glob("*.tf"))
        self.assertNotRegex(bootstrap_source, r'(?m)^\s*backend\s+"')
        self.assertNotRegex(bootstrap_source, r'(?m)^\s*(?:resource|data)\s+"aws_(?:dynamodb|kms)\w*"')
        self.assertRegex(bootstrap_source, r'(?m)^\s*prevent_destroy\s*=\s*true\s*$')

    def test_examples_match_generated_config_and_contain_no_auth(self):
        expected = render_backend(manifest(), {"aws_region": "us-east-1"}, "000000000000")
        example = (LAB / "examples/lab.s3.tfbackend.example").read_text(encoding="utf-8").splitlines()
        example_settings = [line.strip() for line in example if line.strip() and not line.startswith("#")]
        self.assertEqual(example_settings, expected.splitlines())
        self.assertNotRegex(expected, r"(?i)access_key|secret_key|session_token|dynamodb_table")

    def test_environment_and_project_use_distinct_state_objects(self):
        initial = render_backend(manifest(), {"aws_region": "us-east-1"}, "000000000000")
        for candidate in (manifest(environment="demo"), manifest(project="other-platform")):
            rendered = render_backend(candidate, {
                "aws_region": "us-east-1",
                "environment": candidate["environment"],
                "project_name": candidate["project_name"],
            }, "000000000000")
            self.assertNotEqual(initial, rendered)
            self.assertIn(candidate["key"], rendered)
            self.assertIn(candidate["workspace_key_prefix"], rendered)
            self.assertNotIn(manifest()["key"], rendered)

    def test_rejects_wrong_environment_project_region_or_account(self):
        for overrides in (
            {"environment": "demo"}, {"project_name": "other-platform"}, {"aws_region": "us-west-2"}
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                render_backend(manifest(), {"aws_region": "us-east-1", **overrides}, "000000000000")
        with self.assertRaises(ValueError):
            render_backend(manifest(), {"aws_region": "us-east-1"}, "111111111111")

    def test_rejects_changed_keys_or_disabled_controls(self):
        for field, value in {
            "key": "custom.tfstate", "lock_key": "other.tflock", "workspace_key_prefix": "env:",
            "encrypt": False, "use_lockfile": 1, "bucket": "example-not-a-state-bucket--x-s3",
        }.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                render_backend({**manifest(), field: value}, {"aws_region": "us-east-1"}, "000000000000")

    def test_bootstrap_role_template_has_no_object_or_delete_grants(self):
        template = BOOTSTRAP / "examples/bootstrap-execution-policy.json.example"
        policy = json.loads(template.read_text(encoding="utf-8"))
        self.assertEqual(policy["Version"], "2012-10-17")
        self.assertEqual(len(policy["Statement"]), 2)
        for statement in policy["Statement"]:
            self.assertEqual(statement["Effect"], "Allow")
            self.assertEqual(statement["Resource"], "arn:__PARTITION__:s3:::__BUCKET__")
            self.assertTrue(all(action.startswith("s3:") and "*" not in action for action in statement["Action"]))
            self.assertTrue(all("Delete" not in action and "ObjectVersion" not in action
                                for action in statement["Action"]))
            self.assertTrue({"s3:GetObject", "s3:PutObject"}.isdisjoint(statement["Action"]))
        self.assertEqual(policy["Statement"][1]["Condition"], {"StringEquals": {"aws:RequestedRegion": "__REGION__"}})

    def test_cli_creates_only_a_new_backend_file(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            bootstrap_output = tmp / "bootstrap.json"
            bootstrap_output.write_text(json.dumps(manifest()), encoding="utf-8")
            tfvars = tmp / "lab.tfvars.json"
            tfvars.write_text(json.dumps({"aws_region": "us-east-1"}), encoding="utf-8")
            destination = tmp / "lab.s3.tfbackend"
            command = [
                sys.executable, "-B", str(BOOTSTRAP / "render_backend_config.py"),
                "--bootstrap-output", str(bootstrap_output), "--lab-tfvars", str(tfvars),
                "--account-id", "000000000000", "--out", str(destination),
            ]
            created = subprocess.run(command, capture_output=True, check=False)
            self.assertEqual(created.returncode, 0, created.stderr)
            original = destination.read_bytes()
            rejected = subprocess.run(command, capture_output=True, check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(destination.read_bytes(), original)
