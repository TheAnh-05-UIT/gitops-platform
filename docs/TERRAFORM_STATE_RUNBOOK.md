# Terraform state owner runbook

All AWS steps below are owner-executed under the [Manual Cloud Execution Policy](../AGENTS.md#manual-cloud-execution-policy). Live work requires P1.5.1 and P1.10 acceptance plus the applicable owner decision. AWS-11-S0 is a preflight subgate. The AWS-12 and AWS-13 subgates distinguish bootstrap plan and apply from lab initialization and plan. The bootstrap apply must take place before the lab plan. The AWS-12/13 recovery subgates apply only during an incident. An approval for one mutation grants no permission for another.

## Private setup

Run these PowerShell commands in an encrypted, access-restricted working directory outside Git on the approved workstation. Keep a separate protected backup location. Avoid shared terminals, transcripts and synced folders. Use the approved Terraform CLI version and provider lock, a clean profile-based AWS session, and an approved Terraform CLI configuration. Clear inherited direct AWS credentials, endpoint overrides, `AWS_DEFAULT_PROFILE`, `TF_CLI_ARGS*`, `TF_DATA_DIR`, `TF_WORKSPACE` and `TF_VAR_*`. Do not reuse test directories or another environment's backend metadata. Replace placeholders privately. Gate commands use the same variables, which must be re-established from approved records after reopening the shell.

```powershell
$ErrorActionPreference = 'Stop'
$Platform = (Resolve-Path '<reviewed Platform root>').Path
$RunRoot = (Resolve-Path '<protected environment directory outside Git>').Path
$BackupRoot = (Resolve-Path '<separate protected backup directory>').Path
$BootstrapSource = Join-Path $Platform 'infra/terraform/bootstrap'
$LabSource = Join-Path $Platform 'infra/terraform/lab'
$BootstrapRoot = Join-Path $RunRoot 'bootstrap'
$LabRoot = Join-Path $RunRoot 'lab'
$ModuleRoot = Join-Path $RunRoot 'modules'
$Account = '<approved 12-digit AWS account ID>'
$Region = '<approved AWS Region>'
$BootstrapProfile = '<short-lived bootstrap profile>'
$LabProfile = '<short-lived Terraform profile scoped to this environment>'
$RecoveryProfile = '<separately authorized recovery profile>'
$DecommissionProfile = '<temporary decommission profile>'
$BootstrapVars = Join-Path $RunRoot 'bootstrap.tfvars.json'
$LabVars = Join-Path $RunRoot 'lab.tfvars.json'
$BootstrapPlan = Join-Path $RunRoot 'bootstrap.tfplan'
$LabPlan = Join-Path $RunRoot 'lab.tfplan'
$ManifestFile = Join-Path $RunRoot 'backend-manifest.json'
$BackendConfig = Join-Path $RunRoot 'lab.s3.tfbackend'
$BootstrapState = Join-Path $BootstrapRoot 'terraform.tfstate'
$LabState = Join-Path $LabRoot 'terraform.tfstate'
if ($Account -notmatch '^\d{12}$' -or $Region -notmatch '^[a-z]{2}(-[a-z]+)+-[1-9][0-9]*$') {
    throw 'Supply the approved account and Region.'
}
function Invoke-Checked {
    $Program = $args[0]
    $Arguments = @($args | Select-Object -Skip 1)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited $LASTEXITCODE. Stop this gate." }
}
function Invoke-ApprovedAws {
    Invoke-Checked aws --profile $env:AWS_PROFILE --region $Region --no-cli-pager @args
}
function Select-ApprovedProfile($Profile) {
    $env:AWS_PROFILE = $Profile
    $env:AWS_REGION = $Region
    $env:AWS_DEFAULT_REGION = $Region
    $Observed = Invoke-ApprovedAws sts get-caller-identity --output json | ConvertFrom-Json
    if ($Observed.Account -ne $Account) { throw 'Unexpected AWS account.' }
    # Compare $Observed.Arn privately with the approved role before proceeding.
}
function Assert-DefaultWorkspace($Root) {
    if ((Invoke-Checked terraform "-chdir=$Root" workspace show) -ne 'default') {
        throw 'Only the default workspace is approved.'
    }
}
function Assert-Hash($Path, $Expected) {
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Expected) {
        throw 'Artifact fingerprint differs from approval.'
    }
}
function Assert-LabBackendInputs {
    Assert-Hash $BackendConfig $ApprovedBackendHash
    Assert-Hash $LabVars $ApprovedLabVarsHash
}
function Get-StateObjects($Key) {
    Invoke-ApprovedAws s3api list-objects-v2 --bucket $Bucket --prefix $Key --expected-bucket-owner $Account --output json | ConvertFrom-Json
}
function Get-StateVersions($Key) {
    Invoke-ApprovedAws s3api list-object-versions --bucket $Bucket --prefix $Key --expected-bucket-owner $Account --output json | ConvertFrom-Json
}
```

For a new working copy, use the following once. Resume existing work from its approved private root and local bootstrap state. Prepare the two private JSON variable files from the [bootstrap example](../infra/terraform/bootstrap/examples/lab.tfvars.json.example) and [lab examples](../infra/terraform/lab/examples/). Match project, environment and Region. Record the approved input fingerprints. Pin inputs for each plan/apply with no CLI or environment overrides of their identity fields.

```powershell
foreach ($Directory in @($BootstrapRoot, $LabRoot, $ModuleRoot)) {
    if (Test-Path -LiteralPath $Directory) { throw 'Use a fresh protected source directory.' }
    New-Item -ItemType Directory -Path $Directory | Out-Null
}
Get-ChildItem -LiteralPath $BootstrapSource -File -Filter '*.tf' | Copy-Item -Destination $BootstrapRoot
Get-ChildItem -LiteralPath $LabSource -File -Filter '*.tf' | Copy-Item -Destination $LabRoot
Copy-Item -LiteralPath (Join-Path $BootstrapSource '.terraform.lock.hcl') -Destination $BootstrapRoot
Copy-Item -LiteralPath (Join-Path $LabSource '.terraform.lock.hcl') -Destination $LabRoot
foreach ($Module in @('networking','security','compute','iam','ansible-inventory')) {
    $Source = Join-Path $Platform "infra/terraform/modules/$Module"
    $Destination = Join-Path $ModuleRoot $Module
    New-Item -ItemType Directory -Path $Destination | Out-Null
    Get-ChildItem -LiteralPath $Source -File -Filter '*.tf' | Copy-Item -Destination $Destination
}
```

## AWS-11-S0 · Backend identity and permission preflight

**Read-only.** Working directory `$BootstrapRoot`. Requires AWS-11 approval, short-lived approved sessions, budget and an approved bucket name, Region, project and environment. If the owner uses AWS SSO, authenticate each needed profile with `Invoke-Checked aws sso login --profile $BootstrapProfile` (replace the profile per identity). Verify each role's ARN and boundary privately.

```powershell
Set-Location -LiteralPath $BootstrapRoot
Select-ApprovedProfile $BootstrapProfile
$BootstrapInput = Get-Content -Raw -LiteralPath $BootstrapVars | ConvertFrom-Json
$LabInput = Get-Content -Raw -LiteralPath $LabVars | ConvertFrom-Json
$Bucket = $BootstrapInput.bucket_name
$LabProject = if ($null -eq $LabInput.project_name) { 'gitops-platform' } else { $LabInput.project_name }
$LabEnvironment = if ($null -eq $LabInput.environment) { 'lab' } else { $LabInput.environment }
if ($BootstrapInput.aws_account_id -ne $Account -or $BootstrapInput.aws_region -ne $Region -or
    $LabInput.aws_region -ne $Region -or $BootstrapInput.project_name -cne $LabProject -or
    $BootstrapInput.environment -cne $LabEnvironment) { throw 'Bootstrap and lab inputs do not match approval.' }
Get-FileHash -Algorithm SHA256 $BootstrapVars, $LabVars
Invoke-Checked terraform version
```

Review [bootstrap IAM capabilities](../infra/terraform/bootstrap/README.md#execution-identities) and ensure the lab and recovery profiles will have only the exact environment-scoped state permissions in addition to their approved purposes. EC2 and the Ansible Controller have no state permission. Bucket availability is unverified until owner execution. A 403 or missing response never proves ownership or availability. Stop on a mismatch or ambiguous scope. Read requests may incur charges. Share only identity-match and permission/budget review status.

## AWS-12-S1 · Bootstrap init and plan

**Read/planning.** Working directory `$BootstrapRoot`. Requires AWS-11-S0 acceptance, reviewed source and private inputs. If a bucket or bootstrap state already exists, match its ownership and state before resuming.

```powershell
Select-ApprovedProfile $BootstrapProfile
Invoke-Checked terraform "-chdir=$BootstrapRoot" init -input=false -lockfile=readonly
Assert-DefaultWorkspace $BootstrapRoot
Invoke-Checked terraform "-chdir=$BootstrapRoot" plan "-var-file=$BootstrapVars" "-out=$BootstrapPlan"
Invoke-Checked terraform "-chdir=$BootstrapRoot" show $BootstrapPlan
Get-FileHash -Algorithm SHA256 -LiteralPath $BootstrapPlan
```

A fresh plan adds six resource addresses for one bucket and five controls. Review tags, Region, public blocks, versioning, SSE-S3, object ownership and TLS. Reject drift, existing-name ambiguity, permission errors or unexpected deletes and replacements. Preserve local state and make a new reviewed plan after resolution. Read requests may cost. Share only plan hash and counts.

## AWS-13-S1 · Bootstrap apply

**Mutation.** Working directory `$BootstrapRoot`. Requires specific owner approval for the exact AWS-12-S1 plan fingerprint, scope, target and cost. Saved-plan apply does not prompt.

```powershell
Select-ApprovedProfile $BootstrapProfile
Assert-Hash $BootstrapPlan '<owner-approved AWS-12-S1 SHA-256>'
Invoke-Checked terraform "-chdir=$BootstrapRoot" apply $BootstrapPlan
```

Expect one bucket and five controls, with no new identity grants. Costs are S3 requests and later storage. On partial failure preserve the local state and its backup and review a corrective plan. Never initialize the lab as a retry or roll back by deleting the bucket. Share counts and completion status.

## AWS-13-S2 · Verify bucket and back up bootstrap state

**AWS read-only and protected local writes.** Working directory `$BootstrapRoot`. Requires AWS-13-S1 acceptance for lab handoff. Preserve local state promptly, including after partial apply if the file exists.

```powershell
$Backup = Join-Path $BackupRoot ("bootstrap-{0}.tfstate" -f [guid]::NewGuid())
Copy-Item -LiteralPath $BootstrapState -Destination $Backup
Assert-Hash $Backup (Get-FileHash -LiteralPath $BootstrapState).Hash
Select-ApprovedProfile $BootstrapProfile
Invoke-ApprovedAws s3api head-bucket --bucket $Bucket --expected-bucket-owner $Account
foreach ($Check in @('get-bucket-location','get-bucket-versioning','get-bucket-encryption',
    'get-public-access-block','get-bucket-ownership-controls','get-bucket-policy-status')) {
    Invoke-ApprovedAws s3api $Check --bucket $Bucket --expected-bucket-owner $Account
}
$Policy = Invoke-ApprovedAws s3api get-bucket-policy --bucket $Bucket --expected-bucket-owner $Account | ConvertFrom-Json
$TlsPolicy = $Policy.Policy | ConvertFrom-Json
Invoke-Checked terraform "-chdir=$BootstrapRoot" output -json backend_configuration |
    Set-Content -LiteralPath $ManifestFile -Encoding utf8
Invoke-Checked terraform "-chdir=$BootstrapRoot" output -raw lab_state_policy_json |
    Set-Content -LiteralPath (Join-Path $RunRoot 'lab-state-policy.json') -Encoding utf8
Invoke-Checked terraform "-chdir=$BootstrapRoot" output -raw recovery_state_policy_json |
    Set-Content -LiteralPath (Join-Path $RunRoot 'recovery-state-policy.json') -Encoding utf8
```

Expect correct owner/Region (empty location constraint for us-east-1), versioning `Enabled`, `AES256`, four public blocks, `BucketOwnerEnforced`, `IsPublic=false` and one deny-only TLS statement. Allow 15 minutes after first enabling versioning before object writes. Have the owner review and assign the exported IAM policies to the designated identities through a separate approval. Stop on missing controls, unverified backup or drift. Read requests may cost. Share status of controls and backup checksum match only.

The bootstrap state, its `.backup`, the saved plan and exported settings remain outside Git. Retain an independent encrypted copy after each change with revision and checksum. If local bootstrap state is lost, freeze writers and restore only a verified backup into a new protected copy with matching revision, lineage and serial. Review a plan before any mutation. If there is no trustworthy copy, open a separate state reconstruction review. [S3 versioning enablement](https://docs.aws.amazon.com/AmazonS3/latest/userguide/manage-versioning-examples.html)

## AWS-12-L0 · Bind backend and detect state

**Local render and AWS read-only.** Working directory `$LabRoot`. Requires verified backend and owner-approved recovery access. Set the same private parameters on any later execution host.

```powershell
Invoke-Checked python -B (Join-Path $BootstrapSource 'render_backend_config.py') --bootstrap-output $ManifestFile --lab-tfvars $LabVars --account-id $Account --out $BackendConfig
$Backend = Get-Content -Raw -LiteralPath $ManifestFile | ConvertFrom-Json
if ($Backend.bucket -ne $Bucket) { throw 'Unexpected backend bucket.' }
$StateKey = $Backend.key
$LockKey = $Backend.lock_key
Select-ApprovedProfile $RecoveryProfile
$CurrentState = @((Get-StateObjects $StateKey).Contents | Where-Object Key -CEQ $StateKey)
$StateHistory = Get-StateVersions $StateKey
$Versions = @($StateHistory.Versions | Where-Object Key -CEQ $StateKey)
$Markers = @($StateHistory.DeleteMarkers | Where-Object Key -CEQ $StateKey)
$LiveLocks = @((Get-StateObjects $LockKey).Contents | Where-Object Key -CEQ $LockKey)
foreach ($Directory in @($LabRoot, $LabSource, (Join-Path $Platform 'infra/terraform'))) {
    Get-ChildItem -LiteralPath $Directory -Force |
        Where-Object { $_.Name -like '*.tfstate*' -or $_.Name -eq '.terraform' } |
        Select-Object DirectoryName, Name
}
Get-FileHash -Algorithm SHA256 $BackendConfig, $LabVars
```

Also check owner-held local state paths, previous backend metadata and alternate workspaces. Keep candidate copies private and distinguish existing draft addresses from the reviewed lab module addresses.

| Evidence | Route |
| --- | --- |
| No applicable local state, remote object/history/delete marker or live lock | AWS-12-L1 fresh. |
| Expected current remote state with verified lineage and no competing local state | AWS-12-L1 reconnect. Privately inspect a protected copy before approval. |
| Approved same-lab local state and no remote object/history/delete marker or live lock | AWS-12-L2, with separate migration approval. |
| Missing current object with history, conflicting or legacy state, nondefault workspace, unexpected lineage or live lock | Stop. Use AWS-12-R0 or a separate legacy state review. |

Record the approved hashes as `$ApprovedBackendHash` and `$ApprovedLabVarsHash` for the subsequent gates. Report only existence flags and selected route. A denied list is an error. Requests may incur costs. Correct mismatched scope without overwriting the backend file. Archive an obsolete rendered file privately and use a fresh output path.

## AWS-12-L1 · Initialize fresh or reconnect

**Owner backend initialization.** Working directory `$LabRoot`. Requires AWS-12-L0 approval of the exact route, role and input fingerprints. Initialization may interact with remote state.

```powershell
Assert-LabBackendInputs
Select-ApprovedProfile $LabProfile
Invoke-Checked terraform "-chdir=$LabRoot" init -reconfigure -input=false -lockfile=readonly "-backend-config=$BackendConfig"
Assert-DefaultWorkspace $LabRoot
```

Expect success against the approved default workspace and bucket. Report init status and fresh/reconnect classification. Read and potential state/lock requests incur costs. On a `403`, preserve local and remote metadata, verify the exact approved role and bucket, and check the effective `HeadObject` and bucket-scoped `s3:ListBucket` permissions before retrying. Treat absence only as confirmed by AWS-12-L0. [Backend IAM capabilities](../infra/terraform/bootstrap/README.md#execution-identities)

## AWS-12-L2 · Migrate an approved same-lab local state

**State mutation.** Working directory `$LabRoot`, a private migration copy. Requires AWS-12-L0 to prove the remote target is empty, including versions and delete markers. Freeze other writers. Approve the local state fingerprint, verified lineage, serial, addresses and exact destination. The original draft state requires a separate mapping/import review. Keep the original source untouched.

```powershell
Assert-LabBackendInputs
$ApprovedLocalState = '<protected approved local state>'
$ApprovedSourceHash = '<owner-approved SHA-256>'
Assert-Hash $ApprovedLocalState $ApprovedSourceHash
if ((Test-Path -LiteralPath $LabState) -or (Test-Path -LiteralPath (Join-Path $LabRoot '.terraform'))) {
    throw 'Migration copy is not clean.'
}
$MigrationBackup = Join-Path $BackupRoot ("lab-before-migration-{0}.tfstate" -f [guid]::NewGuid())
Copy-Item -LiteralPath $ApprovedLocalState -Destination $MigrationBackup
Assert-Hash $MigrationBackup $ApprovedSourceHash
Copy-Item -LiteralPath $MigrationBackup -Destination $LabState
$MigrationOverride = Join-Path $LabRoot 'p15_migration_override.tf'
if (Test-Path -LiteralPath $MigrationOverride) { throw 'Unexpected override.' }
@('terraform {', '  backend "local" {}', '}') | Set-Content -LiteralPath $MigrationOverride -Encoding ascii
Invoke-Checked terraform "-chdir=$LabRoot" init -reconfigure -input=false -lockfile=readonly
Assert-DefaultWorkspace $LabRoot
Remove-Item -LiteralPath $MigrationOverride
Select-ApprovedProfile $LabProfile
Invoke-Checked terraform "-chdir=$LabRoot" init -migrate-state -lockfile=readonly "-backend-config=$BackendConfig"
Assert-DefaultWorkspace $LabRoot
$MigratedCopy = Join-Path $BackupRoot ("lab-after-migration-{0}.tfstate" -f [guid]::NewGuid())
Invoke-ApprovedAws s3api get-object --bucket $Bucket --key $StateKey --expected-bucket-owner $Account $MigratedCopy | Out-Null
$Before = Get-Content -Raw -LiteralPath $MigrationBackup | ConvertFrom-Json
$After = Get-Content -Raw -LiteralPath $MigratedCopy | ConvertFrom-Json
if ($Before.lineage -ne $After.lineage -or $After.serial -lt $Before.serial) {
    throw 'Migrated state does not match the approved source.'
}
```

Accept the interactive prompt only after checking the approved local source and empty S3 target. Never use `-force-copy`. Verify address set and resource IDs privately. Reject unexpected replacements in the subsequent plan. A missing prompt, mismatch, conflict or error stops the gate. Keep both copies, metadata and original state and use AWS-12-R0. Migration adds read/write/lock requests and retained versions. Share lineage/address match and migration outcome only. [Terraform init and migration](https://developer.hashicorp.com/terraform/cli/commands/init)

## AWS-12-L3 · Verify locking and review the lab plan

**AWS planning with lock writes.** Working directory `$LabRoot`. Requires accepted initialization or migration and the exact recorded backend and vars hashes. Use the default workspace.

```powershell
Assert-LabBackendInputs
Select-ApprovedProfile $RecoveryProfile
$LockBefore = Get-StateVersions $LockKey
Select-ApprovedProfile $LabProfile
Assert-DefaultWorkspace $LabRoot
Invoke-Checked terraform "-chdir=$LabRoot" plan "-var-file=$LabVars" -lock-timeout=60s "-out=$LabPlan"
Invoke-Checked terraform "-chdir=$LabRoot" show $LabPlan
Get-FileHash -Algorithm SHA256 -LiteralPath $LabPlan
Select-ApprovedProfile $RecoveryProfile
$LockAfter = Get-StateVersions $LockKey
$LockNow = Get-StateObjects $LockKey
```

Expect a new exact lock version and release delete marker, no current lock after exit and the reviewed lab plan. An approved contention check may run `terraform "-chdir=$LockObserverRoot" plan "-var-file=$LabVars" -lock-timeout=5s` with the lab profile from a second protected copy already initialized by AWS-12-L1 to the same backend while the first plan is observed holding the lock. Only an actual overlap and lock error establish contention behavior. Inspect a lock conflict through AWS-12-R0. Never bypass locks. Read/lock requests and version history cost money. Share plan hash, counts and lock observations. AWS-13 cluster apply requires its own approval. Re-select the lab profile, verify the exact plan hash, then run `Invoke-Checked terraform "-chdir=$LabRoot" apply $LabPlan` only at that gate. [Native S3 locking](https://developer.hashicorp.com/terraform/language/backend/s3)


## AWS-12-R0 · Inspect state and lock history

**Read-only incident review.** Working directory `$LabRoot`. Requires the recovery identity, exact backend fingerprint, approved account/Region, and a freeze on writers. Identify whether an operation still owns the lock before considering any mutation.

```powershell
Select-ApprovedProfile $RecoveryProfile
$IncidentState = Get-StateVersions $StateKey
$IncidentLock = Get-StateObjects $LockKey
$CandidateVersion = '<privately reviewed state version ID>'
$CandidateFile = Join-Path $BackupRoot ("lab-candidate-{0}.tfstate" -f [guid]::NewGuid())
# Run the following only when inspecting a historical state version.
Invoke-ApprovedAws s3api get-object --bucket $Bucket --key $StateKey --version-id $CandidateVersion --expected-bucket-owner $Account $CandidateFile | Out-Null
$CandidateState = Get-Content -Raw -LiteralPath $CandidateFile | ConvertFrom-Json
```

Check lineage, serial, state addresses and actual resource identities against the approved record. Preserve any `errored.tfstate` emitted after a failed backend write. Reconcile it with the remote copy before retrying any operation. If a lock exists, download the **current** lock metadata privately with `Invoke-ApprovedAws s3api get-object --bucket $Bucket --key $LockKey --expected-bucket-owner $Account $ProtectedLockFile`, using a new path in the encrypted directory. Keep ID, operation and owner private. Expected evidence is a verified candidate or lock disposition. A missing or suspect candidate, mismatched lineage or ongoing operation stops recovery. Reads and backup storage may cost. This gate has no remote mutation. Version history cannot recover a lost bucket, permanently deleted versions or a compromised account.

## AWS-13-R1 · Remove a confirmed stale lock

**Lock mutation.** Working directory `$LabRoot` with the verified backend initialized. Requires AWS-12-R0, exact current lock ID, a verified backup where available and owner confirmation that no process, runner or other operator still holds the lock.

```powershell
Select-ApprovedProfile $RecoveryProfile
Assert-DefaultWorkspace $LabRoot
$LockId = '<reviewed current lock ID>'
Invoke-Checked terraform "-chdir=$LabRoot" force-unlock $LockId
$LockNow = Get-StateObjects $LockKey
```

Confirm Terraform's prompt only for the exact incident. Never use `-force` or delete the live lock directly. Expect lock release with the state unchanged. Share release outcome and confirmation that writers stayed frozen. Lock reads/releases and retained history may cost. If the lock changed or Terraform cannot see the state, stop and escalate. No blind retry.

## AWS-13-R2 · Restore an approved historical state version

**State mutation.** Working directory `$LabRoot`. Requires AWS-12-R0, an approved candidate hash, verified candidate lineage and reconciliation against actual resources. Freeze all writers and confirm the absence of a live lock. Restoring old state can forget resources created later or reference deleted resources. If current state exists, back it up to a new encrypted path before approval. Record its ETag from the same download response. The owner must approve the ETag or verified absence alongside the candidate.

```powershell
Select-ApprovedProfile $RecoveryProfile
$ApprovedCandidateHash = '<owner-approved candidate SHA-256>'
Assert-Hash $CandidateFile $ApprovedCandidateHash
if (@((Get-StateObjects $LockKey).Contents | Where-Object Key -CEQ $LockKey).Count) { throw 'Lock exists.' }
# Use exactly one condition authorized for this incident.
$Condition = @('--if-match','<approved current ETag without quotes>')
# If separately approved and absence was verified instead: $Condition = @('--if-none-match','*')
Invoke-ApprovedAws s3api put-object --bucket $Bucket --key $StateKey --body $CandidateFile --server-side-encryption AES256 --expected-bucket-owner $Account @Condition | Out-Null
$RestoredCopy = Join-Path $BackupRoot ("lab-restored-{0}.tfstate" -f [guid]::NewGuid())
Invoke-ApprovedAws s3api get-object --bucket $Bucket --key $StateKey --expected-bucket-owner $Account $RestoredCopy | Out-Null
Assert-Hash $RestoredCopy $ApprovedCandidateHash
```

The conditional PUT creates a new current version, preserves former versions and bypasses Terraform's normal serial and lock handling. The freeze and separate approval are required. Stop on precondition or authorization failure. Do not retry with an unconditional PUT. Retain the former current copy and use the same reviewed process if rollback becomes necessary. Keep writers frozen until a new AWS-12 reconciliation plan is reviewed. Share hash match, approval and reconciliation status only. Costs include recovery reads, writes and retained versions. [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)

## AWS-16 · Lab destruction

**Reviewed teardown.** Working directory `$LabRoot`. Requires the existing AWS-16 gate, independent state backup, retention decision, correct default workspace and no conflicting lock. Planning and application are distinct approvals.

```powershell
Select-ApprovedProfile $LabProfile
Assert-DefaultWorkspace $LabRoot
$LabDestroyPlan = Join-Path $RunRoot 'lab-destroy.tfplan'
Invoke-Checked terraform "-chdir=$LabRoot" plan -destroy "-var-file=$LabVars" "-out=$LabDestroyPlan"
Invoke-Checked terraform "-chdir=$LabRoot" show $LabDestroyPlan
Get-FileHash -LiteralPath $LabDestroyPlan
# At the separate owner apply approval:
Assert-Hash $LabDestroyPlan '<owner-approved lab destroy SHA-256>'
Invoke-Checked terraform "-chdir=$LabRoot" apply $LabDestroyPlan
```

Expect lab resources removed according to the saved plan and state written to the retained backend. Stop on partial teardown and review residuals before retrying. Check EBS, NAT/EIP and other retained resources and charges separately. Share counts and residual resource classes. S3 history and requests remain billable.

## AWS-16-S0 · Backend decommission plan and version review

**Read-only inventory and destroy planning.** Working directory `$DecommissionRoot`, a protected owner-reviewed copy of bootstrap source and the exact latest local bootstrap state. Requires completed lab teardown, all writers and old credentials revoked or frozen, no live lock, and verified encrypted backups including any state required for retention. Temporary decommission access is scoped to this bucket. Provider control deletion and version deletion require separate permissions from normal bootstrap.

```powershell
$DecommissionRoot = '<protected bootstrap decommission copy>'
$BackendDestroyPlan = Join-Path $RunRoot 'backend-destroy.tfplan'
Select-ApprovedProfile $DecommissionProfile
$Inventory = Invoke-ApprovedAws s3api list-object-versions --bucket $Bucket --expected-bucket-owner $Account --output json | ConvertFrom-Json
$Uploads = Invoke-ApprovedAws s3api list-multipart-uploads --bucket $Bucket --expected-bucket-owner $Account --output json | ConvertFrom-Json
$Versions = @($Inventory.Versions | Where-Object Key) + @($Inventory.DeleteMarkers | Where-Object Key)
if (@($Versions | Where-Object { $_.Key -cnotin @($StateKey,$LockKey) }).Count -or
    @($Uploads.Uploads | Where-Object Key).Count -or
    @((Get-StateObjects $LockKey).Contents | Where-Object Key -CEQ $LockKey).Count) {
    throw 'Unexpected keys, pending uploads or a live lock.'
}
# With owner authorization edit only the private copy to set prevent_destroy = false.
# Keep force_destroy = false and preserve the canonical source and its state.
Invoke-Checked terraform "-chdir=$DecommissionRoot" init -input=false -lockfile=readonly
Assert-DefaultWorkspace $DecommissionRoot
Invoke-Checked terraform "-chdir=$DecommissionRoot" plan -destroy "-var-file=$BootstrapVars" "-out=$BackendDestroyPlan"
Invoke-Checked terraform "-chdir=$DecommissionRoot" show $BackendDestroyPlan
Get-FileHash -LiteralPath $BackendDestroyPlan
```

Expect only the bucket and five controls in the destroy plan. Keep the approved exact version inventory and plan hash in the private record. Stop on unapproved objects, incomplete multipart uploads, active lock or unexpected plan changes. Costs are read requests. There is no remote change to roll back. Retain the bucket instead if its name must stay reserved.

## AWS-16-S1 · Separately approved purge and backend deletion

**Destructive mutation.** Working directory `$DecommissionRoot`. Requires explicit owner approval of the exact AWS-16-S0 manifest and plan hash, backup integrity and continuing writer freeze. Give the temporary profile `s3:DeleteObjectVersion` only on the two approved object keys and delete/control privileges only for the bucket in the reviewed plan. Never run an unscoped recursive deletion.

```powershell
Select-ApprovedProfile $DecommissionProfile
Assert-Hash $BackendDestroyPlan '<owner-approved backend destroy SHA-256>'
$Fresh = Invoke-ApprovedAws s3api list-object-versions --bucket $Bucket --expected-bucket-owner $Account --output json | ConvertFrom-Json
$FreshUploads = Invoke-ApprovedAws s3api list-multipart-uploads --bucket $Bucket --expected-bucket-owner $Account --output json | ConvertFrom-Json
$FreshVersions = @($Fresh.Versions | Where-Object Key) + @($Fresh.DeleteMarkers | Where-Object Key)
$ApprovedPairs = @($Versions | ForEach-Object { "$($_.Key)|$($_.VersionId)" } | Sort-Object)
$FreshPairs = @($FreshVersions | ForEach-Object { "$($_.Key)|$($_.VersionId)" } | Sort-Object)
if (($ApprovedPairs -join '|') -cne ($FreshPairs -join '|') -or
    @($FreshUploads.Uploads | Where-Object Key).Count -or
    @((Get-StateObjects $LockKey).Contents | Where-Object Key -CEQ $LockKey).Count) {
    throw 'Versions, uploads or locks changed.'
}
foreach ($Item in $FreshVersions) {
    if ($Item.Key -cnotin @($StateKey,$LockKey) -or -not $Item.VersionId) { throw 'Unapproved version.' }
    Invoke-ApprovedAws s3api delete-object --bucket $Bucket --key $Item.Key --version-id $Item.VersionId --expected-bucket-owner $Account | Out-Null
}
$Empty = Invoke-ApprovedAws s3api list-object-versions --bucket $Bucket --expected-bucket-owner $Account --output json | ConvertFrom-Json
if (@($Empty.Versions | Where-Object Key).Count -or @($Empty.DeleteMarkers | Where-Object Key).Count) {
    throw 'Bucket is not empty.'
}
Invoke-Checked terraform "-chdir=$DecommissionRoot" apply $BackendDestroyPlan
```

Expect exact-version deletion and bucket/control removal. Verify absence using approved inventory, revoke temporary permissions and verify residual charges after billing catches up. A forbidden response does not establish deletion. Permanently deleted versions cannot be restored through S3. On a partial failure stop, preserve remaining state and backups, inventory residuals and seek a new approval. Report counts, backup retention and residual billing status only.
