mock_provider "aws" {
  override_during = plan
}

override_resource {
  target          = aws_vpc.lab
  override_during = plan
  values          = { id = "vpc-00000000000000001" }
}

override_resource {
  target          = aws_internet_gateway.lab
  override_during = plan
  values          = { id = "igw-00000000000000001" }
}

override_resource {
  target          = aws_subnet.lab["public"]
  override_during = plan
  values          = { id = "subnet-00000000000000001" }
}

override_resource {
  target          = aws_subnet.lab["private"]
  override_during = plan
  values          = { id = "subnet-00000000000000002" }
}

override_resource {
  target          = aws_route_table.lab["public"]
  override_during = plan
  values          = { id = "rtb-00000000000000001" }
}

override_resource {
  target          = aws_route_table.lab["private"]
  override_during = plan
  values          = { id = "rtb-00000000000000002" }
}

override_resource {
  target          = aws_eip.nat["private"]
  override_during = plan
  values          = { id = "eipalloc-00000000000000001" }
}

override_resource {
  target          = aws_nat_gateway.egress["private"]
  override_during = plan
  values          = { id = "nat-00000000000000001" }
}

variables {
  name_prefix = "platform-lab"
  tags = {
    Project     = "platform"
    Environment = "lab"
    Owner       = "platform"
    CostCenter  = "engineering"
    ManagedBy   = "terraform"
  }
  network_topology = {
    lab_profile           = "multi-node"
    availability_zone     = "us-east-1b"
    vpc_cidr              = "10.30.0.0/16"
    public_subnet_cidr    = "10.30.10.0/24"
    node_subnet           = "public"
    egress                = "internet-gateway"
    associate_public_ipv4 = true
    nat_gateway_enabled   = false
  }
}

run "minimal_topology" {
  command = plan

  variables {
    network_topology = merge(var.network_topology, { lab_profile = "minimal" })
  }

  assert {
    condition = (
      aws_route.public_default.destination_cidr_block == "0.0.0.0/0" &&
      aws_route.public_default.gateway_id == aws_internet_gateway.lab.id &&
      aws_route.public_default.route_table_id == aws_route_table.lab["public"].id &&
      toset(keys(aws_route_table_association.subnet)) == toset(["public"]) &&
      aws_route_table_association.subnet["public"].subnet_id == aws_subnet.lab["public"].id &&
      aws_route_table_association.subnet["public"].route_table_id == aws_route_table.lab["public"].id
    )
    error_message = "The public subnet must explicitly use its IGW route table."
  }

  assert {
    condition = (
      length(aws_nat_gateway.egress) == 0 && length(aws_eip.nat) == 0 &&
      length(aws_route.private_default) == 0 &&
      output.private_subnet_id == null && output.private_route_table_id == null &&
      output.nat_gateway_id == null &&
      output.node_subnet_key == "public" && output.expected_egress == "internet-gateway" &&
      output.node_subnet_id == output.public_subnet_id
    )
    error_message = "A/B must have no private or NAT resources and route nodes through the public subnet."
  }

  assert {
    condition     = output.lab_profile == "minimal" && toset(keys(output.subnet_ids)) == toset(["public"])
    error_message = "A must select the public-only topology."
  }
}

