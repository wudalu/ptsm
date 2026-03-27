## Shared Contracts

This directory holds design-time shared contracts that are not yet wired into the
current runtime loader in `src/ptsm/playbooks/`.

The templates here assume:

- a single super agent
- user-defined skills
- runtime skill selection by capability and contract, not by fixed skill id
- explicit phase policy, approval gates, and verification rules

Use these files as reference templates when defining future playbook policies.

Contents:

- `skill_manifest.template.yaml`
  Minimal metadata contract for user-defined skills.
- `planning/planning_brief.schema.yaml`
  Runtime-to-planner input contract for one planning step.
- `planning/plan_output.schema.yaml`
  Planner-to-runtime output contract for a structured executable plan.
- `playbook_policies/base.single_agent_skills.template.yaml`
  Generic capability-based skeleton.
- `playbook_policies/research_synthesis.policy.yaml`
  Research, reading, synthesis, and citation flow.
- `playbook_policies/content_drafting.policy.yaml`
  Draft, reflect, revise, and optional publish flow.
- `playbook_policies/code_change_verification.policy.yaml`
  Inspect, edit, test, and summarize flow.
- `playbook_policies/external_action_approval.policy.yaml`
  Action-oriented flow with strict human approval for risky writes.
