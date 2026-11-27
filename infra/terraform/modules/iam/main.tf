locals {
  partition = startswith(var.aws_region, "cn-") ? "aws-cn" : (
    startswith(var.aws_region, "us-gov-") ? "aws-us-gov" : "aws"
  )

  # IAM names are account-wide. The Region suffix keeps independent lab roots distinct.
  name           = "${var.project_name}-${var.environment}-node-${substr(sha256(var.aws_region), 0, 8)}"
  ssm_policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
  tags           = merge(var.tags, { Name = local.name, Role = "node-ssm" })
}

resource "aws_iam_role" "node" {
  name        = local.name
  description = "Shared K3s lab EC2 role for Systems Manager managed nodes"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.node.name
  policy_arn = local.ssm_policy_arn
}

resource "aws_iam_instance_profile" "node" {
  name = local.name
  role = aws_iam_role.node.name
  tags = local.tags

  depends_on = [aws_iam_role_policy_attachment.ssm]
}
