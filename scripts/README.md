# Offline Terraform regression

Run from the Platform root with Python 3.9 or later, the reviewed Terraform CLI on PATH, and the AWS provider package from the committed lock in an approved unpacked local mirror. A mirror package is stored at `registry.terraform.io/hashicorp/aws/<locked-version>/<os>_<arch>/` under the mirror root. Unpacked packages require an `h1:` checksum for that platform. The existing Windows amd64 lock and mirror were used to verify this runner. Other platforms require a matching package and reviewed lock checksum. [Terraform dependency lock checksums](https://developer.hashicorp.com/terraform/language/files/dependency-lock#checksum-verification)

```sh
python -B -m unittest discover -s tests -p 'test_terraform_offline.py' -v
python -B scripts/terraform_offline.py --provider-mirror infra/terraform/.terraform/providers
python -B -m unittest discover -s infra/terraform/bootstrap/tests -p 'test_*.py' -v
```

The first command exercises the runner's isolation guard without launching Terraform. The second makes a temporary source-only copy of the lab and bootstrap roots, networking, security, Compute, IAM and inventory modules. The runner checks the supported project's HCL source and plan-only mock tests before starting Terraform. It checks formatting, initializes with the local mirror and readonly dependency lock, and validates and tests each suite in a fresh data directory. It validates the production S3 declaration with backend disabled and adds the local-backend override only to the temporary lab copy for its mock tests. It provides empty AWS shared files, discards inherited AWS and Terraform settings and disables EC2 metadata and checkpoint. The third command checks backend file rendering and key separation separately.

The local mirror and Terraform CLI are trusted dependencies. Use the runner only on reviewed source layouts and test fixtures for this project. Its static guard is scoped to these configurations and is not a sandbox for arbitrary Terraform files or provider packages. The mirror package uses hard links in the temporary workspace where possible. For a cross-volume mirror, the runner makes one temporary package copy, then uses hard links to share it among suites. Choose a local temporary filesystem that supports hard links and has room for one provider package if a cross-volume copy is needed.

A nonzero status marks a stopped offline check. If CLI, local package, matching checksums or scratch storage are unavailable, record the blocker and supply the approved dependencies locally. Hosted verification, real AWS authorization, backend initialization, S3 locking behavior and state operations follow their separate gates. [Terraform validation and manual state gates](../infra/terraform/README.md#state-and-offline-verification)
