variable "node_definitions" {
  description = "Desired lab nodes keyed by stable logical ID, with placement, storage, identity tags and optional simulated Region."
  type = map(object({
    role                  = string
    name                  = string
    instance_type         = string
    availability_zone     = string
    subnet_key            = string
    associate_public_ipv4 = bool
    imdsv2_required       = bool
    root_volume = object({
      type                  = string
      size_gib              = number
      encrypted             = bool
      delete_on_termination = bool
    })
    tags             = map(string)
    simulated_region = optional(string)
  }))
  nullable = false

  validation {
    condition = contains([
      tolist(["k3s-server"]),
      tolist(["k3s-agent1", "k3s-server"]),
      tolist(["k3s-agent1", "k3s-agent2", "k3s-server"])
    ], tolist(keys(var.node_definitions)))
    error_message = "Supply k3s-server and zero, one or two consecutive k3s-agent slots."
  }

  validation {
    condition = try(
      length(distinct([for node in var.node_definitions : node.subnet_key])) == 1 &&
      length(distinct([for node in var.node_definitions : node.availability_zone])) == 1 &&
      alltrue([
        for id, node in var.node_definitions :
        node.role == (id == "k3s-server" ? "server" : "worker") &&
        contains(["public", "private"], node.subnet_key) &&
        (node.subnet_key == "public" || length(var.node_definitions) > 1) &&
        node.associate_public_ipv4 == (node.subnet_key == "public")
      ]),
      false
    )
    error_message = "Use one subnet role and AZ, match node keys to roles, and assign IPv4 publicly only in the public subnet. Private profiles need a worker."
  }

  validation {
    condition = try(alltrue([
      for node in var.node_definitions :
      node.imdsv2_required && node.root_volume.encrypted &&
      node.root_volume.type == "gp3" &&
      node.root_volume.size_gib >= 1 && node.root_volume.size_gib <= 16384 &&
      floor(node.root_volume.size_gib) == node.root_volume.size_gib &&
      node.root_volume.delete_on_termination != null
    ]), false)
    error_message = "Every node requires IMDSv2 and an encrypted gp3 root with a whole 1–16384 GiB size and explicit deletion behavior."
  }

  validation {
    condition = try(alltrue([
      for node in var.node_definitions :
      can(regex("^[a-z][a-z0-9-]*[.][a-z0-9]+$", node.instance_type)) &&
      lookup(local.known_architectures, split(".", node.instance_type)[0], var.ami.architecture) == var.ami.architecture
    ]), false)
    error_message = "Supply a valid instance type and pair known instance families with the declared AMI architecture."
  }
}

variable "subnet_ids" {
  description = "Route-ready subnet IDs keyed by public or private role."
  type        = map(string)
  nullable    = false

  validation {
    condition = alltrue([
      for node in var.node_definitions : try(length(trimspace(var.subnet_ids[node.subnet_key])) > 0, false)
    ])
    error_message = "Each node requires an explicit subnet ID for its selected subnet role."
  }
}

variable "security_group_ids_by_role" {
  description = "Rule-ready lists of security group IDs keyed by server or worker role."
  type        = map(list(string))
  nullable    = false

  validation {
    condition = alltrue([
      for node in var.node_definitions : try(
        length(var.security_group_ids_by_role[node.role]) > 0 &&
        alltrue([for id in var.security_group_ids_by_role[node.role] : length(trimspace(id)) > 0]),
        false
      )
    ])
    error_message = "Each active role needs at least one explicit security group ID."
  }
}

variable "instance_profile_names_by_role" {
  description = "SSM-ready instance profile names keyed by server or worker role."
  type        = map(string)
  nullable    = false

  validation {
    condition = alltrue([
      for node in var.node_definitions : try(length(trimspace(var.instance_profile_names_by_role[node.role])) > 0, false)
    ])
    error_message = "Each active role needs an explicit IAM instance profile name."
  }
}

variable "ami" {
  description = "One pinned regional EBS-backed Linux AMI and its declared architecture. Verify image metadata and all instance types at the owner gate."
  type = object({
    id           = string
    architecture = optional(string, "x86_64")
  })
  nullable = false

  validation {
    condition     = can(regex("^ami-([0-9a-f]{8}|[0-9a-f]{17})$", var.ami.id)) && contains(["x86_64", "arm64"], var.ami.architecture)
    error_message = "Supply a pinned AMI ID and supported architecture x86_64 or arm64."
  }
}
