---
title: XHS Content Experiment Runbook
status: active
owner: ptsm
last_verified: 2026-07-23
source_of_truth: true
related_paths:
  - docs/research/2026-05-15-xhs-content-experiment-log.md
  - docs/plans/2026-05-15-xhs-content-quality-improvement.md
  - src/ptsm/application/use_cases/xhs_post_metrics.py
  - src/ptsm/domain/psychology_learning.py
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
5. Confirm the planned image format in `content_review.image_plan`, `content_review.image_form`, or `image_generation.image_plan` when the run generated an image.
6. Record the planned variant and image format in `docs/research/2026-05-15-xhs-content-experiment-log.md`.

Variant labels are operator metadata. They can be written in the experiment log or used while planning, but final正文 must not contain `变体要求`, `comment_chain`, `save_tool`, or `identity_conflict`; the playbook eval contracts treat those as instruction leakage.

When generating several variants for the same account and playbook, keep each returned `artifact_path`. Artifact storage appends a numeric suffix when a run key already exists, so repeated dry-runs should produce separate files instead of overwriting earlier candidates.

For XHS copy experiments, reject variants whose title is only a category label such as `日常`, `实录`, or `干货分享`; use the playbook’s concrete-entry rule rather than inserting a universal tension keyword. The final正文 follows `xhs_compact_native_v1`: 2–4 short beats with a scene/human anchor, one usable domain detail, and a natural save or reply opening. Save and comment intent may share one sentence; do not turn them into four labelled moves. Keep candidates inside their compact playbook body band before considering publish.

For `modern_psychology_post`, do not reuse six near-identical "反复复盘一句话" scenes. The deterministic fallback now separates meeting replay, boundary pressure, Sunday work-message anxiety, after-work message pullback, brain-in-review-meeting, and ordinary-reply replay. A calibration batch should keep those scene mechanics distinct before publishing.

For `modern_psychology_post --psychology-content-mode learning_series`, this rule is stricter: a variant is one confirmed catalog lesson, not a rewritten free scene or a made-up next lesson. The controlled renderer gives each selected lesson its own catalog-approved title and cover hook, then fixes its body, tags, and catalog-owned image plan; do not hand-edit them or add `--local-image-style` as an experiment. Compare lessons only after a reviewed catalog/version change, and keep the returned series/lesson identity fixed. Do not infer a reader's course progress from previous artifacts, and do not use hotspot text as lesson evidence.

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
- image format used, such as provider image, `note_card`, `iphone_notes`, or `wechat_chat`
- comment quality notes
- next rewrite decision

Use the same score proxy from topic-radar triage:

```text
interaction_score = likes + collects*2 + comments*4 + shares*6
interaction_rate = interaction_score / views
```

Record the numbers through the local metrics loop instead of only writing free-form notes:

```bash
uv run python -m ptsm.bootstrap xhs-record-metrics \
  --artifact outputs/artifacts/<artifact>.json \
  --checkpoint 24h \
  --views 1000 \
  --likes 80 \
  --collects 60 \
  --comments 8 \
  --shares 2 \
  --decision keep \
  --notes "collects close to likes"
```

For psychology readouts, compare the confirmed PTSM direction ids and image styles:

```bash
uv run python -m ptsm.bootstrap xhs-metrics-report \
  --playbook-id modern_psychology_post \
  --checkpoint 24h \
  --group-by topic_direction_id

uv run python -m ptsm.bootstrap xhs-metrics-report \
  --playbook-id modern_psychology_post \
  --checkpoint 24h \
  --group-by image_style

uv run python -m ptsm.bootstrap xhs-metrics-report \
  --playbook-id modern_psychology_post \
  --checkpoint 24h \
  --group-by psychology_learning_series_id

uv run python -m ptsm.bootstrap xhs-metrics-report \
  --playbook-id modern_psychology_post \
  --checkpoint 24h \
  --group-by psychology_learning_curriculum_version

uv run python -m ptsm.bootstrap xhs-metrics-report \
  --playbook-id modern_psychology_post \
  --checkpoint 24h \
  --group-by psychology_learning_lesson_id
```

The metrics store is `outputs/artifacts/xhs-post-metrics/metrics.jsonl`. Learning rows carry `psychology_learning_series_id`, `psychology_learning_curriculum_version`, and `psychology_learning_lesson_id` only after the closed receipt is revalidated. Re-recording the same artifact/checkpoint replaces the old measurement, so a correction cannot inflate the cohort. Learning reports exclude ordinary psychology rows and mark any group with fewer than 3 posts as `needs_more_data`. Treat these as early signals, not proof that a direction, lesson or cover style wins.

## Readout Rules

- `comment_chain` wins only if comments contain user examples or completions, not just “哈哈哈”.
- `save_tool` wins only if collects grow faster than likes or readers mention saving/screenshotting.
- `identity_conflict` wins only if shares/comments show “this is me” recognition.
- Image format changes should be read separately from正文 mechanics. A strong正文 with a weak cover is `revise_hook`; a strong cover with low saves/comments is usually `revise_mechanic`.
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
