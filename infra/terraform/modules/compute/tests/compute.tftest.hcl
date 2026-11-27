mock_provider "aws" {
  override_during = plan
}


override_resource {
  target          = aws_instance.node["k3s-server"]
  override_during = plan
  values = {
    id               = "i-00000000000000001"
    private_ip       = "10.20.1.10"
    public_ip        = "192.0.2.10"
    key_name         = ""
    user_data_base64 = ""
  }
}

override_resource {
  target          = aws_instance.node["k3s-agent1"]
  override_during = plan
  values = {
    id               = "i-00000000000000002"
    private_ip       = "10.20.1.11"
    public_ip        = "192.0.2.11"
    key_name         = ""
    user_data_base64 = ""
  }
}

override_resource {
  target          = aws_instance.node["k3s-agent2"]
  override_during = plan
  values = {
    id               = "i-00000000000000003"
    private_ip       = "10.20.1.12"
    public_ip        = "192.0.2.12"
    key_name         = ""
    user_data_base64 = ""
  }
}

variables {
  ami                            = { id = "ami-00000000000000000", architecture = "x86_64" }
  subnet_ids                     = { public = "subnet-00000000000000001", private = "subnet-00000000000000002" }
  security_group_ids_by_role     = { server = ["sg-00000000000000001"], worker = ["sg-00000000000000002"] }
  instance_profile_names_by_role = { server = "lab-ssm", worker = "lab-ssm" }
  node_definitions = {
    k3s-server = {
      role                  = "server"
      name                  = "gitops-platform-lab-k3s-server"
      instance_type         = "t3.medium"
      availability_zone     = "us-east-1a"
      subnet_key            = "public"
      associate_public_ipv4 = true
      imdsv2_required       = true
      root_volume           = { type = "gp3", size_gib = 30, encrypted = true, delete_on_termination = false }
      simulated_region      = null
      tags = {
        Name        = "gitops-platform-lab-k3s-server"
        Role        = "server"
        Project     = "gitops-platform"
        Environment = "lab"
        Owner       = "platform-lab"
        CostCenter  = "engineering-lab"
      }
    }
    k3s-agent1 = {
      role                  = "worker"
      name                  = "gitops-platform-lab-k3s-agent1"
      instance_type         = "t3.small"
      availability_zone     = "us-east-1a"
      subnet_key            = "public"
      associate_public_ipv4 = true
      imdsv2_required       = true
      root_volume           = { type = "gp3", size_gib = 20, encrypted = true, delete_on_termination = true }
      simulated_region      = "ap-southeast-1"
      tags = {
        Name        = "gitops-platform-lab-k3s-agent1"
        Role        = "worker"
        Project     = "gitops-platform"
        Environment = "lab"
        Owner       = "platform-lab"
        CostCenter  = "engineering-lab"
      }
    }
  }
}


run "minimal_only_server" {
  command = plan

  variables {
    node_definitions = { k3s-server = var.node_definitions["k3s-server"] }
  }

  assert {
    condition = (
      toset(keys(aws_instance.node)) == toset(["k3s-server"]) &&
      aws_instance.node["k3s-server"].subnet_id == var.subnet_ids["public"] &&
      aws_instance.node["k3s-server"].associate_public_ip_address &&
      aws_instance.node["k3s-server"].vpc_security_group_ids == toset(var.security_group_ids_by_role["server"])
    )
    error_message = "Only the minimal server is placed in the routed public subnet with its dedicated SG."
  }
}


run "multi_node_secure_configuration" {
  command = plan

  assert {
    condition = (
      toset(keys(aws_instance.node)) == toset(["k3s-server", "k3s-agent1"]) &&
      alltrue([for id, instance in aws_instance.node :
        instance.ami == var.ami.id &&
        instance.instance_type == var.node_definitions[id].instance_type &&
        instance.availability_zone == var.node_definitions[id].availability_zone &&
        instance.subnet_id == var.subnet_ids["public"] &&
        instance.associate_public_ip_address &&
        instance.vpc_security_group_ids == toset(var.security_group_ids_by_role[var.node_definitions[id].role]) &&
        instance.iam_instance_profile == var.instance_profile_names_by_role[var.node_definitions[id].role]
      ])
    )
    error_message = "The server and worker must each use their reviewed AMI, sizing, subnet, SG and SSM profile."
  }

  assert {
    condition = alltrue([for id, instance in aws_instance.node :
      one(instance.metadata_options).http_endpoint == "enabled" &&
      one(instance.metadata_options).http_tokens == "required" &&
      one(instance.metadata_options).http_put_response_hop_limit == 1 &&
      one(instance.metadata_options).http_protocol_ipv6 == "disabled" &&
      one(instance.metadata_options).instance_metadata_tags == "disabled" &&
      one(instance.root_block_device).encrypted &&
      one(instance.root_block_device).volume_type == "gp3" &&
      one(instance.root_block_device).volume_size == var.node_definitions[id].root_volume.size_gib &&
      one(instance.root_block_device).delete_on_termination == var.node_definitions[id].root_volume.delete_on_termination &&
      instance.tags == tomap(var.node_definitions[id].tags) &&
      instance.volume_tags == tomap(merge(var.node_definitions[id].tags, { Name = "${var.node_definitions[id].name}-root" })) &&
      length(instance.ebs_block_device) == 0
    ])
    error_message = "Every EC2 instance must have fixed metadata settings and an encrypted gp3 root with explicit lifecycle and tags."
  }

  assert {
    condition = alltrue([for instance in aws_instance.node :
      instance.key_name == "" && instance.user_data == null &&
      nonsensitive(instance.user_data_base64 == "")
    ])
    error_message = "Every EC2 instance must omit SSH keys and bootstrap payloads."
  }

  assert {
    condition = (
      output.nodes["k3s-agent1"].instance_id == aws_instance.node["k3s-agent1"].id &&
      output.nodes["k3s-agent1"].private_ip == "10.20.1.11" &&
      output.nodes["k3s-agent1"].public_ip == "192.0.2.11" &&
      output.nodes["k3s-agent1"].logical_id == "k3s-agent1" &&
      output.nodes["k3s-agent1"].simulated_region == "ap-southeast-1" &&
      output.nodes["k3s-agent1"].role == "worker"
    )
    error_message = "Node output must use observed EC2 facts without losing logical metadata."
  }
}


