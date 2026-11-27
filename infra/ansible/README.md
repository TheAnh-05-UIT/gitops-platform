# SSM and K3s handoff

Use the AWS-free `render_inventory.py` adapter with Terraform inventory v1. It validates environment, Region, stable IDs, roles, single-AZ membership, addresses and the profile cardinality. It creates a new owner-readable inventory and excludes public IPs from the connection configuration. Run from the Platform root using a protected local file produced by the accepted AWS-13 gate.

```sh
python -B infra/ansible/render_inventory.py --terraform-output "$TERRAFORM_INVENTORY" --environment "$LAB_ENVIRONMENT" --region "$LAB_REGION" --transfer-bucket "$SSM_TRANSFER_BUCKET" --output "$ANSIBLE_INVENTORY"
```

The controller requires a reviewed Ansible core and `amazon.aws` version, AWS SDK dependencies and Session Manager plugin. The owner confirms target managed-node identities, usable AWS SSM egress, approved Ubuntu 22.04 or 24.04 and the anticipated private addresses before deployment. Use short-lived credentials and the dedicated transfer bucket, separate from Terraform state. Scope controller S3 access to the necessary bucket and instance prefixes, block public access, require TLS and encryption, avoid retaining older object versions and set short independent retention for abandoned transfers. Test IAM, transfer behavior and residual objects at the owner gate. The playbook passes the agent token through the SSM transport. No-log reduces log exposure. Bucket and session authorization still matter. [SSM connection plugin](https://docs.ansible.com/projects/ansible/latest/collections/amazon/aws/aws_ssm_connection.html)

Supply a protected JSON or YAML vars file containing the exact reviewed `k3s_release` such as a release tag of shape `v1.x.y+k3sN` and `k3s_sha256` with one approved publisher digest per selected architecture (`x86_64` or `aarch64`). Verify the release and checksums independently before approval. The playbook installs a checksum-verified versioned binary and a lab-owned systemd unit. It can resume after a partial bootstrap of a marked node. It refuses to adopt an unmanaged K3s installation. The legacy draft remains at `playbooks/install-k3s.yml`. [K3s configuration](https://docs.k3s.io/installation/configuration) · [K3s tokens](https://docs.k3s.io/cli/token)

During AWS-14 preflight, the owner verifies `command -v curl python3` and `sudo -n true` from an approved native SSM session using the intended remote user on each node. SSM file transfer and Ansible fact gathering require these before the playbook can install packages. Compare simulated placement labels to the reviewed Terraform variables before rendering the inventory.

## AWS-14 owner gate

Work from the reviewed Platform checkout. Requires accepted AWS-13, approved short-lived controller identity and transfer bucket, protected variables, owner permission to configure the exact nodes and a backup/teardown decision. Start with Profile B and one worker. Rerun after the reviewed second worker is added for the demo. Only the owner runs these commands.

```sh
ansible-inventory -i "$ANSIBLE_INVENTORY" --graph
ansible-playbook -i "$ANSIBLE_INVENTORY" infra/ansible/playbooks/bootstrap-lab.yml --extra-vars "@$K3S_VARS" --syntax-check
ansible-playbook -i "$ANSIBLE_INVENTORY" infra/ansible/playbooks/bootstrap-lab.yml --extra-vars "@$K3S_VARS"
```

Expect exactly one ready server, selected ready workers, checked private addresses and the approved version. The server in a multi-node profile stays outside the simulated worker selector. Confirm a second run with no unintended service restart or label changes. Use approved shell-based owner access for the cluster health check. Keep kubeconfig, tokens and detailed inventory out of Git and shared output. Evidence is count, version, readiness, expected labels, first/second run summaries and transfer cleanup status.

SSH and a public control-plane path are unnecessary. K3s default Traefik/ServiceLB are disabled by this playbook. Any later ingress controller needs its own reviewed manifests. Package downloads, EC2 time, SSM transfer files and NAT where applicable can cost. On failure stop further enrollment, keep service and datastore evidence private and use a reviewed repair. Before changing K3s versions, back up the server datastore and server token to protected storage and plan restoration. Follow supported K3s upgrade/rollback constraints. Never use an uninstall command as error recovery. [K3s backup and restore](https://docs.k3s.io/datastore/backup-restore)
