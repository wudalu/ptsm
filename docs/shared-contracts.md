---
title: PTSM Shared Contracts
status: active
owner: ptsm
last_verified: 2026-04-17
source_of_truth: true
related_paths:
  - shared_contracts/README.md
  - shared_contracts/planning
  - shared_contracts/playbook_policies
  - shared_contracts/skill_manifest.template.yaml
---

# Shared Contracts

`shared_contracts/` 保存的是设计期共享契约模板，当前并不等于“已经接入运行时的稳定 API”。

## Entry Point

- 总览: [`shared_contracts/README.md`](../shared_contracts/README.md)

## Planning Schemas

- planning brief: [`shared_contracts/planning/planning_brief.schema.yaml`](../shared_contracts/planning/planning_brief.schema.yaml)
- plan output: [`shared_contracts/planning/plan_output.schema.yaml`](../shared_contracts/planning/plan_output.schema.yaml)

## Policy Templates

- base skeleton: [`shared_contracts/playbook_policies/base.single_agent_skills.template.yaml`](../shared_contracts/playbook_policies/base.single_agent_skills.template.yaml)
- content drafting: [`shared_contracts/playbook_policies/content_drafting.policy.yaml`](../shared_contracts/playbook_policies/content_drafting.policy.yaml)
- research synthesis: [`shared_contracts/playbook_policies/research_synthesis.policy.yaml`](../shared_contracts/playbook_policies/research_synthesis.policy.yaml)
- code verification: [`shared_contracts/playbook_policies/code_change_verification.policy.yaml`](../shared_contracts/playbook_policies/code_change_verification.policy.yaml)
- external approval: [`shared_contracts/playbook_policies/external_action_approval.policy.yaml`](../shared_contracts/playbook_policies/external_action_approval.policy.yaml)

## Skill Metadata Template

- [`shared_contracts/skill_manifest.template.yaml`](../shared_contracts/skill_manifest.template.yaml)

这些文件更适合被当成未来平台化扩展的模板，而不是当前 loader 已经消费的事实来源。
