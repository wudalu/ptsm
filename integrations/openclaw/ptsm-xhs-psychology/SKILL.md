---
name: ptsm-xhs-psychology
description: 当用户想发布、复盘或优化小红书心理学、情绪、关系边界、焦虑、内耗、自我关怀、睡眠恢复、AI 陪伴类内容，创建心理学学习系列、自定义课程目录、继续下一课、查看系列进度或调整系列目录时使用。
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# PTSM XHS Psychology

Use this skill when the user asks OpenClaw to create, prepare, draft, save, publish, review, or optimize a Xiaohongshu post in the psychology domain. Common triggers include 心理学、情绪、焦虑、内耗、边界感、关系、自我关怀、孤独、比较焦虑、睡眠恢复、轻养生、办公室恢复、AI 陪伴、学习系列、课程目录、继续下一课、系列进度、改目录, 提高浏览量、提高点赞、数据复盘, and similar wording.

For non-psychology XHS playbooks, use `ptsm-xhs-topic-guide`; this file remains the psychology-specific wrapper.

## Choose a publication mode

Treat this as a user-facing publication-mode router before showing commands or
drafting content. Resolve a clear request into exactly one of these paths:

- **单篇心理学帖**: the user has one concrete psychology scene or direction and
  wants one post. Use the existing generic `guide-post --scene ...` flow in
  [Required Flow](#required-flow).
- **内置学习系列**: the user wants a structured psychology series without making
  their own curriculum. Query only the builtin `after_work_rumination` roadmap,
  show its `selection_required` response, and wait for an explicit lesson choice.
- **自定义学习系列**: the user wants their own study topic or publication
  directory. Collect a safe topic and optional 2–6 item outline; then use the
  existing custom path: `provision → plan → review → exact confirmation → roadmap`
  before the user explicitly selects a lesson.

If the request is ambiguous, show these three choices and wait. Do not default to a custom series, generate a post, or publish.

### Ordinary-carousel count boundary

If the user explicitly asks for **more than 7 pages/images** (for example 12),
stop and clarify. PTSM supports **one 4–7-page carousel for one topic**, not a
12-image batch. Ask whether the user wants one ordinary carousel or multiple
separately confirmed posts/topics. Do not silently split, loop, repeat, or
promise an unsupported batch. `max_text_units` is per-page copy, not page
count. Never turn this clarification into an automatic multi-run workflow.

For a custom series with no supplied outline, let PTSM produce review-only
proposal material. Do not invent psychology course facts, lesson goals, or a
directory outside PTSM's returned proposal.

### Continue, review progress, or revise a custom series

When the user says **继续下一课** or **看系列进度**, first require the known
series identity and re-query the roadmap. For a custom catalog, show the
returned `series.roadmap`, `series.recommended_next_lesson`, and
`series.production_progress`; for the builtin catalog, show its returned roadmap
only. The recommendation is not automatic selection, generation, or publishing:
wait for an explicit lesson choice and use its returned frozen version and
matching direction.

When the user says **改目录**, do not edit a confirmed catalog or progress file.
Changes to a custom topic, outline, lesson identity, or order require a new
proposal and immutable version, followed by the same exact confirmation and
roadmap flow. Existing versions remain valid historical records.

## Psychology Learning Series

When the user explicitly asks for a psychology learning series, a study topic,
or a specific lesson, use the `learning_series` path instead of the generic
scene flow. There are two valid catalog sources: builtin
`after_work_rumination`, and an immutable `user_confirmed` curriculum that PTSM
created after proposal review. Never turn a scene, hotspot, or operator idea
directly into a runnable lesson.

### Custom topic and outline

Before creating the first custom catalog, run this setup command exactly once
while **all writers are stopped** and a trusted operator exclusively controls
the storage parent. Do not use it as a retry while a plan, confirmation, or run
may still be writing.

```bash
uv run python -m ptsm.bootstrap provision-psychology-learning-storage --format json
```

It creates PTSM's fixed private `proposals`, `confirmations`, `catalogs`, and
`progress` directories. `plan-psychology-series` and
`confirm-psychology-series` never provision missing directories themselves;
they fail closed if that storage is absent or rebound.

1. Let the user provide a safe topic and, if useful, a 2–6 item JSON outline.
Each item may have `id`, `title`, and optional `goal`. Use PTSM to create a
proposal; it is review material, not a runnable catalog.

```bash
uv run python -m ptsm.bootstrap plan-psychology-series \
  --topic "下班后如何把工作从脑子里放下" \
  --curriculum-outline-file outline.json \
  --format json
```

2. Show the safe returned review. The proposal response has `series.lessons`
plus top-level `publication_plan`, `proposal_id`, and exact
`proposal_fingerprint`; it does not have a roadmap. Do not create a lesson,
rewrite order, or invent course evidence while the proposal is unconfirmed. Ask
for exact confirmation.

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

3. Query the confirmed roadmap without a lesson. For a `user_confirmed` custom
catalog, surface `series.roadmap`, `series.publication_plan`,
`series.recommended_next_lesson`, and `series.production_progress`, whose
`kind` is `operator_content_production`. These extra fields only apply to
`user_confirmed` custom catalogs; builtin catalog roadmaps omit them. The
recommendation is not an auto-selection: it is a publication suggestion, PTSM
never auto-selects/generates a lesson, and the progress is not reader learning
progress.

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
operator content-production progress. If `--auto-generate-image` is requested,
only a complete committed carousel can advance that progress; without image
generation, the existing safe content-artifact timing remains unchanged.
Preflight/workflow/image/eval/final-artifact failure cannot advance it.
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
  --auto-generate-image \
  --publish-mode dry-run
```

Use `eval-artifact --artifact <path>` to audit the completed artifact. A missing
or tampered custom catalog/receipt must fail closed; do not expose proposal topic,
outline goal, source, URL, or local path.

If PTSM reports a storage, artifact, or progress race, do not report that lesson
as completed and do not issue path-based cleanup. Runtime deliberately does not
delete or overwrite an untrusted residual by its mutable name; trusted offline maintenance
handles review, cleanup, or rebuild only after all writers have stopped. Production progress is at-least-once: after a safe artifact, a later
rename/durability error can still leave the completion marker visible. Re-query
the roadmap and retry the exact series/version/lesson idempotently instead of
assuming no update occurred. These checks fail closed within a transaction; they
are not a promise of persistent tamper resistance to a continuing same-UID writer
between independent operations.

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
course-contract JSON. PTSM owns the catalog-approved title/cover hook, image
plan, and every carousel page; the guide response exposes only the bounded
carousel structure needed before the run.

historic controlled-template-v1 curricula keep their immutable single-card
contract. builtin and newly confirmed v2 curricula return an exact
`psychology_text_card_v1` carousel. Show only the PTSM-returned `page_count` and
`ordered_roles` before the run. Do not claim that `guide-post` returned `slides`
or page copy. Never write, rewrite, split, reorder, or fill a carousel page in
OpenClaw.

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

5. Then show only the returned `topic_guidance.image_recommendation`: `recommended_backend`, `local_style`, `provider`, `model`, `format_archetype`, `carousel_style`, `role`, `text_density`, `max_text_units`, `page_count`, `ordered_roles`, `reason`, `command_hint`, and `fallback`.

If `recommended_backend` is `provider_image`, describe it as an LLM/provider image recommendation and use the returned `provider` and `model`. If `recommended_backend` is `local_social_screenshot`, describe the returned local style such as `wechat_chat`, `iphone_notes`, or `note_card`. Do not add extra image styles, providers, or model names.

For `format_archetype=text_carousel`, explain that PTSM will locally render one
topic across the returned 4–7 ordered roles with `psychology_text_card_v1`.
The cover remains low density and inner pages remain bounded text cards. Do not
author `slides`; the run must use the exact PTSM-reviewed plan.

After an ordinary run, an outer relay may forward images only when the returned
`carousel_delivery.status=ready`. Use its exact ordered `attachments` as one
complete set, and retain the canonical `page_sha256` (page content) and
`file_sha256` (PNG bytes) checks for every attachment. PTSM does not own
external chat/IM delivery: `ready` means that local render, canonical receipt,
and asset ledger are complete; it does not mean the user received any image.
Do not expose local paths to the user. If the relay fails, report relay failure
rather than PTSM/user delivery success.

6. Generate through PTSM only after the direction is chosen or confirmed. Pass the chosen direction's id as `--topic-direction-id`.

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --caller openclaw \
  --guidance-ack \
  --scene "<confirmed psychology direction and concrete scene>" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --topic-direction-id "<chosen direction id>" \
  --auto-generate-image \
  --publish-mode dry-run
```

Treat `psychology_carousel_generation_failed` as a whole-set failure: do not
publish a subset, do not claim the lesson advanced, and retry through PTSM after
the underlying local generation or asset-ledger issue is fixed. It has no
`carousel_delivery.status=ready`, does not consume the ordinary recent-12
inner-page window, and must never be described as delivered.

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
  --group-by carousel_style

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
Use returned `image_count` and `carousel_style` to distinguish a 4–7 page text
carousel from a historic/single cover.
Use the report to choose the next PTSM-returned psychology direction or image
recommendation; do not claim a direction is proven until real metrics support it.

## Guardrails

- 不要展示内部研究路径。
- 不要展示原始研究笔记。
- Do not mention hidden research documents, file paths, raw source URLs, or provenance to the user.
- Do not copy topic logic into this skill; PTSM owns the guidance payload.
- Do not run a lesson outside the PTSM plan → review → exact confirmation boundary. For builtin catalogs, use only the returned `learning_series_lesson`; for custom catalogs, first use `provision-psychology-learning-storage` only during trusted exclusive setup, then let the user define topic/outline through `plan-psychology-series`, review, and exact `--confirm`. Never invent a lesson, concept, exercise, source reference, or learning outcome in a run.
- Do not add `--local-image-style` or `--publish-image-path` to a learning-series run; its catalog-owned image plan is part of the approved lesson contract.
- Do not use `fresh-topic-research` as a way to write psychology lesson facts. Topic Radar/hotspot discovery is a separate discovery decision step, not custom lesson evidence, outline, or run input.
- Do not invent, expand, or replace PTSM-returned open_scene direction(s); only display them when they are present in `topic_guidance.directions`.
- Do not invent, expand, or replace PTSM-returned psychology sublane direction(s), including 睡眠恢复、轻养生 or 办公室恢复; only display them when PTSM returns them.
- Do not invent, expand, or replace PTSM-returned growth-oriented psychology direction(s), including `relationship_mixed_signal_camp_vote`, `social_battery_cancel_plan_boundary`, or `after_hours_message_body_alarm`; only display them when PTSM returns them.
- Do not invent, expand, or replace PTSM-returned format recommendation; only display `format_recommendation` when PTSM returns it.
- Do not invent, expand, or replace PTSM-returned image recommendation; only display `topic_guidance.image_recommendation` when PTSM returns it.
- Before the run, show only the PTSM-returned `page_count` and `ordered_roles`; do not claim that `guide-post` returned `slides` or page copy. Never write, rewrite, split, reorder, or fill a carousel page; one carousel represents one topic. After a successful ordinary run, use only `carousel_delivery.status=ready` for internal relay handoff; do not display its local attachment paths to the user or turn ready into a delivery claim.
- Do not invent views, likes, saves, comments, shares, interaction rates, or uplift claims. Use `xhs-record-metrics` / `xhs-metrics-report` only with real supplied metrics.
- If `run-playbook --caller openclaw` returns `topic_guidance_required`, show the directions and call `run-playbook` again only after direction confirmation with `--guidance-ack`.
- Keep psychology safety boundaries intact: no diagnosis, no treatment promises, no medication advice, and crisis or persistent impairment should be redirected to professional support.
