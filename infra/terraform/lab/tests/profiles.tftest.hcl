mock_provider "aws" {}

variables {
  aws_region        = jsondecode(file("examples/multi-node.tfvars.json.example")).aws_region
  availability_zone = jsondecode(file("examples/multi-node.tfvars.json.example")).availability_zone
  ami               = jsondecode(file("examples/multi-node.tfvars.json.example")).ami
  cost_allocation   = jsondecode(file("examples/multi-node.tfvars.json.example")).cost_allocation
}

run "minimal_profile" {
  command = plan

  variables {
    aws_region        = jsondecode(file("examples/minimal.tfvars.json.example")).aws_region
    availability_zone = jsondecode(file("examples/minimal.tfvars.json.example")).availability_zone
    ami               = jsondecode(file("examples/minimal.tfvars.json.example")).ami
    cost_allocation   = jsondecode(file("examples/minimal.tfvars.json.example")).cost_allocation
    lab_profile       = jsondecode(file("examples/minimal.tfvars.json.example")).lab_profile
    worker_count      = jsondecode(file("examples/minimal.tfvars.json.example")).worker_count
  }

  assert {
    condition     = tolist(keys(output.node_definitions)) == tolist(["k3s-server"])
    error_message = "The profile must expose only its stable logical node keys."
  }

  assert {
    condition = (
      output.network_topology.node_subnet == "public" &&
      output.network_topology.egress == "internet-gateway" &&
      output.network_topology.nat_gateway_enabled == false &&
      output.network_topology.associate_public_ipv4 == true &&
      output.network_topology.private_subnet_cidr == null
    )
    error_message = "Profile minimal has an unexpected egress or subnet contract."
  }

  assert {
    condition = (
      output.access.administration == "ssm" &&
      output.access.public_ingress == null &&
      alltrue([for node in values(output.node_definitions) :
        node.imdsv2_required && node.root_volume.encrypted && node.root_volume.type == "gp3"
      ])
    )
    error_message = "SSM-only administration, no default ingress, IMDSv2 and encrypted gp3 are required."
  }
}

run "multi_node_profile" {
  command = plan

  variables {
    aws_region        = jsondecode(file("examples/multi-node.tfvars.json.example")).aws_region
    availability_zone = jsondecode(file("examples/multi-node.tfvars.json.example")).availability_zone
    ami               = jsondecode(file("examples/multi-node.tfvars.json.example")).ami
    cost_allocation   = jsondecode(file("examples/multi-node.tfvars.json.example")).cost_allocation
    lab_profile       = jsondecode(file("examples/multi-node.tfvars.json.example")).lab_profile
    worker_count      = jsondecode(file("examples/multi-node.tfvars.json.example")).worker_count
  }

  assert {
    condition     = tolist(keys(output.node_definitions)) == tolist(["k3s-agent1", "k3s-server"])
    error_message = "The profile must expose only its stable logical node keys."
  }

  assert {
    condition = (
      output.network_topology.node_subnet == "public" &&
      output.network_topology.egress == "internet-gateway" &&
      output.network_topology.nat_gateway_enabled == false &&
      output.network_topology.associate_public_ipv4 == true &&
      output.network_topology.private_subnet_cidr == null
    )
    error_message = "Profile multi-node has an unexpected egress or subnet contract."
  }

  assert {
    condition = (
      output.access.administration == "ssm" &&
      output.access.public_ingress == null &&
      alltrue([for node in values(output.node_definitions) :
        node.imdsv2_required && node.root_volume.encrypted && node.root_volume.type == "gp3"
      ])
    )
    error_message = "SSM-only administration, no default ingress, IMDSv2 and encrypted gp3 are required."
  }
}

