# Project state

## Nghiệm thu R2 Local Runtime

Ba worktree giữ trên nhánh cục bộ `chore/r2-local-runtime`. Platform giữ sửa Ansible `8b7886e`, Workload `b0ddbba` khóa OCI base và Linux wheels, Config `dfd3486` và `b235d28` sửa Alertmanager và Alloy. k3d ba node, Argo sync/drift/revert, telemetry, browser Portal với OIDC giả lập, optimizer với dữ liệu Kubernetes thật, k6/HPA, Pod recovery và drain đều có bằng chứng lab. Trivy báo 54 HIGH trên ảnh Trixie. Ảnh Workload Alpine `1fa207e` khóa bản sửa Kerberos và đã qua cùng gate với 0 HIGH, 0 CRITICAL và 0 secret trên linux/amd64. Full Ansible bootstrap trong ba container Ubuntu systemd dùng tmpfs **PASS**, cả ba K3s nodes Ready và lượt lặp có 0 changed trên mỗi host. R3 Hosted Integration **chưa đủ điều kiện**. [Báo cáo R2](LOCAL_RUNTIME_ACCEPTANCE.md)

Historical baseline and planned work. The [acceptance review](FINAL_ACCEPTANCE.md) and [defect register](DEFECT_REGISTER.md) record current candidate behavior and evidence.

The initialization baseline was recorded on 2026-11-26. P0.1–P0.2 rechecked the local refs and source. GitHub, GHCR, AWS and Kubernetes state can change independently.

| Checkout | Baseline branch and HEAD | Starting worktree |
| --- | --- | --- |
| Platform | `feat/provision-aws-k3s-infrastructure` at `8b2a57b` | Untracked `infra/` draft with Terraform and Ansible source. |
| Configuration | `feat/move-workload-api-to-ap-southeast-1` at `e0eb7b` | Clean. Local `main` at `9b4fae6` selects `eu-west-1`. Cached `origin/main` at `f4f9979` and the checked-out branch select `ap-southeast-1`. |
| Workload API | `main` at `2dd86b7` | Clean. The local source declares `v2`. |

Config `main...origin/main` is `0 6` and `HEAD...origin/main` is `0 5`, where the second number is the number of commits only in the cached remote-tracking ref. The checked-out feature branch matches its own cached upstream. Platform `main` and workload `main` each match their cached `origin/main`. Platform's checked-out infrastructure branch has no upstream. The housekeeping files and Platform's existing infrastructure draft are local, untracked changes. Use an explicitly verified remote config base for future promotion.

## Historical image promotion and revert

- Config commit `5bcaae9` changed `image.tag` from `97172600d3b87dded805e942d6e247190a0827e1` to `2dd86b7d8237da0ae37878ae99bc9cf983e3a9d0`. Cached history includes merge `0f83b6b` for PR #2.
- Commit `8b5497e` restored the first tag. Cached history includes merge `9ad70cc` for PR #3. The revert message identifies the change being undone. Its reason, GHCR digest, Argo CD revision and observed rollout outcome are unknown.
- The checked-out config and cached `origin/main` have two replicas in `ap-southeast-1` and reference the first tag, whose workload source declares `v1`. Workload `main` at `2dd86b7` declares `v2`. These are statements about source and Git desired state. Current Kubernetes image identity and health require runtime evidence.
- The Helm Deployment renders `image.repository:image.tag`. A SHA-shaped tag can be reassigned. The proposed P0.3 contract verifies a registry digest while preserving the current chart behavior. Digest-pinned desired state is a separate migration. See the [promotion proposal](IMAGE_PROMOTION.md).

## Evidence and status