run "multi_node_topology" {
  command = plan

  assert {
    condition = (
      aws_vpc.lab.cidr_block == "10.30.0.0/16" &&
      aws_vpc.lab.enable_dns_support && aws_vpc.lab.enable_dns_hostnames &&
      aws_internet_gateway.lab.vpc_id == aws_vpc.lab.id &&
      output.vpc_cidr == aws_vpc.lab.cidr_block && output.vpc_id == aws_vpc.lab.id &&
      output.internet_gateway_id == aws_internet_gateway.lab.id
    )
    error_message = "The lab VPC and IGW must be explicit, with both VPC DNS flags set."
  }

  assert {
    condition = (
      toset(keys(aws_subnet.lab)) == toset(["public"]) &&
      toset(keys(aws_route_table.lab)) == toset(["public"]) &&
      aws_subnet.lab["public"].vpc_id == aws_vpc.lab.id &&
      aws_route_table.lab["public"].vpc_id == aws_vpc.lab.id &&
      aws_subnet.lab["public"].cidr_block == "10.30.10.0/24" &&
      aws_subnet.lab["public"].availability_zone == "us-east-1b" &&
      !aws_subnet.lab["public"].map_public_ip_on_launch &&
      output.public_subnet_id == aws_subnet.lab["public"].id &&
      output.public_route_table_id == aws_route_table.lab["public"].id &&
      output.availability_zone == "us-east-1b"
    )
    error_message = "Public subnet identity, CIDR, AZ, IDs and explicit IP behavior must match the contract."
  }

  assert {
    condition = (
      aws_route.public_default.destination_cidr_block == "0.0.0.0/0" &&
      aws_route.public_default.gateway_id == aws_internet_gateway.lab.id &&
      aws_route.public_default.route_table_id == aws_route_table.lab["public"].id &&
      toset(keys(aws_route_table_association.subnet)) == toset(["public"]) &&
      aws_route_table_association.subnet["public"].subnet_id == aws_subnet.lab["public"].id &&
      aws_route_table_association.subnet["public"].route_table_id == aws_route_table.lab["public"].id
    )
    error_message = "The public subnet must explicitly use its IGW route table."
  }

  assert {
    condition = (
      length(aws_nat_gateway.egress) == 0 && length(aws_eip.nat) == 0 &&
      length(aws_route.private_default) == 0 &&
      output.private_subnet_id == null && output.private_route_table_id == null &&
      output.nat_gateway_id == null &&
      output.node_subnet_key == "public" && output.expected_egress == "internet-gateway" &&
      output.node_subnet_id == output.public_subnet_id
    )
    error_message = "A/B must have no private or NAT resources and route nodes through the public subnet."
  }

  assert {
    condition = (
      aws_vpc.lab.tags == tomap(merge(var.tags, { Name = "platform-lab-vpc" })) &&
      aws_subnet.lab["public"].tags == tomap(merge(var.tags, { Name = "platform-lab-subnet-public", Role = "public" })) &&
      aws_route_table.lab["public"].tags == tomap(merge(var.tags, { Name = "platform-lab-rt-public", Role = "public" })) &&
      aws_internet_gateway.lab.tags == tomap(merge(var.tags, { Name = "platform-lab-igw" }))
    )
    error_message = "Named resources must carry the common identity and billing tags."
  }

  assert {
    condition     = output.lab_profile == "multi-node" && output.topology.associate_public_ipv4
    error_message = "B must delegate node public IPv4 assignment to compute."
  }
}

