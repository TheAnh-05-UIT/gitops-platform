mock_provider "aws" {
  override_during = plan
}

override_resource {
  target          = aws_s3_bucket.state
  override_during = plan
  values = {
    id  = "example-platform-lab-tfstate-a1b2"
    arn = "arn:aws:s3:::example-platform-lab-tfstate-a1b2"
  }
}

variables {
  bucket_name     = "example-platform-lab-tfstate-a1b2"
  aws_region      = "us-east-1"
  aws_account_id  = "000000000000"
  project_name    = "gitops-platform"
  environment     = "lab"
  cost_allocation = { owner = "platform-lab", cost_center = "engineering-lab" }
  resource_tags   = { Purpose = "terraform-state" }
}

run "bucket_protection_and_exact_tls_policy" {
  command = plan

  assert {
    condition = (
      aws_s3_bucket.state.bucket == var.bucket_name &&
      aws_s3_bucket.state.region == var.aws_region &&
      !aws_s3_bucket.state.force_destroy &&
      aws_s3_bucket.state.tags == tomap({
        Name        = var.bucket_name
        Project     = "gitops-platform"
        Environment = "lab"
        Owner       = "platform-lab"
        CostCenter  = "engineering-lab"
        ManagedBy   = "terraform"
        Purpose     = "terraform-state"
      })
    )
    error_message = "The bucket must use the explicit Region, ownership/cost tags and force_destroy=false."
  }

  assert {
    condition = (
      one(aws_s3_bucket_versioning.state.versioning_configuration).status == "Enabled" &&
      one(one(aws_s3_bucket_server_side_encryption_configuration.state.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256" &&
      one(aws_s3_bucket_ownership_controls.state.rule).object_ownership == "BucketOwnerEnforced" &&
      aws_s3_bucket_public_access_block.state.block_public_acls &&
      aws_s3_bucket_public_access_block.state.ignore_public_acls &&
      aws_s3_bucket_public_access_block.state.block_public_policy &&
      aws_s3_bucket_public_access_block.state.restrict_public_buckets &&
      toset([
        aws_s3_bucket_versioning.state.bucket,
        aws_s3_bucket_server_side_encryption_configuration.state.bucket,
        aws_s3_bucket_ownership_controls.state.bucket,
        aws_s3_bucket_public_access_block.state.bucket,
        aws_s3_bucket_policy.state.bucket
      ]) == toset([aws_s3_bucket.state.id])
    )
    error_message = "The same bucket must have versioning, explicit SSE-S3, ACLs disabled and all public access blocks."
  }

  assert {
    condition = jsonencode(jsondecode(aws_s3_bucket_policy.state.policy)) == jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = ["arn:aws:s3:::example-platform-lab-tfstate-a1b2", "arn:aws:s3:::example-platform-lab-tfstate-a1b2/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }]
    })
    error_message = "The entire bucket policy must deny non-TLS access and contain no grants."
  }
}

run "backend_keys_and_exact_identity_policies" {
  command = plan

  assert {
    condition = jsonencode(output.backend_configuration) == jsonencode({
      account_id           = "000000000000"
      project_name         = "gitops-platform"
      environment          = "lab"
      bucket               = "example-platform-lab-tfstate-a1b2"
      region               = "us-east-1"
      key                  = "terraform-state/gitops-platform/lab/terraform.tfstate"
      lock_key             = "terraform-state/gitops-platform/lab/terraform.tfstate.tflock"
      workspace_key_prefix = "terraform-state/gitops-platform/lab/workspaces"
      encrypt              = true
      use_lockfile         = true
    })
    error_message = "The backend settings must bind the approved account, environment and exact state and lock keys."
  }

  assert {
    condition = jsonencode(jsondecode(output.lab_state_policy_json)) == jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Sid      = "ListStateAndDiscoverWorkspaces"
          Effect   = "Allow"
          Action   = "s3:ListBucket"
          Resource = "arn:aws:s3:::example-platform-lab-tfstate-a1b2"
          Condition = { StringEqualsIfExists = { "s3:prefix" = [
            "terraform-state/gitops-platform/lab/terraform.tfstate",
            "terraform-state/gitops-platform/lab/terraform.tfstate.tflock",
            "terraform-state/gitops-platform/lab/workspaces/"
          ] } }
        },
        {
          Sid      = "ReadWriteState"
          Effect   = "Allow"
          Action   = ["s3:GetObject", "s3:PutObject"]
          Resource = "arn:aws:s3:::example-platform-lab-tfstate-a1b2/terraform-state/gitops-platform/lab/terraform.tfstate"
        },
        {
          Sid      = "ManageNativeLock"
          Effect   = "Allow"
          Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
          Resource = "arn:aws:s3:::example-platform-lab-tfstate-a1b2/terraform-state/gitops-platform/lab/terraform.tfstate.tflock"
        }
      ]
    })
    error_message = "Allow prefixless state existence checks in the dedicated bucket and keep object permissions scoped to the exact state and lock keys."
  }

  assert {
    condition = jsonencode(jsondecode(output.recovery_state_policy_json)) == jsonencode({
      Version = "2012-10-17"
      Statement = concat(jsondecode(output.lab_state_policy_json).Statement, [
        {
          Sid      = "ListStateAndLockHistory"
          Effect   = "Allow"
          Action   = "s3:ListBucketVersions"
          Resource = "arn:aws:s3:::example-platform-lab-tfstate-a1b2"
          Condition = { StringEquals = { "s3:prefix" = [
            "terraform-state/gitops-platform/lab/terraform.tfstate",
            "terraform-state/gitops-platform/lab/terraform.tfstate.tflock"
          ] } }
        },
        {
          Sid      = "ReadStateVersion"
          Effect   = "Allow"
          Action   = "s3:GetObjectVersion"
          Resource = "arn:aws:s3:::example-platform-lab-tfstate-a1b2/terraform-state/gitops-platform/lab/terraform.tfstate"
        }
      ])
    })
    error_message = "Recovery adds only scoped listing and historical state reads. State and version deletion remain excluded."
  }
}

