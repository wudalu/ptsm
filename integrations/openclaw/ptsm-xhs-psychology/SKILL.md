---
name: ptsm-xhs-psychology
description: 当用户想发布、复盘或优化小红书心理学、情绪、关系边界、焦虑、内耗、自我关怀、睡眠恢复、AI 陪伴类内容，或想提高相关内容浏览/点赞时，先调用 PTSM 心理学选题引导或指标复盘入口。
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# PTSM XHS Psychology

Use this skill when the user asks OpenClaw to create, prepare, draft, save, publish, review, or optimize a Xiaohongshu post in the psychology domain. Common triggers include 心理学、情绪、焦虑、内耗、边界感、关系、自我关怀、孤独、比较焦虑、睡眠恢复、轻养生、办公室恢复、AI 陪伴, 提高浏览量、提高点赞、数据复盘, and similar wording.

For non-psychology XHS playbooks, use `ptsm-xhs-topic-guide`; this file remains the psychology-specific wrapper.

## Psychology Learning Series

When the user explicitly asks for a psychology learning series, a study topic,
or a specific lesson, use the `learning_series` path instead of the generic
scene flow. There are two valid catalog sources: builtin
`after_work_rumination`, and an immutable `user_confirmed` curriculum that PTSM
created after proposal review. Never turn a scene, hotspot, or operator idea
directly into a runnable lesson.

### Custom topic and outline

1. Let the user provide a safe topic and, if useful, a 2–6 item JSON outline.
Each item may have `id`, `title`, and optional `goal`. Use PTSM to create a
proposal; it is review material, not a runnable catalog.

```bash
uv run python -m ptsm.bootstrap plan-psychology-series \
  --topic "下班后如何把工作从脑子里放下" \
  --curriculum-outline-file outline.json \
  --format json
```

2. Show the safe returned review, roadmap/publication order, `proposal_id`, and
exact `proposal_fingerprint`. Do not create a lesson, rewrite order, or invent
course evidence while the proposal is unconfirmed. Ask for exact confirmation.

```bash
uv run python -m ptsm.bootstrap confirm-psychology-series \
  --proposal-id "<returned proposal_id>" \
  --proposal-fingerprint "<returned proposal_fingerprint>" \
  --confirm \
  --format json
```

Confirmation creates a `user_confirmed` immutable curriculum version. A changed
topic, outline, lesson identity, or order requires a new proposal and version;
do not use catalog-root flags or hand-edit PTSM files.

3. Query the confirmed roadmap without a lesson. Show its returned
`series.roadmap`, `publication_plan`, `recommended_next_lesson`, and
`operator_content_production` only. The recommendation is not an auto-selection:
it is a publication suggestion, PTSM never auto-selects/generates a lesson, and
the progress is not reader learning progress.

```bash
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id "<returned series_id>" \
  --non-interactive \
  --format json
```

4. Ask the user to choose one returned lesson. A non-recommended lesson is
allowed, but a custom selection must send the returned explicit frozen curriculum version
back to `guide-post`; do not silently pick the recommended lesson.

```bash
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id "<returned series_id>" \
  --psychology-lesson-id "<chosen lesson_id>" \
  --psychology-curriculum-version "<returned curriculum_version>" \
  --non-interactive \
  --format json
```

5. Generate only after exact lesson confirmation. Pass the catalog IDs and the
matching returned direction id; omit `--scene`, never add
`--fresh-topic-research`, and do not append `--local-image-style` or
`--publish-image-path`. A safe completed artifact with strict receipt may update
operator content-production progress (dry-run or content success followed by
publish failure can count); preflight/workflow/eval/final-artifact failure cannot.
PTSM never auto-publishes.

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --caller openclaw \
  --guidance-ack \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --psychology-content-mode learning_series \
  --psychology-series-id "<returned series_id>" \
  --psychology-lesson-id "<chosen lesson_id>" \
  --psychology-curriculum-version "<returned curriculum_version>" \
  --topic-direction-id "<matching returned direction id>" \
  --publish-mode dry-run
```

Use `eval-artifact --artifact <path>` to audit the completed artifact. A missing
or tampered custom catalog/receipt must fail closed; do not expose proposal topic,
outline goal, source, URL, or local path.

### Builtin catalog

For `after_work_rumination`, ask PTSM for the catalog roadmap:

```bash
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id modern_psychology_post \
  --account-id acct-psychology-local \
  --psychology-content-mode learning_series \
  --psychology-series-id after_work_rumination \
  --non-interactive \
  --format json
```

Show only the returned `series.roadmap` and `topic_guidance.directions`. Label
each returned direction as `learning_series_lesson` and the selection policy as
`catalog_learning_series`. Ask the user to choose one returned lesson; do not
invent a seventh lesson or substitute a free scene. The roadmap is intentionally
`selection_required`: it has no `run-playbook` command，PTSM 不会默认生成第一课。

If the user chooses a lesson, call `guide-post` again with its returned
`lesson_id` and returned curriculum version, then show the selected direction and
image recommendation. Do not expose `source_refs`, raw research, URLs, or
course-contract JSON. The selected response owns the catalog-owned image plan
and approved title/cover hook.

If PTSM returns `topic_guidance_required`, display the returned catalog lesson
directions and wait for the user's exact lesson confirmation before retrying
with `--guidance-ack`.

## Required Flow

1. Call PTSM guidance first. Do not write or publish the post before this step.

```bash
uv run python -m ptsm.bootstrap guide-post \
  --scene "<user request or concrete scene>" \
  --non-interactive \
  --format json
