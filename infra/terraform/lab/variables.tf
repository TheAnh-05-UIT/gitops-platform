variable "project_name" {
  description = "Project name used in AWS Name tags and resource names."
  type        = string
  default     = "gitops-platform"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9]*(-[a-z0-9]+)*$", var.project_name)) && length(var.project_name) <= 32
    error_message = "project_name must be 1 to 32 lowercase alphanumeric characters in hyphen-separated segments, starting with a letter."
  }
}

variable "environment" {
  description = "Environment name identifying the deployment and future state key."
  type        = string
  default     = "lab"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9]*(-[a-z0-9]+)*$", var.environment)) && length(var.environment) <= 16
    error_message = "environment must be 1 to 16 lowercase alphanumeric characters in hyphen-separated segments, starting with a letter."
  }
}

variable "aws_region" {
  description = "Owner-approved AWS Region for subnet placement and the pinned AMI."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[1-9][0-9]*$", var.aws_region))
    error_message = "aws_region must have the format of a standard AWS Region name."
  }
}

variable "availability_zone" {
  description = "One standard Availability Zone name in aws_region, resolved for the owner's account later."
  type        = string
  nullable    = false

  validation {
    condition = (
      startswith(var.availability_zone, var.aws_region) &&
      length(var.availability_zone) == length(var.aws_region) + 1 &&
      can(regex("[a-z]$", var.availability_zone))
    )
    error_message = "availability_zone must be aws_region followed by a single lowercase letter."
  }
}

variable "lab_profile" {
  description = "One deployment topology: minimal (A), multi-node (B), or private (C)."
  type        = string
  default     = "multi-node"
  nullable    = false

  validation {
    condition     = contains(["minimal", "multi-node", "private"], var.lab_profile)
    error_message = "lab_profile must be minimal, multi-node or private."
  }
}

variable "network" {
  description = "Canonical IPv4 CIDRs for the VPC and subnets. Set private_subnet_cidr only for Profile C."
  type = object({
    vpc_cidr            = optional(string, "10.20.0.0/16")
    public_subnet_cidr  = optional(string, "10.20.1.0/24")
    private_subnet_cidr = optional(string)
  })
  default  = {}
  nullable = false

  validation {
    condition = try(alltrue([
      for cidr in values(var.network) : (
        can(cidrnetmask(cidr)) &&
        cidr == format("%s/%d", cidrhost(cidr, 0), tonumber(split("/", cidr)[1])) &&
        tonumber(split("/", cidr)[1]) >= 16 &&
        tonumber(split("/", cidr)[1]) <= 28
      ) if cidr != null
    ]), false)
    error_message = "Network CIDRs must be canonical IPv4 blocks with a prefix length of /16 through /28."
  }

  validation {
    condition     = (var.network.private_subnet_cidr != null) == (var.lab_profile == "private")
    error_message = "private_subnet_cidr is required for Profile C and omitted for Profiles A and B."
  }

  validation {
    # A subnet fits when its prefix is at least as specific and its base masks to the VPC base.
    condition = try(alltrue([
      for subnet in [var.network.public_subnet_cidr, var.network.private_subnet_cidr] : (
        tonumber(split("/", subnet)[1]) >= tonumber(split("/", var.network.vpc_cidr)[1]) &&
        cidrhost("${cidrhost(subnet, 0)}/${split("/", var.network.vpc_cidr)[1]}", 0) == cidrhost(var.network.vpc_cidr, 0)
      ) if subnet != null
    ]), false)
    error_message = "Subnets must be fully contained in the VPC."
  }

  validation {
    # Canonical CIDRs overlap only if one subnet contains the base address of the other.
    condition = var.network.private_subnet_cidr == null ? true : try(alltrue([
      for pair in [
        { subnet = var.network.public_subnet_cidr, other = var.network.private_subnet_cidr },
        { subnet = var.network.private_subnet_cidr, other = var.network.public_subnet_cidr }
        ] : (
        cidrhost("${cidrhost(pair.subnet, 0)}/${split("/", pair.other)[1]}", 0) != cidrhost(pair.other, 0)
      )
    ]), false)
    error_message = "The public and private subnets must not overlap."
  }
}

variable "nat_gateway_enabled" {
  description = "Explicitly approve the intended same-AZ public NAT Gateway for Profile C configuration."
  type        = bool
  default     = false
  nullable    = false

  validation {
    condition     = var.nat_gateway_enabled == (var.lab_profile == "private")
    error_message = "Profile C requires nat_gateway_enabled = true. Profiles A and B do not use NAT."
  }
}

variable "worker_count" {
  description = "Number of K3s workers. The second worker is always explicit."
  type        = number
  default     = 1
  nullable    = false

  validation {
    condition     = var.lab_profile == "minimal" ? var.worker_count == 0 : contains([1, 2], var.worker_count)
    error_message = "Use zero workers for Profile A, or one or two whole workers for Profiles B and C."
  }
}

