locals {
  node_roles = var.worker_count > 0 ? toset(["server", "worker"]) : toset(["server"])

  peer_directions = {
    for key, direction in {
      server-worker = { source = "server", destination = "worker" }
      worker-server = { source = "worker", destination = "server" }
      worker-worker = { source = "worker", destination = "worker" }
    } : key => direction if var.worker_count >= (key == "worker-worker" ? 2 : 1)
  }

  internal_rules = merge(
    var.worker_count > 0 ? {
      api-worker-server = {
        source      = "worker"
        destination = "server"
        protocol    = "tcp"
        port        = var.node_communication.api_port
        purpose     = "K3s API and supervisor"
      }
    } : {},
    {
      for key, direction in local.peer_directions : "vxlan-${key}" => merge(direction, {
        protocol = "udp"
        port     = var.node_communication.vxlan_port
        purpose  = "Flannel VXLAN"
      }) if var.node_communication.flannel_backend == "vxlan"
    },
    {
      for key, direction in local.peer_directions : "kubelet-${key}" => merge(direction, {
        protocol = "tcp"
        port     = var.node_communication.kubelet_port
        purpose  = "Kubelet metrics"
      }) if var.node_communication.metrics_server_enabled
    }
  )

  application_rules = var.public_ingress == null ? {} : {
    for entry in setproduct(var.public_ingress.node_roles, var.public_ingress.ports, var.public_ingress.source_cidrs) :
    "${entry[0]}:${entry[1]}:${entry[2]}" => {
      role = entry[0]
      port = entry[1]
      cidr = entry[2]
    }
  }

  web_egress_ports = toset([80, 443])
  web_egress_rules = {
    for entry in setproduct(local.node_roles, local.web_egress_ports) :
    "${entry[0]}-${entry[1]}" => { role = entry[0], port = entry[1] }
  }
}

resource "aws_security_group" "node" {
  for_each = local.node_roles

  name        = "k3s-${var.name_prefix}-${each.key}"
  description = "K3s lab ${each.key} node traffic"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "k3s-${var.name_prefix}-${each.key}"
    Role = each.key
  })
}

resource "aws_vpc_security_group_ingress_rule" "internal" {
  for_each = local.internal_rules

  security_group_id            = aws_security_group.node[each.value.destination].id
  referenced_security_group_id = aws_security_group.node[each.value.source].id
  description                  = "${each.value.purpose} from ${each.value.source} to ${each.value.destination}"
  ip_protocol                  = each.value.protocol
  from_port                    = each.value.port
  to_port                      = each.value.port
}

resource "aws_vpc_security_group_egress_rule" "internal" {
  for_each = local.internal_rules

  security_group_id            = aws_security_group.node[each.value.source].id
  referenced_security_group_id = aws_security_group.node[each.value.destination].id
  description                  = "${each.value.purpose} from ${each.value.source} to ${each.value.destination}"
  ip_protocol                  = each.value.protocol
  from_port                    = each.value.port
  to_port                      = each.value.port
}

resource "aws_vpc_security_group_ingress_rule" "application" {
  for_each = local.application_rules

  security_group_id = aws_security_group.node[each.value.role].id
  description       = "Approved application traffic to ${each.value.role}"
  cidr_ipv4         = each.value.cidr
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
}

resource "aws_vpc_security_group_egress_rule" "web" {
  for_each = local.web_egress_rules

  security_group_id = aws_security_group.node[each.value.role].id
  description       = each.value.port == 443 ? "HTTPS for SSM, OS and registry traffic" : "HTTP for signed OS package repositories"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
}