run "add_worker_preserves_addresses" {
  command = plan

  variables {
    node_definitions = merge(var.node_definitions, {
      k3s-agent2 = merge(var.node_definitions["k3s-agent1"], {
        name = "gitops-platform-lab-k3s-agent2"
        tags = merge(var.node_definitions["k3s-agent1"].tags, { Name = "gitops-platform-lab-k3s-agent2" })
      })
    })
  }

  assert {
    condition = (
      toset(keys(aws_instance.node)) == toset(["k3s-server", "k3s-agent1", "k3s-agent2"]) &&
      output.nodes["k3s-server"] == run.multi_node_secure_configuration.nodes["k3s-server"] &&
      output.nodes["k3s-agent1"] == run.multi_node_secure_configuration.nodes["k3s-agent1"] &&
      output.nodes["k3s-agent2"].instance_id == "i-00000000000000003"
    )
    error_message = "Adding the second worker must leave the existing for_each node identities intact."
  }
}


run "private_explicitly_disables_public_ipv4" {
  command = plan

  variables {
    node_definitions = {
      for id, node in var.node_definitions : id => merge(node, {
        subnet_key            = "private"
        associate_public_ipv4 = false
      })
    }
  }

  override_resource {
    target          = aws_instance.node["k3s-server"]
    override_during = plan
    values = {
      id         = "i-00000000000000001"
      private_ip = "10.20.2.10"
      public_ip  = ""
    }
  }

  override_resource {
    target          = aws_instance.node["k3s-agent1"]
    override_during = plan
    values = {
      id         = "i-00000000000000002"
      private_ip = "10.20.2.11"
      public_ip  = ""
    }
  }

  assert {
    condition = alltrue([for id, instance in aws_instance.node :
      instance.subnet_id == var.subnet_ids["private"] && !instance.associate_public_ip_address &&
      output.nodes[id].public_ip == null && startswith(output.nodes[id].private_ip, "10.20.2.")
    ])
    error_message = "Private nodes must use the private subnet and publish null public IPs."
  }
}


run "known_arm64_families_supported" {
  command = plan

  variables {
    ami = { id = "ami-00000000000000000", architecture = "arm64" }
    node_definitions = {
      for id, node in var.node_definitions : id => merge(node, { instance_type = node.role == "server" ? "t4g.medium" : "m7g.large" })
    }
  }

  assert {
    condition     = aws_instance.node["k3s-server"].instance_type == "t4g.medium" && aws_instance.node["k3s-agent1"].instance_type == "m7g.large"
    error_message = "Known Graviton families must accept an arm64 input."
  }
}


run "reject_known_architecture_mismatch" {
  command = plan

  variables {
    ami = { id = "ami-00000000000000000", architecture = "arm64" }
  }

  expect_failures = [var.node_definitions]
}


run "reject_x86_on_graviton" {
  command = plan

  variables {
    node_definitions = { k3s-server = merge(var.node_definitions["k3s-server"], { instance_type = "t4g.medium" }) }
  }

  expect_failures = [var.node_definitions]
}


run "reject_arbitrary_latest_ami" {
  command = plan

  variables {
    ami = { id = "latest", architecture = "x86_64" }
  }

  expect_failures = [var.ami]
}


run "reject_unencrypted_root" {
  command = plan

  variables {
    node_definitions = {
      k3s-server = merge(var.node_definitions["k3s-server"], {
        root_volume = merge(var.node_definitions["k3s-server"].root_volume, { encrypted = false })
      })
    }
  }

  expect_failures = [var.node_definitions]
}


run "reject_private_public_ipv4" {
  command = plan

  variables {
    node_definitions = { k3s-server = merge(var.node_definitions["k3s-server"], { subnet_key = "private" }) }
  }

  expect_failures = [var.node_definitions]
}


run "reject_missing_worker_profile" {
  command = plan

  variables {
    instance_profile_names_by_role = { server = "lab-ssm" }
  }

  expect_failures = [var.instance_profile_names_by_role]
}
