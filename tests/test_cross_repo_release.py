"""Check that approved artifacts match their consumers across all three repositories."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

import yaml

PLATFORM = Path(__file__).resolve().parents[1]
CONFIG = Path(os.environ.get("PLATFORM_CONFIG_CHECKOUT", PLATFORM.parent / "gitops-platform-config"))
WORKLOAD = Path(os.environ.get("PLATFORM_WORKLOAD_CHECKOUT", PLATFORM.parent / "gitops-platform-workload-api"))
DIGEST = "sha256:" + "a" * 64


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class ReleaseContract(unittest.TestCase):
    def test_config_and_workload_metrics_contract(self):
        service = load(CONFIG / "apps/workload-api/templates/service.yaml")
        monitoring_path = CONFIG / "observability/metrics/workload-monitoring.yaml"
        manifests = list(yaml.safe_load_all(monitoring_path.read_text(encoding="utf-8")))
        monitor = next(obj for obj in manifests if obj["kind"] == "ServiceMonitor")
        monitored_port = monitor["spec"]["endpoints"][0]
        self.assertEqual(service["spec"]["ports"][0]["name"], monitored_port["port"])
        workload = (WORKLOAD / "workload_api/app.py").read_text(encoding="utf-8")
        self.assertIn(f'("{monitored_port["path"]}")', workload)
        labels = monitor["spec"]["selector"]["matchLabels"]
        self.assertEqual({key: service["metadata"]["labels"][key] for key in labels}, labels)

    @unittest.skipUnless(shutil.which("helm"), "Helm unavailable")
    def test_demo_chart_image_and_worker_entrypoint(self):
        result = subprocess.check_output([
            "helm", "template", "demo-jobs", str(CONFIG / "apps/demo-jobs"), "-n", "workloads",
            "--set", f"enabled=true,imageDigest={DIGEST},placementRegion=eu-west-1",
        ])
        resources = {obj["kind"]: obj for obj in yaml.safe_load_all(result)}
        deployment = resources["Deployment"]["spec"]["template"]["spec"]
        cron_job = resources["CronJob"]["spec"]["jobTemplate"]["spec"]["template"]["spec"]
        for pod, role in ((deployment, "worker"), (cron_job, "batch")):
            container = pod["containers"][0]
            self.assertEqual(container["command"], ["python", "-B", "-m", "workload_api.demo_jobs"])
            self.assertEqual(container["args"], [role])
            self.assertTrue(container["image"].endswith(f"@{DIGEST}"))
        self.assertTrue((WORKLOAD / "workload_api/demo_jobs.py").is_file())

    @unittest.skipUnless(os.environ.get("PLATFORM_WORKLOAD_CHECKOUT"), "Assert hard stop on isolated release candidate")
    def test_isolated_release_candidate_keeps_hosted_gates_hard_disabled(self):
        for filename, name in (("ci.yml", "publish"), ("promotion-preview.yml", "preview")):
            workflow = load(WORKLOAD / ".github/workflows" / filename)
            self.assertRegex(workflow["jobs"][name]["if"], r"^false\s+&&")
        control = load(CONFIG / "promotion/workload-api.yaml")
        self.assertIs(control["frozen"], True)
        self.assertIsNone(control["request"])
        for repo in (CONFIG, WORKLOAD):
            for workflow in (repo / ".github/workflows").glob("*.yml"):
                uses = re.findall(r"(?m)^\s*(?:-\s*)?uses:\s+([^\s]+)", workflow.read_text(encoding="utf-8"))
                self.assertTrue(all(re.fullmatch(r"[\w./-]+@[a-f0-9]{40}", action) for action in uses))
