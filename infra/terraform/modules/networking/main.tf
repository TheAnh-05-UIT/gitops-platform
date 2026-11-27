locals {
  private_subnet = var.network_topology.lab_profile == "private" && var.network_topology.private_subnet_cidr != null
  subnet_cidrs = merge(
    { public = var.network_topology.public_subnet_cidr },
    local.private_subnet ? { private = var.network_topology.private_subnet_cidr } : {}
  )
  nat_keys = local.private_subnet && var.network_topology.nat_gateway_enabled ? toset(["private"]) : toset([])
}

resource "aws_vpc" "lab" {
  cidr_block           = var.network_topology.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_subnet" "lab" {
  for_each = local.subnet_cidrs

  vpc_id                  = aws_vpc.lab.id
  cidr_block              = each.value
  availability_zone       = var.network_topology.availability_zone
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-subnet-${each.key}"
    Role = each.key
  })
}

resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id

  tags = merge(var.tags, { Name = "${var.name_prefix}-igw" })
}

resource "aws_route_table" "lab" {
  for_each = local.subnet_cidrs

  vpc_id = aws_vpc.lab.id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-rt-${each.key}"
    Role = each.key
  })
}

resource "aws_route" "public_default" {
  route_table_id         = aws_route_table.lab["public"].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.lab.id
}

resource "aws_route_table_association" "subnet" {
  for_each = local.subnet_cidrs

  subnet_id      = aws_subnet.lab[each.key].id
  route_table_id = aws_route_table.lab[each.key].id
}

resource "aws_eip" "nat" {
  for_each = local.nat_keys

  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name_prefix}-nat-eip", Role = each.key })
}

resource "aws_nat_gateway" "egress" {
  for_each = local.nat_keys

  allocation_id     = aws_eip.nat[each.key].id
  subnet_id         = aws_subnet.lab["public"].id
  availability_mode = "zonal"
  connectivity_type = "public"

  tags = merge(var.tags, { Name = "${var.name_prefix}-nat", Role = each.key })

  # The public route depends on the VPC's attached IGW.
  depends_on = [aws_route.public_default, aws_route_table_association.subnet["public"]]
}

resource "aws_route" "private_default" {
  for_each = local.nat_keys

  route_table_id         = aws_route_table.lab[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.egress[each.key].id
}