run "private_profile" {
  command = plan

  variables {
    aws_region          = jsondecode(file("examples/private.tfvars.json.example")).aws_region
    availability_zone   = jsondecode(file("examples/private.tfvars.json.example")).availability_zone
    ami                 = jsondecode(file("examples/private.tfvars.json.example")).ami
    cost_allocation     = jsondecode(file("examples/private.tfvars.json.example")).cost_allocation
    lab_profile         = jsondecode(file("examples/private.tfvars.json.example")).lab_profile
    worker_count        = jsondecode(file("examples/private.tfvars.json.example")).worker_count
    nat_gateway_enabled = jsondecode(file("examples/private.tfvars.json.example")).nat_gateway_enabled
    network             = jsondecode(file("examples/private.tfvars.json.example")).network
  }

  assert {
    condition     = tolist(keys(output.node_definitions)) == tolist(["k3s-agent1", "k3s-agent2", "k3s-server"])
    error_message = "The profile must expose only its stable logical node keys."
  }

  assert {
    condition = (
      output.network_topology.node_subnet == "private" &&
      output.network_topology.egress == "nat-gateway" &&
      output.network_topology.nat_gateway_enabled == true &&
      output.network_topology.associate_public_ipv4 == false &&
      output.network_topology.private_subnet_cidr == "10.20.2.0/24"
    )
    error_message = "Profile private has an unexpected egress or subnet contract."
  }

  assert {
    condition = (
      output.access.administration == "ssm" &&
      output.access.public_ingress == null &&
      alltrue([for node in values(output.node_definitions) :
        node.imdsv2_required && node.root_volume.encrypted && node.root_volume.type == "gp3"
      ])
    )
    error_message = "SSM-only administration, no default ingress, IMDSv2 and encrypted gp3 are required."
  }
}

run "private_with_one_worker" {
  command = plan

  variables {
    lab_profile         = "private"
    worker_count        = 1
    nat_gateway_enabled = true
    network             = { private_subnet_cidr = "10.20.2.0/24" }
  }

  assert {
    condition     = tolist(keys(output.node_definitions)) == tolist(["k3s-agent1", "k3s-server"])
    error_message = "Profile C supports a single worker with an explicitly enabled NAT."
  }
}

run "add_worker_preserves_existing_node_definitions" {
  command = plan

  variables {
    worker_count = 2
  }

  assert {
    condition = (
      output.node_definitions["k3s-server"] == run.multi_node_profile.node_definitions["k3s-server"] &&
      output.node_definitions["k3s-agent1"] == run.multi_node_profile.node_definitions["k3s-agent1"] &&
      output.node_definitions["k3s-agent2"].role == "worker" &&
      output.node_definitions["k3s-agent1"].simulated_region == "ap-southeast-1" &&
      output.node_definitions["k3s-server"].tags.Name == "gitops-platform-lab-k3s-server" &&
      output.node_definitions["k3s-agent2"].tags.Role == "worker"
    )
    error_message = "Adding a worker must leave the existing node keys and values intact."
  }
}

run "explicit_application_ingress" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [443] }
  }

  assert {
    condition     = output.access.public_ingress.ports == toset([443])
    error_message = "The contract must carry an explicitly enabled application port."
  }
}

run "unsupported_profile" {
  command = plan

  variables {
    lab_profile = "production"
  }

  expect_failures = [var.lab_profile]
}

run "minimal_rejects_worker" {
  command = plan

  variables {
    lab_profile  = "minimal"
    worker_count = 1
  }

  expect_failures = [var.worker_count]
}

run "multi_node_requires_worker" {
  command = plan

  variables {
    worker_count = 0
  }

  expect_failures = [var.worker_count]
}

run "private_requires_worker" {
  command = plan

  variables {
    lab_profile         = "private"
    worker_count        = 0
    nat_gateway_enabled = true
    network             = { private_subnet_cidr = "10.20.2.0/24" }
  }

  expect_failures = [var.worker_count]
}

run "too_many_workers" {
  command = plan

  variables {
    worker_count = 3
  }

  expect_failures = [var.worker_count]
}

run "fractional_worker_count" {
  command = plan

  variables {
    worker_count = 1.5
  }

  expect_failures = [var.worker_count]
}

