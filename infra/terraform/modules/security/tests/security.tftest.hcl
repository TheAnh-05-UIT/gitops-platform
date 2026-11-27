mock_provider "aws" {
  override_during = plan
}

override_resource {
  target          = aws_security_group.node["server"]
  override_during = plan
  values          = { id = "sg-00000000000000001" }
}

override_resource {
  target          = aws_security_group.node["worker"]
  override_during = plan
  values          = { id = "sg-00000000000000002" }
}

variables {
  vpc_id      = "vpc-0123456789abcdef0"
  name_prefix = "platform-lab"
  tags = {
    Project     = "platform"
    Environment = "lab"
    Owner       = "platform"
    CostCenter  = "engineering"
    ManagedBy   = "terraform"
  }
  administration     = "ssm"
  lab_profile        = "multi-node"
  worker_count       = 1
  node_communication = {}
}

run "minimal_has_no_inbound_rules" {
  command = plan

  variables {
    lab_profile  = "minimal"
    worker_count = 0
  }

  assert {
    condition = (
      toset(keys(aws_security_group.node)) == toset(["server"]) &&
      length(aws_vpc_security_group_ingress_rule.internal) == 0 &&
      length(aws_vpc_security_group_egress_rule.internal) == 0 &&
      length(aws_vpc_security_group_ingress_rule.application) == 0 &&
      output.worker_security_group_id == null && output.application_security_group_id == null &&
      output.server_security_group_id == aws_security_group.node["server"].id &&
      toset(keys(output.security_group_ids_by_role)) == toset(["server"]) &&
      toset(keys(aws_vpc_security_group_egress_rule.web)) == toset(["server-80", "server-443"])
    )
    error_message = "A must have a server SG with no ingress and just the web egress policy."
  }
}

run "one_worker_exact_internal_policy" {
  command = plan

  assert {
    condition = (
      toset([
        for key, rule in aws_vpc_security_group_ingress_rule.internal :
        "${key}:${rule.ip_protocol}:${rule.from_port}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.referenced_security_group_id])}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.security_group_id])}"
        ]) == toset([
        "api-worker-server:tcp:6443:worker:server",
        "vxlan-server-worker:udp:8472:server:worker",
        "vxlan-worker-server:udp:8472:worker:server",
        "kubelet-server-worker:tcp:10250:server:worker",
        "kubelet-worker-server:tcp:10250:worker:server",
      ]) &&
      toset([
        for key, rule in aws_vpc_security_group_egress_rule.internal :
        "${key}:${rule.ip_protocol}:${rule.from_port}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.security_group_id])}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.referenced_security_group_id])}"
        ]) == toset([
        "api-worker-server:tcp:6443:worker:server",
        "vxlan-server-worker:udp:8472:server:worker",
        "vxlan-worker-server:udp:8472:worker:server",
        "kubelet-server-worker:tcp:10250:server:worker",
        "kubelet-worker-server:tcp:10250:worker:server",
      ])
    )
    error_message = "Every internal rule must have the correct role direction, port and protocol in both SGs."
  }

  assert {
    condition = (
      length(aws_vpc_security_group_ingress_rule.application) == 0 &&
      alltrue([for rule in aws_vpc_security_group_ingress_rule.internal :
        rule.cidr_ipv4 == null && rule.cidr_ipv6 == null && rule.prefix_list_id == null &&
        rule.from_port == rule.to_port
      ]) &&
      alltrue([for rule in aws_vpc_security_group_egress_rule.internal :
        rule.cidr_ipv4 == null && rule.cidr_ipv6 == null && rule.prefix_list_id == null &&
        rule.from_port == rule.to_port
      ]) &&
      alltrue([for sg in aws_security_group.node : sg.vpc_id == var.vpc_id &&
        length(sg.ingress) == 0 && length(sg.egress) == 0 &&
        sg.tags.Project == "platform" && sg.tags.Environment == "lab"
      ])
    )
    error_message = "The full default ingress set must consist only of single-port SG references."
  }

  assert {
    condition = (
      toset(keys(aws_vpc_security_group_egress_rule.web)) == toset(["server-80", "server-443", "worker-80", "worker-443"]) &&
      alltrue([for key, rule in aws_vpc_security_group_egress_rule.web :
        rule.cidr_ipv4 == "0.0.0.0/0" && rule.cidr_ipv6 == null && rule.referenced_security_group_id == null &&
        rule.prefix_list_id == null && rule.ip_protocol == "tcp" && rule.from_port == rule.to_port &&
        key == "${one([for role, sg in aws_security_group.node : role if sg.id == rule.security_group_id])}-${rule.to_port}"
      ]) &&
      output.security_group_ids_by_role["server"][0] == output.server_security_group_id &&
      output.security_group_ids_by_role["worker"][0] == output.worker_security_group_id &&
      output.policy.administration == "ssm" &&
      output.policy.public_ingress == null
    )
    error_message = "Web egress and future compute outputs must match the scoped policy."
  }
}

