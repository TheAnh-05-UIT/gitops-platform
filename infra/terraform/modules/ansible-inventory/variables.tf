terraform {
  required_version = ">= 1.10.0, < 2.0.0"
}

variable "environment" {
  description = "Environment name from the calling lab root."
  type        = string
  nullable    = false
}

variable "aws_region" {
  description = "Region to pass to the Ansible SSM connection plugin."
  type        = string
  nullable    = false
}

variable "availability_zone" {
  description = "Single selected AZ for validating the compute output."
  type        = string
  nullable    = false
}

variable "lab_profile" {
  description = "Selected lab profile from the calling lab root."
  type        = string
  nullable    = false

  validation {
    condition     = contains(["minimal", "multi-node", "private"], var.lab_profile)
    error_message = "Inventory requires a supported lab profile."
  }
}

variable "nodes" {
  description = "Observed compute facts keyed by logical node ID. Public IP and placement label may be null."
  type = map(object({
    role              = string
    instance_id       = string
    private_ip        = string
    public_ip         = optional(string)
    availability_zone = string
    simulated_region  = optional(string)
  }))
  nullable = false

  validation {
    condition = (
      var.lab_profile == "minimal"
      ? keys(var.nodes) == tolist(["k3s-server"])
      : contains([
        tolist(["k3s-agent1", "k3s-server"]),
        tolist(["k3s-agent1", "k3s-agent2", "k3s-server"])
      ], keys(var.nodes))
    )
    error_message = "Inventory must contain k3s-server and the contiguous worker IDs required by the selected profile."
  }

  validation {
    condition = try(alltrue([
      for id, node in var.nodes : (
        node.role == (id == "k3s-server" ? "server" : "worker") &&
        can(regex("^i-([0-9a-f]{8}|[0-9a-f]{17})$", node.instance_id)) &&
        node.availability_zone == var.availability_zone &&
        can(cidrnetmask("${node.private_ip}/32")) &&
        node.private_ip == cidrhost("${node.private_ip}/32", 0) &&
        (var.lab_profile == "private" ? node.public_ip == null : (
          can(cidrnetmask("${node.public_ip}/32")) && node.public_ip == cidrhost("${node.public_ip}/32", 0)
        )) &&
        (id == "k3s-server" && var.lab_profile != "minimal"
          ? node.simulated_region == null
          : can(regex("^[a-z]{2}(-[a-z]+)+-[1-9][0-9]*$", node.simulated_region))
        )
      )
    ]), false)
    error_message = "Node facts must match the key, profile and selected AZ, with valid instance IDs, IPv4 addresses and placement labels for eligible nodes."
  }

  validation {
    condition = try(
      length(distinct([for node in var.nodes : node.instance_id])) == length(var.nodes) &&
      length(distinct([for node in var.nodes : node.private_ip])) == length(var.nodes) &&
      (var.lab_profile == "private" || length(distinct([for node in var.nodes : node.public_ip])) == length(var.nodes)),
      false
    )
    error_message = "Instance IDs, private IPs and any public IPs must be unique."
  }
}
