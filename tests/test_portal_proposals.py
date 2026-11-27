import base64
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from portal.app import create_app
from portal.github_client import GitHubError, prepare_change, submit_change
from portal.status import observed_status

BASE = "a" * 40
BLOB = "b" * 40
HEAD = "d" * 40
BOT = 123
VALUES = """image:
  repository: ghcr.io/fixture/api
  tag: immutable-fixture
replicaCount: 2
nodeSelector:
  idp.example.com/region: ap-southeast-1
autoscaling:
  enabled: false
"""
PATH = "apps/workload-api/values.yaml"


def snapshot(values=VALUES, base=BASE):
    return {"object": {"sha": base}}, {"content": base64.b64encode(values.encode()).decode(), "sha": BLOB}


class GitHubProposalTests(unittest.TestCase):
    def test_preview_only_reads_and_patch_has_exact_scope(self):
        with patch("portal.github_client.github_request", side_effect=snapshot()) as api:
            change = prepare_change("fixture/config", "fixture-read", 3, "eu-west-1")
        self.assertEqual([call.args[0] for call in api.call_args_list], ["GET", "GET"])
        self.assertIn(f"+++ b/{PATH}", change.diff)
        self.assertIn("+replicaCount: 3", change.diff)
        self.assertIn("+  idp.example.com/region: eu-west-1", change.diff)
        self.assertIn("tag: immutable-fixture", change.updated)

    def test_hpa_and_ambiguous_contract_reject_fixed_placement(self):
        for values in (VALUES.replace("false", "true"), VALUES + "\n  enabled: true\n", VALUES.replace("enabled:", "'enabled':"),
                       VALUES + "autoscaling: {enabled: true}\n", VALUES.replace("autoscaling:", '"autoscaling":'),
                       VALUES.replace("autoscaling:", "  'idp.example.com/region': eu-west-1\nautoscaling:")):
            with self.subTest(values=values), patch("portal.github_client.github_request", side_effect=snapshot(values)):
                with self.assertRaises(GitHubError):
                    prepare_change("fixture/config", "fixture-read", 3, "eu-west-1")

    def test_matching_request_is_reused_without_write(self):
        change = prepare_fixture()
        existing = [{"number": 19, "body": "<!-- idp-request:" + "c" * 32 + " -->", "user": {"id": BOT},
                     "head": {"ref": "portal/workload-api-" + "c" * 32,
                              "sha": HEAD, "repo": {"full_name": "fixture/config"}},
                     "base": {"ref": "main", "repo": {"full_name": "fixture/config"}}}]
        commit = {"sha": HEAD, "author": {"id": BOT}, "parents": [{"sha": BASE}],
                  "files": [{"filename": PATH, "status": "modified"}]}
        with patch("portal.github_client.github_request", side_effect=[existing, commit, snapshot(change.updated)[1]]) as api:
            self.assertEqual(submit_change(change, "fixture-write", "c" * 32, "placement", BOT), 19)
            self.assertTrue(all(call.args[0] == "GET" for call in api.call_args_list))
        commit["files"].append({"filename": "another-file", "status": "modified"})
        with patch("portal.github_client.github_request", side_effect=[existing, commit]) as api, self.assertRaises(GitHubError):
            submit_change(change, "fixture-write", "c" * 32, "placement", BOT)
        self.assertTrue(all(call.args[0] == "GET" for call in api.call_args_list))

    def test_fresh_pr_confirmation_rejects_a_race_on_head(self):
        change = prepare_fixture()
        rid = "c" * 32
        commit = {"sha": HEAD, "author": {"id": BOT}, "parents": [{"sha": BASE}],
                  "files": [{"filename": PATH, "status": "modified"}]}
        response = {"number": 19, "body": f"<!-- idp-request:{rid} -->", "user": {"id": BOT},
                    "head": {"ref": f"portal/workload-api-{rid}", "sha": "e" * 40,
                             "repo": {"full_name": "fixture/config"}},
                    "base": {"ref": "main", "repo": {"full_name": "fixture/config"}}}
        api = [[], {}, {}, {"object": {"sha": HEAD}}, commit, snapshot(change.updated)[1], response]
        with patch("portal.github_client.github_request", side_effect=api), self.assertRaisesRegex(GitHubError, "Nhánh đã thay đổi"):
            submit_change(change, "fixture-write", rid, "placement", BOT)


def prepare_fixture():
    with patch("portal.github_client.github_request", side_effect=snapshot()):
        return prepare_change("fixture/config", "fixture-read", 3, "eu-west-1")


class PortalProposalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        acl = Path(directory.name) / "acl.json"
        self.audit_file = Path(directory.name) / "audit.jsonl"
        acl.write_text('{"subjects":{"requester":{"workload-api":"deployer"},"other":{"workload-api":"deployer"}}}')
        self.app = create_app({"TESTING": True, "SECRET_KEY": "fixture-" * 8, "PORTAL_ACL_FILE": str(acl),
                               "GITOPS_CONFIG_REPO": "fixture/config", "PORTAL_GITHUB_READ_TOKEN": "fixture-read",
                               "PORTAL_GITHUB_TOKEN": "fixture-write", "PORTAL_WRITES_ENABLED": True,
                               "PORTAL_AUDIT_FILE": str(self.audit_file),
                               "PORTAL_GITHUB_BOT_ID": BOT, "PORTAL_ALLOW_SIMULATION_PROPOSALS": True})
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session.update(subject="requester", expires=int(time.time()) + 90, csrf_token="fixture")

    def preview(self):
        return self.client.post("/", data={"csrf_token": "fixture", "action": "preview", "replicas": 3, "max_rtt_ms": 180})

    def test_preview_does_not_write(self):
        with patch("portal.app.prepare_change", return_value=prepare_fixture()), patch("portal.app.submit_change") as submit:
            result = self.preview()
        self.assertEqual(result.status_code, 200)
        self.assertIn(b"+replicaCount: 3", result.data)
        self.assertIn(b'name="proposal"', result.data)
        submit.assert_not_called()

    def test_submit_requires_unmodified_actor_bound_preview_and_csrf(self):
        for payload in ({"proposal": "invalid", "csrf_token": "fixture"}, {"proposal": "invalid", "csrf_token": "bad"}):
            with patch("portal.app.submit_change") as write:
                response = self.client.post("/", data={"action": "submit", **payload})
                self.assertEqual(response.status_code, 400)
                write.assert_not_called()

    def test_closed_write_gate_denies_submission(self):
        self.app.config["PORTAL_WRITES_ENABLED"] = False
        with patch("portal.app.submit_change") as write:
            response = self.client.post("/", data={"action": "submit", "csrf_token": "fixture"})
        self.assertEqual(response.status_code, 403)
        write.assert_not_called()

    def test_stale_base_is_rejected_and_same_approved_scope_can_submit(self):
        import re
        change = prepare_fixture()
        evidence = {"source_mode": "simulation", "workloads": {"workload-api": {"placement_region": change.region}},
                    "rejections": {}}
        with patch("portal.app._snapshot_placement", return_value=("Optimal", evidence)), \
             patch("portal.app.prepare_change", return_value=change):
            proposal = re.search(rb'name="proposal" value="([^" ]+)"', self.preview().data)[1].decode()
        params = {"action": "submit", "proposal": proposal, "csrf_token": "fixture"}
        from dataclasses import replace
        with patch("portal.app.observed_status", return_value={"compared_revision": BASE}), \
             patch("portal.app._snapshot_placement", return_value=("Optimal", evidence)), \
             patch("portal.app.prepare_change", return_value=replace(change, base="e" * 40)) as prepare, \
             patch("portal.app.submit_change", return_value=17) as write:
            self.assertEqual(self.client.post("/", data=params).status_code, 409)
            write.assert_not_called()
            prepare.return_value = change
            confirmed = self.client.post("/", data=params)
            self.assertEqual(confirmed.status_code, 200)
            self.assertIn(b"/pull/17", confirmed.data)
            write.assert_called_once()
            recorded = [json.loads(line) for line in self.audit_file.read_text().splitlines()]
            self.assertEqual([row["event"] for row in recorded], ["submit_started", "submit_confirmed"])
            self.app.config["PORTAL_AUDIT_FILE"] = None
            self.assertEqual(self.client.post("/", data=params).status_code, 503)
            write.assert_called_once()

    def test_out_of_sync_comparison_does_not_become_deployed_revision(self):
        source = {"repoURL": "https://github.com/fixture/config.git", "path": "apps/workload-api", "targetRevision": "main"}
        argo = {"metadata": {"name": "workload-api"}, "spec": {"project": "workload-lab", "source": source,
                "destination": {"namespace": "workloads", "server": "https://kubernetes.default.svc"}},
                "status": {"sync": {"status": "OutOfSync", "revision": HEAD}, "health": {"status": "Healthy"},
                           "history": [{"revision": BASE, "source": source, "deployedAt": "2026-11-26T08:00:00Z"}]}}
        with patch("portal.status.requests.get") as get:
            get.return_value.status_code = 200
            get.return_value.json.return_value = argo
            result = observed_status("https://argo.example.test", "fixture-read", "fixture/config")
            self.assertEqual(result["last_synced_revision"], BASE)
            self.assertEqual(result["compared_revision"], HEAD)
            source["helm"] = {"parameters": [{"name": "autoscaling.enabled", "value": "true"}]}
            self.assertIsNone(observed_status("https://argo.example.test", "fixture-read", "fixture/config"))
            source.pop("helm")
            source["plugin"] = {"name": "alternate"}
            self.assertIsNone(observed_status("https://argo.example.test", "fixture-read", "fixture/config"))
