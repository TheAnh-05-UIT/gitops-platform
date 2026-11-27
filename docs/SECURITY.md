# Security policy and baseline

Historical baseline and planned work. The [acceptance review](FINAL_ACCEPTANCE.md) and [defect register](DEFECT_REGISTER.md) record current candidate behavior and evidence.

## Requirements

- Keep credentials in environment injection or managed secret stores. Avoid printing values from tokens, private keys, kubeconfigs, inventories, Terraform state, plans and sensitive logs. Share sensitive repository details only through authorized channels.
- Use least privilege for GitHub Actions, GHCR, cross-repo clients and cluster identities. Verify credential scope, actor restrictions and branch rules separately. Keep authentication, authorization and CSRF protection as separate controls.
- Validate input at trust boundaries and report errors with minimal exposure. Use reproducible, reviewed dependencies and container images. Keep security checks enabled. Review dependency and image vulnerabilities when changing supply-chain inputs.
- Run containers non-root and review pod and container privileges, service-account access, network exposure, and secret handling in rendered output.

## Baseline findings

| Finding | Evidence and impact |
| --- | --- |
| Portal access control | `portal/app.py` has session CSRF validation but no application login or authorization gate. Reachable callers can use the server's GitHub authority. Deployment perimeter and token scope are unknown. The random per-process session key also makes multi-worker or restart continuity unreliable. |
| GitHub write recovery | `portal/github_client.py` compares against a base snapshot and generates a fresh branch per request. Parallel or repeated requests can produce duplicate or competing PRs. A failure after branch creation can leave a branch behind. GitHub API error text reaches the UI via `GitHubError`. |
| Supply chain | Workload CI blocks critical Trivy findings before publishing, uses version-tagged Actions for existing steps, and uses a floating Python base and ranged direct dependencies. P0.3 adds read-only PR validation and an Actions publication receipt. Digest-pinned deployment, signed attestation and live branch-rule enforcement still require separate work or evidence. |
| Deployment hardening | The chart declares pod non-root and readiness, and the image specifies UID/GID 10001. The current templates lack explicit container capability restrictions, seccomp, token-mount policy and NetworkPolicy. The policy script checks a limited set of Deployment properties. |
| Infrastructure draft | The untracked AWS lab config declares public EC2 IPs, a single public subnet, unrestricted egress, SSH restricted to an input /32, IMDSv2 and encrypted root volumes. Ansible masks token tasks and writes the token with mode `0600`. The server installer URL has no source checksum or pinned server version in the draft. Actual deployment and controls are unknown. |

See [roadmap](ROADMAP.md) for remediation sequencing.

## Promotion trust boundary

- Promotion takes authorization from protected Config base history and the separately reviewed admission record. Config's guard evaluates the candidate Git merge, requires its exact base and head, and verifies the selected image after Helm render. An image PR cannot approve itself by editing the control file.
- The PR workflow uses the base revision's Python policy. GitHub must also protect the workflow definition and trusted policy paths, bind the actual required check, require updated PR heads and independent review, and prevent bypasses. A PR-controlled workflow definition cannot serve as the only enforcement boundary. These settings require owner verification before P0.4.
- The publisher verifies GHCR manifest bytes and uploads a run-scoped artifact. The reader matches the run attempt and checks the archive digest from the Actions API. Signed redirect locations and tokens remain private. Fixture snapshots are local test inputs. Hosted evidence must be fetched from approved read endpoints.
- GitHub preview uses read-only credentials and sends only GET requests. The planned App write credential, GHCR publication token and cluster identity have separate scopes. The chart still resolves a mutable tag at pull time. Protected package write access, descriptor checks and a future digest migration reduce that risk.

See the [runbook](PROMOTION_RUNBOOK.md) for the required GitHub rules, secret names and activation procedure.