```

2. Show the user only the returned `topic_guidance.directions`: direction name, `direction_type`, `scene_fit`, trend signal, viral hook, why it may work, best scenes, content angle, saveable tool, comment prompt, avoid note, and each direction's `format_recommendation` fields: `format_archetype`, `cover_role`, `body_shape`, `visual_evidence_need`, and `avoid_format`. When returned direction(s) have `direction_type: open_scene`, label them as PTSM-returned open_scene exploration directions.

PTSM may return sleep recovery / light-wellness directions such as 睡眠恢复、轻养生、办公室恢复 as a PTSM-returned psychology sublane. Display them exactly like other returned psychology directions; do not turn them into a separate non-psychology playbook or add unreturned wellness advice.

PTSM may also return growth-oriented psychology direction hypotheses such as `relationship_mixed_signal_camp_vote`, `social_battery_cancel_plan_boundary`, and `after_hours_message_body_alarm`. Display them exactly as PTSM-returned directions with their saveable tool and A/B or A/B/C comment prompt; do not describe them as proven uplift until real post metrics support that.

3. Ask the user to choose one direction, or pick the best matching direction when the user has already given a clear scene.

If the user changes the scene, call `guide-post` again with the new scene. Do not reuse previous directions for a different scene.

4. After the topic direction is chosen or confirmed, show only that direction's returned `format_recommendation`: `format_archetype`, `cover_role`, `body_shape`, `visual_evidence_need`, and `avoid_format`. Treat it as the body/cover/comment structure constraint for generation; do not add extra format archetypes, wellness advice, or replace it with generic dense text poster guidance.

5. Then show only the returned `topic_guidance.image_recommendation`: `recommended_backend`, `local_style`, `provider`, `model`, `role`, `text_density`, `max_text_units`, `reason`, `command_hint`, and `fallback`.

If `recommended_backend` is `provider_image`, describe it as an LLM/provider image recommendation and use the returned `provider` and `model`. If `recommended_backend` is `local_social_screenshot`, describe the returned local style such as `wechat_chat`, `iphone_notes`, or `note_card`. Do not add extra image styles, providers, or model names.

6. Generate through PTSM only after the direction is chosen or confirmed. Pass the chosen direction's id as `--topic-direction-id`.

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --caller openclaw \
  --guidance-ack \
  --scene "<confirmed psychology direction and concrete scene>" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --topic-direction-id "<chosen direction id>" \
  --publish-mode dry-run
```

7. Real publishing requires the user's explicit publish intent and the normal PTSM publish flags. Prefer dry-run first.

8. If the user asks to improve views/likes, review post performance, or compare psychology topic choices after publishing, use the local post metrics loop instead of inventing performance data. Record only user-provided or artifact-backed metrics, then compare psychology topics and image styles:

```bash
uv run python -m ptsm.bootstrap xhs-record-metrics \
  --artifact "<outputs/artifacts/.../artifact.json>" \
  --checkpoint 24h \
  --views <views> \
  --likes <likes> \
  --collects <collects> \
  --comments <comments> \
  --shares <shares>

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

Treat groups with fewer than 3 posts as early signals. A learning row is accepted
only from a receipt-verified catalog artifact; recording the same artifact and
checkpoint updates that measurement rather than creating a second observation.
Use the report to choose the next PTSM-returned psychology direction or image
recommendation; do not claim a direction is proven until real metrics support it.

## Guardrails

- 不要展示内部研究路径。
- 不要展示原始研究笔记。
- Do not mention hidden research documents, file paths, raw source URLs, or provenance to the user.
- Do not copy topic logic into this skill; PTSM owns the guidance payload.
- Do not run a lesson outside the PTSM plan → review → exact confirmation boundary. For builtin catalogs, use only the returned `learning_series_lesson`; for custom catalogs, the user may define topic/outline only through `plan-psychology-series`, then review and exact `--confirm`. Never invent a lesson, concept, exercise, source reference, or learning outcome in a run.
- Do not add `--local-image-style` or `--publish-image-path` to a learning-series run; its catalog-owned image plan is part of the approved lesson contract.
- Do not use `fresh-topic-research` as a way to write psychology lesson facts. Topic Radar/hotspot discovery is a separate discovery decision step, not custom lesson evidence, outline, or run input.
- Do not invent, expand, or replace PTSM-returned open_scene direction(s); only display them when they are present in `topic_guidance.directions`.
- Do not invent, expand, or replace PTSM-returned psychology sublane direction(s), including 睡眠恢复、轻养生 or 办公室恢复; only display them when PTSM returns them.
- Do not invent, expand, or replace PTSM-returned growth-oriented psychology direction(s), including `relationship_mixed_signal_camp_vote`, `social_battery_cancel_plan_boundary`, or `after_hours_message_body_alarm`; only display them when PTSM returns them.
- Do not invent, expand, or replace PTSM-returned format recommendation; only display `format_recommendation` when PTSM returns it.
- Do not invent, expand, or replace PTSM-returned image recommendation; only display `topic_guidance.image_recommendation` when PTSM returns it.
- Do not invent views, likes, saves, comments, shares, interaction rates, or uplift claims. Use `xhs-record-metrics` / `xhs-metrics-report` only with real supplied metrics.
- If `run-playbook --caller openclaw` returns `topic_guidance_required`, show the directions and call `run-playbook` again only after direction confirmation with `--guidance-ack`.
- Keep psychology safety boundaries intact: no diagnosis, no treatment promises, no medication advice, and crisis or persistent impairment should be redirected to professional support.
