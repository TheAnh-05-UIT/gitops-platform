---
name: security-review
description: Perform defensive review of the portal trust boundary, GitHub permissions, container supply chain, rendered deployment or infrastructure exposure.
---

# Defensive security review

Take the review scope and affected identities as inputs. Return source-backed findings with impact, owner, remediation and unverified assumptions.

1. Read the [security baseline](../../../docs/SECURITY.md). Trace authentication, authorization and CSRF separately in `portal/app.py`. Review privileged mutations in `portal/github_client.py` and both hosted workflows' permissions.
2. Review inputs, error handling, retries, Docker identity, dependency trust, image publication and rendered pod permissions. For infrastructure, inspect declared network exposure and credential handling using source.
3. Verify findings with focused static checks or safe local tests. Keep credential values, state, plans and sensitive logs private. Report missing live permissions or required-check evidence explicitly.
