---
title: XHS Content Experiment Runbook
status: active
owner: ptsm
last_verified: 2026-05-16
source_of_truth: true
related_paths:
  - docs/research/2026-05-15-xhs-content-experiment-log.md
  - docs/plans/2026-05-15-xhs-content-quality-improvement.md
  - src/ptsm/playbooks/definitions
  - src/ptsm/skills/builtin
  - outputs/artifacts
---

# XHS Content Experiment Runbook

Use this runbook to test content mechanics. It is separate from real publish mechanics: a post can publish successfully and still fail the experiment.

## Variant Types

Run each topic as one of three variants:

- `comment_chain`: optimized for comments and UGC completion. The post must ask readers to complete, rewrite, or submit an example.
- `save_tool`: optimized for collects, screenshots, and reuse. The post must include a mini-tool, template, checklist, phrase, or reusable line.
- `identity_conflict`: optimized for recognition and sharing. The post must name a clear identity tension, such as “下班了但脑子还在工位”.

## Before Publishing

1. Pick one playbook and one scene.
2. Assign exactly one variant type.
3. Generate the draft with `--eval`.
4. Confirm deterministic eval has `required_failed = 0`.
5. Record the planned variant in `docs/research/2026-05-15-xhs-content-experiment-log.md`.

Variant labels are operator metadata. They can be written in the experiment log or used while planning, but final正文 must not contain `变体要求`, `comment_chain`, `save_tool`, or `identity_conflict`; the playbook eval contracts treat those as instruction leakage.

When generating several variants for the same account and playbook, keep each returned `artifact_path`. Artifact storage appends a numeric suffix when a run key already exists, so repeated dry-runs should produce separate files instead of overwriting earlier candidates.

Example:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "领导18:57突然发来一句在吗，明天早会还要我补材料" \
  --account-id acct-fk-local \
  --playbook-id fengkuang_daily_post \
  --eval
```

## Metrics To Record

Record metrics at `2h`, `24h`, and `72h` after publish:

- views
- likes
- collects
- comments
- shares
- comment quality notes
- next rewrite decision

Use the same score proxy from topic-radar triage:

```text
interaction_score = likes + collects*2 + comments*4 + shares*6
interaction_rate = interaction_score / views
```

## Readout Rules

- `comment_chain` wins only if comments contain user examples or completions, not just “哈哈哈”.
- `save_tool` wins only if collects grow faster than likes or readers mention saving/screenshotting.
- `identity_conflict` wins only if shares/comments show “this is me” recognition.
- A losing variant is still useful when the failed mechanic is clear.

## First Calibration Thresholds

- 24h views beat the recent account median by 50%.
- 24h `interaction_rate` improves over the recent account median.
- Comments contain usable examples for the next prompt update.
- Psychology `save_tool` variants should show collects close to or above likes.

## Rewrite Decisions

Use one of these decisions after the `72h` readout:

- `keep`: repeat the mechanic with a new scene.
- `revise_hook`: title/cover did not earn the click.
- `revise_mechanic`: readers clicked but did not comment/save/share as intended.
- `drop`: topic or mechanic repeatedly underperforms.

Do not update prompts/evals from one post. Wait for at least three comparable variants unless the failure is a clear safety or platform-format problem.
