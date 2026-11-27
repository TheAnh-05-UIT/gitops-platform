variable "vpc_id" {
  description = "ID of the VPC hosting the node security groups."
  type        = string
  nullable    = false
}

variable "name_prefix" {
  description = "Project and environment prefix for security group names."
  type        = string
  nullable    = false
}

variable "tags" {
  description = "Common Project, Environment, Owner, CostCenter, ManagedBy and optional resource tags."
  type        = map(string)
  nullable    = false
}

variable "administration" {
  description = "Only outbound SSM administration is supported."
  type        = string
  nullable    = false

  validation {
    condition     = var.administration == "ssm"
    error_message = "Node administration must use SSM without an inbound management rule."
  }
}

variable "lab_profile" {
  description = "Selected lab profile. Private nodes do not support public application ingress."
  type        = string
  nullable    = false

  validation {
    condition     = contains(["minimal", "multi-node", "private"], var.lab_profile)
    error_message = "Use the minimal, multi-node or private lab profile."
  }
}

variable "worker_count" {
  description = "Number of workers. Worker peer rules require two workers."
  type        = number
  nullable    = false

  validation {
    condition     = var.lab_profile == "minimal" ? var.worker_count == 0 : contains([1, 2], var.worker_count)
    error_message = "Use no workers with A and one or two with B/C."
  }
}

variable "node_communication" {
  description = "Single-server K3s ports and feature flags. A backend of none omits VXLAN rules and assumes separate CNI review."
  type = object({
    api_port               = optional(number, 6443)
    vxlan_port             = optional(number, 8472)
    kubelet_port           = optional(number, 10250)
    flannel_backend        = optional(string, "vxlan")
    metrics_server_enabled = optional(bool, true)
  })
  nullable = false

  validation {
    condition = (
      var.node_communication.api_port == 6443 &&
      var.node_communication.vxlan_port == 8472 &&
      var.node_communication.kubelet_port == 10250 &&
      contains(["vxlan", "none"], var.node_communication.flannel_backend)
    )
    error_message = "Use K3s ports 6443, 8472 and 10250, with the VXLAN or no-Flannel policy."
  }
}

variable "public_ingress" {
  description = "Approved application ingress for A/B. Explicit node roles and canonical restricted IPv4 sources are required."
  type = object({
    source_cidrs = set(string)
    ports        = set(number)
    node_roles   = set(string)
  })
  default = null

  validation {
    condition = var.public_ingress == null ? true : try(
      var.lab_profile != "private" &&
      length(var.public_ingress.node_roles) > 0 &&
      alltrue([
        for role in var.public_ingress.node_roles :
        role == "server" || (role == "worker" && var.worker_count > 0)
      ]) &&
      length(var.public_ingress.ports) > 0 &&
      alltrue([for port in var.public_ingress.ports : contains([80, 443], port)]) &&
      length(var.public_ingress.source_cidrs) > 0 &&
      alltrue([
        for cidr in var.public_ingress.source_cidrs :
        can(cidrnetmask(cidr)) &&
        cidr == format("%s/%d", cidrhost(cidr, 0), tonumber(split("/", cidr)[1]))
      ]) &&
      sum([for cidr in var.public_ingress.source_cidrs : pow(2, 32 - tonumber(split("/", cidr)[1]))]) < pow(2, 32),
      false
    )
    error_message = "Public application ingress requires A/B, existing node roles, TCP 80 or 443, and restricted canonical IPv4 sources."
  }
}