| Status | Component | Evidence and boundary |
| --- | --- | --- |
| Implemented and verified locally | Workload Flask HTTP behavior | Two Flask test-client assertions confirmed identity, `v2` and health. |
| Implemented and verified locally | Optimizer, benchmark and portal request handling | CBC returned `ap-southeast-1`, 45 ms and 0.003733 USD/hour for the default fixture and infeasible at 1 ms. Baseline benchmark ILP and exhaustive agreed and greedy had an 8% gap. The infeasible benchmark returned no solution. Portal smoke checked GET, CSRF rejection, invalid replicas, infeasibility and a mocked optimal PR handoff. |
| Implemented and verified locally | Helm chart and policy | Helm 4.3.2 lint and rendering passed on the checked-out branch. The policy script accepted one Deployment. |
| Implemented and verified locally | Cross-repository contract samples | Four mocked GitHub-client cases exercised successful PR creation, the no-op path, unexpected values layout and failure after branch creation. The update preserved the image and unrelated values. Optimizer demand matched chart requests. The Dockerfile, rendered port and readiness settings, Service target and Argo CD source and destination also agreed in static checks. |
| Implemented, runtime unverified | Container build and publication workflow, portal GitHub integration, remote config validation, Argo CD Application | Source and Git history show intended behavior. Docker daemon access was denied locally. Local config history includes a merged portal placement PR in cached `origin/main`, but this session has no live job, package, PR API or reconciliation evidence. |
| Partially implemented | End-to-end delivery | Workload publication and config validation exist in source. The checked-out config and cached `origin/main` use `9717260…`, whose source declares `v1`. CI has no handoff to promote the `v2` revision, and its publication is unknown. |
| Partially implemented | AWS and k3s lab | Pre-existing untracked source in `infra/terraform/` and `infra/ansible/` defines a three-EC2, single-AZ lab and a k3s server with two agents. The playbook applies simulated region labels. Terraform formatting and validation passed. Ansible tooling was unavailable and actual resources, topology and node readiness are unknown. |
| Planned | Reproducible infrastructure, operational telemetry and live placement inputs | See [roadmap](ROADMAP.md). There are no tracked provider inputs for live inventory, pricing, RTT or telemetry. |
| Missing | Automated image promotion, application auth and authorization, tracked unit and integration test suites, observability stack and verified runtime rollback evidence | CI container smoke and config policy checks are the existing automated checks. The config Git rollback is recorded above. No tracked platform workflow exists. |
| Unknown | Remote branch protection and required checks, registry visibility, production portal perimeter, cloud resources, Argo CD installation and sync | Evidence would require authorized access and live checks. |

The draft Terraform provider takes `aws_region`, `ubuntu_ami_id`, `admin_cidr` and `ssh_public_key_path` and outputs public and private IP maps. The AWS Region defaults to `us-east-1` and the subnet AZ is hardcoded to `us-east-1a`. Ansible expects `k3s_server`, `k3s_agents` and `k3s` groups plus `node_private_ip` and `simulated_region`. The playbook passes the observed server version through `INSTALL_K3S_VERSION` for the agents. Keep ignored state, plans and inventories private. No sensitive configuration values were opened during discovery.

## Validation and external evidence

The table above preserves initialization validation. The follow-up audit rechecked both workload routes, the portal GET and missing-CSRF response, and Helm render and policy for config `main`, `HEAD` and cached `origin/main`. P0.1–P0.2 rechecked the ref relationships and both tag-changing commits. Helm lint passed and renders for the same three values refs passed policy. The original documentation was copied with matching SHA-256 before edits. Local links and all nine skill headers were validated. The proposal's acceptance tests are specified for P0.3.

| External evidence | P0.1–P0.2 result |
| --- | --- |
| Live workload and config `main`, hosted Actions, promotion/revert PR records and protection rules | The unauthenticated workload `main` GitHub API probe could not connect to `api.github.com:443`. curl exit `7`, HTTP `000`. The remaining endpoints on that host were left unqueried. The earlier audit's `git ls-remote` also could not connect to `github.com:443`. The refs and revert above are cached Git evidence. |
| GHCR availability, intended digest, rollback digest and visibility | The candidate manifest probe could not connect to `ghcr.io:443`. curl exit `7`, HTTP `000`. Availability, mapping and package grants are unresolved. |
| Argo CD and Kubernetes | The `argocd` CLI was unavailable. `kubectl` is installed. An authorized cluster target and read access were not established, so no cluster query was made. The Application file is desired-state configuration. |

The installed Codex CLI reported `0.172.0` during the audit. Its offline diagnostic returned `Could not find home directory` under the sandbox identity. Automatic instruction and skill discovery remain unverified. Use manual file reads.

## P0.3 local implementation

The user-supplied GitHub review snapshot recorded Config `f4f9979f1a749d73d56bab69978bd30e18d82d9e`, Workload `2dd86b7d8237da0ae37878ae99bc9cf983e3a9d0` and a successful workload run `44419195493`. An active ruleset named `main` was reported. The exact rules, digest, current refs and observed Argo CD state were not verified in this implementation. The historical revert reason is still unknown.

Config now contains the frozen seed, promotion schema, trusted-base merge guard and read-only preview. Workload CI code records a verified manifest receipt after the original validation and publication gates. The separately dispatched preview workflow is opt-in and read-only. Platform regression tests use the actual Portal updater with mocked GitHub calls and verify both merge orders. Hosted guard enforcement, protected credentials, artifact availability and GitOps rollout remain unverified. Use the [promotion runbook](PROMOTION_RUNBOOK.md) for the activation gate.

Local P0.3 verification passed 19 Config, 4 Workload and 3 Platform tests. Helm lint, render and the Deployment and exact-image policies passed for the local chart. The dry-run fixture proposed the deterministic branch and retained all unrelated values. Python compilation, workflow YAML checks and Git diff whitespace checks passed. Dedicated secret scanners and Actionlint were unavailable. A scoped token/key pattern scan found no matches.

See [security findings](SECURITY.md), [validation commands](TESTING.md) and [the roadmap](ROADMAP.md).
