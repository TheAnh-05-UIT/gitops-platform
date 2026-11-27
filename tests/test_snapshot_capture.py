import copy
import json
from pathlib import Path
import unittest

from optimizer.snapshot import build_snapshot_model, timestamp
from optimizer.snapshot_capture import assemble_snapshot

FIXTURE = Path(__file__).resolve().parents[1] / "optimizer/data/placement_snapshot_v1.json"
AT = "2026-11-26T12:00:00Z"


class SnapshotCaptureTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.nodes = self.template["capacity"]["nodes"]
        self.pods = self.template["capacity"]["pods"]
        self.metrics = {"apiVersion": "metrics.k8s.io/v1beta1", "kind": "NodeMetricsList", "items": [
            {"metadata": {"name": "worker-a"}, "timestamp": AT, "window": "30s",
             "usage": {"cpu": "420m", "memory": "180Mi"}},
        ]}

    def capture(self):
        return assemble_snapshot(self.template, self.nodes, self.pods, observed_at=AT,
                                 revision="a" * 40, metrics=self.metrics)

    def test_normalized_metrics_and_freshness(self):
        self.template["mode"] = "observed"
        self.nodes["items"][0]["metadata"]["annotations"] = {"review": "synthetic-private-annotation"}
        self.pods["items"][0]["spec"]["containers"][0]["env"] = [{"name": "TEST", "value": "synthetic-private-env"}]
        result = self.capture()
        self.assertNotIn("synthetic-private", json.dumps(result))
        self.assertEqual(result["config_revision"], "a" * 40)
        self.assertEqual(result["mode"], "observed")
        self.assertEqual(result["metrics"]["usage_by_node"], {"worker-a": {"cpu_mcpu": 420, "memory_mib": 180}})
        self.assertEqual(build_snapshot_model(result, timestamp(AT), 300).mode, "observed")
        self.assertNotIn("config_revision", self.template)

    def test_refuses_to_relabel_demo_template_as_observed(self):
        with self.assertRaisesRegex(ValueError, "observed inputs"):
            self.capture()

    def test_duplicate_and_future_metrics_are_rejected(self):
        self.template["mode"] = "observed"
        entries = self.metrics["items"]
        entries.append(copy.deepcopy(entries[0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.capture()
        entries.pop()
        entries[0]["timestamp"] = "2026-11-26T12:01:00Z"
        with self.assertRaisesRegex(ValueError, "newer"):
            self.capture()
