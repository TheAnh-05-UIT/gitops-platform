output "ansible_inventory" {
  description = "Version 1 inventory for the Ansible adapter. Treat real EC2 facts as private."
  value = {
    schema_version      = 1
    environment         = var.environment
    aws_region          = var.aws_region
    lab_profile         = var.lab_profile
    connection_strategy = "ssm"
    nodes               = { for id, facts in var.nodes : id => merge(facts, { logical_id = id }) }
    groups = {
      k3s        = keys(var.nodes)
      k3s_server = [for id, facts in var.nodes : id if facts.role == "server"]
      k3s_agents = [for id, facts in var.nodes : id if facts.role == "worker"]
    }
  }
}