variable "ami" {
  description = "Pinned regional AMI ID and expected Linux CPU architecture. Verify ownership, architecture, SSM Agent and platform compatibility at the owner gate."
  type = object({
    id           = string
    architecture = optional(string, "x86_64")
  })
  nullable = false

  validation {
    condition     = can(regex("^ami-([0-9a-f]{8}|[0-9a-f]{17})$", var.ami.id)) && contains(["x86_64", "arm64"], var.ami.architecture)
    error_message = "ami requires a pinned AMI ID and an architecture of x86_64 or arm64."
  }
}

variable "server" {
  description = "K3s server EC2 type and encrypted gp3 root volume settings."
  type = object({
    instance_type = optional(string, "t3.medium")
    root_volume = optional(object({
      size_gib              = optional(number, 20)
      delete_on_termination = optional(bool, true)
    }), {})
  })
  default  = {}
  nullable = false

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]*[.][a-z0-9]+$", var.server.instance_type)) &&
      var.server.root_volume.size_gib >= 1 && var.server.root_volume.size_gib <= 16384 &&
      floor(var.server.root_volume.size_gib) == var.server.root_volume.size_gib
    )
    error_message = "server needs an EC2 instance type and a whole root volume size between 1 and 16384 GiB."
  }
}

variable "worker" {
  description = "EC2 type and encrypted gp3 root volume settings shared by workers, with optional placement label overrides keyed by worker ID."
  type = object({
    instance_type = optional(string, "t3.small")
    root_volume = optional(object({
      size_gib              = optional(number, 20)
      delete_on_termination = optional(bool, true)
    }), {})
    simulated_regions = optional(map(string), {})
  })
  default  = {}
  nullable = false

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]*[.][a-z0-9]+$", var.worker.instance_type)) &&
      var.worker.root_volume.size_gib >= 1 && var.worker.root_volume.size_gib <= 16384 &&
      floor(var.worker.root_volume.size_gib) == var.worker.root_volume.size_gib &&
      alltrue([
        for id, label in var.worker.simulated_regions :
        contains(["k3s-agent1", "k3s-agent2"], id) && length(label) <= 63 && can(regex("^[a-z]{2}(-[a-z]+)+-[1-9][0-9]*$", label))
      ])
    )
    error_message = "worker needs an EC2 type, a whole volume size between 1 and 16384 GiB, and region-shaped labels keyed by k3s-agent1 or k3s-agent2."
  }
}

variable "administrative_access" {
  description = "SSM is the sole supported administrative strategy. Public SSH and public Kubernetes API are disabled."
  type        = string
  default     = "ssm"
  nullable    = false

  validation {
    condition     = var.administrative_access == "ssm"
    error_message = "administrative_access must be ssm."
  }
}

variable "public_ingress" {
  description = "Optional application ingress intent on TCP 80/443 for A/B with approved IPv4 sources. Rules are created only for explicitly selected node_roles."
  type = object({
    source_cidrs = set(string)
    ports        = set(number)
    node_roles   = optional(set(string), [])
  })
  default = null

  validation {
    condition = var.public_ingress == null ? true : try(
      var.lab_profile != "private" &&
      alltrue([
        for role in var.public_ingress.node_roles :
        role == "server" || (role == "worker" && var.lab_profile == "multi-node")
      ]) &&
      length(var.public_ingress.source_cidrs) > 0 &&
      length(var.public_ingress.ports) > 0 &&
      alltrue([for port in var.public_ingress.ports : contains([80, 443], port)]) &&
      alltrue([
        for cidr in var.public_ingress.source_cidrs :
        can(cidrnetmask(cidr)) &&
        cidr == format("%s/%d", cidrhost(cidr, 0), tonumber(split("/", cidr)[1]))
      ]) &&
      sum([for cidr in var.public_ingress.source_cidrs : pow(2, 32 - tonumber(split("/", cidr)[1]))]) < pow(2, 32),
      false
    )
    error_message = "Public ingress requires A/B, existing node roles, TCP 80/443 and canonical, restricted IPv4 CIDRs."
  }
}

variable "resource_tags" {
  description = "Extra non-sensitive AWS tags. Identity and billing tags are managed by this contract."
  type        = map(string)
  default     = {}
  nullable    = false

  validation {
    condition = length(var.resource_tags) <= 43 && alltrue([
      for key, value in var.resource_tags :
      can(regex("^[A-Za-z0-9][A-Za-z0-9_./:=+@-]{0,127}$", key)) &&
      !startswith(lower(key), "aws:") &&
      !contains(["project", "environment", "owner", "costcenter", "managedby", "name", "role"], lower(key)) &&
      try(length(value) <= 256, false)
    ])
    error_message = "Set up to 43 custom AWS tags with valid keys and at most 256 characters per value. Identity, cost and AWS-reserved keys cannot be overridden."
  }
}

variable "cost_allocation" {
  description = "Non-sensitive owner/team alias and billing cost center used in resource tags."
  type = object({
    owner       = string
    cost_center = string
  })
  nullable = false

  validation {
    condition = alltrue([
      for value in values(var.cost_allocation) :
      try(length(trimspace(value)) > 0 && length(value) <= 256, false)
    ])
    error_message = "cost_allocation requires non-empty owner and cost_center tags of at most 256 characters."
  }
}
