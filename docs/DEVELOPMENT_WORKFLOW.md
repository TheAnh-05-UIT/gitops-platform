# Development workflow

1. Start Codex in the coordinating directory for cross-repo work or at the owning repository root for a focused task. Read the applicable instructions and choose a skill from `gitops-platform/.agents/skills/`.
2. Check status, branch, and existing changes in all affected checkouts. Establish the source-of-truth revision for each contract. A local `origin/main` is a cached reference. Refresh only when network use is authorized and needed.
3. Outline the smallest change and its verification. For a multi-repo change, record owning repositories, compatibility milestones, merge order and rollback. Publish artifacts before promoting their references. Keep existing values or support both interfaces during staged migrations.
4. Implement and validate locally. Review staged, unstaged and new files separately and compare cross-repo contracts. Update [project state](PROJECT_STATE.md) when evidence changes and add an ADR when a material decision is made.
5. With explicit authorization, open scoped PRs to the appropriate repository. Include observed validation, contract impact, links to dependent PRs and a rollback plan. Suggest Conventional Commit messages. Respect required review, branch checks and owner permissions.
6. For an authorized rollout, confirm checks, merge desired state, then observe Argo CD revision, health and sync, the Deployment rollout, image identity and endpoint health. Roll back by reverting the desired-state change through Git and observing reconciliation to the known-good revision.

## Codex instruction and skill discovery

- The [workspace policy](WORKSPACE_POLICY.md), docs directory and [skills directory](../.agents/skills/) are maintained in Platform. The parent is a non-Git coordinator. Its `AGENTS.md` and legacy documentation links route to the canonical files.
- The current workflow uses manual loading. From the workspace parent, read the affected repository's `AGENTS.md` and `gitops-platform/.agents/skills/<name>/SKILL.md`. From Platform, use `.agents/skills/<name>/SKILL.md`. From a sibling, use `../gitops-platform/.agents/skills/<name>/SKILL.md` when Platform is present. Standalone checkouts carry local safety and validation guidance, and share contract changes with sibling owners.
- Codex documents Git-root-bounded discovery. Automatic discovery in this workspace remains unverified. To check a fresh CLI, inspect `/skills` and use `codex debug prompt-input "Instruction discovery check"` in the selected root. Keep raw prompts private. See [project state](PROJECT_STATE.md) for the diagnostic limitation.

See the official guidance for [AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance) and [local skill discovery](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills).

## Promotion planning

Use the [image promotion design](IMAGE_PROMOTION.md) for the proposed admission and rollback procedure. P0.3 requires explicit implementation approval. Recheck the actual source and config heads, image visibility and digest, protected-branch rules, and authorized lab before enabling writes. Follow the design's fail-closed behavior while those dependencies are unresolved.
