# Testing and validation

Run commands from the indicated repository root with its dependencies available. Prefer test doubles and temporary outputs for local checks. Any GitHub, registry, cloud or cluster mutation requires the authorization described in the [workspace policy](WORKSPACE_POLICY.md).

## Platform

```sh
python -m pip install -r requirements.txt
python -m flask --app portal.app run
python -m optimizer.ilp
python -m optimizer.ilp --max-rtt-ms 1
python -m benchmarks.compare_algorithms --repeats 3
python -m benchmarks.compare_algorithms --case infeasible --repeats 3
```

Use Flask's test client with a mocked GitHub boundary. Exercise GET, missing or invalid CSRF, invalid replicas and RTT, infeasibility, solver errors, absent GitHub configuration, no-op and successful or failed PR creation as relevant. For changes to the updater, mock the GitHub request sequence and use the current config values as a fixture. Check it retains the image and unrelated keys. The infeasible CLI prints a status in JSON and currently exits successfully. Inspect the JSON as well as the exit code.

Benchmark changes against both small fixture scenarios and use `--copies`, `--repeats` and `--max-combinations` as needed. Record environment, solver version, fixture case and limits, and expect exhaustive search to skip above its limit.

## Configuration

```powershell
helm lint ./apps/workload-api
$rendered = New-TemporaryFile
helm template workload-api ./apps/workload-api | Set-Content -Encoding utf8 $rendered.FullName
python scripts/check_deployment_policies.py $rendered.FullName
Remove-Item -LiteralPath $rendered.FullName
```

Check Helm lint and render exit codes before interpreting policy output. The validator needs PyYAML. Hosted CI specifies Helm `v4.3.2`, Python `3.12` and `PyYAML==6.0.3`. Inspect image, selectors, readiness and resources in the rendered output. For policy changes, exercise rejected manifests and missing Deployments too. Rendering verifies local syntax and values. Cluster-aware checks require a separately authorized environment.

## Workload API and the integrated flow

- Install workload requirements and use Flask's test client to assert `GET /` returns the service identity and version and `GET /healthz` returns `{"status":"ok"}`.
- Run the local build, loopback HTTP smoke and scan steps from `.github/workflows/ci.yml` when Docker and scanner access are available. Publication is an independent authorized step.
- For a promotion check, compare the image SHA against the workload commit and registry digest, and verify the rendered configuration chooses it. Review the portal's values layout and compare optimizer per-replica demand with chart requests. Retain evidence of the config PR checks. With access to an authorized environment, verify the Argo CD revision and health, Deployment readiness and scheduling, and service responses.
- For authorized infrastructure validation, use `terraform fmt -check`, `terraform validate` after trusted provider initialization, and Ansible syntax validation when available. Review plans and inventories privately. These checks provide no proof of live provisioning.
- For agent changes, validate Markdown links and run the installed skill creator's `quick_validate.py` on each skill directory. Compare fresh CLI launch behavior against the workspace and child discovery rules.

## P0.3 promotion

Run `python -B -W error::SyntaxWarning -m unittest discover -s tests -v` separately from Configuration, Workload and Platform. Use an environment with existing Config PyYAML for Config and the cross-repository test, and with Platform Requests for the cross-repository test. Config tests use fixture approval, receipt and registry observations, and mocked GitHub endpoints. Workload tests cover receipt provenance and exact digest agreement. Platform exercises the actual Portal YAML patcher and both orders using `git merge-file -p` on temporary files.

From Config, run `python -B -m unittest discover -s tests -p test_promotion.py -k dry_run_cli -v` to reproduce a successful synthetic CLI preview. See the [runbook](PROMOTION_RUNBOOK.md) for the preview CLI and validation inputs. The [acceptance matrix](IMAGE_PROMOTION.md#acceptance-matrix) records the hosted tests to run after authorization.

## P0.4.1 trust-boundary tests

Config `tests/test_trusted_promotion.py` exercises the required sequence with mocked GitHub and Git-object resolution. It covers swapped approval base, head and merge, unresolved or mismatched synthetic merges, same-PR authorization, rejected or dismissed reviewer, denied v2, stale receipt, superseded attempt, digest mismatch and missing/failed/skipped jobs and steps. It also verifies raw manifest hashing and runs the real Helm render against candidate values. Helm is required for that test.

Workload `tests/test_workflow_security.py` parses the actual workflow with the existing PyYAML test dependency. It checks the protected event and ref, job-level permissions and secret scope, exact conjunction of successful dependencies and actual Trivy step outcome, and use of the same archive ID and hash. These tests validate workflow structure. Hosted rejection of a registry write from another workflow, missing environment authorization, skipped scan and stale merge evidence must be exercised in an approved lab.
