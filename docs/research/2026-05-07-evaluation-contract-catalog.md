# Evaluation Contract Catalog

Date: 2026-05-07

This catalog is the source of truth for which PTSM outputs are worth evaluating and which layer owns each constraint. It answers four questions for every contract: owner, scope, enforcement, and gate_level.

## Contract Families

| Contract Family | Owner | Purpose | First Gate Level |
| --- | --- | --- | --- |
| `eval_target.v1` | shared evaluation | Normalize what gets scored | required |
| `eval_result.v1` | shared evaluation | Normalize scores, labels, evidence, confidence, cost | required |
| `eval_suite.v1` | shared evaluation | Bind evaluators to scope and thresholds | required |
| `playbook_evaluation.v1` | playbook-local | Define phase contracts for one playbook | required for migrated playbooks |
| `runtime_state_phase.v1` | shared runtime | Define expected state fields after each phase | required |
| `final_content.v1` | shared content with playbook overrides | Define common title/body/image_text/hashtags shape | required |
| `artifact.v1` | shared observability | Define persisted artifact completeness and run links | required |
| `skill_activation.v1` | shared skill/runtime | Define activated skill and runtime context traceability | required |
| `reflection_decision.v1` | shared runtime plus playbook overrides | Define allowed decisions and retry/finalize invariants | required |
| `image_generation.v1` | image infrastructure | Define generated image metadata and file evidence | warning initially |
| `publish_attempt.v1` | publisher/application | Define publish payload/result/idempotency evidence | required for real publish |
| `post_publish_check.v1` | publisher/application | Define status verification and manual-check fallbacks | warning initially |
| `eval_dataset_case.v1` | evaluation datasets | Define offline eval case input/expected/rubric refs | experimental initially |
| `human_review_item.v1` | evaluation review | Define manual review queue item and labels | experimental initially |

## Implementation Priority

1. Shared evaluator infrastructure contracts: `eval_target.v1`, `eval_result.v1`, `eval_suite.v1`
2. Existing runtime evidence contracts: `artifact.v1`, `skill_activation.v1`, `final_content.v1`
3. Playbook-local phase contracts: `playbook_evaluation.v1` for one pilot playbook
4. Safety/side-effect contracts: `publish_attempt.v1`, `post_publish_check.v1` (designed, implemented later)
5. Offline dataset and human review contracts: designed now, implemented later

## Schema Template Locations

All canonical contract schema templates live under `shared_contracts/evaluation/`:

- `eval_target.schema.yaml`
- `eval_result.schema.yaml`
- `eval_suite.schema.yaml`

Runtime evidence contracts:

- `artifact.schema.yaml`
- `final_content.schema.yaml`
- `skill_activation.schema.yaml`

Additional schemas will be created as the implementation progresses through later phases.

## Gate Level Definitions

- `required`: CI/local gate must pass
- `warning`: shown in reports, does not block
- `manual_review`: routed to human review queue
- `experimental`: logged only, not in aggregates

## Rollout Rules

- Phase 1 is deterministic-only (rule + contract evaluators)
- No LLM judge blocks `harness-check` until human agreement is measured
- Every evaluator must have an owner, version, scope, and gate level
- Every failed required evaluator must include evidence paths or JSON pointers