run "other_environment_has_distinct_object_and_policy" {
  command = plan

  variables {
    environment = "demo"
  }

  assert {
    condition = (
      output.backend_configuration.key == "terraform-state/gitops-platform/demo/terraform.tfstate" &&
      output.backend_configuration.lock_key != run.backend_keys_and_exact_identity_policies.backend_configuration.lock_key &&
      output.backend_configuration.workspace_key_prefix != run.backend_keys_and_exact_identity_policies.backend_configuration.workspace_key_prefix &&
      !strcontains(output.lab_state_policy_json, "/lab/") &&
      !strcontains(output.recovery_state_policy_json, "/lab/") &&
      aws_s3_bucket.state.tags.Environment == "demo"
    )
    error_message = "Changing the environment must select distinct state and lock objects and policy scope."
  }
}

run "reject_reserved_bucket_prefix" {
  command = plan
  variables {
    bucket_name = "xn--not-a-state-bucket"
  }
  expect_failures = [var.bucket_name]
}

run "reject_reserved_bucket_suffix" {
  command = plan
  variables {
    bucket_name = "state-bucket--x-s3"
  }
  expect_failures = [var.bucket_name]
}

run "reject_account_regional_bucket_name" {
  command = plan
  variables {
    bucket_name = "state-bucket-an"
  }
  expect_failures = [var.bucket_name]
}

run "reject_dotted_or_ip_bucket_name" {
  command = plan
  variables {
    bucket_name = "192.0.2.1"
  }
  expect_failures = [var.bucket_name]
}

run "reject_bucket_name_too_short" {
  command = plan
  variables {
    bucket_name = "ab"
  }
  expect_failures = [var.bucket_name]
}

run "reject_invalid_environment_path" {
  command = plan
  variables {
    environment = "../prod"
  }
  expect_failures = [var.environment]
}

run "reject_invalid_project_path" {
  command = plan
  variables {
    project_name = "team/demo"
  }
  expect_failures = [var.project_name]
}

run "reject_invalid_region" {
  command = plan
  variables {
    aws_region = "us-east-1a"
  }
  expect_failures = [var.aws_region]
}

run "reject_invalid_account" {
  command = plan
  variables {
    aws_account_id = "not-an-account"
  }
  expect_failures = [var.aws_account_id]
}

run "reject_missing_owner" {
  command = plan
  variables {
    cost_allocation = { owner = "", cost_center = "platform" }
  }
  expect_failures = [var.cost_allocation]
}

run "reject_reserved_tag" {
  command = plan
  variables {
    resource_tags = { environment = "other" }
  }
  expect_failures = [var.resource_tags]
}
