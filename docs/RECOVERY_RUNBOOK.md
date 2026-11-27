# Lab recovery and service objectives

The K3s lab runs one server with the embedded SQLite datastore. Profile B starts with one worker and the final demonstration uses two. A second worker supplies workload capacity when it has the required labels, network and image access. It does not provide control-plane failover. Keep Terraform state, K3s datastore and token, Git-backed desired state, and workload volume data as separate recovery artifacts.

| Incident | First recovery path |
| --- | --- |
| Bad image, chart, selector or workload options | Follow the reviewed Config revert in the [promotion runbook](PROMOTION_RUNBOOK.md). Verify the prior immutable image, allowed selector, and healthy sync. |
| Backend state or lock incident | Use the scoped [Terraform state runbook](TERRAFORM_STATE_RUNBOOK.md). Preserve state lineage and freeze writers. |
| K3s datastore incident, server intact | Use AWS-14-R0/R1/R2 and AWS-15-R3 below. Keep the former datastore until the owner accepts the recovery. |
| Lost server, disk, credentials or availability zone | Preserve evidence, review cost and network identity, and plan replacement under AWS-12/13 before reenrollment under AWS-14. Use a verified off-host backup or explicitly accept an empty rebuild from Git. Review server IP, agent binding, certificates, and stateful recoverability as separate changes. |

