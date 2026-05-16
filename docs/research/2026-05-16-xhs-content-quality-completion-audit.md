---
title: XHS Content Quality Completion Audit
status: active
owner: ptsm
last_verified: 2026-05-16
source_of_truth: false
related_paths:
  - docs/plans/2026-05-15-xhs-content-quality-improvement.md
  - docs/development-workflow.md
  - docs/harness-engineering.md
  - docs/research/2026-05-15-xhs-content-experiment-log.md
  - docs/research/2026-05-16-xhs-dry-run-preview-review.md
---

# XHS Content Quality Completion Audit

Objective audited: follow
`docs/plans/2026-05-15-xhs-content-quality-improvement.md` under
`docs/development-workflow.md`, `docs/harness-engineering.md`, and `AGENTS.md`,
then optimize and verify the XHS content-quality system step by step.

This audit separates engineering completion from publish-experiment completion.
The current operator constraint is no real publish yet; the usable path is
dry-run generation, artifact `content_review`, and follow-up conversation edits.

## Prompt-To-Artifact Checklist

| requirement | concrete evidence | status |
| --- | --- | --- |
| Use isolated worktree/branch | `.worktrees/xhs-content-quality` on `feat/xhs-content-quality`; latest audited commit `a39053f` before this document | done |
| Read and update implementation plan | `docs/plans/2026-05-15-xhs-content-quality-improvement.md` contains the diagnosis, task list, required judge behavior, and no-review-queue scope clarification | done |
| Fix XHS evidence pipeline | `src/topic_radar/cli.py`, `src/topic_radar/output/artifacts.py`, `src/topic_radar/platforms/xiaohongshu.py`, and topic-radar tests changed in this branch; sample set recorded in `docs/research/2026-05-15-xhs-content-quality-sample-set.md` | done |
| Remove mandatory `也算` lock | `fengkuang_daily_post/playbook.yaml` uses `recommended_phrases`; reflector only enforces non-empty `must_include_phrase`; tests cover optional phrase behavior | done |
| Read account memory before drafting | `src/ptsm/agent_runtime/nodes/memory.py` injects `# Recent Account Memory`; dry-run artifacts show `runtime_context_used=["recent_account_memory"]` | done |
| Add content mechanics to runtime context | `src/ptsm/skills/runtime_context.py` renders mechanics such as `copyable_line`, `comment_chain`, and `save_tool`; `tests/unit/skills/test_runtime_context.py` covers it | done |
| Upgrade 发疯文学 prompts/skills/deterministic drafts | fengkuang planner/persona/reflection/skills require concrete object, copyable line, participation hook, safety boundary; dry-run artifact `outputs/artifacts/acct-fk-local-fengkuang_daily_post-1-96.json` passes eval | done |
| Upgrade psychology prompts/skills/deterministic drafts | psychology planner/persona/reflection/skills require micro-scene, mechanism, mini-tool, professional boundary, example prompt; dry-run artifact `outputs/artifacts/acct-psychology-local-modern_psychology_post-1-95.json` passes eval | done |
| Add deterministic content-quality contracts | `evaluation.yaml` and contract evaluators catch generic titles, missing comment/save triggers, forbidden safety terms, and meta-intent leakage | done |
| Add required LLM content-quality judge and human review | `src/ptsm/evaluations/llm_judge.py`, `src/ptsm/infrastructure/evaluations/content_quality_gate.py`, `reflector.py`, and runtime wiring make configured judge failures required retry signals; artifacts include `content_review` | done |
| Keep final human confirmation conversational, not a review UI | `docs/operations.md`, `docs/runtime.md`, `docs/observability.md`, and the plan state that `content_review` plus operator conversation is the review path | done |
| Add publish experiment runbook/log | `docs/operations/content-experiment-runbook.md` and `docs/research/2026-05-15-xhs-content-experiment-log.md` exist with variant and metric schema | done |
| Run two-week calibration batch | 12 dry-run candidate rows exist, but they are `not_published`; no 24h/72h metrics or weekly review exist | blocked by no-publish scope |
| Final harness/source-of-truth sync | `uv run pytest -q`, `docs-sync --base-ref origin/main`, and `harness-check --strict` passed in the worktree after the latest code change; docs-sync also passed after the latest review-sample doc update | done for engineering branch |
| Merge back to `main` | blocked: main worktree contains modified/untracked files, including untracked paths that overlap this branch's tracked plan/research docs | blocked by dirty main |

## Latest Dry-Run Evidence

No real XiaoHongShu publish was attempted.

### 发疯文学

- command shape: `run-playbook --publish-mode dry-run --eval`
- artifact: `outputs/artifacts/acct-fk-local-fengkuang_daily_post-1-96.json`
- title: `领导18:57发「在吗」那一秒`
- cover: `我的工牌先替我发疯`
- eval: passed, `required_failed=0`, `warning_failed=0`
- review: `content_review.status=needs_human_review`

Why it matches the plan: the draft names a concrete after-hours leader-message
scene, uses `工牌` and `群聊`, includes a `可复制疯话`, and asks the comment section
to complete a line.

### Psychology

- command shape: `run-playbook --publish-mode dry-run --eval`
- artifact: `outputs/artifacts/acct-psychology-local-modern_psychology_post-1-95.json`
- title: `会议那句话反复倒带，不是你太敏感`
- cover: `把猜测放回事实栏`
- eval: passed, `required_failed=0`, `warning_failed=0`
- review: `content_review.status=needs_human_review`

Why it matches the plan: the draft starts from a first-person meeting replay
scene, names `反刍思维`, gives a `事实 / 猜测 / 下一步` mini-tool, includes a
professional-help boundary, and asks for reader examples instead of broad opinion.

## Verification Evidence

Fresh verification performed in the worktree after the latest code change:

- `uv run pytest -q`
- `uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main`
- `uv run python -m ptsm.bootstrap harness-check --strict`

Additional verification after the latest docs-only review-sample update:

- `rg -n "Conversation Review Samples|acct-fk-local-fengkuang_daily_post-1-96|acct-psychology-local-modern_psychology_post-1-95|Generation logic|Human adjustment suggestions|Memory Follow-Up" docs/research/2026-05-16-xhs-dry-run-preview-review.md`
- `git diff --check`
- `uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main`

## Remaining Work

Task 10 remains open by design because the user asked to generate and review
before publishing. Completion requires:

- at least 12 real posts with 24h and 72h metrics;
- a weekly review identifying top 3 mechanics and bottom 3 failure patterns;
- winning mechanics converted back into prompt/eval updates.

Local merge is also blocked until the main worktree's unrelated modified and
untracked files are resolved. The branch is preserved at
`.worktrees/xhs-content-quality`.
