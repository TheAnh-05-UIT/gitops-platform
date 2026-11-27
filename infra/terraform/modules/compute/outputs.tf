output "nodes" {
  description = "Observed EC2 node facts and approved placement metadata keyed by logical ID. Keep real instance and network identifiers private."
  value = tomap({
    for id, instance in aws_instance.node : id => {
      logical_id            = id
      role                  = var.node_definitions[id].role
      instance_id           = instance.id
      private_ip            = instance.private_ip
      public_ip             = var.node_definitions[id].associate_public_ipv4 ? instance.public_ip : null
      availability_zone     = instance.availability_zone
      instance_type         = instance.instance_type
      subnet_id             = instance.subnet_id
      security_group_ids    = sort(tolist(instance.vpc_security_group_ids))
      instance_profile_name = instance.iam_instance_profile
      simulated_region      = var.node_definitions[id].simulated_region
    }
  })
}
