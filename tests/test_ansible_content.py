"""Check playbook structure and render both K3s roles without a cluster."""
import json
from pathlib import Path
import unittest

try:
    from jinja2 import Environment, StrictUndefined
    import yaml
except ImportError:
    Environment = None

ROOT = Path(__file__).parents[1] / "infra/ansible"


@unittest.skipUnless(Environment, "Requires the existing PyYAML and Jinja2 test environment")
class PlaybookTests(unittest.TestCase):
    def test_all_playbooks_parse_and_includes_resolve(self):
        paths = list((ROOT / "playbooks").rglob("*.yml"))
        files = {path.resolve() for path in paths}
        for path in paths:
            for task in yaml.safe_load(path.read_text(encoding="utf-8")):
                for key, value in task.items():
                    if key == "ansible.builtin.import_playbook":
                        self.assertIn((path.parent / value).resolve(), files)
                for child in task.get("tasks", []):
                    if "ansible.builtin.include_tasks" in child:
                        self.assertIn((path.parent / child["ansible.builtin.include_tasks"]).resolve(), files)

    def test_template_sources_resolve_from_the_bootstrap_playbook(self):
        playbook_dir = (ROOT / "playbooks").resolve()
        jinja = Environment(undefined=StrictUndefined)
        jinja.filters["dirname"] = lambda value: str(Path(value).parent)
        for filename, template_name in (
            ("k3s-node.yml", "k3s.service.j2"),
            ("k3s-start.yml", "k3s-config.yaml.j2"),
        ):
            with self.subTest(task_file=filename):
                task_file = playbook_dir / "tasks" / filename
                tasks = yaml.safe_load(task_file.read_text(encoding="utf-8"))
                template = next(
                    task["ansible.builtin.template"] for task in tasks if "ansible.builtin.template" in task
                )
                source = Path(jinja.from_string(template["src"]).render(playbook_dir=str(playbook_dir)))
                self.assertEqual(source, playbook_dir.parent / "templates" / template_name)
                self.assertTrue(source.is_file())

    def test_rendered_k3s_uses_private_address_and_separate_tokens(self):
        jinja = Environment(undefined=StrictUndefined)
        jinja.filters["to_json"] = json.dumps
        template = jinja.from_string((ROOT / "templates/k3s-config.yaml.j2").read_text(encoding="utf-8"))
        common = {
            "node_private_ip": "10.20.0.12",
            "hostvars": {"k3s-server": {"node_private_ip": "10.20.0.10"}},
            "k3s_server_id": "k3s-server",
        }
        server = yaml.safe_load(template.render(common, k3s_mode="server", inventory_hostname="k3s-server"))
        agent = yaml.safe_load(template.render(common, k3s_mode="agent", inventory_hostname="k3s-agent1"))
        self.assertEqual(server["write-kubeconfig-mode"], "0600")
        self.assertEqual(server["flannel-backend"], "vxlan")
        self.assertEqual(server["disable"], ["traefik", "servicelb"])
        self.assertEqual(agent["server"], "https://10.20.0.10:6443")
        self.assertNotEqual(agent["token-file"], server["agent-token-file"])
        self.assertNotIn("token", agent)

    def test_secret_tasks_are_redacted_and_worker_enrollment_is_serial(self):
        plays = yaml.safe_load((ROOT / "playbooks/bootstrap-lab.yml").read_text(encoding="utf-8"))
        server, worker = plays[1:3]
        self.assertEqual(worker["serial"], 1)
        read = next(task for task in server["tasks"] if "ansible.builtin.slurp" in task)
        self.assertTrue(read["no_log"])
        self.assertIn("k3s_agents", read["when"])
        transfer = next(task for task in worker["tasks"] if "ansible.builtin.copy" in task)
        self.assertTrue(transfer["no_log"])
        self.assertEqual(transfer["ansible.builtin.copy"]["mode"], "0600")
        self.assertEqual(server["handlers"][0]["ansible.builtin.systemd_service"]["state"], "restarted")
