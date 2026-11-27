locals {
  # Check the starter and sizing-guide families without pretending to be an AWS SKU catalog.
  known_architectures = {
    t2  = "x86_64"
    t3  = "x86_64"
    t3a = "x86_64"
    m7i = "x86_64"
    t4g = "arm64"
    m7g = "arm64"
  }
}

resource "aws_instance" "node" {
  for_each = var.node_definitions

  ami                         = var.ami.id
  instance_type               = each.value.instance_type
  availability_zone           = each.value.availability_zone
  subnet_id                   = var.subnet_ids[each.value.subnet_key]
  associate_public_ip_address = each.value.associate_public_ipv4
  vpc_security_group_ids      = var.security_group_ids_by_role[each.value.role]
  iam_instance_profile        = var.instance_profile_names_by_role[each.value.role]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    http_protocol_ipv6          = "disabled"
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = each.value.root_volume.size_gib
    encrypted             = true
    delete_on_termination = each.value.root_volume.delete_on_termination
  }

  tags = merge(each.value.tags, {
    Name = each.value.name
    Role = each.value.role
  })
  volume_tags = merge(each.value.tags, {
    Name = "${each.value.name}-root"
    Role = each.value.role
  })
}
