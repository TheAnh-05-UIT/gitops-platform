# ADR 0001. Repository and GitOps boundaries

**Status** Accepted as a record of the existing project boundary.

## Context

Application development, placement planning and deployment configuration have distinct review and privilege needs. The existing Workload CI publishes an image. The Portal proposes placement edits to configuration. Argo CD consumes config `main`.

## Decision

Keep the three repositories independent and the parent directory outside Git. Own image builds and publication in the workload repository, desired state and deployment gates in the configuration repository, and placement logic and future environment provisioning automation in the platform repository. A change to an image or placement reaches the managed workload through reviewed configuration history.

## Consequences

Artifact publication can succeed while the deployed config retains an older image. An explicit promotion decision and evidence are required. Workload, chart and optimizer contract changes may require coordinated merge order. A Git revert can restore the previous desired state if its image and target capacity remain available. The Platform repository now owns the [shared policy](../WORKSPACE_POLICY.md), engineering docs and skills. The non-Git parent has a lightweight entry point. Repository-specific instructions cover direct launches.
