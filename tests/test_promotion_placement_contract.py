"""Exercise the real Portal YAML patcher against Config promotion guards."""

import base64
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portal.github_client import create_placement_pull_request

CONFIG = Path(os.environ.get("PLATFORM_CONFIG_CHECKOUT", Path(__file__).resolve().parents[2] / "gitops-platform-config"))
sys.path.insert(0, str(CONFIG))

from scripts.promotion_policy import (  # sibling checkout contract
    CONTROL_PATH, REVERTED_SHA, VALUES_PATH, PolicyError, guard, load_yaml,
    patch_tag, read_state,
)

NEXT = "a" * 40


def placement_proposal(values):
    encoded = base64.b64encode(values.encode()).decode()
    replies = [
        {"object": {"sha": "fixture"}},
        {"sha": "fixture-file", "content": encoded},
        {}, {}, {"number": 1},
    ]
    with patch("portal.github_client.github_request", side_effect=replies) as api:
        create_placement_pull_request("fixture/config", "synthetic", 3, "eu-west-1")
    written = api.call_args_list[3].kwargs["json"]["content"]
    return base64.b64decode(written).decode()


def merge_values(current, base, proposed):
    with tempfile.TemporaryDirectory() as folder:
        paths = [Path(folder) / name for name in ("current", "base", "proposed")]
        for path, values in zip(paths, (current, base, proposed)):
            path.write_bytes(values.encode())
        return subprocess.check_output(["git", "merge-file", "-p", *paths]).decode()


class PlacementContractTests(unittest.TestCase):
    def setUp(self):
        self.base = (CONFIG / VALUES_PATH).read_bytes().decode()
        state = load_yaml((CONFIG / CONTROL_PATH).read_bytes())
        state.update(generation=1, frozen=False, request={
            "id": "workload-api-g1", "mode": "promote", "sha": NEXT,
            "digest": "sha256:" + "a" * 64, "run_id": 1, "run_attempt": 1,
            "expected_tag": load_yaml(self.base)["image"]["tag"],
            "decision": "Synthetic promotion", "replaces_blocks": [],
        })
        self.state = read_state(state)
        self.placement = placement_proposal(self.base)
        self.promotion = patch_tag(self.base, NEXT)

    def assert_combined(self, merged):
        result = load_yaml(merged)
        self.assertEqual(result["replicaCount"], 3)
        self.assertEqual(result["nodeSelector"], {"idp.example.com/region": "eu-west-1"})
        self.assertEqual(result["image"]["tag"], NEXT)
        self.assertEqual(result["resources"], load_yaml(self.base)["resources"])

    def test_placement_then_promotion_preserves_both(self):
        self.assertEqual(guard(self.state, self.state, self.base, self.placement, {VALUES_PATH}), "unchanged-image")
        with self.assertRaises(PolicyError):
            guard(self.state, self.state, self.placement, self.promotion, {VALUES_PATH},
                  head_ref=self.state.request.branch)
        merged = merge_values(self.placement, self.base, self.promotion)
        self.assertEqual(guard(self.state, self.state, self.placement, merged, {VALUES_PATH},
                               head_ref=self.state.request.branch), "promotion")
        self.assert_combined(merged)

    def test_promotion_then_placement_preserves_both(self):
        self.assertEqual(guard(self.state, self.state, self.base, self.promotion, {VALUES_PATH},
                               head_ref=self.state.request.branch), "promotion")
        merged = merge_values(self.promotion, self.base, self.placement)
        self.assertEqual(guard(self.state, self.state, self.promotion, merged, {VALUES_PATH}), "unchanged-image")
        self.assert_combined(merged)

    def test_rollback_blocks_outstanding_promotion_after_placement(self):
        rollback = read_state({
            "generation": 2, "frozen": True, "request": None,
            "blocked_images": [
                {"sha": REVERTED_SHA, "digest": None, "reason": "Historical revert"},
                {"sha": NEXT, "digest": self.state.request.digest, "reason": "Lab rollback"},
            ],
        })
        preview = patch_tag(self.placement, NEXT)
        with self.assertRaises(PolicyError):
            guard(rollback, rollback, self.placement, preview, {VALUES_PATH},
                  head_ref=self.state.request.branch)
