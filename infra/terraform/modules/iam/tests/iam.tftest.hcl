mock_provider "aws" {
  override_during = plan
}


override_resource {
  target          = aws_iam_role.node
  override_during = plan
  values = {
    arn = "arn:aws:iam::123456789012:role/fixture-role"
  }
}

override_resource {
  target          = aws_iam_instance_profile.node
  override_during = plan
  values = {
    arn = "arn:aws:iam::123456789012:instance-profile/fixture-profile"
  }
}

variables {
  project_name         = "gitops-platform"
  environment          = "lab"
  aws_region           = "us-east-1"
  administration       = "ssm"
  node_roles           = ["server", "worker"]
  required_permissions = ["ssm-managed-node"]
  tags                 = { Project = "gitops-platform", Environment = "lab", Owner = "platform-lab", CostCenter = "engineering-lab", ManagedBy = "terraform" }
}


run "exact_ec2_trust_and_only_ssm_attachment" {
  command = plan

  assert {
    condition = jsonencode(jsondecode(aws_iam_role.node.assume_role_policy)) == jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }]
    })
    error_message = "The complete role trust policy must permit only the EC2 service to assume the role."
  }

  assert {
    condition = (
      aws_iam_instance_profile.node.role == aws_iam_role.node.name &&
      aws_iam_role_policy_attachment.ssm.role == aws_iam_role.node.name &&
      aws_iam_role_policy_attachment.ssm.policy_arn == "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" &&
      output.ssm_policy_arn == aws_iam_role_policy_attachment.ssm.policy_arn &&
      aws_iam_role.node.tags.Owner == "platform-lab" &&
      aws_iam_instance_profile.node.tags.CostCenter == "engineering-lab"
    )
    error_message = "The only attachment must be AmazonSSMManagedInstanceCore on the profile's EC2 role."
  }

  assert {
    condition = (
      output.instance_profile_names_by_role == tomap({ server = aws_iam_instance_profile.node.name, worker = aws_iam_instance_profile.node.name }) &&
      output.role_arns_by_role == tomap({ server = "arn:aws:iam::123456789012:role/fixture-role", worker = "arn:aws:iam::123456789012:role/fixture-role" }) &&
      output.instance_profile_arns_by_role == tomap({ server = "arn:aws:iam::123456789012:instance-profile/fixture-profile", worker = "arn:aws:iam::123456789012:instance-profile/fixture-profile" })
    )
    error_message = "The contract must project the one role and profile to both node roles."
  }
}


run "minimal_projects_only_server" {
  command = plan

  variables {
    node_roles = ["server"]
  }

  assert {
    condition     = toset(keys(output.role_arns_by_role)) == toset(["server"]) && toset(keys(output.instance_profile_names_by_role)) == toset(["server"])
    error_message = "Minimal exposes only the server profile."
  }
}


run "govcloud_uses_its_partition" {
  command = plan

  variables {
    aws_region = "us-gov-west-1"
  }

  assert {
    condition = (
      aws_iam_role_policy_attachment.ssm.policy_arn == "arn:aws-us-gov:iam::aws:policy/AmazonSSMManagedInstanceCore" &&
      jsonencode(jsondecode(aws_iam_role.node.assume_role_policy)) == jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Effect    = "Allow"
          Principal = { Service = "ec2.amazonaws.com" }
          Action    = "sts:AssumeRole"
        }]
      })
    )
    error_message = "The managed policy ARN must match the Region partition and preserve EC2-only trust."
  }
}


run "china_uses_its_partition" {
  command = plan

  variables {
    aws_region = "cn-north-1"
  }

  assert {
    condition = (
      aws_iam_role_policy_attachment.ssm.policy_arn == "arn:aws-cn:iam::aws:policy/AmazonSSMManagedInstanceCore" &&
      jsonencode(jsondecode(aws_iam_role.node.assume_role_policy)) == jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Effect    = "Allow"
          Principal = { Service = "ec2.amazonaws.com" }
          Action    = "sts:AssumeRole"
        }]
      })
    )
    error_message = "The managed policy ARN must match the Region partition and preserve EC2-only trust."
  }
}


run "reject_state_and_s3_permissions" {
  command = plan

  variables {
    required_permissions = ["ssm-managed-node", "state-write", "s3-transfer"]
  }

  expect_failures = [var.required_permissions]
}


run "reject_ssh_administration" {
  command = plan

  variables {
    administration = "ssh"
  }

  expect_failures = [var.administration]
}


run "reject_unrecognized_node_role" {
  command = plan

  variables {
    node_roles = ["server", "operator"]
  }

  expect_failures = [var.node_roles]
}


run "reject_unsupported_partition" {
  command = plan

  variables {
    aws_region = "us-iso-east-1"
  }

  expect_failures = [var.aws_region]
}
