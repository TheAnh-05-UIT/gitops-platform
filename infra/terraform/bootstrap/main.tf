locals {
  state_path           = "terraform-state/${var.project_name}/${var.environment}"
  state_key            = "${local.state_path}/terraform.tfstate"
  lock_key             = "${local.state_key}.tflock"
  workspace_key_prefix = "${local.state_path}/workspaces"
  state_object_arn     = "${aws_s3_bucket.state.arn}/${local.state_key}"
  lock_object_arn      = "${aws_s3_bucket.state.arn}/${local.lock_key}"

  lab_permissions = [
    {
      Sid      = "ListStateAndDiscoverWorkspaces"
      Effect   = "Allow"
      Action   = "s3:ListBucket"
      Resource = aws_s3_bucket.state.arn
      # S3 uses ListBucket to report a missing state object as NotFound on a prefixless HEAD.
      Condition = { StringEqualsIfExists = { "s3:prefix" = [
        local.state_key, local.lock_key, "${local.workspace_key_prefix}/"
      ] } }
    },
    {
      Sid      = "ReadWriteState"
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject"]
      Resource = local.state_object_arn
    },
    {
      Sid      = "ManageNativeLock"
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      Resource = local.lock_object_arn
    }
  ]

  recovery_permissions = concat(local.lab_permissions, [
    {
      Sid       = "ListStateAndLockHistory"
      Effect    = "Allow"
      Action    = "s3:ListBucketVersions"
      Resource  = aws_s3_bucket.state.arn
      Condition = { StringEquals = { "s3:prefix" = [local.state_key, local.lock_key] } }
    },
    {
      Sid      = "ReadStateVersion"
      Effect   = "Allow"
      Action   = "s3:GetObjectVersion"
      Resource = local.state_object_arn
    }
  ])
}

resource "aws_s3_bucket" "state" {
  bucket        = var.bucket_name
  region        = var.aws_region
  force_destroy = false

  tags = merge(var.resource_tags, {
    Name        = var.bucket_name
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.cost_allocation.owner
    CostCenter  = var.cost_allocation.cost_center
    ManagedBy   = "terraform"
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.state, aws_s3_bucket_ownership_controls.state]
}
