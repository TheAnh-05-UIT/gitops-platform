mock_provider "aws" {
  override_during = plan
}

override_resource {
  target          = module.networking.aws_vpc.lab
  override_during = plan
  values          = { id = "vpc-00000000000000001" }
}

override_resource {
  target          = module.networking.aws_subnet.lab["public"]
  override_during = plan
  values          = { id = "subnet-00000000000000001" }
}

override_resource {
  target          = module.networking.aws_subnet.lab["private"]
  override_during = plan
  values          = { id = "subnet-00000000000000002" }
}

override_resource {
  target          = module.networking.aws_route_table.lab["private"]
  override_during = plan
  values          = { id = "rtb-00000000000000002" }
}

override_resource {
  target          = module.networking.aws_nat_gateway.egress["private"]
  override_during = plan
  values          = { id = "nat-00000000000000001" }
}

override_resource {
  target          = module.security.aws_security_group.node["server"]
  override_during = plan
  values          = { id = "sg-00000000000000001" }
}

override_resource {
  target          = module.security.aws_security_group.node["worker"]
  override_during = plan
  values          = { id = "sg-00000000000000002" }
}

variables {
  aws_region        = "us-east-1"
  availability_zone = "us-east-1a"
  ami               = { id = "ami-00000000000000000" }
  cost_allocation   = { owner = "platform-lab", cost_center = "engineering-lab" }
}

run "minimal_root" {
  command = plan

  variables {
    lab_profile  = "minimal"
    worker_count = 0
  }

  assert {
    condition = (
      output.network.node_subnet_id == output.network.public_subnet_id &&
      output.network.nat_gateway_id == null && output.network.private_subnet_id == null &&
      output.security.worker_security_group_id == null &&
      length(output.security.policy.internal_rules) == 0 &&
      output.security.policy.public_ingress == null &&
      output.node_definitions["k3s-server"].associate_public_ipv4
    )
    error_message = "A must expose ready public networking and only a server security group."
  }
}

run "multi_node_root" {
  command = plan

  assert {
    condition = (
      toset(keys(output.network.subnet_ids)) == toset(["public"]) &&
      output.network.nat_gateway_id == null &&
      output.network.node_subnet_id == output.network.public_subnet_id &&
      toset(keys(output.security.security_group_ids_by_role)) == toset(["server", "worker"]) &&
      output.security.policy.vpc_id == output.network.vpc_id &&
      output.security.policy.internal_rules["api-worker-server"].port == 6443 &&
      output.security.policy.public_ingress == null
    )
    error_message = "B must wire one public subnet into the two node-role security groups."
  }
}

run "additional_worker_uses_same_network_and_sg_roles" {
  command = plan

  variables {
    worker_count = 2
  }

  assert {
    condition = (
      toset(keys(output.network.subnet_ids)) == toset(keys(run.multi_node_root.network.subnet_ids)) &&
      toset(keys(output.network.route_table_ids)) == toset(keys(run.multi_node_root.network.route_table_ids)) &&
      output.network.nat_gateway_id == null &&
      toset(keys(output.security.security_group_ids_by_role)) == toset(keys(run.multi_node_root.security.security_group_ids_by_role)) &&
      output.node_definitions["k3s-agent2"].subnet_key == "public" &&
      output.security.policy.internal_rules["vxlan-worker-worker"].port == 8472
    )
    error_message = "The second worker must reuse existing network and SG role keys."
  }
}

run "private_root" {
  command = plan

  variables {
    lab_profile         = "private"
    worker_count        = 2
    nat_gateway_enabled = true
    network             = { private_subnet_cidr = "10.20.2.0/24" }
  }

  assert {
    condition = (
      output.network.nat_gateway_id != null &&
      output.network.expected_egress == "nat-gateway" &&
      output.network.private_subnet_id == output.network.node_subnet_id &&
      output.network.private_route_table_id != null &&
      alltrue([for node in output.node_definitions : node.subnet_key == "private" && !node.associate_public_ipv4]) &&
      output.security.worker_security_group_id != null &&
      output.security.policy.public_ingress == null
    )
    error_message = "C must use private IPv4 for both roles and a NAT default route."
  }
}

run "legacy_ingress_intent_stays_closed_without_roles" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [443] }
  }

  assert {
    condition     = output.access.public_ingress != null && output.security.policy.public_ingress == null
    error_message = "Existing inputs without role approval must remain valid and closed."
  }
}

run "explicit_root_ingress_applies_only_to_selected_role" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [443], node_roles = ["worker"] }
  }

  assert {
    condition     = output.security.policy.public_ingress.node_roles == toset(["worker"])
    error_message = "The root must forward the selected ingress role."
  }
}

run "root_rejects_worker_ingress_without_workers" {
  command = plan

  variables {
    lab_profile    = "minimal"
    worker_count   = 0
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [443], node_roles = ["worker"] }
  }

  expect_failures = [var.public_ingress]
}

run "minimal_can_select_server_for_app_ingress" {
  command = plan

  variables {
    lab_profile  = "minimal"
    worker_count = 0
    public_ingress = {
      source_cidrs = ["198.51.100.8/32"]
      ports        = [443]
      node_roles   = ["server"]
    }
  }

  assert {
    condition = (
      output.security.policy.public_ingress.node_roles == toset(["server"]) &&
      length(output.security.policy.internal_rules) == 0 &&
      output.security.worker_security_group_id == null
    )
    error_message = "A may opt in to restricted server application ingress without creating worker access."
  }
}
