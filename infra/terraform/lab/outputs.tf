output "network_topology" {
  description = "Selected network topology and egress intent for the networking module."
  value       = local.network_topology
}

output "node_definitions" {
  description = "Desired EC2 settings keyed by stable logical node ID. These are inputs for compute, not observed inventory."
  value       = local.node_definitions
}

output "access" {
  description = "Administrative and optional application ingress intent for the security module."
  value = {
    administration = var.administrative_access
    public_ingress = var.public_ingress
  }
}

output "network" {
  description = "Network identifiers, subnet assignment and egress for the selected profile."
  value       = module.networking
}

output "security" {
  description = "Role-based security group identifiers and effective policy for the selected profile."
  value       = module.security
}

output "iam" {
  description = "The approved node instance profile and role metadata keyed by active role."
  value       = module.iam
}

output "nodes" {
  description = "Observed EC2 attributes keyed by stable logical node ID."
  value       = module.compute.nodes
}

output "ansible_inventory" {
  description = "Ansible inventory v1 derived from the observed EC2 nodes. Protect live output files."
  value       = module.ansible_inventory.ansible_inventory
}
