variable "name_prefix" {
  description = "Project and environment prefix for network resource names."
  type        = string
  nullable    = false
}

variable "tags" {
  description = "Common Project, Environment, Owner, CostCenter, ManagedBy and optional resource tags."
  type        = map(string)
  nullable    = false
}

variable "network_topology" {
  description = "Validated root network intent. Private placement requires one same-AZ public NAT and no node public IPv4."
  type = object({
    lab_profile           = string
    availability_zone     = string
    vpc_cidr              = string
    public_subnet_cidr    = string
    private_subnet_cidr   = optional(string)
    node_subnet           = string
    egress                = string
    associate_public_ipv4 = bool
    nat_gateway_enabled   = bool
  })
  nullable = false

  validation {
    condition = try(var.network_topology.lab_profile == "private" ? (
      var.network_topology.private_subnet_cidr != null &&
      var.network_topology.node_subnet == "private" &&
      var.network_topology.egress == "nat-gateway" &&
      var.network_topology.nat_gateway_enabled &&
      !var.network_topology.associate_public_ipv4
      ) : (
      contains(["minimal", "multi-node"], var.network_topology.lab_profile) &&
      var.network_topology.private_subnet_cidr == null &&
      var.network_topology.node_subnet == "public" &&
      var.network_topology.egress == "internet-gateway" &&
      !var.network_topology.nat_gateway_enabled &&
      var.network_topology.associate_public_ipv4
    ), false)
    error_message = "A/B require public placement with IGW egress and no NAT. C requires private placement and explicit NAT opt-in."
  }

  validation {
    condition = try(
      can(regex("^[a-z]{2}(-[a-z]+)+-[1-9][0-9]*[a-z]$", var.network_topology.availability_zone)) &&
      alltrue([
        for cidr in [var.network_topology.vpc_cidr, var.network_topology.public_subnet_cidr, var.network_topology.private_subnet_cidr] : (
          can(cidrnetmask(cidr)) &&
          cidr == format("%s/%d", cidrhost(cidr, 0), tonumber(split("/", cidr)[1])) &&
          tonumber(split("/", cidr)[1]) >= 16 &&
          tonumber(split("/", cidr)[1]) <= 28
        ) if cidr != null
      ]) &&
      var.network_topology.vpc_cidr != null && var.network_topology.public_subnet_cidr != null,
      false
    )
    error_message = "Provide a standard AZ and canonical IPv4 VPC and subnet CIDRs with /16 through /28 prefixes."
  }

  validation {
    condition = try(alltrue([
      for subnet in [var.network_topology.public_subnet_cidr, var.network_topology.private_subnet_cidr] : (
        tonumber(split("/", subnet)[1]) >= tonumber(split("/", var.network_topology.vpc_cidr)[1]) &&
        cidrhost("${cidrhost(subnet, 0)}/${split("/", var.network_topology.vpc_cidr)[1]}", 0) == cidrhost(var.network_topology.vpc_cidr, 0)
      ) if subnet != null
    ]), false)
    error_message = "Subnet CIDRs must be contained in the VPC."
  }

  validation {
    condition = var.network_topology.private_subnet_cidr == null ? true : try(alltrue([
      for pair in [
        { subnet = var.network_topology.public_subnet_cidr, other = var.network_topology.private_subnet_cidr },
        { subnet = var.network_topology.private_subnet_cidr, other = var.network_topology.public_subnet_cidr }
      ] :
      cidrhost("${cidrhost(pair.subnet, 0)}/${split("/", pair.other)[1]}", 0) != cidrhost(pair.other, 0)
    ]), false)
    error_message = "The public and private subnet CIDRs must not overlap."
  }
}
