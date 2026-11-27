"""Verify the Terraform runner's isolation without launching Terraform."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("terraform_offline", ROOT / "scripts/terraform_offline.py")
offline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(offline)


class SourcePolicyTests(unittest.TestCase):
    def test_reviewed_source_passes_preflight_and_preserves_only_required_files(self):
        with tempfile.TemporaryDirectory() as temp:
            seeded = Path(temp) / "seeded"
            offline.copy_sources(ROOT / "infra/terraform", seeded)
            for artifact in ("terraform.tfstate", "lab.tfvars", "local.tfbackend", "env_override.tf"):
                (seeded / "lab" / artifact).write_text("placeholder", encoding="utf-8")
            copied = Path(temp) / "copy"
            offline.copy_sources(seeded, copied)
            offline.verify_sources(copied)
            backend = copied / "lab/backend.tf"
            self.assertIn('backend "s3"', backend.read_text(encoding="utf-8"))
            self.assertFalse(list(copied.rglob("*.tfstate*")))
            self.assertFalse(list(copied.rglob("*.tfvars")))
            self.assertFalse(list(copied.rglob("*.tfvars.json")))
            self.assertFalse(list(copied.rglob("*.tfbackend")))
            self.assertFalse(list(copied.rglob("*override.tf")))
            self.assertTrue((copied / "lab/examples/minimal.tfvars.json.example").is_file())

    def test_reject_infrastructure_that_could_contact_external_services(self):
        cases = [
            ('terraform { cloud {} }', offline.BOOTSTRAP),
            ('terraform { backend "s3" {} }', offline.BOOTSTRAP),
            ('data "aws_caller_identity" "account" {}', offline.LAB),
            ('resource "aws_instance" "demo" { provisioner "local-exec" {} }', offline.LAB),
            ('module "networking" { source = "https://example.com/code.zip" }', offline.LAB),
            ('provider "aws" { alias = "unmocked" }', offline.LAB),
        ]
        for source, suite in cases:
            with self.subTest(source=source), self.assertRaises(offline.UnsafeSource):
                offline.check_config(source, suite, "fixture.tf")

    def test_requires_explicit_mock_and_plan_for_every_run(self):
        invalid = [
            'run "one" { command = plan }',
            'mock_provider "aws" {} run "one" {}',
            'mock_provider "aws" {} run "one" { command = apply }',
            'mock_provider "aws" {} run "one" { command = plan } run "two" {}',
            'mock_provider "aws" {} run "one" { command = plan providers = { aws = aws.real } }',
            'mock_provider "aws" { source = "external" } run "one" { command = plan }',
            'mock_provider "aws" {} run "one" { command = plan module { source = "external" } }',
            'mock_provider "aws" {} run "one" { assert { command = plan } }',
        ]
        for content in invalid:
            with self.subTest(content=content), self.assertRaises(offline.UnsafeSource):
                offline.check_test(content, "unsafe.tftest.hcl", uses_aws=True)
        offline.check_test('run "inventory" { command = plan }', "plain.tftest.hcl", uses_aws=False)
        offline.check_test(
            '# comment\nmock_provider "aws" {} run "one" { command = plan }',
            "safe.tftest.hcl",
            uses_aws=True,
        )


class ExecutionPolicyTests(unittest.TestCase):
    def test_environment_discards_inherited_cloud_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            scratch = Path(temp)
            environment = offline.offline_environment(
                scratch,
                {
                    "AWS_SECRET_ACCESS_KEY": "fixture",
                    "AWS_PROFILE": "fixture",
                    "Tf_Cli_Args": "fixture",
                    "TF_LOG_PATH": "fixture",
                    "GODEBUG": "fixture",
                    "PATH": "kept",
                },
            )
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", environment)
            self.assertNotIn("AWS_PROFILE", environment)
            self.assertNotIn("Tf_Cli_Args", environment)
            self.assertNotIn("TF_LOG_PATH", environment)
            self.assertEqual(environment["PATH"], "kept")
            self.assertEqual(environment["CHECKPOINT_DISABLE"], "1")
            self.assertEqual(environment["AWS_EC2_METADATA_DISABLED"], "true")
            for key in ("AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE", "TF_CLI_CONFIG_FILE"):
                path = Path(environment[key])
                self.assertEqual(path.parent, scratch)
                self.assertEqual(path.read_text(encoding="utf-8"), "")

    def test_suite_uses_backend_disabled_init_and_local_override_only_for_lab_tests(self):
        events = []

        def capture(command, cwd, env, check):
            overrides = [path.read_text(encoding="utf-8") for path in cwd.glob("*_override.tf")]
            events.append((command, cwd, env["TF_DATA_DIR"], check, overrides))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for suite in (offline.BOOTSTRAP, offline.LAB):
                workdir = root / "source" / suite
                workdir.mkdir(parents=True)
                offline.run_suite(root, suite, Path("approved-mirror"), {}, execute=capture)
            for offset in (0, 3):
                init, validate, test = events[offset:offset + 3]
                self.assertIn("-backend=false", init[0])
                self.assertIn("-lockfile=readonly", init[0])
                self.assertIn("-plugin-dir=approved-mirror", init[0])
                self.assertEqual(validate[0][1], "validate")
                self.assertEqual(test[0][1], "test")
                self.assertFalse(init[4] or validate[4])
                self.assertEqual(init[2], validate[2])
                self.assertEqual(validate[2], test[2])
            self.assertFalse(events[2][4])
            self.assertIn('backend "local" {}', events[5][4][0])
            self.assertNotEqual(events[2][2], events[5][2])


if __name__ == "__main__":
    unittest.main()
