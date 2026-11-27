mock_provider "aws" {
  override_during = plan
}


override_resource {
  target          = module.networking.aws_subnet.lab["public"]
  override_during = plan
  values = {
    id = "subnet-00000000000000001"
  }
}

override_resource {
  target          = module.networking.aws_subnet.lab["private"]
  override_during = plan
  values = {
    id = "subnet-00000000000000002"
  }
}

override_resource {
  target          = module.networking.aws_nat_gateway.egress["private"]
  override_during = plan
  values = {
    id = "nat-00000000000000001"
  }
}

override_resource {
  target          = module.security.aws_security_group.node["server"]
  override_during = plan
  values = {
    id = "sg-00000000000000001"
  }
}

override_resource {
  target          = module.security.aws_security_group.node["worker"]
  override_during = plan
  values = {
    id = "sg-00000000000000002"
  }
}

override_resource {
  target          = module.compute.aws_instance.node["k3s-server"]
  override_during = plan
  values = {
    id         = "i-00000000000000001"
    private_ip = "10.20.1.10"
    public_ip  = "192.0.2.10"
  }
}

override_resource {
  target          = module.compute.aws_instance.node["k3s-agent1"]
  override_during = plan
  values = {
    id         = "i-00000000000000002"
    private_ip = "10.20.1.11"
    public_ip  = "192.0.2.11"
  }
}

override_resource {
  target          = module.compute.aws_instance.node["k3s-agent2"]
  override_during = plan
  values = {
    id         = "i-00000000000000003"
    private_ip = "10.20.1.12"
    public_ip  = "192.0.2.12"
  }
}

variables {
  aws_region        = "us-east-1"
  availability_zone = "us-east-1a"
  ami               = { id = "ami-00000000000000000" }
  cost_allocation   = { owner = "platform-lab", cost_center = "engineering-lab" }
}


run "minimal_compute_inventory" {
  command = plan

  variables {
    lab_profile  = "minimal"
    worker_count = 0
  }

  assert {
    condition     = jsonencode(output.ansible_inventory) == jsonencode(jsondecode(file("../modules/ansible-inventory/tests/fixtures/minimal.json")))
    error_message = "Compute-to-inventory must match the existing schema v1 fixture exactly."
  }

  assert {
    condition = alltrue([for id, node in output.nodes :
      node.subnet_id == output.network.public_subnet_id &&
      toset(node.security_group_ids) == toset(output.security.security_group_ids_by_role[node.role]) &&
      node.instance_profile_name == output.iam.instance_profile_names_by_role[node.role] &&
      node.availability_zone == "us-east-1a" &&
      node.logical_id == id && node.public_ip != null
    ])
    error_message = "Observed node facts must use the selected subnet, role SGs and IAM profile."
  }

  assert {
    condition     = output.network.nat_gateway_id == null && length(output.nodes) == 1 && toset(keys(output.iam.instance_profile_names_by_role)) == toset(["server"])
    error_message = "Minimal launches one server and no NAT."
  }
}


run "multi_node_compute_inventory" {
  command = plan

  assert {
    condition     = jsonencode(output.ansible_inventory) == jsonencode(jsondecode(file("../modules/ansible-inventory/tests/fixtures/multi-node.json")))
    error_message = "Compute-to-inventory must match the existing schema v1 fixture exactly."
  }

  assert {
    condition = alltrue([for id, node in output.nodes :
      node.subnet_id == output.network.public_subnet_id &&
      toset(node.security_group_ids) == toset(output.security.security_group_ids_by_role[node.role]) &&
      node.instance_profile_name == output.iam.instance_profile_names_by_role[node.role] &&
      node.availability_zone == "us-east-1a" &&
      node.logical_id == id && node.public_ip != null
    ])
    error_message = "Observed node facts must use the selected subnet, role SGs and IAM profile."
  }

  assert {
    condition     = output.network.nat_gateway_id == null && length(output.nodes) == 2
    error_message = "B defaults to one worker and no NAT."
  }
}


