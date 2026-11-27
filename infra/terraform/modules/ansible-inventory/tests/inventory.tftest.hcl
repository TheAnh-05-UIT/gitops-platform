variables {
  environment       = "lab"
  aws_region        = "us-east-1"
  availability_zone = "us-east-1a"
}

run "minimal_inventory" {
  command = plan

  variables {
    lab_profile = "minimal"
    nodes       = jsondecode(file("tests/fixtures/minimal.json")).nodes
  }

  assert {
    condition     = jsonencode(output.ansible_inventory) == jsonencode(jsondecode(file("tests/fixtures/minimal.json")))
    error_message = "Profile minimal must produce the version 1 fields and sorted groups in the fixture."
  }
}

run "multi_node_inventory" {
  command = plan

  variables {
    lab_profile = "multi-node"
    nodes       = jsondecode(file("tests/fixtures/multi-node.json")).nodes
  }

  assert {
    condition     = jsonencode(output.ansible_inventory) == jsonencode(jsondecode(file("tests/fixtures/multi-node.json")))
    error_message = "Profile multi-node must produce the version 1 fields and sorted groups in the fixture."
  }
}

run "private_inventory" {
  command = plan

  variables {
    lab_profile = "private"
    nodes       = jsondecode(file("tests/fixtures/private.json")).nodes
  }

  assert {
    condition     = jsonencode(output.ansible_inventory) == jsonencode(jsondecode(file("tests/fixtures/private.json")))
    error_message = "Profile private must produce the version 1 fields and sorted groups in the fixture."
  }
}

run "reject_duplicate_addresses" {
  command = plan

  variables {
    lab_profile = "multi-node"
    nodes = merge(jsondecode(file("tests/fixtures/multi-node.json")).nodes, {
      k3s-agent1 = merge(jsondecode(file("tests/fixtures/multi-node.json")).nodes["k3s-agent1"], {
        private_ip = "10.20.1.10"
      })
    })
  }

  expect_failures = [var.nodes]
}

run "reject_missing_first_worker" {
  command = plan

  variables {
    lab_profile = "private"
    nodes = {
      for name, facts in jsondecode(file("tests/fixtures/private.json")).nodes : name => facts
      if name != "k3s-agent1"
    }
  }

  expect_failures = [var.nodes]
}

run "reject_public_ip_on_private_node" {
  command = plan

  variables {
    lab_profile = "private"
    nodes = merge(jsondecode(file("tests/fixtures/private.json")).nodes, {
      k3s-server = merge(jsondecode(file("tests/fixtures/private.json")).nodes["k3s-server"], {
        public_ip = "192.0.2.10"
      })
    })
  }

  expect_failures = [var.nodes]
}

run "reject_mismatched_az" {
  command = plan

  variables {
    lab_profile = "minimal"
    nodes = {
      k3s-server = merge(jsondecode(file("tests/fixtures/minimal.json")).nodes["k3s-server"], {
        availability_zone = "us-east-1b"
      })
    }
  }

  expect_failures = [var.nodes]
}

run "reject_ipv6_address" {
  command = plan

  variables {
    lab_profile = "minimal"
    nodes = {
      k3s-server = merge(jsondecode(file("tests/fixtures/minimal.json")).nodes["k3s-server"], {
        private_ip = "2001:db8::"
      })
    }
  }

  expect_failures = [var.nodes]
}

run "reject_unexpected_placement_label" {
  command = plan

  variables {
    lab_profile = "multi-node"
    nodes = merge(jsondecode(file("tests/fixtures/multi-node.json")).nodes, {
      k3s-server = merge(jsondecode(file("tests/fixtures/multi-node.json")).nodes["k3s-server"], {
        simulated_region = "ap-southeast-1"
      })
    })
  }

  expect_failures = [var.nodes]
}
