# ADR 0003. Single-AZ K3s lab profiles on AWS

**Status** P1.5 implements independent state bootstrap and native locking. Live target, profile and spend require owner approval.

## Context

The platform needs repeatable cloud networking, Linux automation and Kubernetes scheduling exercises at lab cost. The current draft has one public subnet and three EC2 nodes. The HTTP app, chart and placement should continue to work with a reviewed baseline.

## Decision

Use one profile and common modules per environment. Start deployment with B, one server and one worker. The final demonstration uses B with a second worker, for three EC2 instances in the same single-AZ topology. Nodes use public IPv4 for egress and private addresses for cluster traffic. All profiles require SSM, deny public SSH and Kubernetes API access, and start without managed load balancing. [Lab topology and cost profiles](../AWS_LAB_DESIGN.md)

Use independently bootstrapped versioned S3 with SSE-S3, TLS and native `use_lockfile`. Use one state bucket and distinct key per environment, retain past versions and use dedicated Terraform and recovery roles. Keep bootstrap state local and protected outside the bucket it creates. Lab teardown retains the bucket until an independent owner gate authorizes decommissioning. [State owner runbook](../TERRAFORM_STATE_RUNBOOK.md)

Use explicit per-instance public IPv4 assignment on the public subnet. Role SG references allow the selected K3s features. Outbound TCP 80/443 supports package mirrors, SSM and rotating Git/registry destinations. Application ingress uses restricted CIDRs and explicit A/B node roles. Before dedicated ingress, demonstrate the ClusterIP service through SSM. [Implemented traffic matrix](../../infra/terraform/README.md#network-traffic-matrix)

Use one EC2-only role and shared profile because server and worker SSM needs are identical. Attach only `AmazonSSMManagedInstanceCore`. Terraform leaves host bootstrap to the approved AMI and Ansible. Require IMDSv2 at hop limit 1 and encrypted gp3 roots. Retention, node replacement and managed policy changes require owner review. [Compute and IAM decisions](../../infra/terraform/README.md#compute-security-and-storage)

## Alternatives and consequences

- A runs one K3s server and no workers, with the same public-subnet egress as B. It minimizes EC2, disk and IPv4 count. Multi-node scheduling exercises require B or C.
- B avoids NAT Gateway charges and supports multi-node scheduling. It still pays for public IPv4 on each node and requires review of inbound exposure.
- C runs one server and one or two workers without public IPs. A public NAT Gateway in the same AZ is required and explicitly opted in. Include NAT hours, traffic processing and its public IPv4 in the budget. Endpoints-only egress would require approved mirrors or another verified path to public artifacts.
- A load balancer, more AZs and EKS are separate decisions. Each lab profile has a single server and AZ. Approve cost, retention and teardown before live use.
