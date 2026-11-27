variable "project_name" {
  description = "Stable project prefix for the lab's IAM role and instance profile."
  type        = string
  nullable    = false

  validation {
    condition     = length(var.project_name) <= 32 && can(regex("^[a-z][a-z0-9]*(-[a-z0-9]+)*$", var.project_name))
    error_message = "Use the lab's lowercase project naming contract, up to 32 characters."
  }
}

variable "environment" {
  description = "Lab environment identifier."
  type        = string
  nullable    = false

  validation {
    condition     = length(var.environment) <= 16 && can(regex("^[a-z][a-z0-9]*(-[a-z0-9]+)*$", var.environment))
    error_message = "Use the lab's lowercase environment naming contract, up to 16 characters."
  }
}

variable "aws_region" {
  description = "Region used to scope the account-wide IAM name and derive the managed policy ARN partition offline."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^((af|ap|ca|cn|eu|il|me|mx|sa|us)-[a-z]+|us-gov-(east|west))-[1-9][0-9]*$", var.aws_region))
    error_message = "Use a standard AWS commercial, China or GovCloud Region name."
  }
}

variable "tags" {
  description = "Common lab project, environment, ownership and cost allocation tags."
  type        = map(string)
  nullable    = false
}

variable "administration" {
  description = "Approved node administration strategy."
  type        = string
  nullable    = false

  validation {
    condition     = var.administration == "ssm"
    error_message = "The node instance profile supports SSM administration."
  }
}

variable "node_roles" {
  description = "Active roles in the selected profile. Both roles use the same instance profile."
  type        = set(string)
  nullable    = false

  validation {
    condition     = contains(var.node_roles, "server") && length(setsubtract(var.node_roles, toset(["server", "worker"]))) == 0
    error_message = "The server role is required and worker is the only optional role."
  }
}

variable "required_permissions" {
  description = "Explicit capability set for the EC2 role. Operator, controller and state capabilities belong to separate identities."
  type        = set(string)
  nullable    = false

  validation {
    condition     = var.required_permissions == toset(["ssm-managed-node"])
    error_message = "Only the ssm-managed-node capability is supported by the EC2 role."
  }
}