run "two_workers_enable_worker_peer_rules" {
  command = plan

  variables {
    lab_profile  = "private"
    worker_count = 2
  }

  assert {
    condition = (
      toset([
        for key, rule in aws_vpc_security_group_ingress_rule.internal :
        "${key}:${rule.ip_protocol}:${rule.from_port}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.referenced_security_group_id])}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.security_group_id])}"
        ]) == toset([
        "api-worker-server:tcp:6443:worker:server",
        "vxlan-server-worker:udp:8472:server:worker",
        "vxlan-worker-server:udp:8472:worker:server",
        "kubelet-server-worker:tcp:10250:server:worker",
        "kubelet-worker-server:tcp:10250:worker:server",
        "vxlan-worker-worker:udp:8472:worker:worker",
        "kubelet-worker-worker:tcp:10250:worker:worker",
      ]) &&
      toset([
        for key, rule in aws_vpc_security_group_egress_rule.internal :
        "${key}:${rule.ip_protocol}:${rule.from_port}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.security_group_id])}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.referenced_security_group_id])}"
        ]) == toset([
        "api-worker-server:tcp:6443:worker:server",
        "vxlan-server-worker:udp:8472:server:worker",
        "vxlan-worker-server:udp:8472:worker:server",
        "kubelet-server-worker:tcp:10250:server:worker",
        "kubelet-worker-server:tcp:10250:worker:server",
        "vxlan-worker-worker:udp:8472:worker:worker",
        "kubelet-worker-worker:tcp:10250:worker:worker",
      ])
    )
    error_message = "Every internal rule must have the correct role direction, port and protocol in both SGs."
  }

  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.application) == 0 && length(aws_security_group.node) == 2
    error_message = "C must keep two role groups and no public application rules."
  }
}

run "without_vxlan_or_metrics_only_api_remains" {
  command = plan

  variables {
    node_communication = { flannel_backend = "none", metrics_server_enabled = false }
  }

  assert {
    condition = (
      toset([
        for key, rule in aws_vpc_security_group_ingress_rule.internal :
        "${key}:${rule.ip_protocol}:${rule.from_port}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.referenced_security_group_id])}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.security_group_id])}"
      ]) == toset(["api-worker-server:tcp:6443:worker:server"]) &&
      toset([
        for key, rule in aws_vpc_security_group_egress_rule.internal :
        "${key}:${rule.ip_protocol}:${rule.from_port}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.security_group_id])}:${one([for role, sg in aws_security_group.node : role if sg.id == rule.referenced_security_group_id])}"
      ]) == toset(["api-worker-server:tcp:6443:worker:server"])
    )
    error_message = "VXLAN and kubelet rules must be conditional on the intended features."
  }
}

run "approved_application_ingress" {
  command = plan

  variables {
    public_ingress = {
      source_cidrs = ["198.51.100.8/32", "203.0.113.0/28"]
      ports        = [80, 443]
      node_roles   = ["worker"]
    }
  }

  assert {
    condition = (
      toset(keys(aws_vpc_security_group_ingress_rule.application)) == toset([
        "worker:80:198.51.100.8/32", "worker:80:203.0.113.0/28",
        "worker:443:198.51.100.8/32", "worker:443:203.0.113.0/28",
      ]) &&
      alltrue([for key, rule in aws_vpc_security_group_ingress_rule.application :
        rule.security_group_id == aws_security_group.node["worker"].id &&
        key == "worker:${rule.to_port}:${rule.cidr_ipv4}" &&
        rule.from_port == rule.to_port && rule.ip_protocol == "tcp" &&
        rule.cidr_ipv6 == null && rule.referenced_security_group_id == null && rule.prefix_list_id == null
      ]) &&
      output.application_security_group_id == null &&
      output.policy.public_ingress.node_roles == toset(["worker"])
    )
    error_message = "Only the explicitly selected group may receive restricted application traffic."
  }
}

run "reject_unrestricted_ipv4" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["0.0.0.0/0"], ports = [443], node_roles = ["server"] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_combined_internet_cidrs" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["0.0.0.0/1", "128.0.0.0/1"], ports = [443], node_roles = ["server"] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_missing_ingress_roles" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [443], node_roles = [] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_worker_ingress_in_minimal" {
  command = plan

  variables {
    lab_profile    = "minimal"
    worker_count   = 0
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [443], node_roles = ["worker"] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_private_public_ingress" {
  command = plan

  variables {
    lab_profile    = "private"
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [443], node_roles = ["server"] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_admin_port" {
  command = plan

  variables {
    public_ingress = { source_cidrs = ["198.51.100.8/32"], ports = [6443], node_roles = ["server"] }
  }

  expect_failures = [var.public_ingress]
}

run "reject_ssh_strategy" {
  command = plan

  variables {
    administration = "ssh"
  }

  expect_failures = [var.administration]
}