run "additional_worker_keeps_existing_nodes_and_network" {
  command = plan

  variables {
    worker_count = 2
  }

  assert {
    condition = (
      output.nodes["k3s-server"] == run.multi_node_compute_inventory.nodes["k3s-server"] &&
      output.nodes["k3s-agent1"] == run.multi_node_compute_inventory.nodes["k3s-agent1"] &&
      output.nodes["k3s-agent2"].instance_profile_name == output.nodes["k3s-agent1"].instance_profile_name &&
      output.network.subnet_ids == run.multi_node_compute_inventory.network.subnet_ids &&
      output.security.security_group_ids_by_role == run.multi_node_compute_inventory.security.security_group_ids_by_role &&
      output.network.nat_gateway_id == null &&
      toset(output.ansible_inventory.groups.k3s_agents) == toset(["k3s-agent1", "k3s-agent2"])
    )
    error_message = "An additional worker must reuse network, role SG and profile identities."
  }
}


run "private_compute_inventory" {
  command = plan

  variables {
    lab_profile         = "private"
    worker_count        = 2
    nat_gateway_enabled = true
    network             = { private_subnet_cidr = "10.20.2.0/24" }
  }

  override_resource {
    target          = module.compute.aws_instance.node["k3s-server"]
    override_during = plan
    values = {
      id         = "i-00000000000000001"
      private_ip = "10.20.2.10"
      public_ip  = ""
    }
  }

  override_resource {
    target          = module.compute.aws_instance.node["k3s-agent1"]
    override_during = plan
    values = {
      id         = "i-00000000000000002"
      private_ip = "10.20.2.11"
      public_ip  = ""
    }
  }

  override_resource {
    target          = module.compute.aws_instance.node["k3s-agent2"]
    override_during = plan
    values = {
      id         = "i-00000000000000003"
      private_ip = "10.20.2.12"
      public_ip  = ""
    }
  }

  assert {
    condition     = jsonencode(output.ansible_inventory) == jsonencode(jsondecode(file("../modules/ansible-inventory/tests/fixtures/private.json")))
    error_message = "Compute-to-inventory must match the existing schema v1 fixture exactly."
  }

  assert {
    condition = alltrue([for id, node in output.nodes :
      node.subnet_id == output.network.private_subnet_id &&
      toset(node.security_group_ids) == toset(output.security.security_group_ids_by_role[node.role]) &&
      node.instance_profile_name == output.iam.instance_profile_names_by_role[node.role] &&
      node.availability_zone == "us-east-1a" &&
      node.logical_id == id && node.public_ip == null
    ])
    error_message = "Observed node facts must use the selected subnet, role SGs and IAM profile."
  }

  assert {
    condition     = output.network.nat_gateway_id != null && length(output.nodes) == 3
    error_message = "The private graph must keep its one NAT alongside the requested nodes."
  }
}

run "private_one_worker_reuses_nat_and_role_sgs" {
  command = plan

  variables {
    lab_profile         = "private"
    worker_count        = 1
    nat_gateway_enabled = true
    network             = { private_subnet_cidr = "10.20.2.0/24" }
  }

  override_resource {
    target          = module.compute.aws_instance.node["k3s-server"]
    override_during = plan
    values = {
      id         = "i-00000000000000001"
      private_ip = "10.20.2.10"
      public_ip  = ""
    }
  }

  override_resource {
    target          = module.compute.aws_instance.node["k3s-agent1"]
    override_during = plan
    values = {
      id         = "i-00000000000000002"
      private_ip = "10.20.2.11"
      public_ip  = ""
    }
  }

  assert {
    condition = (
      output.network.nat_gateway_id == run.private_compute_inventory.network.nat_gateway_id &&
      output.network.subnet_ids == run.private_compute_inventory.network.subnet_ids &&
      output.security.security_group_ids_by_role == run.private_compute_inventory.security.security_group_ids_by_role &&
      output.nodes["k3s-server"] == run.private_compute_inventory.nodes["k3s-server"] &&
      output.nodes["k3s-agent1"] == run.private_compute_inventory.nodes["k3s-agent1"] &&
      toset(output.ansible_inventory.groups.k3s_agents) == toset(["k3s-agent1"]) &&
      length(output.nodes) == 2
    )
    error_message = "C with one worker must use the same private node, NAT and SG identities as C with two workers."
  }
}
