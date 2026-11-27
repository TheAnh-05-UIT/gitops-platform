variable "bucket_name" {
  description = "Globally unique general-purpose S3 bucket name in the shared namespace of the approved partition."
  type        = string
  nullable    = false

  validation {
    condition = (
      can(regex("^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", var.bucket_name)) &&
      !anytrue([for prefix in ["xn--", "sthree-", "amzn-s3-demo-"] : startswith(var.bucket_name, prefix)]) &&
      !anytrue([for suffix in ["-s3alias", "--ol-s3", "--x-s3", "--table-s3", "-an"] : endswith(var.bucket_name, suffix)])
    )
    error_message = "Choose a 3–63 character S3 bucket name with lowercase letters, digits and hyphens, avoiding reserved prefixes and suffixes."
  }
}

variable "aws_account_id" {
  description = "Owner-approved account ID used to guard against initializing against the wrong AWS identity."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Supply the approved 12-digit AWS account ID as a string."
  }
}

variable "aws_region" {
  description = "Owner-approved Region for the state bucket."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[1-9][0-9]*$", var.aws_region))
    error_message = "Supply a Region name, without an Availability Zone suffix."
  }
}

variable "project_name" {
  description = "Project identifier matching the lab root. It becomes a state path segment."
  type        = string
  nullable    = false

  validation {
    condition     = length(var.project_name) <= 32 && can(regex("^[a-z][a-z0-9]*(-[a-z0-9]+)*$", var.project_name))
    error_message = "Use the lowercase lab project naming contract, up to 32 characters."
  }
}

variable "environment" {
  description = "One owner-approved lab environment matching the lab root. It becomes a state path segment."
  type        = string
  nullable    = false

  validation {
    condition     = length(var.environment) <= 16 && can(regex("^[a-z][a-z0-9]*(-[a-z0-9]+)*$", var.environment))
    error_message = "Use the lowercase lab environment naming contract, up to 16 characters."
  }
}

variable "cost_allocation" {
  description = "Non-sensitive owner/team alias and billing cost center for the state bucket."
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
    error_message = "Supply non-empty owner and cost center tags of up to 256 characters."
  }
}

variable "resource_tags" {
  description = "Additional non-sensitive tags. Project, environment, owner, cost center, manager and name are reserved."
  type        = map(string)
  default     = {}
  nullable    = false

  validation {
    condition = length(var.resource_tags) <= 44 && alltrue([
      for key, value in var.resource_tags :
      can(regex("^[A-Za-z0-9][A-Za-z0-9_./:=+@-]{0,127}$", key)) &&
      !startswith(lower(key), "aws:") &&
      !contains(["project", "environment", "owner", "costcenter", "managedby", "name"], lower(key)) &&
      try(length(value) <= 256, false)
    ])
    error_message = "Set up to 44 extra AWS tags with valid keys and values. AWS-reserved and identity/cost keys cannot be overridden."
  }
}
