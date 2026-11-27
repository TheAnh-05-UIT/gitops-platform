output "vpc_id" {
  description = "ID of the lab IPv4 VPC."
  value       = aws_vpc.lab.id
}

output "vpc_cidr" {
  description = "IPv4 CIDR of the lab VPC."
  value       = aws_vpc.lab.cidr_block
}

output "subnet_ids" {
  description = "Subnet IDs keyed by role. The private key is present only in C."
  value       = tomap({ for role, subnet in aws_subnet.lab : role => subnet.id })

  # Compute can use the role map without racing subnet routing setup.
  depends_on = [aws_route.public_default, aws_route.private_default, aws_route_table_association.subnet]
}

output "public_subnet_id" {
  description = "Public subnet ID."
  value       = aws_subnet.lab["public"].id
}

output "private_subnet_id" {
  description = "Private subnet ID in C, null in A/B."
  value       = try(aws_subnet.lab["private"].id, null)
}

output "route_table_ids" {
  description = "Route table IDs keyed by subnet role."
  value       = tomap({ for role, table in aws_route_table.lab : role => table.id })
}

output "public_route_table_id" {
  description = "Public subnet route table ID."
  value       = aws_route_table.lab["public"].id
}

output "private_route_table_id" {
  description = "Private subnet route table ID in C, null in A/B."
  value       = try(aws_route_table.lab["private"].id, null)
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway attached to the lab VPC."
  value       = aws_internet_gateway.lab.id
}

output "nat_gateway_id" {
  description = "ID of the zonal public NAT Gateway in C, null in A/B."
  value       = try(aws_nat_gateway.egress["private"].id, null)
}

output "availability_zone" {
  description = "Single AZ shared by both subnets when present."
  value       = var.network_topology.availability_zone
}

output "lab_profile" {
  description = "Selected profile key."
  value       = var.network_topology.lab_profile
}

output "node_subnet_key" {
  description = "Subnet role selected for all Kubernetes nodes."
  value       = var.network_topology.node_subnet
}

output "node_subnet_id" {
  description = "ID of the subnet assigned to the nodes after its routing is ready."
  value       = try(aws_subnet.lab[var.network_topology.node_subnet].id, null)

  depends_on = [aws_route.public_default, aws_route.private_default, aws_route_table_association.subnet]
}

output "expected_egress" {
  description = "Expected node IPv4 egress gateway type."
  value       = var.network_topology.egress
}

output "topology" {
  description = "Selected topology, including the explicit compute IPv4 association intent."
  value       = var.network_topology
}
