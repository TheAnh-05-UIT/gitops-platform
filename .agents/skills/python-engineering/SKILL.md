---
name: python-engineering
description: Change or review Flask handlers, the portal GitHub client, workload HTTP contracts, or Python deployment policy code.
---

# Python and Flask engineering

Take the affected interface and observed behavior as inputs. Return a scoped change or review with tests and contract implications.

1. Read `portal/app.py` and `portal/github_client.py` for platform work, `gitops-platform-workload-api/workload_api/app.py` for workload behavior, or `gitops-platform-config/scripts/check_deployment_policies.py` for policy. Check the owning requirements and workflow.
2. Keep HTTP, integration and business logic at existing boundaries. Follow PEP 8, validate inputs, handle expected failures deliberately, and keep tokens and sensitive request data out of logs. Preserve response codes and probe semantics.
3. Reproduce bugs with a regression test. Use Flask's test client with mocked GitHub calls and use rendered manifest fixtures for policy changes.
4. Run the relevant [validation](../../../docs/TESTING.md). Check both sides of every changed interface. Record blocked dependencies and external checks.
