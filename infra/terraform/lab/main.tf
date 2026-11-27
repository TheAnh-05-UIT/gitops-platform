locals {
  private_nodes = var.lab_profile == "private"
  name_prefix   = "${var.project_name}-${var.environment}"
  resource_tags = merge(var.resource_tags, {
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.cost_allocation.owner
    CostCenter  = var.cost_allocation.cost_center
    ManagedBy   = "terraform"
  })

  network_topology = merge(var.network, {
    lab_profile           = var.lab_profile
    availability_zone     = var.availability_zone
    node_subnet           = local.private_nodes ? "private" : "public"
    egress                = local.private_nodes ? "nat-gateway" : "internet-gateway"
    associate_public_ipv4 = !local.private_nodes
    nat_gateway_enabled   = var.nat_gateway_enabled
  })

  worker_slots = { k3s-agent1 = 1, k3s-agent2 = 2 }
  node_settings = merge(
    {
      k3s-server = {
        role             = "server"
        instance_type    = var.server.instance_type
        root_volume      = var.server.root_volume
        simulated_region = var.lab_profile == "minimal" ? "ap-southeast-1" : null
      }
    },
    {
      for id, slot in local.worker_slots : id => {
        role             = "worker"
        instance_type    = var.worker.instance_type
        root_volume      = var.worker.root_volume
        simulated_region = lookup(var.worker.simulated_regions, id, "ap-southeast-1")
      } if slot <= var.worker_count
    }
  )

  node_definitions = {
    for id, settings in local.node_settings : id => merge(settings, {
      name                  = "${local.name_prefix}-${id}"
      availability_zone     = var.availability_zone
      subnet_key            = local.network_topology.node_subnet
      associate_public_ipv4 = local.network_topology.associate_public_ipv4
      imdsv2_required       = true
      root_volume           = merge(settings.root_volume, { type = "gp3", encrypted = true })
      tags = merge(local.resource_tags, {
        Name = "${local.name_prefix}-${id}"
        Role = settings.role
      })
    })
  }
}

module "networking" {
  source = "../modules/networking"

  name_prefix      = local.name_prefix
  tags             = local.resource_tags
  network_topology = local.network_topology
}

module "security" {
  source = "../modules/security"

  vpc_id         = module.networking.vpc_id
  name_prefix    = local.name_prefix
  tags           = local.resource_tags
  administration = var.administrative_access
  lab_profile    = var.lab_profile
  worker_count   = var.worker_count

  node_communication = {
    flannel_backend        = "vxlan"
    metrics_server_enabled = true
  }

  # P1.2 input files without role selection remain valid without opening ports.
  public_ingress = var.public_ingress == null ? null : (
    length(var.public_ingress.node_roles) > 0 ? var.public_ingress : null
  )
}

module "iam" {
  source = "../modules/iam"

  project_name         = var.project_name
  environment          = var.environment
  aws_region           = var.aws_region
  tags                 = local.resource_tags
  administration       = var.administrative_access
  node_roles           = toset([for node in local.node_definitions : node.role])
  required_permissions = toset(["ssm-managed-node"])
}

module "compute" {
  source = "../modules/compute"

  node_definitions               = local.node_definitions
  subnet_ids                     = module.networking.subnet_ids
  security_group_ids_by_role     = module.security.security_group_ids_by_role
  instance_profile_names_by_role = module.iam.instance_profile_names_by_role
  ami                            = var.ami
}

module "ansible_inventory" {
  source = "../modules/ansible-inventory"

  environment       = var.environment
  aws_region        = var.aws_region
  availability_zone = var.availability_zone
  lab_profile       = var.lab_profile
  nodes             = module.compute.nodes
}
