output "instance_profile_names_by_role" {
  description = "SSM-ready instance profile names keyed by active node role, for EC2 attachment."
  value       = tomap({ for role in var.node_roles : role => aws_iam_instance_profile.node.name })
}

output "instance_profile_arns_by_role" {
  description = "Instance profile ARNs keyed by active node role."
  value       = tomap({ for role in var.node_roles : role => aws_iam_instance_profile.node.arn })
}

output "role_arns_by_role" {
  description = "EC2 role ARNs keyed by active node role."
  value       = tomap({ for role in var.node_roles : role => aws_iam_role.node.arn })
}

output "ssm_policy_arn" {
  description = "The sole AWS-managed permission policy attached to the EC2 node role."
  value       = aws_iam_role_policy_attachment.ssm.policy_arn
}