run "minimal_rejects_nat" {
  command = plan

  variables {
    lab_profile         = "minimal"
    worker_count        = 0
    nat_gateway_enabled = true
  }

  expect_failures = [var.nat_gateway_enabled]
}

run "multi_node_rejects_nat" {
  command = plan

  variables {
    nat_gateway_enabled = true
  }

  expect_failures = [var.nat_gateway_enabled]
}

run "private_requires_nat_opt_in" {
  command = plan

  variables {
    lab_profile = "private"
    network     = { private_subnet_cidr = "10.20.2.0/24" }
  }

  expect_failures = [var.nat_gateway_enabled]
}

run "private_requires_private_subnet" {
  command = plan

  variables {
    lab_profile         = "private"
    nat_gateway_enabled = true
  }

  expect_failures = [var.network]
}

run "multi_node_rejects_unused_private_subnet" {
  command = plan

  variables {
    network = { private_subnet_cidr = "10.20.2.0/24" }
  }

  expect_failures = [var.network]
}

run "private_subnet_overlap" {
  command = plan

  variables {
    lab_profile         = "private"
    nat_gateway_enabled = true
    network             = { private_subnet_cidr = "10.20.1.128/25" }
  }

  expect_failures = [var.network]
}

run "subnet_outside_vpc" {
  command = plan

  variables {
    network = { public_subnet_cidr = "10.21.1.0/24" }
  }

  expect_failures = [var.network]
}

run "noncanonical_subnet" {
  command = plan

  variables {
    network = { public_subnet_cidr = "10.20.1.14/24" }
  }

  expect_failures = [var.network]
}

run "reject_ipv6_network" {
  command = plan

  variables {
    network = { vpc_cidr = "2001:db8::/32" }
  }

  expect_failures = [var.network]
}

run "az_region_mismatch" {
  command = plan

  variables {
    availability_zone = "us-west-2a"
  }

  expect_failures = [var.availability_zone]
}

run "reject_local_zone" {
  command = plan

  variables {
    availability_zone = "us-east-1-atl-1a"
  }

  expect_failures = [var.availability_zone]
}

run "reject_public_ssh_strategy" {
  command = plan

  variables {
    administrative_access = "public-ssh"
  }

  expect_failures = [var.administrative_access]
}

run "reject_public_kubernetes_port" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [6443] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_world_ingress" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["0.0.0.0/0"], ports = [443] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_cidr_union_covering_the_internet" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["0.0.0.0/1", "128.0.0.0/1"], ports = [443] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_ingress_on_private_nodes" {
  command = plan

  variables {
    lab_profile         = "private"
    nat_gateway_enabled = true
    network             = { private_subnet_cidr = "10.20.2.0/24" }
    public_ingress      = { source_cidrs = ["198.51.100.8/32"], ports = [443] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_project_name" {
  command = plan

  variables {
    project_name = "GitOps/Platform"
  }

  expect_failures = [var.project_name]
}

run "reject_environment_name" {
  command = plan

  variables {
    environment = "-lab"
  }

  expect_failures = [var.environment]
}

run "reject_unpinned_ami" {
  command = plan

  variables {
    ami = { id = "latest" }
  }

  expect_failures = [var.ami]
}

run "reject_ami_architecture" {
  command = plan

  variables {
    ami = { id = "ami-00000000000000000", architecture = "i386" }
  }

  expect_failures = [var.ami]
}

run "reject_invalid_volume" {
  command = plan

  variables {
    server = { root_volume = { size_gib = 0 } }
  }

  expect_failures = [var.server]
}

run "reject_invalid_instance_type" {
  command = plan

  variables {
    worker = { instance_type = "large" }
  }

  expect_failures = [var.worker]
}

run "reject_reserved_tag_override" {
  command = plan

  variables {
    resource_tags = { owner = "other-team" }
  }

  expect_failures = [var.resource_tags]
}

run "reject_blank_billing_tag" {
  command = plan

  variables {
    cost_allocation = { owner = "", cost_center = "lab" }
  }

  expect_failures = [var.cost_allocation]
}