run "private_topology" {
  command = plan

  variables {
    network_topology = merge(var.network_topology, {
      lab_profile           = "private"
      private_subnet_cidr   = "10.30.20.0/24"
      node_subnet           = "private"
      egress                = "nat-gateway"
      associate_public_ipv4 = false
      nat_gateway_enabled   = true
    })
  }

  assert {
    condition = (
      toset(keys(aws_subnet.lab)) == toset(["public", "private"]) &&
      toset(keys(aws_route_table.lab)) == toset(["public", "private"]) &&
      toset(keys(aws_route_table_association.subnet)) == toset(["public", "private"]) &&
      toset(keys(aws_nat_gateway.egress)) == toset(["private"]) &&
      toset(keys(aws_eip.nat)) == toset(["private"]) &&
      toset(keys(aws_route.private_default)) == toset(["private"]) &&
      alltrue([for subnet in aws_subnet.lab : subnet.availability_zone == "us-east-1b" && !subnet.map_public_ip_on_launch])
    )
    error_message = "C must use stable role keys and exactly one same-AZ NAT and EIP."
  }

  assert {
    condition = (
      aws_subnet.lab["private"].cidr_block == "10.30.20.0/24" &&
      aws_route.public_default.gateway_id == aws_internet_gateway.lab.id &&
      aws_route.public_default.route_table_id == aws_route_table.lab["public"].id &&
      aws_nat_gateway.egress["private"].availability_mode == "zonal" &&
      aws_nat_gateway.egress["private"].connectivity_type == "public" &&
      aws_nat_gateway.egress["private"].subnet_id == aws_subnet.lab["public"].id &&
      aws_eip.nat["private"].domain == "vpc" &&
      aws_nat_gateway.egress["private"].allocation_id == aws_eip.nat["private"].id &&
      aws_route.private_default["private"].destination_cidr_block == "0.0.0.0/0" &&
      aws_route.private_default["private"].nat_gateway_id == aws_nat_gateway.egress["private"].id &&
      aws_route.private_default["private"].gateway_id == null &&
      aws_route.private_default["private"].route_table_id == aws_route_table.lab["private"].id
    )
    error_message = "The public default route must point to IGW, and the private default route only to the zonal NAT."
  }

  assert {
    condition = alltrue([
      for role, association in aws_route_table_association.subnet :
      association.subnet_id == aws_subnet.lab[role].id &&
      association.route_table_id == aws_route_table.lab[role].id
    ])
    error_message = "Each subnet must use the route table with the same role."
  }

  assert {
    condition = (
      output.lab_profile == "private" && output.node_subnet_key == "private" &&
      output.expected_egress == "nat-gateway" && !output.topology.associate_public_ipv4 &&
      output.node_subnet_id == output.private_subnet_id &&
      output.private_subnet_id == aws_subnet.lab["private"].id &&
      output.private_route_table_id == aws_route_table.lab["private"].id &&
      output.route_table_ids["private"] == output.private_route_table_id &&
      output.nat_gateway_id == aws_nat_gateway.egress["private"].id &&
      aws_nat_gateway.egress["private"].tags.Owner == var.tags.Owner &&
      aws_eip.nat["private"].tags.CostCenter == var.tags.CostCenter
    )
    error_message = "C must publish its private assignment and tag the NAT and EIP."
  }
}

run "private_without_nat_opt_in" {
  command = plan

  variables {
    network_topology = merge(var.network_topology, {
      lab_profile           = "private"
      private_subnet_cidr   = "10.30.20.0/24"
      node_subnet           = "private"
      egress                = "nat-gateway"
      associate_public_ipv4 = false
      nat_gateway_enabled   = false
    })
  }

  expect_failures = [var.network_topology]
}

run "public_with_nat_opt_in" {
  command = plan

  variables {
    network_topology = merge(var.network_topology, { nat_gateway_enabled = true })
  }

  expect_failures = [var.network_topology]
}

run "private_rejects_igw_egress" {
  command = plan

  variables {
    network_topology = merge(var.network_topology, {
      lab_profile           = "private"
      private_subnet_cidr   = "10.30.20.0/24"
      node_subnet           = "private"
      egress                = "internet-gateway"
      associate_public_ipv4 = false
      nat_gateway_enabled   = true
    })
  }

  expect_failures = [var.network_topology]
}

run "reject_subnet_outside_vpc" {
  command = plan

  variables {
    network_topology = merge(var.network_topology, { public_subnet_cidr = "10.31.10.0/24" })
  }

  expect_failures = [var.network_topology]
}

run "reject_overlapping_subnets" {
  command = plan

  variables {
    network_topology = merge(var.network_topology, {
      lab_profile           = "private"
      private_subnet_cidr   = "10.30.10.128/25"
      node_subnet           = "private"
      egress                = "nat-gateway"
      associate_public_ipv4 = false
      nat_gateway_enabled   = true
    })
  }

  expect_failures = [var.network_topology]
}
