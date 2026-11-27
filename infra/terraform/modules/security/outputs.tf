output "server_security_group_id" {
  description = "K3s server security group ID."
  value       = aws_security_group.node["server"].id
}

output "worker_security_group_id" {
  description = "Shared worker SG ID, null when the profile has no worker."
  value       = try(aws_security_group.node["worker"].id, null)
}

output "application_security_group_id" {
  description = "Null because approved application rules attach to the explicitly selected node SGs."
  value       = tostring(null)
}

output "security_group_ids_by_role" {
  description = "Map of SG ID lists for role-based compute attachment, ready after standalone rules are in place."
  value       = tomap({ for role, group in aws_security_group.node : role => tolist([group.id]) })

  depends_on = [
    aws_vpc_security_group_ingress_rule.internal,
    aws_vpc_security_group_egress_rule.internal,
    aws_vpc_security_group_ingress_rule.application,
    aws_vpc_security_group_egress_rule.web,
  ]
}

output "policy" {
  description = "Effective SSM, node-to-node, application ingress and outbound security policy."
  value = {
    vpc_id             = var.vpc_id
    lab_profile        = var.lab_profile
    administration     = var.administration
    node_roles         = local.node_roles
    node_communication = var.node_communication
    internal_rules     = local.internal_rules
    public_ingress     = var.public_ingress
    web_egress         = { protocol = "tcp", ports = local.web_egress_ports, destination = "0.0.0.0/0" }
    platform_dns       = "AmazonProvidedDNS"
    platform_time      = "Amazon Time Sync Service"
  }
}
