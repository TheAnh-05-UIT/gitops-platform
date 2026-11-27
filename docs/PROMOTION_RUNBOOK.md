# Workload API promotion runbook

P0.3 provides local policy tests and preview tools. Control is frozen with historical v2 blocked. The preview workflow is opt-in and read-only. The App writer and live activation belong to P0.4.

## Local preview

Run from the Config root with existing PyYAML available.

```sh
python -B -W error::SyntaxWarning -m unittest discover -s tests -v
python -B -m unittest discover -s tests -p test_promotion.py -k dry_run_cli -v
python -B -m scripts.promote_image --mode dry-run --request workload-api-g1 --snapshot /path/to/fixture.json
```

The named test generates a synthetic snapshot and checks the CLI's branch and exact resulting values. A hand-built fixture has `control` (the control mapping), `values` (the original YAML string), and `evidence` with `source_tip`, `ancestor`, `receipt`, `run` and `observed_digest`. See Config `tests/test_promotion.py` for the exact shape. The optional `remote_state` exercises reconciliation cases. Fixture success establishes local planner behavior.

Inspect `propose`, `recover-pr`, `refresh-and-recover`, `refresh-branch`, `reuse-pr` or `no-op` as a plan. Refresh stale proposals against the latest verified config base, preserve placement and rerun strict checks. Unknown branch ownership, a closed PR, an image or intent conflict, or ambiguous evidence requires human review. Abort any later mutation if refs move or evidence changes.

## Verify hosted read-only preview

This procedure requires a separately approved hosted target and read access. Keep Config frozen until the release owner reviews the live baseline, historic revert, app scope and rollback artifact.

1. Compare the actual workload and config `main` SHAs with their review snapshots. Check publication run and attempt, GitHub rule enforcement, GHCR head and fallback image descriptors, and the approved Argo CD app's revision, sync, health and running image identity. Run `44419195493` predates receipt upload.
2. Bootstrap Config in order. First land the reviewed policy code, schema and frozen control on the authorized base. Then land the workflow wiring so its separate trusted-base checkout can run the already-present guard. Pin the reviewed config tool SHA as `PROMOTION_CONFIG_TOOL_SHA`. Do not run proposed policy code for an existing check.
3. Use explicit read-only credentials. The workload workflow's `GITHUB_TOKEN` supplies `contents: read`, `actions: read` and `packages: read`. Grant Workload read access to the GHCR package if private. Supply `PROMOTION_CONFIG_READ_TOKEN` through protected secret storage with Config `Contents: read` and `Pull requests: read` only. No App signing key is needed for preview. `PROMOTION_BOT_LOGIN` identifies the approved bot for pre-existing branch recovery.
4. Verify the environment and host allowlist, then enable `PROMOTION_PREVIEW_ENABLED=true` only for the authorized read-only exercise. Dispatch on protected workload `main` with the reviewed request ID. For an authorized workstation with Docker Buildx and package read access, inject the two read credentials securely and use:

```sh
python -B -m scripts.promote_image --mode read-only --request workload-api-g1
```

The second workstation credential is `PROMOTION_SOURCE_READ_TOKEN` with Workload `Actions: read` and `Contents: read`. Keep all credentials, signed download URLs, and Docker auth private. On a failed or missing receipt, stop before promotion. If the same tag exists following a lost receipt, establish a verified publication record under a newly reviewed procedure or build a new source commit. Preserve the existing tag.

## P0.4 App and live authorization

- Require a protected Config `main`, independent review, stale review dismissal, up-to-date heads, trusted required Helm and promotion checks, and no App bypass. Protect the workflow, scripts, and control paths with owner review and a trusted ruleset or approved equivalent. The local PR job validates with base code. A required check alone cannot protect its own editable workflow definition.
- Install a dedicated GitHub App on Config only after owner approval. The approved installation token needs `Contents: write` and `Pull requests: write`, with implicit `Metadata: read`. Protect the bot branch namespace. Use environment-protected App ID and signing key such as `PROMOTION_APP_ID` and `PROMOTION_APP_PRIVATE_KEY` in the future writer. Rotate keys. Keep the writer separate from workload package publication and cluster identities.
- Implement and mock the GitHub write adapter before enabling any writes. Recheck refs, active generation, deny state and fresh digest immediately before each consequential operation. Use non-force bot ref updates, validate exact diff, and recover only verified App-owned branches and PRs. The release owner selects a new lab candidate, validates the published artifact and merges a separate admission record. An independent reviewer merges the checked promotion PR.

## Revert, reject and observe

1. Pause dispatch and hold promotion merges. From the current Config base, confirm the last known-good tag resolves to its independently verified digest. A rollback target found in trusted Git history is a candidate for recovery. Its runtime health and manifest availability require operational evidence.
2. Submit a reviewed rollback PR that restores only the known image, preserves current placement, increments the generation, clears the request, freezes promotion, and records the withdrawn SHA and digest when known. For rejection before merge, record the block and clear the request without changing the image.
3. Verify required checks, then observe actual GitOps sync at the rollback SHA, Deployment readiness, Pod image identity and endpoint smoke. A bare Git revert lacking its control transition is insufficient.
4. Require a new independently reviewed `repromote` intent for the historical v2 or any later blocked candidate. Record evidence resolving the known issue or an explicit owner disposition of the unknown historical reason. Keep prior blocks and their recorded digests.

See the [promotion design](IMAGE_PROMOTION.md) for acceptance criteria and the [security policy](SECURITY.md) for trust boundaries.

## Owner proposal gate for an image-only PR

The local Config command remains disconnected from Actions. It is a manual hosted mutation gate. Run only after the owner authorizes P0.5, reviews the exact Config base, records admission for the publication run/attempt and configures a protected App branch scope. Confirm package visibility and branch protection before review. Keep Workload publication and preview hard stops unless separately approved.

Use the Config checkout on the reviewed tool SHA. Supply short-lived `PROMOTION_CONFIG_READ_TOKEN`, `PROMOTION_SOURCE_READ_TOKEN`, `PROMOTION_CONFIG_APP_TOKEN`, `PROMOTION_BOT_LOGIN` and private read-only GHCR auth if the image is private. The App installation is Config-only with contents and pull request write authority, no protected main bypass. The Config verifier's optional `PROMOTION_REGISTRY_READ_USER` and `PROMOTION_REGISTRY_READ_TOKEN` are environment-scoped and separate from Workload API and registry publisher credentials. Verify scopes before enabling any operation.

```sh
PROMOTION_PROPOSAL_ENABLED=true python -B -m scripts.submit_promotion \
  --request "$APPROVED_REQUEST" --expected-base "$APPROVED_CONFIG_SHA" --confirm-proposal
```

Use `--pin-digest` only after explicit review of a same-source first pin. The command reads current protected refs and latest attempt evidence, then may create one branch, one exact config-file commit and one PR. It reports the PR number and does not merge. Expect only the approved image fields to change. On an unconfirmed request, compare the existing branch and PR, then repeat the same reviewed request. A stale or unrelated branch stops the command for owner review. Do not force-update a branch. The independent reviewer must check the actual candidate and rerun the trusted check after approving the exact marker if required. Require the check publisher and exact candidate linkage before permitting merge. No AWS operation is involved. The registry and CI services may charge for normal usage. Retain sanitized run/attempt, candidate, digest and reviewer/check evidence. [GitHub REST refs](https://docs.github.com/en/rest/git/refs) · [GitHub GraphQL commits](https://docs.github.com/en/graphql/reference/commits)
