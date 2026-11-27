output "backend_configuration" {
  description = "Environment-bound manifest for rendering a local lab backend config. Contains no credentials."
  value = {
    account_id           = var.aws_account_id
    project_name         = var.project_name
    environment          = var.environment
    bucket               = aws_s3_bucket.state.bucket
    region               = var.aws_region
    key                  = local.state_key
    lock_key             = local.lock_key
    workspace_key_prefix = local.workspace_key_prefix
    encrypt              = true
    use_lockfile         = true
  }

  depends_on = [
    aws_s3_bucket_versioning.state,
    aws_s3_bucket_server_side_encryption_configuration.state,
    aws_s3_bucket_policy.state,
  ]
}

output "lab_state_policy_json" {
  description = "Unattached IAM identity policy for one environment's normal Terraform execution role."
  value       = jsonencode({ Version = "2012-10-17", Statement = local.lab_permissions })
}

output "recovery_state_policy_json" {
  description = "Unattached IAM identity policy for a separately authorized state recovery role."
  value       = jsonencode({ Version = "2012-10-17", Statement = local.recovery_permissions })
}
