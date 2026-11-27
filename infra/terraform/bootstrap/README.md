# S3 state bootstrap

This root manages one general-purpose S3 bucket for one approved lab environment. Use the protected owner working copy described in the [Terraform state runbook](../../../docs/TERRAFORM_STATE_RUNBOOK.md). Bootstrap has an implicit local backend and owns no lab resources. The lab's S3 backend depends on the verified bootstrap outputs. The bootstrap state and an independent encrypted recovery copy live outside the checkout and outside the bucket they manage.

## Bucket controls

| Terraform resource | Count | Implemented control |
| --- | ---: | --- |
| `aws_s3_bucket` | 1 | Explicit Region, globally unique name in the chosen partition, project/environment/owner/cost tags, `force_destroy = false` and `prevent_destroy = true`. |
| `aws_s3_bucket_versioning` | 1 | `Enabled`. Preserve historical objects and delete markers. |
| `aws_s3_bucket_server_side_encryption_configuration` | 1 | Explicit SSE-S3 (`AES256`). |
| `aws_s3_bucket_ownership_controls` | 1 | `BucketOwnerEnforced`. S3 ACLs are disabled. |
| `aws_s3_bucket_public_access_block` | 1 | All four public-access controls enabled. |
| `aws_s3_bucket_policy` | 1 | Deny requests without TLS to the bucket and its objects. No policy statement grants access. |

The [bootstrap inputs](examples/lab.tfvars.json.example) use synthetic values. Supply the approved account, Region, name, project and environment and owner/cost metadata privately. Choose a 3–63 character lowercase DNS-style name with digits/hyphens, no dots or reserved forms. The Terraform AWS provider verifies the approved account at live execution. Mock tests cover syntax and controls. S3 ownership, global name availability in the partition, live access and locking are owner checks. [S3 bucket naming constraints](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html)

SSE-S3 protects objects at rest using S3-managed encryption. TLS protects requests in transit. SSE-KMS can add key policy boundaries and key-use auditability. It would require a separately approved key and key policy, scoped `kms:GenerateDataKey` and `kms:Decrypt` where needed for backend writers and recovery, and a retention decision for historic versions encrypted under older keys. Disabling or deleting a key can make these versions unreadable. Key and request charges also apply. This root creates no KMS key or DynamoDB table. [S3 server-side encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/serv-side-encryption.html)

## State and locking

- State object `terraform-state/<project>/<environment>/terraform.tfstate` and lock object at that key plus `.tflock`.
- The bootstrap output `backend_configuration` carries the approved account, bucket, Region, project, environment and both keys. Generate a private `.tfbackend` with `render_backend_config.py` by binding this output to the approved lab JSON variables. The renderer refuses to overwrite an existing file. Recheck the same backend and variable fingerprints before planning/applying. Ordinary Terraform variables and outputs cannot configure a backend directly because backend initialization precedes evaluation.
- The partial S3 backend sets `encrypt = true` and `use_lockfile = true`. Native S3 locking is supported by the existing Terraform 1.10 minimum. Terraform acquires the lock with a conditional object create and releases it after checking the lock ID. An interrupted run can leave a current lock. Only the owner may invoke the stale-lock recovery gate after verifying that all potential holders have stopped.
- Use the default workspace and a separate bucket, key and dedicated state credential per environment. `workspace_key_prefix = terraform-state/<project>/<environment>/workspaces` scopes the discovery call that Terraform makes during initialization. There are no object permissions under that workspace prefix. The normal role cannot silently switch to another environment with the same credentials. The exact-key limits depend on the owner granting no additional broader S3 access to that role. [S3 backend configuration and IAM](https://developer.hashicorp.com/terraform/language/backend/s3) · [Terraform 1.15.5 workspace discovery](https://github.com/hashicorp/terraform/blob/v1.15.5/internal/backend/remote-state/s3/backend_state.go)

## Execution identities

| Identity | Scope |
| --- | --- |
| Bootstrap execution | Create one approved bucket and read/modify its five controls and tags. Scope resource to the exact bucket ARN and review Region. See the [bootstrap identity policy template](examples/bootstrap-execution-policy.json.example). It requires owner review and is never applied by Terraform. No state object access or delete-bucket grant. |
| Lab execution | Attach only the reviewed output `lab_state_policy_json` for this backend. `s3:ListBucket` applies to the dedicated environment bucket. When a prefix is supplied, it must match the state key, lock key or workspace discovery prefix. `GetObject` and `PutObject` apply to the exact state key. `GetObject`, `PutObject` and `DeleteObject` apply to the exact lock key. State deletion and version access are outside the normal role. |
| State recovery administrator | Use separately approved `recovery_state_policy_json` only for the incident. Grants the same scoped state and lock access and adds exact-prefix `ListBucketVersions` and `GetObjectVersion` on the state. It can restore state or remove a confirmed stale lock under owner gates. It cannot delete historical versions or the bucket. |
| EC2 SSM role | Only the approved Systems Manager node policy. No backend or transfer bucket access. |
| Ansible Controller | SSM transport and a separate file-transfer bucket in a later task. No state bucket access. |

Terraform checks state existence with `HeadObject`. S3 uses `s3:ListBucket` to distinguish a missing object (`404`) from forbidden access (`403`). `StringEqualsIfExists` accommodates the check's absent `s3:prefix`. It also allows listing object names without a prefix in that one bucket. Reserve the bucket for this environment's backend and keep object actions scoped to their exact keys. Verify effective authorization during fresh initialization at AWS-12-L1. [S3 HeadObject permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html) · [Terraform 1.15.5 state client](https://github.com/hashicorp/terraform/blob/v1.15.5/internal/backend/remote-state/s3/client.go) · [IAM condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html)

The bootstrap policy template uses the AWS provider 6.73.0 bucket metadata reads in addition to the APIs used for its five controls. The read permissions do not enable CORS, logging, public ACLs or additional resources. Substitute the partition, bucket and Region. Confirm effective permissions with the applicable account SCP, permissions boundary and short-lived session policy. The owner's decommission identity requires separate version-delete, bucket-delete and control removal permissions at AWS-16-S1. [Pinned AWS provider bucket read path](https://github.com/hashicorp/terraform-provider-aws/blob/v6.73.0/internal/service/s3/bucket.go)

## Retention and verification

Keep current and historical state versions, lock versions and delete markers. This root defines no automatic expiration or deletion. A released lock's prior versions remain visible in version history. S3 versioning helps recover overwritten or deleted current state within the bucket. It cannot recover permanently deleted versions or loss of the bucket/account. Terraform `prevent_destroy` operates only while the resource and guard remain in configuration. `force_destroy = false` keeps Terraform from emptying the bucket. To decommission, use the separate approved manifest, backup and destroy process in the runbook. Normal lab destruction keeps the bucket and state history.

Costs include current and historical state storage, acquired lock and delete marker history, S3 list/read/write requests, recovery operations and any transfer. SSE-S3 requires no project-managed KMS key. Optional KMS requests, keys or audit tooling require a separate decision. Verify usage and residual charges after lab teardown and after any backend decommission.

State, saved plans, crash reports and Terraform metadata can expose secrets even if outputs are marked sensitive. Use restricted local storage and do not commit or print these artifacts. The [runbook](../../../docs/TERRAFORM_STATE_RUNBOOK.md) covers bootstrap backups, lane selection for existing state, recovery and teardown. The [offline validation instructions](../README.md#state-and-offline-verification) apply to this root with the local mirror and readonly lock.