SQLite recovery needs the complete server DB directory and the **same server token** as the backup. Keep the dedicated agent token managed separately under the [Ansible contract](../infra/ansible/README.md). The server token can decrypt bootstrap data and is privileged. The copy does not contain PVC contents, host-path storage, Loki retention, or GitHub and Terraform state. Track each of those independently. [K3s datastore backup](https://docs.k3s.io/datastore/backup-restore) · [K3s token roles](https://docs.k3s.io/cli/token)

## Offline rehearsal

Run in the Platform root. The tests create synthetic databases and tokens in disposable directories. They exercise intact backups, uncheckpointed WAL state, rollback-journal refusal, missing token, corrupt DB, empty Kine table and separation of backup from scratch.

```powershell
python -B -m unittest discover -s tests -p test_k3s_restore_rehearsal.py -v
```

For an owner-approved private copy, run `python3 -B scripts/rehearse_k3s_restore.py --bundle "$STAGED_BACKUP" --scratch-dir "$PRIVATE_SCRATCH"` in the Platform root. Both directories must already exist on encrypted local storage outside the repository. The tool copies SQLite data and WAL into a fresh scratch directory, opens the copy read-only, runs integrity and Kine presence checks, and reports only pass/fail. It checks that the server token exists without opening it. It does not test whether that token decrypts the backup or whether K3s and its workloads can start. The live smoke gate supplies that evidence. [SQLite integrity check](https://sqlite.org/pragma.html#pragma_integrity_check)

## Owner-only AWS gates

Run each gate separately under the [Manual Cloud Execution Policy](../AGENTS.md#manual-cloud-execution-policy). Review exact source revisions, deployment fingerprint, outage window, owner acceptance, and restoration priority first. Freeze Terraform writers and delivery changes for the affected environment. AWS-14-R0 is for reads, AWS-14-R1 is for backup and a service interruption, AWS-14-R2 is for a datastore mutation, and AWS-15-R3 is for smoke and evidence. Each mutation needs its own approval. All sections are pending live evidence.

Set parameters on the approved Linux controller from the Platform root using the exact approved private paths. Use a new UTC run identifier, for example `20261126T120000Z`; assign a different restore identifier for each retry. Use a clean owner identity for SSM and the approved separate controller credentials for Ansible transfer.

```bash
AWS_PROFILE_NAME='<owner-session-profile>'
AWS_REGION_NAME='<approved-region>'
SERVER_INSTANCE='<approved-instance-id>'
ANSIBLE_INVENTORY='<private-rendered-ansible-inventory>'
PRIVATE_RUN='<existing-new-private-encrypted-run-directory>'
PRIVATE_SCRATCH='<existing-private-encrypted-scratch-directory>'
RUN_ID='<new-UTC-run-id>'
ANSIBLE_PROFILE_NAME='<approved-ansible-controller-profile>'
CONTROL_ACCOUNT='<approved-account-id>'
export AWS_REGION="$AWS_REGION_NAME"
```

### AWS-14-R0 · Identity, backup access and readiness

**Directory and prerequisites.** Platform root on the controller. Require a successful AWS-14 deployment and scoped Session Manager identities and plugin. Compare the single `k3s-server` target to the protected inventory. The SSM file-transfer bucket in the inventory is separate from the state bucket. Review the backup encryption recipient fingerprint and prove key access by decrypting a synthetic challenge before the outage. Confirm adequate free space for the archive, extracted copy and pre-restore data.

```bash
test "$(aws sts get-caller-identity --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME" --query Account --output text)" = "$CONTROL_ACCOUNT"
test "$(aws ssm describe-instance-information --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME" --filters "Key=InstanceIds,Values=$SERVER_INSTANCE" --query 'InstanceInformationList[0].PingStatus' --output text)" = Online
aws ssm start-session --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION_NAME" --target "$SERVER_INSTANCE" --reason 'AWS-14-R0 inventory and backup access'
```

In the approved Session Manager shell, run the following as the configured operator. Preserve the version and Config sync revision privately. A verified, active `k3s.service` and no datastore/ownership ambiguity are prerequisites for the backup drill.

```bash
cd /var/lib/rancher/k3s
id -un
sudo systemctl is-active k3s
sudo test -s server/db/state.db
sudo test -s server/token
sudo test -f /etc/rancher/k3s/.gitops-platform
command -v gpg python3 tar
df -h .
```

**Effects and evidence.** The account, EC2 managed-node status, systemd and filesystem checks are read-only. Session access and audit storage can incur charges. Keep instance, account, identity, paths, key fingerprint and audit output private. Stop and close the session on any mismatch. Record identity match, version match, approved transfer access and maintenance-window approval.

### AWS-14-R1 · Quiesced, encrypted, off-host backup

**Directory and prerequisites.** Controller uses the Platform root. The target's approved SSM shell uses `/var/lib/rancher/k3s`. Confirm owner approval for K3s downtime. The server uses the approved GnuPG public key, the controller holds the corresponding private key in approved storage, and the temporary archive is ciphertext. No database, token values or key export may enter SSM transcripts. Keep tracing off.

Open the SSM shell using the AWS-14-R0 command with reason `AWS-14-R1 approved SQLite backup`. Run `sudo -i`, then perform the following. Verify the current running binary from the unit's `ExecStart` privately against the reviewed release and digest before stopping the service. Choose the exact human-approved GnuPG recipient fingerprint and the SSM user confirmed in R0.

```bash
set -euo pipefail
set -o noclobber
umask 077
cd /var/lib/rancher/k3s
RUN_ID='<same-new-UTC-run-id>'
RECOVERY_RECIPIENT='<verified-GnuPG-recipient-fingerprint>'
SSM_FILE_USER='<approved-SSM-shell-user>'
K3S_BINARY='<approved-absolute-server-binary-path-from-systemd>'
K3S_BINARY_SHA256='<approved-pin-for-the-installed-architecture>'
EXPECTED_K3S_RELEASE='<pinned-k3s-release>'
ARCHIVE="/var/tmp/idp-k3s-$RUN_ID.tar.gz.gpg"
test ! -e "$ARCHIVE"
printf '%s  %s\n' "$K3S_BINARY_SHA256" "$K3S_BINARY" | sha256sum -c -
test "$("$K3S_BINARY" --version | awk 'NR == 1 {print $3}')" = "$EXPECTED_K3S_RELEASE"
test -s server/db/state.db
test -s server/token
date -u +%FT%TZ
systemctl stop k3s
test "$(systemctl is-active k3s || true)" = inactive
tar -czf - server/db server/token | gpg --batch --encrypt --recipient "$RECOVERY_RECIPIENT" --output - > "$ARCHIVE"
systemctl start k3s
systemctl is-active k3s
chown "$SSM_FILE_USER" -- "$ARCHIVE"
chmod 0600 -- "$ARCHIVE"
sha256sum -- "$ARCHIVE"
```

If any command after stop fails, return through the approved session and run `sudo systemctl start k3s`, then inspect status. Quarantine any partial encrypted artifact and choose a new run identifier. Preserve the pre-failure evidence. The stop/start affects platform availability, and encrypted storage, S3 requests and transfer can incur costs.

On the controller, fetch only the ciphertext without escalation. The exact remote user and transfer bucket were reviewed in R0. Compare the result privately to the server SHA-256 recorded above, then test decryption and integrity using the offline script. Keep the encrypted archive and private checksum on independent approved storage with authorized readers. Do not accept the backup until both the check and the independent copy have succeeded. [Ansible SSM transport](https://docs.ansible.com/projects/ansible/latest/collections/amazon/aws/aws_ssm_connection.html) · [Ansible fetch](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/fetch_module.html)

```bash
set -euo pipefail
umask 077
ARCHIVE="/var/tmp/idp-k3s-$RUN_ID.tar.gz.gpg"
LOCAL_ARCHIVE="$PRIVATE_RUN/idp-k3s-$RUN_ID.tar.gz.gpg"
STAGED_BACKUP="$PRIVATE_RUN/backup"
SOURCE_SHA256='<private-sha256-recorded-on-server>'
test ! -e "$LOCAL_ARCHIVE"
AWS_PROFILE="$ANSIBLE_PROFILE_NAME" ANSIBLE_BECOME=false ansible -i "$ANSIBLE_INVENTORY" k3s_server -m ansible.builtin.fetch -a "src=$ARCHIVE dest=$LOCAL_ARCHIVE flat=true validate_checksum=true"
printf '%s  %s\n' "$SOURCE_SHA256" "$LOCAL_ARCHIVE" | sha256sum -c -
mkdir -m 0700 -- "$STAGED_BACKUP"
gpg --batch --decrypt "$LOCAL_ARCHIVE" | tar -xzf - -C "$STAGED_BACKUP" -- server/db server/token
python3 -B scripts/rehearse_k3s_restore.py --bundle "$STAGED_BACKUP" --scratch-dir "$PRIVATE_SCRATCH"
```

**Expected evidence.** Matching checksums, independently readable encrypted copy, confirmed service restart and sanitized rehearsal result. Record only the backup UTC checkpoint, duration, storage class or retention owner, and pass/fail. Retain at least one independently verified backup before a drill and record the currently approved retention period. If checks fail, preserve the last accepted copy and halt recovery from the failed candidate.

### AWS-14-R2 · Restore on the same lab server

**Directory and prerequisites.** Platform root on controller and `/var/lib/rancher/k3s/server` on the approved server. The owner approves downtime and the exact archive checksum, backup time, K3s release/digest, environment, original server and private address, and holds delivery changes. Verify that the approved binary and node configuration still match the backup and that the separately managed agent secret has not rotated. A missing server, different target identity or different data-store mode requires a new reviewed procedure.

Before stopping the server, stage the verified archive on the approved target. The recovery operator must first review a distinct, time-limited GnuPG encryption recipient with its private key in a root-only keyring on that server. The original recovery private key stays on the controller. The controller decrypts to an in-process stream, encrypts again to the target public key, and uploads ciphertext through the approved transfer bucket. The server operator checks transfer integrity and permissions. Only ciphertext enters the transfer bucket.

```bash
set -euo pipefail
set -o noclobber
umask 077
RESTORE_ID='<new-UTC-restore-id>'
SOURCE_SHA256='<accepted-backup-sha256>'
LOCAL_ARCHIVE='<approved-ciphertext-archive-from-R1>'
TARGET_RECIPIENT='<verified-server-restore-key-fingerprint>'
REWRAPPED="$PRIVATE_RUN/restore-$RESTORE_ID.tar.gz.gpg"
REMOTE_WRAPPED="/var/tmp/idp-restore-$RESTORE_ID.tar.gz.gpg"
printf '%s  %s\n' "$SOURCE_SHA256" "$LOCAL_ARCHIVE" | sha256sum -c -
gpg --batch --decrypt "$LOCAL_ARCHIVE" |
  gpg --batch --encrypt --recipient "$TARGET_RECIPIENT" --output - > "$REWRAPPED"
sha256sum -- "$REWRAPPED"
AWS_PROFILE="$ANSIBLE_PROFILE_NAME" ANSIBLE_BECOME=false ansible -i "$ANSIBLE_INVENTORY" k3s_server -m ansible.builtin.copy -a "src=$REWRAPPED dest=$REMOTE_WRAPPED mode=0600 force=false"
```

Open the approved session using the R0 command with reason `AWS-14-R2 approved SQLite restore`. Elevate via `sudo -i`. Check the rewrapped digest and verify the dedicated stage root is outside active K3s paths and on encrypted storage. Extract DB and token into a fresh root-only child of that stage root. The group and other users must lack access. Continue to the mutation after the staged backup passes the verification command and the owner explicitly confirms the stop.

```bash
set -euo pipefail
umask 077
RESTORE_ID='<same-new-UTC-restore-id>'
RESTORE_KEYRING='<approved-root-only-server-GnuPG-home>'
RESTORE_SHA256='<sha256-rewrapped-archive-recorded-on-controller>'
RESTORE_STAGE_ROOT='<approved-encrypted-root-only-existing-directory>'
RESTORE_REPO='<source-reviewed-local-Platform-copy-on-the-server>'
REMOTE_WRAPPED="/var/tmp/idp-restore-$RESTORE_ID.tar.gz.gpg"
STAGED_BACKUP="$RESTORE_STAGE_ROOT/backup-$RESTORE_ID"
PRIVATE_SCRATCH="$RESTORE_STAGE_ROOT/scratch-$RESTORE_ID"
test ! -L "$REMOTE_WRAPPED"
printf '%s  %s\n' "$RESTORE_SHA256" "$REMOTE_WRAPPED" | sha256sum -c -
mkdir -m 0700 -- "$STAGED_BACKUP" "$PRIVATE_SCRATCH"
gpg --homedir "$RESTORE_KEYRING" --batch --decrypt "$REMOTE_WRAPPED" |
  tar -xzf - -C "$STAGED_BACKUP" -- server/db server/token
python3 -B "$RESTORE_REPO/scripts/rehearse_k3s_restore.py" --bundle "$STAGED_BACKUP" --scratch-dir "$PRIVATE_SCRATCH"
```

In the same approved root shell:

```bash
set -euo pipefail
umask 077
cd /var/lib/rancher/k3s/server
PREVIOUS="$PWD/pre-restore-$RESTORE_ID"
FAILED="$PWD/failed-restore-$RESTORE_ID"
test -s "$STAGED_BACKUP/server/db/state.db"
test -s "$STAGED_BACKUP/server/token"
test -s db/state.db
test -s token
test ! -e "$PREVIOUS"
test ! -e "$FAILED"
mkdir -m 0700 -- "$PREVIOUS"
date -u +%FT%TZ
systemctl stop k3s
test "$(systemctl is-active k3s || true)" = inactive
mv -T -- db "$PREVIOUS/db"
mv -T -- token "$PREVIOUS/token"
cp -a -- "$STAGED_BACKUP/server/db" db
install -o root -g root -m 0600 -- "$STAGED_BACKUP/server/token" token
test -s db/state.db
test -s token
systemctl start k3s
systemctl is-active k3s
```

**Rollback.** After an incomplete command, keep the unit stopped and privately reconcile which originals were moved. If both originals are in `$PREVIOUS`, move any new or partial replacements out of the active paths into a fresh restricted directory and restore both originals together. The following is for that case only, with the same shell variables and fresh failure path. If only one was moved, restore that file or directory to its original path after confirming the untouched original remains in place. If neither original can be verified, stop and use the incident process instead of opening a new empty cluster.

```bash
systemctl stop k3s
test "$(systemctl is-active k3s || true)" = inactive
test -s "$PREVIOUS/db/state.db"
test -s "$PREVIOUS/token"
test ! -e "$FAILED"
mkdir -m 0700 -- "$FAILED"
if test -e db; then mv -T -- db "$FAILED/db"; fi
if test -e token; then mv -T -- token "$FAILED/token"; fi
mv -T -- "$PREVIOUS/db" db
mv -T -- "$PREVIOUS/token" token
systemctl start k3s
systemctl is-active k3s
```

**Effects and evidence.** The procedure changes live K3s storage and interrupts the control plane. It can regress control-plane writes since the accepted backup. Keep both copies and the selected archive until smoke and acceptance. Validate disk availability and clean up staged data and transfer artifacts only in a separate owner-approved retention action. Record timestamps, accepted checkpoint, startup result and rollback status. Never publish SQLite, token, kubeconfig or identifiers.

### AWS-15-R3 · Private smoke and monitoring recovery

**Directory and prerequisites.** Platform root on the controller. Use the explicitly approved private kubeconfig and context after AWS-14-R2 or its rollback. Require expected worker count, current approved Config SHA and trusted digest. There is no AWS mutation in these commands. Kubernetes read and port-forward access still require authorization. Keep Admin APIs private.

```bash
KUBECONFIG_FILE='<private-kubeconfig>'
LAB_CONTEXT='<approved-context>'
kubectl --kubeconfig "$KUBECONFIG_FILE" --context "$LAB_CONTEXT" get --raw='/readyz'
kubectl --kubeconfig "$KUBECONFIG_FILE" --context "$LAB_CONTEXT" wait node --all --for=condition=Ready --timeout=120s
kubectl --kubeconfig "$KUBECONFIG_FILE" --context "$LAB_CONTEXT" -n workloads rollout status deployment/workload-api --timeout=120s
kubectl --kubeconfig "$KUBECONFIG_FILE" --context "$LAB_CONTEXT" -n argocd get application workload-api -o 'jsonpath={.status.sync.status}{" "}{.status.health.status}{" "}{.status.sync.revision}{"\n"}'
kubectl --kubeconfig "$KUBECONFIG_FILE" --context "$LAB_CONTEXT" -n workloads get pod -l app.kubernetes.io/name=workload-api -o 'jsonpath={range .items[*]}{.status.containerStatuses[*].imageID}{"\n"}{end}'
kubectl --kubeconfig "$KUBECONFIG_FILE" --context "$LAB_CONTEXT" -n workloads port-forward --address 127.0.0.1 service/workload-api 18081:80
```

From a second terminal, run `curl --fail --silent --show-error --max-time 5 --output /dev/null http://127.0.0.1:18081/healthz` and close the forward after the check. Compare both restored Git revision and observed image digest with accepted evidence. Record one recovered alert and the first sanitized log line after restart using the approved private monitoring path where observability is installed. Stop on timeout or revision mismatch. Investigate rather than force reconciliation. If the restore caused the failure, use the separately approved R2 rollback and repeat R3. Transfer, audit and log retention charges can apply. [Private port forward](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_port-forward/)

## Lab measurements and acceptance

| Signal | Proposed lab objective | Evidence and limits |
| --- | --- | --- |
| Control-plane RPO | At most 24 hours | UTC interval between the last verified usable backup and the incident. Record the restored checkpoint and missed approved changes. |
| Same-server RTO | At most 60 minutes | From service interruption to API readiness, expected nodes and digest, and HTTP success. A replacement instance or unavailable AZ has a different recovery envelope. |
| API availability during the authorized exercise | At least 99% successful requests | Over one bounded window, ratio of increments in `workload_api_http_requests_total` for `route="index",status_class="2xx"` to all index requests. Require a positive request denominator and matching targets. |
| API latency during the exercise | p95 under 250 ms | Use `histogram_quantile(0.95, sum by (le) (rate(workload_api_http_request_duration_seconds_bucket{route="index",job="workload-api"}[5m])))` once enough samples exist. Keep load authorized and bounded. |
| Delivery and telemetry recovery | Intended revision, immutable digest and expected collector health | Compare Argo status, observed pod image, Prometheus scrape health, alert transition and redacted log receipt. Mark absent signals as unverified. |

These are lab objectives awaiting owner measurements. The datastore and collector share lab failure domains. Preserve timestamps and incident evidence independently of the cluster, report missing data as unverified, and keep any alert credentials or raw logs private. Off-host encrypted backup, access review, SSM transfer and real K3s recovery remain owner gates.
