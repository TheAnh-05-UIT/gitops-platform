---
name: repository-analysis
description: Trace ownership, entry points, dependencies and compatibility across the portal, config and workload repositories for discovery or architecture review.
---

# Repository and architecture analysis

Use for onboarding, uncertain ownership, cross-repo impact analysis, or reviewing a boundary change. Take the task, affected checkouts and baseline refs as inputs. Return an ownership map, source evidence, compatibility impact and verification gaps.

1. Resolve checkout roots and read the workspace and repository AGENTS.md files. Inspect status, relevant refs and tracked paths without updating branches or reading secrets. Use [architecture](../../../docs/ARCHITECTURE.md) to locate entry points.
2. Trace both sides of affected interfaces. Start with gitops-platform/portal/github_client.py, gitops-platform-config/apps/workload-api/values.yaml and gitops-platform-workload-api/.github/workflows/ci.yml. Check whether the selected branch, local main and cached origin/main represent different contracts.
3. For a boundary change, identify ownership, privilege, failure recovery and tradeoffs. Record migration order, compatibility windows and rollback before implementation.
4. Distinguish code evidence, locally reproduced behavior and external evidence. Record gaps when a sibling checkout or live service is unavailable. Follow the validation links from the architecture before concluding.
