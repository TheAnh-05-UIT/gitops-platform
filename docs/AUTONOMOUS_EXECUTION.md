# Autonomous execution

Implement the approved roadmap across the three existing checkouts. Begin with the current [execution log](EXECUTION_LOG.md), [roadmap](ROADMAP.md), repository instructions and actual Git state. Use existing modules and contracts. Routine offline work advances automatically after implementation, validation, review and correction.

For each cycle, record an acceptance test, run focused checks, review the complete scoped diff, run regression at the milestone boundary and record evidence. Keep code state and live evidence separate. [Quality gates](QUALITY_GATES.md)

Only the owner runs AWS operations. This includes authentication, reads, real backend initialization or Terraform plans, remote scripts, SSM, AWS Kubernetes and indirect execution. Use empty local credentials and AWS mocks where applicable. An external gate blocks that operation. Continue independent offline work. Hosted publication, promotion, preview, repository settings, push, remote PR, merge and external deployment require their own authorization. Keep the current freeze and disabled hosted gates. [Manual AWS gates](MANUAL_AWS_GATES.md)

Use explicit file or hunk staging for safe local Conventional Commits on feature branches. Review the entire Terraform milestone before its checkpoint. Leave ambiguous mixed work and unsafe ancestry in place, recording the exact blocker. Preserve the parent as a non-Git directory and retain existing drafts, refs and review worktrees. Bilingual PR drafts are review artifacts until authorized for publication.

Use independent reviewers for disjoint scopes. Record unresolved external or environment-dependent outcomes and resume from the next eligible task. Complete only after the offline definition of done and [final review](FINAL_REVIEW.md) are supported by evidence.
